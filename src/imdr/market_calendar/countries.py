"""Country definitions loader and utilities.

Renamed from ``markets.py`` 2026-05-13 (Phase D Step 5 of the country-anchor
restructure). The on-disk config is now ``countries.yml`` with top-level key
``countries:`` keyed by canonical ``country_code``. The previous
``MarketConfig`` / ``load_markets()`` / ``get_market()`` names retire here —
no deprecation shims (Step 5 is mechanical: all call sites move in lockstep).
"""

from __future__ import annotations

from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml
from pydantic import BaseModel

_COUNTRIES_PATH = Path(__file__).parent / "countries.yml"


class TradingHoursConfig(BaseModel):
    """Equity-style trading hours in local market time."""

    open: str       # "HH:MM" local time
    close: str      # "HH:MM" local time
    lunch_start: str | None = None
    lunch_end: str | None = None


class CountryConfig(BaseModel):
    timezone: str
    currencies: list[str]
    exchanges: list[str]
    calendar_type: str
    country_code: str
    weekend_days: list[int] = [5, 6]                    # Python weekday: 5=Sat, 6=Sun
    isda_centers: list[str] = []                         # ISDA financial center codes
    trading_hours: TradingHoursConfig | None = None      # None = 24h / OTC market


class CountriesConfig(BaseModel):
    countries: dict[str, CountryConfig]


@lru_cache(maxsize=1)
def load_countries(config_path: Path = _COUNTRIES_PATH) -> CountriesConfig:
    """Load and cache country definitions from YAML."""
    with open(config_path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return CountriesConfig.model_validate(raw)


def get_country(country_code: str, config_path: Path = _COUNTRIES_PATH) -> CountryConfig:
    """Get a specific country's config by code (e.g. 'US', 'EU')."""
    config = load_countries(config_path)
    if country_code not in config.countries:
        available = ", ".join(config.countries.keys())
        msg = f"Country '{country_code}' not found. Available: {available}"
        raise KeyError(msg)
    return config.countries[country_code]


def country_local_date(country_code: str, utc_dt: datetime | None = None) -> date:
    """Get the local date for a country at a given UTC datetime."""
    if utc_dt is None:
        utc_dt = datetime.now(ZoneInfo("UTC"))
    country = get_country(country_code)
    tz = ZoneInfo(country.timezone)
    return utc_dt.astimezone(tz).date()


def countries_for_currency(ccy: str) -> list[str]:
    """Find all countries associated with a currency, sorted by country_code.

    Sorted output gives deterministic ``[0]`` selection — callers picking a
    single country for a multi-country ccy get the same answer regardless of
    ``countries.yml`` ordering. For the common single-country case the sort
    is a no-op. Note: ``[0]`` picks the first country alphabetically, not a
    semantic "primary"; callers wanting a specific country should pass the
    country_code explicitly.
    """
    config = load_countries()
    return sorted(
        code
        for code, country in config.countries.items()
        if ccy.upper() in country.currencies
    )


# ─── Project-wide default calendar per country ───────────────────────────
#
# Phase D Step 7 (2026-05-13): explicit per-country default calendar_code,
# replacing the legacy ``calendar.dim_market_calendar`` bridge's silent
# DEFAULT resolution. Each consumer migrating off the legacy API can either:
#
#   1. Pick a specific calendar_code at the call site (preferred when the
#      script's domain is unambiguous — e.g., NYSE equity ingest → "NY").
#   2. Look up the default here when no specific intent applies — e.g.,
#      ``rates/run_cohorts`` picking a regional anchor's trading day.
#
# US default is set to "GT" (SIFMA US Govt Bond) rather than "NY" (NYSE)
# because the original legacy-DEFAULT consumers were predominantly rates
# pipelines. Non-rates scripts that still use this map are flagged as
# tech-debt — see docs/admin/development/per_script_calendar_intent.md.
#
# Countries with zero calendars in ``dbo.dim_calendar`` (BR, MX, PL, TR, IL,
# ZA, RU, BD, KZ, LK, VN, AR, CL, CO, PE, BM, AE, EG, NG, SA, DK, CZ, HU, RO,
# and the EU member states ES/FI/FR/IT/NL) are deliberately ABSENT here.
# A KeyError at the call site is the right surface to flag the gap when a
# future consumer first lands on one of those countries.

DEFAULT_CALENDAR_BY_COUNTRY: dict[str, str] = {
    # Multi-calendar countries — explicit project choice:
    "US": "GT",   # SIFMA US Govt Bond (NOT "NY" / NYSE)
    "JP": "JN",   # TSE (chosen over OK Osaka)
    "NZ": "WL",   # RBNZ Wellington (chosen over KD NZX)
    "PH": "+P",   # Philippines FX Settlement (chosen over PH PSE)
    # Single-calendar countries — only available choice:
    "AU": "AU", "CA": "CA", "CH": "S5", "CN": "I6", "DE": "IB",
    "EU": "TE", "HK": "HK", "ID": "ID", "IN": "RB", "KR": "SK",
    "MY": "MA", "NO": "NO", "SE": "SW", "SG": "SI",
    "TH": "TH", "TW": "TA", "UK": "LS",
}


def default_calendar(country_code: str) -> str:
    """Return the project-wide default calendar_code for a country.

    Raises ``KeyError`` for countries with no calendar configured (most EM
    + EU member states + pseudo-countries). See
    ``DEFAULT_CALENDAR_BY_COUNTRY`` docstring for the rationale.
    """
    try:
        return DEFAULT_CALENDAR_BY_COUNTRY[country_code]
    except KeyError as exc:
        configured = ", ".join(sorted(DEFAULT_CALENDAR_BY_COUNTRY))
        msg = (
            f"No default calendar configured for country {country_code!r}. "
            f"Configured: {configured}. To add one, append to "
            "DEFAULT_CALENDAR_BY_COUNTRY in src/imdr/market_calendar/countries.py "
            "after confirming the calendar exists in calendar.dim_calendar."
        )
        raise KeyError(msg) from exc
