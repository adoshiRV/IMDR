"""Unit tests for _parse_forward_premia in
scripts.econ.in.rbi.rbi_dbie_forward_premia.

No network calls, no DB writes, no headed Chrome.
The fixture mirrors the live SAP-BO table layout confirmed 2026-07-14:
  row[0]: header        ('Date', '1-month', '3-month', '6-month')
  row[1]: ordinal row   ('1', '2', '3', '4')
  row[2]: FY-label row  ('2026-27', '', '', '')
  row[3+]: data rows    ('30-Jun-26', '3.17', '3.04', '2.90')

Covers:
- 3 indicator codes produced (1M / 3M / 6M tenors -- no 12M column exists)
- Correct tenor slug mapping (_COL_MAP)
- Date parsing: %d-%b-%y (2-digit year)
- Header / ordinal / FY-label rows silently skipped (none parse as a date)
- Known value anchor (2026-06-30 scrape)
- Dedup: same (code, date) appears only once
- Blank / dash / NA cells produce no observation
- Empty-table input
"""
from __future__ import annotations

import datetime
import importlib

# Use importlib because the package path contains `in`, a Python keyword.
_mod = importlib.import_module("scripts.econ.in.rbi.rbi_dbie_forward_premia")

_parse_forward_premia = _mod._parse_forward_premia
_parse_date = _mod._parse_date
_COL_MAP = _mod._COL_MAP

NOW = datetime.datetime(2026, 7, 14, 12, 0, 0, tzinfo=datetime.timezone.utc)


# ---------------------------------------------------------------------------
# Fixture helper
# ---------------------------------------------------------------------------

def _make_rows(*, include_extra_days: bool = False) -> list[list[str]]:
    """Minimal fixture matching the live SAP-BO Forward Premia table layout."""
    rows = [
        ["Date", "1-month", "3-month", "6-month"],
        ["1", "2", "3", "4"],
        ["2026-27", "", "", ""],
        ["30-Jun-26", "3.17", "3.04", "2.90"],
    ]
    if include_extra_days:
        rows.append(["29-Jun-26", "3.31", "3.05", "2.90"])
        rows.append(["27-Jan-26", "2.35", "3.01", "2.70"])
    return rows


# ---------------------------------------------------------------------------
# Tests: indicator count and codes
# ---------------------------------------------------------------------------

class TestIndicatorCodes:
    def test_3_indicators_produced(self):
        inds, _ = _parse_forward_premia(_make_rows(), NOW)
        assert len(inds) == 3

    def test_all_tenor_slugs_present(self):
        inds, _ = _parse_forward_premia(_make_rows(), NOW)
        codes = {ind.imdr_code for ind in inds}
        for tenor in ("1M", "3M", "6M"):
            assert any(f".{tenor}." in c for c in codes), f"Missing tenor {tenor}"

    def test_no_12m_tenor(self):
        """Neither DBIE report (698 daily / 558 monthly-avg) carries a 12M column."""
        inds, _ = _parse_forward_premia(_make_rows(), NOW)
        codes = {ind.imdr_code for ind in inds}
        assert not any("12M" in c or "1Y" in c for c in codes)

    def test_imdr_code_format(self):
        inds, _ = _parse_forward_premia(_make_rows(), NOW)
        for ind in inds:
            assert ind.imdr_code.startswith("INDIA.DBIE.FORWARD_PREMIA.")
            assert ind.imdr_code.endswith(".IN")

    def test_unit_pct_for_all(self):
        inds, _ = _parse_forward_premia(_make_rows(), NOW)
        for ind in inds:
            assert ind.unit == "pct"

    def test_vendor_name_rbi(self):
        inds, _ = _parse_forward_premia(_make_rows(), NOW)
        for ind in inds:
            assert ind.vendor_name == "RBI"

    def test_category_fx(self):
        inds, _ = _parse_forward_premia(_make_rows(), NOW)
        for ind in inds:
            assert ind.category == "fx"

    def test_frequency_daily(self):
        inds, _ = _parse_forward_premia(_make_rows(), NOW)
        for ind in inds:
            assert ind.frequency == "DAILY"


# ---------------------------------------------------------------------------
# Tests: date parsing
# ---------------------------------------------------------------------------

class TestDateParsing:
    def test_two_digit_year_resolves_to_2026(self):
        assert _parse_date("30-Jun-26") == datetime.date(2026, 6, 30)

    def test_header_row_col0_does_not_parse(self):
        assert _parse_date("Date") is None

    def test_ordinal_row_col0_does_not_parse(self):
        assert _parse_date("1") is None

    def test_fy_label_row_col0_does_not_parse(self):
        assert _parse_date("2026-27") is None

    def test_blank_col0_does_not_parse(self):
        assert _parse_date("") is None

    def test_header_ordinal_fy_rows_produce_no_obs(self):
        _, obs = _parse_forward_premia(_make_rows(), NOW)
        dates = {o.obs_date for o in obs}
        assert datetime.date(2026, 6, 30) in dates
        assert len(obs) == 3  # only the one data row * 3 tenors


# ---------------------------------------------------------------------------
# Tests: known values (2026-06-30 scrape anchor)
# ---------------------------------------------------------------------------

class TestKnownValues:
    def test_1m_2026_06_30_317(self):
        _, obs = _parse_forward_premia(_make_rows(), NOW)
        match = [
            o for o in obs
            if ".1M." in o.imdr_code and o.obs_date == datetime.date(2026, 6, 30)
        ]
        assert len(match) == 1
        assert abs(match[0].value - 3.17) < 0.001

    def test_3m_2026_06_30_304(self):
        _, obs = _parse_forward_premia(_make_rows(), NOW)
        match = [
            o for o in obs
            if ".3M." in o.imdr_code and o.obs_date == datetime.date(2026, 6, 30)
        ]
        assert len(match) == 1
        assert abs(match[0].value - 3.04) < 0.001

    def test_6m_2026_06_30_290(self):
        _, obs = _parse_forward_premia(_make_rows(), NOW)
        match = [
            o for o in obs
            if ".6M." in o.imdr_code and o.obs_date == datetime.date(2026, 6, 30)
        ]
        assert len(match) == 1
        assert abs(match[0].value - 2.90) < 0.001

    def test_multiple_days_all_present(self):
        _, obs = _parse_forward_premia(_make_rows(include_extra_days=True), NOW)
        dates = {o.obs_date for o in obs}
        assert datetime.date(2026, 6, 30) in dates
        assert datetime.date(2026, 6, 29) in dates
        assert datetime.date(2026, 1, 27) in dates
        assert len(obs) == 9  # 3 data rows * 3 tenors


# ---------------------------------------------------------------------------
# Tests: blank/dash/NA cell handling
# ---------------------------------------------------------------------------

class TestBlankDashCells:
    def test_dash_cell_produces_no_obs(self):
        rows = [
            ["Date", "1-month", "3-month", "6-month"],
            ["1", "2", "3", "4"],
            ["2026-27", "", "", ""],
            ["30-Jun-26", "-", "3.04", "2.90"],
        ]
        _, obs = _parse_forward_premia(rows, NOW)
        one_m = [o for o in obs if ".1M." in o.imdr_code]
        assert len(one_m) == 0

    def test_blank_cell_produces_no_obs(self):
        rows = [
            ["Date", "1-month", "3-month", "6-month"],
            ["1", "2", "3", "4"],
            ["2026-27", "", "", ""],
            ["30-Jun-26", "", "3.04", "2.90"],
        ]
        _, obs = _parse_forward_premia(rows, NOW)
        one_m = [o for o in obs if ".1M." in o.imdr_code]
        assert len(one_m) == 0

    def test_na_cell_produces_no_obs(self):
        rows = [
            ["Date", "1-month", "3-month", "6-month"],
            ["1", "2", "3", "4"],
            ["2026-27", "", "", ""],
            ["30-Jun-26", "N.A.", "3.04", "2.90"],
        ]
        _, obs = _parse_forward_premia(rows, NOW)
        one_m = [o for o in obs if ".1M." in o.imdr_code]
        assert len(one_m) == 0


# ---------------------------------------------------------------------------
# Tests: dedup
# ---------------------------------------------------------------------------

class TestDedup:
    def test_duplicate_rows_deduplicated(self):
        rows = [
            ["Date", "1-month", "3-month", "6-month"],
            ["1", "2", "3", "4"],
            ["2026-27", "", "", ""],
            ["30-Jun-26", "3.17", "3.04", "2.90"],
            ["30-Jun-26", "3.17", "3.04", "2.90"],
        ]
        _, obs = _parse_forward_premia(rows, NOW)
        one_m = [
            o for o in obs
            if ".1M." in o.imdr_code and o.obs_date == datetime.date(2026, 6, 30)
        ]
        assert len(one_m) == 1


# ---------------------------------------------------------------------------
# Tests: empty input
# ---------------------------------------------------------------------------

class TestEmptyInput:
    def test_empty_table_returns_empty_lists(self):
        inds, obs = _parse_forward_premia([], NOW)
        assert inds == []
        assert obs == []

    def test_only_header_rows_return_empty_obs(self):
        rows = [
            ["Date", "1-month", "3-month", "6-month"],
            ["1", "2", "3", "4"],
        ]
        inds, obs = _parse_forward_premia(rows, NOW)
        assert obs == []


# ---------------------------------------------------------------------------
# Tests: _COL_MAP coverage
# ---------------------------------------------------------------------------

class TestColMap:
    def test_3_columns_mapped(self):
        assert len(_COL_MAP) == 3

    def test_col_order(self):
        assert _COL_MAP[1] == "1M"
        assert _COL_MAP[2] == "3M"
        assert _COL_MAP[3] == "6M"
