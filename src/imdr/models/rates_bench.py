"""Rates bench rates ORM models mapping to [rates] schema tables."""
from __future__ import annotations

from datetime import date

from sqlalchemy import Date, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.mssql import TINYINT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from imdr.models.base import Base


class RatesDimCentralBank(Base):
    """Central bank dimension — one row per policy rate series."""

    __tablename__ = "dim_central_bank"
    __table_args__ = (
        UniqueConstraint("cb_code", name="uq_rates_dim_central_bank"),
        {"schema": "rates"},
    )

    cb_code: Mapped[str] = mapped_column(String(30), nullable=False)
    display_name: Mapped[str] = mapped_column(String(60), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    # Legacy VARCHAR market_code still populated; new code prefers market_id FK.
    market_code: Mapped[str] = mapped_column(String(5), nullable=False)
    # Added by migration 026 — FK to calendar.dim_market(id).
    market_id: Mapped[int | None] = mapped_column(
        TINYINT, ForeignKey("calendar.dim_market.id"), nullable=True
    )
    citi_tag: Mapped[str] = mapped_column(String(60), nullable=False)

    observations: Mapped[list[RatesFactBenchRates]] = relationship(
        back_populates="central_bank"
    )

    def __repr__(self) -> str:
        return f"<RatesDimCentralBank {self.cb_code} ({self.currency}/{self.market_code})>"


class RatesFactBenchRates(Base):
    """Daily central bank policy rate observations."""

    __tablename__ = "fact_bench_rates"
    __table_args__ = (
        UniqueConstraint("cb_id", "obs_date", name="uq_rates_fact_bench_rates"),
        {"schema": "rates"},
    )

    cb_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("rates.dim_central_bank.id"), nullable=False
    )
    vendor_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("dbo.dim_vendor.id"), nullable=False
    )
    obs_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    rate: Mapped[float] = mapped_column(Float, nullable=False)

    central_bank: Mapped[RatesDimCentralBank] = relationship(
        back_populates="observations"
    )

    def __repr__(self) -> str:
        return f"<RatesFactBenchRates cb_id={self.cb_id} {self.obs_date} rate={self.rate}>"
