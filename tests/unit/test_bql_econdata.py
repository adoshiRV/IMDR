"""Unit tests for the BQL econ-calendar loader (imdr.market_calendar.bql_econdata).

Pure-function + read/dedup tests against a throwaway tmp SQLite DB shaped like
the real ``bql_events`` table — no SQL Server / IMDR DB connection needed.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from datetime import date

from imdr.market_calendar.bql_econdata import (
    BqlEvent,
    UpsertResult,
    _map_country_code,
    _parse_datetime,
    _relevance,
    default_window,
    read_bql_events,
    upsert_events,
)

_COLS = [
    "date", "time", "country_code", "name", "display_name", "category",
    "category_label", "tier", "tier_rank", "relevancy", "survey", "actual",
    "prior", "revision", "release_freq", "ingested_at",
]


def _make_db(tmp_path: Path, rows: list[dict]) -> Path:
    db = tmp_path / "bql_test.db"
    con = sqlite3.connect(db)
    con.execute(f"CREATE TABLE bql_events ({', '.join(f'{c} TEXT' for c in _COLS)})")
    for r in rows:
        cols = ", ".join(r.keys())
        ph = ", ".join("?" for _ in r)
        con.execute(f"INSERT INTO bql_events ({cols}) VALUES ({ph})", list(r.values()))
    con.commit()
    con.close()
    return db


def _row(**kw) -> dict:
    base = {c: "" for c in _COLS}
    base.update(kw)
    return base


def test_country_remap():
    assert _map_country_code("GB") == "UK"
    assert _map_country_code("EZ") == "EU"
    assert _map_country_code("us") == "US"
    assert _map_country_code(None) == "XX"


def test_relevance_mapping():
    assert _relevance("Very High", "tier1", "1") == 100.0
    assert _relevance("Medium", "tier2", "2") == 60.0
    assert _relevance("United States", "tier2", "2") == 60.0  # name → tier fallback
    assert _relevance("Japan", "policy", None) == 100.0
    assert _relevance("", "", None) is None


def test_parse_datetime_utc():
    dt = _parse_datetime("2026-06-02", "09:30")
    assert dt == datetime(2026, 6, 2, 9, 30, tzinfo=timezone.utc)
    assert _parse_datetime("2026-06-02", "") is None
    assert _parse_datetime("", "09:30") is None


def test_read_basic_mapping(tmp_path):
    db = _make_db(tmp_path, [
        _row(date="2026-06-02", time="09:30", country_code="GB", name="CPI Core YoY",
             display_name="Core CPI YoY", category="macro",
             category_label="Macro economic data", tier="tier1", tier_rank="1",
             relevancy="Very High", survey="2.3", actual="2.4", prior="2.2",
             revision="", release_freq="M", ingested_at="2026-06-02T10:00:00"),
    ])
    events = read_bql_events(db)
    assert len(events) == 1
    e = events[0]
    assert e.country_code == "UK"
    assert e.event_name == "CPI Core YoY"
    assert e.event_datetime == datetime(2026, 6, 2, 9, 30, tzinfo=timezone.utc)
    assert e.category == "Macro economic data"
    assert (e.survey, e.actual, e.prior_value) == ("2.3", "2.4", "2.2")
    assert e.revised is None
    assert e.relevance == 100.0
    assert e.frequency == "M"


def test_dedup_keeps_freshest_snapshot(tmp_path):
    # Same event, three daily snapshots: empty actual, then two revisions.
    db = _make_db(tmp_path, [
        _row(date="2025-12-09", time="23:00", country_code="US", name="JOLTS Job Openings",
             tier="tier1", tier_rank="1", relevancy="High", survey="7197.5",
             actual="", ingested_at="2025-12-08T10:00:00"),
        _row(date="2025-12-09", time="23:00", country_code="US", name="JOLTS Job Openings",
             tier="tier1", tier_rank="1", relevancy="High", survey="7197.5",
             actual="7658.0", ingested_at="2025-12-09T10:00:00"),
        _row(date="2025-12-09", time="23:00", country_code="US", name="JOLTS Job Openings",
             tier="tier1", tier_rank="1", relevancy="High", survey="7197.5",
             actual="7670.0", ingested_at="2025-12-10T10:00:00"),
    ])
    events = read_bql_events(db)
    assert len(events) == 1
    assert events[0].actual == "7670.0"  # latest revision wins


def test_revision_truncated_to_20(tmp_path):
    db = _make_db(tmp_path, [
        _row(date="2026-06-02", time="08:30", country_code="JP", name="GDP",
             tier="tier1", tier_rank="1", relevancy="High",
             revision="-2.54788418708240541", ingested_at="2026-06-02T09:00:00"),
    ])
    e = read_bql_events(db)[0]
    assert len(e.revised) <= 20


def test_default_window():
    d1, d2 = default_window(today=date(2026, 6, 24))
    assert d1 == date(2026, 6, 17)   # T-7
    assert d2 == date(2026, 7, 15)   # T+21


def test_window_filters_by_event_date_keeping_all_snapshots(tmp_path):
    db = _make_db(tmp_path, [
        # in-window event, two snapshots — both must survive the filter so the
        # freshest-snapshot dedup still works
        _row(date="2026-06-20", time="09:00", country_code="US", name="In Window",
             tier="tier2", tier_rank="2", relevancy="High", actual="1.0",
             ingested_at="2026-06-20T10:00:00"),
        _row(date="2026-06-20", time="09:00", country_code="US", name="In Window",
             tier="tier2", tier_rank="2", relevancy="High", actual="1.2",
             ingested_at="2026-06-21T10:00:00"),
        # out-of-window event
        _row(date="2026-01-05", time="09:00", country_code="US", name="Too Old",
             tier="tier2", tier_rank="2", relevancy="High", actual="9.0",
             ingested_at="2026-01-05T10:00:00"),
    ])
    events = read_bql_events(db, d1=date(2026, 6, 17), d2=date(2026, 7, 15))
    assert len(events) == 1
    assert events[0].event_name == "In Window"
    assert events[0].actual == "1.2"  # freshest snapshot within the window


def test_rows_without_date_or_name_dropped(tmp_path):
    db = _make_db(tmp_path, [
        _row(date="", time="09:30", country_code="US", name="No Date"),
        _row(date="2026-06-02", time="09:30", country_code="US", name=""),
    ])
    assert read_bql_events(db) == []


# --- upsert (forward-event guard), with a fake session -----------------------

class _FakeResult:
    def __init__(self, row=None):
        self._row = row

    def first(self):
        return self._row


class _FakeSession:
    """Minimal stand-in: resolves vendor/country lookups, records MERGE params."""

    def __init__(self):
        self.merged: list[dict] = []
        self.committed = False

    def execute(self, stmt, params=None):
        sql = str(stmt)
        if "dim_vendor" in sql:
            return _FakeResult((4,))
        if "dim_country" in sql:
            return _FakeResult()  # .all() path handled below
        # MERGE
        self.merged.append(params)
        return _FakeResult(("INSERT", None, params.get("actual")))

    def commit(self):
        self.committed = True

    def all(self):  # not used
        return []


def _country_lookup(monkeypatch):
    monkeypatch.setattr(
        "imdr.market_calendar.bql_econdata.build_country_lookup",
        lambda session: {"US": 47, "UK": 46, "EU": 17},
    )


def test_forward_event_guard_nulls_future_actual(monkeypatch):
    _country_lookup(monkeypatch)
    sess = _FakeSession()
    now = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)
    events = [
        BqlEvent(  # future event with a stray actual → must be NULLed
            event_date=datetime(2026, 6, 20).date(),
            event_datetime=datetime(2026, 6, 20, 9, 0, tzinfo=timezone.utc),
            country_code="US", event_name="Future CPI", category="macro",
            survey="2.0", actual="9.9", prior_value="1.9", revised="*",
            relevance=100.0, frequency="M",
        ),
        BqlEvent(  # past event keeps its actual
            event_date=datetime(2026, 6, 5).date(),
            event_datetime=datetime(2026, 6, 5, 9, 0, tzinfo=timezone.utc),
            country_code="US", event_name="Past CPI", category="macro",
            survey="2.0", actual="2.1", prior_value="1.9", revised="*",
            relevance=100.0, frequency="M",
        ),
    ]
    res = upsert_events(sess, events, now_utc=now)
    assert isinstance(res, UpsertResult)
    assert sess.committed is True
    future = next(p for p in sess.merged if p["event_name"] == "Future CPI")
    past = next(p for p in sess.merged if p["event_name"] == "Past CPI")
    assert future["actual"] is None and future["revised"] is None
    assert past["actual"] == "2.1" and past["revised"] == "*"


def test_unknown_country_skipped(monkeypatch):
    _country_lookup(monkeypatch)
    sess = _FakeSession()
    events = [BqlEvent(
        event_date=datetime(2026, 6, 5).date(), event_datetime=None,
        country_code="ZZ", event_name="Mystery", category=None, survey=None,
        actual=None, prior_value=None, revised=None, relevance=None, frequency=None,
    )]
    res = upsert_events(sess, events, now_utc=datetime(2026, 6, 10, tzinfo=timezone.utc))
    assert res.skipped_unknown_country == 1
    assert sess.merged == []
