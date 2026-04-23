"""FX rate ORM mapping to [fx].[fact_fx_rate].

Single fact table for spot + forward outrights + forward points, sourced from
Citi Velocity EOD. Reuses fx.dim_currency_pair (already created by vol pipeline);
FKs to dbo.dim_vendor and dbo.dim_frequency for source and cadence tracking.

See docs/fx/fx_rate_schema.md for column semantics and the tenor enum.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from imdr.models.base import Base


class FXFactFXRate(Base):
    """Daily FX rate observation — spot or forward outright mid, plus optional fwd points."""

    __tablename__ = "fact_fx_rate"
    __table_args__ = (
        UniqueConstraint(
            "pair_id",
            "vendor_id",
            "frequency_id",
            "obs_date",
            "tenor",
            name="uq_fx_fact_fx_rate",
        ),
        CheckConstraint("mid_rate > 0", name="ck_fx_fact_fx_rate_mid_rate_positive"),
        CheckConstraint(
            "tenor <> 'SPOT' OR fwd_points IS NULL",
            name="ck_fx_fact_fx_rate_spot_points_null",
        ),
        {"schema": "fx"},
    )

    pair_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("fx.dim_currency_pair.id"), nullable=False, index=True
    )
    vendor_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("dbo.dim_vendor.id"), nullable=False, index=True
    )
    frequency_id: Mapped[int] = mapped_column(
        SmallInteger, ForeignKey("dbo.dim_frequency.id"), nullable=False, index=True
    )
    obs_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    tenor: Mapped[str] = mapped_column(String(5), nullable=False)
    mid_rate: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    fwd_points: Mapped[Decimal | None] = mapped_column(Numeric(18, 10), nullable=True)

    def __repr__(self) -> str:
        return (
            f"<FXFactFXRate pair_id={self.pair_id} {self.obs_date} "
            f"{self.tenor} mid={self.mid_rate} pts={self.fwd_points}>"
        )
