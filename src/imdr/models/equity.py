"""Equity domain ORM models mapping to [equities] schema tables."""
from __future__ import annotations

from datetime import date

from sqlalchemy import Date, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from imdr.models.base import Base


class EquityDimIndex(Base):
    """Shared equity index dimension — links all equity products."""

    __tablename__ = "dim_index"
    __table_args__ = (
        UniqueConstraint("ticker", name="uq_equities_dim_index"),
        {"schema": "equities"},
    )

    ticker: Mapped[str] = mapped_column(String(20), nullable=False)
    display_name: Mapped[str] = mapped_column(String(60), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    region: Mapped[str] = mapped_column(String(20), nullable=False)
    citi_tag: Mapped[str | None] = mapped_column(String(80), nullable=True)
    market_code: Mapped[str | None] = mapped_column(String(5), nullable=True)

    index_levels: Mapped[list[EquityFactIndexLevel]] = relationship(
        back_populates="index"
    )

    def __repr__(self) -> str:
        return f"<EquityDimIndex {self.ticker} ({self.region})>"


class EquityFactIndexLevel(Base):
    """Daily equity index closing levels."""

    __tablename__ = "fact_index_level"
    __table_args__ = (
        UniqueConstraint("index_id", "obs_date", name="uq_equities_fact_index_level"),
        {"schema": "equities"},
    )

    index_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("equities.dim_index.id"), nullable=False
    )
    obs_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    close_level: Mapped[float] = mapped_column(Float, nullable=False)

    index: Mapped[EquityDimIndex] = relationship(
        back_populates="index_levels"
    )

    def __repr__(self) -> str:
        return f"<EquityFactIndexLevel {self.obs_date} index_id={self.index_id} close_level={self.close_level}>"


class EquityFactVix(Base):
    """Daily VIX family observations (VIX, VIX3M, VIX9D, VVIX, VXN)."""

    __tablename__ = "fact_vix"
    __table_args__ = (
        UniqueConstraint("ticker", "obs_date", name="uq_equities_fact_vix"),
        {"schema": "equities"},
    )

    ticker: Mapped[str] = mapped_column(String(10), nullable=False)
    obs_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    close_level: Mapped[float] = mapped_column(Float, nullable=False)

    def __repr__(self) -> str:
        return f"<EquityFactVix {self.ticker} {self.obs_date} close_level={self.close_level}>"
