"""Pydantic schemas for FX vol domain validation."""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

ALLOWED_STRIKES = {
    "ATM", "25RR", "10RR", "25STR", "10STR",
    "STRIKE_C10", "STRIKE_C25", "STRIKE_C35",
    "STRIKE_P10", "STRIKE_P25", "STRIKE_P35",
}
ALLOWED_VOL_TYPES = {"IMPLIED", "REALISED", "SPREAD"}
ALLOWED_CCY_CLASSES = {"g10", "em_ndf", "em_deliverable"}


class FXCurrencyPairCreate(BaseModel):
    """Schema for creating/seeding a currency pair dimension row."""

    base_ccy: str = Field(..., min_length=3, max_length=3)
    quote_ccy: str = Field(..., min_length=3, max_length=3)
    ccy_class: str = Field(..., min_length=2, max_length=20)

    @field_validator("base_ccy", "quote_ccy")
    @classmethod
    def uppercase_ccy(cls, v: str) -> str:
        return v.upper()

    @field_validator("ccy_class")
    @classmethod
    def valid_ccy_class(cls, v: str) -> str:
        v = v.lower()
        if v not in ALLOWED_CCY_CLASSES:
            msg = f"ccy_class must be one of {ALLOWED_CCY_CLASSES}, got '{v}'"
            raise ValueError(msg)
        return v


class FXVolCreate(BaseModel):
    """Schema for creating an FX vol observation row."""

    pair_id: int = Field(..., gt=0)
    obs_date: date
    strike: str = Field(..., min_length=2, max_length=15)
    tenor: str = Field(..., min_length=1, max_length=5)
    vol_type: str = Field(..., min_length=3, max_length=10)
    value: float

    @field_validator("strike")
    @classmethod
    def valid_strike(cls, v: str) -> str:
        v = v.upper()
        if v not in ALLOWED_STRIKES:
            msg = f"strike must be one of {ALLOWED_STRIKES}, got '{v}'"
            raise ValueError(msg)
        return v

    @field_validator("vol_type")
    @classmethod
    def valid_vol_type(cls, v: str) -> str:
        v = v.upper()
        if v not in ALLOWED_VOL_TYPES:
            msg = f"vol_type must be one of {ALLOWED_VOL_TYPES}, got '{v}'"
            raise ValueError(msg)
        return v


class FXCurrencyPairResponse(FXCurrencyPairCreate):
    """Schema for returning a currency pair."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class FXVolResponse(FXVolCreate):
    """Schema for returning an FX vol observation."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
