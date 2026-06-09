"""Pydantic schemas for bench rates domain validation."""
from __future__ import annotations

import math
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CentralBankCreate(BaseModel):
    """Schema for creating/seeding a central bank dimension row."""

    cb_code: str = Field(..., min_length=2, max_length=30)
    display_name: str = Field(..., min_length=3, max_length=60)
    currency: str = Field(..., min_length=3, max_length=3)
    country_code: str = Field(..., min_length=2, max_length=3)
    citi_tag: str = Field(..., min_length=10, max_length=60)

    @field_validator("cb_code")
    @classmethod
    def uppercase_cb_code(cls, v: str) -> str:
        return v.upper()

    @field_validator("currency")
    @classmethod
    def uppercase_currency(cls, v: str) -> str:
        return v.upper()

    @field_validator("country_code")
    @classmethod
    def uppercase_country_code(cls, v: str) -> str:
        return v.upper()


class BenchRateCreate(BaseModel):
    """Schema for creating a bench rate observation."""

    cb_id: int = Field(..., gt=0)
    vendor_id: int = Field(..., gt=0)
    obs_date: date
    rate: float

    @field_validator("rate")
    @classmethod
    def validate_rate_finite_and_in_range(cls, v: float) -> float:
        if not math.isfinite(v):
            raise ValueError(f"Rate must be finite; got {v}")
        if v < -2.0 or v > 20.0:
            raise ValueError(f"Rate {v} outside expected range [-2.0, 20.0]")
        return v


class CentralBankResponse(CentralBankCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: datetime


class BenchRateResponse(BenchRateCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: datetime
