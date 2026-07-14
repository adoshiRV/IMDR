r"""IMDR MCP Server — read-only database access for Claude Desktop / Claude Code.

Exposes three tools:
  - list_tables:    browse available tables
  - describe_table: inspect column metadata
  - query:          execute read-only SELECT queries

All queries via the `query` tool are audit-logged to [admin].[mcp_query_log].

NOTE: This file is intentionally self-contained.  It does NOT import from
the imdr package (which pulls in pandas, structlog, etc.) so that startup
stays fast enough for Claude Desktop's ~5-second init timeout — especially
when the repo lives on a network share (Z:\).
"""

from __future__ import annotations

import os
import re
import sys
import time
import traceback

print("[imdr-mcp] server.py loading…", file=sys.stderr)

try:
    from mcp.server.fastmcp import FastMCP
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import Engine
    from sqlalchemy.orm import Session, sessionmaker
    print("[imdr-mcp] imports OK", file=sys.stderr)
except Exception:
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)


# ── Settings (inline — avoids importing imdr.config.settings) ────

def _load_env_file() -> None:
    """Best-effort load of DB-related .env vars into os.environ."""
    from pathlib import Path
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key.startswith("IMDR_MSSQL_") or key.startswith("IMDR_POOL_"):
            os.environ.setdefault(key, value.strip())


try:
    _load_env_file()
    _DB_HOST = os.environ.get("IMDR_MSSQL_HOST", "localhost")
    _DB_PORT = os.environ.get("IMDR_MSSQL_PORT", "1433")
    _DB_NAME = os.environ.get("IMDR_MSSQL_DATABASE", "IMDR")
    _DB_DRIVER = os.environ.get("IMDR_MSSQL_DRIVER", "ODBC+Driver+17+for+SQL+Server")
    _CONN_URL = (
        f"mssql+pyodbc://@{_DB_HOST}:{_DB_PORT}/{_DB_NAME}"
        f"?driver={_DB_DRIVER}&Trusted_Connection=yes"
    )
    print(f"[imdr-mcp] Settings loaded: host={_DB_HOST}", file=sys.stderr)
except Exception:
    print("[imdr-mcp] FATAL: Settings load failed", file=sys.stderr)
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)


# ── Database engine (inline — avoids importing imdr.connectors) ──

try:
    _engine: Engine = create_engine(
        _CONN_URL,
        pool_size=5,
        max_overflow=10,
        pool_timeout=30,
        pool_pre_ping=True,
        echo=False,
        use_setinputsizes=False,
    )
    _session_factory = sessionmaker(bind=_engine, expire_on_commit=False)
    print("[imdr-mcp] Engine created", file=sys.stderr)
except Exception:
    print("[imdr-mcp] FATAL: Engine creation failed", file=sys.stderr)
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)

try:
    _MCP_USER = os.getlogin()
except OSError:
    _MCP_USER = os.environ.get("USERNAME", os.environ.get("USER", "unknown"))
    print(f"[imdr-mcp] os.getlogin() failed, using fallback: {_MCP_USER}", file=sys.stderr)

print(f"[imdr-mcp] startup complete — user={_MCP_USER}", file=sys.stderr)


# ── SQL safety ────────────────────────────────────────────────

_COLUMN_RE = re.compile(r"^[\w]+$")

_DML_DDL_RE = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|"
    r"EXEC|EXECUTE|GRANT|REVOKE|MERGE|WAITFOR|DBCC|"
    r"BACKUP|RESTORE|SHUTDOWN|OPENROWSET|OPENDATASOURCE|"
    r"BULK\s+INSERT)\b",
    re.IGNORECASE,
)
_DANGEROUS_RE = re.compile(r"(--|/\*|\bxp_|\bsp_|;)")


def _validate_column(value: str, label: str) -> None:
    """Ensure a column/schema/table name is a simple word."""
    if not _COLUMN_RE.match(value):
        raise ValueError(f"Invalid {label}: {value!r}. Expected alphanumeric name.")


def _assert_readonly(sql: str) -> None:
    """Raise ValueError if *sql* is not a safe read-only statement."""
    stripped = sql.strip()
    if not re.match(r"^(SELECT|WITH)\b", stripped, re.IGNORECASE):
        raise ValueError("Only SELECT / WITH queries are permitted.")
    if _DML_DDL_RE.search(sql):
        raise ValueError("DML/DDL keywords detected — query rejected.")
    if _DANGEROUS_RE.search(sql):
        raise ValueError("Dangerous pattern detected (comment / xp_ / sp_ / semicolon).")
    if re.search(r"\bINTO\b", sql, re.IGNORECASE):
        raise ValueError("INTO keyword detected — query rejected.")


# ── Audit logging ─────────────────────────────────────────────

def _log_query(
    sql_text: str,
    row_count: int | None,
    execution_ms: int | None,
    error: str | None,
) -> None:
    """Best-effort INSERT into [admin].[mcp_query_log]. Never raises."""
    try:
        session = _session_factory()
        try:
            session.execute(
                text(
                    "INSERT INTO [admin].[mcp_query_log] "
                    "(sql_text, called_by, row_count, execution_ms, error_message) "
                    "VALUES (:sql, :user, :rows, :ms, :err)"
                ),
                {
                    "sql": sql_text[:4000],
                    "user": _MCP_USER,
                    "rows": row_count,
                    "ms": execution_ms,
                    "err": str(error)[:2000] if error else None,
                },
            )
            session.commit()
        except Exception as audit_err:
            print(f"[imdr-mcp] audit-log failed: {audit_err}", file=sys.stderr)
            session.rollback()
        finally:
            session.close()
    except Exception as audit_err:
        print(f"[imdr-mcp] audit-log session failed: {audit_err}", file=sys.stderr)


# ── MCP server ────────────────────────────────────────────────

INSTRUCTIONS = """\
You have direct read-only access to IMDR (Internal Market Data Repository),
a SQL Server database.

Schemas: audit, fx, rates (more may be added).
Conventions:
  - Fact tables prefixed fact_, dimension tables prefixed dim_
  - All timestamps are DATETIMEOFFSET
  - Only SELECT queries are permitted

Always call list_tables or describe_table first if unsure of schema.
"""

mcp = FastMCP("imdr-db", instructions=INSTRUCTIONS)


# Tables hidden from non-admin users — internal infra / archived copies
# the MCP consumer shouldn't browse or query. Tables matching `*_old`
# are also hidden (legacy snapshots from migrations).
_HIDDEN_TABLES: frozenset[tuple[str, str]] = frozenset({
    ("admin", "mcp_query_log"),
    ("audit", "pipeline_runs"),
    ("rates", "cache_empty_combo"),
})

# Windows logins exempt from the hide — keyed off os.getlogin(), since
# that's all the MCP server can see. adoshi@rvcapital.com → "adoshi".
_ADMIN_USERS: frozenset[str] = frozenset({"adoshi", "tolsen"})


def _is_admin_user() -> bool:
    return _MCP_USER.lower() in _ADMIN_USERS


def _is_hidden(schema: str, table: str) -> bool:
    if (schema, table) in _HIDDEN_TABLES:
        return True
    return table.endswith("_old") or "_old_" in table


def _assert_no_hidden_refs(sql: str) -> None:
    """For non-admins, reject queries that reference a hidden table by name."""
    if _is_admin_user():
        return
    for _, table in _HIDDEN_TABLES:
        if re.search(rf"\b{re.escape(table)}\b", sql, re.IGNORECASE):
            raise ValueError(f"Table not found.")
    if re.search(r"\b\w+_old\b", sql, re.IGNORECASE):
        raise ValueError("Table not found.")


@mcp.tool()
def list_tables(schema: str = "") -> str:
    """List all tables in IMDR, optionally filtered by schema name."""
    with _engine.connect() as conn:
        if schema:
            _validate_column(schema, "schema")
            rows = conn.execute(
                text(
                    "SELECT TABLE_SCHEMA, TABLE_NAME "
                    "FROM INFORMATION_SCHEMA.TABLES "
                    "WHERE TABLE_TYPE = 'BASE TABLE' AND TABLE_SCHEMA = :s "
                    "ORDER BY TABLE_SCHEMA, TABLE_NAME"
                ),
                {"s": schema},
            ).fetchall()
        else:
            rows = conn.execute(
                text(
                    "SELECT TABLE_SCHEMA, TABLE_NAME "
                    "FROM INFORMATION_SCHEMA.TABLES "
                    "WHERE TABLE_TYPE = 'BASE TABLE' "
                    "ORDER BY TABLE_SCHEMA, TABLE_NAME"
                )
            ).fetchall()

    admin = _is_admin_user()
    visible = [r for r in rows if admin or not _is_hidden(r[0], r[1])]
    if not visible:
        return "No tables found."
    return "\n".join(f"{r[0]}.{r[1]}" for r in visible)


@mcp.tool()
def describe_table(schema: str, table: str) -> str:
    """Return column names, data types, and nullability for a table."""
    _validate_column(schema, "schema")
    _validate_column(table, "table")

    if _is_hidden(schema, table) and not _is_admin_user():
        return f"Table {schema}.{table} not found."

    with _engine.connect() as conn:
        cols = conn.execute(
            text(
                "SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, "
                "CHARACTER_MAXIMUM_LENGTH, NUMERIC_PRECISION, NUMERIC_SCALE "
                "FROM INFORMATION_SCHEMA.COLUMNS "
                "WHERE TABLE_SCHEMA = :s AND TABLE_NAME = :t "
                "ORDER BY ORDINAL_POSITION"
            ),
            {"s": schema, "t": table},
        ).fetchall()

        if not cols:
            return f"Table {schema}.{table} not found."

        count = conn.execute(
            text(
                "SELECT SUM(p.rows) "
                "FROM sys.partitions p "
                "JOIN sys.tables t ON p.object_id = t.object_id "
                "JOIN sys.schemas s ON t.schema_id = s.schema_id "
                "WHERE s.name = :s AND t.name = :t AND p.index_id IN (0, 1)"
            ),
            {"s": schema, "t": table},
        ).scalar() or 0

    lines = [f"{schema}.{table}  ({count:,} rows)", ""]
    for r in cols:
        dtype = r[1]
        if r[3] and r[3] > 0:
            dtype += f"({r[3]})"
        elif r[4] is not None:
            dtype += f"({r[4]},{r[5]})"
        nullable = "NULL" if r[2] == "YES" else "NOT NULL"
        lines.append(f"  {r[0]:30} {dtype:25} {nullable}")

    return "\n".join(lines)


_QUERY_TIMEOUT_S = 30  # hard cap on MCP query execution time
_MAX_QUERY_LENGTH = 4000  # matches audit log sql_text column width


def _inject_top(sql: str, max_rows: int) -> str:
    """Inject TOP(N) into the outermost SELECT to limit work at the SQL Server level.

    Uses the FIRST SELECT (outermost) — capping an inner subquery or CTE would
    truncate intermediate rows before joins/filters complete, producing wrong
    results. For ``WITH cte AS (SELECT …) SELECT … FROM cte``, the first SELECT
    sits inside the CTE; we skip past leading ``WITH`` clauses to the top-level
    SELECT.
    """
    if re.search(r"\bTOP\s*\(?\s*\d+", sql, re.IGNORECASE):
        return sql
    # If the query starts with WITH, target the first SELECT after the CTE
    # definitions close. We approximate this by finding the SELECT that is
    # not preceded by an unmatched '(' — i.e., at depth 0.
    target: re.Match[str] | None = None
    depth = 0
    for m in re.finditer(r"\(|\)|\bSELECT\b(?:\s+DISTINCT)?", sql, re.IGNORECASE):
        token = m.group(0)
        if token == "(":
            depth += 1
        elif token == ")":
            depth = max(0, depth - 1)
        elif depth == 0:
            target = m
            break
    if target is None:
        return sql
    return sql[: target.end()] + f" TOP({max_rows})" + sql[target.end() :]


@mcp.tool()
def query(sql: str, max_rows: int = 500) -> str:
    """Execute a read-only SELECT query against IMDR.

    Use list_tables and describe_table first to understand the schema.
    max_rows defaults to 500. Only SELECT / WITH queries are permitted.
    """
    if len(sql) > _MAX_QUERY_LENGTH:
        raise ValueError(f"Query too long ({len(sql)} chars). Maximum is {_MAX_QUERY_LENGTH}.")
    _assert_readonly(sql)
    _assert_no_hidden_refs(sql)
    sql = _inject_top(sql, max_rows)

    start = time.perf_counter()
    try:
        with _engine.connect() as conn:
            raw_conn = conn.connection.dbapi_connection
            raw_conn.timeout = _QUERY_TIMEOUT_S
            result = conn.execute(text(sql))
            cols = [d[0] for d in result.cursor.description]
            rows = result.fetchmany(max_rows)

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        _log_query(sql, len(rows), elapsed_ms, None)

        if not rows:
            return "Query returned no rows."

        col_widths = [
            max(len(c), max(len(str(r[i])) for r in rows))
            for i, c in enumerate(cols)
        ]
        col_widths = [min(w, 60) for w in col_widths]

        header = " | ".join(c.ljust(col_widths[i]) for i, c in enumerate(cols))
        divider = "-+-".join("-" * w for w in col_widths)
        data = [
            " | ".join(str(r[i])[:60].ljust(col_widths[i]) for i in range(len(cols)))
            for r in rows
        ]

        truncated = f"\n(showing {len(rows)} of {max_rows} max rows)" if len(rows) == max_rows else ""
        return "\n".join([header, divider] + data) + f"\n\n{len(rows)} row(s) returned.{truncated}"

    except ValueError:
        raise
    except Exception as e:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        _log_query(sql, 0, elapsed_ms, str(e))
        return f"Error: query failed ({type(e).__name__}). Details logged to audit."


if __name__ == "__main__":
    print("[imdr-mcp] calling mcp.run()", file=sys.stderr)
    try:
        mcp.run()
    except Exception:
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)
