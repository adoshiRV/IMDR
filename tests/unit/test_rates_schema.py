"""Tests for domains/rates/schema.py — tenor encoding, quote mappings."""

import pytest

from imdr.domains.rates.schema import (
    CITI_TO_QUOTE,
    MULTI_TENOR_LEGS,
    QUOTE_TO_CITI,
    SINGLE_TENOR_QUOTES,
    citi_to_quote,
    decode_tenor,
    display_tenor,
    encode_tenor,
    quote_to_citi,
    validate_quote,
)


# ── Tenor encoding ──────────────────────────────────────────────

class TestEncodeTenor:
    def test_single_par(self):
        assert encode_tenor(["5Y"], "par") == "5Y"

    def test_single_ssw(self):
        assert encode_tenor(["10Y"], "ssw") == "10Y"

    def test_single_rc(self):
        assert encode_tenor(["3M"], "rc") == "3M"

    def test_spread(self):
        assert encode_tenor(["2Y", "10Y"], "spread") == "2ys10ys"

    def test_fwd(self):
        assert encode_tenor(["5Y", "5Y"], "fwd") == "5ys5ys"

    def test_bfly(self):
        assert encode_tenor(["2Y", "5Y", "10Y"], "bfly") == "2ys5ys10ys"

    def test_months(self):
        assert encode_tenor(["3M", "6M"], "spread") == "3ms6ms"

    def test_mixed_units(self):
        assert encode_tenor(["3M", "5Y"], "fwd") == "3ms5ys"

    def test_wrong_legs_single_raises(self):
        with pytest.raises(ValueError, match="expects 1 leg"):
            encode_tenor(["2Y", "10Y"], "par")

    def test_wrong_legs_spread_raises(self):
        with pytest.raises(ValueError, match="expects 2 legs"):
            encode_tenor(["2Y"], "spread")

    def test_wrong_legs_bfly_raises(self):
        with pytest.raises(ValueError, match="expects 3 legs"):
            encode_tenor(["2Y", "10Y"], "bfly")

    def test_invalid_leg_raises(self):
        with pytest.raises(ValueError, match="Invalid tenor leg"):
            encode_tenor(["abc", "def"], "spread")

    def test_unknown_quote_raises(self):
        with pytest.raises(ValueError, match="Unknown quote type"):
            encode_tenor(["5Y"], "invalid")


# ── Tenor decoding ──────────────────────────────────────────────

class TestDecodeTenor:
    def test_single(self):
        assert decode_tenor("5Y", "par") == ["5Y"]

    def test_spread(self):
        assert decode_tenor("2ys10ys", "spread") == ["2Y", "10Y"]

    def test_fwd(self):
        assert decode_tenor("5ys5ys", "fwd") == ["5Y", "5Y"]

    def test_bfly(self):
        assert decode_tenor("2ys5ys10ys", "bfly") == ["2Y", "5Y", "10Y"]

    def test_roundtrip_all_quotes(self):
        cases = [
            (["5Y"], "par"),
            (["10Y"], "ssw"),
            (["3M"], "rc"),
            (["2Y", "10Y"], "spread"),
            (["5Y", "5Y"], "fwd"),
            (["2Y", "5Y", "10Y"], "bfly"),
        ]
        for legs, quote in cases:
            encoded = encode_tenor(legs, quote)
            decoded = decode_tenor(encoded, quote)
            assert decoded == [l.upper() for l in legs], f"Roundtrip failed for {legs}/{quote}"


# ── Display tenor ───────────────────────────────────────────────

class TestDisplayTenor:
    def test_single(self):
        assert display_tenor("5Y") == "5Y"

    def test_spread(self):
        assert display_tenor("2ys10ys", "spread") == "2s10s"

    def test_fwd(self):
        assert display_tenor("5ys5ys", "fwd") == "5y5y"

    def test_bfly(self):
        assert display_tenor("2ys5ys10ys", "bfly") == "2s5s10s"

    def test_months_spread(self):
        assert display_tenor("3ms6ms", "spread") == "3ms6ms"

    def test_infer_bfly(self):
        assert display_tenor("2ys5ys10ys") == "2s5s10s"

    def test_infer_fwd(self):
        # 2-leg without context defaults to fwd
        assert display_tenor("5ys5ys") == "5y5y"


# ── Quote validation ────────────────────────────────────────────

class TestQuoteValidation:
    def test_valid(self):
        assert validate_quote("par") == "par"

    def test_case_insensitive(self):
        assert validate_quote("PAR") == "par"

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            validate_quote("invalid")

    def test_quote_to_citi(self):
        assert quote_to_citi("spread") == "CURVES"
        assert quote_to_citi("par") == "PAR"
        assert quote_to_citi("bfly") == "BFLY"

    def test_citi_to_quote(self):
        assert citi_to_quote("BFLY") == "bfly"
        assert citi_to_quote("CURVES") == "spread"
        assert citi_to_quote("PAR") == "par"

    def test_citi_to_quote_invalid_raises(self):
        with pytest.raises(ValueError):
            citi_to_quote("UNKNOWN")

    def test_mappings_are_inverse(self):
        for internal, citi in QUOTE_TO_CITI.items():
            assert CITI_TO_QUOTE[citi] == internal
