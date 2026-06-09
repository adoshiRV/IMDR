"""Rates domain ORM models mapping to [rates] schema tables."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Date,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.mssql import DATETIMEOFFSET, TINYINT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from imdr.models.base import Base


class RatesCurve(Base):
    """Curve dimension — 39 rows, one per ccy/curve combination."""

    __tablename__ = "dim_curve"
    __table_args__ = (
        UniqueConstraint("ccy", "curve", name="uq_rates_dim_curve"),
        {"schema": "rates"},
    )

    ccy: Mapped[str] = mapped_column(String(10), nullable=False)
    curve: Mapped[str] = mapped_column(String(30), nullable=False)
    curve_type: Mapped[str] = mapped_column(String(10), nullable=False)
    curve_status: Mapped[str] = mapped_column(String(10), nullable=False)
    instrument: Mapped[str] = mapped_column(String(20), nullable=False)
    citi_prefix: Mapped[str] = mapped_column(String(60), nullable=False)
    cessation_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    primary_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    supersedes: Mapped[str | None] = mapped_column(String(30), nullable=True)
    superseded_by: Mapped[str | None] = mapped_column(String(30), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    country_id: Mapped[int] = mapped_column(
        TINYINT, ForeignKey("dbo.dim_country.id"), nullable=False
    )

    observations: Mapped[list[RatesObservation]] = relationship(back_populates="curve")

    def __repr__(self) -> str:
        return f"<RatesCurve {self.ccy} {self.curve} ({self.curve_type})>"


class RatesCacheEmptyCombo(Base):
    """Cache of (ccy, curve, quote) combos that return 0 rows from Citi API."""

    __tablename__ = "cache_empty_combo"
    __table_args__ = (
        UniqueConstraint("ccy", "curve", "quote", name="uq_cache_empty_combo"),
        {"schema": "rates"},
    )

    ccy: Mapped[str] = mapped_column(String(10), nullable=False)
    curve: Mapped[str] = mapped_column(String(30), nullable=False)
    quote: Mapped[str] = mapped_column(String(10), nullable=False)
    last_checked: Mapped[date] = mapped_column(Date, nullable=False)


class RatesObservation(Base):
    """Rate observations fact table — one row per curve/vendor/ts/quote/tenor/freq.

    Natural key updated by migrations 025 (frequency_id) and 029 (vendor_id) —
    multi-vendor (Citi + Bloomberg) and multi-frequency (DAILY + HOURLY +
    SNAPSHOT) coexist on the same fact table, each row tagged.
    """

    __tablename__ = "fact_observation"
    __table_args__ = (
        UniqueConstraint(
            "curve_id", "vendor_id", "ts", "quote", "tenor", "frequency_id",
            name="uq_rates_fact_obs",
        ),
        {"schema": "rates"},
    )

    curve_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("rates.dim_curve.id"), nullable=False
    )
    vendor_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("dbo.dim_vendor.id"), nullable=False, index=True
    )
    ts: Mapped[datetime] = mapped_column(DATETIMEOFFSET, nullable=False, index=True)
    quote: Mapped[str] = mapped_column(String(10), nullable=False)
    tenor: Mapped[str] = mapped_column(String(30), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    frequency_id: Mapped[int] = mapped_column(
        TINYINT, ForeignKey("dbo.dim_frequency.id"), nullable=False
    )

    curve: Mapped[RatesCurve] = relationship(back_populates="observations")

    def __repr__(self) -> str:
        return f"<RatesObservation curve_id={self.curve_id} {self.ts} {self.quote} {self.tenor}={self.value}>"
