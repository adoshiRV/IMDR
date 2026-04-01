"""Global trading calendar — unified API combining holidays, weekends, and trading hours.

Provides market-aware date functions for scheduling, health checks, and pipeline logic.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from imdr.market_calendar.holidays import _get_country_holidays, _target2_holidays
from imdr.market_calendar.markets import get_market


def is_weekend(market_code: str, d: date) -> bool:
    """Check if date falls on the market's weekend days."""
    market = get_market(market_code)
    return d.weekday() in market.weekend_days


def is_holiday(market_code: str, d: date) -> bool:
    """Check if date is a public/financial holiday for the market."""
    market = get_market(market_code)
    year = d.year

    if market.calendar_type == "target2":
        return d in _target2_holidays(year)

    return d in _get_country_holidays(market.country_code, year)


def is_trading_day(market_code: str, d: date) -> bool:
    """True if date is NOT a weekend and NOT a holiday for the market."""
    return not is_weekend(market_code, d) and not is_holiday(market_code, d)


def is_market_open(market_code: str, utc_dt: datetime) -> bool:
    """True if the market is currently in trading hours.

    Converts UTC to local time, then checks:
    1. Is today a trading day?
    2. Is the current local time within trading_hours (if configured)?
    3. Is the current local time outside the lunch break (if configured)?

    Returns True for markets without trading_hours if it's a trading day
    (i.e., 24h/OTC semantics).
    """
    market = get_market(market_code)
    tz = ZoneInfo(market.timezone)
    local_dt = utc_dt.astimezone(tz)
    local_d = local_dt.date()

    if not is_trading_day(market_code, local_d):
        return False

    th = market.trading_hours
    if th is None:
        return True  # No trading hours = open all day on trading days

    local_t = local_dt.time()
    market_open = time.fromisoformat(th.open)
    market_close = time.fromisoformat(th.close)

    if local_t < market_open or local_t >= market_close:
        return False

    # Check lunch break
    if th.lunch_start and th.lunch_end:
        lunch_start = time.fromisoformat(th.lunch_start)
        lunch_end = time.fromisoformat(th.lunch_end)
        if lunch_start <= local_t < lunch_end:
            return False

    return True


def last_trading_day(market_code: str, before: date | None = None) -> date:
    """Most recent trading day strictly before `before` (default: today).

    Walks back over weekends and holidays. Raises ValueError if no trading day
    found within 30 calendar days.
    """
    if before is None:
        before = date.today()
    d = before - timedelta(days=1)
    for _ in range(30):
        if is_trading_day(market_code, d):
            return d
        d -= timedelta(days=1)
    msg = f"No trading day found for {market_code} within 30 days before {before}"
    raise ValueError(msg)


def next_trading_day(market_code: str, after: date | None = None) -> date:
    """Next trading day strictly after `after` (default: today).

    Walks forward over weekends and holidays. Raises ValueError if no trading day
    found within 30 calendar days.
    """
    if after is None:
        after = date.today()
    d = after + timedelta(days=1)
    for _ in range(30):
        if is_trading_day(market_code, d):
            return d
        d += timedelta(days=1)
    msg = f"No trading day found for {market_code} within 30 days after {after}"
    raise ValueError(msg)


def trading_days_between(
    market_code: str, start: date, end: date,
) -> list[date]:
    """All trading days in [start, end] inclusive."""
    days: list[date] = []
    d = start
    while d <= end:
        if is_trading_day(market_code, d):
            days.append(d)
        d += timedelta(days=1)
    return days


def last_business_day(market_code: str = "US") -> datetime:
    """Holiday-aware replacement for the duplicated _last_business_day() in scripts.

    Returns the most recent completed trading day as a timezone-aware UTC
    datetime at midnight. Drop-in compatible with existing script usage.

    Uses the market's local date (not UTC) so that a scheduler running after
    market close in a different timezone gets the correct business day.
    If today is a trading day and the market is already closed, returns today.
    Otherwise returns the most recent prior trading day.
    """
    market = get_market(market_code)
    tz = ZoneInfo(market.timezone)
    now_local = datetime.now(tz)
    today_local = now_local.date()

    if is_trading_day(market_code, today_local):
        th = market.trading_hours
        if th is not None:
            market_close = time.fromisoformat(th.close)
            if now_local.time() >= market_close:
                return datetime(today_local.year, today_local.month, today_local.day, tzinfo=ZoneInfo("UTC"))
        # No trading hours (24h/OTC) — today not yet "complete", fall through

    d = last_trading_day(market_code, before=today_local)
    return datetime(d.year, d.month, d.day, tzinfo=ZoneInfo("UTC"))
