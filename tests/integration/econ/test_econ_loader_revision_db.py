"""Real-DB test for the revision-aware fact loader (_load_fact).

Exercises the actual T-SQL (dedup -> cur_latest -> insert-new / insert-revision)
against a live IMDR database -- the module docstring calls the SQL "the runtime
source of truth", and the pure-Python mirror test (test_econ_loader_revisions.py)
does NOT cover the SQL. This closes that gap.

Uses an EXISTING dim_indicator plus a throwaway far-past obs_date (1901-01-01)
that cannot collide with any real observation, so no dim setup is needed and
cleanup is an unambiguous DELETE on that one (indicator_id, obs_date). DELETE is
allowed CRUD per project rules -- no DDL.

Skipped unless IMDR_MSSQL_HOST + IMDR_MSSQL_DATABASE=IMDR are configured.
"""
from __future__ import annotations

import datetime

import pandas as pd
import pytest
from sqlalchemy import text

# A real quarterly reference date will never be 1 Jan 1901.
FAKE_OBS = datetime.date(1901, 1, 1)
# The legacy "SQL Server" ODBC driver can't bind a Python date param
# (SQLBindParameter HYC00); pass the date as an ISO string in text() queries
# and let SQL Server implicitly convert. The loader's own insert path uses the
# raw pyodbc cursor and is unaffected.
FAKE_OBS_STR = FAKE_OBS.isoformat()
PROBE_CODE = "BOK.GDP.GDP.QOQ_SA.KR"


def _connector():
    try:
        from imdr.config.settings import get_settings  # noqa: PLC0415
        from imdr.connectors.mssql import MSSQLConnector  # noqa: PLC0415
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"imdr settings/connector unavailable: {exc}")
    s = get_settings()
    if s.mssql_database != "IMDR":
        pytest.skip(f"Refusing to run on non-IMDR database ({s.mssql_database!r})")
    if not s.mssql_host or s.mssql_host == "localhost":
        pytest.skip("IMDR_MSSQL_HOST not configured — real-DB integration test")
    return MSSQLConnector(s)


def _resolve_id(connector) -> int:
    with connector.engine.connect() as conn:
        row = conn.execute(
            text("SELECT id FROM econ.dim_indicator WHERE imdr_code = :c"),
            {"c": PROBE_CODE},
        ).first()
    if row is None:
        pytest.skip(f"probe indicator {PROBE_CODE} not in dim_indicator")
    return int(row[0])


def _delete_fake(connector, ind_id: int) -> None:
    with connector.engine.begin() as conn:
        conn.execute(
            text("DELETE FROM econ.fact_indicator WHERE indicator_id = :i AND obs_date = :d"),
            {"i": ind_id, "d": FAKE_OBS_STR},
        )


def _rows(connector, ind_id: int) -> list[tuple[int, float | None]]:
    """(vintage, value) for the fake obs, ordered by vintage."""
    with connector.engine.connect() as conn:
        res = conn.execute(
            text(
                "SELECT vintage, value FROM econ.fact_indicator "
                "WHERE indicator_id = :i AND obs_date = :d ORDER BY vintage"
            ),
            {"i": ind_id, "d": FAKE_OBS_STR},
        ).all()
    return [(int(v), None if val is None else float(val)) for v, val in res]


def _load(connector, ind_id: int, value):
    from scripts.migrations.load_econ_indicator_from_playground import _load_fact  # noqa: PLC0415

    now = datetime.datetime.now(datetime.timezone.utc)
    df = pd.DataFrame(
        [{
            "imdr_code": PROBE_CODE,
            "obs_date": FAKE_OBS,
            "vintage": 0,
            "release_date": now,
            "value": value,
            "is_preliminary": False,
        }]
    )
    return _load_fact(connector, df, {PROBE_CODE: ind_id})


def test_load_fact_revision_lifecycle():
    connector = _connector()
    ind_id = _resolve_id(connector)
    _delete_fake(connector, ind_id)  # guarantee clean slate
    try:
        # 1) brand-new obs -> vintage 0
        stats = _load(connector, ind_id, 9.11)
        assert stats["inserted_new"] == 1
        assert stats["inserted_revision"] == 0
        assert _rows(connector, ind_id) == [(0, 9.11)]

        # 2) same value re-load -> skip (idempotent), no new row
        stats = _load(connector, ind_id, 9.11)
        assert stats["inserted_new"] == 0
        assert stats["inserted_revision"] == 0
        assert stats["skipped"] == 1
        assert _rows(connector, ind_id) == [(0, 9.11)]

        # 3) changed value -> revision at vintage 1 (old print preserved)
        stats = _load(connector, ind_id, 9.22)
        assert stats["inserted_revision"] == 1
        assert _rows(connector, ind_id) == [(0, 9.11), (1, 9.22)]

        # 4) NULL incoming -> never clobbers; no new row
        stats = _load(connector, ind_id, None)
        assert stats["inserted_new"] == 0
        assert stats["inserted_revision"] == 0
        assert _rows(connector, ind_id) == [(0, 9.11), (1, 9.22)]

        # 5) latest-vintage view resolves to the revised value
        with connector.engine.connect() as conn:
            latest = conn.execute(
                text(
                    "SELECT vintage, value FROM econ.vw_fact_indicator_latest "
                    "WHERE indicator_id = :i AND obs_date = :d"
                ),
                {"i": ind_id, "d": FAKE_OBS_STR},
            ).first()
        assert latest is not None
        assert int(latest[0]) == 1
        assert float(latest[1]) == 9.22
    finally:
        _delete_fake(connector, ind_id)
        # confirm cleanup
        assert _rows(connector, ind_id) == []
