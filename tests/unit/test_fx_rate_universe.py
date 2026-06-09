"""Tests for FXUniverse fx_rate methods."""

import pytest

from imdr.universe.fx import get_fx_universe


@pytest.fixture
def universe():
    return get_fx_universe()


class TestFXRateUniverse:
    def test_26_pairs(self, universe) -> None:
        # 19 Citi+BBG shared + 3 BBG-deliverable (MXN/PLN/ILS) + 4 BBG-only onshore (CNY/CNO/MYO/IDO)
        pairs = universe.fx_rate_pairs()
        assert len(pairs) == 26

    def test_bbg_only_pairs(self, universe) -> None:
        bbg_only = universe.fx_rate_bbg_only_pairs()
        assert ("USD", "CNY") in bbg_only
        assert ("USD", "CNO") in bbg_only
        assert ("USD", "MYO") in bbg_only
        assert ("USD", "IDO") in bbg_only
        # Citi-eligible pairs must NOT be in bbg_only
        assert ("EUR", "USD") not in bbg_only
        assert ("USD", "JPY") not in bbg_only

    def test_all_tuples(self, universe) -> None:
        pairs = universe.fx_rate_pairs()
        assert all(isinstance(p, tuple) and len(p) == 2 for p in pairs)

    def test_has_hkd(self, universe) -> None:
        pairs = universe.fx_rate_pairs()
        assert ("USD", "HKD") in pairs

    def test_eur_usd_non_standard_ordering(self, universe) -> None:
        # Citi convention: EUR base, USD quote
        pairs = universe.fx_rate_pairs()
        assert ("EUR", "USD") in pairs
        assert ("USD", "EUR") not in pairs

    def test_tenors(self, universe) -> None:
        tenors = universe.fx_rate_tenors()
        assert tenors[0] == "SPOT"
        assert "ON" in tenors
        assert "10Y" in tenors
        assert len(tenors) == 11

    def test_forward_tenors_excludes_spot(self, universe) -> None:
        fwd = universe.fx_rate_forward_tenors()
        assert "SPOT" not in fwd
        assert len(fwd) == 10

    def test_spot_only_empty(self, universe) -> None:
        # All Phase 1 pairs have Citi forwards; no spot-only carve-outs
        assert universe.fx_rate_spot_only_pairs() == set()

    def test_spot_tag_template(self, universe) -> None:
        assert universe.build_fx_rate_spot_tag("EUR", "USD") == "FX.SPOT.EUR.USD.CITI"

    def test_outright_tag_template(self, universe) -> None:
        tags = universe.build_fx_rate_outright_tags("USD", "HKD")
        assert "FX.FORWARD.FWD_OUTRIGHT.USD.HKD.1M.CITI" in tags
        assert len(tags) == 10  # forward tenors only

    def test_point_tag_template(self, universe) -> None:
        tags = universe.build_fx_rate_point_tags("EUR", "USD")
        assert "FX.FORWARD.FWD_POINT.EUR.USD.1Y.CITI" in tags
        assert len(tags) == 10

    def test_total_tag_count(self, universe) -> None:
        # 26 universe pairs minus 4 bbg_only = 22 Citi-eligible pairs
        # × (1 spot + 10 outright + 10 points) = 22 × 21 = 462
        tags = universe.build_all_fx_rate_tags()
        assert len(tags) == 462

    def test_all_citi_pairs_get_both_spot_and_forward(self, universe) -> None:
        # Every Citi-eligible pair (i.e. universe minus bbg_only) has spot +
        # outright + points Citi tags. BBG-only pairs are excluded by design.
        all_tags = universe.build_all_fx_rate_tags()
        bbg_only = universe.fx_rate_bbg_only_pairs()
        for ccy1, ccy2 in universe.fx_rate_pairs():
            if (ccy1, ccy2) in bbg_only:
                # BBG-only pairs MUST NOT have Citi tags
                assert f"FX.SPOT.{ccy1}.{ccy2}.CITI" not in all_tags
                continue
            assert f"FX.SPOT.{ccy1}.{ccy2}.CITI" in all_tags
            assert f"FX.FORWARD.FWD_OUTRIGHT.{ccy1}.{ccy2}.1M.CITI" in all_tags
            assert f"FX.FORWARD.FWD_POINT.{ccy1}.{ccy2}.1M.CITI" in all_tags

    def test_expected_range_hkd(self, universe) -> None:
        r = universe.fx_rate_expected_range("USD", "HKD")
        assert r is not None
        assert r.min == 7.70
        assert r.max == 7.90

    def test_expected_range_missing_returns_none(self, universe) -> None:
        assert universe.fx_rate_expected_range("USD", "NONEXISTENT") is None

    def test_all_pairs_have_expected_ranges(self, universe) -> None:
        """Every pair in the universe should have an expected_range defined."""
        ranges = universe.fx_rate_expected_ranges()
        for ccy1, ccy2 in universe.fx_rate_pairs():
            code = f"{ccy1}{ccy2}"
            assert code in ranges, f"missing expected_range for {code}"

    def test_dim_seed_entries(self, universe) -> None:
        entries = universe.fx_rate_pair_create_entries()
        assert len(entries) == 26
        ccy_classes = {e.ccy_class for e in entries}
        # At minimum we should see all three classes
        assert "g10" in ccy_classes
        assert "em_deliverable" in ccy_classes
        assert "em_ndf" in ccy_classes

    def test_hkd_classified_em_deliverable(self, universe) -> None:
        assert universe.classification_for("HKD") == "em_deliverable"

    def test_myr_classified_em_ndf(self, universe) -> None:
        assert universe.classification_for("MYR") == "em_ndf"
