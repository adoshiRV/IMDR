"""Unit tests for mcp/server.py helpers — schema-free, no DB required."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


def _load_mcp_server_module():
    """Load mcp/server.py without triggering its module-level engine creation.

    The server module creates an engine and prints to stderr at import. We
    monkey-patch sqlalchemy.create_engine and the FastMCP server before import
    so the helpers (`_inject_top`, `_assert_readonly`, `_validate_column`) can
    be imported and unit-tested in isolation.
    """
    if "mcp_server_under_test" in sys.modules:
        return sys.modules["mcp_server_under_test"]

    import sqlalchemy
    from sqlalchemy.engine import Engine

    real_create_engine = sqlalchemy.create_engine

    class _FakeEngine:
        def __init__(self, *_a, **_kw):
            pass

        def connect(self):  # pragma: no cover — never called in helper tests
            raise RuntimeError("DB not available in unit tests")

    def _fake_create_engine(*_a, **_kw) -> Engine:  # type: ignore[return-value]
        return _FakeEngine()  # type: ignore[return-value]

    sqlalchemy.create_engine = _fake_create_engine  # type: ignore[assignment]
    try:
        repo_root = Path(__file__).resolve().parents[2]
        spec = importlib.util.spec_from_file_location(
            "mcp_server_under_test", repo_root / "mcp" / "server.py"
        )
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules["mcp_server_under_test"] = module
        spec.loader.exec_module(module)
    finally:
        sqlalchemy.create_engine = real_create_engine  # type: ignore[assignment]
    return module


@pytest.fixture(scope="module")
def server():
    return _load_mcp_server_module()


# ────────────────────────────────────────────────────────────────────
# _inject_top — must cap the OUTERMOST SELECT, never an inner one.
# ────────────────────────────────────────────────────────────────────


def test_inject_top_plain_select(server):
    out = server._inject_top("SELECT id FROM t", 100)
    assert out == "SELECT TOP(100) id FROM t"


def test_inject_top_distinct(server):
    out = server._inject_top("SELECT DISTINCT id FROM t", 50)
    assert out == "SELECT DISTINCT TOP(50) id FROM t"


def test_inject_top_already_present_is_unchanged(server):
    sql = "SELECT TOP(10) id FROM t"
    assert server._inject_top(sql, 100) == sql


def test_inject_top_with_subquery_caps_outer_only(server):
    """Regression: prior code injected at parts[-1], capping the inner SELECT
    and producing wrong outer results."""
    sql = "SELECT a FROM (SELECT a, b FROM t1 JOIN t2 ON t1.k = t2.k) sub"
    out = server._inject_top(sql, 500)
    # TOP must be on the OUTER select, the inner subquery untouched.
    assert out.startswith("SELECT TOP(500) a FROM (SELECT a, b FROM t1 JOIN t2")
    assert "(SELECT TOP(500)" not in out


def test_inject_top_with_cte(server):
    """For WITH/CTE queries, TOP must wrap the final SELECT, not the CTE body
    (which would truncate intermediate rows before the join completes)."""
    sql = "WITH x AS (SELECT a, b FROM t1) SELECT a FROM x JOIN t2 ON x.a = t2.a"
    out = server._inject_top(sql, 500)
    # Inner CTE SELECT must NOT have TOP.
    assert "WITH x AS (SELECT a, b FROM t1)" in out
    # Outer SELECT must have TOP.
    assert "SELECT TOP(500) a FROM x JOIN t2" in out


def test_inject_top_with_correlated_subquery_in_select_list(server):
    sql = "SELECT a, (SELECT MAX(b) FROM t2) AS max_b FROM t1"
    out = server._inject_top(sql, 100)
    assert out.startswith("SELECT TOP(100) a, (SELECT MAX(b) FROM t2)")
    # The inner correlated subquery must NOT receive TOP.
    assert "(SELECT TOP" not in out


def test_inject_top_no_select_returns_unchanged(server):
    assert server._inject_top("EXEC sp_help", 100) == "EXEC sp_help"


# ────────────────────────────────────────────────────────────────────
# _assert_readonly — sanity checks (full hardening covered in Phase 4.2).
# ────────────────────────────────────────────────────────────────────


def test_assert_readonly_accepts_select(server):
    server._assert_readonly("SELECT 1")


def test_assert_readonly_accepts_with_cte(server):
    server._assert_readonly("WITH x AS (SELECT 1 AS a) SELECT a FROM x")


def test_assert_readonly_rejects_insert(server):
    with pytest.raises(ValueError):
        server._assert_readonly("INSERT INTO t VALUES (1)")


def test_assert_readonly_rejects_select_into(server):
    with pytest.raises(ValueError):
        server._assert_readonly("SELECT * INTO new_t FROM t")


def test_assert_readonly_rejects_semicolon(server):
    with pytest.raises(ValueError):
        server._assert_readonly("SELECT 1; SELECT 2")


def test_assert_readonly_rejects_inline_comment(server):
    with pytest.raises(ValueError):
        server._assert_readonly("SELECT 1 -- comment")


# Adversarial cases — confirm bypass attempts are blocked.
# These lock in the safety contract; future relaxations must keep them passing.


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT 1; DROP TABLE t",
        "SELECT 1; INSERT INTO t VALUES (1)",
        "WITH x AS (SELECT 1) SELECT * FROM x; DELETE FROM t",
        "SELECT 1 /* drop */ ; UPDATE t SET a = 1",
        "EXEC sp_executesql N'SELECT 1'",
        "EXECUTE xp_cmdshell 'dir'",
        "SELECT 1; EXEC xp_cmdshell 'dir'",
        "SELECT * FROM OPENROWSET('SQLNCLI', '...', 'SELECT * FROM t')",
        "SELECT * FROM OPENDATASOURCE('SQLNCLI', '...').db.dbo.t",
        "WAITFOR DELAY '00:00:05'; SELECT 1",
        "SELECT 1 WAITFOR DELAY '00:00:05'",
        "BULK INSERT t FROM 'c:\\a.csv'",
        "SELECT 1 /**/ ; DROP TABLE t",
        "SELECT * INTO new_t FROM t",
        "MERGE INTO t USING s ON t.k = s.k WHEN MATCHED THEN UPDATE SET t.a = s.a",
        "GRANT SELECT ON t TO public",
        "TRUNCATE TABLE t",
        "DBCC CHECKDB",
        "SHUTDOWN",
        # whitespace/comment tricks — comment markers themselves trigger reject
        "EXEC/**/sp_who",
        "EXEC /*hi*/ sp_who",
    ],
)
def test_assert_readonly_blocks_adversarial(server, sql):
    with pytest.raises(ValueError):
        server._assert_readonly(sql)


# ────────────────────────────────────────────────────────────────────
# _validate_column — identifier safety.
# ────────────────────────────────────────────────────────────────────


def test_validate_column_accepts_word(server):
    server._validate_column("fact_observation", "table")


def test_validate_column_rejects_dot(server):
    with pytest.raises(ValueError):
        server._validate_column("rates.fact", "table")


def test_validate_column_rejects_quote(server):
    with pytest.raises(ValueError):
        server._validate_column("t'; DROP TABLE", "table")
