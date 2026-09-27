"""Unit tests for the DBIE aggregate-SCB parser (reportIds 1130 + 9).

No network, no DB, no headed Chrome. Fixtures mirror the live SAP-BO
tables scraped on 2026-09-15.

Covers the things that would corrupt the series if they broke:
- the SAP-BO DOM fuses wrapped header words (`AggregateDeposits`), so the
  header normaliser must split the lower->upper boundary or every
  multi-word column misses its map
- report 1130 publishes rows where Bank Credit is blank and Non-Food
  Credit is reported as MINUS Food Credit; those rows are dropped whole
  rather than written as a negative credit stock
- only mapped columns are emitted, so a SAP-BO pagination change cannot
  quietly change the series set
- fortnightly prints collapse to the LAST reporting date of each month
"""
from __future__ import annotations

import datetime
import importlib

import pytest

_mod = importlib.import_module("scripts.econ.in.rbi.rbi_dbie_scb_business")

parse_report = _mod.parse_report
_norm_header = _mod._norm_header
_last_fortnight_per_month = _mod._last_fortnight_per_month
REPORTS = {r["report_id"]: r for r in _mod.REPORTS}
# reportId 9 is probed and mapped but NOT scraped -- its SAP-BO grid is
# horizontally panelled and the deposits columns are absent from the panel
# the DOM scrape returns. The map is still exercised here so the knowledge
# stays tested rather than rotting in a comment.
BLOCKED = {r["report_id"]: r for r in _mod.BLOCKED_REPORTS}


def test_report_9_is_not_shipped():
    """Pins the decision: no deposits series until the panel race is solved."""
    assert "9" not in REPORTS
    assert "9" in BLOCKED
    assert "deposits" in BLOCKED["9"]["blocked"].lower()


@pytest.mark.parametrize("raw,expected", [
    # the DOM drops the line break inside a wrapped header without a space
    ("2.1 AggregateDeposits", "AGGREGATE_DEPOSITS"),
    ("Number of ReportingBanks", "NUMBER_OF_REPORTING_BANKS"),
    ("1 Liabilities to theBanking System", "LIABILITIES_TO_THE_BANKING_SYSTEM"),
    ("3 Borrowings fromReserve Bank", "BORROWINGS_FROM_RESERVE_BANK"),
    ("2.1.1 Demand", "DEMAND"),
    ("2.1.2 Time", "TIME"),
    ("Bank Credit", "BANK_CREDIT"),
    ("Non Food Credit", "NON_FOOD_CREDIT"),
    ("Fortnight Date Final", "FORTNIGHT_DATE_FINAL"),
])
def test_norm_header(raw, expected):
    assert _norm_header(raw) == expected


def test_report_1130_maps_its_three_columns():
    rows = [["Fortnight Date Final", "Bank Credit", "Food Credit", "Non Food Credit"],
            ["Aug 31, 2026", "2,23,87,567", "1,12,042", "2,22,75,525"],
            ["Aug 15, 2026", "2,20,07,764", "1,14,136", "2,18,93,628"]]
    labels, obs = parse_report(rows, REPORTS["1130"])
    assert set(labels) == {"BANK_CREDIT", "FOOD_CREDIT", "NON_FOOD_CREDIT"}
    assert ("BANK_CREDIT", datetime.date(2026, 8, 31), 22387567.0) in obs
    assert ("NON_FOOD_CREDIT", datetime.date(2026, 8, 15), 21893628.0) in obs


def test_rows_missing_bank_credit_are_dropped_whole():
    """Upstream reports Non-Food as `0 - Food` when credit has not landed.

    Observed live on 2026-06-30 and 2026-04-30. Taking the non-food
    figure at face value writes a NEGATIVE credit stock.
    """
    rows = [["Fortnight Date Final", "Bank Credit", "Food Credit", "Non Food Credit"],
            ["Jul 31, 2026", "2,20,78,403", "1,17,830", "2,19,60,573"],
            ["Jun 30, 2026", "", "1,32,049", "-1,32,049"]]
    _, obs = parse_report(rows, REPORTS["1130"])
    assert {d for _s, d, _v in obs} == {datetime.date(2026, 7, 31)}
    assert all(v > 0 for _s, _d, v in obs)


def test_only_mapped_columns_are_emitted():
    """Report 9 scrapes 15 of its 31 columns, and which 15 can change."""
    rows = [["As on Date Final", "Number of ReportingBanks",
             "1 Liabilities to theBanking System",
             "1.1 Demand andTime Deposits fromBanks",
             "2 Liabilities to Others", "2.1 AggregateDeposits",
             "2.1.1 Demand", "2.1.2 Time", "2.2 Borrowings"],
            ["Jun 30,2026", "201", "5,60,672", "4,50,247",
             "2,91,33,764", "2,70,90,661", "35,99,794", "2,34,90,866",
             "8,44,990"]]
    labels, obs = parse_report(rows, BLOCKED["9"])
    assert set(labels) == {
        "REPORTING_BANKS", "LIABILITIES_TO_BANKING_SYSTEM",
        "LIABILITIES_TO_OTHERS", "AGGREGATE_DEPOSITS",
        "DEMAND_DEPOSITS", "TIME_DEPOSITS",
    }
    # `1.1 Demand and Time Deposits from Banks` and `2.2 Borrowings` are
    # unmapped and must not leak in under a near-miss name.
    assert ("AGGREGATE_DEPOSITS", datetime.date(2026, 6, 30), 27090661.0) in obs
    assert all(s in labels for s, _d, _v in obs)


def test_unmapped_layout_emits_nothing_rather_than_guessing():
    rows = [["Some Other Date", "Mystery Column"], ["Jun 30,2026", "1"]]
    labels, obs = parse_report(rows, BLOCKED["9"])
    assert labels == {}
    assert obs == []


def test_last_reporting_fortnight_of_the_month_wins():
    obs = [
        ("BANK_CREDIT", datetime.date(2026, 8, 15), 22007764.0),
        ("BANK_CREDIT", datetime.date(2026, 8, 31), 22387567.0),
        ("BANK_CREDIT", datetime.date(2026, 7, 15), 21734674.0),
    ]
    monthly = _last_fortnight_per_month(obs)
    assert monthly[("BANK_CREDIT", datetime.date(2026, 8, 1))] == (
        datetime.date(2026, 8, 31), 22387567.0)
    assert monthly[("BANK_CREDIT", datetime.date(2026, 7, 1))] == (
        datetime.date(2026, 7, 15), 21734674.0)


def test_non_date_rows_are_ignored():
    rows = [["Fortnight Date Final", "Bank Credit", "Food Credit", "Non Food Credit"],
            ["Total", "1", "2", "3"],
            ["Aug 31, 2026", "2,23,87,567", "1,12,042", "2,22,75,525"]]
    _, obs = parse_report(rows, REPORTS["1130"])
    assert {d for _s, d, _v in obs} == {datetime.date(2026, 8, 31)}


def test_empty_table_is_not_an_error():
    assert parse_report([], REPORTS["1130"]) == ({}, [])
