"""ORM models for the calendar schema — dim_market, dim_market_currency, cb_events."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from imdr.models.base import Base


class DimMarket(Base):
    """Shared market dimension — the central hub linking all domains."""

    __tablename__ = "dim_market"
    __table_args__ = {"schema": "calendar"}

    # Override Base auto-increment PK — use market_code as PK instead
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    market_code: Mapped[str] = mapped_column(String(5), unique=True, nullable=False)
    market_name: Mapped[str] = mapped_column(String(100), nullable=False)
    timezone: Mapped[str] = mapped_column(String(50), nullable=False)
    country_code_iso: Mapped[str] = mapped_column(String(2), nullable=False)
    weekend_days: Mapped[str] = mapped_column(String(10), nullable=False, default="5,6")
    trading_open: Mapped[str | None] = mapped_column(String(5), nullable=True)
    trading_close: Mapped[str | None] = mapped_column(String(5), nullable=True)
    lunch_start: Mapped[str | None] = mapped_column(String(5), nullable=True)
    lunch_end: Mapped[str | None] = mapped_column(String(5), nullable=True)


class DimMarketCurrency(Base):
    """Bridge table: market_code ↔ currency. Join key for cross-domain queries."""

    __tablename__ = "dim_market_currency"
    __table_args__ = {"schema": "calendar"}

    # Override Base auto-increment PK
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    market_code: Mapped[str] = mapped_column(
        String(5), ForeignKey("calendar.dim_market.market_code"), nullable=False,
    )
    ccy: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class DimTradingDay(Base):
    """Pre-computed calendar grid — one row per market per date."""

    __tablename__ = "dim_trading_day"
    __table_args__ = {"schema": "calendar"}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    market_code: Mapped[str] = mapped_column(
        String(5), ForeignKey("calendar.dim_market.market_code"), nullable=False,
    )
    calendar_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_weekend: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_holiday: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_trading_day: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    holiday_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_custom: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class CBEvent(Base):
    __tablename__ = "cb_events"
    __table_args__ = {"schema": "calendar"}

    event_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    event_datetime: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    country_code: Mapped[str] = mapped_column(String(5), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    event_name: Mapped[str] = mapped_column(String(500), nullable=False)
    ticker: Mapped[str | None] = mapped_column(String(50), nullable=True)
    period_value: Mapped[date | None] = mapped_column(Date, nullable=True)
    survey: Mapped[str | None] = mapped_column(String(20), nullable=True)
    actual: Mapped[str | None] = mapped_column(String(20), nullable=True)
    prior_value: Mapped[str | None] = mapped_column(String(20), nullable=True)
    revised: Mapped[str | None] = mapped_column(String(20), nullable=True)
    relevance: Mapped[float | None] = mapped_column(Float, nullable=True)
    frequency: Mapped[str | None] = mapped_column(String(5), nullable=True)
    is_estimated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source: Mapped[str | None] = mapped_column(String(200), nullable=True)
