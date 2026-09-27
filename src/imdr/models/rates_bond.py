"""Bond ORM models.

Covers the two grains:
  - **Curve / constant-maturity** (Track A, BBG_mirror): ``dim_bond_curve`` (dbo)
    → ``dim_bond_source`` (rates) → ``fact_bond_yield`` (rates). Schema applied
    by migrations 063/065/067; these classes map the existing tables (previously
    unmodelled).
  - **ISIN / per-bond** (Track B, Govy Monitor): ``dim_bond_instrument`` (dbo) →
    ``fact_bond_instrument_obs`` (rates), plus ``fact_bond_auction`` (rates).
    Schema in migrations 112/113/114.

Design: docs/admin/rates/sov_bond_design.md + docs/admin/development/govt_bond_population.md.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.mssql import DATETIMEOFFSET, TINYINT
from sqlalchemy.orm import Mapped, mapped_column

from imdr.models.base import Base


# ── Track A — curve / constant-maturity grain (existing tables) ──────────

class DimBondCurve(Base):
    """Logical bond curve identity — one row per (ccy, issuer, yield_type, kind)."""

    __tablename__ = "dim_bond_curve"
    __table_args__ = (
        UniqueConstraint("curve_code", name="uq_dim_bond_curve_code"),
        {"schema": "dbo"},
    )

    country_id: Mapped[int] = mapped_column(
        TINYINT, ForeignKey("dbo.dim_country.id"), nullable=False
    )
    ccy: Mapped[str] = mapped_column(String(3), nullable=False)
    issuer_class: Mapped[str] = mapped_column(String(20), nullable=False)
    issuer_code: Mapped[str] = mapped_column(String(30), nullable=False)
    yield_type: Mapped[str] = mapped_column(String(20), nullable=False)
    benchmark_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    curve_code: Mapped[str] = mapped_column(String(40), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    primary_vendor_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("dbo.dim_vendor.id"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)


class DimBondSource(Base):
    """Vendor→curve resolution — one row per (vendor, source_ticker)."""

    __tablename__ = "dim_bond_source"
    __table_args__ = (
        UniqueConstraint("vendor_id", "source_ticker", name="uq_dim_bond_source_ticker"),
        {"schema": "rates"},
    )

    bond_curve_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("dbo.dim_bond_curve.id"), nullable=False
    )
    vendor_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("dbo.dim_vendor.id"), nullable=False
    )
    source_ticker: Mapped[str] = mapped_column(String(80), nullable=False)
    tenor_code: Mapped[str] = mapped_column(String(10), nullable=False)
    tenor_days: Mapped[int] = mapped_column(Integer, nullable=False)
    quote_type: Mapped[str] = mapped_column(String(20), nullable=False)
    spread_anchor: Mapped[str] = mapped_column(String(20), nullable=False, default="NONE")
    fwd_start: Mapped[str] = mapped_column(String(10), nullable=False, default="SPOT")
    horizon: Mapped[str] = mapped_column(String(10), nullable=False, default="NONE")
    units: Mapped[str] = mapped_column(String(10), nullable=False)
    vendor_field: Mapped[str | None] = mapped_column(String(30), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)


class FactBondYield(Base):
    """Constant-maturity bond-yield observations (Track A / BBG_mirror)."""

    __tablename__ = "fact_bond_yield"
    __table_args__ = (
        UniqueConstraint(
            "bond_curve_id", "vendor_id", "obs_date", "tenor_code",
            "quote_type", "spread_anchor", "fwd_start", "horizon",
            name="uq_fact_bond_yield",
        ),
        {"schema": "rates"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    bond_curve_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("dbo.dim_bond_curve.id"), nullable=False
    )
    vendor_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("dbo.dim_vendor.id"), nullable=False
    )
    frequency_id: Mapped[int] = mapped_column(
        TINYINT, ForeignKey("dbo.dim_frequency.id"), nullable=False
    )
    obs_date: Mapped[date] = mapped_column(Date, nullable=False)
    obs_ts: Mapped[datetime] = mapped_column(DATETIMEOFFSET, nullable=False)
    tenor_code: Mapped[str] = mapped_column(String(10), nullable=False)
    tenor_days: Mapped[int] = mapped_column(Integer, nullable=False)
    quote_type: Mapped[str] = mapped_column(String(20), nullable=False)
    spread_anchor: Mapped[str] = mapped_column(String(20), nullable=False, default="NONE")
    fwd_start: Mapped[str] = mapped_column(String(10), nullable=False, default="SPOT")
    horizon: Mapped[str] = mapped_column(String(10), nullable=False, default="NONE")
    value: Mapped[float] = mapped_column(Float, nullable=False)
    units: Mapped[str] = mapped_column(String(10), nullable=False)
    source_ticker: Mapped[str] = mapped_column(String(80), nullable=False)


# ── Track B — ISIN / per-bond grain (Govy Monitor) ───────────────────────

class DimBondInstrument(Base):
    """ISIN-level bond identity — one row per individual security."""

    __tablename__ = "dim_bond_instrument"
    __table_args__ = (
        UniqueConstraint("isin", name="uq_dim_bond_instrument_isin"),
        {"schema": "dbo"},
    )

    isin: Mapped[str] = mapped_column(String(20), nullable=False)
    bbg_ticker: Mapped[str | None] = mapped_column(String(30), nullable=True)
    country_id: Mapped[int] = mapped_column(
        TINYINT, ForeignKey("dbo.dim_country.id"), nullable=False
    )
    ccy: Mapped[str] = mapped_column(String(3), nullable=False)
    issuer_code: Mapped[str] = mapped_column(String(30), nullable=False)
    bond_curve_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("dbo.dim_bond_curve.id"), nullable=True
    )
    description: Mapped[str | None] = mapped_column(String(200), nullable=True)
    coupon: Mapped[float | None] = mapped_column(Float, nullable=True)
    maturity_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)


class FactBondInstrumentObs(Base):
    """Per-bond (ISIN) daily observations — yield / ASW / price + changes."""

    __tablename__ = "fact_bond_instrument_obs"
    __table_args__ = (
        UniqueConstraint(
            "instrument_id", "vendor_id", "obs_date", "quote_type", "pricing_source",
            name="uq_fact_bond_instrument_obs",
        ),
        {"schema": "rates"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    instrument_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("dbo.dim_bond_instrument.id"), nullable=False
    )
    vendor_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("dbo.dim_vendor.id"), nullable=False
    )
    frequency_id: Mapped[int] = mapped_column(
        TINYINT, ForeignKey("dbo.dim_frequency.id"), nullable=False
    )
    obs_date: Mapped[date] = mapped_column(Date, nullable=False)
    obs_ts: Mapped[datetime] = mapped_column(DATETIMEOFFSET, nullable=False)
    quote_type: Mapped[str] = mapped_column(String(20), nullable=False)
    tenor_years: Mapped[float] = mapped_column(Float, nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    chg_1d: Mapped[float | None] = mapped_column(Float, nullable=True)
    chg_1w: Mapped[float | None] = mapped_column(Float, nullable=True)
    chg_1m: Mapped[float | None] = mapped_column(Float, nullable=True)
    chg_3m: Mapped[float | None] = mapped_column(Float, nullable=True)
    pricing_source: Mapped[str] = mapped_column(String(12), nullable=False)
    units: Mapped[str] = mapped_column(String(10), nullable=False)
    source_app: Mapped[str] = mapped_column(String(20), nullable=False, default="GOVY_MONITOR")


class FactBondAuction(Base):
    """Sovereign issuance / auction calendar (Govy Monitor)."""

    __tablename__ = "fact_bond_auction"
    __table_args__ = (
        UniqueConstraint(
            "country_id", "auction_date", "security_type", "term", "isin",
            name="uq_fact_bond_auction",
        ),
        {"schema": "rates"},
    )

    country_id: Mapped[int] = mapped_column(
        TINYINT, ForeignKey("dbo.dim_country.id"), nullable=False
    )
    auction_date: Mapped[date] = mapped_column(Date, nullable=False)
    security_type: Mapped[str] = mapped_column(String(30), nullable=False, default="")
    term: Mapped[str] = mapped_column(String(10), nullable=False, default="")
    isin: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    cusip: Mapped[str | None] = mapped_column(String(20), nullable=True)
    coupon: Mapped[float | None] = mapped_column(Float, nullable=True)
    maturity_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    reopening: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    offered_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency_id: Mapped[int | None] = mapped_column(
        TINYINT, ForeignKey("dbo.dim_currency.id"), nullable=True
    )
    source: Mapped[str | None] = mapped_column(String(30), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DATETIMEOFFSET, nullable=False)
