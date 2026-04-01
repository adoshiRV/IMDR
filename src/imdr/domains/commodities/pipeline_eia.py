"""Commodities EIA pipeline — extract from Citi Velocity, load to SQL + parquet.

67 tags, weekly (Wednesday publication).
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
from imdr.domains.commodities.extractors import CitiVelocityCmdtyExtractor
from imdr.domains.commodities.repository import (
    CmdtyEIARepository,
    CmdtyEIASeriesRepository,
)
from imdr.domains.commodities.store_eia import write as parquet_write
from imdr.healthchecks.base import HealthCheck
from imdr.healthchecks.checks import (
    DuplicateCheck,
    FreshnessCheck,
    NullCheck,
    RowCountCheck,
)
from imdr.models.commodities import CmdtyFactEIA
from imdr.pipelines.base import BasePipeline
from imdr.schemas.commodities import EIACreate
from imdr.universe.commodities import CommoditiesUniverse

_log = structlog.get_logger("CmdtyEIAPipeline")


class CmdtyEIAPipeline(BasePipeline[pd.DataFrame, list[EIACreate], int]):
    """ETL pipeline: Citi Velocity EIA petroleum data → SQL Server + parquet."""

    pipeline_name = "commodities.eia"
    domain = "commodities"

    def __init__(
        self,
        connector: MSSQLConnector,
        settings: Settings,
        universe: CommoditiesUniverse,
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
            extractor = CitiVelocityCmdtyExtractor(
                client=client, settings=self._settings,
                universe=self._universe, quota_tracker=tracker,
            )
            df = extractor.extract_eia(self._start, self._end)

        self._extraction_errors = extractor._errors
        self._quota_usage = tracker.current_usage()
        self._raw_df = df
        _log.info("extract_complete", rows=len(df))
        return df

    def transform(self, raw: pd.DataFrame) -> list[EIACreate]:
        # 1. Seed dim_eia_series
        entries = self._universe.eia_series_create_entries()
        with self._connector.session() as session:
            repo = CmdtyEIASeriesRepository(session)
            inserted = repo.bulk_seed_from_universe(entries)
            if inserted:
                _log.info("dim_eia_series_seeded", new_rows=inserted)

            # 2. Build series_id cache
            series_id_cache: dict[tuple[str, str], int] = {}
            for s in repo.all():
                series_id_cache[(s.series_name, s.region)] = s.id

        if raw.empty:
            return []

        # 3. Resolve series_id, validate via Pydantic
        observations: list[EIACreate] = []
        skipped = 0
        for _, row in raw.iterrows():
            series_id = series_id_cache.get((row["series_name"], row["region"]))
            if series_id is None:
                skipped += 1
                continue
            observations.append(EIACreate(
                eia_series_id=series_id,
                obs_date=row["ts"].date() if hasattr(row["ts"], "date") else row["ts"],
                stat_value=row["value"],
            ))

        if skipped:
            _log.warning("transform_skipped_unmapped_series", count=skipped)
        _log.info("transform_complete", observations=len(observations))
        return observations

    def load(self, data: list[EIACreate]) -> int:
        if not data:
            return 0
        with self._connector.session() as session:
            repo = CmdtyEIARepository(session)
            count = repo.bulk_upsert(data)
        _log.info("load_complete", rows_loaded=count)
        return count

    def post_load(self, result: int, data: list[EIACreate]) -> None:
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
        return [
            RowCountCheck(CmdtyFactEIA, self._config.date_column, cfg.row_count_min),
            NullCheck(CmdtyFactEIA, self._config.required_columns, self._config.date_column),
            DuplicateCheck(CmdtyFactEIA, self._config.unique_columns, self._config.date_column),
            FreshnessCheck(CmdtyFactEIA, "created_at", cfg.max_staleness_hours),
        ]

    def get_run_context(self) -> dict[str, Any]:
        return {"run_date": self._start.date()}
