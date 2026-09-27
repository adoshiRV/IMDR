"""Unit tests for new RBI Bulletin parsers added 2026-06-18.

No network calls, no DB writes, no headed Chrome.
All parsers are tested with small inline row fixtures that mirror the
real XLSX layout documented in the task spec and confirmed against
playground/econ/in/rbi/_smoke/downloads/T*.xlsx.

Covered parsers:
- parse_nri_deposits_34  (T34 — Outstanding/Flow dual-block)
- parse_wide_table       (T35/T36/T30 — plain wide; T25/T38/T5 — with carry_section)
- parse_cd_cp            (T28/T29 — amount rows + range-string rate row)
- parse_date_rows        (T3 — LAF daily date-per-row)
- parse_iip_assets_liab  (T44 — Assets/Liabilities paired columns)
- parse_tbill_auctions_26 (T26 — per-tenor per-auction-date)
- _parse_date            (format coverage including T3 "Mar. 1, 2026")
"""
from __future__ import annotations

import datetime
import importlib

import pytest

# Use importlib because the package path contains `in`, a Python keyword.
_rbi = importlib.import_module("scripts.econ.in.rbi.rbi_bulletin")

_parse_date = _rbi._parse_date
parse_nri_deposits_34 = _rbi.parse_nri_deposits_34
parse_wide_table = _rbi.parse_wide_table
parse_cd_cp = _rbi.parse_cd_cp
parse_date_rows = _rbi.parse_date_rows
parse_iip_assets_liab = _rbi.parse_iip_assets_liab
parse_tbill_auctions_26 = _rbi.parse_tbill_auctions_26
parse_fx_intervention_4 = _rbi.parse_fx_intervention_4
parse_forward_book_tenor_4a = _rbi.parse_forward_book_tenor_4a

NOW = datetime.datetime(2026, 6, 18, 12, 0, 0, tzinfo=datetime.timezone.utc)

# ---------------------------------------------------------------------------
# _parse_date format coverage
# ---------------------------------------------------------------------------

class TestParseDate:
    def test_iso(self):
        assert _parse_date("2026-03-01") == datetime.date(2026, 3, 1)

    def test_b_d_Y_with_period(self):
        # T3: "Mar. 1, 2026"
        assert _parse_date("Mar. 1, 2026") == datetime.date(2026, 3, 1)

    def test_b_Y_no_day(self):
        # "Mar. 2026" → 1st of month
        assert _parse_date("Mar. 2026") == datetime.date(2026, 3, 1)

    def test_fy_maps_to_april_1(self):
        assert _parse_date("2024-25") == datetime.date(2024, 4, 1)

    def test_empty_returns_none(self):
        assert _parse_date("") is None

    def test_p_suffix_stripped(self):
        # "(P)" suffix must be stripped before parsing
        assert _parse_date("Mar 2026 (P)") == datetime.date(2026, 3, 1)


# ---------------------------------------------------------------------------
# parse_nri_deposits_34
# ---------------------------------------------------------------------------

def _make_t34_rows() -> list[list[str]]:
    """Minimal T34 fixture matching May-2026 layout."""
    return [
        ["", "No. 34: Non-Resident Deposits"],
        ["", "(US $ Million)"],
        # R2: block header
        ["", "Scheme", "Outstanding", "", "", "", "Flows"],
        # R3: FY / year labels
        ["", "", "2024-25", "2025", "2026", "", "2024-25", "2025-26"],
        # R4: month tokens
        ["", "", "", "Mar.", "Feb.", "Mar. (P)", "Apr.-Mar.", "Apr.-Mar.(P)"],
        # R5: col numbers
        ["", "", "1", "2", "3", "4", "5", "6"],
        # Data rows
        ["", "1. NRI Deposits", "164677", "164677", "167579", "165654", "16163", "14413"],
        ["", "1.1 FCNR(B)",    "32809",  "32809",  "33720",  "33756",  "7076",  "946"],
        ["", "1.2 NR(E)RA",    "100733", "100733", "99766",  "98564",  "4713",  "7941"],
        ["", "1.3 NRO",        "31135",  "31135",  "34092",  "33334",  "4374",  "5526"],
        ["", "P: Provisional"],
    ]


class TestParseNriDeposits34:
    def _target(self):
        return {
            "name": "nri_deposits_34", "table_num": "34",
            "imdr_prefix": "INDIA.RBI_BULLETIN.NRI_DEPOSITS",
            "category": "bop", "frequency": "MONTHLY",
            "description": "T34 test",
        }

    def test_returns_8_indicators(self):
        inds, obs = parse_nri_deposits_34(_make_t34_rows(), self._target(), NOW)
        assert len(inds) == 8  # 4 schemes × 2 measures

    def test_fcnrb_flow_946(self):
        inds, obs = parse_nri_deposits_34(_make_t34_rows(), self._target(), NOW)
        match = [o for o in obs
                 if "FCNRB.FLOW" in o.imdr_code and o.value == pytest.approx(946)]
        assert len(match) == 1, "FCNR(B) FY25-26 flow=946 not found"

    def test_fcnrb_outstanding_mar2026_33756(self):
        inds, obs = parse_nri_deposits_34(_make_t34_rows(), self._target(), NOW)
        # Mar.(P) 2026 OUTSTANDING = 33756; date resolves to 2026-03-01
        match = [o for o in obs
                 if "FCNRB.OUTSTANDING" in o.imdr_code
                 and o.obs_date == datetime.date(2026, 3, 1)
                 and abs(o.value - 33756) < 0.1]
        assert len(match) == 1, (
            f"FCNR(B) OUTSTANDING Mar-2026 not found; obs={[(o.obs_date, o.value) for o in obs if 'FCNRB.OUTSTANDING' in o.imdr_code]}"
        )

    def test_flow_dates_are_fy_end_march31(self):
        inds, obs = parse_nri_deposits_34(_make_t34_rows(), self._target(), NOW)
        flow_obs = [o for o in obs if "FLOW" in o.imdr_code]
        for o in flow_obs:
            assert o.obs_date.month == 3 and o.obs_date.day == 31, (
                f"FLOW obs not at March 31: {o.obs_date}"
            )

    def test_outstanding_unit_usd_mn(self):
        inds, _ = parse_nri_deposits_34(_make_t34_rows(), self._target(), NOW)
        for ind in inds:
            assert ind.unit == "usd_mn"

    def test_all_4_schemes_present(self):
        inds, _ = parse_nri_deposits_34(_make_t34_rows(), self._target(), NOW)
        codes = {ind.imdr_code for ind in inds}
        for scheme in ("NRI_TOTAL", "FCNRB", "NRERA", "NRO"):
            assert any(scheme in c for c in codes), f"missing scheme {scheme}"


# ---------------------------------------------------------------------------
# parse_wide_table — plain (T35/T36/T30)
# ---------------------------------------------------------------------------

def _make_wide_rows(items: list[str]) -> list[list[str]]:
    """Minimal wide-table rows: 1 FY + 2 monthly periods."""
    rows = [
        ["", "No. 35: Test"],
        ["", "(US $ Million)"],
        ["", "Item", "2024-25", "2025", "2026"],
        ["", "",      "",       "Mar.", "Feb."],
        ["", "",      "1",      "2",    "3"],
    ]
    for item in items:
        rows.append(["", item, "100", "110", "120"])
    return rows


class TestParseWideTable:
    def _target(self, carry=False):
        return {
            "name": "foreign_investment_35", "table_num": "35",
            "imdr_prefix": "INDIA.RBI_BULLETIN.FOREIGN_INVESTMENT",
            "category": "bop", "frequency": "MONTHLY",
            "description": "T35 test",
            "wide": {"header_match": "Item", "data_first_col": 2, "unit": "usd_mn",
                     "carry_section": carry},
        }

    def test_indicator_count(self):
        rows = _make_wide_rows(["1.1 Net FDI", "1.2 Portfolio FDI"])
        inds, obs = parse_wide_table(rows, self._target(), NOW)
        assert len(inds) == 2

    def test_obs_count(self):
        rows = _make_wide_rows(["1.1 Net FDI"])
        _, obs = parse_wide_table(rows, self._target(), NOW)
        # 3 period cols → 3 obs
        assert len(obs) == 3

    def test_unit_usd_mn(self):
        rows = _make_wide_rows(["1.1 Net FDI"])
        inds, _ = parse_wide_table(rows, self._target(), NOW)
        assert inds[0].unit == "usd_mn"

    def test_carry_section_prefixes_sub_rows(self):
        rows = [
            ["", "No. 25: T-bill ownership"],
            ["", "(₹ Crore)"],
            ["", "Item", "2025", "2026"],
            ["", "",      "Mar.", "Feb."],
            ["", "",      "1",    "2"],
            ["", "1. 91-day"],                    # section header — no values
            ["", "1.1 Banks", "26554", "17961"],  # sub-row
        ]
        target = {
            "name": "tbill_ownership_25", "table_num": "25",
            "imdr_prefix": "INDIA.RBI_BULLETIN.TBILL_OWNERSHIP",
            "category": "rates", "frequency": "WEEKLY",
            "description": "T25 test",
            "wide": {"header_match": "Item", "data_first_col": 2,
                     "unit": "inr_cr", "carry_section": True},
        }
        inds, obs = parse_wide_table(rows, target, NOW)
        assert len(inds) == 1
        # Slug must include the normalised section prefix "91_DAY" AND the
        # sub-row "BANKS" — proving carry_section actually prefixed the sub-row
        # (not just that some digit/word appears somewhere).
        assert "91_DAY" in inds[0].imdr_code
        assert "BANKS" in inds[0].imdr_code
        assert inds[0].imdr_code.index("91_DAY") < inds[0].imdr_code.index("BANKS")


# ---------------------------------------------------------------------------
# parse_cd_cp — T28/T29
# ---------------------------------------------------------------------------

def _make_cd_rows(table_name: str = "T28") -> list[list[str]]:
    return [
        ["", f"No. 28 : {table_name}"],
        ["", "Item", "2025", "2026"],
        ["", "",     "Apr. 18", "Mar. 15"],
        ["", "",     "1",       "2"],
        ["", "1. Amount Outstanding (₹ Crore)", "518759.57", "679391.41"],
        ["", "1.1 Issued during the fortnight (₹ Crore)", "7213.32", "107613.36"],
        ["", "2. Rate of Interest (per cent)", "6.43-7.37", "5.25-7.56"],
    ]


class TestParseCdCp:
    def _target(self, prefix: str = "INDIA.RBI_BULLETIN.CD"):
        return {
            "name": "cd_28", "table_num": "28",
            "imdr_prefix": prefix,
            "category": "rates", "frequency": "WEEKLY",
            "description": "T28 Certificates of Deposit",
        }

    def test_4_indicators(self):
        inds, _ = parse_cd_cp(_make_cd_rows(), self._target(), NOW)
        # 2 amount rows + 2 range indicators (LO/HI)
        assert len(inds) == 4

    def test_range_lo_indicator_unit_pct(self):
        inds, _ = parse_cd_cp(_make_cd_rows(), self._target(), NOW)
        lo_inds = [i for i in inds if "RANGE_LO" in i.imdr_code]
        assert len(lo_inds) == 1
        assert lo_inds[0].unit == "pct"

    def test_range_lo_value_6_43(self):
        _, obs = parse_cd_cp(_make_cd_rows(), self._target(), NOW)
        lo_obs = [o for o in obs if "RANGE_LO" in o.imdr_code
                  and o.value == pytest.approx(6.43)]
        assert len(lo_obs) == 1

    def test_range_hi_value_7_37(self):
        _, obs = parse_cd_cp(_make_cd_rows(), self._target(), NOW)
        hi_obs = [o for o in obs if "RANGE_HI" in o.imdr_code
                  and o.value == pytest.approx(7.37)]
        assert len(hi_obs) == 1

    def test_amount_outstanding_unit_inr_cr(self):
        inds, _ = parse_cd_cp(_make_cd_rows(), self._target(), NOW)
        amount_inds = [i for i in inds if "RANGE" not in i.imdr_code]
        for ind in amount_inds:
            assert ind.unit == "inr_cr"

    def test_range_string_does_not_crash_amount_parse(self):
        # The range row should not produce numeric obs for the amount indicators
        _, obs = parse_cd_cp(_make_cd_rows(), self._target(), NOW)
        amount_codes = {o.imdr_code for o in obs if "RANGE" not in o.imdr_code}
        # No NaN / crash — amount obs should be present with valid floats
        amount_obs = [o for o in obs if o.imdr_code in amount_codes]
        assert all(isinstance(o.value, float) for o in amount_obs)


# ---------------------------------------------------------------------------
# parse_date_rows — T3 LAF
# ---------------------------------------------------------------------------

def _make_t3_rows() -> list[list[str]]:
    """Minimal T3 fixture: Date-per-row with Repo + SDF columns."""
    return [
        ["", "No. 3: Liquidity Operations by RBI"],
        ["", "(₹ Crore)"],
        ["", "Date", "Liquidity Adjustment Facility", "", "Standing Liquidity Facilities"],
        ["", "",     "Repo", "SDF", ""],
        ["", "",     "1",    "2",   "3"],
        ["", "Mar. 1, 2026",  "-",     "300689", "-"],
        ["", "Mar. 2, 2026",  "-",     "389616", "-"],
        ["", "Mar. 17, 2026", "48014", "255412", "-"],
    ]


class TestParseDateRows:
    def _target(self):
        return {
            "name": "laf_3", "table_num": "3",
            "imdr_prefix": "INDIA.RBI_BULLETIN.LAF",
            "category": "cb_balance_sheet", "frequency": "DAILY",
            "description": "T3 Liquidity Operations",
        }

    def test_indicators_found(self):
        inds, _ = parse_date_rows(_make_t3_rows(), self._target(), NOW)
        assert len(inds) >= 1

    def test_sdf_obs_count(self):
        _, obs = parse_date_rows(_make_t3_rows(), self._target(), NOW)
        # SDF has values in all 3 rows
        sdf_obs = [o for o in obs if "SDF" in o.imdr_code]
        assert len(sdf_obs) == 3

    def test_repo_obs_only_where_not_dash(self):
        _, obs = parse_date_rows(_make_t3_rows(), self._target(), NOW)
        repo_obs = [o for o in obs if o.imdr_code.endswith("REPO.IN")
                    and "VARIABLE" not in o.imdr_code
                    and "REVERSE" not in o.imdr_code]
        # Only Mar. 17, 2026 has Repo=48014 (others are "-")
        assert len(repo_obs) == 1
        assert repo_obs[0].value == pytest.approx(48014)
        assert repo_obs[0].obs_date == datetime.date(2026, 3, 17)

    def test_date_format_mar_dot_1_comma_2026(self):
        _, obs = parse_date_rows(_make_t3_rows(), self._target(), NOW)
        dates = {o.obs_date for o in obs}
        assert datetime.date(2026, 3, 1) in dates
        assert datetime.date(2026, 3, 2) in dates

    def test_dash_cells_produce_no_obs(self):
        _, obs = parse_date_rows(_make_t3_rows(), self._target(), NOW)
        # Every observation must have a non-None, non-dash value
        for o in obs:
            assert o.value is not None


# ---------------------------------------------------------------------------
# parse_iip_assets_liab — T44
# ---------------------------------------------------------------------------

def _make_t44_rows() -> list[list[str]]:
    """Minimal T44: 1 item, 2 quarter-end periods, Assets + Liabilities."""
    return [
        ["", "No. 44: India's International Investment Position"],
        ["", "(US$ Million)"],
        ["", "Item", "As on Financial Year/Quarter End"],
        # R3: FY / year labels — FY spans A+L cols, Dec spans A+L cols
        ["", "", "2024-25", "", "2024"],
        # R4: month tokens for non-FY periods
        ["", "", "", "", "Dec."],
        # R5: Assets / Liabilities sub-header
        ["", "", "Assets", "Liabilities", "Assets", "Liabilities"],
        # R6: col numbers
        ["", "", "1", "2", "3", "4"],
        # Data rows
        ["", "1. Direct investment Abroad/in India", "270441", "556974", "260755", "547234"],
        ["", "1.1 Equity Capital", "173559", "521931", "166493", "512997"],
        ["", "Note: test footnote"],
    ]


class TestParseIipAssetsLiab:
    def _target(self):
        return {
            "name": "iip_44", "table_num": "44",
            "imdr_prefix": "INDIA.RBI_BULLETIN.IIP_INTL",
            "category": "bop", "frequency": "QUARTERLY",
            "description": "T44 IIP test",
        }

    def test_assets_and_liabilities_indicators(self):
        inds, _ = parse_iip_assets_liab(_make_t44_rows(), self._target(), NOW)
        codes = {ind.imdr_code for ind in inds}
        has_assets = any("ASSETS" in c for c in codes)
        has_liab = any("LIABILITIES" in c for c in codes)
        assert has_assets and has_liab

    def test_direct_investment_assets_270441(self):
        _, obs = parse_iip_assets_liab(_make_t44_rows(), self._target(), NOW)
        match = [o for o in obs
                 if "DIRECT_INVESTMENT" in o.imdr_code
                 and "ASSETS" in o.imdr_code
                 and abs(o.value - 270441) < 0.1]
        assert len(match) >= 1

    def test_unit_usd_mn(self):
        inds, _ = parse_iip_assets_liab(_make_t44_rows(), self._target(), NOW)
        for ind in inds:
            assert ind.unit == "usd_mn"

    def test_note_row_excluded(self):
        inds, _ = parse_iip_assets_liab(_make_t44_rows(), self._target(), NOW)
        for ind in inds:
            assert "NOTE" not in ind.imdr_code.upper()


# ---------------------------------------------------------------------------
# parse_tbill_auctions_26 — T26
# ---------------------------------------------------------------------------

def _make_t26_rows() -> list[list[str]]:
    """Minimal T26: 91-day section with 2 auctions."""
    return [
        ["", "No. 26: Auctions of Treasury Bills"],
        ["", "(Amount in ₹ Crore)"],
        ["", "Date of Auction", "Notified Amount", "Bids Received", "", "",
         "Bids Accepted", "", "", "Total Issue (6+7)", "Cut-off Price (₹)",
         "Implicit Yield at Cut-off Price (per cent)"],
        ["", "", "", "Number", "Total Face Value", "", "Number", "Total Face Value"],
        ["", "", "", "", "Competitive", "Non-Competitive", "",
         "Competitive", "Non-Competitive"],
        ["", "", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10"],
        ["", "91-day Treasury Bills"],
        ["", "2025-26"],
        ["", "Feb. 25", "14000", "147", "46399", "1538", "69", "13981", "1538", "15519", "98.7", "5.2998"],
        ["", "Mar. 4",  "14000", "134", "43907", "1517", "52", "13983", "1517", "15500", "98.69", "5.3397"],
    ]


class TestParseTbillAuctions26:
    def _target(self):
        return {
            "name": "tbill_auctions_26", "table_num": "26",
            "imdr_prefix": "INDIA.RBI_BULLETIN.TBILL_AUCTIONS",
            "category": "rates", "frequency": "WEEKLY",
            "description": "T26 T-bill auctions test",
        }

    def test_three_indicators_per_tenor(self):
        inds, _ = parse_tbill_auctions_26(_make_t26_rows(), self._target(), NOW)
        # 91D × 3 measures
        codes_91 = [i.imdr_code for i in inds if "91D" in i.imdr_code]
        assert len(codes_91) == 3

    def test_cutoff_yield_indicator_unit_pct(self):
        inds, _ = parse_tbill_auctions_26(_make_t26_rows(), self._target(), NOW)
        yield_inds = [i for i in inds if "CUTOFF_YIELD" in i.imdr_code]
        assert len(yield_inds) >= 1
        for ind in yield_inds:
            assert ind.unit == "pct"

    def test_feb25_yield_5_2998(self):
        _, obs = parse_tbill_auctions_26(_make_t26_rows(), self._target(), NOW)
        match = [o for o in obs
                 if "CUTOFF_YIELD" in o.imdr_code
                 and o.obs_date == datetime.date(2026, 2, 25)
                 and abs(o.value - 5.2998) < 0.0001]
        assert len(match) == 1

    def test_notified_amount_14000(self):
        _, obs = parse_tbill_auctions_26(_make_t26_rows(), self._target(), NOW)
        match = [o for o in obs
                 if "NOTIFIED_AMT" in o.imdr_code
                 and abs(o.value - 14000) < 0.1]
        assert len(match) >= 1

    def test_accepted_fv_comp_plus_noncomp(self):
        _, obs = parse_tbill_auctions_26(_make_t26_rows(), self._target(), NOW)
        # Feb 25 accepted: 13981 (comp) + 1538 (noncomp) = 15519
        match = [o for o in obs
                 if "ACCEPTED_FV" in o.imdr_code
                 and o.obs_date == datetime.date(2026, 2, 25)
                 and abs(o.value - 15519) < 0.1]
        assert len(match) == 1

    def test_tenor_section_header_not_emitted_as_indicator(self):
        inds, _ = parse_tbill_auctions_26(_make_t26_rows(), self._target(), NOW)
        for ind in inds:
            # The "91-day Treasury Bills" section header must not become an indicator
            assert "TREASURY_BILLS" not in ind.imdr_code or "91D" in ind.imdr_code

    def test_early_fy_month_resolves_to_start_year(self):
        # Regression: an Apr auction in FY 2025-26 must resolve to 2025, NOT
        # 2026. The old "first parseable year" logic wrongly produced 2026.
        rows = [
            ["", "No. 26: Auctions of Treasury Bills"],
            ["", "(Amount in ₹ Crore)"],
            ["", "Date of Auction", "Notified Amount", "Bids Received", "", "",
             "Bids Accepted", "", "", "Total Issue (6+7)", "Cut-off Price (₹)",
             "Implicit Yield at Cut-off Price (per cent)"],
            ["", "", "", "Number", "Total Face Value", "", "Number", "Total Face Value"],
            ["", "", "", "", "Competitive", "Non-Competitive", "",
             "Competitive", "Non-Competitive"],
            ["", "", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10"],
            ["", "91-day Treasury Bills"],
            ["", "2025-26"],
            ["", "Apr. 2", "12000", "100", "30000", "1000", "50", "11000",
             "1000", "12000", "98.8", "5.10"],
        ]
        _, obs = parse_tbill_auctions_26(rows, self._target(), NOW)
        apr = [o for o in obs if "CUTOFF_YIELD" in o.imdr_code]
        assert len(apr) == 1
        assert apr[0].obs_date == datetime.date(2025, 4, 2)


# ---------------------------------------------------------------------------
# parse_fx_intervention_4 — T4 (added 2026-07-14)
# ---------------------------------------------------------------------------
# Fixture trimmed from the live Jul-2026 download
# (playground/econ/in/rbi/_smoke/downloads/T4.xlsx). The user's original ask
# named this table "39"; live discovery confirmed the Bulletin's current
# numbering has "Sale/Purchase of U.S. Dollar by the RBI" at Table No. 4
# (T39 is now split into 39a/39b, unrelated INR-invoicing tables).

def _make_t4_rows() -> list[list[str]]:
    return [
        ["", "No. 4: Sale/ Purchase of U.S. Dollar by the RBI"],
        ["", "i) Operations in onshore / offshore OTC segment"],
        ["", "Item", "2024-25", "2025", "2026"],
        ["", "", "", "Mar.", "Feb.", "Mar."],
        ["", "", "1", "2", "3", "4"],
        ["", "1.\xa0Net Purchase/ Sale of Foreign Currency (US $ Million) (1.1-1.2)",
         "-34511", "14355", "7409", "-9758"],
        ["", "1.1 Purchase (+)", "364200", "41515", "21403", "19880"],
        ["", "1.2 Sale (–)", "398711", "27160", "13994", "29638"],
        ["", "2. ₹ equivalent at contract rate (₹ Crores)",
         "-291233", "124586", "66881", "-89785"],
        ["", "3. Cumulative (over end-March) (US $ Million)",
         "-34511", "-34511", "-43374", "-53132"],
        ["", "(₹ Crore)", "-291233", "-291233", "-379669", "-469454"],
        ["", "4. Outstanding Net Forward Sales (-)/ Purchase (+) at the end of month (US $ Million)",
         "-84345", "-84345", "-77666", "-103064"],
        ["", "ii) Operations in currency futures segment"],
        ["", "Item", "2024-25", "2025", "2026"],
        ["", "", "", "Mar.", "Feb.", "Mar."],
        ["", "", "1", "2", "3", "4"],
        ["", "1.\xa0Net Purchase/ Sale of Foreign Currency (US $ Million) (1.1-1.2)",
         "0", "0", "0", "0"],
        ["", "1.1 Purchase (+)", "31415", "1202", "1405", "3244"],
        ["", "1.2 Sale (–)", "31415", "1202", "1405", "3244"],
        ["", "2. Outstanding Net Currency Futures Sales (-)/ Purchase (+) at the end of month (US $ Million)",
         "0", "0", "-522", "-1401"],
        ["", "Note: Maturity-wise position of outstanding forward contracts is available at "
              "http://nsdp.rbi.org.in under 'Reserves Template'."],
    ]


class TestParseFxIntervention4:
    def _target(self):
        return {
            "name": "fx_intervention_4", "table_num": "4",
            "imdr_prefix": "INDIA.RBI_BULLETIN.FX_INTERVENTION",
            "category": "fx", "frequency": "MONTHLY",
            "description": "T4 test",
        }

    def test_four_indicators(self):
        inds, _ = parse_fx_intervention_4(_make_t4_rows(), self._target(), NOW)
        codes = {i.imdr_code for i in inds}
        assert codes == {
            "INDIA.RBI_BULLETIN.FX_INTERVENTION.PURCHASE.IN",
            "INDIA.RBI_BULLETIN.FX_INTERVENTION.SALE.IN",
            "INDIA.RBI_BULLETIN.FX_INTERVENTION.NET.IN",
            "INDIA.RBI_BULLETIN.FORWARD_BOOK.NET_OUTSTANDING.IN",
        }

    def test_currency_futures_block_excluded(self):
        # Block (ii) values (0/0/0/0 net, 31415 purchase) must NOT leak into
        # the OTC-segment PURCHASE/SALE/NET series.
        _, obs = parse_fx_intervention_4(_make_t4_rows(), self._target(), NOW)
        purchase_vals = {o.value for o in obs if o.imdr_code.endswith("PURCHASE.IN")}
        assert 31415.0 not in purchase_vals
        assert 1202.0 not in purchase_vals

    def test_mar_2026_purchase_19880(self):
        _, obs = parse_fx_intervention_4(_make_t4_rows(), self._target(), NOW)
        match = [o for o in obs if o.imdr_code.endswith("PURCHASE.IN")
                 and o.obs_date == datetime.date(2026, 3, 1)
                 and o.value == pytest.approx(19880)]
        assert len(match) == 1

    def test_mar_2026_sale_29638(self):
        _, obs = parse_fx_intervention_4(_make_t4_rows(), self._target(), NOW)
        match = [o for o in obs if o.imdr_code.endswith("SALE.IN")
                 and o.obs_date == datetime.date(2026, 3, 1)
                 and o.value == pytest.approx(29638)]
        assert len(match) == 1

    def test_mar_2026_net_negative_9758(self):
        _, obs = parse_fx_intervention_4(_make_t4_rows(), self._target(), NOW)
        match = [o for o in obs if o.imdr_code.endswith("FX_INTERVENTION.NET.IN")
                 and o.obs_date == datetime.date(2026, 3, 1)
                 and o.value == pytest.approx(-9758)]
        assert len(match) == 1

    def test_net_outstanding_mar_2026_negative_103064(self):
        _, obs = parse_fx_intervention_4(_make_t4_rows(), self._target(), NOW)
        match = [o for o in obs if o.imdr_code.endswith("FORWARD_BOOK.NET_OUTSTANDING.IN")
                 and o.obs_date == datetime.date(2026, 3, 1)
                 and o.value == pytest.approx(-103064)]
        assert len(match) == 1

    def test_fy_column_dropped_from_flow_series(self):
        # Regression (2026-07-14 code review): the "2024-25" FY-cumulative
        # column must NOT appear in PURCHASE/SALE/NET (MONTHLY flow series) --
        # it's an annual total (364200/398711/-34511 in the fixture), and
        # mixing it with the monthly columns lets a naive SUM/AVG
        # double-count. Only the 3 explicit month columns should survive.
        _, obs = parse_fx_intervention_4(_make_t4_rows(), self._target(), NOW)
        flow_obs = [o for o in obs if "FX_INTERVENTION" in o.imdr_code]
        assert len(flow_obs) == 9  # 3 codes x 3 monthly columns (FY col dropped)
        flow_values = {o.value for o in flow_obs}
        assert 364200.0 not in flow_values
        assert 398711.0 not in flow_values
        assert -34511.0 not in flow_values

    def test_net_outstanding_stock_keeps_fy_column_normalised_to_month_start(self):
        # FORWARD_BOOK.NET_OUTSTANDING is a STOCK/snapshot, not a flow -- the
        # FY column and the "Mar." column describe the SAME period-end
        # balance (identical value in the raw table: -84345), so both must
        # collapse to the same month-start obs_date rather than being
        # silently dropped or left as two near-duplicate dates.
        _, obs = parse_fx_intervention_4(_make_t4_rows(), self._target(), NOW)
        fb_obs = [o for o in obs if o.imdr_code.endswith("NET_OUTSTANDING.IN")]
        dates = [o.obs_date for o in fb_obs]
        assert all(d.day == 1 for d in dates), f"expected all day=1, got {dates}"
        mar_2025 = [o for o in fb_obs if o.obs_date == datetime.date(2025, 3, 1)]
        assert len(mar_2025) == 2  # FY column + explicit "Mar." column, same value
        assert {o.value for o in mar_2025} == {-84345.0}

    def test_all_units_usd_mn(self):
        inds, _ = parse_fx_intervention_4(_make_t4_rows(), self._target(), NOW)
        for ind in inds:
            assert ind.unit == "usd_mn"


# ---------------------------------------------------------------------------
# parse_forward_book_tenor_4a — T4A (added 2026-07-14)
# ---------------------------------------------------------------------------

def _make_t4a_rows() -> list[list[str]]:
    return [
        ["", "No. 4A : Maturity Breakdown (by Residual Maturity) of Outstanding Forwards of RBI (US $ Million)"],
        ["", "Item", "As on April 30, 2026"],
        ["", "", "Long (+)", "Short (-)", "Net (1-2)"],
        ["", "", "1", "2", "3"],
        ["", "1. Upto 1 month", "0", "13525", "-13525"],
        ["", "2. More than 1 month and upto 3 months", "0", "10898", "-10898"],
        ["", "3. More than 3 months and upto 1 year", "0", "20153", "-20153"],
        ["", "4. More than 1 year", "0", "50728", "-50728"],
        ["", "Total (1+2+3+4)", "0", "95304", "-95304"],
    ]


class TestParseForwardBookTenor4a:
    def _target(self):
        return {
            "name": "forward_book_tenor_4a", "table_num": "4A",
            "imdr_prefix": "INDIA.RBI_BULLETIN.FORWARD_BOOK",
            "category": "fx", "frequency": "MONTHLY",
            "description": "T4A test",
        }

    def test_five_indicators(self):
        inds, _ = parse_forward_book_tenor_4a(_make_t4a_rows(), self._target(), NOW)
        codes = {i.imdr_code for i in inds}
        assert codes == {
            "INDIA.RBI_BULLETIN.FORWARD_BOOK.UPTO_1M.IN",
            "INDIA.RBI_BULLETIN.FORWARD_BOOK.1_3M.IN",
            "INDIA.RBI_BULLETIN.FORWARD_BOOK.3M_1Y.IN",
            "INDIA.RBI_BULLETIN.FORWARD_BOOK.OVER_1Y.IN",
            "INDIA.RBI_BULLETIN.FORWARD_BOOK.NET_OUTSTANDING.IN",
        }

    def test_tenor_buckets_use_literal_as_on_date(self):
        _, obs = parse_forward_book_tenor_4a(_make_t4a_rows(), self._target(), NOW)
        bucket_dates = {o.obs_date for o in obs if not o.imdr_code.endswith("NET_OUTSTANDING.IN")}
        assert bucket_dates == {datetime.date(2026, 4, 30)}

    def test_net_outstanding_normalised_to_month_start(self):
        # Regression (2026-07-14 code review): NET_OUTSTANDING must NOT use
        # the literal "as on" day (30) -- it needs to collide with T4's own
        # NET_OUTSTANDING column for the same month (which resolves to
        # day=1), or the two tables produce two near-duplicate rows per
        # month for the same series.
        _, obs = parse_forward_book_tenor_4a(_make_t4a_rows(), self._target(), NOW)
        net_outstanding = [o for o in obs if o.imdr_code.endswith("NET_OUTSTANDING.IN")]
        assert len(net_outstanding) == 1
        assert net_outstanding[0].obs_date == datetime.date(2026, 4, 1)

    def test_net_values_are_signed_short(self):
        # Net column values are already signed (Long - Short); RBI has a net
        # short forward-dollar book across every bucket in this fixture.
        _, obs = parse_forward_book_tenor_4a(_make_t4a_rows(), self._target(), NOW)
        by_code = {o.imdr_code: o.value for o in obs}
        assert by_code["INDIA.RBI_BULLETIN.FORWARD_BOOK.UPTO_1M.IN"] == pytest.approx(-13525)
        assert by_code["INDIA.RBI_BULLETIN.FORWARD_BOOK.1_3M.IN"] == pytest.approx(-10898)
        assert by_code["INDIA.RBI_BULLETIN.FORWARD_BOOK.3M_1Y.IN"] == pytest.approx(-20153)
        assert by_code["INDIA.RBI_BULLETIN.FORWARD_BOOK.OVER_1Y.IN"] == pytest.approx(-50728)

    def test_total_maps_to_net_outstanding_and_sums_buckets(self):
        _, obs = parse_forward_book_tenor_4a(_make_t4a_rows(), self._target(), NOW)
        by_code = {o.imdr_code: o.value for o in obs}
        total = by_code["INDIA.RBI_BULLETIN.FORWARD_BOOK.NET_OUTSTANDING.IN"]
        assert total == pytest.approx(-95304)
        buckets = (
            by_code["INDIA.RBI_BULLETIN.FORWARD_BOOK.UPTO_1M.IN"]
            + by_code["INDIA.RBI_BULLETIN.FORWARD_BOOK.1_3M.IN"]
            + by_code["INDIA.RBI_BULLETIN.FORWARD_BOOK.3M_1Y.IN"]
            + by_code["INDIA.RBI_BULLETIN.FORWARD_BOOK.OVER_1Y.IN"]
        )
        assert buckets == pytest.approx(total)

    def test_all_units_usd_mn(self):
        inds, _ = parse_forward_book_tenor_4a(_make_t4a_rows(), self._target(), NOW)
        for ind in inds:
            assert ind.unit == "usd_mn"

    def test_net_column_resolved_dynamically_not_hardcoded(self):
        # If Long/Short/Net get reordered (or a column inserted), a hard-coded
        # index would silently read the wrong column. Insert a spare column
        # after "Long (+)" and confirm Net is still picked up correctly by
        # its own sub-header label, not by position.
        rows = [
            ["", "No. 4A test with a reordered column"],
            ["", "Item", "As on April 30, 2026"],
            ["", "", "Long (+)", "Spare", "Short (-)", "Net (1-2)"],
            ["", "", "1", "1a", "2", "3"],
            ["", "1. Upto 1 month", "0", "999", "13525", "-13525"],
        ]
        _, obs = parse_forward_book_tenor_4a(rows, self._target(), NOW)
        match = [o for o in obs if o.imdr_code.endswith("UPTO_1M.IN")]
        assert len(match) == 1
        assert match[0].value == pytest.approx(-13525)  # not 999 (the spare col)

    def test_no_net_subheader_returns_empty_not_wrong_column(self):
        # Sub-header shape changed beyond recognition (no "Net" token at
        # all) -- must fail loudly (empty result), not guess a column.
        rows = [
            ["", "No. 4A test with unrecognisable sub-header"],
            ["", "Item", "As on April 30, 2026"],
            ["", "", "Buy", "Sell", "Balance"],
            ["", "", "1", "2", "3"],
            ["", "1. Upto 1 month", "0", "13525", "-13525"],
        ]
        inds, obs = parse_forward_book_tenor_4a(rows, self._target(), NOW)
        assert inds == []
        assert obs == []


class TestT4T4ADedupInteraction:
    """The interaction the MUST-FIX bugs (2026-07-14 code review) lived in:
    T4 and T4A both emit FORWARD_BOOK.NET_OUTSTANDING for overlapping
    months, and run_fetch's final step dedups on the fact PK
    (imdr_code, obs_date, vintage). Before the fix, T4 normalised its
    NET_OUTSTANDING dates to month-start while T4A used the literal "as on"
    day -- so the same month's value landed as TWO rows instead of
    colliding into one.
    """

    def _dedup(self, *obs_lists):
        deduped: dict[tuple, object] = {}
        for obs in obs_lists:
            for o in obs:
                deduped[(o.imdr_code, o.obs_date, o.vintage)] = o
        return list(deduped.values())

    def test_exactly_one_net_outstanding_obs_per_month(self):
        _, obs4 = parse_fx_intervention_4(_make_t4_rows(), {
            "name": "fx_intervention_4", "table_num": "4",
            "imdr_prefix": "INDIA.RBI_BULLETIN.FX_INTERVENTION",
            "category": "fx", "frequency": "MONTHLY", "description": "T4 test",
        }, NOW)
        _, obs4a = parse_forward_book_tenor_4a(_make_t4a_rows(), {
            "name": "forward_book_tenor_4a", "table_num": "4A",
            "imdr_prefix": "INDIA.RBI_BULLETIN.FORWARD_BOOK",
            "category": "fx", "frequency": "MONTHLY", "description": "T4A test",
        }, NOW)
        deduped = self._dedup(obs4, obs4a)
        net_outstanding = [o for o in deduped if o.imdr_code.endswith("NET_OUTSTANDING.IN")]
        dates = [o.obs_date for o in net_outstanding]
        assert len(dates) == len(set(dates)), (
            f"duplicate obs_date(s) in NET_OUTSTANDING after dedup: {dates}"
        )
        # T4's fixture months (2025-03, 2026-02, 2026-03) + T4A's month
        # (2026-04, normalised from "As on April 30" to day=1) -- 4 distinct
        # months, exactly 4 rows, none doubled.
        assert sorted(dates) == [
            datetime.date(2025, 3, 1),
            datetime.date(2026, 2, 1),
            datetime.date(2026, 3, 1),
            datetime.date(2026, 4, 1),
        ]


class TestIndexDiscovery:
    """Guard the bulletin index URL matching against RBI filename changes.

    2026-07 regression: RBI dropped the 'BULL' token from XLSX filenames
    (34T_BULL22052026....XLSX -> 34T_22062026....XLSX). The old regex required
    'BULL', so _map_anchors_to_tables returned {} and the ENTIRE bulletin loaded
    0 rows silently. These tests exercise both the current and legacy filename
    forms so a future change fails here, not in prod.
    """

    _BASE = "https://website.rbi.org.in/documents/rdocs/Bulletin/DOCs/"

    def _anchor(self, fname):
        return {"href": self._BASE + fname, "text": ""}

    def test_current_filenames_no_bull_token(self):
        anchors = [
            self._anchor("34T_22062026ABCD.XLSX"),
            self._anchor("4T_22062026ABCD.XLSX"),
            self._anchor("4AT_22062026ABCD.XLSX"),
            self._anchor("19CT_22062026ABCD.XLSX"),
        ]
        m = _rbi._map_anchors_to_tables(anchors)
        assert m.keys() >= {"34", "4", "4A", "19C"}

    def test_legacy_bull_filenames_still_match(self):
        anchors = [self._anchor("34T_BULL22052026ABCD.XLSX")]
        m = _rbi._map_anchors_to_tables(anchors)
        assert "34" in m

    def test_aug_2026_bul_token_matches(self):
        """Third spelling: the token came BACK, as three letters not four.

        `1T_BUL25082026....XLSX`. The 2026-07 fix made the literal 'BULL'
        optional, which still missed 'BUL' -- so every table silently
        stopped resolving from the August issue onward. Found 2026-09-15:
        `data/econ/in/rbi/bulletin/` stopped at 2026-08-25 (the August
        bulletin date) while every other India fetcher kept producing.
        Five scheduled runs lost over three weeks, nothing alerted.
        """
        anchors = [
            self._anchor("1T_BUL2508202622735BAE809B471E.XLSX"),
            self._anchor("4AT_BUL2508202696FC7CB2197C48.XLSX"),
            self._anchor("19CT_BUL25082026ABCD.XLSX"),
        ]
        m = _rbi._map_anchors_to_tables(anchors)
        assert m.keys() >= {"1", "4A", "19C"}

    def test_an_unseen_future_token_still_matches(self):
        """Match ANY alphabetic token rather than enumerate known ones.

        Three outages have come from this one field. A fourth spelling
        must not cost a fourth.
        """
        for token in ("", "BUL", "BULL", "BULLETIN", "B"):
            anchors = [self._anchor(f"34T_{token}22062026ABCD.XLSX")]
            assert "34" in _rbi._map_anchors_to_tables(anchors), token

    def test_non_bulletin_and_non_xlsx_ignored(self):
        anchors = [
            {"href": "https://website.rbi.org.in/some/other/notification.pdf", "text": ""},
            {"href": self._BASE + "readme.txt", "text": ""},
            self._anchor("34T_22062026ABCD.XLSX"),
        ]
        m = _rbi._map_anchors_to_tables(anchors)
        assert list(m.keys()) == ["34"]

    def test_empty_result_is_detectable(self):
        # a filename form that matches NOTHING must yield {} (the prod caller
        # treats {} as "index broken" -> all targets skip)
        assert _rbi._map_anchors_to_tables([{"href": "x/UNRELATED.XLSX", "text": ""}]) == {}
