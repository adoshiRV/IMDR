"""Pydantic schemas for rates swaption skew domain validation."""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

ALLOWED_STRIKE_OFFSETS = {-200, -150, -100, -75, -50, -25, 25, 50, 75, 100, 150, 200}


class RatesSkewSurfaceCreate(BaseModel):
    """Schema for creating/seeding a skew surface dimension row."""

    ccy: str = Field(..., min_length=2, max_length=3)
    option_expiry: str = Field(..., min_length=2, max_length=4)

    @field_validator("ccy")
    @classmethod
    def uppercase_ccy(cls, v: str) -> str:
        return v.upper()


class RatesSwaptionSkewCreate(BaseModel):
    """Schema for creating a swaption skew observation row."""

    surface_id: int = Field(..., gt=0)
    vendor_id: int = Field(..., gt=0)
    obs_date: date
    swap_tenor: str = Field(..., min_length=2, max_length=4)
    strike_offset: int
    vol: float

    @field_validator("strike_offset")
    @classmethod
    def valid_strike_offset(cls, v: int) -> int:
        if v not in ALLOWED_STRIKE_OFFSETS:
            msg = f"strike_offset must be one of {sorted(ALLOWED_STRIKE_OFFSETS)}, got {v}"
            raise ValueError(msg)
        return v


class RatesSkewSurfaceResponse(RatesSkewSurfaceCreate):
    """Schema for returning a skew surface dimension row."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class RatesSwaptionSkewResponse(RatesSwaptionSkewCreate):
    """Schema for returning a swaption skew observation."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
