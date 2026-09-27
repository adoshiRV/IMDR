"""Arrival-pass drift check: scripts/rates/health/check_curve_arrival.

Covers the pure logic — pass bucketing, business-day offsets, the learned
baseline and the verdict — with hand-built Series objects, so none of it needs
a database. The fixtures are real observed arrivals, not invented ones: the
EUR 3s6s sequence below is what ``rates.fact_observation.created_at`` actually
held for curve 63 over 2026-09-07..17, and the EURIBOR par sequence is curve
18's real progressive build. Both shapes have already broken an earlier
version of this checker, which is why they are pinned here.
"""
from __future__ import annotations

import datetime as dt

import pytest
from scripts.rates.health.check_curve_arrival import (
    DEFAULT_MIN_ON_TIME,
    Pass,
    Series,
    arrival_pass,
    business_days_between,
    evaluate,
    parse_pass,
    pass_due_at,
    pass_slot,
)

D = dt.date
T = dt.datetime
FAR_FUTURE = T(2030, 1, 1)


def _series(by_date, *, curve_id=63, ccy="EUR", curve="3S6S_BASIS",
            quote="basis") -> Series:
    return Series(curve_id=curve_id, ccy=ccy, curve=curve, quote=quote,
                  by_date=by_date)


# --- pass bucketing --------------------------------------------------------

@pytest.mark.parametrize("loaded,expected", [
    (T(2026, 9, 17, 8, 3, 15), (D(2026, 9, 17), 8)),     # on the 08:01 run
    (T(2026, 9, 17, 14, 3, 38), (D(2026, 9, 17), 14)),   # on the 14:01 run
    (T(2026, 9, 11, 16, 21, 52), (D(2026, 9, 11), 14)),  # retry rolls into 14:00
    (T(2026, 9, 9, 14, 45, 31), (D(2026, 9, 9), 14)),
    (T(2026, 9, 14, 2, 27, 40), (D(2026, 9, 14), 2)),
])
def test_pass_slot_buckets_to_the_scheduled_run(loaded, expected):
    assert pass_slot(loaded) == expected


def test_pre_dawn_write_belongs_to_the_previous_days_last_pass():
    # 01:40 is the tail of the 23:00 run, not a ninth pass of its own.
    assert pass_slot(T(2026, 9, 17, 1, 40)) == (D(2026, 9, 16), 23)


# --- business-day offsets --------------------------------------------------

def test_weekend_does_not_inflate_the_offset():
    """A Friday row loaded Monday is B+1, exactly like a Monday row on Tuesday.

    This is the whole reason offsets are business days. On calendar days the
    Friday arrival would read B+3 every single week and every curve would look
    like it drifted two days each weekend.
    """
    friday, monday = D(2026, 9, 11), D(2026, 9, 14)
    assert arrival_pass(friday, T(2026, 9, 14, 2, 27)) == Pass(1, 2)
    assert arrival_pass(monday, T(2026, 9, 15, 8, 21)) == Pass(1, 8)


def test_business_days_between_is_signed_and_skips_weekends():
    assert business_days_between(D(2026, 9, 11), D(2026, 9, 14)) == 1
    assert business_days_between(D(2026, 9, 14), D(2026, 9, 14)) == 0
    assert business_days_between(D(2026, 9, 14), D(2026, 9, 11)) == -1


def test_pass_ordering_is_chronological():
    assert Pass(1, 8) < Pass(1, 14) < Pass(2, 2) < Pass(2, 8)


def test_pass_due_at_advances_business_days_and_adds_grace():
    # B+1 08:00 for a Friday value date fires Monday morning, not Saturday.
    due = pass_due_at(D(2026, 9, 11), Pass(1, 8))
    assert due.date() == D(2026, 9, 14)
    assert (due.hour, due.minute) == (8, 30)


@pytest.mark.parametrize("spec", ["B+1 08:00", "b+1 8", "1@8", "+1 08:00"])
def test_parse_pass_accepts_the_documented_spellings(spec):
    assert parse_pass(spec) == Pass(1, 8)


def test_parse_pass_rejects_an_unscheduled_hour():
    with pytest.raises(ValueError, match="not a scheduled pass"):
        parse_pass("B+1 09:00")


# --- the real EUR 3s6s deterioration ---------------------------------------
#
# curve 63, as loaded. 09-14: 19 tenors at 08:21 + 1 at 14:22. 09-15: 5 at
# 08:03 + 15 at 14:23. 09-16: all 20 at 14:03. 09-17: all 20 back at 08:03.

EUR_3S6S = {
    D(2026, 9, 7): {Pass(2, 8): 20},                    # Labor Day, a day late
    D(2026, 9, 8): {Pass(1, 8): 20},
    D(2026, 9, 9): {Pass(1, 14): 20},
    D(2026, 9, 10): {Pass(1, 8): 20},
    D(2026, 9, 11): {Pass(1, 2): 20},                   # Fri, loaded Mon 02:27
    D(2026, 9, 14): {Pass(1, 8): 19, Pass(1, 14): 1},
    D(2026, 9, 15): {Pass(1, 8): 5, Pass(1, 14): 15},
    D(2026, 9, 16): {Pass(1, 14): 20},
}


def test_learns_the_morning_baseline_and_calls_the_afternoon_build_late():
    v = evaluate(_series(EUR_3S6S), D(2026, 9, 16), FAR_FUTURE)
    assert v.baseline == Pass(1, 8)
    assert v.status == "LATE"
    assert v.latest_pct == 0.0
    assert v.latest_complete == Pass(1, 14)


def test_on_time_share_reproduces_the_95_25_0_deterioration():
    """The number the original ops note got wrong.

    It reported three days of "nothing in the 08:00 batch"; the morning pass
    actually delivered 95%, then 25%, then 0%. A checker that cannot tell
    those apart would have confirmed the wrong story.
    """
    s = _series(EUR_3S6S)
    pcts = [s.on_time_pct(d, Pass(1, 8))
            for d in (D(2026, 9, 14), D(2026, 9, 15), D(2026, 9, 16))]
    assert pcts == [95.0, 25.0, 0.0]


def test_a_run_of_bad_days_cannot_redefine_the_baseline_as_itself():
    """Baseline is learned from settled dates only, excluding the newest.

    With 09-16 settled the window holds three B+1 08:00 completions and three
    B+1 14:00 ones — a tie, which must break to the earlier pass. Breaking it
    the other way would declare the drift to be the new normal and go quiet.
    """
    drifted = dict(EUR_3S6S)
    drifted[D(2026, 9, 17)] = {Pass(1, 14): 20}
    v = evaluate(_series(drifted), D(2026, 9, 17), FAR_FUTURE)
    assert v.baseline == Pass(1, 8)
    assert v.status == "LATE"


def test_recovery_still_reports_the_window_as_intermittent():
    """09-17 came back clean on 08:03 — but four earlier days had not.

    Judging on the newest value date alone would print OK over exactly the
    multi-day pattern this script exists to surface.
    """
    recovered = dict(EUR_3S6S)
    recovered[D(2026, 9, 17)] = {Pass(1, 8): 20}
    v = evaluate(_series(recovered), D(2026, 9, 17), FAR_FUTURE)
    assert v.status == "INTERMITTENT"
    assert v.late_dates == [D(2026, 9, 7), D(2026, 9, 9),
                            D(2026, 9, 15), D(2026, 9, 16)]
    assert v.flagged


def test_intermittent_yields_to_an_explicit_tolerance():
    recovered = dict(EUR_3S6S)
    recovered[D(2026, 9, 17)] = {Pass(1, 8): 20}
    v = evaluate(_series(recovered), D(2026, 9, 17), FAR_FUTURE,
                 max_late_days=5)
    assert v.status == "OK"
    assert not v.flagged


def test_expect_pass_overrides_the_learned_baseline():
    v = evaluate(_series(EUR_3S6S), D(2026, 9, 16), FAR_FUTURE,
                 expect_pass=Pass(1, 14))
    assert v.baseline == Pass(1, 14)
    assert v.status == "OK"


# --- progressive builds must not false-alarm -------------------------------
#
# curve 18 EUR EURIBOR par: ~8% of the grid lands on the 14:00 pass and the
# rest accumulates through 17:00/20:00/23:00, completing at 02:00 the next
# morning. Every day. Keyed on first arrival this reads 8% on-time forever.

def _euribor_day():
    return {Pass(0, 14): 36, Pass(0, 17): 108, Pass(0, 20): 108,
            Pass(0, 23): 108, Pass(1, 2): 72}


EURIBOR_PAR = {d: _euribor_day() for d in (
    D(2026, 9, 10), D(2026, 9, 11), D(2026, 9, 14),
    D(2026, 9, 15), D(2026, 9, 16), D(2026, 9, 17))}


def test_progressive_build_is_not_flagged():
    v = evaluate(_series(EURIBOR_PAR, curve_id=18, curve="EURIBOR",
                         quote="par"),
                 D(2026, 9, 17), FAR_FUTURE)
    assert v.baseline == Pass(1, 2), "baseline must key on completion"
    assert v.status == "OK"
    assert v.late_dates == []


def test_progressive_build_that_finishes_a_pass_late_is_flagged():
    slipped = dict(EURIBOR_PAR)
    slipped[D(2026, 9, 17)] = {Pass(0, 14): 36, Pass(0, 17): 108,
                               Pass(0, 20): 108, Pass(1, 8): 180}
    v = evaluate(_series(slipped, curve_id=18, curve="EURIBOR", quote="par"),
                 D(2026, 9, 17), FAR_FUTURE)
    assert v.status == "LATE"
    assert v.latest_complete == Pass(1, 8)


def test_complete_pass_uses_the_threshold_not_the_last_trickle():
    """A late top-up after the grid is effectively complete is not lateness."""
    s = _series({D(2026, 9, 16): {Pass(1, 2): 460, Pass(2, 2): 8}},
                curve_id=18, curve="EURIBOR", quote="par")
    assert s.complete_pass(D(2026, 9, 16), DEFAULT_MIN_ON_TIME) == Pass(1, 2)
    assert s.last_pass(D(2026, 9, 16)) == Pass(2, 2)


# --- due-vs-late -----------------------------------------------------------

AFTERNOON = {
    D(2026, 9, 10): {Pass(1, 14): 20},
    D(2026, 9, 11): {Pass(1, 14): 20},
    D(2026, 9, 14): {Pass(1, 14): 20},
    D(2026, 9, 15): {Pass(1, 14): 20},
    D(2026, 9, 16): {Pass(1, 14): 20},
}


def test_afternoon_series_is_pending_not_behind_during_the_morning():
    """USD SOFR_FEDFUND_BASIS at 11:49 on 09-18, missing 09-17.

    Its baseline is the 14:00 pass, so nothing is wrong yet. Without this the
    check would flag every afternoon-arriving curve every single morning and
    be ignored by its second run.
    """
    v = evaluate(_series(AFTERNOON, curve_id=66, ccy="USD",
                         curve="SOFR_FEDFUND_BASIS"),
                 cohort_latest=D(2026, 9, 17),
                 now=T(2026, 9, 18, 11, 49))
    assert v.status == "PENDING"
    assert not v.flagged


def test_the_same_gap_after_the_pass_has_fired_is_behind():
    v = evaluate(_series(AFTERNOON, curve_id=66, ccy="USD",
                         curve="SOFR_FEDFUND_BASIS"),
                 cohort_latest=D(2026, 9, 17),
                 now=T(2026, 9, 18, 16, 0))
    assert v.status == "BEHIND"
    assert v.flagged


def test_too_little_history_is_sparse_not_a_guess():
    v = evaluate(_series({D(2026, 9, 16): {Pass(1, 8): 20}}),
                 D(2026, 9, 16), FAR_FUTURE)
    assert v.status == "SPARSE"
    assert v.baseline is None
    assert not v.flagged
