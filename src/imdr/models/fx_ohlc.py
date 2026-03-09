"""FX OHLC bar model mapping to existing [FX].[fact_ohlc] table."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from imdr.models.base import Base


class FXFactOHLC(Base):
    """Hourly FX OHLC bar for a symbol/series/tenor combination."""

    __tablename__ = "fact_ohlc"
    __table_args__ = (
        UniqueConstraint("ts", "symbol", "series", "tenor", name="uq_fx_fact_ohlc"),
        {"schema": "fx"},
    )

    # Table has id + created_at but NOT updated_at — suppress inherited column
    updated_at = None

    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    series: Mapped[str] = mapped_column(String(30), nullable=False)
    tenor: Mapped[str] = mapped_column(String(10), nullable=False)
    deal_type: Mapped[str] = mapped_column(String(20), nullable=False)
    pair_used: Mapped[str] = mapped_column(String(20), nullable=False)

    open_px: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    high_px: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    low_px: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    close_px: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    mid_px: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    mid_mean_px: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    mid_median_px: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    bid: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    ask: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    n_ticks: Mapped[int] = mapped_column(Integer, nullable=False)

    def __repr__(self) -> str:
        return f"<FXFactOHLC {self.symbol} {self.series} {self.ts} close={self.close_px}>"
