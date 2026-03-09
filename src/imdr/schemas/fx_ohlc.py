"""Pydantic schemas for FX OHLC bar validation."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

ALLOWED_SERIES = {"SPOT", "FORWARD_1M", "NDF_1M"}
ALLOWED_DEAL_TYPES = {"SPOT", "FORWARD", "NDF"}


class FXFactOHLCCreate(BaseModel):
    """Schema for creating/ingesting an FX OHLC bar."""

    ts: datetime
    symbol: str = Field(..., min_length=3, max_length=10)
    series: str = Field(..., min_length=1, max_length=30)
    tenor: str = Field(..., min_length=1, max_length=10)
    deal_type: str = Field(..., min_length=1, max_length=20)
    pair_used: str = Field(..., min_length=1, max_length=20)

    open_px: Decimal
    high_px: Decimal
    low_px: Decimal
    close_px: Decimal
    mid_px: Decimal
    mid_mean_px: Decimal
    mid_median_px: Decimal
    bid: Decimal
    ask: Decimal
    n_ticks: int = Field(..., gt=0)

    @field_validator("symbol")
    @classmethod
    def uppercase_symbol(cls, v: str) -> str:
        return v.upper()

    @field_validator("series")
    @classmethod
    def valid_series(cls, v: str) -> str:
        v = v.upper()
        if v not in ALLOWED_SERIES:
            msg = f"series must be one of {ALLOWED_SERIES}, got '{v}'"
            raise ValueError(msg)
        return v

    @field_validator("deal_type")
    @classmethod
    def valid_deal_type(cls, v: str) -> str:
        v = v.upper()
        if v not in ALLOWED_DEAL_TYPES:
            msg = f"deal_type must be one of {ALLOWED_DEAL_TYPES}, got '{v}'"
            raise ValueError(msg)
        return v

    @field_validator("low_px")
    @classmethod
    def low_lte_high(cls, v: Decimal, info: ValidationInfo) -> Decimal:
        high = info.data.get("high_px")
        if high is not None and v > high:
            msg = "low_px must be <= high_px"
            raise ValueError(msg)
        return v


class FXFactOHLCResponse(FXFactOHLCCreate):
    """Schema for returning FX OHLC bars."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
