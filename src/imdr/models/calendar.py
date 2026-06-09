"""ORM models for the calendar schema — cb_events, dim_calendar, market_holidays.

Phase D Step 11 / Block 5 sub-step 5.1 (2026-05-13): the legacy ``dim_market``,
``dim_market_currency``, ``dim_market_calendar``, and ``dim_trading_day`` ORM
models were deleted here ahead of the table rename in migration 050. Nothing
in the codebase referenced these classes any more (the calendar API moved to
``dbo.dim_country`` + ``calendar.dim_calendar`` + ``calendar.market_holidays``
during Phase D Steps 1–11).
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.mssql import TINYINT
from sqlalchemy.orm import Mapped, mapped_column

from imdr.models.base import Base


class CBEvent(Base):
    """Central-bank / macroeconomic event row.

    Phase H sub-step 5.3 (2026-05-13): the ``country_code`` varchar(5) column
    was dropped in migration 051. Use ``country_id`` (FK to ``dbo.dim_country.id``)
    and JOIN to ``dim_country`` if you need the string code.
    """

    __tablename__ = "cb_events"
    __table_args__ = {"schema": "calendar"}

    event_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    event_datetime: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    country_id: Mapped[int] = mapped_column(
        TINYINT, ForeignKey("dbo.dim_country.id"), nullable=False,
    )
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


class DimCalendar(Base):
    """Named holiday calendar — e.g. 'YO' (NYSE), 'GT' (US Govt Bond / SIFMA),
    'TE' (TARGET2), 'RB' (RBI). One country can have several (rates vs equity
    vs settlement).

    Migration history:
    - Seeded by migration 031
    - Migration 040: added country_id FK -> dbo.dim_country(id);
      dropped country_code_iso
    - Migration 041: dropped calendar_segment (segment moved to caller-side
      config; callers pick calendar_code directly)
    - Migration 042: description backfilled from BBG xlsx
    """

    __tablename__ = "dim_calendar"
    __table_args__ = {"schema": "calendar"}

    # TINYINT IDENTITY PK — small dim, max 255 calendars
    id: Mapped[int] = mapped_column(TINYINT, primary_key=True, autoincrement=True)
    calendar_code: Mapped[str] = mapped_column(String(5), nullable=False, unique=True)
    calendar_name: Mapped[str] = mapped_column(String(100), nullable=False)
    country_id: Mapped[int] = mapped_column(
        TINYINT, ForeignKey("dbo.dim_country.id"), nullable=False, index=True,
    )
    description: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class MarketHoliday(Base):
    """One holiday date for one calendar from one vendor.

    Multi-vendor: BBG, MANUAL, HOLIDAYS_LIB, EXCHANGE_CALENDARS coexist for the
    same (calendar_id, holiday_date). The calendar API picks the trusted vendor
    via the ``trusted_vendor`` parameter on ``is_holiday_db`` /
    ``resolve_holiday_set``, falling back through ``GLOBAL_VENDOR_PRIORITY`` if
    the trusted vendor has no coverage for the calendar.
    """

    __tablename__ = "market_holidays"
    __table_args__ = {"schema": "calendar"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    calendar_id: Mapped[int] = mapped_column(
        TINYINT, ForeignKey("calendar.dim_calendar.id"), nullable=False,
    )
    vendor_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("dbo.dim_vendor.id"), nullable=False,
    )
    holiday_date: Mapped[date] = mapped_column(Date, nullable=False)
    holiday_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_custom: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    load_batch: Mapped[str | None] = mapped_column(String(50), nullable=True)
