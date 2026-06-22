"""Tests for scripts/econ/in/ogd/ogd_food_mom.py.

Network-free and DB-free. The DB read is mocked via a patch on the
module-level _read_weekly_medians function, which is loaded via importlib
to avoid the `in` keyword in the dotted import path.

Exercises:
  - MoM math (current vs prior month mean; pin a value)
  - Month bucketing (weekly obs_date → calendar month)
  - Both-months-required (commodity with only current-month data is skipped)
  - Composite weighting (known MoMs → assert exact CPI-weighted composite;
    verify renormalisation when a sub-group is absent)
  - Tier filter (Tier-C commodity gets MoM_PCT row but NOT in the composite)
  - imdr_code construction (pin VEG/FRUIT/SPICE examples + composite codes)
"""
from __future__ import annotations

import datetime
import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Load the module via importlib (avoids `in` keyword in dotted import path)
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]
_MOD_PATH = _REPO_ROOT / "scripts" / "econ" / "in" / "ogd" / "ogd_food_mom.py"

_spec = importlib.util.spec_from_file_location("ogd_food_mom", _MOD_PATH)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["ogd_food_mom"] = _mod
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]

run_fetch = _mod.run_fetch
_parse_imdr_code = _mod._parse_imdr_code
_slug_to_canonical = _mod._slug_to_canonical
_month_start = _mod._month_start
_prior_month = _mod._prior_month

_PATCH_PREFIX = "ogd_food_mom"

UTC = datetime.timezone.utc


# ---------------------------------------------------------------------------
# Helpers to build synthetic series
# ---------------------------------------------------------------------------

def _make_series(
    commodity: str,
    subgroup: str,   # "vegetables" / "fruits" / "spices"
    tier: str,       # "A" / "B" / "C"
    dates_values: list[tuple[datetime.date, float]],
) -> tuple[str, list[tuple[datetime.date, float]]]:
    """Return (imdr_code, [(obs_date, value)]) matching the P1 naming convention."""
    from imdr.domains.econ.upag import slug as _slug
    _SUBGROUP_PREFIX = {"vegetables": "VEG", "fruits": "FRUIT", "spices": "SPICE"}
    sub_prefix = _SUBGROUP_PREFIX[subgroup]
    commodity_slug = _slug(commodity)
    imdr_code = f"INDIA.FOODNOWCAST.{sub_prefix}.{commodity_slug}.MEDIAN_WK.NATL.IN"
    return imdr_code, dates_values


def _run_with_series(
    series_dict: dict[str, list[tuple[datetime.date, float]]],
    until: str,
) -> tuple[list, list]:
    """Run run_fetch with mocked DB read and _engine."""
    mock_engine = MagicMock()
    with (
        patch(f"{_PATCH_PREFIX}._engine", return_value=mock_engine),
        patch(f"{_PATCH_PREFIX}._read_weekly_medians", return_value=series_dict),
    ):
        return run_fetch(None, until)


# ---------------------------------------------------------------------------
# _parse_imdr_code
# ---------------------------------------------------------------------------

class TestParseImdrCode:
    def test_valid_veg(self) -> None:
        result = _parse_imdr_code("INDIA.FOODNOWCAST.VEG.TOMATO.MEDIAN_WK.NATL.IN")
        assert result == ("TOMATO", "VEG")

    def test_valid_fruit(self) -> None:
        result = _parse_imdr_code("INDIA.FOODNOWCAST.FRUIT.BANANA.MEDIAN_WK.NATL.IN")
        assert result == ("BANANA", "FRUIT")

    def test_valid_spice(self) -> None:
        result = _parse_imdr_code("INDIA.FOODNOWCAST.SPICE.GARLIC.MEDIAN_WK.NATL.IN")
        assert result == ("GARLIC", "SPICE")

    def test_wrong_metric_returns_none(self) -> None:
        # MOM_PCT code should not parse as a MEDIAN_WK input
        result = _parse_imdr_code("INDIA.FOODNOWCAST.VEG.TOMATO.MOM_PCT.NATL.IN")
        assert result is None

    def test_too_few_parts_returns_none(self) -> None:
        result = _parse_imdr_code("INDIA.FOODNOWCAST.VEG.TOMATO")
        assert result is None


# ---------------------------------------------------------------------------
# _prior_month
# ---------------------------------------------------------------------------

class TestPriorMonth:
    def test_jan_wraps_to_dec_prior_year(self) -> None:
        assert _prior_month(2026, 1) == (2025, 12)

    def test_june_to_may(self) -> None:
        assert _prior_month(2026, 6) == (2026, 5)

    def test_dec_to_nov(self) -> None:
        assert _prior_month(2026, 12) == (2026, 11)


# ---------------------------------------------------------------------------
# MoM math — pin exact value
# ---------------------------------------------------------------------------

class TestMoMMath:
    """MoM = (mean_cur / mean_pri - 1) * 100."""

    def test_pinned_mom_value(self) -> None:
        # Tomato: prior month 3 weeks at 1000, 1100, 1200 → mean = 1100
        #         current month 2 weeks at 1300, 1500 → mean = 1400
        # MoM = (1400/1100 - 1)*100 = 27.272...%
        prior_dates = [
            datetime.date(2026, 4, 6),   # week 15 Mon
            datetime.date(2026, 4, 13),  # week 16 Mon
            datetime.date(2026, 4, 20),  # week 17 Mon
        ]
        cur_dates = [
            datetime.date(2026, 5, 4),   # week 19 Mon
            datetime.date(2026, 5, 11),  # week 20 Mon
        ]
        code, pts = _make_series(
            "Tomato", "vegetables", "A",
            list(zip(prior_dates, [1000.0, 1100.0, 1200.0]))
            + list(zip(cur_dates, [1300.0, 1500.0])),
        )
        inds, obs = _run_with_series({code: pts}, until="2026-05-15")

        # Expect a MoM_PCT observation for Tomato
        tomato_mom_obs = [
            o for o in obs
            if "TOMATO" in o.imdr_code and "MOM_PCT" in o.imdr_code
        ]
        assert len(tomato_mom_obs) == 1
        expected = (1400.0 / 1100.0 - 1) * 100
        assert tomato_mom_obs[0].value == pytest.approx(expected, rel=1e-6)

    def test_equal_months_mom_is_zero(self) -> None:
        dates_pri = [datetime.date(2026, 4, 6), datetime.date(2026, 4, 13)]
        dates_cur = [datetime.date(2026, 5, 4), datetime.date(2026, 5, 11)]
        code, pts = _make_series(
            "Onion", "vegetables", "A",
            list(zip(dates_pri, [1500.0, 1500.0]))
            + list(zip(dates_cur, [1500.0, 1500.0])),
        )
        inds, obs = _run_with_series({code: pts}, until="2026-05-15")
        onion_mom = [o for o in obs if "ONION" in o.imdr_code and "MOM_PCT" in o.imdr_code]
        assert len(onion_mom) == 1
        assert onion_mom[0].value == pytest.approx(0.0, abs=1e-10)


# ---------------------------------------------------------------------------
# Month bucketing
# ---------------------------------------------------------------------------

class TestMonthBucketing:
    """Obs_dates in different calendar months must land in the correct bucket."""

    def test_obs_date_month_boundary(self) -> None:
        # One obs at 2026-04-27 (April) and one at 2026-05-04 (May).
        # Running until=2026-05-15 → current=May, prior=April.
        # Both months present → computable.
        code, pts = _make_series(
            "Potato", "vegetables", "A",
            [
                (datetime.date(2026, 4, 27), 800.0),
                (datetime.date(2026, 5, 4), 900.0),
            ],
        )
        inds, obs = _run_with_series({code: pts}, until="2026-05-15")
        potato_mom = [o for o in obs if "POTATO" in o.imdr_code and "MOM_PCT" in o.imdr_code]
        assert len(potato_mom) == 1
        # MoM = (900/800 - 1)*100 = 12.5%
        assert potato_mom[0].value == pytest.approx(12.5, rel=1e-6)

    def test_obs_date_is_month_start(self) -> None:
        # The emitted obs_date for the MoM indicator should be the first of current month.
        code, pts = _make_series(
            "Garlic", "spices", "A",
            [
                (datetime.date(2026, 4, 13), 10000.0),
                (datetime.date(2026, 5, 11), 11000.0),
            ],
        )
        inds, obs = _run_with_series({code: pts}, until="2026-05-20")
        garlic_mom = [o for o in obs if "GARLIC" in o.imdr_code and "MOM_PCT" in o.imdr_code]
        assert len(garlic_mom) == 1
        assert garlic_mom[0].obs_date == datetime.date(2026, 5, 1)


# ---------------------------------------------------------------------------
# Both-months-required
# ---------------------------------------------------------------------------

class TestBothMonthsRequired:
    """A commodity with only current-month data must be skipped."""

    def test_missing_prior_month_skipped(self) -> None:
        # Only May data — no April data.
        code, pts = _make_series(
            "Banana", "fruits", "A",
            [
                (datetime.date(2026, 5, 4), 2000.0),
                (datetime.date(2026, 5, 11), 2100.0),
            ],
        )
        inds, obs = _run_with_series({code: pts}, until="2026-05-15")
        banana_mom = [o for o in obs if "BANANA" in o.imdr_code and "MOM_PCT" in o.imdr_code]
        assert len(banana_mom) == 0

    def test_missing_current_month_skipped(self) -> None:
        # Only April data — no May data.
        code, pts = _make_series(
            "Mango", "fruits", "A",
            [
                (datetime.date(2026, 4, 6), 3000.0),
                (datetime.date(2026, 4, 13), 3100.0),
            ],
        )
        inds, obs = _run_with_series({code: pts}, until="2026-05-15")
        mango_mom = [o for o in obs if "MANGO" in o.imdr_code and "MOM_PCT" in o.imdr_code]
        assert len(mango_mom) == 0

    def test_both_months_present_emitted(self) -> None:
        code, pts = _make_series(
            "Tomato", "vegetables", "A",
            [
                (datetime.date(2026, 4, 13), 1500.0),
                (datetime.date(2026, 5, 11), 1800.0),
            ],
        )
        inds, obs = _run_with_series({code: pts}, until="2026-05-15")
        tomato_mom = [o for o in obs if "TOMATO" in o.imdr_code and "MOM_PCT" in o.imdr_code]
        assert len(tomato_mom) == 1


# ---------------------------------------------------------------------------
# Composite weighting
# ---------------------------------------------------------------------------

class TestCompositeWeighting:
    """CPI-weighted composite = Σ w_i × sub_mom_i / Σ w_i."""

    def _build_subgroup_series(
        self,
        veg_mom: float,
        fruit_mom: float,
        spice_mom: float,
        *,
        pri_val: float = 1000.0,
    ) -> dict[str, list[tuple[datetime.date, float]]]:
        """Build synthetic series producing known per-sub-group MoMs.

        Uses a single Tier-A commodity per sub-group to avoid median-of-median
        complexity in this test (median of 1 value = that value).
        prior price = pri_val; current price = pri_val * (1 + mom/100).
        """
        pri_date = datetime.date(2026, 4, 13)
        cur_date = datetime.date(2026, 5, 11)

        def _series(commodity, subgroup):
            mom = {"vegetables": veg_mom, "fruits": fruit_mom, "spices": spice_mom}[subgroup]
            cur_val = pri_val * (1 + mom / 100)
            code, pts = _make_series(
                commodity, subgroup, "A",
                [(pri_date, pri_val), (cur_date, cur_val)],
            )
            return code, pts

        d = {}
        veg_code, veg_pts = _series("Tomato", "vegetables")
        d[veg_code] = veg_pts
        fruit_code, fruit_pts = _series("Banana", "fruits")
        d[fruit_code] = fruit_pts
        spice_code, spice_pts = _series("Garlic", "spices")
        d[spice_code] = spice_pts
        return d

    def test_cpi_weighted_composite_exact(self) -> None:
        # veg MoM = +10%, fruit MoM = +5%, spice MoM = +2%
        # CPI weights: veg=6.04, fruit=2.89, spice=2.50 → sum=11.43
        # composite = (10*6.04 + 5*2.89 + 2*2.50) / 11.43
        # = (60.4 + 14.45 + 5.0) / 11.43 = 79.85 / 11.43 ≈ 6.9859...
        series = self._build_subgroup_series(10.0, 5.0, 2.0)
        inds, obs = _run_with_series(series, until="2026-05-15")

        headline = [o for o in obs if o.imdr_code == "INDIA.FOODNOWCAST.PERISHABLE.MOM_NOWCAST.NATL.IN"]
        assert len(headline) == 1

        expected = (10.0 * 6.04 + 5.0 * 2.89 + 2.0 * 2.50) / (6.04 + 2.89 + 2.50)
        assert headline[0].value == pytest.approx(expected, rel=1e-6)

    def test_renormalisation_when_subgroup_absent(self) -> None:
        # Only vegetables and fruits — spices missing (no prior-month data).
        # Renormalised weights: veg=6.04, fruit=2.89 → sum=8.93
        # composite = (10*6.04 + 5*2.89) / (6.04+2.89)
        pri_date = datetime.date(2026, 4, 13)
        cur_date = datetime.date(2026, 5, 11)

        veg_code, veg_pts = _make_series(
            "Tomato", "vegetables", "A",
            [(pri_date, 1000.0), (cur_date, 1100.0)],   # +10%
        )
        fruit_code, fruit_pts = _make_series(
            "Banana", "fruits", "A",
            [(pri_date, 2000.0), (cur_date, 2100.0)],   # +5%
        )
        # Garlic only has current-month data → skipped (no spice composite)
        spice_code, spice_pts = _make_series(
            "Garlic", "spices", "A",
            [(cur_date, 8000.0)],
        )

        series = {veg_code: veg_pts, fruit_code: fruit_pts, spice_code: spice_pts}
        inds, obs = _run_with_series(series, until="2026-05-15")

        headline = [o for o in obs if o.imdr_code == "INDIA.FOODNOWCAST.PERISHABLE.MOM_NOWCAST.NATL.IN"]
        assert len(headline) == 1

        veg_mom = (1100.0 / 1000.0 - 1) * 100   # 10.0
        fruit_mom = (2100.0 / 2000.0 - 1) * 100  # 5.0
        expected = (veg_mom * 6.04 + fruit_mom * 2.89) / (6.04 + 2.89)
        assert headline[0].value == pytest.approx(expected, rel=1e-6)

    def test_sub_group_composites_emitted(self) -> None:
        series = self._build_subgroup_series(10.0, 5.0, 2.0)
        inds, obs = _run_with_series(series, until="2026-05-15")

        sg_codes = {o.imdr_code for o in obs}
        assert "INDIA.FOODNOWCAST.VEG.COMPOSITE.MOM_PCT.NATL.IN" in sg_codes
        assert "INDIA.FOODNOWCAST.FRUIT.COMPOSITE.MOM_PCT.NATL.IN" in sg_codes
        assert "INDIA.FOODNOWCAST.SPICE.COMPOSITE.MOM_PCT.NATL.IN" in sg_codes


# ---------------------------------------------------------------------------
# Tier filter — Tier C gets MoM_PCT but is NOT in the composite
# ---------------------------------------------------------------------------

class TestTierFilter:
    """Tier-C commodities emit a MoM_PCT row but do not enter the sub-group composite."""

    def test_tier_c_excluded_from_composite(self) -> None:
        # Green Peas is Tier C (vegetables).
        # Tomato is Tier A (vegetables).
        # Sub-group composite should reflect only Tomato (tier A).
        pri = datetime.date(2026, 4, 13)
        cur = datetime.date(2026, 5, 11)

        # Tomato (tier A): pri=1000, cur=1200 → MoM = +20%
        tomato_code, tomato_pts = _make_series(
            "Tomato", "vegetables", "A",
            [(pri, 1000.0), (cur, 1200.0)],
        )
        # Green Peas (tier C): pri=500, cur=700 → MoM = +40%
        peas_code, peas_pts = _make_series(
            "Green Peas", "vegetables", "C",
            [(pri, 500.0), (cur, 700.0)],
        )

        series = {tomato_code: tomato_pts, peas_code: peas_pts}
        inds, obs = _run_with_series(series, until="2026-05-15")

        # Green Peas must have a MoM_PCT observation (Tier C gets its own row)
        peas_mom = [
            o for o in obs
            if "GREEN_PEAS" in o.imdr_code and "MOM_PCT" in o.imdr_code
        ]
        assert len(peas_mom) == 1
        assert peas_mom[0].value == pytest.approx(40.0, rel=1e-4)

        # Sub-group composite should be median of [20.0] = 20.0 (Tomato only)
        veg_composite = [
            o for o in obs
            if o.imdr_code == "INDIA.FOODNOWCAST.VEG.COMPOSITE.MOM_PCT.NATL.IN"
        ]
        assert len(veg_composite) == 1
        assert veg_composite[0].value == pytest.approx(20.0, rel=1e-4)

    def test_tier_b_included_in_composite(self) -> None:
        # Tier B commodity DOES enter the composite.
        pri = datetime.date(2026, 4, 13)
        cur = datetime.date(2026, 5, 11)

        # Colacasia is Tier B vegetables: pri=300, cur=360 → +20%
        cola_code, cola_pts = _make_series(
            "Colacasia", "vegetables", "B",
            [(pri, 300.0), (cur, 360.0)],
        )
        series = {cola_code: cola_pts}
        inds, obs = _run_with_series(series, until="2026-05-15")

        veg_composite = [
            o for o in obs
            if o.imdr_code == "INDIA.FOODNOWCAST.VEG.COMPOSITE.MOM_PCT.NATL.IN"
        ]
        assert len(veg_composite) == 1
        assert veg_composite[0].value == pytest.approx(20.0, rel=1e-4)


# ---------------------------------------------------------------------------
# imdr_code construction — pin exact strings
# ---------------------------------------------------------------------------

class TestImdrCodeConstruction:
    def _run_single(self, commodity: str, subgroup: str, tier: str) -> tuple[list, list]:
        pri = datetime.date(2026, 4, 13)
        cur = datetime.date(2026, 5, 11)
        code, pts = _make_series(commodity, subgroup, tier, [(pri, 1000.0), (cur, 1100.0)])
        return _run_with_series({code: pts}, until="2026-05-15")

    def test_veg_imdr_code(self) -> None:
        inds, obs = self._run_single("Tomato", "vegetables", "A")
        codes = {o.imdr_code for o in obs}
        assert "INDIA.FOODNOWCAST.VEG.TOMATO.MOM_PCT.NATL.IN" in codes

    def test_fruit_imdr_code(self) -> None:
        inds, obs = self._run_single("Banana", "fruits", "A")
        codes = {o.imdr_code for o in obs}
        assert "INDIA.FOODNOWCAST.FRUIT.BANANA.MOM_PCT.NATL.IN" in codes

    def test_spice_imdr_code(self) -> None:
        inds, obs = self._run_single("Garlic", "spices", "A")
        codes = {o.imdr_code for o in obs}
        assert "INDIA.FOODNOWCAST.SPICE.GARLIC.MOM_PCT.NATL.IN" in codes

    def test_headline_composite_code(self) -> None:
        # Need all three sub-groups present to get the headline.
        pri = datetime.date(2026, 4, 13)
        cur = datetime.date(2026, 5, 11)
        series = {}
        for comm, sg in [("Tomato", "vegetables"), ("Banana", "fruits"), ("Garlic", "spices")]:
            code, pts = _make_series(comm, sg, "A", [(pri, 1000.0), (cur, 1100.0)])
            series[code] = pts
        inds, obs = _run_with_series(series, until="2026-05-15")
        codes = {o.imdr_code for o in obs}
        assert "INDIA.FOODNOWCAST.PERISHABLE.MOM_NOWCAST.NATL.IN" in codes

    def test_sub_composite_codes(self) -> None:
        pri = datetime.date(2026, 4, 13)
        cur = datetime.date(2026, 5, 11)
        series = {}
        for comm, sg in [("Tomato", "vegetables"), ("Banana", "fruits"), ("Garlic", "spices")]:
            code, pts = _make_series(comm, sg, "A", [(pri, 1000.0), (cur, 1100.0)])
            series[code] = pts
        inds, obs = _run_with_series(series, until="2026-05-15")
        codes = {o.imdr_code for o in obs}
        assert "INDIA.FOODNOWCAST.VEG.COMPOSITE.MOM_PCT.NATL.IN" in codes
        assert "INDIA.FOODNOWCAST.FRUIT.COMPOSITE.MOM_PCT.NATL.IN" in codes
        assert "INDIA.FOODNOWCAST.SPICE.COMPOSITE.MOM_PCT.NATL.IN" in codes

    def test_complex_slug_veg(self) -> None:
        pri = datetime.date(2026, 4, 13)
        cur = datetime.date(2026, 5, 11)
        code, pts = _make_series("Bhindi(Ladies Finger)", "vegetables", "A",
                                 [(pri, 1500.0), (cur, 1600.0)])
        inds, obs = _run_with_series({code: pts}, until="2026-05-15")
        codes = {o.imdr_code for o in obs}
        assert "INDIA.FOODNOWCAST.VEG.BHINDI_LADIES_FINGER.MOM_PCT.NATL.IN" in codes


# ---------------------------------------------------------------------------
# Composite sub-group median — multiple constituents
# ---------------------------------------------------------------------------

class TestSubGroupMedian:
    """Sub-group composite = MEDIAN of constituent MoMs."""

    def test_median_of_three_constituents(self) -> None:
        # Three vegetables with MoMs = +5%, +10%, +20%
        # Median = 10%
        pri = datetime.date(2026, 4, 13)
        cur = datetime.date(2026, 5, 11)
        series = {}
        for comm, pri_val, cur_val in [
            ("Tomato", 1000.0, 1050.0),    # +5%
            ("Onion", 1000.0, 1100.0),     # +10%
            ("Potato", 1000.0, 1200.0),    # +20%
        ]:
            code, pts = _make_series(comm, "vegetables", "A",
                                     [(pri, pri_val), (cur, cur_val)])
            series[code] = pts

        inds, obs = _run_with_series(series, until="2026-05-15")
        veg_composite = [
            o for o in obs
            if o.imdr_code == "INDIA.FOODNOWCAST.VEG.COMPOSITE.MOM_PCT.NATL.IN"
        ]
        assert len(veg_composite) == 1
        assert veg_composite[0].value == pytest.approx(10.0, rel=1e-4)

    def test_even_constituent_median(self) -> None:
        # Four vegetables: +5%, +10%, +15%, +20% → median = (10+15)/2 = 12.5%
        pri = datetime.date(2026, 4, 13)
        cur = datetime.date(2026, 5, 11)
        series = {}
        vals = [(1000.0, 1050.0), (1000.0, 1100.0), (1000.0, 1150.0), (1000.0, 1200.0)]
        comms = ["Tomato", "Onion", "Potato", "Brinjal"]
        for comm, (p, c) in zip(comms, vals):
            code, pts = _make_series(comm, "vegetables", "A", [(pri, p), (cur, c)])
            series[code] = pts

        inds, obs = _run_with_series(series, until="2026-05-15")
        veg_composite = [
            o for o in obs
            if o.imdr_code == "INDIA.FOODNOWCAST.VEG.COMPOSITE.MOM_PCT.NATL.IN"
        ]
        assert len(veg_composite) == 1
        assert veg_composite[0].value == pytest.approx(12.5, rel=1e-4)


# ---------------------------------------------------------------------------
# No headline composite when all commodities are skipped
# ---------------------------------------------------------------------------

class TestNoHeadlineWhenAllSkipped:
    def test_no_headline_when_prior_month_missing_for_all(self) -> None:
        # All commodities only have current-month data → all skipped → no composite.
        cur = datetime.date(2026, 5, 11)
        series = {}
        for comm, sg in [("Tomato", "vegetables"), ("Banana", "fruits"), ("Garlic", "spices")]:
            code, pts = _make_series(comm, sg, "A", [(cur, 1000.0)])
            series[code] = pts

        inds, obs = _run_with_series(series, until="2026-05-15")
        headline = [o for o in obs if "MOM_NOWCAST" in o.imdr_code]
        assert len(headline) == 0
        assert len(obs) == 0

    def test_empty_series_returns_no_obs(self) -> None:
        inds, obs = _run_with_series({}, until="2026-05-15")
        assert len(obs) == 0
        assert len(inds) == 0
