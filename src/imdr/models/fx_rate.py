"""FX rate ORM mapping to [fx].[fact_fx_rate].

Single fact table for spot + forward outrights + forward points, sourced from
Citi Velocity EOD. Reuses fx.dim_currency_pair (already created by vol pipeline);
FKs to dbo.dim_vendor and dbo.dim_frequency for source and cadence tracking.

See docs/fx/fx_rate_schema.md for column semantics and the tenor enum.
"""
from __future__ import annotations

from datetime import date, datetime
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
from sqlalchemy.dialects.mssql import DATETIMEOFFSET
from sqlalchemy.orm import Mapped, mapped_column

from imdr.models.base import Base


class FXFactFXRate(Base):
    """FX rate observation — spot or forward outright mid, plus optional fwd points.

    Post-migration 027 the natural key is (pair_id, vendor_id, frequency_id,
    obs_ts, tenor). obs_date is retained for backwards-compat reads and is
    populated by the pipeline as obs_ts.date().
    """

    __tablename__ = "fact_fx_rate"
    __table_args__ = (
        UniqueConstraint(
            "pair_id",
            "vendor_id",
            "frequency_id",
            "obs_ts",
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
    obs_ts: Mapped[datetime] = mapped_column(DATETIMEOFFSET, nullable=False, index=True)
    obs_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    tenor: Mapped[str] = mapped_column(String(5), nullable=False)
    mid_rate: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    fwd_points: Mapped[Decimal | None] = mapped_column(Numeric(18, 10), nullable=True)

    def __repr__(self) -> str:
        return (
            f"<FXFactFXRate pair_id={self.pair_id} {self.obs_ts} "
            f"{self.tenor} mid={self.mid_rate} pts={self.fwd_points}>"
        )
