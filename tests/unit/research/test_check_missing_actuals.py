"""Tests for scripts/research/check_missing_actuals.py.

Pins the distinction the check exists to draw, using the two real 08 Sep 2026
releases that motivated it:

  * Taiwan August CPI -- a forecast on BOTH lanes, an actual on neither, and no
    third source in IMDR. UNCOVERED, and must fail the check.
  * Philippine unemployment -- 6.0% against a 5.0% TE forecast. Blank on the TE
    row, present on the BQL row. ONE-LANE, and must NOT fail the check.

Both look like "actual IS NULL" in a naive query; only one is a data gap.
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import sys
from pathlib import Path

import pytest

_MOD_PATH = (
    Path(__file__).resolve().parents[3]
    / "scripts" / "research" / "check_missing_actuals.py"
)
_spec = importlib.util.spec_from_file_location("check_missing_actuals", _MOD_PATH)
cma = importlib.util.module_from_spec(_spec)
sys.modules["check_missing_actuals"] = cma
_spec.loader.exec_module(cma)

UTC = dt.timezone.utc
_AS_OF = dt.datetime(2026, 9, 9, 23, 59, tzinfo=UTC)

# The two real release instants.
_TW_CPI = dt.datetime(2026, 9, 8, 8, 0, tzinfo=UTC)
_PH_UNEMP = dt.datetime(2026, 9, 8, 1, 0, tzinfo=UTC)


def _row(cc, name, source, instant, survey=None, forecast=None,
         actual=None, revised=None, prior="1.0"):
    return {
        "event_date": instant.date(),
        "event_datetime": instant,
        "event_name": name,
        "source": source,
        "lane": cma.lane_of(source),
        "survey": survey,
        "forecast": forecast,
        "actual": actual,
        "revised": revised,
        "prior_value": prior,
        "country_code": cc,
    }


# ---------------------------------------------------------------------------
# lane_of
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("source, lane", [
    ("tradingeconomics:414232", "TE"),
    ("tradingeconomics", "TE"),
    ("bloomberg_bql", "BQL"),
    ("bsp.gov.ph", "bsp.gov.ph"),
    (None, "(none)"),
    ("", "(none)"),
])
def test_lane_of(source, lane):
    assert cma.lane_of(source) == lane


# ---------------------------------------------------------------------------
# _as_datetime — the pinned ODBC driver's actual shapes
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw", [
    "2026-09-08 08:00:00.0000000 +00:00",   # what the driver really returns
    "2026-09-08 08:00:00 +00:00",
    "2026-09-08T08:00:00Z",
    "2026-09-08 08:00:00",                   # naive -> treated as UTC
    dt.datetime(2026, 9, 8, 8, 0, tzinfo=UTC),
    dt.datetime(2026, 9, 8, 8, 0),           # naive datetime -> UTC
])
def test_as_datetime_shapes(raw):
    """SQL Server's 7 fractional digits break datetime.fromisoformat."""
    assert cma._as_datetime(raw) == _TW_CPI


def test_as_datetime_honours_a_real_offset():
    got = cma._as_datetime("2026-09-08 16:00:00.0000000 +08:00")
    assert got == _TW_CPI


def test_as_datetime_rejects_garbage():
    with pytest.raises(ValueError, match="unparseable"):
        cma._as_datetime("not a timestamp")


# ---------------------------------------------------------------------------
# expected_an_actual
# ---------------------------------------------------------------------------

def test_forecast_row_with_no_actual_is_expected():
    r = _row("TW", "inflation rate yoy", "tradingeconomics:1", _TW_CPI,
             forecast="2.6%")
    assert cma.expected_an_actual(r)


def test_survey_row_with_no_actual_is_expected():
    r = _row("TW", "CPI YoY", "bloomberg_bql", _TW_CPI, survey="2.35")
    assert cma.expected_an_actual(r)


def test_row_with_an_actual_is_not_expected():
    r = _row("PH", "unemployment rate", "bloomberg_bql", _PH_UNEMP,
             survey="5.0", actual="6.0")
    assert not cma.expected_an_actual(r)


def test_revised_counts_as_a_print():
    """A revised-only row has a number; it is not a missing actual."""
    r = _row("PH", "unemployment rate", "bloomberg_bql", _PH_UNEMP,
             forecast="5.0%", revised="6.1")
    assert not cma.expected_an_actual(r)


@pytest.mark.parametrize("name", [
    "philippines to sell 91-day bills on sep. 07",
    "bsp governor speech",
])
def test_rows_that_never_get_an_actual_are_ignored(name):
    """No survey and no forecast -> not a forecastable data release.

    Auction announcements and speeches would otherwise flood the output.
    """
    r = _row("PH", name, "bloomberg_bql", _PH_UNEMP, prior=None)
    assert not cma.expected_an_actual(r)


@pytest.mark.parametrize("blank", [None, "", "  ", "-", "—"])
def test_blank_actual_placeholders(blank):
    r = _row("TW", "CPI YoY", "bloomberg_bql", _TW_CPI,
             survey="2.35", actual=blank)
    assert cma.expected_an_actual(r)


# ---------------------------------------------------------------------------
# classify — UNCOVERED vs ONE-LANE
# ---------------------------------------------------------------------------

def test_taiwan_cpi_is_uncovered():
    """THE gap: a forecast on both lanes, an actual on neither."""
    rows = [
        _row("TW", "CPI YoY", "bloomberg_bql", _TW_CPI, survey="2.35",
             prior="2.54"),
        _row("TW", "cpi core yoy", "bloomberg_bql", _TW_CPI, survey="2.45",
             prior="2.38"),
        _row("TW", "inflation rate yoy", "tradingeconomics:414232", _TW_CPI,
             forecast="2.6%", prior="2.54%"),
        _row("TW", "inflation rate mom", "tradingeconomics:410680", _TW_CPI,
             forecast="0.2%", prior="0.18%"),
    ]
    findings = cma.classify(rows, _AS_OF, grace_hours=24)
    assert len(findings) == 4
    assert {f["status"] for f in findings} == {"UNCOVERED"}
    assert all(f["covered_by"] == [] for f in findings)


def test_philippine_unemployment_is_one_lane_not_uncovered():
    """The BQL row carries 6.0, so the blank TE row is NOT a data gap.

    Pairing is by (country, instant) -- the lanes name this release the same
    here, but Taiwan's they do not, which is why name is never the join key.
    """
    rows = [
        _row("PH", "unemployment rate", "bloomberg_bql", _PH_UNEMP,
             actual="6.0", prior="4.9"),
        _row("PH", "unemployment rate", "tradingeconomics:406796", _PH_UNEMP,
             forecast="5.0%", prior="4.9%"),
    ]
    findings = cma.classify(rows, _AS_OF, grace_hours=24)
    assert len(findings) == 1
    assert findings[0]["status"] == "ONE-LANE"
    assert findings[0]["covered_by"] == ["BQL"]


def test_cross_lane_pairing_ignores_event_name():
    """Taiwan's lanes disagree on the name; a name join would misreport.

    If the actual lands on BQL as "CPI YoY" while TE still shows "inflation
    rate yoy" blank, that is covered -- not a gap.
    """
    rows = [
        _row("TW", "CPI YoY", "bloomberg_bql", _TW_CPI, survey="2.35",
             actual="2.5"),
        _row("TW", "inflation rate yoy", "tradingeconomics:414232", _TW_CPI,
             forecast="2.6%"),
    ]
    findings = cma.classify(rows, _AS_OF, grace_hours=24)
    assert [f["status"] for f in findings] == ["ONE-LANE"]
    assert findings[0]["covered_by"] == ["BQL"]


def test_a_release_inside_the_grace_window_is_not_flagged():
    """A print that simply has not arrived yet is never a finding."""
    recent = _AS_OF - dt.timedelta(hours=3)
    rows = [_row("TW", "CPI YoY", "bloomberg_bql", recent, survey="2.35")]
    assert cma.classify(rows, _AS_OF, grace_hours=24) == []
    late = cma.classify(rows, _AS_OF, grace_hours=2)
    assert [f["status"] for f in late] == ["UNCOVERED"]


def test_age_hours_is_measured_from_the_instant():
    rows = [_row("TW", "CPI YoY", "bloomberg_bql", _TW_CPI, survey="2.35")]
    f = cma.classify(rows, _AS_OF, grace_hours=24)[0]
    assert 39 <= f["age_hours"] <= 41   # 08 Sep 08:00 -> 09 Sep 23:59


def test_same_instant_different_country_does_not_cover():
    """Coverage is per country; a foreign print must not mask a local gap."""
    rows = [
        _row("TW", "CPI YoY", "bloomberg_bql", _TW_CPI, survey="2.35"),
        _row("PH", "cpi yoy", "bloomberg_bql", _TW_CPI, actual="6.1"),
    ]
    findings = cma.classify(rows, _AS_OF, grace_hours=24)
    assert [f["status"] for f in findings] == ["UNCOVERED"]


def test_findings_are_sorted_by_instant():
    rows = [
        _row("TW", "CPI YoY", "bloomberg_bql", _TW_CPI, survey="1"),
        _row("PH", "unemployment rate", "tradingeconomics:1", _PH_UNEMP,
             forecast="5.0%"),
    ]
    findings = cma.classify(rows, _AS_OF, grace_hours=24)
    assert [f["event_datetime"] for f in findings] == [_PH_UNEMP, _TW_CPI]


# ---------------------------------------------------------------------------
# Roster
# ---------------------------------------------------------------------------

def test_spider_roster_covers_both_incident_countries():
    assert "TW" in cma.SPIDER_UNIVERSE
    assert "PH" in cma.SPIDER_UNIVERSE


def test_spider_roster_is_distinct_and_the_documented_size():
    assert len(cma.SPIDER_UNIVERSE) == len(set(cma.SPIDER_UNIVERSE))
    assert len(cma.SPIDER_UNIVERSE) == 17


def test_bad_as_of_returns_nonzero():
    assert cma.main(["--as-of", "09-09-2026"]) == 1


def test_bad_lookback_returns_nonzero():
    assert cma.main(["--lookback-days", "0"]) == 1
