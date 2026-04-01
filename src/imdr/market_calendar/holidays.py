"""Holiday detection for FX and other markets.

Uses the `holidays` library with fallback for TARGET2 and custom calendars.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

import structlog

from imdr.market_calendar.markets import get_market, markets_for_currency

log = structlog.get_logger(__name__)

try:
    import holidays as holidays_lib

    _HAS_HOLIDAYS = True
except ImportError:
    _HAS_HOLIDAYS = False


@dataclass
class HolidayHit:
    """A holiday match for a currency/market."""

    currency: str
    market_code: str
    date: date
    name: str


def _get_country_holidays(country_code: str, year: int) -> dict[date, str]:
    """Get holidays for a country code using the holidays library."""
    if not _HAS_HOLIDAYS:
        return {}
    try:
        return holidays_lib.country_holidays(country_code, years=year)
    except NotImplementedError:
        log.debug("holidays_not_available", country_code=country_code)
        return {}


def _target2_holidays(year: int) -> dict[date, str]:
    """TARGET2 settlement system holidays (ECB).

    Fixed dates that don't change year to year.
    """
    fixed = {
        date(year, 1, 1): "New Year's Day",
        date(year, 5, 1): "Labour Day",
        date(year, 12, 25): "Christmas Day",
        date(year, 12, 26): "St Stephen's Day",
    }
    # Good Friday and Easter Monday vary — use holidays lib if available
    if _HAS_HOLIDAYS:
        try:
            ecb = holidays_lib.financial_holidays("ECB", years=year)
            fixed.update(ecb)
        except Exception:
            pass
    return fixed


def isda_holidays(center_code: str, year: int) -> dict[date, str]:
    """Get holidays for an ISDA financial center using the holidays library.

    Supported centers (holidays>=0.40): NYSE, XNYS, ECB, TAR, XECB,
    B3, BVMF, BSE, NSE, XBOM, XNSE, IFEU.
    Returns empty dict for unsupported centers.
    """
    if not _HAS_HOLIDAYS:
        return {}
    try:
        return holidays_lib.financial_holidays(center_code, years=year)
    except NotImplementedError:
        log.debug("isda_center_not_available", center=center_code)
        return {}


def is_settlement_holiday(market_code: str, d: date) -> bool:
    """Check if date is a settlement holiday for any of the market's ISDA centers."""
    market = get_market(market_code)
    for center in market.isda_centers:
        hols = isda_holidays(center, d.year)
        if d in hols:
            return True
    return False


def holiday_hits_for_date(currencies: list[str], check_date: date) -> list[HolidayHit]:
    """Check which currencies have a holiday on the given date."""
    hits: list[HolidayHit] = []
    year = check_date.year

    for ccy in currencies:
        market_codes = markets_for_currency(ccy)
        for mc in market_codes:
            market = get_market(mc)

            # Special handling for TARGET2 (EUR)
            if market.calendar_type == "target2":
                t2 = _target2_holidays(year)
                if check_date in t2:
                    hits.append(HolidayHit(
                        currency=ccy,
                        market_code=mc,
                        date=check_date,
                        name=t2[check_date],
                    ))
                continue

            country_hols = _get_country_holidays(market.country_code, year)
            if check_date in country_hols:
                hits.append(HolidayHit(
                    currency=ccy,
                    market_code=mc,
                    date=check_date,
                    name=country_hols[check_date],
                ))

    return hits


def holiday_hits_for_timestamp(
    currencies: list[str],
    utc_dt: datetime,
) -> list[HolidayHit]:
    """Check holidays for currencies at a UTC timestamp.

    Converts to each market's local date before checking.
    """
    hits: list[HolidayHit] = []
    year = utc_dt.year

    for ccy in currencies:
        market_codes = markets_for_currency(ccy)
        for mc in market_codes:
            market = get_market(mc)
            tz = ZoneInfo(market.timezone)
            local_date = utc_dt.astimezone(tz).date()

            if market.calendar_type == "target2":
                t2 = _target2_holidays(year)
                if local_date in t2:
                    hits.append(HolidayHit(
                        currency=ccy,
                        market_code=mc,
                        date=local_date,
                        name=t2[local_date],
                    ))
                continue

            country_hols = _get_country_holidays(market.country_code, year)
            if local_date in country_hols:
                hits.append(HolidayHit(
                    currency=ccy,
                    market_code=mc,
                    date=local_date,
                    name=country_hols[local_date],
                ))

    return hits
