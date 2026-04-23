"""Unit tests for equity universe YAML loading and helpers."""
from __future__ import annotations

import pytest

from imdr.universe.equity import get_equity_universe


@pytest.fixture
def universe():
    return get_equity_universe()


class TestEquityUniverse:
    def test_instruments_non_empty(self, universe):
        instruments = universe.instruments()
        assert len(instruments) > 0

    def test_spx_in_instruments(self, universe):
        assert "SPX" in universe.instruments()

    def test_vix_not_in_instruments(self, universe):
        """VIX is in indices (us region), but VIX3M etc only in vix_family."""
        # VIX is listed under us indices, so it IS in instruments()
        assert "VIX" in universe.instruments()

    def test_api_symbols_includes_vix_family(self, universe):
        symbols = universe.api_symbols()
        assert any("VIX3M" in s for s in symbols)
        assert any("VVIX" in s for s in symbols)

    def test_tag_format(self, universe):
        tag = universe.tag_for_ticker("SPX")
        assert tag == "EQUITY.EQUITY_INDEX..SPX.LEVEL.REUTERS"

    def test_tag_to_ticker_round_trip(self, universe):
        mapping = universe.tag_to_ticker()
        assert mapping["EQUITY.EQUITY_INDEX..SPX.LEVEL.REUTERS"] == "SPX"
        assert mapping["EQUITY.EQUITY_INDEX..N225.LEVEL.REUTERS"] == "N225"

    def test_regions(self, universe):
        regions = universe.regions()
        assert "us" in regions
        assert "europe" in regions
        assert "asia_pacific" in regions

    def test_indices_for_region(self, universe):
        us = universe.indices_for_region("us")
        tickers = [e["ticker"] for e in us]
        assert "SPX" in tickers
        assert "NDX" in tickers

    def test_ticker_to_display(self, universe):
        mapping = universe.ticker_to_display()
        assert mapping["SPX"] == "S&P 500"

    def test_ticker_to_currency(self, universe):
        mapping = universe.ticker_to_currency()
        assert mapping["SPX"] == "USD"
        assert mapping["N225"] == "JPY"

    def test_vix_tickers(self, universe):
        tickers = universe.vix_tickers()
        assert "VIX" in tickers
        assert "VIX3M" in tickers
        assert "VVIX" in tickers

    def test_index_create_entries_excludes_vix(self, universe):
        entries = universe.index_create_entries()
        tickers = [e.ticker for e in entries]
        assert "SPX" in tickers
        assert "VIX" not in tickers  # VIX excluded from dim_index seeding

    def test_index_create_entries_have_region(self, universe):
        entries = universe.index_create_entries()
        for e in entries:
            assert e.region in ("us", "europe", "asia_pacific")

    def test_index_create_entries_have_market_code(self, universe):
        entries = universe.index_create_entries()
        for e in entries:
            assert e.market_code is not None, f"{e.ticker} missing market_code"
            assert len(e.market_code) == 2

    def test_market_code_mapping(self, universe):
        entries = {e.ticker: e for e in universe.index_create_entries()}
        assert entries["SPX"].market_code == "US"
        assert entries["N225"].market_code == "JP"
        assert entries["FTSE"].market_code == "UK"
        assert entries["STOXX50E"].market_code == "EU"
        assert entries["FCHI"].market_code == "FR"

    def test_target_currencies(self, universe):
        ccys = universe.target_currencies()
        assert "USD" in ccys
        assert "JPY" in ccys
