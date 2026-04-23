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
    # Legacy market_code VARCHAR (migration 010) still in DB; new code uses market_id FK.
    market_code: Mapped[str | None] = mapped_column(String(5), nullable=True)
    # Added by migration 026 — FK to calendar.dim_market(id).
    market_id: Mapped[int | None] = mapped_column(
        TINYINT, ForeignKey("calendar.dim_market.id"), nullable=True
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
    """Rate observations fact table — one row per curve/ts/quote/tenor."""

    __tablename__ = "fact_observation"
    __table_args__ = (
        UniqueConstraint("curve_id", "ts", "quote", "tenor", name="uq_rates_fact_obs"),
        {"schema": "rates"},
    )

    curve_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("rates.dim_curve.id"), nullable=False
    )
    ts: Mapped[datetime] = mapped_column(DATETIMEOFFSET, nullable=False, index=True)
    quote: Mapped[str] = mapped_column(String(10), nullable=False)
    tenor: Mapped[str] = mapped_column(String(30), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)

    curve: Mapped[RatesCurve] = relationship(back_populates="observations")

    def __repr__(self) -> str:
        return f"<RatesObservation curve_id={self.curve_id} {self.ts} {self.quote} {self.tenor}={self.value}>"
