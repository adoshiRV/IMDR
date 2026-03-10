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
        assert len(universe.all_curves()) == 39

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
        assert len(instruments) == 39
        assert "USD.SOFR" in instruments

    def test_api_symbols(self, universe):
        symbols = universe.api_symbols()
        assert "RATES.OIS.USD_SOFR" in symbols
