"""Unit tests for scripts.migrations.seed_dim_scenario.

The seed module already enforces taxonomy hygiene at import time (the asserts
right after SCENARIOS). These tests are a regression net for the curated data
itself: scenario count, window encoding, tag coverage.
"""
from __future__ import annotations

from scripts.migrations.seed_dim_scenario import CANONICAL_TAGS, SCENARIOS


class TestScenarioInventory:
    def test_has_25_scenarios(self):
        assert len(SCENARIOS) == 25

    def test_names_are_unique(self):
        names = [s.name for s in SCENARIOS]
        assert len(set(names)) == len(names)

    def test_every_scenario_has_at_least_one_window(self):
        for sc in SCENARIOS:
            assert len(sc.windows) >= 1, sc.name

    def test_windows_are_valid_ranges(self):
        for sc in SCENARIOS:
            for start, end in sc.windows:
                if end is not None:
                    assert end >= start, f"{sc.name}: {start} > {end}"

    def test_us_debt_ceiling_2023_has_two_windows(self):
        match = next(s for s in SCENARIOS if "Fitch downgrade" in s.name)
        assert len(match.windows) == 2

    def test_open_ended_windows_have_null_end_date(self):
        open_ended = [s for s in SCENARIOS if any(end is None for _, end in s.windows)]
        assert {s.name for s in open_ended} == {
            "Russia-Ukraine invasion",
            "US-Iran war / Hormuz-oil shock",
        }


class TestTaxonomy:
    def test_canonical_set_size(self):
        # 6 asset classes + 9 themes + 8 regions = 23 — guard against typos.
        assert len(CANONICAL_TAGS) == 23

    def test_every_scenario_has_at_least_one_tag(self):
        for sc in SCENARIOS:
            assert len(sc.tags) >= 1, sc.name

    def test_no_duplicate_tags_within_scenario(self):
        for sc in SCENARIOS:
            assert len(sc.tags) == len(set(sc.tags)), f"{sc.name} has duplicate tags"
