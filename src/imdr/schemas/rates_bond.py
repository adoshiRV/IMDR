"""Pydantic schemas for bond ingest validation.

Track A (CMT / BBG_mirror): ``BondYieldCreate``.
Track B (ISIN / Govy Monitor): ``BondInstrumentCreate``, ``BondInstrumentObsCreate``,
``BondAuctionCreate``.

See docs/admin/development/govt_bond_population.md.
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator

BOND_YIELD_QUOTE_TYPES = {
    "YIELD", "PRICE", "SPREAD", "CARRY", "DURATION", "CONVEXITY", "BREAKEVEN", "FWD_PREMIUM",
}
INSTRUMENT_QUOTE_TYPES = {"YIELD", "ASW", "PRICE"}
BOND_UNITS = {"PCT", "BP", "YR", "YR2", "PRICE"}


# ── Track A — constant-maturity ──────────────────────────────────────────

class BondYieldCreate(BaseModel):
    """One CMT bond-yield observation (rates.fact_bond_yield)."""

    bond_curve_id: int = Field(..., gt=0)
    vendor_id: int = Field(..., gt=0)
    frequency_id: int = Field(..., gt=0)
    obs_date: date
    obs_ts: datetime
    tenor_code: str = Field(..., min_length=1, max_length=10)
    tenor_days: int = Field(..., gt=0)
    quote_type: str = Field(..., max_length=20)
    spread_anchor: str = Field(default="NONE", max_length=20)
    fwd_start: str = Field(default="SPOT", max_length=10)
    horizon: str = Field(default="NONE", max_length=10)
    value: float
    units: str = Field(..., max_length=10)
    source_ticker: str = Field(..., min_length=1, max_length=80)

    @field_validator("quote_type")
    @classmethod
    def valid_quote_type(cls, v: str) -> str:
        v = v.upper()
        if v not in BOND_YIELD_QUOTE_TYPES:
            raise ValueError(f"quote_type must be one of {BOND_YIELD_QUOTE_TYPES}, got '{v}'")
        return v

    @field_validator("units")
    @classmethod
    def valid_units(cls, v: str) -> str:
        v = v.upper()
        if v not in BOND_UNITS:
            raise ValueError(f"units must be one of {BOND_UNITS}, got '{v}'")
        return v


# ── Track B — ISIN grain ─────────────────────────────────────────────────

class BondInstrumentCreate(BaseModel):
    """One ISIN-level bond identity row (dbo.dim_bond_instrument)."""

    isin: str = Field(..., min_length=6, max_length=20)
    bbg_ticker: str | None = Field(default=None, max_length=30)
    country_id: int = Field(..., gt=0)
    ccy: str = Field(..., min_length=3, max_length=3)
    issuer_code: str = Field(..., min_length=1, max_length=30)
    bond_curve_id: int | None = Field(default=None, gt=0)
    description: str | None = Field(default=None, max_length=200)
    coupon: float | None = None
    maturity_date: date | None = None

    @field_validator("ccy")
    @classmethod
    def uppercase_ccy(cls, v: str) -> str:
        return v.upper()


class BondInstrumentObsCreate(BaseModel):
    """One per-bond observation (rates.fact_bond_instrument_obs)."""

    instrument_id: int = Field(..., gt=0)
    vendor_id: int = Field(..., gt=0)
    frequency_id: int = Field(..., gt=0)
    obs_date: date
    obs_ts: datetime
    quote_type: str = Field(..., max_length=20)
    tenor_years: float
    value: float
    chg_1d: float | None = None
    chg_1w: float | None = None
    chg_1m: float | None = None
    chg_3m: float | None = None
    pricing_source: str = Field(..., min_length=1, max_length=12)
    units: str = Field(..., max_length=10)
    source_app: str = Field(default="GOVY_MONITOR", max_length=20)

    @field_validator("quote_type")
    @classmethod
    def valid_quote_type(cls, v: str) -> str:
        v = v.upper()
        if v not in INSTRUMENT_QUOTE_TYPES:
            raise ValueError(f"quote_type must be one of {INSTRUMENT_QUOTE_TYPES}, got '{v}'")
        return v


class BondAuctionCreate(BaseModel):
    """One auction-calendar row (rates.fact_bond_auction)."""

    country_id: int = Field(..., gt=0)
    auction_date: date
    security_type: str = Field(default="", max_length=30)
    term: str = Field(default="", max_length=10)
    isin: str = Field(default="", max_length=20)
    cusip: str | None = Field(default=None, max_length=20)
    coupon: float | None = None
    maturity_date: date | None = None
    reopening: bool | None = None
    offered_amount: float | None = None
    currency_id: int | None = Field(default=None, gt=0)
    source: str | None = Field(default=None, max_length=30)
    fetched_at: datetime
