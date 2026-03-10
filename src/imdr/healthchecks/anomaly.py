"""Anomaly detection — domain-agnostic % change threshold vs previous period."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

log = structlog.get_logger(__name__)


@dataclass
class AnomalyRecord:
    """A detected anomaly."""

    symbol: str
    series: str
    field: str
    previous: float
    current: float
    pct_change: float
    ts: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "series": self.series,
            "field": self.field,
            "previous": self.previous,
            "current": self.current,
            "pct_change": self.pct_change,
            "ts": self.ts.isoformat(),
        }


class AnomalyDetector:
    """Detect anomalous price changes by comparing to previous period.

    Domain-agnostic — works with any ORM model that has symbol, series,
    timestamp, and numeric price columns.
    """

    def __init__(self, threshold_pct: float = 50.0) -> None:
        self._threshold = threshold_pct

    def detect(
        self,
        session: Session,
        model: type,
        ts_column: str,
        value_columns: list[str],
        symbol_column: str,
        series_column: str,
        current_ts: datetime,
        previous_ts: datetime,
    ) -> list[AnomalyRecord]:
        """Compare current vs previous period bars and flag anomalies.

        Args:
            session: SQLAlchemy session.
            model: ORM model class.
            ts_column: Name of the timestamp column.
            value_columns: Numeric columns to check (e.g. ['close_px', 'mid_px']).
            symbol_column: Name of the symbol column.
            series_column: Name of the series column.
            current_ts: Timestamp of current bars.
            previous_ts: Timestamp of previous bars to compare against.

        Returns:
            List of AnomalyRecord for bars exceeding the threshold.
        """
        ts_col = getattr(model, ts_column)
        sym_col = getattr(model, symbol_column)
        ser_col = getattr(model, series_column)

        # Strip timezone to avoid pyodbc 'Invalid precision value' error
        # with datetimeoffset bind parameters (ODBC Driver 17 limitation).
        # Safe because all data is stored as UTC.
        if getattr(current_ts, "tzinfo", None):
            current_ts = current_ts.replace(tzinfo=None)
        if getattr(previous_ts, "tzinfo", None):
            previous_ts = previous_ts.replace(tzinfo=None)

        # Fetch current and previous bars
        current_bars = session.scalars(
            select(model).where(ts_col == current_ts)
        ).all()
        previous_bars = session.scalars(
            select(model).where(ts_col == previous_ts)
        ).all()

        # Index previous bars by (symbol, series)
        prev_index: dict[tuple[str, str], Any] = {}
        for bar in previous_bars:
            key = (getattr(bar, symbol_column), getattr(bar, series_column))
            prev_index[key] = bar

        anomalies: list[AnomalyRecord] = []
        for bar in current_bars:
            symbol = getattr(bar, symbol_column)
            series = getattr(bar, series_column)
            key = (symbol, series)
            prev = prev_index.get(key)
            if prev is None:
                continue

            for col_name in value_columns:
                curr_val = getattr(bar, col_name)
                prev_val = getattr(prev, col_name)

                if curr_val is None or prev_val is None:
                    continue

                curr_f = float(curr_val) if isinstance(curr_val, Decimal) else curr_val
                prev_f = float(prev_val) if isinstance(prev_val, Decimal) else prev_val

                if prev_f == 0:
                    continue

                pct_change = abs((curr_f - prev_f) / prev_f) * 100
                if pct_change >= self._threshold:
                    anomalies.append(AnomalyRecord(
                        symbol=symbol,
                        series=series,
                        field=col_name,
                        previous=prev_f,
                        current=curr_f,
                        pct_change=pct_change,
                        ts=current_ts,
                    ))

        if anomalies:
            log.warning(
                "anomalies_detected",
                count=len(anomalies),
                threshold_pct=self._threshold,
            )
        return anomalies
