"""Rates swaption skew ORM models mapping to [rates] schema tables."""
from __future__ import annotations

from datetime import date

from sqlalchemy import Date, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.mssql import TINYINT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from imdr.models.base import Base
from imdr.models.currency import DimCurrency
from imdr.models.vendor import DimVendor


class RatesSkewSurface(Base):
    """Skew surface dimension — one row per (ccy, option_expiry) combo."""

    __tablename__ = "dim_skew_surface"
    __table_args__ = (
        UniqueConstraint(
            "ccy", "option_expiry",
            name="uq_rates_dim_skew_surface",
        ),
        {"schema": "rates"},
    )

    ccy: Mapped[str] = mapped_column(String(3), nullable=False)
    currency_id: Mapped[int] = mapped_column(
        TINYINT, ForeignKey("dbo.dim_currency.id"), nullable=False
    )
    option_expiry: Mapped[str] = mapped_column(String(4), nullable=False)
    country_id: Mapped[int] = mapped_column(
        TINYINT, ForeignKey("dbo.dim_country.id"), nullable=False
    )

    currency: Mapped[DimCurrency] = relationship()
    observations: Mapped[list[RatesFactSwaptionSkew]] = relationship(
        back_populates="surface"
    )

    def __repr__(self) -> str:
        return f"<RatesSkewSurface {self.ccy}.{self.option_expiry}>"


class RatesFactSwaptionSkew(Base):
    """Daily swaption vol skew — normalised bp vol at strike offsets."""

    __tablename__ = "fact_swaption_skew"
    __table_args__ = (
        UniqueConstraint(
            "surface_id", "obs_date", "swap_tenor", "strike_offset",
            name="uq_rates_fact_swaption_skew",
        ),
        {"schema": "rates"},
    )

    surface_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("rates.dim_skew_surface.id"), nullable=False
    )
    vendor_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("dbo.dim_vendor.id"), nullable=False
    )
    obs_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    swap_tenor: Mapped[str] = mapped_column(String(4), nullable=False)
    strike_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    vol: Mapped[float] = mapped_column(Float, nullable=False)

    surface: Mapped[RatesSkewSurface] = relationship(back_populates="observations")
    vendor: Mapped[DimVendor] = relationship()

    def __repr__(self) -> str:
        return (
            f"<RatesFactSwaptionSkew surface_id={self.surface_id} "
            f"{self.obs_date} {self.swap_tenor} "
            f"{self.strike_offset:+d}bps={self.vol}>"
        )
