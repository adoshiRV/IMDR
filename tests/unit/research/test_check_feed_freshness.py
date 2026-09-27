"""Tests for scripts/research/check_feed_freshness.py.

Pins the two failure modes that produced the phantom "seven sessions stale"
FRED outage in the 25/26 Aug 2026 daily editions:

  * a T+1 daily series read at a cut one session later must be OK, not stale;
  * a WEEKLY series (the NFCI block) must not be judged on a daily tolerance.
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import sys
from pathlib import Path

import pytest

_MOD_PATH = (
    Path(__file__).resolve().parents[3]
    / "scripts" / "research" / "check_feed_freshness.py"
)
_spec = importlib.util.spec_from_file_location("check_feed_freshness", _MOD_PATH)
cff = importlib.util.module_from_spec(_spec)
sys.modules["check_feed_freshness"] = cff
_spec.loader.exec_module(cff)


# ---------------------------------------------------------------------------
# business_days_between
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "start, end, expected",
    [
        # 2026-08-24 Mon .. 2026-08-26 Wed
        (dt.date(2026, 8, 24), dt.date(2026, 8, 26), 2),
        # Fri -> Mon is ONE business day, not three.
        (dt.date(2026, 8, 21), dt.date(2026, 8, 24), 1),
        # Fri -> Sat/Sun score zero: a weekend-only gap is never staleness.
        (dt.date(2026, 8, 21), dt.date(2026, 8, 22), 0),
        (dt.date(2026, 8, 21), dt.date(2026, 8, 23), 0),
        # Same day, and a backwards range, are both zero.
        (dt.date(2026, 8, 26), dt.date(2026, 8, 26), 0),
        (dt.date(2026, 8, 26), dt.date(2026, 8, 20), 0),
        # A full week apart = 5 business days.
        (dt.date(2026, 8, 19), dt.date(2026, 8, 26), 5),
    ],
)
def test_business_days_between(start, end, expected):
    assert cff.business_days_between(start, end) == expected


# ---------------------------------------------------------------------------
# Tolerance derivation
# ---------------------------------------------------------------------------

def test_daily_tolerance_is_lag_plus_grace():
    fam = cff.Family("d", "X%", cff.DAILY, lag_days=1, grace=1)
    assert fam.tolerance == 2


def test_weekly_tolerance_absorbs_a_full_week():
    """A weekly series is a week behind by construction, not by failure."""
    fam = cff.Family("w", "X%", cff.WEEKLY, lag_days=3, grace=1)
    assert fam.tolerance == 9


# ---------------------------------------------------------------------------
# evaluate() — the regression cases
# ---------------------------------------------------------------------------

def _probe(obs, n=4, ingest="2026-08-26T02:31:00"):
    return {"n_series": n, "latest_obs": obs, "latest_ingest": ingest}


def test_credit_oas_one_session_behind_is_ok():
    """THE regression. Obs 24 Aug at a 26 Aug cut is FRED's normal T+1 lag.

    The 26 Aug edition called this 'seven sessions stale' and dropped the
    credit read. It is two business days behind against a tolerance of two.
    """
    fam = next(f for f in cff.REGISTRY if f.name == "credit OAS")
    v = cff.evaluate(fam, _probe(dt.date(2026, 8, 24)), dt.date(2026, 8, 26))
    assert v["behind"] == 2
    assert v["status"] == "OK"


def test_vix_one_session_behind_is_ok():
    fam = next(f for f in cff.REGISTRY if f.name == "volatility")
    v = cff.evaluate(fam, _probe(dt.date(2026, 8, 24), n=2), dt.date(2026, 8, 26))
    assert v["status"] == "OK"


def test_nfci_weekly_is_not_stale_at_a_week_behind():
    """NFCI_CREDIT reads as 'credit' but is a Chicago Fed WEEKLY.

    Obs 14 Aug at a 26 Aug cut is 8 business days -- within the weekly
    tolerance of 9. Judged on the daily block's tolerance it would falsely
    read as stale, which is how '19 Aug' leaked into the editions.
    """
    fam = next(f for f in cff.REGISTRY if f.name == "NFCI block")
    v = cff.evaluate(fam, _probe(dt.date(2026, 8, 14), n=5), dt.date(2026, 8, 26))
    assert v["behind"] == 8
    assert v["status"] == "OK"

    daily = cff.Family("as-if-daily", "X%", cff.DAILY, lag_days=1)
    assert cff.evaluate(daily, _probe(dt.date(2026, 8, 14)),
                        dt.date(2026, 8, 26))["status"] == "STALE"


def test_genuinely_stale_is_flagged():
    """The real IMD outage: frozen at 19 Aug while editions ran to 26 Aug."""
    fam = next(f for f in cff.REGISTRY if f.name.startswith("IMD rainfall"))
    v = cff.evaluate(fam, _probe(dt.date(2026, 8, 19), n=3), dt.date(2026, 8, 26))
    assert v["behind"] == 5
    assert v["status"] == "STALE"


def test_no_matching_series_is_missing_not_ok():
    """Pattern drift must fail loudly, never silently pass as fresh."""
    fam = cff.Family("gone", "NOPE.%", cff.DAILY, lag_days=1)
    v = cff.evaluate(fam, _probe(None, n=0), dt.date(2026, 8, 26))
    assert v["status"] == "MISSING"


@pytest.mark.parametrize(
    "raw",
    [
        dt.date(2026, 8, 24),
        dt.datetime(2026, 8, 24, 17, 0),
        "2026-08-24",                    # the pinned ODBC driver's actual shape
        "2026-08-24 00:00:00",
    ],
)
def test_obs_is_narrowed_to_date(raw):
    """The driver returns DATE as a string; all shapes must compare."""
    fam = next(f for f in cff.REGISTRY if f.name == "credit OAS")
    v = cff.evaluate(fam, _probe(raw), dt.date(2026, 8, 26))
    assert v["latest_obs"] == dt.date(2026, 8, 24)
    assert v["status"] == "OK"


# ---------------------------------------------------------------------------
# Registry sanity
# ---------------------------------------------------------------------------

def test_registry_patterns_are_distinct_and_named():
    names = [f.name for f in cff.REGISTRY]
    assert len(names) == len(set(names)), "duplicate family name"
    assert all(f.pattern.endswith("%") for f in cff.REGISTRY)


def test_nfci_is_the_only_weekly_fred_family():
    """Guards the exact confusion that caused the incident.

    Scoped to FRED patterns: the EIA energy block is also WEEKLY, but it is a
    different vendor and its cadence was verified independently.
    """
    weekly = [f.name for f in cff.REGISTRY
              if f.cadence == cff.WEEKLY and f.pattern.startswith("FRED.")]
    assert weekly == ["NFCI block"]


def test_select_rejects_unknown_family():
    assert cff._select(["no-such-family"], None) == []


def test_select_defaults_to_full_registry():
    assert cff._select(None, None) == cff.REGISTRY


def test_select_code_overrides_family():
    fams = cff._select(["credit OAS"], ["FRED.RATES.UST[_]%"])
    assert len(fams) == 1
    assert fams[0].pattern == "FRED.RATES.UST[_]%"


def test_bad_as_of_returns_nonzero():
    assert cff.main(["--as-of", "26-08-2026"]) == 1

# ---------------------------------------------------------------------------
# Holiday-aware counting — the 2026-09-09 regression
#
# US Labor Day fell on Mon 2026-09-07. Counted as a business day, the H.15
# blocks read one day staler than they were and the 09-09 run printed a false
# STALE for cash Treasuries and TIPS. Every long weekend would repeat it.
# ---------------------------------------------------------------------------

_LABOR_DAY = frozenset({dt.date(2026, 9, 7)})


def test_holiday_is_not_a_business_day():
    """Fri 04 Sep -> Wed 09 Sep is 2 trading days, not 3, across Labor Day."""
    assert cff.business_days_between(
        dt.date(2026, 9, 4), dt.date(2026, 9, 9)) == 3
    assert cff.business_days_between(
        dt.date(2026, 9, 4), dt.date(2026, 9, 9), _LABOR_DAY) == 2


def test_holiday_only_gap_scores_zero():
    """Fri -> the following holiday Monday is no staleness at all."""
    assert cff.business_days_between(
        dt.date(2026, 9, 4), dt.date(2026, 9, 7), _LABOR_DAY) == 0


@pytest.mark.parametrize("family", ["cash Treasuries", "TIPS real yields"])
def test_h15_blocks_not_stale_across_labor_day(family):
    """THE 09-09 regression: obs 04 Sep at a 09 Sep cut is FRED's normal T+2.

    The pre-fix run reported '3 business days behind, tolerance 2 -> STALE'
    for both blocks. Verified against the FRED API on 2026-09-09: DGS10 and
    DFII10 genuinely ended 04 Sep upstream, so there was nothing to ingest.
    """
    fam = next(f for f in cff.REGISTRY if f.name == family)
    v = cff.evaluate(fam, _probe(dt.date(2026, 9, 4), n=11),
                     dt.date(2026, 9, 9), _LABOR_DAY)
    assert v["behind"] == 2
    assert v["status"] == "OK"


def test_h15_input_blocks_publish_at_t_plus_2():
    """DGS*/DFII* land a business day after the spreads computed from them.

    Not a typo and not a defect -- FRED posts T10Y2Y/T10YIE before the levels.
    Pinning it stops the lag being 'corrected' back to 1 and re-breaking the
    check every holiday week.
    """
    for name in ("cash Treasuries", "TIPS real yields"):
        assert next(f for f in cff.REGISTRY if f.name == name).lag_days == 2
    for name in ("breakevens", "curve spreads"):
        assert next(f for f in cff.REGISTRY if f.name == name).lag_days == 1


def test_curve_spreads_family_is_registered():
    """CURVE_10Y2Y / CURVE_10Y3M were unmonitored until 2026-09-09.

    The registry had UST/TIPS/BEI patterns but no CURVE one, so a stall in the
    curve block could not have been detected by this script at all.
    """
    fam = next((f for f in cff.REGISTRY if f.name == "curve spreads"), None)
    assert fam is not None
    assert fam.pattern == "FRED.RATES.CURVE[_]%"


def test_fred_families_ride_the_fed_calendar():
    fred = [f for f in cff.REGISTRY if f.pattern.startswith("FRED.")]
    assert fred and all(f.calendar_code == "FD" for f in fred)
    imd = next(f for f in cff.REGISTRY if f.name.startswith("IMD rainfall"))
    assert imd.calendar_code == "RB"


# ---------------------------------------------------------------------------
# check_coherence — derived advancing without its inputs
# ---------------------------------------------------------------------------

def _verdicts(pairs, as_of=dt.date(2026, 9, 9), holidays=_LABOR_DAY):
    """Build evaluate() verdicts for {family name: latest obs date}."""
    out = []
    for name, obs in pairs.items():
        fam = next(f for f in cff.REGISTRY if f.name == name)
        out.append(cff.evaluate(fam, _probe(obs, n=3), as_of, holidays))
    return out


def test_one_day_lead_of_derived_over_inputs_is_coherent():
    """The normal steady state, and the actual 2026-09-09 state.

    Curve at 08 Sep over UST at 04 Sep is a single trading day once Labor Day
    is excluded -- exactly FRED's publication order, so it must NOT warn.
    """
    v = _verdicts({
        "curve spreads": dt.date(2026, 9, 8),
        "breakevens": dt.date(2026, 9, 8),
        "cash Treasuries": dt.date(2026, 9, 4),
        "TIPS real yields": dt.date(2026, 9, 4),
    })
    assert cff.check_coherence(v, {"FD": _LABOR_DAY}) == []


def test_derived_running_two_days_ahead_is_flagged():
    """The dangerous direction: inputs stalled, derived still advancing.

    A consumer quoting only the curve would show a fresh number resting on
    stale levels. One extra stalled session must trip the guard.
    """
    v = _verdicts({
        "curve spreads": dt.date(2026, 9, 9),
        "cash Treasuries": dt.date(2026, 9, 4),
    }, as_of=dt.date(2026, 9, 10))
    warnings = cff.check_coherence(v, {"FD": _LABOR_DAY})
    assert len(warnings) == 1
    assert "INCOHERENT" in warnings[0]
    assert "curve spreads" in warnings[0] and "cash Treasuries" in warnings[0]


def test_coherence_skips_families_not_selected():
    """--family runs must not warn about pairs they didn't probe."""
    v = _verdicts({"curve spreads": dt.date(2026, 9, 8)})
    assert cff.check_coherence(v, {"FD": _LABOR_DAY}) == []


def test_coherence_ignores_missing_families():
    """A MISSING family has no obs date; it is reported by the stale path."""
    fam = next(f for f in cff.REGISTRY if f.name == "cash Treasuries")
    missing = cff.evaluate(fam, _probe(None, n=0), dt.date(2026, 9, 9))
    v = _verdicts({"curve spreads": dt.date(2026, 9, 8)}) + [missing]
    assert cff.check_coherence(v, {"FD": _LABOR_DAY}) == []


def test_coherence_pairs_reference_real_families():
    names = {f.name for f in cff.REGISTRY}
    for derived, inputs, max_lead in cff.COHERENCE_PAIRS:
        assert derived in names, derived
        assert inputs in names, inputs
        assert max_lead >= 1


# ---------------------------------------------------------------------------
# The flapping credit/vol lane — 2026-09-10
#
# At lag_days=1 the tolerance (2) exactly EQUALLED these families' structural
# lag, so they sat on the boundary and flipped OK/STALE on any perturbation:
# a holiday, a skipped weekend 02:30 run, or simply being evaluated before
# that run. Measured over 2026-08-10..09-07, every observation arrived on the
# ~02:30-04:00 SGT run two calendar days after obs_date (four across a
# weekend) — because FRED posts them in the US afternoon, after our ~21:00
# run, and the next run is ~02:30.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("family", ["credit OAS", "volatility"])
def test_credit_and_vol_publish_at_t_plus_2(family):
    """Pinning the measured lag; reverting it re-introduces the flapping."""
    fam = next(f for f in cff.REGISTRY if f.name == family)
    assert fam.lag_days == 2
    assert fam.tolerance == 3


@pytest.mark.parametrize("family", ["credit OAS", "volatility"])
def test_credit_and_vol_ok_at_the_pre_run_trough(family):
    """THE 09-10 regression: obs 07 Sep at a 10 Sep cut must be OK.

    This is the deepest point of the normal cycle — evaluated before the
    02:30 run, across Labor Day. It read STALE at the old tolerance.
    """
    fam = next(f for f in cff.REGISTRY if f.name == family)
    v = cff.evaluate(fam, _probe(dt.date(2026, 9, 7)), dt.date(2026, 9, 10),
                     _LABOR_DAY)
    assert v["behind"] == 3
    assert v["status"] == "OK"


@pytest.mark.parametrize("family", ["credit OAS", "volatility"])
def test_credit_and_vol_have_headroom_after_the_run(family):
    """Post-run steady state keeps a day in hand — no longer bistable."""
    fam = next(f for f in cff.REGISTRY if f.name == family)
    v = cff.evaluate(fam, _probe(dt.date(2026, 9, 8)), dt.date(2026, 9, 10),
                     _LABOR_DAY)
    assert v["behind"] == 2
    assert v["status"] == "OK"


@pytest.mark.parametrize("family", ["credit OAS", "volatility"])
def test_credit_and_vol_still_catch_a_genuinely_missed_day(family):
    """Widening the tolerance must not blind the check.

    One more stalled session past the trough and it fires.
    """
    fam = next(f for f in cff.REGISTRY if f.name == family)
    v = cff.evaluate(fam, _probe(dt.date(2026, 9, 7)), dt.date(2026, 9, 11),
                     _LABOR_DAY)
    assert v["behind"] == 4
    assert v["status"] == "STALE"


# ---------------------------------------------------------------------------
# EIA energy spot — a WEEKLY batch of DAILY observations
#
# Ingests on 07-23/07-30/08-06/08-13/08-20/08-27/09-03 were all Thursdays,
# each carrying five daily obs ending 2 calendar days back. A mid-week
# plateau is therefore the normal state, and this is IMDR's ONLY Brent price
# source — Citi's COMMODITIES.SPOT namespace has no Brent tag, the FRED
# duplicates are is_active=0, and BBG\Commodities died in 2023.
# ---------------------------------------------------------------------------

def test_energy_family_is_registered_and_weekly():
    fam = next(f for f in cff.REGISTRY if f.name == "energy spot (EIA)")
    assert fam.cadence == cff.WEEKLY
    assert fam.lag_days == 2
    assert fam.tolerance == 8
    assert fam.pattern == "EIA.ENERGY.%"


def test_energy_midweek_plateau_is_not_stale():
    """Brent at 01 Sep on a 10 Sep cut is a normal pre-batch plateau.

    The 09-03 Thursday batch delivered through 09-01; the next was due
    09-10. Nine calendar days looks dead only if you assume daily publication.
    """
    fam = next(f for f in cff.REGISTRY if f.name == "energy spot (EIA)")
    v = cff.evaluate(fam, _probe(dt.date(2026, 9, 1), n=3),
                     dt.date(2026, 9, 10), _LABOR_DAY)
    assert v["behind"] == 6
    assert v["status"] == "OK"


def test_energy_on_a_daily_tolerance_would_falsely_read_stale():
    """The cadence error itself — the NFCI incident in a new lane."""
    as_if_daily = cff.Family("as-if-daily", "EIA.ENERGY.%", cff.DAILY,
                             lag_days=2)
    v = cff.evaluate(as_if_daily, _probe(dt.date(2026, 9, 1), n=3),
                     dt.date(2026, 9, 10), _LABOR_DAY)
    assert v["status"] == "STALE"


def test_energy_missed_batch_is_flagged():
    """A skipped Thursday batch must surface: 01 Sep still latest on 17 Sep."""
    fam = next(f for f in cff.REGISTRY if f.name == "energy spot (EIA)")
    v = cff.evaluate(fam, _probe(dt.date(2026, 9, 1), n=3),
                     dt.date(2026, 9, 17), _LABOR_DAY)
    assert v["status"] == "STALE"


def test_deactivated_series_are_excluded_by_the_query():
    """FRED's oil duplicates are is_active=0 (migration 106).

    They mirror the same EIA data and stopped at 2026-06-01 by design, so the
    registry must never surface them. The SQL filters on is_active.
    """
    assert "i.is_active = 1" in cff._SQL
