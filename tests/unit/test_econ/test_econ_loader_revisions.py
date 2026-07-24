"""Tests for the revision-classification contract in the econ fact loader.

``scripts.migrations.load_econ_indicator_from_playground`` captures data
revisions by writing a NEW vintage when a re-loaded value differs from the
current latest one (docs §3.3 -- vintage 0 = first print, 1+ = revisions).
The runtime decision is made in T-SQL, but ``classify_fact_action`` is the
pure-Python mirror of that predicate and is the testable contract.

Covered:
- brand-new obs -> "new" (regardless of value, incl. NULL)
- existing obs, unchanged value -> "skip" (idempotent re-load)
- existing obs, changed value -> "revision"
- existing obs, NULL incoming -> "skip" (never clobber a real value with NULL)
- existing obs with NULL current, real incoming -> "revision" (fills the gap)
- the KR Q1'26 GDP case that motivated the fix (1.7 -> 1.8) -> "revision"
"""
from __future__ import annotations

from scripts.migrations.load_econ_indicator_from_playground import (
    classify_fact_action,
)


class TestClassifyFactAction:
    def test_new_obs_when_not_exists(self) -> None:
        assert classify_fact_action(exists=False, incoming_value=1.8, current_value=None) == "new"

    def test_new_obs_even_when_value_null(self) -> None:
        # A brand-new observation is inserted at its staged vintage regardless
        # of whether the value is present.
        assert classify_fact_action(exists=False, incoming_value=None, current_value=None) == "new"

    def test_unchanged_value_skips(self) -> None:
        assert classify_fact_action(exists=True, incoming_value=1.8, current_value=1.8) == "skip"

    def test_changed_value_is_revision(self) -> None:
        assert classify_fact_action(exists=True, incoming_value=0.6, current_value=1.3) == "revision"

    def test_null_incoming_never_clobbers(self) -> None:
        # We must not supersede a real stored value with a NULL re-load.
        assert classify_fact_action(exists=True, incoming_value=None, current_value=1.8) == "skip"

    def test_null_current_filled_is_revision(self) -> None:
        assert classify_fact_action(exists=True, incoming_value=2.5, current_value=None) == "revision"

    def test_kr_q1_2026_gdp_revision(self) -> None:
        # The motivating case: KOSIS revised KR Q1'26 real GDP QoQ from 1.7 to
        # 1.8 -- must be captured as a revision, not silently skipped.
        assert classify_fact_action(exists=True, incoming_value=1.8, current_value=1.7) == "revision"
