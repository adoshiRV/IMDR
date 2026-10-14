"""Tests for the xccy_ois_swap curve-filter helpers in the historical/live scripts."""

from imdr.universe.rates import get_rates_universe
from scripts.rates.citi.rates_xccy_ois_citi_historical import (
    _xccy_ois_curves as _xccy_ois_curves_historical,
)
from scripts.rates.citi.rates_xccy_ois_citi_live import (
    _xccy_ois_curves as _xccy_ois_curves_live,
)


def universe():
    return get_rates_universe()


class TestHistoricalCurveFilter:
    def test_returns_90_pairs(self):
        curves = _xccy_ois_curves_historical(universe())
        assert len(curves) == 90

    def test_contains_eur_usd(self):
        curves = _xccy_ois_curves_historical(universe())
        assert ("EUR", "XCCY_OIS_VS_USD") in curves

    def test_all_tuples_are_g10(self):
        g10 = {"AUD", "CAD", "CHF", "EUR", "GBP", "JPY", "NOK", "NZD", "SEK", "USD"}
        for ccy, curve in _xccy_ois_curves_historical(universe()):
            assert ccy in g10
            assert curve.startswith("XCCY_OIS_VS_")


class TestLiveCurveFilter:
    def test_returns_90_active_curves(self):
        cohort = _xccy_ois_curves_live(universe())
        assert len(cohort) == 90
        assert all(c.status == "active" for c in cohort)

    def test_contains_gbp_usd(self):
        cohort = _xccy_ois_curves_live(universe())
        keys = [(c.ccy, c.curve) for c in cohort]
        assert ("GBP", "XCCY_OIS_VS_USD") in keys
