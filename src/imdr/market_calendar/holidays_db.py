"""DB-backed, vendor-aware holiday lookup.

Reads from `calendar.market_holidays` (multi-vendor fact). Callers identify the
calendar by `calendar_code` and (optionally) preferred vendor; vendor priority
falls back through :data:`GLOBAL_VENDOR_PRIORITY` when no preference is given
or the preferred vendor has no rows.

Caches are populated lazily on first access and can be invalidated with
:func:`refresh`. The data set is tiny (~25K holidays × N vendors), so we keep
everything in process memory.

Phase D Step 3 (2026-05-13): the `dim_market_calendar` segment bridge has been
removed from this module — modern callers pass `calendar_code` directly. The
legacy `(market_code, segment)` resolution still exists, scoped to the legacy
paths in :mod:`imdr.market_calendar.calendar`, and is removed in Step 11.
"""

from __future__ import annotations

import threading
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

import structlog
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DatabaseError, OperationalError, ProgrammingError

from imdr.config.settings import get_settings
from imdr.connectors.mssql import MSSQLConnector

log = structlog.get_logger(__name__)

# Order is "trust this vendor first if no per-market trusted_vendor_id is set
# OR if the trusted vendor has no rows for the calendar". MANUAL beats
# everything so an override row always wins.
GLOBAL_VENDOR_PRIORITY: tuple[str, ...] = (
    "MANUAL",
    "BBG",
    "EXCHANGE_CALENDARS",
    "HOLIDAYS_LIB",
)

# Country with NULL weekend_days (pseudo-countries EU/WW/XX/RU) falls back here.
_DEFAULT_WEEKEND: frozenset[int] = frozenset({5, 6})


# ─── Cache state ─────────────────────────────────────────────────────────

_LOCK = threading.Lock()

# (calendar_code, vendor_code) → frozenset of holiday dates
_HOLIDAYS: dict[tuple[str, str], frozenset[date]] | None = None

# calendar_code → set of vendor codes that have rows for this calendar
_VENDORS_BY_CAL: dict[str, frozenset[str]] | None = None

# country_code → frozenset of Python weekday ints (0=Mon..6=Sun).
# Sourced from dbo.dim_country.weekend_days (canonical, country-anchor restructure).
_WEEKEND_DAYS_BY_COUNTRY: dict[str, frozenset[int]] | None = None

# Country codes we've already logged a fallback warning for (dedupe to avoid log spam).
_WEEKEND_FALLBACK_WARNED: set[str] = set()

_engine: Engine | None = None


def _get_engine() -> Engine:
    """Lazy singleton engine — avoid building a connector at import time."""
    global _engine
    if _engine is None:
        _engine = MSSQLConnector(get_settings()).read_engine
    return _engine


def _load() -> None:
    """Populate the holidays + vendor caches. Idempotent under the module lock.

    If `calendar.market_holidays` doesn't exist (migration 031 not applied) or
    the DB is unreachable, the caches initialise empty and every lookup
    returns None — callers (e.g. :mod:`imdr.market_calendar.calendar`) fall
    through to the legacy `holidays`-library path.
    """
    global _HOLIDAYS, _VENDORS_BY_CAL

    with _LOCK:
        if _HOLIDAYS is not None:
            return

        try:
            engine = _get_engine()
            with engine.connect() as conn:
                holiday_rows = conn.execute(text("""
                    SELECT c.calendar_code, v.vendor_code, mh.holiday_date
                    FROM calendar.market_holidays mh
                    JOIN calendar.dim_calendar c ON c.id = mh.calendar_id
                    JOIN dbo.dim_vendor v        ON v.id = mh.vendor_id
                """)).all()
        except (ProgrammingError, OperationalError, DatabaseError) as exc:
            log.warning("market_holidays_load_failed_using_legacy", error=str(exc))
            _HOLIDAYS = {}
            _VENDORS_BY_CAL = {}
            return

        bucket: dict[tuple[str, str], set[date]] = {}
        for cal, vendor, d in holiday_rows:
            # The legacy 'SQL Server' ODBC driver returns DATE columns as
            # strings on some setups; normalise to datetime.date so set
            # membership and range comparisons work consistently.
            if isinstance(d, str):
                d = date.fromisoformat(d)
            elif hasattr(d, "date") and not isinstance(d, date):
                d = d.date()
            bucket.setdefault((cal, vendor), set()).add(d)
        _HOLIDAYS = {k: frozenset(v) for k, v in bucket.items()}

        vendors: dict[str, set[str]] = {}
        for cal, vendor in _HOLIDAYS:
            vendors.setdefault(cal, set()).add(vendor)
        _VENDORS_BY_CAL = {k: frozenset(v) for k, v in vendors.items()}


def refresh() -> None:
    """Drop this module's in-memory caches; next call re-queries the DB.

    Clears the holiday + vendor caches and the weekend-days cache. Use after a
    bulk load (Excel ingest, exchange_calendars loader) or in tests that need
    to reset state between cases.
    """
    global _HOLIDAYS, _VENDORS_BY_CAL, _WEEKEND_DAYS_BY_COUNTRY
    with _LOCK:
        _HOLIDAYS = None
        _VENDORS_BY_CAL = None
        _WEEKEND_DAYS_BY_COUNTRY = None
        _WEEKEND_FALLBACK_WARNED.clear()


def _load_weekend_days() -> None:
    """Populate the country → weekend_days cache from dbo.dim_country.

    Parses the comma-separated `weekend_days` VARCHAR (e.g. "5,6" or "4,5")
    into a set of Python weekday ints. Pseudo-countries with NULL weekend_days
    are simply absent from the cache; callers fall back to _DEFAULT_WEEKEND.

    If the DB is unreachable or dim_country is missing (shouldn't happen post
    migration 037), the cache initialises empty and all lookups fall back.
    """
    global _WEEKEND_DAYS_BY_COUNTRY
    with _LOCK:
        if _WEEKEND_DAYS_BY_COUNTRY is not None:
            return

        try:
            engine = _get_engine()
            with engine.connect() as conn:
                rows = conn.execute(text("""
                    SELECT country_code, weekend_days
                    FROM dbo.dim_country
                    WHERE weekend_days IS NOT NULL
                """)).all()
        except (ProgrammingError, OperationalError, DatabaseError) as exc:
            log.warning("weekend_days_load_failed_using_default", error=str(exc))
            _WEEKEND_DAYS_BY_COUNTRY = {}
            return

        cache: dict[str, frozenset[int]] = {}
        for country_code, weekend_days_str in rows:
            try:
                days = frozenset(
                    int(d.strip()) for d in weekend_days_str.split(",") if d.strip()
                )
            except (ValueError, AttributeError):
                log.warning(
                    "weekend_days_parse_failed",
                    country_code=country_code,
                    value=weekend_days_str,
                )
                continue
            cache[country_code] = days
        _WEEKEND_DAYS_BY_COUNTRY = cache


def get_weekend_days(country_code: str) -> frozenset[int]:
    """Return the weekend weekday ints (0=Mon..6=Sun) for a country.

    Reads from `dbo.dim_country.weekend_days` (DB is canonical after the
    country-anchor restructure). Pseudo-countries (EU, WW, XX, RU) and any
    country with NULL `weekend_days` fall back to Saturday/Sunday `{5, 6}`.

    Unknown country codes (not present in dim_country at all) log a one-time
    warning per code, then fall back to the same default. This is a soft
    contract for backwards compatibility with callers passing legacy market
    codes; the strict-validation surface comes in Step 2 of Phase D.
    """
    if _WEEKEND_DAYS_BY_COUNTRY is None:
        _load_weekend_days()
    assert _WEEKEND_DAYS_BY_COUNTRY is not None  # noqa: S101 — invariant

    hit = _WEEKEND_DAYS_BY_COUNTRY.get(country_code)
    if hit is not None:
        return hit

    if country_code not in _WEEKEND_FALLBACK_WARNED:
        _WEEKEND_FALLBACK_WARNED.add(country_code)
        log.warning(
            "weekend_days_fallback_to_default",
            country_code=country_code,
            default=sorted(_DEFAULT_WEEKEND),
            reason=(
                "country_code not found in dim_country, or its weekend_days is NULL "
                "(pseudo-countries EU/WW/XX/RU). Returning Sat/Sun default."
            ),
        )
    return _DEFAULT_WEEKEND


# ─── Public API ──────────────────────────────────────────────────────────


def resolve_holiday_set(
    calendar_code: str, trusted_vendor: str | None = None,
) -> frozenset[date] | None:
    """Return the trusted holiday set for one calendar, falling back through
    GLOBAL_VENDOR_PRIORITY if the trusted vendor has no rows.

    Returns None if no vendor has rows for this calendar at all — the caller
    decides whether to use a legacy fallback or treat as "no holidays".
    """
    if _HOLIDAYS is None:
        _load()
    assert _HOLIDAYS is not None and _VENDORS_BY_CAL is not None  # noqa: S101

    available = _VENDORS_BY_CAL.get(calendar_code)
    if not available:
        return None

    # Try the trusted vendor first if it has data; then walk the global order.
    candidate_order: list[str] = []
    if trusted_vendor and trusted_vendor in available:
        candidate_order.append(trusted_vendor)
    for v in GLOBAL_VENDOR_PRIORITY:
        if v in available and v not in candidate_order:
            candidate_order.append(v)

    for vendor in candidate_order:
        hols = _HOLIDAYS.get((calendar_code, vendor))
        if hols:
            return hols

    return None


def is_holiday_db(
    calendar_code: str, d: date, *, trusted_vendor: str | None = None,
) -> bool | None:
    """Vendor-aware holiday check.

    Returns:
      * True / False — the trusted (or next-priority) vendor has coverage and
        answered.
      * None — no vendor has rows for this calendar; caller should fall back.
    """
    hols = resolve_holiday_set(calendar_code, trusted_vendor)
    if hols is None:
        return None
    return d in hols


# ─── Reconciliation helper (off the hot path) ────────────────────────────

@dataclass(frozen=True)
class Disagreement:
    calendar_code: str
    holiday_date: date
    vendors_say_holiday: frozenset[str]
    vendors_say_trading: frozenset[str]


def vendor_disagreements(
    calendar_code: str, start: date, end: date,
    vendors: Iterable[str] | None = None,
) -> list[Disagreement]:
    """Dates in [start, end] where vendors disagree about holiday status.

    Only flags dates that are a holiday per at least one vendor — silent
    agreement (everyone says trading day) is not surfaced.
    """
    if _HOLIDAYS is None:
        _load()
    assert _HOLIDAYS is not None and _VENDORS_BY_CAL is not None  # noqa: S101

    available = _VENDORS_BY_CAL.get(calendar_code, frozenset())
    if vendors is not None:
        available = available & frozenset(vendors)
    if len(available) < 2:
        return []  # need at least two vendors to disagree

    # Union of all holiday dates in the window across the chosen vendors.
    candidate_dates: set[date] = set()
    for v in available:
        for d in _HOLIDAYS.get((calendar_code, v), frozenset()):
            if start <= d <= end:
                candidate_dates.add(d)

    out: list[Disagreement] = []
    for d in sorted(candidate_dates):
        say_holiday = frozenset(
            v for v in available if d in _HOLIDAYS.get((calendar_code, v), frozenset())
        )
        say_trading = available - say_holiday
        if say_trading:  # disagreement
            out.append(Disagreement(calendar_code, d, say_holiday, say_trading))
    return out
