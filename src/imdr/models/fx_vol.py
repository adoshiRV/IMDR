"""FX vol domain ORM models mapping to [fx] schema tables."""
from __future__ import annotations

from datetime import date

from sqlalchemy import Date, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from imdr.models.base import Base


class FXCurrencyPair(Base):
    """Currency pair dimension — shared across FX domain."""

    __tablename__ = "dim_currency_pair"
    __table_args__ = (
        UniqueConstraint("base_ccy", "quote_ccy", name="uq_fx_dim_currency_pair"),
        {"schema": "fx"},
    )

    base_ccy: Mapped[str] = mapped_column(String(3), nullable=False)
    quote_ccy: Mapped[str] = mapped_column(String(3), nullable=False)
    ccy_class: Mapped[str] = mapped_column(String(20), nullable=False)

    vol_observations: Mapped[list[FXFactVol]] = relationship(back_populates="pair")

    def __repr__(self) -> str:
        return f"<FXCurrencyPair {self.base_ccy}/{self.quote_ccy} ({self.ccy_class})>"


class FXFactVol(Base):
    """Daily FX vol surface observations."""

    __tablename__ = "fact_vol"
    __table_args__ = (
        UniqueConstraint(
            "pair_id", "obs_date", "strike", "tenor", "vol_type",
            name="uq_fx_fact_vol",
        ),
        {"schema": "fx"},
    )

    pair_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("fx.dim_currency_pair.id"), nullable=False
    )
    obs_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    strike: Mapped[str] = mapped_column(String(15), nullable=False)
    tenor: Mapped[str] = mapped_column(String(5), nullable=False)
    vol_type: Mapped[str] = mapped_column(String(10), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)

    pair: Mapped[FXCurrencyPair] = relationship(back_populates="vol_observations")

    def __repr__(self) -> str:
        return f"<FXFactVol pair_id={self.pair_id} {self.obs_date} {self.strike} {self.tenor} {self.vol_type}={self.value}>"
