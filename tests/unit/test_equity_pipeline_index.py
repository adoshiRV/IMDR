"""Tests for EquityIndexPipeline's fetch window.

Pins the two halves of the FTSE repair, which are easy to break silently:

  * extraction must use the WIDENED window (``_fetch_start``), or Citi is never
    asked for the late-publishing tag and the day is lost for good — FTSE is
    served 12-20h after the LSE close and was absent on 13 UK business days
    between June and September 2026 for exactly this reason;

  * everything that MEASURES the run — the health checks and
    ``get_run_context()`` — must stay keyed on the ANCHOR (``_start``). If one
    of them ever follows ``_fetch_start``, a 5-day window would satisfy a
    row-count or freshness check that a same-day miss should have failed, and
    the widening would have converted a loud failure into a silent one.
"""
from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

from imdr.domains.equity.pipeline_index import EquityIndexPipeline

UTC = dt.timezone.utc

ANCHOR = dt.datetime(2026, 9, 14, tzinfo=UTC)
END = ANCHOR.replace(hour=23, minute=59)
WIDE = dt.datetime(2026, 9, 9, tzinfo=UTC)


class _StubConnector:
    """BasePipeline only stores the connector; nothing here opens a session."""


class _StubUniverse:
    def api_symbols(self):
        return []

    def tag_to_ticker(self):
        return {}

    def index_create_entries(self):
        return []

    def market_calendars(self):
        return [("UK", "LN")]


def _pipeline(fetch_start):
    return EquityIndexPipeline(
        connector=_StubConnector(),
        settings=object(),
        universe=_StubUniverse(),
        start=ANCHOR,
        end=END,
        fetch_start=fetch_start,
    )


def test_fetch_start_defaults_to_the_anchor():
    """Omitting it must not silently widen anything."""
    assert _pipeline(None)._fetch_start == ANCHOR


def test_extract_asks_the_vendor_for_the_WIDENED_window(monkeypatch):
    """The whole point of the widening: Citi must be asked from _fetch_start.

    A single-day fetch is what lost FTSE — the anchor advances as soon as the
    first exchange closes, so the day FTSE eventually publishes is no longer
    the day being requested.
    """
    seen = {}

    class _Extractor:
        _errors: list = []

        def __init__(self, **kw):
            pass

        def extract_index(self, start, end, *a, **kw):
            seen["start"], seen["end"] = start, end
            return pd.DataFrame(columns=["ticker", "ts", "value"])

    class _Client:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class _Tracker:
        def __init__(self, **kw):
            pass

        def current_usage(self):
            return 0

    import imdr.domains.equity.pipeline_index as mod

    monkeypatch.setattr(mod, "CitiVelocityEquityExtractor", _Extractor)
    monkeypatch.setattr(mod, "CitiVelocityClient", lambda s: _Client())
    monkeypatch.setattr(mod, "TagQuotaTracker", _Tracker)

    p = _pipeline(WIDE)
    p._settings = type("S", (), {"citi_tag_quota_limit": 1, "citi_tag_quota_file": None})()
    p.extract()

    assert seen["start"] == WIDE, "extraction must use the widened window"
    assert seen["end"] == END


@pytest.mark.parametrize("fetch_start", [None, WIDE])
def test_run_context_stays_on_the_anchor(fetch_start):
    """What the run REPORTS is the anchor day, whatever was fetched."""
    assert _pipeline(fetch_start).get_run_context() == {"run_date": ANCHOR.date()}


def test_health_checks_are_keyed_on_the_anchor_not_the_fetch_window():
    """A health check reading _fetch_start would pass a 5-day window where a
    same-day miss should fail it — turning the widening into a silent hole."""
    checks = _pipeline(WIDE).get_health_checks()
    assert checks, "expected health checks to be configured"
    dates = {getattr(c, "_date_column", None) for c in checks}
    assert dates <= {"obs_date", None}
    # None of them may have captured the widened start.
    for c in checks:
        for attr in vars(c).values():
            assert attr != WIDE, (
                f"{type(c).__name__} captured the widened fetch window; "
                "health checks must measure the anchor day only"
            )


# ---------------------------------------------------------------------------
# anchor_row_count — the widened window must not hide an anchor-day outage
# ---------------------------------------------------------------------------

def _with_raw(rows):
    p = _pipeline(WIDE)
    p._raw_df = pd.DataFrame(rows, columns=["ticker", "ts", "value"]) if rows else pd.DataFrame()
    return p


def test_anchor_row_count_ignores_the_backfilled_days():
    """5 settled days re-upserting must not read as a successful anchor run."""
    p = _with_raw([
        ("FTSE", pd.Timestamp("2026-09-09"), 1.0),
        ("SPX", pd.Timestamp("2026-09-10"), 2.0),
        ("SPX", pd.Timestamp("2026-09-11"), 3.0),
    ])
    assert p.anchor_row_count == 0, "nothing landed for the 14 Sep anchor"


def test_anchor_row_count_counts_only_the_anchor_day():
    p = _with_raw([
        ("FTSE", pd.Timestamp("2026-09-09"), 1.0),
        ("SPX", pd.Timestamp("2026-09-14"), 2.0),
        ("N225", pd.Timestamp("2026-09-14"), 3.0),
    ])
    assert p.anchor_row_count == 2


def test_anchor_row_count_handles_no_extract():
    assert _with_raw([]).anchor_row_count == 0
    assert _pipeline(WIDE).anchor_row_count == 0
