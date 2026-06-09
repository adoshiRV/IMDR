"""Tests for domains/rates/translate.py — tag ↔ internal schema translation."""

import pandas as pd
import pytest

from imdr.domains.rates.translate import (
    citi_response_to_df,
    citi_tag_to_internal,
    internal_to_citi_tags,
)
from imdr.domains.rates.utils import parse_x_to_ts_utc
from imdr.universe.rates import get_rates_universe


@pytest.fixture
def universe():
    return get_rates_universe()


# ── Tag → Internal ──────────────────────────────────────────────

class TestCitiTagToInternal:
    def test_ois_par(self, universe):
        result = citi_tag_to_internal("RATES.OIS.USD_SOFR.PAR.5Y", universe)
        assert result == {"ccy": "USD", "curve": "SOFR", "quote": "par", "tenor": "5Y"}

    def test_swap_libor_par(self, universe):
        result = citi_tag_to_internal("RATES.SWAP_LIBOR.USD.PAR.5Y", universe)
        assert result == {"ccy": "USD", "curve": "LIBOR", "quote": "par", "tenor": "5Y"}

    def test_multi_tenor_spread(self, universe):
        result = citi_tag_to_internal("RATES.OIS.USD_SOFR.CURVES.2Y.10Y", universe)
        assert result is not None
        assert result["quote"] == "spread"
        assert result["tenor"] == "2Y.10Y"

    def test_bfly(self, universe):
        result = citi_tag_to_internal("RATES.OIS.USD_SOFR.BFLY.2Y.5Y.10Y", universe)
        assert result is not None
        assert result["quote"] == "bfly"
        assert result["tenor"] == "2Y.5Y.10Y"

    def test_swap_spread(self, universe):
        result = citi_tag_to_internal("RATES.OIS.USD_SOFR.SWAP_SPREAD.5Y", universe)
        assert result is not None
        assert result["quote"] == "ssw"

    def test_unknown_tag_returns_none(self, universe):
        assert citi_tag_to_internal("UNKNOWN.TAG", universe) is None

    def test_unknown_prefix_returns_none(self, universe):
        assert citi_tag_to_internal("RATES.OIS.XXX_YYY.PAR.5Y", universe) is None

    def test_unknown_quote_type_returns_none(self, universe):
        assert citi_tag_to_internal("RATES.OIS.USD_SOFR.UNKNOWN.5Y", universe) is None

    def test_too_short_returns_none(self, universe):
        assert citi_tag_to_internal("RATES.OIS", universe) is None

    def test_compound_index(self, universe):
        result = citi_tag_to_internal("RATES.OIS.JPY_TONAR_JSCC.PAR.3M", universe)
        assert result is not None
        assert result["ccy"] == "JPY"
        assert result["curve"] == "TONAR_JSCC"

    def test_cny_ndirs(self, universe):
        result = citi_tag_to_internal("RATES.SWAP_LIBOR.CNY_NDIRS.PAR.5Y", universe)
        assert result is not None
        assert result["ccy"] == "CNY"
        assert result["curve"] == "NDIRS"

    def test_basis_swaps_3s6s(self, universe):
        # Quote LAST: {prefix}.{TENOR}.BASIS_SPREAD
        result = citi_tag_to_internal(
            "RATES.BASIS_SWAPS.3S6S_BASIS.AUD.SPOT.10Y.BASIS_SPREAD", universe,
        )
        assert result == {"ccy": "AUD", "curve": "3S6S_BASIS", "quote": "basis", "tenor": "10Y"}

    def test_basis_swaps_18m(self, universe):
        result = citi_tag_to_internal(
            "RATES.BASIS_SWAPS.3S6S_BASIS.EUR.SPOT.18M.BASIS_SPREAD", universe,
        )
        assert result is not None
        assert result["tenor"] == "18M"
        assert result["quote"] == "basis"

    def test_basis_swaps_unknown_prefix(self, universe):
        assert citi_tag_to_internal(
            "RATES.BASIS_SWAPS.ZZZ_BASIS.AUD.SPOT.5Y.BASIS_SPREAD", universe,
        ) is None

    def test_basis_swaps_too_short(self, universe):
        # Missing the trailing BASIS_SPREAD
        assert citi_tag_to_internal(
            "RATES.BASIS_SWAPS.3S6S_BASIS.AUD.SPOT.5Y", universe,
        ) is None


# ── Internal → Tag ──────────────────────────────────────────────

class TestInternalToCitiTags:
    def test_par_specific_tenors(self, universe):
        tags = internal_to_citi_tags("USD", "SOFR", "par", ["5Y", "10Y"], universe)
        assert tags == ["RATES.OIS.USD_SOFR.PAR.5Y", "RATES.OIS.USD_SOFR.PAR.10Y"]

    def test_swap_libor(self, universe):
        tags = internal_to_citi_tags("USD", "LIBOR", "par", ["5Y"], universe)
        assert tags == ["RATES.SWAP_LIBOR.USD.PAR.5Y"]

    def test_all_maturities(self, universe):
        tags = internal_to_citi_tags("USD", "SOFR", "par", universe=universe)
        assert len(tags) == 44  # OIS has 44 maturities

    def test_basis_swaps_roundtrip(self, universe):
        tags = internal_to_citi_tags("AUD", "3S6S_BASIS", "basis", ["10Y"], universe=universe)
        assert tags == ["RATES.BASIS_SWAPS.3S6S_BASIS.AUD.SPOT.10Y.BASIS_SPREAD"]


# ── Response → DataFrame ───────────────────────────────────────

class TestCitiResponseToDf:
    def test_basic(self, universe):
        resp = {
            "status": "OK",
            "body": {
                "RATES.OIS.USD_SOFR.PAR.5Y": {
                    "type": "LINE",
                    "x": [20240102, 20240103],
                    "c": [3.85, 3.87],
                }
            },
        }
        df = citi_response_to_df(resp, parse_x_to_ts_utc, universe)
        assert len(df) == 2
        assert list(df.columns) == ["ts", "ccy", "curve", "quote", "tenor", "value"]
        assert df["ccy"].iloc[0] == "USD"
        assert df["curve"].iloc[0] == "SOFR"
        assert df["value"].iloc[0] == 3.85

    def test_skips_errors(self, universe):
        resp = {
            "status": "OK",
            "body": {
                "RATES.OIS.USD_SOFR.PAR.5Y": {"type": "ERROR"}
            },
        }
        df = citi_response_to_df(resp, parse_x_to_ts_utc, universe)
        assert df.empty

    def test_skips_nulls(self, universe):
        resp = {
            "status": "OK",
            "body": {
                "RATES.OIS.USD_SOFR.PAR.5Y": {
                    "type": "LINE",
                    "x": [20240102, 20240103],
                    "c": [3.85, None],
                }
            },
        }
        df = citi_response_to_df(resp, parse_x_to_ts_utc, universe)
        assert len(df) == 1

    def test_not_ok_raises(self, universe):
        resp = {"status": "ERROR", "body": {}}
        with pytest.raises(RuntimeError, match="not OK"):
            citi_response_to_df(resp, parse_x_to_ts_utc, universe)

    def test_unknown_tag_skipped(self, universe):
        resp = {
            "status": "OK",
            "body": {
                "RATES.OIS.XXX_YYY.PAR.5Y": {
                    "type": "LINE",
                    "x": [20240102],
                    "c": [3.85],
                }
            },
        }
        df = citi_response_to_df(resp, parse_x_to_ts_utc, universe)
        assert df.empty
