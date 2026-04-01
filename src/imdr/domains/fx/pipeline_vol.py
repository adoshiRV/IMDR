"""FX vol pipeline — extract from Citi Velocity, load to SQL + parquet.

Usage:
    python -m scripts.run_pipeline fx.vol --start 2026-03-10 --end 2026-03-10
    python -m scripts.run_pipeline fx.vol --start 2024-01-01 --end 2024-12-31
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
from imdr.domains.fx.extractors_vol import CitiVelocityFXVolExtractor
from imdr.connectors.bulk import chunked_bulk_merge
from imdr.domains.fx.repository_vol import (
    FXCurrencyPairRepository,
    FXVolRepository,
    _FX_VOL_SPEC,
)
from imdr.domains.fx.store_vol import write as parquet_write
from imdr.healthchecks.base import HealthCheck
from imdr.healthchecks.checks import (
    DuplicateCheck,
    FreshnessCheck,
    NullCheck,
    RowCountCheck,
    ValueRangeCheck,
)
from imdr.models.fx_vol import FXFactVol
from imdr.pipelines.base import BasePipeline
from imdr.schemas.fx_vol import FXVolCreate
from imdr.universe.fx import FXUniverse

_log = structlog.get_logger("FXVolPipeline")


class FXVolPipeline(BasePipeline[pd.DataFrame, list[FXVolCreate], int]):
    """ETL pipeline: Citi Velocity FX vol → SQL Server + parquet."""

    pipeline_name = "fx.vol"
    domain = "fx"

    def __init__(
        self,
        connector: MSSQLConnector,
        settings: Settings,
        universe: FXUniverse,
        start: datetime,
        end: datetime,
        pairs: list[tuple[str, str]] | None = None,
        chunk_size: int | None = None,
    ) -> None:
        super().__init__(connector)
        self._settings = settings
        self._universe = universe
        self._config = get_pipeline_config(self.pipeline_name)
        self._start = start
        self._end = end
        self._pairs = pairs
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
            extractor = CitiVelocityFXVolExtractor(
                client=client,
                settings=self._settings,
                universe=self._universe,
                quota_tracker=tracker,
            )
            df = extractor.extract(self._start, self._end, self._pairs)

        self._extraction_errors = extractor._errors
        self._quota_usage = tracker.current_usage()
        self._raw_df = df
        _log.info("extract_complete", rows=len(df),
                   extraction_errors=len(self._extraction_errors),
                   quota_used=self._quota_usage)
        return df

    def transform(self, raw: pd.DataFrame) -> list[FXVolCreate]:
        """Seed dim_currency_pair, resolve pair_ids, validate via Pydantic."""
        # 1. Auto-seed dim_currency_pair (same pattern as rates dim_curve seeding)
        pairs_to_seed = self._universe.vol_pair_create_entries()
        with self._connector.session() as session:
            pair_repo = FXCurrencyPairRepository(session)
            inserted = pair_repo.bulk_seed_from_universe(pairs_to_seed)
            if inserted:
                _log.info("dim_currency_pair_seeded", new_pairs=inserted)

            # 2. Build pair_id cache (same session — sees freshly seeded rows)
            pair_id_cache: dict[tuple[str, str], int] = {}
            for pair in pair_repo.all():
                pair_id_cache[(pair.base_ccy, pair.quote_ccy)] = pair.id

        if raw.empty:
            return []

        # 3. Resolve pair_ids, validate via Pydantic
        observations: list[FXVolCreate] = []
        skipped = 0
        for _, row in raw.iterrows():
            pair_id = pair_id_cache.get((row["base_ccy"], row["quote_ccy"]))
            if pair_id is None:
                skipped += 1
                continue
            observations.append(FXVolCreate(
                pair_id=pair_id,
                obs_date=row["ts"].date() if hasattr(row["ts"], "date") else row["ts"],
                strike=row["strike"],
                tenor=row["tenor"],
                vol_type=row["vol_type"],
                value=row["value"],
            ))

        if skipped:
            _log.warning("transform_skipped_unmapped_pairs", count=skipped)
        _log.info("transform_complete", observations=len(observations))
        return observations

    def load(self, data: list[FXVolCreate]) -> int:
        """Bulk upsert vol observations to SQL Server."""
        if not data:
            return 0

        if self._chunk_size:
            count = chunked_bulk_merge(
                self._connector, _FX_VOL_SPEC, data, self._chunk_size,
            )
        else:
            with self._connector.session() as session:
                repo = FXVolRepository(session)
                count = repo.bulk_upsert(data)

        _log.info("load_complete", rows_loaded=count)
        return count

    def post_load(self, result: int, data: list[FXVolCreate]) -> None:
        """Write to parquet archive + run domain-specific quality checks."""
        if self._raw_df is None or self._raw_df.empty:
            return

        manifest: dict[str, Any] = {
            "source": "citi_velocity_historical",
            "range": [str(self._start.date()), str(self._end.date())],
            "rows_loaded": result,
        }
        written = parquet_write(self._raw_df, manifest=manifest)
        _log.info("parquet_archive_complete", files_written=len(written))

        # Domain-specific quality checks (flag, don't block)
        self._run_quality_checks()

    def get_health_checks(self) -> list[HealthCheck]:
        cfg = self._config.health_checks
        checks: list[HealthCheck] = [
            RowCountCheck(FXFactVol, self._config.date_column, cfg.row_count_min),
            NullCheck(FXFactVol, self._config.required_columns, self._config.date_column),
            DuplicateCheck(FXFactVol, self._config.unique_columns, self._config.date_column),
            FreshnessCheck(FXFactVol, "created_at", cfg.max_staleness_hours),
        ]
        for col_name, vr in cfg.value_ranges.items():
            checks.append(
                ValueRangeCheck(FXFactVol, col_name, vr.min, vr.max, self._config.date_column)
            )
        return checks

    def get_run_context(self) -> dict[str, Any]:
        return {"run_date": self._start.date()}

    # ── Domain-specific quality checks ─────────────────────────

    def _run_quality_checks(self) -> None:
        """Run vol-specific quality checks (flag, don't block)."""
        from imdr.healthchecks.base import CheckStatus
        from imdr.healthchecks.quality import (
            CompositeRangeCheck,
            PercentageChangeCheck,
            RobustStatisticalOutlierCheck,
        )

        vol_quality = self._universe.vol_quality_config()
        cleaning = self._config.cleaning
        reader = AnalyticalReader(self._connector)
        table = self._config.fully_qualified_table
        where = (
            f"AND [{self._config.date_column}] >= '{self._start:%Y-%m-%d}' "
            f"AND [{self._config.date_column}] <= '{self._end:%Y-%m-%d}'"
        )

        checks = [
            # 1. Strike+vol_type composite range (includes butterfly positivity)
            CompositeRangeCheck(
                range_map=vol_quality.ranges,
                key_columns=["strike", "vol_type"],
                value_column="value",
            ),
            # 2. Day-over-day % change — flag unusual vol moves
            #    min_abs_value=0.5 skips near-zero prev values (RR/STR)
            #    where pct change is meaningless
            PercentageChangeCheck(
                value_column="value",
                group_columns=["pair_id", "strike", "tenor", "vol_type"],
                ts_column=self._config.date_column,
                threshold_pct=cleaning.pct_threshold,
                min_abs_value=0.5,
            ),
            # 3. Robust outlier detection — MAD-based (fat-tail resistant)
            RobustStatisticalOutlierCheck(
                value_column="value",
                group_columns=["pair_id", "strike", "tenor", "vol_type"],
                n_mad=cleaning.n_mad,
                trailing_months=cleaning.trailing_months,
                ts_column=self._config.date_column,
                min_obs=cleaning.min_obs,
            ),
        ]

        for check in checks:
            try:
                qr = check.run(reader, table, where=where)
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
