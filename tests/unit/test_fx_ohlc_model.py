"""Tests for FX OHLC model and schema."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from imdr.models.fx_ohlc import FXFactOHLC
from imdr.schemas.fx_ohlc import ALLOWED_SERIES, FXFactOHLCCreate


def _valid_bar(**overrides) -> dict:
    """Return a valid bar dict with optional overrides."""
    base = {
        "ts": datetime(2026, 3, 9, 13, 0, tzinfo=timezone.utc),
        "symbol": "EURUSD",
        "series": "SPOT",
        "tenor": "SPOT",
        "deal_type": "SPOT",
        "pair_used": "EURUSD",
        "open_px": Decimal("1.08500000"),
        "high_px": Decimal("1.08700000"),
        "low_px": Decimal("1.08400000"),
        "close_px": Decimal("1.08600000"),
        "mid_px": Decimal("1.08600000"),
        "mid_mean_px": Decimal("1.08550000"),
        "mid_median_px": Decimal("1.08560000"),
        "bid": Decimal("1.08590000"),
        "ask": Decimal("1.08610000"),
        "n_ticks": 150,
    }
    base.update(overrides)
    return base


def test_model_tablename():
    assert FXFactOHLC.__tablename__ == "fact_ohlc"
    assert FXFactOHLC.__table_args__[-1] == {"schema": "fx"}


def test_schema_valid():
    bar = FXFactOHLCCreate.model_validate(_valid_bar())
    assert bar.symbol == "EURUSD"
    assert bar.series == "SPOT"
    assert bar.n_ticks == 150


def test_schema_uppercase_symbol():
    bar = FXFactOHLCCreate.model_validate(_valid_bar(symbol="eurusd"))
    assert bar.symbol == "EURUSD"


def test_schema_valid_series():
    for series in ALLOWED_SERIES:
        bar = FXFactOHLCCreate.model_validate(_valid_bar(series=series))
        assert bar.series == series


def test_schema_invalid_series():
    with pytest.raises(ValueError, match="series must be one of"):
        FXFactOHLCCreate.model_validate(_valid_bar(series="INVALID"))


def test_schema_invalid_deal_type():
    with pytest.raises(ValueError, match="deal_type must be one of"):
        FXFactOHLCCreate.model_validate(_valid_bar(deal_type="INVALID"))


def test_schema_n_ticks_positive():
    with pytest.raises(ValueError):
        FXFactOHLCCreate.model_validate(_valid_bar(n_ticks=0))


def test_schema_low_lte_high():
    with pytest.raises(ValueError, match="low_px must be <= high_px"):
        FXFactOHLCCreate.model_validate(_valid_bar(
            high_px=Decimal("1.08000000"),
            low_px=Decimal("1.09000000"),
        ))
