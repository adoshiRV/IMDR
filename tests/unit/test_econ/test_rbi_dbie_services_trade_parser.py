"""Unit tests for _parse_services_trade in
scripts.econ.in.rbi.rbi_dbie_services_trade.

No network calls, no DB writes, no headed Chrome.
The fixture mirrors the live SAP-BO table layout confirmed 2026-07-14:
  row[0]: header   ('Month', 'Receipts (Exports)', 'Payments (Imports)', 'Net')
  row[1]: ordinal  ('1', '2', '3', '4')
  row[2+]: data    ('Jun-2025', '32,108', '15,900', '16,208')

Covers:
- 3 indicator codes produced (EXPORTS / IMPORTS / NET)
- Correct measure slug mapping (_COL_MAP)
- Date parsing: "Mon-YYYY"
- Header / ordinal rows silently skipped (neither parses as a month)
- Known value anchor (Jun-2025 scrape)
- Duplicate-row dedup keeps the FIRST occurrence (Mar-2020 quirk)
- Blank / dash / NA cells produce no observation
- Comma-thousands stripped before float parse
- Empty-table input
"""
from __future__ import annotations

import datetime
import importlib

# Use importlib because the package path contains `in`, a Python keyword.
_mod = importlib.import_module("scripts.econ.in.rbi.rbi_dbie_services_trade")

_parse_services_trade = _mod._parse_services_trade
_parse_month = _mod._parse_month
_COL_MAP = _mod._COL_MAP

NOW = datetime.datetime(2026, 7, 14, 12, 0, 0, tzinfo=datetime.timezone.utc)


# ---------------------------------------------------------------------------
# Fixture helper
# ---------------------------------------------------------------------------

def _make_rows(*, include_extra_months: bool = False) -> list[list[str]]:
    """Minimal fixture matching the live SAP-BO ITS table layout."""
    rows = [
        ["Month", "Receipts (Exports)", "Payments (Imports)", "Net"],
        ["1", "2", "3", "4"],
        ["Jun-2025", "32,108", "15,900", "16,208"],
    ]
    if include_extra_months:
        rows.append(["May-2025", "32,456", "16,697", "15,758"])
        rows.append(["Apr-2018", "16,728", "10,255", "6,472"])
    return rows


# ---------------------------------------------------------------------------
# Tests: indicator count and codes
# ---------------------------------------------------------------------------

class TestIndicatorCodes:
    def test_3_indicators_produced(self):
        inds, _ = _parse_services_trade(_make_rows(), NOW)
        assert len(inds) == 3

    def test_all_measure_slugs_present(self):
        inds, _ = _parse_services_trade(_make_rows(), NOW)
        codes = {ind.imdr_code for ind in inds}
        for measure in ("EXPORTS", "IMPORTS", "NET"):
            assert any(f".{measure}." in c for c in codes), f"Missing measure {measure}"

    def test_imdr_code_format(self):
        inds, _ = _parse_services_trade(_make_rows(), NOW)
        for ind in inds:
            assert ind.imdr_code.startswith("INDIA.DBIE.SERVICES_TRADE.")
            assert ind.imdr_code.endswith(".IN")

    def test_unit_usd_mn_for_all(self):
        inds, _ = _parse_services_trade(_make_rows(), NOW)
        for ind in inds:
            assert ind.unit == "usd_mn"

    def test_vendor_name_rbi(self):
        inds, _ = _parse_services_trade(_make_rows(), NOW)
        for ind in inds:
            assert ind.vendor_name == "RBI"

    def test_category_bop(self):
        inds, _ = _parse_services_trade(_make_rows(), NOW)
        for ind in inds:
            assert ind.category == "bop"

    def test_frequency_monthly(self):
        inds, _ = _parse_services_trade(_make_rows(), NOW)
        for ind in inds:
            assert ind.frequency == "MONTHLY"

    def test_no_category_breakdown_codes(self):
        """This report is headline-only -- no Software/Travel/etc split."""
        inds, _ = _parse_services_trade(_make_rows(), NOW)
        codes = {ind.imdr_code for ind in inds}
        for leak in ("SOFTWARE", "TRAVEL", "TRANSPORTATION", "INSURANCE"):
            assert not any(leak in c for c in codes)


# ---------------------------------------------------------------------------
# Tests: date parsing
# ---------------------------------------------------------------------------

class TestMonthParsing:
    def test_mon_yyyy_resolves(self):
        assert _parse_month("Jun-2025") == datetime.date(2025, 6, 1)

    def test_header_row_col0_does_not_parse(self):
        assert _parse_month("Month") is None

    def test_ordinal_row_col0_does_not_parse(self):
        assert _parse_month("1") is None

    def test_blank_col0_does_not_parse(self):
        assert _parse_month("") is None

    def test_header_ordinal_rows_produce_no_obs(self):
        _, obs = _parse_services_trade(_make_rows(), NOW)
        dates = {o.obs_date for o in obs}
        assert datetime.date(2025, 6, 1) in dates
        assert len(obs) == 3  # only the one data row * 3 measures


# ---------------------------------------------------------------------------
# Tests: known values (Jun-2025 scrape anchor)
# ---------------------------------------------------------------------------

class TestKnownValues:
    def test_exports_jun_2025_32108(self):
        _, obs = _parse_services_trade(_make_rows(), NOW)
        match = [
            o for o in obs
            if ".EXPORTS." in o.imdr_code and o.obs_date == datetime.date(2025, 6, 1)
        ]
        assert len(match) == 1
        assert abs(match[0].value - 32108) < 0.001

    def test_imports_jun_2025_15900(self):
        _, obs = _parse_services_trade(_make_rows(), NOW)
        match = [
            o for o in obs
            if ".IMPORTS." in o.imdr_code and o.obs_date == datetime.date(2025, 6, 1)
        ]
        assert len(match) == 1
        assert abs(match[0].value - 15900) < 0.001

    def test_net_jun_2025_16208(self):
        _, obs = _parse_services_trade(_make_rows(), NOW)
        match = [
            o for o in obs
            if ".NET." in o.imdr_code and o.obs_date == datetime.date(2025, 6, 1)
        ]
        assert len(match) == 1
        assert abs(match[0].value - 16208) < 0.001

    def test_multiple_months_all_present(self):
        _, obs = _parse_services_trade(_make_rows(include_extra_months=True), NOW)
        dates = {o.obs_date for o in obs}
        assert datetime.date(2025, 6, 1) in dates
        assert datetime.date(2025, 5, 1) in dates
        assert datetime.date(2018, 4, 1) in dates
        assert len(obs) == 9  # 3 data rows * 3 measures


# ---------------------------------------------------------------------------
# Tests: comma-thousands + blank/dash/NA cell handling
# ---------------------------------------------------------------------------

class TestCellParsing:
    def test_comma_thousands_stripped(self):
        _, obs = _parse_services_trade(_make_rows(), NOW)
        exports = [o for o in obs if ".EXPORTS." in o.imdr_code][0]
        assert exports.value == 32108.0

    def test_dash_cell_produces_no_obs(self):
        rows = [
            ["Month", "Receipts (Exports)", "Payments (Imports)", "Net"],
            ["1", "2", "3", "4"],
            ["Jun-2025", "-", "15,900", "16,208"],
        ]
        _, obs = _parse_services_trade(rows, NOW)
        exports = [o for o in obs if ".EXPORTS." in o.imdr_code]
        assert len(exports) == 0

    def test_blank_cell_produces_no_obs(self):
        rows = [
            ["Month", "Receipts (Exports)", "Payments (Imports)", "Net"],
            ["1", "2", "3", "4"],
            ["Jun-2025", "", "15,900", "16,208"],
        ]
        _, obs = _parse_services_trade(rows, NOW)
        exports = [o for o in obs if ".EXPORTS." in o.imdr_code]
        assert len(exports) == 0

    def test_na_cell_produces_no_obs(self):
        rows = [
            ["Month", "Receipts (Exports)", "Payments (Imports)", "Net"],
            ["1", "2", "3", "4"],
            ["Jun-2025", "N.A.", "15,900", "16,208"],
        ]
        _, obs = _parse_services_trade(rows, NOW)
        exports = [o for o in obs if ".EXPORTS." in o.imdr_code]
        assert len(exports) == 0


# ---------------------------------------------------------------------------
# Tests: duplicate-row dedup (Mar-2020 quirk)
# ---------------------------------------------------------------------------

class TestDuplicateRowDedup:
    def test_duplicate_month_keeps_first_occurrence(self):
        rows = [
            ["Month", "Receipts (Exports)", "Payments (Imports)", "Net"],
            ["1", "2", "3", "4"],
            ["Mar-2020", "17,563", "10,089", "7,474"],
            ["Mar-2020", "17,139", "10,048", "7,091"],
        ]
        _, obs = _parse_services_trade(rows, NOW)
        exports = [o for o in obs if ".EXPORTS." in o.imdr_code]
        assert len(exports) == 1
        assert exports[0].value == 17563.0


# ---------------------------------------------------------------------------
# Tests: empty input
# ---------------------------------------------------------------------------

class TestEmptyInput:
    def test_empty_table_returns_empty_lists(self):
        inds, obs = _parse_services_trade([], NOW)
        assert inds == []
        assert obs == []

    def test_only_header_rows_return_empty_obs(self):
        rows = [
            ["Month", "Receipts (Exports)", "Payments (Imports)", "Net"],
            ["1", "2", "3", "4"],
        ]
        inds, obs = _parse_services_trade(rows, NOW)
        assert obs == []


# ---------------------------------------------------------------------------
# Tests: _COL_MAP coverage
# ---------------------------------------------------------------------------

class TestColMap:
    def test_3_columns_mapped(self):
        assert len(_COL_MAP) == 3

    def test_col_order(self):
        assert _COL_MAP[1] == "EXPORTS"
        assert _COL_MAP[2] == "IMPORTS"
        assert _COL_MAP[3] == "NET"
