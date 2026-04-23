"""Unit tests for equity index tag parsing (translate module)."""
from __future__ import annotations

import pytest

from imdr.domains.equity.translate_index import citi_index_tag_to_internal


class TestIndexTagParsing:
    """Test EQUITY.EQUITY_INDEX..{TICKER}.LEVEL.REUTERS tag parsing."""

    def test_spx_tag(self):
        result = citi_index_tag_to_internal("EQUITY.EQUITY_INDEX..SPX.LEVEL.REUTERS")
        assert result == {"ticker": "SPX"}

    def test_ndx_tag(self):
        result = citi_index_tag_to_internal("EQUITY.EQUITY_INDEX..NDX.LEVEL.REUTERS")
        assert result == {"ticker": "NDX"}

    def test_n225_tag(self):
        result = citi_index_tag_to_internal("EQUITY.EQUITY_INDEX..N225.LEVEL.REUTERS")
        assert result == {"ticker": "N225"}

    def test_vix_tag(self):
        result = citi_index_tag_to_internal("EQUITY.EQUITY_INDEX..VIX.LEVEL.REUTERS")
        assert result == {"ticker": "VIX"}

    def test_stoxx50e_tag(self):
        result = citi_index_tag_to_internal("EQUITY.EQUITY_INDEX..STOXX50E.LEVEL.REUTERS")
        assert result == {"ticker": "STOXX50E"}

    def test_invalid_prefix(self):
        assert citi_index_tag_to_internal("FX.EQUITY_INDEX..SPX.LEVEL.REUTERS") is None

    def test_invalid_category(self):
        assert citi_index_tag_to_internal("EQUITY.SOMETHING..SPX.LEVEL.REUTERS") is None

    def test_wrong_qualifier(self):
        assert citi_index_tag_to_internal("EQUITY.EQUITY_INDEX..SPX.OHLC.REUTERS") is None

    def test_wrong_source(self):
        assert citi_index_tag_to_internal("EQUITY.EQUITY_INDEX..SPX.LEVEL.CITI") is None

    def test_too_few_parts(self):
        assert citi_index_tag_to_internal("EQUITY.EQUITY_INDEX.SPX") is None

    def test_too_many_parts(self):
        assert citi_index_tag_to_internal("EQUITY.EQUITY_INDEX..SPX.LEVEL.REUTERS.EXTRA") is None

    def test_empty_ticker(self):
        # Tag: EQUITY.EQUITY_INDEX...LEVEL.REUTERS (empty ticker)
        assert citi_index_tag_to_internal("EQUITY.EQUITY_INDEX...LEVEL.REUTERS") is None
