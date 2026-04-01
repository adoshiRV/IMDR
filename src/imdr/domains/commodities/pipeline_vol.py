"""Commodities implied vol pipeline — extract from Citi Velocity, load to SQL + parquet.

1,011 tags across 5 products (XAU, XAG, XPT precious metals + Brent/WTI oil).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd
import structlog

from imdr.config.pipeline_config import get_pipeline_config
from imdr.config.settings import Settings
from imdr.connectors.bulk import chunked_bulk_merge
from imdr.connectors.citi_quota import TagQuotaTracker
from imdr.connectors.citi_velocity import CitiVelocityClient
from imdr.connectors.mssql import MSSQLConnector
from imdr.connectors.reader import AnalyticalReader
from imdr.domains.commodities.extractors import CitiVelocityCmdtyExtractor
from imdr.domains.commodities.repository import (
    CmdtyCommodityRepository,
    CmdtyImpliedVolRepository,
    _VOL_SPEC,
)
from imdr.domains.commodities.store_vol import write as parquet_write
from imdr.healthchecks.base import HealthCheck
from imdr.healthchecks.checks import (
    DuplicateCheck,
    FreshnessCheck,
    NullCheck,
    RowCountCheck,
)
from imdr.models.commodities import CmdtyFactImpliedVol
from imdr.pipelines.base import BasePipeline
from imdr.schemas.commodities import ImpliedVolCreate
from imdr.universe.commodities import CommoditiesUniverse

_log = structlog.get_logger("CmdtyImpliedVolPipeline")


class CmdtyImpliedVolPipeline(BasePipeline[pd.DataFrame, list[ImpliedVolCreate], int]):
    """ETL pipeline: Citi Velocity commodity vol surfaces → SQL Server + parquet."""

    pipeline_name = "commodities.vol"
    domain = "commodities"

    def __init__(
        self,
        connector: MSSQLConnector,
        settings: Settings,
        universe: CommoditiesUniverse,
        start: datetime,
        end: datetime,
        products: list[str] | None = None,
        chunk_size: int | None = None,
    ) -> None:
        super().__init__(connector)
        self._settings = settings
        self._universe = universe
        self._config = get_pipeline_config(self.pipeline_name)
        self._start = start
        self._end = end
        self._products = products
        self._chunk_size = chunk_size
        self._raw_df: pd.DataFrame | None = None
        self._quality_results: list[dict[str, Any]] = []
        self._extraction_errors: list[dict] = []
        self._quota_usage: int | None = None

    def extract(self) -> pd.DataFrame:
        tracker = TagQuotaTracker(
            quota_limit=self._settings.citi_tag_quota_limit,
            tracker_path=self._settings.citi_tag_quota_file or None,
        )
        with CitiVelocityClient(self._settings) as client:
            extractor = CitiVelocityCmdtyExtractor(
                client=client, settings=self._settings,
                universe=self._universe, quota_tracker=tracker,
            )
            df = extractor.extract_vol(self._start, self._end, self._products)

        self._extraction_errors = extractor._errors
        self._quota_usage = tracker.current_usage()
        self._raw_df = df
        _log.info("extract_complete", rows=len(df),
                   extraction_errors=len(self._extraction_errors),
                   quota_used=self._quota_usage)
        return df

    def transform(self, raw: pd.DataFrame) -> list[ImpliedVolCreate]:
        # 1. Seed dim_commodity
        entries = self._universe.commodity_create_entries()
        with self._connector.session() as session:
            repo = CmdtyCommodityRepository(session)
            inserted = repo.bulk_seed_from_universe(entries)
            if inserted:
                _log.info("dim_commodity_seeded", new_rows=inserted)

            # 2. Build commodity_id cache
            commodity_id_cache: dict[str, int] = {}
            for c in repo.all():
                commodity_id_cache[c.symbol] = c.id

        if raw.empty:
            return []

        # 3. Resolve commodity_id, validate via Pydantic
        observations: list[ImpliedVolCreate] = []
        skipped = 0
        for _, row in raw.iterrows():
            commodity_id = commodity_id_cache.get(row["product"])
            if commodity_id is None:
                skipped += 1
                continue
            observations.append(ImpliedVolCreate(
                commodity_id=commodity_id,
                obs_date=row["ts"].date() if hasattr(row["ts"], "date") else row["ts"],
                strike=row["strike"],
                tenor=row["tenor"],
                vol=row["value"],
            ))

        if skipped:
            _log.warning("transform_skipped_unmapped_products", count=skipped)
        _log.info("transform_complete", observations=len(observations))
        return observations

    def load(self, data: list[ImpliedVolCreate]) -> int:
        if not data:
            return 0

        if self._chunk_size:
            count = chunked_bulk_merge(
                self._connector, _VOL_SPEC, data, self._chunk_size,
            )
        else:
            with self._connector.session() as session:
                repo = CmdtyImpliedVolRepository(session)
                count = repo.bulk_upsert(data)

        _log.info("load_complete", rows_loaded=count)
        return count

    def post_load(self, result: int, data: list[ImpliedVolCreate]) -> None:
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
            RowCountCheck(CmdtyFactImpliedVol, self._config.date_column, cfg.row_count_min),
            NullCheck(CmdtyFactImpliedVol, self._config.required_columns, self._config.date_column),
            DuplicateCheck(CmdtyFactImpliedVol, self._config.unique_columns, self._config.date_column),
            FreshnessCheck(CmdtyFactImpliedVol, "created_at", cfg.max_staleness_hours),
        ]

    def get_run_context(self) -> dict[str, Any]:
        return {"run_date": self._start.date()}

    # ── Domain-specific quality checks ─────────────────────────

    def _run_quality_checks(self) -> None:
        """Run vol-specific quality checks (flag, don't block)."""
        from imdr.healthchecks.base import CheckStatus
        from imdr.healthchecks.quality import (
            PercentageChangeCheck,
            RobustStatisticalOutlierCheck,
            SymbolRangeCheck,
        )

        quality_ranges = self._universe.vol_quality_ranges()
        cleaning = self._config.cleaning
        reader = AnalyticalReader(self._connector)
        table = self._config.fully_qualified_table
        where = (
            f"AND [{self._config.date_column}] >= '{self._start:%Y-%m-%d}' "
            f"AND [{self._config.date_column}] <= '{self._end:%Y-%m-%d}'"
        )

        checks = [
            SymbolRangeCheck(
                ranges={strike: {"min": lo, "max": hi} for strike, (lo, hi) in quality_ranges.items()},
                value_column="vol",
                symbol_column="strike",
            ),
            PercentageChangeCheck(
                value_column="vol",
                group_columns=["commodity_id", "strike", "tenor"],
                ts_column=self._config.date_column,
                threshold_pct=cleaning.pct_threshold,
                min_abs_value=0.5,
            ),
            RobustStatisticalOutlierCheck(
                value_column="vol",
                group_columns=["commodity_id", "strike", "tenor"],
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
