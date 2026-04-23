"""Rates swaption skew pipeline — load from Barclays/S&P Excel files to SQL + parquet.

Usage:
    python -m scripts.rates.barclays.rates_skew_load
    python -m scripts.rates.barclays.rates_skew_load --dir data/skew --start 2024-01-01
"""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import structlog

from imdr.config.pipeline_config import get_pipeline_config
from imdr.config.settings import Settings
from imdr.connectors.bulk import chunked_bulk_merge
from imdr.connectors.mssql import MSSQLConnector
from imdr.connectors.reader import AnalyticalReader
from imdr.domains.rates.repository_skew import (
    RatesSkewSurfaceRepository,
    RatesSwaptionSkewRepository,
    _SWAPTION_SKEW_SPEC,
)
from imdr.domains.rates.skew_translate import COLUMNS, read_skew_files
from imdr.domains.rates.store_skew import write as parquet_write
from imdr.healthchecks.base import HealthCheck
from imdr.healthchecks.checks import (
    DuplicateCheck,
    FreshnessCheck,
    NullCheck,
    RowCountCheck,
)
from imdr.models.rates_skew import RatesFactSwaptionSkew
from imdr.pipelines.base import BasePipeline
from imdr.schemas.rates_skew import RatesSkewSurfaceCreate, RatesSwaptionSkewCreate

_log = structlog.get_logger("RatesSkewPipeline")


class RatesSkewPipeline(BasePipeline[pd.DataFrame, list[RatesSwaptionSkewCreate], int]):
    """ETL pipeline: Barclays Excel skew files -> SQL Server + parquet."""

    pipeline_name = "rates.skew"
    domain = "rates"

    def __init__(
        self,
        connector: MSSQLConnector,
        settings: Settings,
        file_paths: list[Path],
        vendor_id: int,
        start: date | None = None,
        end: date | None = None,
        chunk_size: int | None = None,
    ) -> None:
        super().__init__(connector)
        self._settings = settings
        self._config = get_pipeline_config(self.pipeline_name)
        self._file_paths = file_paths
        self._vendor_id = vendor_id
        self._start = start
        self._end = end
        self._chunk_size = chunk_size
        self._raw_df: pd.DataFrame | None = None

    def extract(self) -> pd.DataFrame:
        """Read skew data from Excel files."""
        df = read_skew_files(self._file_paths, start=self._start, end=self._end)
        self._raw_df = df
        _log.info("extract_complete", rows=len(df), n_files=len(self._file_paths))
        return df

    def transform(self, raw: pd.DataFrame) -> list[RatesSwaptionSkewCreate]:
        """Seed dim_skew_surface, resolve surface_ids, validate via Pydantic."""
        if raw.empty:
            return []

        # 1. Auto-seed dim_skew_surface from unique (ccy, option_expiry) combos
        unique_surfaces = raw[["ccy", "option_expiry"]].drop_duplicates()
        seed_entries = [
            RatesSkewSurfaceCreate(ccy=row["ccy"], option_expiry=row["option_expiry"])
            for _, row in unique_surfaces.iterrows()
        ]

        with self._connector.session() as session:
            surface_repo = RatesSkewSurfaceRepository(session)
            inserted = surface_repo.bulk_seed_from_universe(seed_entries)
            if inserted:
                _log.info("dim_skew_surface_seeded", new_surfaces=inserted)

            # 2. Build surface_id cache
            surface_id_cache: dict[tuple[str, str], int] = {}
            for s in surface_repo.all():
                surface_id_cache[(s.ccy, s.option_expiry)] = s.id

        # 3. Resolve surface_ids, validate via Pydantic
        observations: list[RatesSwaptionSkewCreate] = []
        skipped = 0
        for _, row in raw.iterrows():
            key = (row["ccy"], row["option_expiry"])
            surface_id = surface_id_cache.get(key)
            if surface_id is None:
                skipped += 1
                continue
            observations.append(RatesSwaptionSkewCreate(
                surface_id=surface_id,
                vendor_id=self._vendor_id,
                obs_date=row["ts"].date() if hasattr(row["ts"], "date") else row["ts"],
                swap_tenor=row["swap_tenor"],
                strike_offset=row["strike_offset"],
                vol=row["vol"],
            ))

        if skipped:
            _log.warning("transform_skipped_unmapped_surfaces", count=skipped)
        _log.info("transform_complete", observations=len(observations))
        return observations

    def load(self, data: list[RatesSwaptionSkewCreate]) -> int:
        """Bulk upsert skew observations to SQL Server."""
        if not data:
            return 0

        if self._chunk_size:
            count = chunked_bulk_merge(
                self._connector, _SWAPTION_SKEW_SPEC, data, self._chunk_size,
            )
        else:
            with self._connector.session() as session:
                repo = RatesSwaptionSkewRepository(session)
                count = repo.bulk_upsert(data)

        _log.info("load_complete", rows_loaded=count)
        return count

    def post_load(self, result: int, data: list[RatesSwaptionSkewCreate]) -> None:
        """Write to parquet archive + run health checks."""
        if self._raw_df is None or self._raw_df.empty:
            return

        start_str = str(self._start) if self._start else "earliest"
        end_str = str(self._end) if self._end else "latest"

        manifest: dict[str, Any] = {
            "source": "barclays_excel",
            "range": [start_str, end_str],
            "rows_loaded": result,
            "n_files": len(self._file_paths),
        }
        written = parquet_write(self._raw_df, manifest=manifest)
        _log.info("parquet_archive_complete", files_written=len(written))

    def get_health_checks(self) -> list[HealthCheck]:
        cfg = self._config.health_checks
        return [
            RowCountCheck(RatesFactSwaptionSkew, self._config.date_column, cfg.row_count_min),
            NullCheck(RatesFactSwaptionSkew, self._config.required_columns, self._config.date_column),
            DuplicateCheck(RatesFactSwaptionSkew, self._config.unique_columns, self._config.date_column),
            FreshnessCheck(RatesFactSwaptionSkew, "created_at", cfg.max_staleness_hours),
        ]

    def get_run_context(self) -> dict[str, Any]:
        # Health checks need window_start/window_end (BETWEEN range) for backfills.
        # Prefer actual data range from _raw_df; fall back to CLI --start/--end.
        window_start: date | None = self._start
        window_end: date | None = self._end
        if self._raw_df is not None and not self._raw_df.empty:
            ts = pd.to_datetime(self._raw_df["ts"])
            window_start = window_start or ts.min().date()
            window_end = window_end or ts.max().date()
        return {
            "window_start": window_start,
            "window_end": window_end,
            "n_files": len(self._file_paths),
        }
