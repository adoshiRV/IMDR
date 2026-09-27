"""Scalar parsers shared by the RBI fetchers.

RBI serves the same two scalars in a different shape on every surface --
press-release XLSX, DBIE SAP-BO table, Bulletin table -- and both are
easy to get subtly wrong:

* **Dates.** Day-first with a dot (`26.Jul,2024`), month-first with a
  comma (`Jun 30, 2026`), and the older press-release form
  (`Mar.29, 2019`) all appear. Handing one of these to
  `datetime.strptime` with a single format silently drops the column.
* **Numbers.** Indian digit grouping (`1,63,55,330`) is not 3-digit, so
  a locale-aware float parse is wrong; and the missing-value vocabulary
  is a small zoo (`-`, `..`, `NA`, `*`, `#`) that must become None
  rather than 0.
"""
from __future__ import annotations

import datetime
import re

MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"], start=1)}

# `26.Jul,2024` / `4.Apr,2025` / `28.Aug,2020` / `31 March 2026`
_DAY_FIRST = re.compile(
    r"^\s*(\d{1,2})\s*[.,]?\s*([A-Za-z]{3,9})\.?\s*[,.]?\s*(\d{4})\s*$")
# `Jun. 23, 2017` / `Mar.29, 2019` / `Jun 30,2026`
_MONTH_FIRST = re.compile(
    r"^\s*([A-Za-z]{3,9})\.?\s*(\d{1,2})\s*,\s*(\d{4})\s*$")

# Everything RBI uses to mean "no value". Zero is NOT among them.
NULL_TOKENS = frozenset({"", "-", "--", "..", ".", "NA", "N.A.", "N.A",
                         "n.a.", "*", "#", "nil", "Nil"})


def month_number(name: str) -> int | None:
    """`'Jul'`, `'July'`, `'JULY'` -> 7. Unknown -> None."""
    key = name.strip().lower().rstrip(".")
    if key in MONTHS:
        return MONTHS[key]
    return next((v for k, v in MONTHS.items() if k.startswith(key[:3])), None)


def parse_date(cell: object) -> datetime.date | None:
    """Any RBI date spelling -> a date. Anything else -> None."""
    if isinstance(cell, datetime.datetime):
        return cell.date()
    if isinstance(cell, datetime.date):
        return cell
    if cell is None:
        return None
    text = str(cell)
    for rx, day_first in ((_DAY_FIRST, True), (_MONTH_FIRST, False)):
        m = rx.match(text)
        if not m:
            continue
        day, mon = (m.group(1), m.group(2)) if day_first else (m.group(2), m.group(1))
        mi = month_number(mon)
        if mi is None:
            return None
        try:
            return datetime.date(int(m.group(3)), mi, int(day))
        except ValueError:
            return None
    return None


def parse_number(cell: object) -> float | None:
    """Indian-grouped numeric string -> float; a null token -> None.

    `bool` is rejected explicitly: it is an `int` subclass, so a stray
    True would otherwise arrive as the value 1.0.
    """
    if cell is None or isinstance(cell, bool):
        return None
    if isinstance(cell, (int, float)):
        return float(cell)
    text = str(cell).replace(",", "").strip()
    if text in NULL_TOKENS or str(cell).strip() in NULL_TOKENS:
        return None
    try:
        return float(text)
    except ValueError:
        return None
