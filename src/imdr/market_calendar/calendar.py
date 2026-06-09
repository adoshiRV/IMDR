"""Global trading calendar — unified API combining holidays, weekends, and trading hours.

Provides country-anchored date functions for scheduling, health checks, and
pipeline logic. Every holiday-aware function takes an explicit ``country_code``
plus ``calendar_code`` (the BBG-master 2-letter calendar identifier — ``GT``
for SIFMA US Govt Bond, ``NY`` for NYSE, ``TE`` for TARGET2, etc.). The
calendar choice is fully the caller's: there is no default resolution, no
silent fallback to country-level holidays. Holiday data lives in
``calendar.market_holidays`` keyed by ``(calendar_id, vendor_id, date)``; if
the calendar has no rows there, :class:`CalendarDBError` is raised at the
call site rather than masked.

Phase D Step 11 (2026-05-13): the legacy ``(market_code, d, segment=…)``
signatures, the ``calendar.dim_market_calendar`` bridge, and the Python
``holidays``-library fallback are gone. ``DEFAULT_CALENDAR_BY_COUNTRY`` in
``countries.py`` is the one place where project-wide "default calendar per
country" policy is encoded; everything else either passes a calendar_code
explicitly or asks ``default_calendar(country)``.

>>> from datetime import date
>>> is_holiday("US", "GT", date(2026, 11, 11))   # SIFMA closed for Veterans Day
True
>>> is_holiday("US", "NY", date(2026, 11, 11))   # NYSE open
False
>>> last_business_day("US", "GT")                # most recent SIFMA business day
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from imdr.market_calendar.countries import get_country
from imdr.market_calendar.holidays_db import (
    get_weekend_days,
    is_holiday_db,
)


class CalendarDBError(LookupError):
    """Raised when a calendar_code is requested that has no rows in the DB.

    Indicates one of:

    * **Typo**: caller passed a calendar_code that doesn't exist in
      ``calendar.dim_calendar`` (e.g. ``"GTT"`` instead of ``"GT"``).
    * **Missing data**: caller passed a real calendar_code but no vendor has
      loaded holidays into ``calendar.market_holidays`` for it.
    * **Stub gap**: in unit tests, the in-memory stub fixture is missing the
      ``(calendar, vendor)`` rows the test depends on.

    Fix at the call site — either correct the calendar_code, load holidays
    for it, or extend the stub fixture. Do not catch this and continue.
    """


# ─── Weekend ─────────────────────────────────────────────────────────────


def is_weekend(country_code: str, d: date) -> bool:
    """Check if date falls on the country's weekend days.

    Reads ``weekend_days`` from ``dbo.dim_country``. Pseudo-countries
    (``EU``, ``WW``, ``XX``) and any country whose row has ``weekend_days
    IS NULL`` fall back to Saturday/Sunday.
    """
    return d.weekday() in get_weekend_days(country_code)


# ─── Internal cores ──────────────────────────────────────────────────────


def _holiday_check_core(
    country_code: str, calendar_code: str, d: date, trusted_vendor: str | None = None,
) -> bool:
    """Query ``calendar.market_holidays`` for the calendar; raise on miss.

    The ``country_code`` is informational only here — it shows up in the
    error message but doesn't affect lookup. Calendar coverage is keyed
    purely by ``calendar_code`` + ``trusted_vendor``.
    """
    answer = is_holiday_db(calendar_code, d, trusted_vendor=trusted_vendor)
    if answer is None:
        raise CalendarDBError(
            f"No holiday rows in calendar.market_holidays for "
            f"calendar_code={calendar_code!r} (country={country_code!r}, "
            f"date={d.isoformat()}). Either the calendar_code is wrong or "
            f"the calendar has no vendor coverage."
        )
    return answer


def _is_trading_day_core(country_code: str, calendar_code: str, d: date) -> bool:
    if d.weekday() in get_weekend_days(country_code):
        return False
    return not _holiday_check_core(country_code, calendar_code, d)


def _last_trading_day_core(
    country_code: str, calendar_code: str, before: date | None = None,
) -> date:
    if before is None:
        before = date.today()
    d = before - timedelta(days=1)
    for _ in range(30):
        if _is_trading_day_core(country_code, calendar_code, d):
            return d
        d -= timedelta(days=1)
    raise ValueError(
        f"No trading day found for {country_code}/{calendar_code} "
        f"within 30 days before {before}"
    )


def _next_trading_day_core(
    country_code: str, calendar_code: str, after: date | None = None,
) -> date:
    if after is None:
        after = date.today()
    d = after + timedelta(days=1)
    for _ in range(30):
        if _is_trading_day_core(country_code, calendar_code, d):
            return d
        d += timedelta(days=1)
    raise ValueError(
        f"No trading day found for {country_code}/{calendar_code} "
        f"within 30 days after {after}"
    )


def _trading_days_between_core(
    country_code: str, calendar_code: str, start: date, end: date,
) -> list[date]:
    days: list[date] = []
    d = start
    while d <= end:
        if _is_trading_day_core(country_code, calendar_code, d):
            days.append(d)
        d += timedelta(days=1)
    return days


def _is_market_open_core(
    country_code: str, calendar_code: str, utc_dt: datetime,
) -> bool:
    country = get_country(country_code)
    tz = ZoneInfo(country.timezone)
    local_dt = utc_dt.astimezone(tz)
    local_d = local_dt.date()

    if not _is_trading_day_core(country_code, calendar_code, local_d):
        return False

    th = country.trading_hours
    if th is None:
        return True

    local_t = local_dt.time()
    market_open = time.fromisoformat(th.open)
    market_close = time.fromisoformat(th.close)

    if local_t < market_open or local_t >= market_close:
        return False

    if th.lunch_start and th.lunch_end:
        lunch_start = time.fromisoformat(th.lunch_start)
        lunch_end = time.fromisoformat(th.lunch_end)
        if lunch_start <= local_t < lunch_end:
            return False

    return True


def _last_business_day_core(country_code: str, calendar_code: str) -> datetime:
    """Most recent completed trading day as a UTC-midnight datetime.

    Uses the country's local date (via ``countries.yml`` timezone for now;
    a future cleanup moves this to ``dim_country.timezone``). If today is a
    trading day and the market is already closed, returns today. Otherwise
    the previous trading day.
    """
    country = get_country(country_code)
    tz = ZoneInfo(country.timezone)
    now_local = datetime.now(tz)
    today_local = now_local.date()

    if _is_trading_day_core(country_code, calendar_code, today_local):
        th = country.trading_hours
        if th is not None:
            market_close = time.fromisoformat(th.close)
            if now_local.time() >= market_close:
                return datetime(
                    today_local.year, today_local.month, today_local.day,
                    tzinfo=ZoneInfo("UTC"),
                )
        # 24h/OTC: today not yet "complete"; fall through to previous day

    d = _last_trading_day_core(country_code, calendar_code, before=today_local)
    return datetime(d.year, d.month, d.day, tzinfo=ZoneInfo("UTC"))


# ─── Public API ───────────────────────────────────────────────────────────


def is_holiday(country_code: str, calendar_code: str, d: date) -> bool:
    """Check if a date is a holiday for a country's calendar."""
    return _holiday_check_core(country_code, calendar_code, d)


def is_trading_day(country_code: str, calendar_code: str, d: date) -> bool:
    """True if a date is NOT a weekend AND NOT a holiday for the calendar."""
    return _is_trading_day_core(country_code, calendar_code, d)


def is_market_open(country_code: str, calendar_code: str, utc_dt: datetime) -> bool:
    """True if the market is currently in trading hours."""
    return _is_market_open_core(country_code, calendar_code, utc_dt)


def last_trading_day(
    country_code: str, calendar_code: str, before: date | None = None,
) -> date:
    """Most recent trading day strictly before ``before`` (default: today)."""
    return _last_trading_day_core(country_code, calendar_code, before)


def next_trading_day(
    country_code: str, calendar_code: str, after: date | None = None,
) -> date:
    """Next trading day strictly after ``after`` (default: today)."""
    return _next_trading_day_core(country_code, calendar_code, after)


def trading_days_between(
    country_code: str, calendar_code: str, start: date, end: date,
) -> list[date]:
    """All trading days in ``[start, end]`` inclusive."""
    return _trading_days_between_core(country_code, calendar_code, start, end)


def last_business_day(country_code: str, calendar_code: str) -> datetime:
    """Most recent completed trading day as a UTC-midnight datetime."""
    return _last_business_day_core(country_code, calendar_code)
