"""Unit tests for the ASX RBA Rate Tracker parser / row builder.

No network: ``build_rows`` is exercised by monkeypatching ``_get_json``
with captured fixture payloads (real shape from asx.com.au, 2026-06-11).
"""

from __future__ import annotations

import datetime as dt

import pytest

from imdr.domains.econ import asx_rate_tracker as mod
from imdr.domains.econ.asx_rate_tracker import (
    _add_months,
    _expiry_anchor,
    _interp,
    build_rows,
    parse_yield_curve,
)

# --- Fixtures: real payload shape, trimmed ---------------------------------

_YIELD_CURVE = {
    "Crnt_Stlmnt_Dt": "2026-06-11",
    "RBA_Trgt_Cash_Rate": 4.35,
    "months": [
        {"Expiry_Month": "Jun-26", "Implied_Yield": 4.35},
        {"Expiry_Month": "Jul-26", "Implied_Yield": 4.35},
        {"Expiry_Month": "Aug-26", "Implied_Yield": 4.4},
        {"Expiry_Month": "Sep-26", "Implied_Yield": 4.44},
        {"Expiry_Month": "Oct-26", "Implied_Yield": 4.445},
        {"Expiry_Month": "Nov-26", "Implied_Yield": 4.485},
        {"Expiry_Month": "Dec-26", "Implied_Yield": 4.5},
        {"Expiry_Month": "Jun-27", "Implied_Yield": 4.47},
    ],
}

_MARKET_EXP = {
    "Ftre_Cash_Rate": 4.1,
    "Ftre_Cash_Rate_Change": -0.25,
    "days": [
        {"Stlmnt_Dt": "2026-06-11", "Prob_No_Change": 100, "Prob_Change": 0},
        {"Stlmnt_Dt": "2026-06-10", "Prob_No_Change": 80, "Prob_Change": 20},
    ],
}


@pytest.fixture
def _patched(monkeypatch):
    def fake_get_json(name, *, client=None):
        if name == "yield_curve.csv":
            return _YIELD_CURVE
        if name == "market_exp.csv":
            return _MARKET_EXP
        raise AssertionError(f"unexpected fetch: {name}")

    monkeypatch.setattr(mod, "_get_json", fake_get_json)


# --- Date helpers -----------------------------------------------------------

def test_expiry_anchor_maps_to_month_15th():
    assert _expiry_anchor("Jun-26") == dt.date(2026, 6, 15)
    assert _expiry_anchor("Jan-27") == dt.date(2027, 1, 15)


def test_add_months_rolls_year():
    assert _add_months(dt.date(2026, 11, 11), 3) == dt.date(2027, 2, 11)


def test_add_months_clamps_day_to_28():
    assert _add_months(dt.date(2026, 1, 31), 1) == dt.date(2026, 2, 28)


# --- Interpolation ----------------------------------------------------------

def test_interp_at_anchor_returns_exact():
    curve = [(dt.date(2026, 6, 15), 4.35), (dt.date(2026, 7, 15), 4.55)]
    assert _interp(curve, dt.date(2026, 6, 15)) == 4.35


def test_interp_midpoint_is_linear():
    curve = [(dt.date(2026, 6, 15), 4.0), (dt.date(2026, 7, 15), 5.0)]
    # 2026-06-30 is 15 days into a 30-day span -> halfway -> 4.5
    assert _interp(curve, dt.date(2026, 6, 30)) == 4.5


def test_interp_before_curve_clamps_to_front():
    curve = [(dt.date(2026, 6, 15), 4.35), (dt.date(2026, 7, 15), 4.55)]
    assert _interp(curve, dt.date(2026, 1, 1)) == 4.35


def test_interp_beyond_curve_returns_none_no_extrapolation():
    curve = [(dt.date(2026, 6, 15), 4.35), (dt.date(2026, 7, 15), 4.55)]
    assert _interp(curve, dt.date(2027, 1, 1)) is None


# --- parse_yield_curve error pinning ---------------------------------------

def test_parse_yield_curve_missing_keys_raises():
    with pytest.raises(ValueError, match="missing 'Crnt_Stlmnt_Dt'/'months' keys"):
        parse_yield_curve({"Crnt_Stlmnt_Dt": "2026-06-11"})


def test_parse_yield_curve_empty_months_raises():
    with pytest.raises(ValueError, match="empty 'months' array"):
        parse_yield_curve({"Crnt_Stlmnt_Dt": "2026-06-11", "months": []})


def test_parse_yield_curve_orders_by_anchor():
    settle, curve = parse_yield_curve(_YIELD_CURVE)
    assert settle == dt.date(2026, 6, 11)
    anchors = [a for a, _ in curve]
    assert anchors == sorted(anchors)


# --- build_rows -------------------------------------------------------------

def test_build_rows_emits_five_indicators(_patched):
    inds, _ = build_rows()
    codes = {i.imdr_code for i in inds}
    assert codes == {
        "ASX.CASHRATE.IMPLIED_1M.AU",
        "ASX.CASHRATE.IMPLIED_3M.AU",
        "ASX.CASHRATE.IMPLIED_6M.AU",
        "ASX.CASHRATE.IMPLIED_12M.AU",
        "ASX.RATETRACKER.PROB_CHANGE_NEXT_MEETING.AU",
    }


def test_build_rows_implied_1m_obs_on_settlement_date(_patched):
    _, obs = build_rows()
    one_m = [o for o in obs if o.imdr_code == "ASX.CASHRATE.IMPLIED_1M.AU"]
    assert len(one_m) == 1
    assert one_m[0].obs_date == dt.date(2026, 6, 11)
    # 1M ahead of 2026-06-11 is 2026-07-11, between Jun-15 (4.35) and
    # Jul-15 (4.35) -> 4.35.
    assert one_m[0].value == 4.35


def test_build_rows_prob_change_backfills_each_day(_patched):
    _, obs = build_rows()
    prob = sorted(
        (o for o in obs if o.imdr_code.endswith("PROB_CHANGE_NEXT_MEETING.AU")),
        key=lambda o: o.obs_date,
    )
    assert [o.obs_date for o in prob] == [dt.date(2026, 6, 10), dt.date(2026, 6, 11)]
    assert [o.value for o in prob] == [20.0, 0.0]


def test_build_rows_all_indicators_are_au_daily_rates(_patched):
    inds, _ = build_rows()
    for i in inds:
        assert i.country_iso == "AU"
        assert i.frequency == "DAILY"
        assert i.category == "rates"
        assert i.unit == "pct"
        assert i.vendor_name == "ASX"


def test_build_rows_market_exp_missing_days_raises(monkeypatch):
    monkeypatch.setattr(
        mod, "_get_json",
        lambda name, *, client=None: _YIELD_CURVE if name == "yield_curve.csv" else {"Ftre_Cash_Rate": 4.1},
    )
    with pytest.raises(ValueError, match="missing 'days' key"):
        build_rows()
