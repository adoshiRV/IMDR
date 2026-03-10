"""Rates historical pipeline — extract from Citi Velocity, load to SQL + parquet.

Usage:
    python -m scripts.run_pipeline rates.historical --start 2024-01-01 --end 2024-01-31
    python -m scripts.run_pipeline rates.historical --start 2024-01-01 --end 2024-01-31 --quotes par spread
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd
import structlog

from imdr.config.settings import Settings
from imdr.connectors.citi_velocity import CitiVelocityClient
from imdr.connectors.mssql import MSSQLConnector
from imdr.domains.rates.extractors import CitiVelocityRatesExtractor
from imdr.domains.rates.repository import RatesCurveRepository, RatesObservationRepository
from imdr.domains.rates.store import write as parquet_write
from imdr.healthchecks.base import HealthCheck
from imdr.healthchecks.checks import RowCountCheck
from imdr.pipelines.base import BasePipeline
from imdr.schemas.rates import RatesObservationCreate
from imdr.universe.rates import RatesUniverse, get_rates_universe

_log = structlog.get_logger("RatesHistoricalPipeline")

# Sample tags for metadata freshness check (one per major region)
_FRESHNESS_SAMPLE_TAGS = [
    "RATES.OIS.USD_SOFR.PAR.5Y",       # Americas
    "RATES.OIS.EUR_EUROSTR.PAR.5Y",     # Europe
    "RATES.OIS.JPY_TONAR.PAR.5Y",       # Asia
]


class RatesHistoricalPipeline(BasePipeline[pd.DataFrame, list[RatesObservationCreate], int]):
    """ETL pipeline: Citi Velocity → SQL Server + Hive-partitioned parquet."""

    pipeline_name = "rates.historical"
    domain = "rates"

    def __init__(
        self,
        connector: MSSQLConnector,
        settings: Settings,
        universe: RatesUniverse,
        start: datetime,
        end: datetime,
        quotes: list[str] | None = None,
        frequency: str = "DAILY",
        curves: list[tuple[str, str]] | None = None,
    ) -> None:
        super().__init__(connector)
        self._settings = settings
        self._universe = universe
        self._start = start
        self._end = end
        self._quotes = quotes or ["par"]
        self._frequency = frequency
        self._curves = curves
        self._raw_df: pd.DataFrame | None = None
        self._metadata_freshness: dict[str, Any] | None = None

    def _check_metadata_freshness(self, client: CitiVelocityClient) -> dict[str, Any]:
        """Query Citi Metadata API to check when sample tags were last updated.

        Returns a dict with per-tag modifiedTimes for audit logging.
        This is a pre-extract freshness check — not a blocker, just recorded.
        """
        try:
            resp = client.fetch_metadata(_FRESHNESS_SAMPLE_TAGS)
            body = resp.get("body", {})

            freshness: dict[str, Any] = {}
            for tag in _FRESHNESS_SAMPLE_TAGS:
                tag_info = body.get(tag, {})
                modified = tag_info.get("modifiedTimes", [])
                freshness[tag] = {
                    "last_modified": modified[0] if modified else None,
                    "recent_updates": len(modified),
                }
                if modified:
                    _log.info("metadata_freshness", tag=tag, last_modified=modified[0])
                else:
                    _log.warning("metadata_no_update", tag=tag)

            return freshness

        except Exception:
            _log.warning("metadata_freshness_check_failed", exc_info=True)
            return {"error": "metadata check failed"}

    def extract(self) -> pd.DataFrame:
        """Fetch from Citi Velocity Historical API (with pre-extract freshness check)."""
        with CitiVelocityClient(self._settings) as client:
            # Freshness check — sample metadata before pulling data
            self._metadata_freshness = self._check_metadata_freshness(client)

            extractor = CitiVelocityRatesExtractor(
                client=client,
                settings=self._settings,
                universe=self._universe,
            )
            df = extractor.extract(
                start=self._start,
                end=self._end,
                quotes=self._quotes,
                frequency=self._frequency,
                curves=self._curves,
            )
        self._raw_df = df
        _log.info("extract_complete", rows=len(df))
        return df

    def transform(self, raw: pd.DataFrame) -> list[RatesObservationCreate]:
        """Resolve curve_ids and validate via Pydantic."""
        if raw.empty:
            return []

        observations: list[RatesObservationCreate] = []

        with self._connector.session() as session:
            curve_repo = RatesCurveRepository(session)

            # Build curve_id cache
            curve_id_cache: dict[tuple[str, str], int] = {}
            for curve_entry in curve_repo.all():
                curve_id_cache[(curve_entry.ccy, curve_entry.curve)] = curve_entry.id

        skipped = 0
        for _, row in raw.iterrows():
            key = (row["ccy"], row["curve"])
            curve_id = curve_id_cache.get(key)
            if curve_id is None:
                skipped += 1
                continue

            obs = RatesObservationCreate(
                curve_id=curve_id,
                ts=row["ts"],
                quote=row["quote"],
                tenor=row["tenor"],
                value=row["value"],
            )
            observations.append(obs)

        if skipped:
            _log.warning("transform_skipped_unmapped_curves", count=skipped)
        _log.info("transform_complete", observations=len(observations))
        return observations

    def load(self, data: list[RatesObservationCreate]) -> int:
        """Bulk upsert observations to SQL Server."""
        if not data:
            return 0

        with self._connector.session() as session:
            repo = RatesObservationRepository(session)
            count = repo.bulk_upsert(data)

        _log.info("load_complete", rows_loaded=count)
        return count

    def post_load(self, result: int, data: list[RatesObservationCreate]) -> None:
        """Write to Hive-partitioned parquet archive."""
        if self._raw_df is None or self._raw_df.empty:
            return

        manifest: dict[str, Any] = {
            "source": "citi_velocity_historical",
            "range": [str(self._start.date()), str(self._end.date())],
            "frequency": self._frequency,
            "quotes": self._quotes,
            "rows_loaded": result,
        }
        if self._metadata_freshness:
            manifest["metadata_freshness"] = self._metadata_freshness
        written = parquet_write(self._raw_df, manifest=manifest)
        _log.info("parquet_archive_complete", files_written=len(written))

    def get_health_checks(self) -> list[HealthCheck]:
        return [
            RowCountCheck(
                schema="rates",
                table="fact_observation",
                date_column="ts",
                min_rows=1,
            ),
        ]

    def get_run_context(self) -> dict[str, Any]:
        ctx: dict[str, Any] = {
            "run_date": self._start.date(),
        }
        if self._metadata_freshness:
            ctx["metadata_freshness"] = self._metadata_freshness
        return ctx
