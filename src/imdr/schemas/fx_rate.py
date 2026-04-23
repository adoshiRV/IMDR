"""Pydantic schemas for fx.fact_fx_rate ingest validation."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ALLOWED_TENORS = {
    "SPOT", "ON", "1W", "1M", "3M", "6M", "9M", "1Y", "2Y", "5Y", "10Y",
}


class FXRateCreate(BaseModel):
    """Schema for creating an FX rate observation."""

    pair_id: int = Field(..., gt=0)
    vendor_id: int = Field(..., gt=0)
    frequency_id: int = Field(..., gt=0)
    obs_date: date
    tenor: str = Field(..., min_length=2, max_length=5)
    mid_rate: Decimal = Field(..., gt=0)
    fwd_points: Decimal | None = None

    @field_validator("tenor")
    @classmethod
    def validate_tenor(cls, v: str) -> str:
        v = v.upper()
        if v not in ALLOWED_TENORS:
            raise ValueError(f"tenor must be one of {sorted(ALLOWED_TENORS)}, got '{v}'")
        return v

    @model_validator(mode="after")
    def spot_has_no_points(self) -> FXRateCreate:
        if self.tenor == "SPOT" and self.fwd_points is not None:
            raise ValueError("fwd_points must be NULL for SPOT tenor rows")
        return self


class FXRateResponse(FXRateCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
