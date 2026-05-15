"""FX rate pipeline — Citi Velocity spot + forward outrights + forward points.

Usage:
    python -m scripts.run_pipeline fx.citi_rate --start 2026-04-21 --end 2026-04-21
    python -m scripts.run_pipeline fx.citi_rate --start 2024-01-01 --end 2024-12-31
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pandas as pd
import structlog
from sqlalchemy import select

from imdr.config.pipeline_config import get_pipeline_config
from imdr.config.settings import Settings
from imdr.connectors.bulk import chunked_bulk_merge
from imdr.connectors.citi_quota import TagQuotaTracker
from imdr.connectors.citi_velocity import CitiVelocityClient
from imdr.connectors.mssql import MSSQLConnector
from imdr.connectors.reader import AnalyticalReader
from imdr.domains.fx._parquet_store import write_partitioned_parquet
from imdr.domains.fx.extractors_rate import CitiVelocityFXRateExtractor
from imdr.domains.fx.rate_translate import WIDE_COLUMNS
from imdr.domains.fx.repository_rate import FXRateRepository, FX_RATE_SPEC
from imdr.domains.fx.repository_vol import FXCurrencyPairRepository
from imdr.healthchecks.base import HealthCheck
from imdr.healthchecks.checks import (
    DuplicateCheck,
    FreshnessCheck,
    NullCheck,
    RowCountCheck,
    ValueRangeCheck,
)
from imdr.models.fx_rate import FXFactFXRate
from imdr.models.frequency import DimFrequency
from imdr.models.vendor import DimVendor
from imdr.pipelines.base import BasePipeline
from imdr.schemas.fx_rate import FXRateCreate
from imdr.universe.fx import FXUniverse

_log = structlog.get_logger("FXRatePipeline")

VENDOR_CODE = "citi_velocity"


class FXRatePipeline(BasePipeline[pd.DataFrame, list[FXRateCreate], int]):
    """ETL pipeline: Citi Velocity FX rates → fx.fact_fx_rate + parquet."""

    pipeline_name = "fx.citi_rate"
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
        frequency: str = "DAILY",
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
        self._pairs = pairs
        self._chunk_size = chunk_size
        self._frequency = frequency
        self._client_id = client_id
        self._client_secret = client_secret
        self._quota_tracker_path = quota_tracker_path
        self._raw_df: pd.DataFrame | None = None
        self._quality_results: list[dict[str, Any]] = []
        self._extraction_errors: list[dict] = []
        self._tag_errors: list[dict] = []
        self._quota_usage: int | None = None

    def extract(self) -> pd.DataFrame:
        """Fetch spot + forward rates from Citi Velocity Historical API."""
        tracker = TagQuotaTracker(
            quota_limit=self._settings.citi_tag_quota_limit,
            tracker_path=self._quota_tracker_path
            or self._settings.citi_tag_quota_file
            or None,
        )

        extractor: CitiVelocityFXRateExtractor | None = None
        with CitiVelocityClient(
            self._settings,
            client_id=self._client_id,
            client_secret=self._client_secret,
        ) as client:
            extractor = CitiVelocityFXRateExtractor(
                client=client,
                settings=self._settings,
                universe=self._universe,
                quota_tracker=tracker,
            )
            # Alias the extractor's diagnostic lists so they're populated
            # in-place even if extract() raises (e.g. TagQuotaExceeded).
            self._extraction_errors = extractor.errors
            self._tag_errors = extractor.tag_errors
            try:
                df = extractor.extract(
                    self._start, self._end, self._pairs, frequency=self._frequency,
                )
            finally:
                self._quota_usage = tracker.current_usage()

        self._raw_df = df
        _log.info(
            "extract_complete",
            rows=len(df),
            extraction_errors=len(self._extraction_errors),
            tag_errors=len(self._tag_errors),
            quota_used=self._quota_usage,
            frequency=self._frequency,
        )
        return df

    def transform(self, raw: pd.DataFrame) -> list[FXRateCreate]:
        """Seed dim_currency_pair, resolve FKs, validate via Pydantic."""
        # 1. Auto-seed dim_currency_pair with fx_rate universe pairs
        pairs_to_seed = self._universe.fx_rate_pair_create_entries()
        with self._connector.session() as session:
            pair_repo = FXCurrencyPairRepository(session)
            inserted = pair_repo.bulk_seed_from_universe(pairs_to_seed)
            if inserted:
                _log.info("dim_currency_pair_seeded", new_pairs=inserted)

            # 2. Build pair_id cache (same session — sees freshly seeded rows)
            pair_id_cache: dict[tuple[str, str], int] = {}
            for pair in pair_repo.all():
                pair_id_cache[(pair.base_ccy, pair.quote_ccy)] = pair.id

            # 3. Resolve vendor_id + frequency_id (fail loudly if missing)
            vendor = session.execute(
                select(DimVendor).where(DimVendor.vendor_code == VENDOR_CODE)
            ).scalar_one_or_none()
            if vendor is None:
                raise RuntimeError(
                    f"Vendor '{VENDOR_CODE}' missing from dbo.dim_vendor — cannot load fx_rate"
                )
            freq_code = self._frequency.upper()
            frequency = session.execute(
                select(DimFrequency).where(DimFrequency.frequency_code == freq_code)
            ).scalar_one_or_none()
            if frequency is None:
                raise RuntimeError(
                    f"Frequency '{freq_code}' missing from dbo.dim_frequency — "
                    "run migration 023_create_dim_frequency.sql"
                )
            vendor_id = vendor.id
            frequency_id = frequency.id

        if raw.empty:
            return []

        # 4. Resolve pair_ids, validate via Pydantic.
        # `to_dict("records")` iteration is 10-50× faster than `iterrows()`
        # for the historical-backfill case (years of daily data) where this
        # loop runs over hundreds of thousands of rows.
        observations: list[FXRateCreate] = []
        skipped_unmapped = 0
        skipped_nan_mid = 0
        skipped_nonpositive = 0
        for row in raw.to_dict("records"):
            key = (row["base_ccy"], row["quote_ccy"])
            pair_id = pair_id_cache.get(key)
            if pair_id is None:
                skipped_unmapped += 1
                continue

            mid_rate_raw = row["mid_rate"]
            if pd.isna(mid_rate_raw):
                # Row exists because a fwd_points tag returned data but outright
                # didn't — safer to drop than store NULL mid_rate (schema requires NOT NULL).
                skipped_nan_mid += 1
                continue

            mid_rate_dec = Decimal(str(mid_rate_raw))
            if mid_rate_dec <= 0:
                # Citi occasionally returns non-positive values for thin tenors
                # (placeholder/error sentinels). FX outright rates must be > 0
                # by construction; drop rather than fail the whole load.
                skipped_nonpositive += 1
                continue

            fwd_points_raw = row["fwd_points"]
            fwd_points = (
                None if pd.isna(fwd_points_raw) else Decimal(str(fwd_points_raw))
            )

            obs_ts = row["ts"]
            obs_date = obs_ts.date() if hasattr(obs_ts, "date") else obs_ts

            observations.append(
                FXRateCreate(
                    pair_id=pair_id,
                    vendor_id=vendor_id,
                    frequency_id=frequency_id,
                    obs_ts=obs_ts,
                    obs_date=obs_date,
                    tenor=row["tenor"],
                    mid_rate=mid_rate_dec,
                    fwd_points=fwd_points,
                )
            )

        if skipped_unmapped:
            _log.warning("transform_skipped_unmapped_pairs", count=skipped_unmapped)
        if skipped_nan_mid:
            _log.warning("transform_skipped_nan_mid_rate", count=skipped_nan_mid)
        if skipped_nonpositive:
            _log.warning("transform_skipped_nonpositive_mid_rate", count=skipped_nonpositive)
        _log.info("transform_complete", observations=len(observations))
        return observations

    def load(self, data: list[FXRateCreate]) -> int:
        """Bulk upsert rate observations via temp-table MERGE."""
        if not data:
            return 0

        if self._chunk_size:
            count = chunked_bulk_merge(
                self._connector, FX_RATE_SPEC, data, self._chunk_size,
            )
        else:
            with self._connector.session() as session:
                repo = FXRateRepository(session)
                count = repo.bulk_upsert(data)

        _log.info("load_complete", rows_loaded=count)
        return count

    def post_load(self, result: int, data: list[FXRateCreate]) -> None:
        """Write to parquet archive + run quality checks."""
        if self._raw_df is None or self._raw_df.empty:
            return

        manifest: dict[str, Any] = {
            "source": "citi_velocity_historical",
            "range": [str(self._start.date()), str(self._end.date())],
            "frequency": self._frequency,
            "rows_loaded": result,
        }
        written = write_partitioned_parquet(
            self._raw_df,
            root=Path("data/parquet/fx/fact_fx_rate"),
            required_columns=WIDE_COLUMNS,
            file_columns=["obs_date", "tenor", "mid_rate", "fwd_points"],
            dedup_key=["obs_date", "tenor"],
            manifest=manifest,
        )
        _log.info("parquet_archive_complete", files_written=len(written))

        self._run_quality_checks()

    def get_health_checks(self) -> list[HealthCheck]:
        cfg = self._config.health_checks
        checks: list[HealthCheck] = [
            RowCountCheck(FXFactFXRate, self._config.date_column, cfg.row_count_min),
            NullCheck(FXFactFXRate, self._config.required_columns, self._config.date_column),
            DuplicateCheck(FXFactFXRate, self._config.unique_columns, self._config.date_column),
            FreshnessCheck(FXFactFXRate, "created_at", cfg.max_staleness_hours),
        ]
        for col_name, vr in cfg.value_ranges.items():
            checks.append(
                ValueRangeCheck(FXFactFXRate, col_name, vr.min, vr.max, self._config.date_column)
            )
        return checks

    def get_run_context(self) -> dict[str, Any]:
        return {"run_date": self._start.date()}

    # ── Domain-specific quality checks (flag, don't block) ────────

    def _run_quality_checks(self) -> None:
        from imdr.healthchecks.base import CheckStatus
        from imdr.healthchecks.quality import (
            PercentageChangeCheck,
            PositiveValueCheck,
            RobustStatisticalOutlierCheck,
        )

        cleaning = self._config.cleaning
        reader = AnalyticalReader(self._connector)
        table = self._config.fully_qualified_table
        where = (
            f"AND [{self._config.date_column}] >= '{self._start:%Y-%m-%d}' "
            f"AND [{self._config.date_column}] <= '{self._end:%Y-%m-%d}'"
        )

        # Per-pair hard-bound violations are handled by the cleaning pipeline
        # (HardBoundViolationRule with pair_id-keyed ranges). Live quality only
        # checks things that don't need the range map.
        checks = [
            PositiveValueCheck(columns=["mid_rate"], symbol_column="pair_id"),
            PercentageChangeCheck(
                value_column="mid_rate",
                group_columns=["pair_id", "tenor"],
                ts_column=self._config.date_column,
                threshold_pct=cleaning.pct_threshold,
                min_abs_value=1e-6,
            ),
            RobustStatisticalOutlierCheck(
                value_column="mid_rate",
                group_columns=["pair_id", "tenor"],
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
