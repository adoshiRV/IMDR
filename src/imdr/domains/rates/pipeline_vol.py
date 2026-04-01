"""Rates swaption vol pipeline — extract from Citi Velocity, load to SQL + parquet.

Usage:
    python -m scripts.run_pipeline rates.vol --start 2026-03-10 --end 2026-03-10
    python -m scripts.run_pipeline rates.vol --start 2024-01-01 --end 2024-12-31
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
from imdr.domains.rates.extractors_vol import CitiVelocityRatesVolExtractor
from imdr.connectors.bulk import chunked_bulk_merge
from imdr.domains.rates.repository_vol import (
    RatesSwaptionVolRepository,
    RatesVolSurfaceRepository,
    _SWAPTION_VOL_SPEC,
)
from imdr.domains.rates.store_vol import write as parquet_write
from imdr.healthchecks.base import HealthCheck
from imdr.healthchecks.checks import (
    DuplicateCheck,
    FreshnessCheck,
    NullCheck,
    RowCountCheck,
)
from imdr.models.rates_vol import RatesFactSwaptionVol
from imdr.pipelines.base import BasePipeline
from imdr.schemas.rates_vol import RatesSwaptionVolCreate, RatesVolSurfaceCreate
from imdr.universe.rates import RatesUniverse

_log = structlog.get_logger("RatesVolPipeline")


class RatesVolPipeline(BasePipeline[pd.DataFrame, list[RatesSwaptionVolCreate], int]):
    """ETL pipeline: Citi Velocity swaption vol -> SQL Server + parquet."""

    pipeline_name = "rates.vol"
    domain = "rates"

    def __init__(
        self,
        connector: MSSQLConnector,
        settings: Settings,
        universe: RatesUniverse,
        start: datetime,
        end: datetime,
        currencies: list[str] | None = None,
        chunk_size: int | None = None,
    ) -> None:
        super().__init__(connector)
        self._settings = settings
        self._universe = universe
        self._config = get_pipeline_config(self.pipeline_name)
        self._start = start
        self._end = end
        self._currencies = currencies
        self._chunk_size = chunk_size
        self._raw_df: pd.DataFrame | None = None
        self._quality_results: list[dict[str, Any]] = []
        self._extraction_errors: list[dict] = []
        self._quota_usage: int | None = None

    def extract(self) -> pd.DataFrame:
        """Fetch vol surfaces from Citi Velocity Historical API."""
        tracker = TagQuotaTracker(
            quota_limit=self._settings.citi_tag_quota_limit,
            tracker_path=self._settings.citi_tag_quota_file or None,
        )

        with CitiVelocityClient(self._settings) as client:
            extractor = CitiVelocityRatesVolExtractor(
                client=client,
                settings=self._settings,
                universe=self._universe,
                quota_tracker=tracker,
            )
            df = extractor.extract(self._start, self._end, self._currencies)

        self._extraction_errors = extractor._errors
        self._quota_usage = tracker.current_usage()
        self._raw_df = df
        _log.info("extract_complete", rows=len(df),
                   extraction_errors=len(self._extraction_errors),
                   quota_used=self._quota_usage)
        return df

    def transform(self, raw: pd.DataFrame) -> list[RatesSwaptionVolCreate]:
        """Seed dim_vol_surface, resolve surface_ids, validate via Pydantic."""
        # 1. Auto-seed dim_vol_surface
        seed_entries = [
            RatesVolSurfaceCreate(**e) for e in self._universe.vol_surface_create_entries()
        ]
        with self._connector.session() as session:
            surface_repo = RatesVolSurfaceRepository(session)
            inserted = surface_repo.bulk_seed_from_universe(seed_entries)
            if inserted:
                _log.info("dim_vol_surface_seeded", new_surfaces=inserted)

            # 2. Build surface_id cache
            surface_id_cache: dict[tuple[str, str, str, str, str], int] = {}
            for s in surface_repo.all():
                key = (s.ccy, s.data_type, s.quote_type, s.vol_window, s.freq)
                surface_id_cache[key] = s.id

        if raw.empty:
            return []

        # 3. Resolve surface_ids, validate via Pydantic
        observations: list[RatesSwaptionVolCreate] = []
        skipped = 0
        for _, row in raw.iterrows():
            key = (row["ccy"], row["data_type"], row["quote_type"],
                   row["vol_window"], row["freq"])
            surface_id = surface_id_cache.get(key)
            if surface_id is None:
                skipped += 1
                continue
            observations.append(RatesSwaptionVolCreate(
                surface_id=surface_id,
                obs_date=row["ts"].date() if hasattr(row["ts"], "date") else row["ts"],
                option_expiry=row["option_expiry"],
                swap_tenor=row["swap_tenor"],
                value=row["value"],
            ))

        if skipped:
            _log.warning("transform_skipped_unmapped_surfaces", count=skipped)
        _log.info("transform_complete", observations=len(observations))
        return observations

    def load(self, data: list[RatesSwaptionVolCreate]) -> int:
        """Bulk upsert vol observations to SQL Server."""
        if not data:
            return 0

        if self._chunk_size:
            count = chunked_bulk_merge(
                self._connector, _SWAPTION_VOL_SPEC, data, self._chunk_size,
            )
        else:
            with self._connector.session() as session:
                repo = RatesSwaptionVolRepository(session)
                count = repo.bulk_upsert(data)

        _log.info("load_complete", rows_loaded=count)
        return count

    def post_load(self, result: int, data: list[RatesSwaptionVolCreate]) -> None:
        """Write to parquet archive + run quality checks."""
        if self._raw_df is None or self._raw_df.empty:
            return

        manifest: dict[str, Any] = {
            "source": "citi_velocity_historical",
            "range": [str(self._start.date()), str(self._end.date())],
            "rows_loaded": result,
        }
        written = parquet_write(self._raw_df, manifest=manifest)
        _log.info("parquet_archive_complete", files_written=len(written))

        self._run_quality_checks()

    def get_health_checks(self) -> list[HealthCheck]:
        cfg = self._config.health_checks
        return [
            RowCountCheck(RatesFactSwaptionVol, self._config.date_column, cfg.row_count_min),
            NullCheck(RatesFactSwaptionVol, self._config.required_columns, self._config.date_column),
            DuplicateCheck(RatesFactSwaptionVol, self._config.unique_columns, self._config.date_column),
            FreshnessCheck(RatesFactSwaptionVol, "created_at", cfg.max_staleness_hours),
        ]

    def get_run_context(self) -> dict[str, Any]:
        return {"run_date": self._start.date()}

    # ── Quality checks ──────────────────────────────────────────

    def _run_quality_checks(self) -> None:
        """Run vol-specific quality checks (flag, don't block)."""
        from imdr.healthchecks.base import CheckStatus
        from imdr.healthchecks.quality import (
            CompositeRangeCheck,
            PercentageChangeCheck,
            RobustStatisticalOutlierCheck,
        )

        vol_ranges = self._universe.vol_quality_ranges()
        cleaning = self._config.cleaning
        reader = AnalyticalReader(self._connector)
        table = self._config.fully_qualified_table
        where = (
            f"AND [{self._config.date_column}] >= '{self._start:%Y-%m-%d}' "
            f"AND [{self._config.date_column}] <= '{self._end:%Y-%m-%d}'"
        )

        # CompositeRangeCheck needs data_type/quote_type from dim_vol_surface,
        # but the fact table only has surface_id.  Use a joined source.
        range_table = (
            "(SELECT f.*, d.data_type, d.quote_type "
            "FROM [rates].[fact_swaption_vol] f "
            "JOIN [rates].[dim_vol_surface] d ON f.surface_id = d.id) AS fv"
        )
        range_where = (
            f"AND [{self._config.date_column}] >= '{self._start:%Y-%m-%d}' "
            f"AND [{self._config.date_column}] <= '{self._end:%Y-%m-%d}'"
        )

        # Each tuple: (check, source_table, where_clause)
        checks: list[tuple] = [
            (
                CompositeRangeCheck(
                    range_map=vol_ranges,
                    key_columns=["data_type", "quote_type"],
                    value_column="value",
                ),
                range_table,  # joined source with dim columns
                range_where,
            ),
            (
                PercentageChangeCheck(
                    value_column="value",
                    group_columns=["surface_id", "option_expiry", "swap_tenor"],
                    ts_column=self._config.date_column,
                    threshold_pct=cleaning.pct_threshold,
                    min_abs_value=0.5,
                ),
                table,
                where,
            ),
            (
                RobustStatisticalOutlierCheck(
                    value_column="value",
                    group_columns=["surface_id", "option_expiry", "swap_tenor"],
                    n_mad=cleaning.n_mad,
                    trailing_months=cleaning.trailing_months,
                    ts_column=self._config.date_column,
                    min_obs=cleaning.min_obs,
                ),
                table,
                where,
            ),
        ]

        for check, src_table, src_where in checks:
            try:
                qr = check.run(reader, src_table, where=src_where)
                self._quality_results.append({
                    "check": qr.check_name,
                    "status": qr.status.value,
                    "message": qr.message,
                    "flagged_count": qr.meta.get("total_violations")
                    or qr.meta.get("outlier_count")
                    or qr.meta.get("flagged_count"),
                })
                if qr.status != CheckStatus.PASSED:
                    _log.warning(
                        "quality_flag",
                        check=qr.check_name,
                        status=qr.status.value,
                        message=qr.message,
                    )
            except Exception:
                _log.exception("quality_check_failed", check=type(check).__name__)
