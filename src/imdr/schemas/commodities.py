"""Pydantic schemas for commodities domain validation."""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

ALLOWED_COMMODITY_CLASSES = {"precious_metal", "energy"}

ALLOWED_STRIKES = {
    "ATM", "10RR", "25RR", "35RR",
    "10STR", "25STR", "35STR",
    "C10", "C25", "C35",
    "P10", "P25", "P35",
    "SVVSTAR", "SVXI", "XI",
    "BID", "ASK", "ATMF",
}


# ── Dimension schemas ────────────────────────────────────────────────


class CommodityCreate(BaseModel):
    """Schema for creating/seeding a commodity dimension row."""

    symbol: str = Field(..., min_length=2, max_length=20)
    display_name: str = Field(..., min_length=2, max_length=60)
    commodity_class: str = Field(..., min_length=3, max_length=20)
    spot_tag: str | None = Field(default=None, max_length=60)

    @field_validator("symbol")
    @classmethod
    def uppercase_symbol(cls, v: str) -> str:
        return v.upper()

    @field_validator("commodity_class")
    @classmethod
    def valid_class(cls, v: str) -> str:
        v = v.lower()
        if v not in ALLOWED_COMMODITY_CLASSES:
            msg = f"commodity_class must be one of {ALLOWED_COMMODITY_CLASSES}, got '{v}'"
            raise ValueError(msg)
        return v


class EIASeriesCreate(BaseModel):
    """Schema for creating/seeding an EIA series dimension row."""

    series_name: str = Field(..., min_length=3, max_length=30)
    region: str = Field(..., min_length=3, max_length=20)
    series_units: str = Field(default="", max_length=40)

    @field_validator("series_name", "region")
    @classmethod
    def uppercase_fields(cls, v: str) -> str:
        return v.upper()


# ── Fact schemas ─────────────────────────────────────────────────────


class SpotCreate(BaseModel):
    """Schema for creating a commodity spot observation row."""

    commodity_id: int = Field(..., gt=0)
    obs_date: date
    price: float


class EIACreate(BaseModel):
    """Schema for creating an EIA observation row."""

    eia_series_id: int = Field(..., gt=0)
    obs_date: date
    stat_value: float


class ImpliedVolCreate(BaseModel):
    """Schema for creating a commodity implied vol observation row."""

    commodity_id: int = Field(..., gt=0)
    obs_date: date
    strike: str = Field(..., min_length=2, max_length=15)
    tenor: str = Field(..., min_length=1, max_length=15)
    vol: float

    @field_validator("strike")
    @classmethod
    def valid_strike(cls, v: str) -> str:
        v = v.upper()
        if v not in ALLOWED_STRIKES:
            msg = f"strike must be one of {ALLOWED_STRIKES}, got '{v}'"
            raise ValueError(msg)
        return v


# ── Response schemas ─────────────────────────────────────────────────


class CommodityResponse(CommodityCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: datetime


class EIASeriesResponse(EIASeriesCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: datetime


class SpotResponse(SpotCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: datetime


class EIAResponse(EIACreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: datetime


class ImpliedVolResponse(ImpliedVolCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: datetime
