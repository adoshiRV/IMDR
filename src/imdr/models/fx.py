from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from imdr.models.base import Base


class FXSpotRate(Base):
    """FX spot rate observation for a currency pair on a given date."""

    __tablename__ = "fx_spot_rates"
    __table_args__ = (
        UniqueConstraint("base_currency", "quote_currency", "rate_date", name="uq_fx_spot_rate"),
        {"schema": "fx"},
    )

    base_currency: Mapped[str] = mapped_column(String(3), nullable=False, index=True)
    quote_currency: Mapped[str] = mapped_column(String(3), nullable=False, index=True)
    rate_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    bid: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    ask: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    mid: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<FXSpotRate {self.base_currency}/{self.quote_currency} {self.rate_date} mid={self.mid}>"
