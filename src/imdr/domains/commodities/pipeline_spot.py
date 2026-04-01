"""Commodities SPOT pipeline — extract from Citi Velocity, load to SQL + parquet.

3 tags (Gold, Silver, WTI), ~3 rows/day.
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
from imdr.domains.commodities.repository import CmdtyCommodityRepository, CmdtySpotRepository
from imdr.domains.commodities.store_spot import write as parquet_write
from imdr.healthchecks.base import HealthCheck
from imdr.healthchecks.checks import (
    DuplicateCheck,
    FreshnessCheck,
    NullCheck,
    RowCountCheck,
    ValueRangeCheck,
)
from imdr.models.commodities import CmdtyFactSpot
from imdr.pipelines.base import BasePipeline
from imdr.schemas.commodities import SpotCreate
from imdr.universe.commodities import CommoditiesUniverse

_log = structlog.get_logger("CmdtySpotPipeline")


class CmdtySpotPipeline(BasePipeline[pd.DataFrame, list[SpotCreate], int]):
    """ETL pipeline: Citi Velocity commodity spot prices → SQL Server + parquet."""

    pipeline_name = "commodities.spot"
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
            df = extractor.extract_spot(self._start, self._end)

        self._extraction_errors = extractor._errors
        self._quota_usage = tracker.current_usage()
        self._raw_df = df
        _log.info("extract_complete", rows=len(df))
        return df

    def transform(self, raw: pd.DataFrame) -> list[SpotCreate]:
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

        # 3. Map spot_tag → symbol → commodity_id
        spot_tag_map = self._universe.spot_tags()
        observations: list[SpotCreate] = []
        for _, row in raw.iterrows():
            symbol = spot_tag_map.get(row["spot_tag"])
            if symbol is None:
                continue
            commodity_id = commodity_id_cache.get(symbol)
            if commodity_id is None:
                continue
            observations.append(SpotCreate(
                commodity_id=commodity_id,
                obs_date=row["ts"].date() if hasattr(row["ts"], "date") else row["ts"],
                price=row["value"],
            ))

        _log.info("transform_complete", observations=len(observations))
        return observations

    def load(self, data: list[SpotCreate]) -> int:
        if not data:
            return 0
        with self._connector.session() as session:
            repo = CmdtySpotRepository(session)
            count = repo.bulk_upsert(data)
        _log.info("load_complete", rows_loaded=count)
        return count

    def post_load(self, result: int, data: list[SpotCreate]) -> None:
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
            RowCountCheck(CmdtyFactSpot, self._config.date_column, cfg.row_count_min),
            NullCheck(CmdtyFactSpot, self._config.required_columns, self._config.date_column),
            DuplicateCheck(CmdtyFactSpot, self._config.unique_columns, self._config.date_column),
            FreshnessCheck(CmdtyFactSpot, "created_at", cfg.max_staleness_hours),
        ]
        for col_name, vr in cfg.value_ranges.items():
            checks.append(
                ValueRangeCheck(CmdtyFactSpot, col_name, vr.min, vr.max, self._config.date_column)
            )
        return checks

    def get_run_context(self) -> dict[str, Any]:
        return {"run_date": self._start.date()}
