"""Pydantic schemas for rates swaption vol domain validation."""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

ALLOWED_DATA_TYPES = {
    "ATM", "ATM_RFR", "REALIZED", "REALIZED_RFR", "VOL_RATIO", "VOL_RATIO_RFR",
}
ALLOWED_QUOTE_TYPES = {"BLACK", "NORMAL", "FWDPREMIUM", "PREMIUM", ""}
ALLOWED_FREQS = {"ANNUAL", "DAILY", ""}


class RatesVolSurfaceCreate(BaseModel):
    """Schema for creating/seeding a vol surface dimension row."""

    ccy: str = Field(..., min_length=2, max_length=3)
    data_type: str = Field(..., min_length=2, max_length=15)
    quote_type: str = Field(default="", max_length=12)
    vol_window: str = Field(default="", max_length=3)
    freq: str = Field(default="", max_length=6)
    is_rfr: bool = False

    @field_validator("ccy")
    @classmethod
    def uppercase_ccy(cls, v: str) -> str:
        return v.upper()

    @field_validator("data_type")
    @classmethod
    def valid_data_type(cls, v: str) -> str:
        v = v.upper()
        if v not in ALLOWED_DATA_TYPES:
            msg = f"data_type must be one of {ALLOWED_DATA_TYPES}, got '{v}'"
            raise ValueError(msg)
        return v

    @field_validator("quote_type")
    @classmethod
    def valid_quote_type(cls, v: str) -> str:
        v = v.upper() if v else ""
        if v not in ALLOWED_QUOTE_TYPES:
            msg = f"quote_type must be one of {ALLOWED_QUOTE_TYPES}, got '{v}'"
            raise ValueError(msg)
        return v

    @field_validator("freq")
    @classmethod
    def valid_freq(cls, v: str) -> str:
        v = v.upper() if v else ""
        if v not in ALLOWED_FREQS:
            msg = f"freq must be one of {ALLOWED_FREQS}, got '{v}'"
            raise ValueError(msg)
        return v


class RatesSwaptionVolCreate(BaseModel):
    """Schema for creating a swaption vol observation row."""

    surface_id: int = Field(..., gt=0)
    obs_date: date
    option_expiry: str = Field(..., min_length=2, max_length=4)
    swap_tenor: str = Field(..., min_length=2, max_length=4)
    value: float


class RatesVolSurfaceResponse(RatesVolSurfaceCreate):
    """Schema for returning a vol surface dimension row."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class RatesSwaptionVolResponse(RatesSwaptionVolCreate):
    """Schema for returning a swaption vol observation."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
