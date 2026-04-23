"""Unit tests for equity Pydantic schemas."""
from __future__ import annotations

from datetime import date

import pytest

from imdr.schemas.equity import IndexCreate, IndexLevelCreate, VixCreate


class TestIndexCreate:
    def test_valid(self):
        ic = IndexCreate(
            ticker="SPX",
            display_name="S&P 500",
            currency="USD",
            region="us",
        )
        assert ic.ticker == "SPX"
        assert ic.currency == "USD"

    def test_uppercase_ticker(self):
        ic = IndexCreate(
            ticker="spx",
            display_name="S&P 500",
            currency="usd",
            region="us",
        )
        assert ic.ticker == "SPX"
        assert ic.currency == "USD"

    def test_with_citi_tag(self):
        ic = IndexCreate(
            ticker="SPX",
            display_name="S&P 500",
            currency="USD",
            region="us",
            citi_tag="EQUITY.EQUITY_INDEX..SPX.LEVEL.REUTERS",
        )
        assert ic.citi_tag == "EQUITY.EQUITY_INDEX..SPX.LEVEL.REUTERS"

    def test_with_market_code(self):
        ic = IndexCreate(
            ticker="N225",
            display_name="Nikkei 225",
            currency="JPY",
            region="asia_pacific",
            market_code="JP",
        )
        assert ic.market_code == "JP"

    def test_market_code_optional(self):
        ic = IndexCreate(
            ticker="SPX",
            display_name="S&P 500",
            currency="USD",
            region="us",
        )
        assert ic.market_code is None

    def test_ticker_too_short(self):
        with pytest.raises(Exception):
            IndexCreate(ticker="X", display_name="Test", currency="USD", region="us")


class TestIndexLevelCreate:
    def test_valid(self):
        ilc = IndexLevelCreate(index_id=1, obs_date=date(2026, 3, 25), close_level=5432.10)
        assert ilc.index_id == 1
        assert ilc.close_level == 5432.10

    def test_invalid_index_id(self):
        with pytest.raises(Exception):
            IndexLevelCreate(index_id=0, obs_date=date(2026, 3, 25), close_level=100.0)


class TestVixCreate:
    def test_valid(self):
        vc = VixCreate(ticker="VIX", obs_date=date(2026, 3, 25), close_level=18.5)
        assert vc.ticker == "VIX"

    def test_uppercase_ticker(self):
        vc = VixCreate(ticker="vix", obs_date=date(2026, 3, 25), close_level=18.5)
        assert vc.ticker == "VIX"

    def test_vvix(self):
        vc = VixCreate(ticker="VVIX", obs_date=date(2026, 3, 25), close_level=95.0)
        assert vc.ticker == "VVIX"
