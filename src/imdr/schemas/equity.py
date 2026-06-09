"""Pydantic schemas for equity domain validation."""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ── VIX tickers ─────────────────────────────────────────────────────

VIX_TICKERS = {"VIX", "VIX3M", "VIX9D", "VVIX", "VXN"}


# ── Dimension schemas ───────────────────────────────────────────────


class IndexCreate(BaseModel):
    """Schema for creating/seeding an equity index dimension row."""

    ticker: str = Field(..., min_length=2, max_length=20)
    display_name: str = Field(..., min_length=2, max_length=60)
    currency: str = Field(..., min_length=3, max_length=3)
    region: str = Field(..., min_length=2, max_length=20)
    citi_tag: str | None = Field(default=None, max_length=80)
    country_code: str = Field(..., min_length=2, max_length=3)

    @field_validator("ticker")
    @classmethod
    def uppercase_ticker(cls, v: str) -> str:
        return v.upper()

    @field_validator("currency")
    @classmethod
    def uppercase_currency(cls, v: str) -> str:
        return v.upper()

    @field_validator("country_code")
    @classmethod
    def uppercase_country_code(cls, v: str) -> str:
        return v.upper()


# ── Fact schemas ────────────────────────────────────────────────────


class IndexLevelCreate(BaseModel):
    """Schema for creating an equity index level observation."""

    index_id: int = Field(..., gt=0)
    obs_date: date
    close_level: float


class VixCreate(BaseModel):
    """Schema for creating a VIX family observation."""

    ticker: str = Field(..., min_length=2, max_length=10)
    obs_date: date
    close_level: float

    @field_validator("ticker")
    @classmethod
    def uppercase_ticker(cls, v: str) -> str:
        return v.upper()


# ── Response schemas ────────────────────────────────────────────────


class IndexResponse(IndexCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: datetime


class IndexLevelResponse(IndexLevelCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: datetime


class VixResponse(VixCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: datetime
