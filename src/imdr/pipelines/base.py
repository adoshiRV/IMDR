from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

import structlog

from imdr.connectors.mssql import MSSQLConnector

RawT = TypeVar("RawT")
CleanT = TypeVar("CleanT")
ResultT = TypeVar("ResultT")


class BasePipeline(ABC, Generic[RawT, CleanT, ResultT]):
    """Abstract ETL pipeline with extract/transform/load stages.

    Subclasses define the concrete types and implement each stage.
    """

    def __init__(self, connector: MSSQLConnector) -> None:
        self._connector = connector
        self._log = structlog.get_logger(self.__class__.__name__)

    @abstractmethod
    def extract(self) -> RawT:
        """Extract raw data from source."""
        ...

    @abstractmethod
    def transform(self, raw: RawT) -> CleanT:
        """Validate and transform raw data."""
        ...

    @abstractmethod
    def load(self, data: CleanT) -> ResultT:
        """Load transformed data into the database."""
        ...

    def run(self) -> ResultT:
        """Execute the full ETL pipeline."""
        self._log.info("pipeline_started")
        try:
            raw = self.extract()
            self._log.info("extract_complete")
            clean = self.transform(raw)
            self._log.info("transform_complete")
            result = self.load(clean)
            self._log.info("load_complete")
            return result
        except Exception:
            self._log.exception("pipeline_failed")
            raise
