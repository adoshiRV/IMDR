"""Unit tests for _parse_nri_deposits in scripts.econ.in.rbi.rbi_dbie_nri_deposits.

No network calls, no DB writes, no headed Chrome.
The fixture mirrors the live SAP-BO table layout confirmed 2026-06-23:
  row[0]: super-header  (Month | | Outstanding | | Flows)
  row[1]: sub-header    (1 NRI Deposits | 1.1 FCNR(B) | 1.2 NR(E)RA | 1.3 NRO | ...)
  row[2]: FY separator  ('2025-26', '', ...)
  row[3+]: month data   ('Apr.', value, ...)

Covers:
- 8 indicator codes produced (4 schemes × 2 measures)
- Correct scheme/measure slug mapping (_COL_MAP)
- FY-year→month date resolution: Apr-Dec = FY start year; Jan-Mar = start year+1
- FCNR(B) Outstanding Mar-2026 value (~33,756 per T34 reconciliation)
- Dedup: same (code, date) appears only once
- Blank / dash cells produce no observation
- Error message strings for empty-table input
"""
from __future__ import annotations

import datetime
import importlib

import pytest

# Use importlib because the package path contains `in`, a Python keyword.
_mod = importlib.import_module("scripts.econ.in.rbi.rbi_dbie_nri_deposits")

_parse_nri_deposits = _mod._parse_nri_deposits
_MONTH_MAP = _mod._MONTH_MAP
_COL_MAP = _mod._COL_MAP

NOW = datetime.datetime(2026, 6, 23, 12, 0, 0, tzinfo=datetime.timezone.utc)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _make_rows(*, include_apr_feb: bool = False) -> list[list[str]]:
    """Minimal fixture matching the live SAP-BO NRI Deposits table layout.

    Columns (0-indexed):
      0=month  1=NRI_TOTAL_OS  2=FCNRB_OS  3=NRERA_OS  4=NRO_OS
               5=NRI_TOTAL_FL  6=FCNRB_FL  7=NRERA_FL  8=NRO_FL
    """
    rows = [
        # row[0]: super-header
        ["Month", "", "Outstanding", "", "", "", "Inflows (+)/ Outflows (-)", "", "", ""],
        # row[1]: sub-header
        [
            "1 NRI Deposits", "1.1 FCNR(B)", "1.2 NR(E)RA", "1.3 NRO",
            "1 NRI Deposits", "1.4 FCNR(B)", "1.5 NR(E)RA", "1.6 NRO",
        ],
        # row[2]: FY separator — skipped
        ["2025-26", "", "", "", "", "", "", "", ""],
        # row[3]: Mar 2026 (FY end, Jan-Mar → start_year+1 = 2026)
        ["Mar.", "165654", "33756", "98564", "33334", "14413", "946", "7941", "5526"],
    ]
    if include_apr_feb:
        # Apr 2025 → FY2025-26 start (Apr-Dec → start_year=2025 → year=2025)
        # Feb 2026 → FY2025-26 (Feb → fy_offset=1 → year=2026)
        rows.insert(3, ["Apr.", "162000", "32500", "97000", "32500", "1300", "80", "700", "520"])
        rows.insert(4, ["Feb.", "164500", "33200", "99100", "32200", "1200", "75", "680", "445"])
    return rows


# ---------------------------------------------------------------------------
# Tests: indicator count and codes
# ---------------------------------------------------------------------------

class TestIndicatorCodes:
    def test_8_indicators_produced(self):
        inds, _ = _parse_nri_deposits(_make_rows(), NOW)
        assert len(inds) == 8

    def test_all_scheme_slugs_present(self):
        inds, _ = _parse_nri_deposits(_make_rows(), NOW)
        codes = {ind.imdr_code for ind in inds}
        for scheme in ("NRI_TOTAL", "FCNRB", "NRERA", "NRO"):
            assert any(scheme in c for c in codes), f"Missing scheme {scheme}"

    def test_both_measures_present(self):
        inds, _ = _parse_nri_deposits(_make_rows(), NOW)
        codes = {ind.imdr_code for ind in inds}
        assert any("OUTSTANDING" in c for c in codes)
        assert any("FLOW" in c for c in codes)

    def test_imdr_code_format(self):
        inds, _ = _parse_nri_deposits(_make_rows(), NOW)
        for ind in inds:
            assert ind.imdr_code.startswith("INDIA.DBIE.NRI_DEPOSITS.")
            assert ind.imdr_code.endswith(".IN")

    def test_unit_usd_mn_for_all(self):
        inds, _ = _parse_nri_deposits(_make_rows(), NOW)
        for ind in inds:
            assert ind.unit == "usd_mn"

    def test_vendor_name_rbi(self):
        inds, _ = _parse_nri_deposits(_make_rows(), NOW)
        for ind in inds:
            assert ind.vendor_name == "RBI"

    def test_category_bop(self):
        inds, _ = _parse_nri_deposits(_make_rows(), NOW)
        for ind in inds:
            assert ind.category == "bop"

    def test_frequency_monthly(self):
        inds, _ = _parse_nri_deposits(_make_rows(), NOW)
        for ind in inds:
            assert ind.frequency == "MONTHLY"


# ---------------------------------------------------------------------------
# Tests: date resolution (FY-year carryforward + month offset)
# ---------------------------------------------------------------------------

class TestDateResolution:
    def test_mar_in_fy2025_26_resolves_to_2026_03_01(self):
        """Mar in FY 2025-26 → fy_offset=1 → year=2025+1=2026 → 2026-03-01."""
        _, obs = _parse_nri_deposits(_make_rows(), NOW)
        dates = {o.obs_date for o in obs}
        assert datetime.date(2026, 3, 1) in dates

    def test_apr_in_fy2025_26_resolves_to_2025_04_01(self):
        """Apr in FY 2025-26 → fy_offset=0 → year=2025 → 2025-04-01."""
        _, obs = _parse_nri_deposits(_make_rows(include_apr_feb=True), NOW)
        dates = {o.obs_date for o in obs}
        assert datetime.date(2025, 4, 1) in dates

    def test_feb_in_fy2025_26_resolves_to_2026_02_01(self):
        """Feb in FY 2025-26 → fy_offset=1 → year=2026 → 2026-02-01."""
        _, obs = _parse_nri_deposits(_make_rows(include_apr_feb=True), NOW)
        dates = {o.obs_date for o in obs}
        assert datetime.date(2026, 2, 1) in dates

    def test_no_obs_before_first_fy_row(self):
        """Rows before any FY separator must be silently skipped."""
        rows = [
            ["Month", "", "Outstanding", "", "", "", "Flows", "", "", ""],
            ["1 NRI Deposits", "1.1 FCNR(B)", "1.2 NR(E)RA", "1.3 NRO",
             "1 NRI Deposits", "1.4 FCNR(B)", "1.5 NR(E)RA", "1.6 NRO"],
            # No FY row before this data row → current_fy_start is None → skip
            ["Apr.", "162000", "32500", "97000", "32500", "1300", "80", "700", "520"],
            ["2025-26", "", "", "", "", "", "", "", ""],
            ["Mar.", "165654", "33756", "98564", "33334", "14413", "946", "7941", "5526"],
        ]
        _, obs = _parse_nri_deposits(rows, NOW)
        dates = {o.obs_date for o in obs}
        # Apr row has no FY context → must not appear
        assert datetime.date(2025, 4, 1) not in dates
        # Mar row after FY row → must appear
        assert datetime.date(2026, 3, 1) in dates


# ---------------------------------------------------------------------------
# Tests: known values (T34 reconciliation anchor)
# ---------------------------------------------------------------------------

class TestKnownValues:
    def test_fcnrb_outstanding_mar2026_33756(self):
        """FCNR(B) Outstanding Mar-2026 = 33,756 USD mn (T34 anchor)."""
        _, obs = _parse_nri_deposits(_make_rows(), NOW)
        match = [
            o for o in obs
            if "FCNRB.OUTSTANDING" in o.imdr_code
            and o.obs_date == datetime.date(2026, 3, 1)
        ]
        assert len(match) == 1
        assert abs(match[0].value - 33756.0) < 0.01

    def test_fcnrb_flow_mar2026_946(self):
        """FCNR(B) Flow (col 6) Mar-2026 FY row = 946 USD mn."""
        _, obs = _parse_nri_deposits(_make_rows(), NOW)
        match = [
            o for o in obs
            if "FCNRB.FLOW" in o.imdr_code
            and o.obs_date == datetime.date(2026, 3, 1)
        ]
        assert len(match) == 1
        assert abs(match[0].value - 946.0) < 0.01

    def test_nri_total_outstanding_165654(self):
        _, obs = _parse_nri_deposits(_make_rows(), NOW)
        match = [
            o for o in obs
            if "NRI_TOTAL.OUTSTANDING" in o.imdr_code
            and o.obs_date == datetime.date(2026, 3, 1)
        ]
        assert len(match) == 1
        assert abs(match[0].value - 165654.0) < 0.01


# ---------------------------------------------------------------------------
# Tests: blank/dash cell handling
# ---------------------------------------------------------------------------

class TestBlankDashCells:
    def test_dash_cell_produces_no_obs(self):
        rows = [
            ["Month", "", "Outstanding", "", "", "", "Flows", "", "", ""],
            ["1 NRI Deposits", "1.1 FCNR(B)", "1.2 NR(E)RA", "1.3 NRO",
             "1 NRI Deposits", "1.4 FCNR(B)", "1.5 NR(E)RA", "1.6 NRO"],
            ["2025-26", "", "", "", "", "", "", "", ""],
            # Col 1 is dash → NRI_TOTAL OUTSTANDING should produce no obs for that col
            ["Mar.", "-", "33756", "98564", "33334", "14413", "946", "7941", "5526"],
        ]
        _, obs = _parse_nri_deposits(rows, NOW)
        nri_total_os = [
            o for o in obs
            if "NRI_TOTAL.OUTSTANDING" in o.imdr_code
            and o.obs_date == datetime.date(2026, 3, 1)
        ]
        assert len(nri_total_os) == 0

    def test_blank_cell_produces_no_obs(self):
        rows = [
            ["Month", "", "Outstanding", "", "", "", "Flows", "", "", ""],
            ["1 NRI Deposits", "1.1 FCNR(B)", "1.2 NR(E)RA", "1.3 NRO",
             "1 NRI Deposits", "1.4 FCNR(B)", "1.5 NR(E)RA", "1.6 NRO"],
            ["2025-26", "", "", "", "", "", "", "", ""],
            ["Mar.", "", "33756", "98564", "33334", "14413", "946", "7941", "5526"],
        ]
        _, obs = _parse_nri_deposits(rows, NOW)
        nri_total_os = [
            o for o in obs
            if "NRI_TOTAL.OUTSTANDING" in o.imdr_code
        ]
        assert len(nri_total_os) == 0

    def test_na_cell_produces_no_obs(self):
        rows = [
            ["Month", "", "Outstanding", "", "", "", "Flows", "", "", ""],
            ["1 NRI Deposits", "1.1 FCNR(B)", "1.2 NR(E)RA", "1.3 NRO",
             "1 NRI Deposits", "1.4 FCNR(B)", "1.5 NR(E)RA", "1.6 NRO"],
            ["2025-26", "", "", "", "", "", "", "", ""],
            ["Mar.", "N.A.", "33756", "98564", "33334", "14413", "946", "7941", "5526"],
        ]
        _, obs = _parse_nri_deposits(rows, NOW)
        nri_total_os = [
            o for o in obs
            if "NRI_TOTAL.OUTSTANDING" in o.imdr_code
        ]
        assert len(nri_total_os) == 0


# ---------------------------------------------------------------------------
# Tests: dedup
# ---------------------------------------------------------------------------

class TestDedup:
    def test_duplicate_rows_deduplicated(self):
        """Same (code, date) from two identical data rows → single obs."""
        rows = [
            ["Month", "", "Outstanding", "", "", "", "Flows", "", "", ""],
            ["1 NRI Deposits", "1.1 FCNR(B)", "1.2 NR(E)RA", "1.3 NRO",
             "1 NRI Deposits", "1.4 FCNR(B)", "1.5 NR(E)RA", "1.6 NRO"],
            ["2025-26", "", "", "", "", "", "", "", ""],
            ["Mar.", "165654", "33756", "98564", "33334", "14413", "946", "7941", "5526"],
            ["Mar.", "165654", "33756", "98564", "33334", "14413", "946", "7941", "5526"],
        ]
        _, obs = _parse_nri_deposits(rows, NOW)
        fcnrb_os = [
            o for o in obs
            if "FCNRB.OUTSTANDING" in o.imdr_code
            and o.obs_date == datetime.date(2026, 3, 1)
        ]
        assert len(fcnrb_os) == 1


# ---------------------------------------------------------------------------
# Tests: empty input
# ---------------------------------------------------------------------------

class TestEmptyInput:
    def test_empty_table_returns_empty_lists(self):
        inds, obs = _parse_nri_deposits([], NOW)
        assert inds == []
        assert obs == []

    def test_only_headers_returns_empty_obs(self):
        rows = [
            ["Month", "", "Outstanding", "", "", "", "Flows", "", "", ""],
            ["1 NRI Deposits", "1.1 FCNR(B)", "1.2 NR(E)RA", "1.3 NRO",
             "1 NRI Deposits", "1.4 FCNR(B)", "1.5 NR(E)RA", "1.6 NRO"],
        ]
        inds, obs = _parse_nri_deposits(rows, NOW)
        assert obs == []


# ---------------------------------------------------------------------------
# Tests: _MONTH_MAP coverage
# ---------------------------------------------------------------------------

class TestMonthMap:
    def test_all_12_months_covered(self):
        expected = {
            "apr", "may", "jun", "jul", "aug", "sep",
            "oct", "nov", "dec", "jan", "feb", "mar",
        }
        assert set(_MONTH_MAP.keys()) == expected

    def test_apr_is_offset_0(self):
        _, offset = _MONTH_MAP["apr"]
        assert offset == 0

    def test_mar_is_offset_1(self):
        _, offset = _MONTH_MAP["mar"]
        assert offset == 1

    def test_jan_is_offset_1(self):
        _, offset = _MONTH_MAP["jan"]
        assert offset == 1


# ---------------------------------------------------------------------------
# Tests: _COL_MAP coverage
# ---------------------------------------------------------------------------

class TestColMap:
    def test_8_columns_mapped(self):
        assert len(_COL_MAP) == 8

    def test_cols_1_to_4_are_outstanding(self):
        for ci in (1, 2, 3, 4):
            _, measure = _COL_MAP[ci]
            assert measure == "OUTSTANDING", f"col {ci} should be OUTSTANDING"

    def test_cols_5_to_8_are_flow(self):
        for ci in (5, 6, 7, 8):
            _, measure = _COL_MAP[ci]
            assert measure == "FLOW", f"col {ci} should be FLOW"

    def test_scheme_order(self):
        assert _COL_MAP[1][0] == "NRI_TOTAL"
        assert _COL_MAP[2][0] == "FCNRB"
        assert _COL_MAP[3][0] == "NRERA"
        assert _COL_MAP[4][0] == "NRO"
        assert _COL_MAP[5][0] == "NRI_TOTAL"
        assert _COL_MAP[6][0] == "FCNRB"
        assert _COL_MAP[7][0] == "NRERA"
        assert _COL_MAP[8][0] == "NRO"
