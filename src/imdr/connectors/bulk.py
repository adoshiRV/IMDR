"""Shared temp-table → MERGE upsert for MSSQL.

Standardizes the bulk upsert pattern across fact-table repositories
(rates.fact_observation, fx.fact_vol, and future high-volume tables).

Handles the legacy 'SQL Server' ODBC driver quirk: datetime.date objects
cannot be bound via SQLBindParameter (HYC00 error). DATE columns are staged
as VARCHAR(10) with ISO strings; SQL Server converts implicitly on MERGE.

Low-volume repos (FX OHLC: ~17 rows/hour) use row-by-row ORM upsert instead
— different pattern, not included here.

Usage:
    spec = MergeSpec(
        target_table="[fx].[fact_vol]",
        staging_name="#fx_vol_staging",
        columns={"pair_id": "INT", "obs_date": "DATE", "strike": "VARCHAR(15)", ...},
        natural_key=["pair_id", "obs_date", "strike", "tenor", "vol_type"],
        value_columns=["value"],
    )
    count = bulk_merge(session, spec, items)
"""
from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import date, datetime
from typing import Any

import structlog
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

_log = structlog.get_logger("bulk_merge")

# Identifier validation — prevents SQL injection in dynamic SQL
_IDENTIFIER_RE = re.compile(r"^\[[\w]+\](?:\.\[[\w]+\])?$")
_COLUMN_RE = re.compile(r"^[\w]+$")
_STAGING_RE = re.compile(r"^#[\w]+$")

# Legacy ODBC driver can't bind these Python types.
# Staged as VARCHAR; SQL Server converts implicitly on MERGE.
_DATE_TYPES = frozenset({"DATE", "SMALLDATETIME"})

_DEFAULT_BATCH_SIZE = 1000


def _validate_identifier(value: str, label: str) -> None:
    if not _IDENTIFIER_RE.match(value):
        raise ValueError(f"Invalid {label}: {value!r}. Expected [schema].[name] format.")


def _validate_column(value: str, label: str) -> None:
    if not _COLUMN_RE.match(value):
        raise ValueError(f"Invalid {label}: {value!r}. Expected alphanumeric column name.")


def _validate_staging(value: str, label: str) -> None:
    if not _STAGING_RE.match(value):
        raise ValueError(f"Invalid {label}: {value!r}. Expected #temp_name format.")


class MergeSpec:
    """Describes a temp-table → MERGE upsert operation.

    Parameters
    ----------
    target_table : str
        Fully-qualified target, e.g. ``[fx].[fact_vol]``.
    staging_name : str
        Session-scoped temp table, e.g. ``#fx_vol_staging``.
    columns : dict[str, str]
        Ordered mapping of column name → SQL type for the staging table.
    natural_key : list[str]
        Columns forming the MERGE ON clause (subset of columns).
    value_columns : list[str]
        Columns updated on MATCHED (subset of columns, disjoint from natural_key).
    batch_size : int
        Rows per INSERT batch into the staging table.
    """

    def __init__(
        self,
        target_table: str,
        staging_name: str,
        columns: dict[str, str],
        natural_key: list[str],
        value_columns: list[str],
        batch_size: int = _DEFAULT_BATCH_SIZE,
    ) -> None:
        _validate_identifier(target_table, "target_table")
        _validate_staging(staging_name, "staging_name")
        for col in columns:
            _validate_column(col, "column")
        for col in natural_key:
            _validate_column(col, "natural_key column")
        for col in value_columns:
            _validate_column(col, "value_column")

        all_cols = set(columns)
        if not set(natural_key).issubset(all_cols):
            raise ValueError(f"natural_key columns not in columns: {set(natural_key) - all_cols}")
        if not set(value_columns).issubset(all_cols):
            raise ValueError(f"value_columns not in columns: {set(value_columns) - all_cols}")

        self.target_table = target_table
        self.staging_name = staging_name
        self.columns = columns
        self.natural_key = natural_key
        self.value_columns = value_columns
        self.batch_size = batch_size

        # Pre-compute which columns need date→string serialization
        self._date_columns = frozenset(
            col for col, sql_type in columns.items()
            if sql_type.upper() in _DATE_TYPES
        )

        # Staging types: swap DATE → VARCHAR(10) for legacy driver compat
        self._staging_types = {
            col: "VARCHAR(10)" if sql_type.upper() in _DATE_TYPES else sql_type
            for col, sql_type in columns.items()
        }

    def _create_staging_sql(self) -> str:
        col_defs = ",\n                ".join(
            f"{col}  {self._staging_types[col]}  NOT NULL"
            for col in self.columns
        )
        return f"""
            IF OBJECT_ID('tempdb..{self.staging_name}') IS NOT NULL
                DROP TABLE {self.staging_name};
            CREATE TABLE {self.staging_name} (
                {col_defs}
            );
        """

    def _insert_sql(self) -> str:
        col_list = ", ".join(self.columns)
        param_list = ", ".join(f":{col}" for col in self.columns)
        return f"""
            INSERT INTO {self.staging_name} ({col_list})
            VALUES ({param_list})
        """

    def _merge_sql(self) -> str:
        on_clause = " AND ".join(
            f"tgt.{col} = src.{col}" for col in self.natural_key
        )
        update_set = ",\n                    ".join(
            [f"tgt.{col} = src.{col}" for col in self.value_columns]
            + ["tgt.updated_at = SYSDATETIMEOFFSET()"]
        )
        all_cols = list(self.columns)
        insert_cols = ", ".join(all_cols + ["created_at", "updated_at"])
        insert_vals = ", ".join(
            [f"src.{col}" for col in all_cols]
            + ["SYSDATETIMEOFFSET()", "SYSDATETIMEOFFSET()"]
        )
        return f"""
            MERGE {self.target_table} AS tgt
            USING {self.staging_name} AS src
                ON {on_clause}
            WHEN MATCHED THEN
                UPDATE SET
                    {update_set}
            WHEN NOT MATCHED THEN
                INSERT ({insert_cols})
                VALUES ({insert_vals});
        """

    def serialize_row(self, item: BaseModel) -> dict[str, Any]:
        """Convert a Pydantic model to a parameter dict, handling date→string."""
        d = item.model_dump()
        for col in self._date_columns:
            val = d.get(col)
            if isinstance(val, (date, datetime)):
                d[col] = val.isoformat()
        return d


def bulk_merge(
    session: Session,
    spec: MergeSpec,
    items: Sequence[BaseModel],
) -> int:
    """Execute a temp-table → MERGE upsert.

    Returns the number of items submitted.
    """
    if not items:
        return 0

    conn = session.connection()

    # 1. Create staging table
    conn.execute(text(spec._create_staging_sql()))

    # 2. Batch insert into staging
    insert_sql = text(spec._insert_sql())
    for i in range(0, len(items), spec.batch_size):
        batch = items[i : i + spec.batch_size]
        rows = [spec.serialize_row(item) for item in batch]
        conn.execute(insert_sql, rows)

    # 3. MERGE
    result = conn.execute(text(spec._merge_sql()))
    merged = result.rowcount
    _log.info(
        "bulk_merge_complete",
        target=spec.target_table,
        total_items=len(items),
        rows_affected=merged,
    )

    # 4. Cleanup
    conn.execute(text(f"DROP TABLE IF EXISTS {spec.staging_name};"))

    return len(items)
