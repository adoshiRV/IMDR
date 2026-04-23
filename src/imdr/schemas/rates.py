"""Pydantic schemas for rates domain validation."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

ALLOWED_QUOTES = {"par", "spread", "fwd", "bfly", "ssw", "rc"}
ALLOWED_CURVE_TYPES = {"rfr", "ibor"}
ALLOWED_CURVE_STATUSES = {"active", "ceased", "reformed"}


class RatesCurveCreate(BaseModel):
    """Schema for creating/seeding a rates curve dimension row."""

    ccy: str = Field(..., min_length=2, max_length=10)
    curve: str = Field(..., min_length=1, max_length=30)
    curve_type: str = Field(..., min_length=1, max_length=10)
    curve_status: str = Field(..., min_length=1, max_length=10)
    instrument: str = Field(..., min_length=1, max_length=20)
    citi_prefix: str = Field(..., min_length=1, max_length=60)
    cessation_date: date | None = None
    primary_from: date | None = None
    supersedes: str | None = None
    superseded_by: str | None = None
    notes: str | None = None

    @field_validator("ccy")
    @classmethod
    def uppercase_ccy(cls, v: str) -> str:
        return v.upper()

    @field_validator("curve_type")
    @classmethod
    def valid_curve_type(cls, v: str) -> str:
        v = v.lower()
        if v not in ALLOWED_CURVE_TYPES:
            msg = f"curve_type must be one of {ALLOWED_CURVE_TYPES}, got '{v}'"
            raise ValueError(msg)
        return v

    @field_validator("curve_status")
    @classmethod
    def valid_curve_status(cls, v: str) -> str:
        v = v.lower()
        if v not in ALLOWED_CURVE_STATUSES:
            msg = f"curve_status must be one of {ALLOWED_CURVE_STATUSES}, got '{v}'"
            raise ValueError(msg)
        return v


class RatesObservationCreate(BaseModel):
    """Schema for creating a rates observation row."""

    curve_id: int = Field(..., gt=0)
    ts: datetime
    quote: str = Field(..., min_length=1, max_length=10)
    tenor: str = Field(..., min_length=1, max_length=30)
    value: float
    frequency_id: int = Field(..., gt=0)

    @field_validator("quote")
    @classmethod
    def valid_quote(cls, v: str) -> str:
        v = v.lower()
        if v not in ALLOWED_QUOTES:
            msg = f"quote must be one of {ALLOWED_QUOTES}, got '{v}'"
            raise ValueError(msg)
        return v


class RatesCurveResponse(RatesCurveCreate):
    """Schema for returning a rates curve."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class RatesObservationResponse(RatesObservationCreate):
    """Schema for returning a rates observation."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
