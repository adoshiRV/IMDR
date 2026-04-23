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

from imdr.config.pipeline_config import get_pipeline_config
from imdr.config.settings import Settings
from imdr.connectors.citi_quota import TagQuotaTracker
from imdr.connectors.citi_velocity import CitiVelocityClient
from imdr.connectors.mssql import MSSQLConnector
from imdr.connectors.reader import AnalyticalReader
from imdr.domains.rates.cache import CurveQuoteCache
from imdr.domains.rates.extractors import CitiVelocityRatesExtractor
from imdr.connectors.bulk import chunked_bulk_merge
from imdr.domains.rates.repository import (
    RatesCurveRepository,
    RatesObservationRepository,
    _RATES_OBS_SPEC,
)
from imdr.domains.rates.store import write as parquet_write
from imdr.domains.rates.utils import curve_entry_to_create
from imdr.healthchecks.base import HealthCheck
from imdr.healthchecks.checks import (
    DuplicateCheck,
    FreshnessCheck,
    NullCheck,
    RowCountCheck,
)
from imdr.healthchecks.base import CheckStatus
from imdr.healthchecks.quality import SymbolRangeCheck
from imdr.models.frequency import DimFrequency
from imdr.models.rates import RatesObservation
from imdr.pipelines.base import BasePipeline
from imdr.schemas.rates import RatesObservationCreate
from imdr.universe.rates import RatesUniverse, get_rates_universe
from sqlalchemy import select

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
        use_cache: bool = True,
        chunk_size: int | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        quota_tracker_path: str | None = None,
    ) -> None:
        super().__init__(connector)
        self._settings = settings
        self._universe = universe
        self._config = get_pipeline_config(self.pipeline_name)
        self._start = start
        self._end = end
        self._quotes = quotes or self._config.default_quotes or ["par"]
        self._frequency = frequency
        self._curves = curves
        self._use_cache = use_cache
        self._chunk_size = chunk_size
        self._client_id = client_id
        self._client_secret = client_secret
        self._quota_tracker_path = quota_tracker_path
        self._raw_df: pd.DataFrame | None = None
        self._metadata_freshness: dict[str, Any] | None = None
        self._extraction_errors: list[dict] = []
        self._quota_usage: int | None = None

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
        cache: CurveQuoteCache | None = None
        if self._use_cache:
            cache_dir = self._settings.cache_dir or "data/cache"
            cache = CurveQuoteCache(cache_dir)
            cache.load()

        tracker = TagQuotaTracker(
            quota_limit=self._settings.citi_tag_quota_limit,
            tracker_path=self._quota_tracker_path
            or self._settings.citi_tag_quota_file
            or None,
        )

        with CitiVelocityClient(
            self._settings,
            client_id=self._client_id,
            client_secret=self._client_secret,
        ) as client:
            # Freshness check — sample metadata before pulling data
            self._metadata_freshness = self._check_metadata_freshness(client)

            extractor = CitiVelocityRatesExtractor(
                client=client,
                settings=self._settings,
                universe=self._universe,
                cache=cache,
                quota_tracker=tracker,
            )
            df = extractor.extract(
                start=self._start,
                end=self._end,
                quotes=self._quotes,
                frequency=self._frequency,
                curves=self._curves,
            )

        self._extraction_errors = extractor._errors
        self._quota_usage = tracker.current_usage()
        self._raw_df = df
        _log.info("extract_complete", rows=len(df),
                   extraction_errors=len(self._extraction_errors),
                   quota_used=self._quota_usage)
        return df

    def transform(self, raw: pd.DataFrame) -> list[RatesObservationCreate]:
        """Ensure dim_curve is populated, resolve curve_ids, validate via Pydantic."""
        # Seed + cache in a single session to avoid N+1 round-trips
        curves_to_seed = [curve_entry_to_create(e) for e in self._universe.all_curves()]
        with self._connector.session() as session:
            curve_repo = RatesCurveRepository(session)
            inserted = curve_repo.bulk_seed_from_universe(curves_to_seed)
            if inserted:
                _log.info("dim_curve_seeded", new_curves=inserted, total=len(curves_to_seed))

            # Build curve_id cache (same session — sees freshly seeded rows)
            curve_id_cache: dict[tuple[str, str], int] = {}
            for curve_entry in curve_repo.all():
                curve_id_cache[(curve_entry.ccy, curve_entry.curve)] = curve_entry.id

            # Resolve frequency_id once (FK to dbo.dim_frequency; NOT NULL in fact_observation)
            freq_code = self._frequency.upper()
            frequency = session.execute(
                select(DimFrequency).where(DimFrequency.frequency_code == freq_code)
            ).scalar_one_or_none()
            if frequency is None:
                raise RuntimeError(
                    f"Frequency '{freq_code}' missing from dbo.dim_frequency — "
                    "run migration 023_create_dim_frequency.sql"
                )
            frequency_id = frequency.id

        if raw.empty:
            return []

        observations: list[RatesObservationCreate] = []

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
                frequency_id=frequency_id,
            )
            observations.append(obs)

        if skipped:
            _log.warning("transform_skipped_unmapped_curves", count=skipped)
        _log.info("transform_complete", observations=len(observations),
                  frequency=freq_code, frequency_id=frequency_id)
        return observations

    def load(self, data: list[RatesObservationCreate]) -> int:
        """Bulk upsert observations to SQL Server."""
        if not data:
            return 0

        if self._chunk_size:
            count = chunked_bulk_merge(
                self._connector, _RATES_OBS_SPEC, data, self._chunk_size,
            )
        else:
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

        # Per-quote quality check (replaces global ValueRangeCheck)
        ranges = {qt: (r.min, r.max) for qt, r in self._universe.expected_ranges.items()}
        if ranges:
            check = SymbolRangeCheck(ranges, value_column="value", symbol_column="quote")
            reader = AnalyticalReader(self._connector)
            where = f"AND [ts] >= '{self._start:%Y-%m-%d}' AND [ts] <= '{self._end:%Y-%m-%d}'"
            qr = check.run(reader, self._config.fully_qualified_table, where=where)
            if qr.status != CheckStatus.PASSED:
                _log.warning("quality_flag_quote_range", status=qr.status.value, message=qr.message)
            else:
                _log.info("quality_passed_quote_range")

    def get_health_checks(self) -> list[HealthCheck]:
        cfg = self._config.health_checks
        return [
            RowCountCheck(RatesObservation, self._config.date_column, cfg.row_count_min),
            NullCheck(RatesObservation, self._config.required_columns, self._config.date_column),
            DuplicateCheck(RatesObservation, self._config.unique_columns, self._config.date_column),
            FreshnessCheck(RatesObservation, "created_at", cfg.max_staleness_hours),
        ]

    def get_run_context(self) -> dict[str, Any]:
        ctx: dict[str, Any] = {
            "run_date": self._start.date(),
        }
        if self._metadata_freshness:
            ctx["metadata_freshness"] = self._metadata_freshness
        return ctx
