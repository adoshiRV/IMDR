"""Tests for universe/rates.py — RatesUniverse class."""

import pytest

from imdr.universe.rates import get_rates_universe


@pytest.fixture
def universe():
    return get_rates_universe()


class TestUniverseLoading:
    def test_loads(self, universe):
        assert universe is not None

    def test_curve_count(self, universe):
        # 39 prior + 4 basis_swaps (USD/EUR/GBP/AUD 3S6S_BASIS) = 43
        assert len(universe.all_curves()) == 43

    def test_target_currencies(self, universe):
        ccys = universe.target_currencies()
        assert len(ccys) >= 22
        assert "USD" in ccys
        assert "SGD" in ccys


class TestCurveLookups:
    def test_get_curve_usd_sofr(self, universe):
        c = universe.get_curve("USD", "SOFR")
        assert c.type == "rfr"
        assert c.status == "active"

    def test_get_curve_not_found_raises(self, universe):
        with pytest.raises(KeyError):
            universe.get_curve("XXX", "YYY")

    def test_curves_for_ccy_jpy(self, universe):
        curves = universe.curves_for_ccy("JPY")
        assert len(curves) == 4  # TONAR, TONAR_JSCC, TONAR_LCH, JPY_LIBOR

    def test_curves_for_ccy_usd(self, universe):
        curves = universe.curves_for_ccy("USD")
        names = [c.curve for c in curves]
        assert "SOFR" in names
        assert "FEDFUND" in names
        assert "LIBOR" in names

    def test_ceased_curve(self, universe):
        c = universe.get_curve("USD", "LIBOR")
        assert c.status == "ceased"
        assert c.superseded_by == "SOFR"


class TestMaturities:
    def test_ois_count(self, universe):
        assert len(universe.maturities("ois")) == 44

    def test_swap_libor_count(self, universe):
        assert len(universe.maturities("swap_libor")) == 36

    def test_basis_swaps_count(self, universe):
        assert len(universe.maturities("basis_swaps")) == 20

    def test_maturities_for_curve(self, universe):
        mats = universe.maturities_for_curve("USD", "SOFR")
        assert mats == universe.maturities("ois")

    def test_maturities_for_swap_curve(self, universe):
        mats = universe.maturities_for_curve("USD", "LIBOR")
        assert mats == universe.maturities("swap_libor")

    def test_unknown_key_raises(self, universe):
        with pytest.raises(KeyError):
            universe.maturities("unknown")


class TestBenchmarkHelpers:
    def test_primary_curve_usd(self, universe):
        assert universe.primary_curve("USD") == "SOFR"

    def test_primary_curve_gbp(self, universe):
        assert universe.primary_curve("GBP") == "SONIA"

    def test_primary_curve_eur(self, universe):
        assert universe.primary_curve("EUR") == "EUROSTR"

    def test_primary_curve_unknown(self, universe):
        assert universe.primary_curve("ZZZ") is None


class TestTagGeneration:
    def test_build_tags_ois(self, universe):
        tags = universe.build_tags("USD", "SOFR", "PAR", ["5Y", "10Y"])
        assert tags == ["RATES.OIS.USD_SOFR.PAR.5Y", "RATES.OIS.USD_SOFR.PAR.10Y"]

    def test_build_tags_swap(self, universe):
        tags = universe.build_tags("USD", "LIBOR", "PAR", ["5Y"])
        assert tags == ["RATES.SWAP_LIBOR.USD.PAR.5Y"]

    def test_build_tags_compound_index(self, universe):
        tags = universe.build_tags("JPY", "TONAR_JSCC", "PAR", ["3M"])
        assert tags == ["RATES.OIS.JPY_TONAR_JSCC.PAR.3M"]

    def test_build_tags_all_maturities(self, universe):
        tags = universe.build_tags("USD", "SOFR", "PAR")
        assert len(tags) == 44


class TestMultiTenorTagGeneration:
    """Tests for FWD / CURVES / BFLY multi-tenor tag generation."""

    def test_fwd_tags_use_combos(self, universe):
        """FWD tags should use multi_tenor_combos, not single maturities."""
        tags = universe.build_tags("USD", "SOFR", "FWD")
        # Should produce 6-part tags like RATES.OIS.USD_SOFR.FWD.5Y.5Y
        assert len(tags) > 0
        for tag in tags:
            parts = tag.split(".")
            assert len(parts) == 6, f"FWD tag should have 6 parts: {tag}"
            assert parts[3] == "FWD"

    def test_curves_tags_use_combos(self, universe):
        """CURVES tags should use multi_tenor_combos, not single maturities."""
        tags = universe.build_tags("USD", "SOFR", "CURVES")
        assert len(tags) > 0
        for tag in tags:
            parts = tag.split(".")
            assert len(parts) == 6, f"CURVES tag should have 6 parts: {tag}"
            assert parts[3] == "CURVES"

    def test_bfly_tags_use_combos(self, universe):
        """BFLY tags should use multi_tenor_combos with 3 legs."""
        tags = universe.build_tags("USD", "SOFR", "BFLY")
        assert len(tags) > 0
        for tag in tags:
            parts = tag.split(".")
            assert len(parts) == 7, f"BFLY tag should have 7 parts: {tag}"
            assert parts[3] == "BFLY"

    def test_fwd_specific_combos(self, universe):
        """Verify specific key forward combos are generated."""
        tags = universe.build_tags("USD", "SOFR", "FWD")
        assert "RATES.OIS.USD_SOFR.FWD.5Y.5Y" in tags
        assert "RATES.OIS.USD_SOFR.FWD.2Y.10Y" in tags
        assert "RATES.OIS.USD_SOFR.FWD.10Y.10Y" in tags
        assert "RATES.OIS.USD_SOFR.FWD.3Y.3Y" in tags
        assert "RATES.OIS.USD_SOFR.FWD.7Y.3Y" in tags

    def test_curves_specific_combos(self, universe):
        """Verify standard curve spreads are generated."""
        tags = universe.build_tags("USD", "SOFR", "CURVES")
        assert "RATES.OIS.USD_SOFR.CURVES.2Y.10Y" in tags
        assert "RATES.OIS.USD_SOFR.CURVES.5Y.30Y" in tags
        assert "RATES.OIS.USD_SOFR.CURVES.7Y.10Y" in tags
        assert "RATES.OIS.USD_SOFR.CURVES.10Y.20Y" in tags

    def test_bfly_specific_combos(self, universe):
        """Verify standard butterflies are generated."""
        tags = universe.build_tags("USD", "SOFR", "BFLY")
        assert "RATES.OIS.USD_SOFR.BFLY.2Y.5Y.10Y" in tags
        assert "RATES.OIS.USD_SOFR.BFLY.5Y.7Y.10Y" in tags
        assert "RATES.OIS.USD_SOFR.BFLY.3Y.5Y.10Y" in tags

    def test_fwd_swap_libor(self, universe):
        """FWD combos work for SWAP_LIBOR curves too."""
        tags = universe.build_tags("EUR", "EURIBOR", "FWD")
        assert len(tags) > 0
        assert "RATES.SWAP_LIBOR.EUR.FWD.5Y.5Y" in tags

    def test_par_unaffected(self, universe):
        """PAR tags should still use single maturities (no regression)."""
        tags = universe.build_tags("USD", "SOFR", "PAR")
        assert len(tags) == 44
        assert "RATES.OIS.USD_SOFR.PAR.5Y" in tags

    def test_fwd_with_explicit_tenors_override(self, universe):
        """Explicit tenors override multi-tenor combos."""
        tags = universe.build_tags("USD", "SOFR", "FWD", ["5Y"])
        assert tags == ["RATES.OIS.USD_SOFR.FWD.5Y"]

    def test_multi_tenor_combos_for(self, universe):
        """Helper method returns configured combos."""
        combos = universe.multi_tenor_combos_for("fwd")
        assert len(combos) > 0
        assert ["5Y", "5Y"] in combos

    def test_multi_tenor_combos_for_unknown(self, universe):
        """Unknown quote returns empty list."""
        assert universe.multi_tenor_combos_for("unknown") == []


class TestProviderLookups:
    def test_citi_prefix_ois(self, universe):
        assert universe.citi_prefix("USD", "SOFR") == "RATES.OIS.USD_SOFR"

    def test_citi_prefix_swap(self, universe):
        assert universe.citi_prefix("USD", "LIBOR") == "RATES.SWAP_LIBOR.USD"

    def test_resolve_prefix(self, universe):
        result = universe.resolve_prefix("RATES.OIS.USD_SOFR")
        assert result == ("USD", "SOFR")

    def test_resolve_prefix_swap(self, universe):
        result = universe.resolve_prefix("RATES.SWAP_LIBOR.USD")
        assert result == ("USD", "LIBOR")

    def test_resolve_prefix_unknown(self, universe):
        assert universe.resolve_prefix("RATES.OIS.XXX_YYY") is None


class TestCcyIndexPairs:
    def test_ois_pairs(self, universe):
        pairs = universe.ccy_index_pairs(target_only=False)
        assert len(pairs) > 0
        assert ("USD", "SOFR") in pairs
        assert ("USD", "FEDFUND") in pairs

    def test_swap_currencies(self, universe):
        ccys = universe.swap_currencies(target_only=False)
        assert "USD" in ccys
        assert "EUR" in ccys
        assert len(ccys) > 20


class TestBaseUniverseABC:
    def test_instruments(self, universe):
        instruments = universe.instruments()
        # 39 prior + 4 basis_swaps = 43
        assert len(instruments) == 43
        assert "USD.SOFR" in instruments

    def test_api_symbols(self, universe):
        symbols = universe.api_symbols()
        assert "RATES.OIS.USD_SOFR" in symbols


class TestBasisSwaps:
    """3s6s tenor basis swaps — tag layout `{prefix}.{TENOR}.{QUOTE}`."""

    def test_curves_loaded(self, universe):
        for ccy in ("USD", "EUR", "GBP", "AUD"):
            c = universe.get_curve(ccy, "3S6S_BASIS")
            assert c.type == "basis"
            assert c.providers["citi"]["instrument"] == "basis_swaps"

    def test_eur_aud_active(self, universe):
        assert universe.get_curve("EUR", "3S6S_BASIS").status == "active"
        assert universe.get_curve("AUD", "3S6S_BASIS").status == "active"

    def test_usd_gbp_ceased(self, universe):
        assert universe.get_curve("USD", "3S6S_BASIS").status == "ceased"
        assert universe.get_curve("GBP", "3S6S_BASIS").status == "ceased"

    def test_build_tags_tenor_first_order(self, universe):
        tags = universe.build_tags("EUR", "3S6S_BASIS", "BASIS_SPREAD", ["10Y"])
        # Quote comes LAST, not after the prefix
        assert tags == ["RATES.BASIS_SWAPS.3S6S_BASIS.EUR.SPOT.10Y.BASIS_SPREAD"]

    def test_build_tags_all_tenors(self, universe):
        tags = universe.build_tags("EUR", "3S6S_BASIS", "BASIS_SPREAD")
        assert len(tags) == 20  # 3M..30Y

    def test_par_returns_empty_on_basis_curve(self, universe):
        # Quote-not-supported -> empty (lets extractor loop without false tags)
        assert universe.build_tags("EUR", "3S6S_BASIS", "PAR") == []

    def test_basis_returns_empty_on_ois_curve(self, universe):
        assert universe.build_tags("USD", "SOFR", "BASIS_SPREAD") == []

    def test_resolve_prefix(self, universe):
        result = universe.resolve_prefix("RATES.BASIS_SWAPS.3S6S_BASIS.AUD.SPOT")
        assert result == ("AUD", "3S6S_BASIS")
