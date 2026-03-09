"""Extractor protocol and base classes.

Extractors decouple data sourcing from the pipeline.
Subclass ``CSVExtractor`` or ``APIExtractor`` per domain/provider.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Generic, TypeVar

import pandas as pd
import structlog

DataT = TypeVar("DataT")


class Extractor(ABC, Generic[DataT]):
    """Base class for all data extractors."""

    def __init__(self) -> None:
        self._log = structlog.get_logger(self.__class__.__name__)

    @abstractmethod
    def extract(self) -> DataT:
        """Pull data from source and return raw form."""
        ...


class CSVExtractor(Extractor[pd.DataFrame]):
    """Extract data from a local CSV file."""

    def __init__(self, path: Path, parse_dates: list[str] | None = None) -> None:
        super().__init__()
        self._path = path
        self._parse_dates = parse_dates or []

    def extract(self) -> pd.DataFrame:
        self._log.info("reading_csv", path=str(self._path))
        return pd.read_csv(self._path, parse_dates=self._parse_dates)


class APIExtractor(Extractor[DataT]):
    """Base for HTTP API extractors.

    Subclasses should inject an ``HTTPClient`` and implement ``extract()``.
    """
