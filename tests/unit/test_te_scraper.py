"""Regression tests for the TradingEconomics /calendar parser.

Pins the column-index mapping after the 2026-06-12 incident where
parse_calendar_html() treated td[3] as a separate "reference" column
and shifted Actual/Previous/Consensus/Forecast one cell right — so
every cb_events.actual ended up holding TE's *Previous* value (e.g.
the India May CPI YoY release was alerted as 3.48% instead of 3.93%).
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime, timezone

from sqlalchemy.exc import SQLAlchemyError

from imdr.market_calendar.te_scraper import (
    TECalendarEvent,
    UpsertResult,
    _build_collision_set,
    _is_placeholder_symbol,
    parse_calendar_html,
    upsert_events,
)


def _ev(*, country_iso_te: str, symbol: str | None, event_slug: str,
        event_date: date = date(2026, 6, 18)) -> TECalendarEvent:
    """Minimal TECalendarEvent for upsert-side helper tests."""
    return TECalendarEvent(
        event_date=event_date,
        event_datetime=datetime(2026, 6, 18, 8, 40, tzinfo=timezone.utc),
        country_iso_te=country_iso_te,
        country_name=country_iso_te,
        event_slug=event_slug,
        event_text=event_slug,
        category="calendar",
        symbol=symbol,
        te_id="419028",
        te_url=None,
        importance=1,
        time_text="08:40 AM",
        actual=None,
        previous=None,
        consensus=None,
        forecast=None,
    )


# Minimal markup mirroring TE's live /calendar row structure. Two rows:
# one with all four numeric cells populated, one with missing consensus/
# forecast (e.g. the India MoM row from the same release).
_FIXTURE_HTML = """
<html><body>
<table id="calendar">
  <tr data-id="400945"
      data-country="India"
      data-event="inflation rate yoy"
      data-category="Inflation Rate"
      data-symbol="INDIANINFLATION"
      data-url="/india/inflation-cpi"
      data-importance="2">
    <td class="2026-06-12">
      <span class="calendar-date-2"></span>06:30 PM
    </td>
    <td>
      <table><tr><td class="calendar-iso">IN</td></tr></table>
    </td>
    <td>Inflation Rate YoY <span class="calendar-period">MAY</span></td>
    <td>3.93%</td>
    <td>3.48%</td>
    <td>4%</td>
    <td>3.9%</td>
    <td><span class="bars"></span><span class="bell"></span></td>
  </tr>
  <tr data-id="400946"
      data-country="India"
      data-event="inflation rate mom"
      data-category="Inflation Rate"
      data-symbol="INDIANINFLATIONMOM"
      data-url="/india/inflation-mom"
      data-importance="1">
    <td class="2026-06-12">
      <span class="calendar-date-1"></span>06:30 PM
    </td>
    <td>
      <table><tr><td class="calendar-iso">IN</td></tr></table>
    </td>
    <td>Inflation Rate MoM <span class="calendar-period">MAY</span></td>
    <td>0.75%</td>
    <td>0.27%</td>
    <td></td>
    <td>0.7%</td>
    <td><span class="bars"></span><span class="bell"></span></td>
  </tr>
</table>
</body></html>
"""


class TestParseCalendarHtmlColumnOrder:
    """The 2026-06-12 bug: Actual/Previous/Consensus/Forecast off by one."""

    def test_india_cpi_yoy_columns_map_correctly(self):
        events = parse_calendar_html(_FIXTURE_HTML)
        assert len(events) == 2
        yoy = events[0]
        assert yoy.event_slug == "inflation rate yoy"
        assert yoy.event_date == date(2026, 6, 12)
        assert yoy.country_iso_te == "IN"
        # The cells that matter — these were all shifted by one column
        # before the fix. Pin them here.
        assert yoy.actual == "3.93%"
        assert yoy.previous == "3.48%"
        assert yoy.consensus == "4%"
        assert yoy.forecast == "3.9%"

    def test_missing_consensus_does_not_shift_forecast(self):
        events = parse_calendar_html(_FIXTURE_HTML)
        mom = events[1]
        assert mom.event_slug == "inflation rate mom"
        assert mom.actual == "0.75%"
        assert mom.previous == "0.27%"
        # Empty consensus stays empty — must NOT pull the Forecast value
        # forward (that was the exact failure mode of the old parser).
        assert mom.consensus is None
        assert mom.forecast == "0.7%"


class TestPlaceholderSymbol:
    """The 2026-06-15 bug: 'ESP CALENDAR' hit the ticker unique index.

    Generic 'CALENDAR' placeholders are shared across many distinct
    same-country events, so they must always be NULLed and routed through
    the event_name uniqueness index.
    """

    def test_calendar_family_is_placeholder(self):
        for sym in ("CALENDAR", "ESP CALENDAR", "USD CALENDAR", "OPECALENDAR",
                    "esp calendar"):
            assert _is_placeholder_symbol(sym), sym

    def test_real_tickers_are_not_placeholders(self):
        for sym in ("FDTR", "EURR002W", "INDIANINFLATION", "GERMANYSERPMI"):
            assert not _is_placeholder_symbol(sym), sym

    def test_none_and_empty_are_not_placeholders(self):
        assert not _is_placeholder_symbol(None)
        assert not _is_placeholder_symbol("")


class TestCollisionSet:
    """In-batch backstop for non-placeholder symbols reused same-day."""

    def test_real_symbol_reused_same_day_collides(self):
        # Use a non-overridden ISO so the assertion doesn't depend on
        # _COUNTRY_OVERRIDES — collision detection is what's under test.
        events = [
            _ev(country_iso_te="US", symbol="FDTR", event_slug="a"),
            _ev(country_iso_te="US", symbol="FDTR", event_slug="b"),
        ]
        out = _build_collision_set(events, {"US": 1})
        assert ("2026-06-18", 1, "FDTR") in out

    def test_unique_symbol_does_not_collide(self):
        events = [
            _ev(country_iso_te="US", symbol="FDTR", event_slug="a"),
            _ev(country_iso_te="US", symbol="EURR002W", event_slug="b"),
        ]
        assert _build_collision_set(events, {"US": 1}) == set()


# ---------------------------------------------------------------------------
# upsert_events(): event_name normalization + per-row error isolation
#
# Regression for the 2026-07 TE-run-abort incident: TE event id 420801
# (2026-07-10, country_id 17) alternated between an accented rendered-text
# fallback ("ecb vujčić speech") and its plain-ASCII data-event slug
# ("ecb vujcic speech"). The MERGE's ON clause treated the two spellings as
# different rows (no MATCH -> INSERT branch), which then collided with
# calendar.cb_events' accent/case-insensitive unique index
# (pyodbc.IntegrityError 2601) and aborted the whole run.
# ---------------------------------------------------------------------------

def _te_event(event_text: str, *, event_slug: str = "", country_iso_te: str = "US",
              event_date: date = date(2026, 7, 10), symbol: str | None = None,
              te_id: str = "420801") -> TECalendarEvent:
    return TECalendarEvent(
        event_date=event_date,
        event_datetime=datetime(event_date.year, event_date.month, event_date.day, 9, 0,
                                 tzinfo=timezone.utc),
        country_iso_te=country_iso_te,
        country_name=country_iso_te,
        event_slug=event_slug,
        event_text=event_text,
        category="Central Banks",
        symbol=symbol,
        te_id=te_id,
        te_url=None,
        importance=2,
        time_text="09:00 AM",
        actual=None,
        previous=None,
        consensus=None,
        forecast=None,
    )


class _FakeResult:
    def __init__(self, rows=None, row=None):
        self._rows = rows if rows is not None else []
        self._row = row

    def all(self):
        return self._rows

    def first(self):
        return self._row


class _FakeSession:
    """Minimal stand-in for upsert_events(): resolves vendor/country lookups,
    records MERGE params, and lets a test force a specific row to fail so the
    per-row SAVEPOINT isolation can be exercised without a real DB.
    """

    def __init__(self, fail_event_names: set[str] | None = None):
        self.merged: list[dict] = []
        self.committed = False
        self._fail_event_names = fail_event_names or set()

    def execute(self, stmt, params=None):
        sql = str(stmt)
        if "dim_vendor" in sql:
            return _FakeResult(row=(73,))
        if "country_code" in sql and "dim_country" in sql:
            return _FakeResult(rows=[("US", 47), ("EU", 17)])
        if "display_name" in sql:
            return _FakeResult(rows=[(47, "United States"), (17, "Euro Area")])
        # MERGE
        if params is not None and params.get("event_name") in self._fail_event_names:
            raise SQLAlchemyError(f"simulated failure for {params['event_name']!r}")
        self.merged.append(params)
        return _FakeResult(row=("INSERT", len(self.merged), None, params.get("actual")))

    def commit(self):
        self.committed = True

    @contextmanager
    def begin_nested(self):
        yield


class TestEventNameAccentCollision:
    def test_accented_and_plain_spelling_produce_the_same_merge_key(self):
        sess = _FakeSession()
        events = [
            _te_event("ECB Vujčić Speech"),
            _te_event("ecb vujcic speech"),
        ]
        res = upsert_events(sess, events, now_utc=datetime(2026, 7, 11, tzinfo=timezone.utc))
        assert isinstance(res, UpsertResult)
        assert res.errored == 0
        assert len(sess.merged) == 2
        assert sess.merged[0]["event_name"] == "ecb vujcic speech"
        assert sess.merged[1]["event_name"] == "ecb vujcic speech"


class TestPerRowErrorIsolation:
    def test_one_failing_row_does_not_abort_the_batch(self):
        sess = _FakeSession(fail_event_names={"ecb vujcic speech"})
        events = [
            _te_event("ecb vujcic speech", event_date=date(2026, 7, 10)),
            _te_event("good event", event_date=date(2026, 7, 11)),
        ]
        res = upsert_events(sess, events, now_utc=datetime(2026, 7, 12, tzinfo=timezone.utc))
        assert res.errored == 1
        assert [p["event_name"] for p in sess.merged] == ["good event"]
        assert sess.committed is True
