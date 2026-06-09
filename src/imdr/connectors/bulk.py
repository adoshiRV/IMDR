"""Shared temp-table → MERGE upsert for MSSQL.

Standardizes the bulk upsert pattern across fact-table repositories
(rates.fact_observation, fx.fact_vol, and future high-volume tables).

Handles the legacy 'SQL Server' ODBC driver quirk: datetime.date objects
cannot be bound via SQLBindParameter (HYC00 error). DATE columns are staged
as VARCHAR(10) with ISO strings; SQL Server converts implicitly on MERGE.

Every fact-table repository that writes through MSSQL routes its upserts
through `bulk_merge`, including the hourly FX OHLC repo (~17 rows/hour) —
ORM row-by-row was the pre-2026 pattern and has been retired.

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

import math
from collections.abc import Sequence
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

import structlog
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from imdr.connectors._sql_safety import (
    validate_column,
    validate_identifier,
    validate_staging,
)

if TYPE_CHECKING:
    from imdr.connectors.mssql import MSSQLConnector

_log = structlog.get_logger("bulk_merge")

# Legacy ODBC driver can't bind these Python types.
# Staged as VARCHAR; SQL Server converts implicitly on MERGE.
_DATE_TYPES = frozenset({"DATE", "SMALLDATETIME"})

_DEFAULT_BATCH_SIZE = 1000


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
        audit_columns: dict[str, str] | None = None,
        nullable_columns: list[str] | None = None,
    ) -> None:
        validate_identifier(target_table, "target_table")
        validate_staging(staging_name, "staging_name")
        for col in columns:
            validate_column(col, "column")
        for col in natural_key:
            validate_column(col, "natural_key column")
        for col in value_columns:
            validate_column(col, "value_column")
        for col in (nullable_columns or []):
            validate_column(col, "nullable_column")

        all_cols = set(columns)
        if not set(natural_key).issubset(all_cols):
            raise ValueError(f"natural_key columns not in columns: {set(natural_key) - all_cols}")
        if not set(value_columns).issubset(all_cols):
            raise ValueError(f"value_columns not in columns: {set(value_columns) - all_cols}")
        if nullable_columns and not set(nullable_columns).issubset(all_cols):
            raise ValueError(
                f"nullable_columns not in columns: {set(nullable_columns) - all_cols}"
            )

        self.target_table = target_table
        self.staging_name = staging_name
        self.columns = columns
        self.natural_key = natural_key
        self.value_columns = value_columns
        self.batch_size = batch_size
        self.nullable_columns: frozenset[str] = frozenset(nullable_columns or [])

        # Audit timestamp columns injected into MERGE SQL.
        # None = default (created_at + updated_at); pass {} to omit entirely.
        if audit_columns is None:
            self.audit_columns: dict[str, str] = {
                "created_at": "SYSDATETIMEOFFSET()",
                "updated_at": "SYSDATETIMEOFFSET()",
            }
        else:
            self.audit_columns = audit_columns

        # Pre-compute which columns need date→string serialization
        self._date_columns = frozenset(
            col for col, sql_type in columns.items()
            if sql_type.upper() in _DATE_TYPES
        )

        # Pre-compute which columns need Decimal→float conversion
        self._float_columns = frozenset(
            col for col, sql_type in columns.items()
            if sql_type.upper() == "FLOAT"
        )

        # Staging types: swap DATE → VARCHAR(10) for legacy driver compat
        self._staging_types = {
            col: "VARCHAR(10)" if sql_type.upper() in _DATE_TYPES else sql_type
            for col, sql_type in columns.items()
        }

        # SQL strings depend only on the immutable fields above, so build them
        # once at construction time instead of recomputing on every bulk_merge call.
        self.create_staging_sql = self._build_create_staging_sql()
        self.insert_sql = self._build_insert_sql()
        self.merge_sql = self._build_merge_sql()
        self.drop_staging_sql = f"DROP TABLE IF EXISTS {self.staging_name};"

    def _build_create_staging_sql(self) -> str:
        col_defs = ",\n                ".join(
            f"{col}  {self._staging_types[col]}  "
            f"{'NULL' if col in self.nullable_columns else 'NOT NULL'}"
            for col in self.columns
        )
        return f"""
            IF OBJECT_ID('tempdb..{self.staging_name}') IS NOT NULL
                DROP TABLE {self.staging_name};
            CREATE TABLE {self.staging_name} (
                {col_defs}
            );
        """

    def _build_insert_sql(self) -> str:
        col_list = ", ".join(self.columns)
        param_list = ", ".join(f":{col}" for col in self.columns)
        return f"""
            INSERT INTO {self.staging_name} ({col_list})
            VALUES ({param_list})
        """

    def _build_merge_sql(self) -> str:
        on_clause = " AND ".join(
            f"tgt.{col} = src.{col}" for col in self.natural_key
        )
        # UPDATE SET: value columns + any audit columns that should update on match
        update_parts = [f"tgt.{col} = src.{col}" for col in self.value_columns]
        if "updated_at" in self.audit_columns:
            update_parts.append(f"tgt.updated_at = {self.audit_columns['updated_at']}")
        update_set = ",\n                    ".join(update_parts)

        # INSERT: all data columns + all audit columns
        all_cols = list(self.columns)
        audit_keys = list(self.audit_columns.keys())
        insert_cols = ", ".join(all_cols + audit_keys)
        insert_vals = ", ".join(
            [f"src.{col}" for col in all_cols]
            + [self.audit_columns[k] for k in audit_keys]
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
        """Convert a Pydantic model to a parameter dict.

        Handles date→string (legacy ODBC compat) and Decimal→float conversions.
        """
        d = item.model_dump()
        for col in self._date_columns:
            val = d.get(col)
            if isinstance(val, (date, datetime)):
                d[col] = val.isoformat()
        for col in self._float_columns:
            val = d.get(col)
            if val is not None and not isinstance(val, float):
                d[col] = float(val)
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
    conn.execute(text(spec.create_staging_sql))

    # 2. Batch insert into staging
    insert_sql = text(spec.insert_sql)
    for i in range(0, len(items), spec.batch_size):
        batch = items[i : i + spec.batch_size]
        rows = [spec.serialize_row(item) for item in batch]
        conn.execute(insert_sql, rows)

    # 3. MERGE
    result = conn.execute(text(spec.merge_sql))
    merged = result.rowcount
    _log.info(
        "bulk_merge_complete",
        target=spec.target_table,
        total_items=len(items),
        rows_affected=merged,
    )

    # 4. Cleanup
    conn.execute(text(spec.drop_staging_sql))

    return len(items)


def chunked_bulk_merge(
    connector: MSSQLConnector,
    spec: MergeSpec,
    items: Sequence[BaseModel],
    chunk_size: int = 5000,
) -> int:
    """Execute bulk merge in chunks with intermediate commits.

    Unlike bulk_merge() which operates within an existing session/transaction,
    this function manages its own sessions and commits per chunk.  Designed for
    large historical backfills where a single giant MERGE would hold locks too
    long and stress tempdb.

    For small loads (<= chunk_size) this is a single chunk — minimal overhead.
    MERGE is idempotent so partial completion on crash is safe to re-run.
    """
    if not items:
        return 0

    n_chunks = math.ceil(len(items) / chunk_size)
    total = 0

    for i in range(0, len(items), chunk_size):
        chunk = items[i : i + chunk_size]
        with connector.session() as session:
            bulk_merge(session, spec, chunk)
        total += len(chunk)
        _log.info(
            "chunked_merge_progress",
            target=spec.target_table,
            chunk=i // chunk_size + 1,
            n_chunks=n_chunks,
            chunk_rows=len(chunk),
            total_so_far=total,
            total_items=len(items),
        )

    _log.info(
        "chunked_merge_complete",
        target=spec.target_table,
        total_items=total,
        chunks=n_chunks,
    )
    return total
