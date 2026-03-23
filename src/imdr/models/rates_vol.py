"""Rates swaption vol ORM models mapping to [rates] schema tables."""
from __future__ import annotations

from datetime import date

from sqlalchemy import Boolean, Date, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from imdr.models.base import Base


class RatesVolSurface(Base):
    """Vol surface dimension — one row per (ccy, data_type, qualifier) combo."""

    __tablename__ = "dim_vol_surface"
    __table_args__ = (
        UniqueConstraint(
            "ccy", "data_type", "quote_type", "vol_window", "freq",
            name="uq_rates_dim_vol_surface",
        ),
        {"schema": "rates"},
    )

    ccy: Mapped[str] = mapped_column(String(3), nullable=False)
    data_type: Mapped[str] = mapped_column(String(15), nullable=False)
    quote_type: Mapped[str] = mapped_column(String(12), nullable=False, default="")
    vol_window: Mapped[str] = mapped_column(String(3), nullable=False, default="")
    freq: Mapped[str] = mapped_column(String(6), nullable=False, default="")
    is_rfr: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    observations: Mapped[list[RatesFactSwaptionVol]] = relationship(
        back_populates="surface"
    )

    def __repr__(self) -> str:
        parts = [f"{self.ccy}.{self.data_type}"]
        if self.quote_type:
            parts.append(self.quote_type)
        if self.vol_window:
            parts.append(self.vol_window)
        if self.freq:
            parts.append(self.freq)
        return f"<RatesVolSurface {'.'.join(parts)}>"


class RatesFactSwaptionVol(Base):
    """Daily swaption vol observations on the expiry x swap tenor grid."""

    __tablename__ = "fact_swaption_vol"
    __table_args__ = (
        UniqueConstraint(
            "surface_id", "obs_date", "option_expiry", "swap_tenor",
            name="uq_rates_fact_swaption_vol",
        ),
        {"schema": "rates"},
    )

    surface_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("rates.dim_vol_surface.id"), nullable=False
    )
    obs_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    option_expiry: Mapped[str] = mapped_column(String(4), nullable=False)
    swap_tenor: Mapped[str] = mapped_column(String(4), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)

    surface: Mapped[RatesVolSurface] = relationship(back_populates="observations")

    def __repr__(self) -> str:
        return (
            f"<RatesFactSwaptionVol surface_id={self.surface_id} "
            f"{self.obs_date} {self.option_expiry}x{self.swap_tenor}={self.value}>"
        )
