"""FX spot rate ingestion pipeline.

Supports CSV and API extraction. Post-append health checks are
configured from pipelines.yml.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from imdr.config.pipeline_config import get_pipeline_config
from imdr.connectors.mssql import MSSQLConnector
from imdr.domains.fx.repository import FXRepository
from imdr.healthchecks.base import HealthCheck
from imdr.healthchecks.checks import (
    DuplicateCheck,
    FreshnessCheck,
    NullCheck,
    RowCountCheck,
    ValueRangeCheck,
)
from imdr.models.fx import FXSpotRate
from imdr.pipelines.base import BasePipeline
from imdr.pipelines.extractors import CSVExtractor, Extractor
from imdr.schemas.fx import FXSpotRateCreate


class FXSpotRatePipeline(BasePipeline[pd.DataFrame, list[FXSpotRateCreate], int]):
    """Ingest FX spot rates into MSSQL.

    RawT = pd.DataFrame (from CSV or API)
    CleanT = list[FXSpotRateCreate] (validated)
    ResultT = int (rows loaded)
    """

    pipeline_name = "fx.spot_rates"
    domain = "fx"

    def __init__(
        self,
        connector: MSSQLConnector,
        extractor: Extractor[pd.DataFrame] | None = None,
        source_path: Path | None = None,
    ) -> None:
        super().__init__(connector)
        self._extractor = extractor
        self._source_path = source_path
        self._config = get_pipeline_config(self.pipeline_name)
        self._run_date = date.today()

    def extract(self) -> pd.DataFrame:
        if self._extractor is not None:
            return self._extractor.extract()
        if self._source_path is not None:
            return CSVExtractor(self._source_path, parse_dates=["rate_date"]).extract()
        msg = "Either extractor or source_path must be provided"
        raise ValueError(msg)

    def transform(self, raw: pd.DataFrame) -> list[FXSpotRateCreate]:
        records = raw.to_dict(orient="records")
        validated: list[FXSpotRateCreate] = []
        errors: list[dict[str, object]] = []
        for i, record in enumerate(records):
            try:
                validated.append(FXSpotRateCreate.model_validate(record))
            except Exception as exc:
                errors.append({"row": i, "error": str(exc)})
        if errors:
            self._log.warning("validation_errors", count=len(errors), errors=errors[:10])
        self._log.info("transform_summary", valid=len(validated), invalid=len(errors))
        return validated

    def load(self, data: list[FXSpotRateCreate]) -> int:
        with self._connector.session() as session:
            repo = FXRepository(session)
            repo.bulk_create(data)
        return len(data)

    def get_health_checks(self) -> list[HealthCheck]:
        cfg = self._config.health_checks
        checks: list[HealthCheck] = [
            RowCountCheck(FXSpotRate, self._config.date_column, cfg.row_count_min),
            NullCheck(FXSpotRate, self._config.required_columns, self._config.date_column),
            DuplicateCheck(FXSpotRate, self._config.unique_columns, self._config.date_column),
            FreshnessCheck(FXSpotRate, "created_at", cfg.max_staleness_hours),
        ]
        for col_name, vr in cfg.value_ranges.items():
            checks.append(
                ValueRangeCheck(FXSpotRate, col_name, vr.min, vr.max, self._config.date_column)
            )
        return checks

    def get_run_context(self) -> dict[str, Any]:
        return {"run_date": self._run_date}
