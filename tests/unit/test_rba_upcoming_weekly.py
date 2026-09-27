"""Unit tests for the RBA weekly upcoming-events view (pure logic, no DB)."""

from __future__ import annotations

from datetime import UTC, date, datetime

from scripts.calendar.rba_upcoming_weekly import classify_event, collapse


def _dt(y, m, d, h, mi):
    return datetime(y, m, d, h, mi, tzinfo=UTC)


def test_classify_rate_decision_synonyms():
    assert classify_event("RBA Cash Rate Target")[0] == "Rate Decision"
    assert classify_event("rba interest rate decision")[0] == "Rate Decision"


def test_classify_minutes_and_others():
    assert classify_event("RBA Minutes of Aug. Policy Meeting")[0] == "Minutes"
    assert classify_event("rba meeting minutes")[0] == "Minutes"
    assert classify_event("rba chart pack")[0] == "Chart Pack"
    assert classify_event("RBA-Statement on Monetary Policy")[0] == "Statement on Monetary Policy"
    assert classify_event("rba payments system board meeting")[0] == "Payments System Board Meeting"


def test_classify_core_cpi_keeps_measure_and_freq():
    assert classify_event("rba trimmed mean cpi yoy") == ("Core CPI", "Trimmed mean CPI YoY")
    assert classify_event("rba weighted median cpi mom") == ("Core CPI", "Weighted median CPI MoM")


def test_classify_speech_extracts_speaker():
    assert classify_event("rba kent speech") == ("Speech", "Kent")
    assert classify_event("rba's kent-fireside chat") == ("Speech", "Kent")
    assert classify_event("rba's bullock-testimony") == ("Speech", "Bullock")


def test_classify_non_rba_returns_none():
    assert classify_event("US CPI") is None
    assert classify_event("Fed FOMC decision") is None


def test_collapse_merges_cross_vendor_rate_decision():
    rows = [
        (date(2026, 8, 11), _dt(2026, 8, 11, 4, 30), "RBA Cash Rate Target", False),
        (date(2026, 8, 11), _dt(2026, 8, 11, 4, 30), "rba interest rate decision", False),
    ]
    items = collapse(rows)
    assert len(items) == 1
    assert items[0].kind == "Rate Decision"
    assert items[0].is_soft is False


def test_collapse_merges_two_speech_spellings_same_speaker_day():
    rows = [
        (date(2026, 8, 13), _dt(2026, 8, 13, 0, 15), "rba kent speech", False),
        (date(2026, 8, 13), _dt(2026, 8, 13, 0, 15), "rba's kent-fireside chat", False),
    ]
    items = collapse(rows)
    assert len(items) == 1
    assert items[0].label == "RBA speech — Kent"


def test_collapse_prefers_hard_timebearing_row():
    rows = [
        (date(2028, 2, 9), None, "RBA Cash Rate Target", True),                 # projected/soft
        (date(2028, 2, 9), _dt(2028, 2, 9, 3, 30), "RBA Cash Rate Target", False),  # hard
    ]
    items = collapse(rows)
    assert len(items) == 1
    assert items[0].is_soft is False
    assert items[0].event_datetime is not None


def test_collapse_soft_when_only_projected():
    rows = [(date(2028, 5, 6), None, "RBA Cash Rate Target", True)]
    items = collapse(rows)
    assert len(items) == 1 and items[0].is_soft is True


def test_collapse_sorted_by_date_then_time():
    rows = [
        (date(2026, 8, 12), _dt(2026, 8, 12, 1, 30), "rba chart pack", False),
        (date(2026, 8, 11), _dt(2026, 8, 11, 4, 30), "RBA Cash Rate Target", False),
        (date(2026, 8, 11), _dt(2026, 8, 11, 5, 30), "rba press conference", False),
    ]
    items = collapse(rows)
    assert [i.event_date for i in items] == [date(2026, 8, 11), date(2026, 8, 11), date(2026, 8, 12)]
    assert items[0].kind == "Rate Decision"  # 04:30 before 05:30
