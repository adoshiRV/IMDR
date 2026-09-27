"""Real-DB test for the Citi FX proprietary-index vintage-aware loader.

Exercises the actual T-SQL (dedup -> cur_latest -> insert-new / insert-revision)
in fx.citi_fx_indices.load_values against a live IMDR database -- the module
calls the SQL "the runtime source of truth"; the unit tests only cover the pure
mirror. This closes that gap.

Self-seeds a throwaway series (a synthetic citi_tag that cannot collide with any
real Citi leaf) via upsert_series, exercises the lifecycle on a far-past
obs_date (1901-01-01), then cleans up with DELETEs on the fact + dim rows (CRUD,
no DDL).

Skipped unless IMDR_MSSQL_HOST + IMDR_MSSQL_DATABASE=IMDR are configured AND
migrations 120-122 have been applied (fx.dim_index_series exists).
"""
from __future__ import annotations

import datetime

import pytest
from sqlalchemy import text

from imdr.domains.fx import citi_fx_indices as csi

FAKE_OBS = datetime.date(1901, 1, 1)
FAKE_OBS_STR = FAKE_OBS.isoformat()
# Synthetic tag: parses cleanly (region SI_ZZZ -> no currency, sector __TEST__)
# but is not a real Citi leaf, so it can never collide with ingested data.
TEST_TAG = "FX.SURPRISE_INDEX.ESI.CESI.DM.SI_ZZZ.__PYTEST__"


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
    connector = MSSQLConnector(s)
    with connector.engine.connect() as conn:
        exists = conn.execute(
            text("SELECT OBJECT_ID('fx.dim_index_series', 'U')")
        ).scalar()
    if exists is None:
        pytest.skip("fx.dim_index_series not present — migrations 120-122 not applied yet")
    return connector


def _seed_series(connector) -> int:
    series = csi.build_series([TEST_TAG], currency_codes=set())
    tag_to_id = csi.upsert_series(connector, series)
    return tag_to_id[TEST_TAG]


def _cleanup(connector, series_id: int) -> None:
    with connector.engine.begin() as conn:
        conn.execute(
            text("DELETE FROM fx.fact_index_value WHERE series_id = :i AND obs_date = :d"),
            {"i": series_id, "d": FAKE_OBS_STR},
        )
        conn.execute(
            text("DELETE FROM fx.dim_index_series WHERE citi_tag = :t"),
            {"t": TEST_TAG},
        )


def _rows(connector, series_id: int) -> list[tuple[int, float]]:
    with connector.engine.connect() as conn:
        res = conn.execute(
            text(
                "SELECT vintage, value FROM fx.fact_index_value "
                "WHERE series_id = :i AND obs_date = :d ORDER BY vintage"
            ),
            {"i": series_id, "d": FAKE_OBS_STR},
        ).all()
    return [(int(v), float(val)) for v, val in res]


def _load(connector, series_id: int, value: float):
    row = csi.ValueRow(citi_tag=TEST_TAG, obs_date=FAKE_OBS, value=value)
    return csi.load_values(connector, [row], {TEST_TAG: series_id})


def test_load_values_revision_lifecycle():
    connector = _connector()
    series_id = _seed_series(connector)
    _cleanup(connector, series_id)  # clean slate (keep the just-seeded dim row)
    series_id = _seed_series(connector)
    try:
        # 1) brand-new obs -> vintage 0
        stats = _load(connector, series_id, 9.11)
        assert stats["inserted_new"] == 1
        assert stats["inserted_revision"] == 0
        assert _rows(connector, series_id) == [(0, 9.11)]

        # 2) same value re-load -> skip (idempotent)
        stats = _load(connector, series_id, 9.11)
        assert stats["inserted_new"] == 0
        assert stats["inserted_revision"] == 0
        assert stats["skipped"] == 1
        assert _rows(connector, series_id) == [(0, 9.11)]

        # 3) changed value -> revision at vintage 1 (old print preserved)
        stats = _load(connector, series_id, 9.22)
        assert stats["inserted_revision"] == 1
        assert _rows(connector, series_id) == [(0, 9.11), (1, 9.22)]

        # 4) latest view resolves to the revised value
        with connector.engine.connect() as conn:
            latest = conn.execute(
                text(
                    "SELECT vintage, value FROM fx.vw_fact_index_value_latest "
                    "WHERE series_id = :i AND obs_date = :d"
                ),
                {"i": series_id, "d": FAKE_OBS_STR},
            ).first()
        assert latest is not None
        assert int(latest[0]) == 1
        assert float(latest[1]) == 9.22
    finally:
        _cleanup(connector, series_id)
        assert _rows(connector, series_id) == []
