from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator


class FXSpotRateBase(BaseModel):
    """Shared fields for FX spot rate schemas."""

    base_currency: str = Field(..., min_length=3, max_length=3)
    quote_currency: str = Field(..., min_length=3, max_length=3)
    rate_date: date
    mid: Decimal = Field(..., gt=0)
    bid: Decimal | None = Field(None, gt=0)
    ask: Decimal | None = Field(None, gt=0)
    source: str = Field(..., min_length=1, max_length=50)
    observed_at: datetime | None = None

    @field_validator("base_currency", "quote_currency")
    @classmethod
    def uppercase_currency(cls, v: str) -> str:
        return v.upper()

    @field_validator("ask")
    @classmethod
    def ask_gte_bid(cls, v: Decimal | None, info: ValidationInfo) -> Decimal | None:
        bid = info.data.get("bid")
        if v is not None and bid is not None and v < bid:
            msg = "ask must be >= bid"
            raise ValueError(msg)
        return v


class FXSpotRateCreate(FXSpotRateBase):
    """Schema for ingesting/creating FX spot rates."""


class FXSpotRateResponse(FXSpotRateBase):
    """Schema for returning FX spot rates."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class FXSpotRateBulkCreate(BaseModel):
    """Schema for bulk ingestion."""

    rates: list[FXSpotRateCreate] = Field(..., min_length=1)
