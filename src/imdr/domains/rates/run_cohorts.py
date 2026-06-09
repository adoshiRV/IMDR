"""Region-aware cohort selection for staggered rates ingest.

Routes curves into ASIA / EUROPE / AMERICAS runs so each region's data lands
in the DB shortly after that region's curves settle in Citi, instead of
waiting for a single US-anchored daily run after NY close.

Routing rules
-------------
1. Curves listed in ``LATE_PUBLISH_CURVES`` always route to AMERICAS (the
   late run), regardless of the underlying currency's home market. These
   are overnight publishers (Fed H.15, BoC, JSCC/LCH CCP marks) whose data
   isn't available until after NY close anyway.

2. Every other active curve routes by its currency's primary market:
   currency → country_code (via ``countries_for_currency``, picking the
   first alphabetically — every ccy maps to exactly one country today, so
   "primary" and "the country" are the same) → REGION.

3. Ceased curves never route to any cohort — historical-only curves should
   not be re-queried in scheduled runs.

UTC auto-resolution
-------------------
``resolve_region_auto(now_utc)`` maps the current UTC time to whichever
region's data is freshly available, so a single ``--region auto`` script
invocation picks the right cohort for the current trigger time.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from imdr.market_calendar.calendar import last_business_day
from imdr.market_calendar.countries import countries_for_currency, default_calendar

if TYPE_CHECKING:
    from imdr.universe.rates import CurveEntry


# Curves whose data only becomes available after NY close, regardless of
# the underlying currency's home market.
#   (USD, SOFR)        — NY Fed publishes T+1 ~12:00 UTC
#   (USD, FEDFUND)     — NY Fed H.15 release T+1 ~13:00 UTC
#   (CAD, CORRA)       — Bank of Canada publishes T+1 ~13:00 UTC
#   (JPY, TONAR_JSCC)  — JSCC CCP mark, post-Asia EOD batch
#   (JPY, TONAR_LCH)   — LCH CCP mark, post-London EOD batch
LATE_PUBLISH_CURVES: frozenset[tuple[str, str]] = frozenset({
    ("USD", "SOFR"),
    ("USD", "FEDFUND"),
    ("CAD", "CORRA"),
    ("JPY", "TONAR_JSCC"),
    ("JPY", "TONAR_LCH"),
})


# Country codes (from src/imdr/market_calendar/countries.yml) grouped by region.
REGION_MARKETS: dict[str, frozenset[str]] = {
    "asia":     frozenset({"AU", "NZ", "JP", "HK", "SG", "TH", "CN",
                           "ID", "IN", "KR", "MY", "PH", "TW", "VN"}),
    "europe":   frozenset({"EU", "UK", "CH", "NO", "SE", "DK"}),
    "americas": frozenset({"US", "CA", "MX"}),
}


# Anchor market for ``last_business_day(...)`` per region. Picks the latest-
# closing market in each cohort so the "target date" reflects when the
# region's data has actually settled.
REGION_ANCHORS: dict[str, str] = {
    "asia":     "JP",
    "europe":   "UK",
    "americas": "US",
}


# UTC fire windows for ``--region auto``. Each window is (start_hour,
# end_hour) — half-open; if start > end the window wraps midnight UTC.
#
# Sized so that:
#   - ASIA fires after Asia equity close (~10:00 UTC = 18:00 SGT)
#   - EUROPE fires after London close (~17:30 UTC = 01:30 SGT)
#   - AMERICAS fires after NY close + Citi publish (~22:00 UTC = 06:00 SGT)
#
# Windows don't overlap; gaps between windows return ``None`` from
# resolve_region_auto so a stray fire outside any window is a no-op.
UTC_FIRE_WINDOWS: dict[str, tuple[int, int]] = {
    "asia":     (8,  15),    # 08:00 → 15:00 UTC
    "europe":   (16, 21),    # 16:00 → 21:00 UTC
    "americas": (21,  6),    # 21:00 → 06:00 UTC (wraps midnight)
}


# Last 3-hourly snapshot fire hour per region under imdr_snapshots_citi's
# 0/3/6/.../21 UTC schedule. Fires at this hour (and only this hour) pull
# the full quote set including static/derived quotes (bfly, ssw, rc) that
# don't move intraday — earlier fires in the same window pull only the
# live quote set (par, spread, fwd) to save tag-budget.
#   asia:     window 08-15 → fires 09, 12 → last = 12
#   europe:   window 16-21 → fires 18    → only = 18
#   americas: window 21-06 → fires 21, 00, 03 → last (latest before 06) = 03
STATIC_QUOTE_FIRE_HOURS: dict[str, int] = {
    "asia":     12,
    "europe":   18,
    "americas": 3,
}


VALID_REGIONS: frozenset[str] = frozenset({"asia", "europe", "americas", "all"})


def select_curves(curves: list["CurveEntry"], region: str) -> list["CurveEntry"]:
    """Filter ``curves`` to the cohort for ``region``.

    Ceased curves are always excluded (historical-only). When
    ``region == 'all'`` returns every active curve unchanged — back-compat
    for full-run invocations and historical backfills.
    """
    if region not in VALID_REGIONS:
        raise ValueError(
            f"Unknown region {region!r}; expected one of {sorted(VALID_REGIONS)}"
        )

    active = [c for c in curves if c.status != "ceased"]
    if region == "all":
        return active

    target_markets = REGION_MARKETS[region]
    is_late_region = region == "americas"
    out: list["CurveEntry"] = []
    for c in active:
        key = (c.ccy, c.curve)
        if key in LATE_PUBLISH_CURVES:
            if is_late_region:
                out.append(c)
            continue
        primary_countries = countries_for_currency(c.ccy)
        if not primary_countries:
            continue
        if primary_countries[0] in target_markets:
            out.append(c)
    return out


def target_for_region(region: str) -> datetime:
    """Region-anchored ``last_business_day`` (UTC midnight).

    Resolves the anchor country (``US``/``UK``/``JP``) to its project-wide
    default calendar via ``default_calendar()``. For US that's ``GT`` (SIFMA
    Govt Bond) — Veterans Day closes SIFMA but not NYSE. UK and JP fall back
    to equity calendars (``LS``/``JN``) because no DB-resident rates
    calendars exist for them; see
    ``docs/admin/development/per_script_calendar_intent.md`` for the gap.
    """
    anchor = REGION_ANCHORS.get(region, "US")
    return last_business_day(anchor, default_calendar(anchor))


def _hour_in_window(hour: int, window: tuple[int, int]) -> bool:
    lo, hi = window
    if lo < hi:
        return lo <= hour < hi
    return hour >= lo or hour < hi


def resolve_region_auto(now_utc: datetime | None = None) -> str | None:
    """Return the region whose UTC fire window contains ``now_utc``.

    Returns ``None`` if no window matches (gaps between windows). Caller
    should treat ``None`` as "no-op skip" rather than falling back to
    ``all`` — preserves the design intent that scheduled fires only run
    when their target region has data available.
    """
    if now_utc is None:
        now_utc = datetime.now(timezone.utc)
    hour = now_utc.hour
    for region, window in UTC_FIRE_WINDOWS.items():
        if _hour_in_window(hour, window):
            return region
    return None


def default_run_label(region: str) -> str:
    """Stable label used in RunReport names, email subjects, and log filenames."""
    return f"{region.upper()}_PM"


def is_static_quote_fire(region: str, now_utc: datetime | None = None) -> bool:
    """True when the current UTC hour matches the region's once-per-day
    static-quote fire slot defined in ``STATIC_QUOTE_FIRE_HOURS``.

    Used by the live runner under ``--region auto`` to gate when the
    derived quotes (bfly, ssw, rc) are pulled — once per region per day
    instead of on every fire in that region's window.
    """
    if region not in STATIC_QUOTE_FIRE_HOURS:
        return False
    if now_utc is None:
        now_utc = datetime.now(timezone.utc)
    return now_utc.hour == STATIC_QUOTE_FIRE_HOURS[region]
