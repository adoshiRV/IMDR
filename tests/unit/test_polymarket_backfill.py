from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import pytest

from scripts.prediction.polymarket import backfill

_DDL = """
CREATE TABLE market_observation (
    snapshot_ts        TEXT NOT NULL,
    condition_id       TEXT NOT NULL,
    event_id           INTEGER,
    event_slug         TEXT,
    event_title        TEXT,
    question           TEXT,
    yes_price          REAL,
    no_price           REAL,
    best_bid           REAL,
    best_ask           REAL,
    spread             REAL,
    last_trade_price   REAL,
    volume_total       REAL,
    volume_24h         REAL,
    liquidity          REAL,
    updated_at_src     TEXT,
    PRIMARY KEY (snapshot_ts, condition_id)
);
"""


def _epoch(y, mo, d, h=0, mi=0) -> int:
    return int(datetime(y, mo, d, h, mi, tzinfo=timezone.utc).timestamp())


@pytest.fixture
def conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.executescript(_DDL)
    return c


def _seed(conn: sqlite3.Connection, snap_iso: str, cond: str = "0xC1") -> None:
    conn.execute(
        "INSERT INTO market_observation (snapshot_ts, condition_id, event_slug) "
        "VALUES (?,?,?)",
        [snap_iso, cond, "fed-decision-in-july"],
    )
    conn.commit()


def _fake_event() -> dict:
    return {
        "id": 1,
        "slug": "fed-decision-in-july",
        "title": "Fed decision in July",
        "markets": [
            {
                "conditionId": "0xC1",
                "question": "25 bps cut?",
                "clobTokenIds": '["tokYES", "tokNO"]',
            }
        ],
    }


class TestParseTs:
    def test_epoch_passthrough(self) -> None:
        assert backfill._parse_ts("1700000000") == 1700000000

    def test_date_assumed_utc(self) -> None:
        assert backfill._parse_ts("2026-06-13") == _epoch(2026, 6, 13)

    def test_datetime_naive_assumed_utc(self) -> None:
        assert backfill._parse_ts("2026-06-13T18:00") == _epoch(2026, 6, 13, 18, 0)

    def test_datetime_with_z(self) -> None:
        assert backfill._parse_ts("2026-06-13T18:00:00Z") == _epoch(2026, 6, 13, 18, 0)


class TestWindowBackfill:
    def test_fills_interior_gap(self, conn, monkeypatch) -> None:
        # Live rows exist on either side of the gap (06-13 18:00 .. 06-15 00:00).
        _seed(conn, "2026-06-08T00:00:00+00:00")
        _seed(conn, "2026-06-15T02:00:00+00:00")

        monkeypatch.setattr(backfill, "fetch_event", lambda slug: _fake_event())

        captured = {}

        def fake_hist(token, start_ts, end_ts, fidelity):
            captured["start_ts"] = start_ts
            captured["end_ts"] = end_ts
            # one point inside the requested window
            return [{"t": _epoch(2026, 6, 14, 12, 0), "p": "0.93"}]

        monkeypatch.setattr(backfill, "fetch_history", fake_hist)

        n_mkts, n_rows, msg = backfill.backfill_slug_window(
            conn, "fed-decision-in-july",
            start_ts=_epoch(2026, 6, 13, 18, 0),
            end_ts=_epoch(2026, 6, 15, 0, 0),
            fidelity=15,
        )
        assert (n_mkts, n_rows, msg) == (1, 1, "ok")
        row = conn.execute(
            "SELECT yes_price, no_price FROM market_observation "
            "WHERE snapshot_ts='2026-06-14T12:00:00.000000+00:00'"
        ).fetchone()
        assert row == (0.93, pytest.approx(0.07))
        # global-max cap (06-15 02:00) is later than requested end, so the
        # window is passed through untouched.
        assert captured["end_ts"] == _epoch(2026, 6, 15, 0, 0)

    def test_trailing_point_past_end_is_dropped(self, conn, monkeypatch) -> None:
        # CLOB /prices-history ignores endTs and appends a trailing near-current
        # point. It must be filtered out, else it overtakes the live MAX and
        # breaks macro_snapshot. Only the in-window point should be written.
        _seed(conn, "2026-06-08T00:00:00+00:00")
        _seed(conn, "2026-06-15T02:00:00+00:00")
        monkeypatch.setattr(backfill, "fetch_event", lambda slug: _fake_event())

        end = _epoch(2026, 6, 15, 0, 0)
        monkeypatch.setattr(
            backfill, "fetch_history",
            lambda *a, **k: [
                {"t": _epoch(2026, 6, 14, 12, 0), "p": "0.90"},   # in window
                {"t": end + 9000, "p": "0.95"},                   # trailing, past end
            ],
        )
        n_mkts, n_rows, msg = backfill.backfill_slug_window(
            conn, "fed-decision-in-july",
            start_ts=_epoch(2026, 6, 13, 18, 0), end_ts=end, fidelity=15,
        )
        assert (n_mkts, n_rows, msg) == (1, 1, "ok")
        # nothing written past the window end
        late = conn.execute(
            "SELECT count(*) FROM market_observation WHERE snapshot_ts > ?",
            ["2026-06-15T00:00:00.000000+00:00"],
        ).fetchone()[0]
        # only the pre-existing seed at 02:00 remains beyond the end
        assert late == 1

    def test_end_ts_capped_below_global_max(self, conn, monkeypatch) -> None:
        # Latest live row is BEFORE the requested window end → end must be clamped.
        _seed(conn, "2026-06-14T00:00:00+00:00")
        monkeypatch.setattr(backfill, "fetch_event", lambda slug: _fake_event())

        captured = {}

        def fake_hist(token, start_ts, end_ts, fidelity):
            captured["end_ts"] = end_ts
            return []

        monkeypatch.setattr(backfill, "fetch_history", fake_hist)

        backfill.backfill_slug_window(
            conn, "fed-decision-in-july",
            start_ts=_epoch(2026, 6, 13, 0, 0),
            end_ts=_epoch(2026, 6, 20, 0, 0),  # far in the future
            fidelity=15,
        )
        # capped to one second below the global MAX(snapshot_ts)
        assert captured["end_ts"] == _epoch(2026, 6, 14, 0, 0) - 1

    def test_collapsed_window_writes_nothing(self, conn, monkeypatch) -> None:
        _seed(conn, "2026-06-14T00:00:00+00:00")
        monkeypatch.setattr(backfill, "fetch_event", lambda slug: _fake_event())
        monkeypatch.setattr(
            backfill, "fetch_history",
            lambda *a, **k: pytest.fail("fetch_history should not be called"),
        )
        n_mkts, n_rows, msg = backfill.backfill_slug_window(
            conn, "fed-decision-in-july",
            start_ts=_epoch(2026, 6, 15, 0, 0),   # after the global-max cap
            end_ts=_epoch(2026, 6, 16, 0, 0),
            fidelity=15,
        )
        assert (n_mkts, n_rows, msg) == (0, 0, "window collapsed after global-max cap")

    def test_insert_or_ignore_does_not_clobber_live_row(self, conn, monkeypatch) -> None:
        # A live row already exists at the exact instant the backfill point lands.
        live_ts = "2026-06-14T12:00:00.000000+00:00"
        conn.execute(
            "INSERT INTO market_observation (snapshot_ts, condition_id, event_slug, yes_price) "
            "VALUES (?,?,?,?)",
            [live_ts, "0xC1", "fed-decision-in-july", 0.5],
        )
        _seed(conn, "2026-06-15T02:00:00+00:00", cond="0xOTHER")
        monkeypatch.setattr(backfill, "fetch_event", lambda slug: _fake_event())
        monkeypatch.setattr(
            backfill, "fetch_history",
            lambda *a, **k: [{"t": _epoch(2026, 6, 14, 12, 0), "p": "0.93"}],
        )
        backfill.backfill_slug_window(
            conn, "fed-decision-in-july",
            start_ts=_epoch(2026, 6, 13, 18, 0),
            end_ts=_epoch(2026, 6, 15, 0, 0),
            fidelity=15,
        )
        # live value preserved, NOT overwritten by the 0.93 backfill point
        kept = conn.execute(
            "SELECT yes_price FROM market_observation WHERE snapshot_ts=? AND condition_id='0xC1'",
            [live_ts],
        ).fetchone()[0]
        assert kept == 0.5
