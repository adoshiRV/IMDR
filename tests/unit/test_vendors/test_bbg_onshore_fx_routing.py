"""Tests for the BBG vendor-spec factory's onshore FX routing.

``BBG_mirror\\FX`` holds 22 currency folders and none of CNY/CNO/MYO/IDO, so
the onshore EM forward curves stopped at 2026-04-24 -- the day the FX feed cut
over to the mirror -- even though the legacy ``BBG\\FX`` tree still carries
them and is still refreshed. These pin the split routing that restores them.
"""
from __future__ import annotations

from pathlib import Path

from imdr.vendors.specs._bbg_factory import (
    BBG_FX_ROOT,
    BBG_LEGACY_FX_ROOT,
    ONSHORE_FX_CCYS,
    fx_patterns_from_universe,
    onshore_fx_extra_source,
)


def _ccy(pattern: str) -> str:
    return pattern.split("/")[0]


class TestMirrorPatterns:
    def test_excludes_the_onshore_ccys(self):
        """The mirror has no folder for these; asking logged a warning a run."""
        ccys = {_ccy(p) for p in fx_patterns_from_universe()}
        for onshore in ONSHORE_FX_CCYS:
            assert onshore not in ccys, onshore

    def test_excludes_cno(self):
        """CNO is not in ONSHORE_FX_CCYS either -- it must not slip back in.

        FX_CNO.csv labels tenors ``FX_CNY_*`` against a ``CNO`` folder, so
        every row is rejected by alias_to_tenor. USD/CNO has never held a
        fact row.
        """
        ccys = {_ccy(p) for p in fx_patterns_from_universe()}
        assert "CNO" not in ccys
        assert "CNO" not in ONSHORE_FX_CCYS

    def test_still_covers_the_offshore_equivalents(self):
        """CNH/IDR/MYR are the live mirror pairs and must be untouched."""
        ccys = {_ccy(p) for p in fx_patterns_from_universe()}
        for live in ("CNH", "IDR", "MYR", "JPY", "EUR"):
            assert live in ccys, live

    def test_patterns_are_the_per_pair_shape(self):
        for p in fx_patterns_from_universe():
            assert p == f"{_ccy(p)}/FX_{_ccy(p)}.csv"


class TestOnshoreExtraSource:
    def test_points_at_the_legacy_tree(self):
        (root, patterns), = onshore_fx_extra_source()
        assert root == BBG_LEGACY_FX_ROOT
        assert root != BBG_FX_ROOT
        assert "BBG_mirror" not in str(root)

    def test_requests_exactly_the_onshore_ccys(self):
        (_, patterns), = onshore_fx_extra_source()
        assert {_ccy(p) for p in patterns} == set(ONSHORE_FX_CCYS)

    def test_does_not_request_cno_or_kro(self):
        """Both sit in the legacy tree next to the files we want."""
        (_, patterns), = onshore_fx_extra_source()
        ccys = {_ccy(p) for p in patterns}
        assert "CNO" not in ccys
        assert "KRO" not in ccys

    def test_mirror_and_legacy_ccys_do_not_overlap(self):
        """No ccy may be acquired from both roots -- that would double-count."""
        mirror = {_ccy(p) for p in fx_patterns_from_universe()}
        (_, patterns), = onshore_fx_extra_source()
        assert mirror.isdisjoint({_ccy(p) for p in patterns})


class TestSpecsWireItUp:
    def test_both_fx_feeds_carry_the_extra_source(self):
        from imdr.vendors.specs.bbg_fx_daily import SPEC as DAILY
        from imdr.vendors.specs.bbg_fx_snapshot import SPEC as SNAP

        for spec in (SNAP, DAILY):
            assert spec.root == BBG_FX_ROOT
            assert spec.extra_sources == onshore_fx_extra_source()

    def test_rates_feeds_have_no_extra_source(self):
        """Only FX had the onshore split; rates must be unchanged."""
        from imdr.vendors.specs.bbg_rates_snapshot import SPEC as RATES

        assert RATES.extra_sources == ()
