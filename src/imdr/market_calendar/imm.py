"""IMM (International Monetary Market) date utilities.

IMM dates are the 3rd Wednesday of each month. Quarterly IMM dates
(Mar, Jun, Sep, Dec) are the standard futures/swaps roll dates.
"""

from __future__ import annotations

import calendar
from datetime import date

_QUARTERLY_MONTHS = {3, 6, 9, 12}


def imm_date(year: int, month: int) -> date:
    """3rd Wednesday of the given month/year."""
    # Find the first day of the month and its weekday
    first_day_weekday = calendar.weekday(year, month, 1)  # 0=Mon
    # Wednesday = 2. Days until first Wednesday:
    days_to_wed = (2 - first_day_weekday) % 7
    first_wed = 1 + days_to_wed
    third_wed = first_wed + 14
    return date(year, month, third_wed)


def imm_dates_monthly(year: int) -> list[date]:
    """All 12 monthly IMM dates for a year."""
    return [imm_date(year, m) for m in range(1, 13)]


def imm_dates_quarterly(year: int) -> list[date]:
    """Quarterly IMM dates (Mar, Jun, Sep, Dec) for a year."""
    return [imm_date(year, m) for m in sorted(_QUARTERLY_MONTHS)]


def is_imm_date(d: date) -> bool:
    """Check if date is a monthly IMM date (3rd Wednesday of any month)."""
    return d == imm_date(d.year, d.month)


def is_quarterly_imm_date(d: date) -> bool:
    """Check if date is a quarterly IMM date (3rd Wed of Mar/Jun/Sep/Dec)."""
    return d.month in _QUARTERLY_MONTHS and is_imm_date(d)


def next_imm_date(after: date | None = None, quarterly_only: bool = False) -> date:
    """Next IMM date strictly after the given date (default: today)."""
    if after is None:
        after = date.today()

    year, month = after.year, after.month

    # Check up to 13 months ahead (current month might still be valid)
    for _ in range(13):
        if not quarterly_only or month in _QUARTERLY_MONTHS:
            d = imm_date(year, month)
            if d > after:
                return d
        month += 1
        if month > 12:
            month = 1
            year += 1

    msg = f"No IMM date found within 13 months after {after}"
    raise ValueError(msg)
