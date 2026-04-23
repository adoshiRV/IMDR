"""Equity VIX pipeline — extract VIX family from Citi Velocity, load to SQL + parquet.

5 tickers (VIX, VIX3M, VIX9D, VVIX, VXN), ~5 rows/day.
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
from imdr.domains.equity.extractors import CitiVelocityEquityExtractor
from imdr.domains.equity.repository import EquityVixRepository
from imdr.domains.equity.store_vix import write as parquet_write
from imdr.healthchecks.base import HealthCheck
from imdr.healthchecks.checks import (
    DuplicateCheck,
    FreshnessCheck,
    NullCheck,
    RowCountCheck,
    ValueRangeCheck,
)
from imdr.models.equity import EquityFactVix
from imdr.pipelines.base import BasePipeline
from imdr.schemas.equity import VixCreate
from imdr.universe.equity import EquityUniverse

_log = structlog.get_logger("EquityVixPipeline")


class EquityVixPipeline(BasePipeline[pd.DataFrame, list[VixCreate], int]):
    """ETL pipeline: Citi Velocity VIX family → SQL Server + parquet."""

    pipeline_name = "equity.vix"
    domain = "equities"

    def __init__(
        self,
        connector: MSSQLConnector,
        settings: Settings,
        universe: EquityUniverse,
        start: datetime,
        end: datetime,
    ) -> None:
        super().__init__(connector)
        self._settings = settings
        self._universe = universe
        self._config = get_pipeline_config(self.pipeline_name)
        self._start = start
        self._end = end
        self._raw_df: pd.DataFrame | None = None
        self._extraction_errors: list[dict] = []
        self._quota_usage: int | None = None

    def extract(self) -> pd.DataFrame:
        tracker = TagQuotaTracker(
            quota_limit=self._settings.citi_tag_quota_limit,
            tracker_path=self._settings.citi_tag_quota_file or None,
        )
        with CitiVelocityClient(self._settings) as client:
            extractor = CitiVelocityEquityExtractor(
                client=client, settings=self._settings,
                universe=self._universe, quota_tracker=tracker,
            )
            df = extractor.extract_vix(self._start, self._end)

        self._extraction_errors = extractor._errors
        self._quota_usage = tracker.current_usage()
        self._raw_df = df
        _log.info("extract_complete", rows=len(df))
        return df

    def transform(self, raw: pd.DataFrame) -> list[VixCreate]:
        if raw.empty:
            return []

        observations: list[VixCreate] = []
        for _, row in raw.iterrows():
            observations.append(VixCreate(
                ticker=row["ticker"],
                obs_date=row["ts"].date() if hasattr(row["ts"], "date") else row["ts"],
                close_level=row["value"],
            ))

        _log.info("transform_complete", observations=len(observations))
        return observations

    def load(self, data: list[VixCreate]) -> int:
        if not data:
            return 0
        with self._connector.session() as session:
            repo = EquityVixRepository(session)
            count = repo.bulk_upsert(data)
        _log.info("load_complete", rows_loaded=count)
        return count

    def post_load(self, result: int, data: list[VixCreate]) -> None:
        if self._raw_df is None or self._raw_df.empty:
            return
        manifest = {
            "source": "citi_velocity_historical",
            "range": [str(self._start.date()), str(self._end.date())],
            "rows_loaded": result,
        }
        written = parquet_write(self._raw_df, manifest=manifest)
        _log.info("parquet_archive_complete", files_written=len(written))

    def get_health_checks(self) -> list[HealthCheck]:
        cfg = self._config.health_checks
        checks: list[HealthCheck] = [
            RowCountCheck(EquityFactVix, self._config.date_column, cfg.row_count_min),
            NullCheck(EquityFactVix, self._config.required_columns, self._config.date_column),
            DuplicateCheck(EquityFactVix, self._config.unique_columns, self._config.date_column),
            FreshnessCheck(EquityFactVix, "created_at", cfg.max_staleness_hours),
        ]
        for col_name, vr in cfg.value_ranges.items():
            checks.append(
                ValueRangeCheck(EquityFactVix, col_name, vr.min, vr.max, self._config.date_column)
            )
        return checks

    def get_run_context(self) -> dict[str, Any]:
        return {"run_date": self._start.date()}
