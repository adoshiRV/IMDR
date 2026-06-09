"""AnalyticalReader — fast analytical reads bypassing ORM.

Uses engine.connect() directly to avoid session/identity-map overhead.
Returns pandas or polars DataFrames for downstream analysis.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import pandas as pd
import structlog
from sqlalchemy import text

from imdr.connectors._sql_safety import validate_column, validate_identifier
from imdr.connectors.mssql import MSSQLConnector

log = structlog.get_logger(__name__)


class AnalyticalReader:
    """Fast analytical reads against MSSQL, bypassing ORM overhead."""

    def __init__(self, connector: MSSQLConnector) -> None:
        self._engine = connector.read_engine

    def read_sql(self, sql: str, params: dict[str, Any] | None = None) -> pd.DataFrame:
        """Execute raw SQL and return a pandas DataFrame."""
        log.debug("read_sql", sql=sql[:100], params=params)
        with self._engine.connect() as conn:
            return pd.read_sql(text(sql), conn, params=params or {})

    def read_polars(self, sql: str, params: dict[str, Any] | None = None) -> Any:
        """Execute raw SQL and return a polars DataFrame via pandas bridge."""
        import polars as pl

        pdf = self.read_sql(sql, params)
        return pl.from_pandas(pdf)

    def date_range_scan(
        self,
        table: str,
        date_column: str,
        start: date | datetime,
        end: date | datetime,
        columns: list[str] | None = None,
    ) -> pd.DataFrame:
        """Date range scan on a table.

        Args:
            table: Fully qualified table name, e.g. "[fx].[fact_ohlc]"
            date_column: Column to filter on, e.g. "ts"
            start: Start date (inclusive)
            end: End date (inclusive)
            columns: Specific columns to select, or None for all
        """
        validate_identifier(table, "table")
        validate_column(date_column, "date_column")
        if columns:
            for c in columns:
                validate_column(c, "column")
            cols = ", ".join(f"[{c}]" for c in columns)
        else:
            cols = "*"
        sql = f"SELECT {cols} FROM {table} WHERE [{date_column}] BETWEEN :start AND :end ORDER BY [{date_column}]"
        return self.read_sql(sql, {"start": start, "end": end})

    def read_view(
        self,
        view_name: str,
        filters: dict[str, Any] | None = None,
        order_by: str | None = None,
        limit: int | None = None,
    ) -> pd.DataFrame:
        """Read from a view with optional parameterized filters.

        Args:
            view_name: Fully qualified view name, e.g. "[fx].[some_view]"
            filters: Column=value filters applied as WHERE clauses
            order_by: Column name to order by (validated, not raw SQL)
            limit: Max rows to return
        """
        validate_identifier(view_name, "view_name")

        limit_clause = ""
        if limit is not None:
            if not isinstance(limit, int) or limit < 1:
                raise ValueError(f"Invalid limit: {limit!r}")
            limit_clause = f"TOP({limit}) "

        sql = f"SELECT {limit_clause}* FROM {view_name}"

        params: dict[str, Any] = {}
        if filters:
            clauses = []
            for col, val in filters.items():
                validate_column(col, "filter column")
                param_name = f"p_{col}"
                clauses.append(f"[{col}] = :{param_name}")
                params[param_name] = val
            sql += " WHERE " + " AND ".join(clauses)

        if order_by:
            validate_column(order_by, "order_by")
            sql += f" ORDER BY [{order_by}]"

        return self.read_sql(sql, params)
