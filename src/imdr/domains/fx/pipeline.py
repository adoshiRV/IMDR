from __future__ import annotations

from pathlib import Path

import pandas as pd

from imdr.connectors.mssql import MSSQLConnector
from imdr.domains.fx.repository import FXRepository
from imdr.pipelines.base import BasePipeline
from imdr.schemas.fx import FXSpotRateCreate


class FXSpotRatePipeline(BasePipeline[pd.DataFrame, list[FXSpotRateCreate], int]):
    """Ingest FX spot rates from CSV into MSSQL.

    RawT = pd.DataFrame (from CSV)
    CleanT = list[FXSpotRateCreate] (validated)
    ResultT = int (rows loaded)
    """

    def __init__(self, connector: MSSQLConnector, source_path: Path) -> None:
        super().__init__(connector)
        self._source_path = source_path

    def extract(self) -> pd.DataFrame:
        self._log.info("reading_csv", path=str(self._source_path))
        return pd.read_csv(self._source_path, parse_dates=["rate_date"])

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
