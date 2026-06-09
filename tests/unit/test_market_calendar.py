"""Tests for market calendar module."""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from imdr.market_calendar.countries import (
    countries_for_currency,
    country_local_date,
    get_country,
    load_countries,
)
from imdr.market_calendar.events import market_events_for_date


def test_load_countries():
    config = load_countries()
    assert "US" in config.countries
    assert "EU" in config.countries
    assert "JP" in config.countries


def test_get_country_us():
    country = get_country("US")
    assert country.timezone == "America/New_York"
    assert "USD" in country.currencies
    assert "NYSE" in country.exchanges


def test_get_country_eu():
    country = get_country("EU")
    assert country.calendar_type == "target2"
    assert "EUR" in country.currencies


def test_country_local_date():
    # 2026-03-09 23:30 UTC = 2026-03-10 in Tokyo
    utc_dt = datetime(2026, 3, 9, 23, 30, tzinfo=ZoneInfo("UTC"))
    local = country_local_date("JP", utc_dt)
    assert local == date(2026, 3, 10)


def test_countries_for_currency():
    countries = countries_for_currency("USD")
    assert "US" in countries

    countries = countries_for_currency("EUR")
    assert "EU" in countries

    countries = countries_for_currency("JPY")
    assert "JP" in countries


def test_countries_for_currency_sorted(monkeypatch):
    """Output is sorted alphabetically — guarantees deterministic [0] selection
    even when a currency is mapped to multiple countries (future-proofing for
    cases like a pegged currency listed under both its home and peg country).
    """
    from imdr.market_calendar import countries as countries_mod

    fake = countries_mod.CountriesConfig.model_validate({
        "countries": {
            "ZZ": {"timezone": "UTC", "currencies": ["XXX"], "exchanges": [],
                   "calendar_type": "global", "country_code": "ZZ"},
            "AA": {"timezone": "UTC", "currencies": ["XXX"], "exchanges": [],
                   "calendar_type": "global", "country_code": "AA"},
            "MM": {"timezone": "UTC", "currencies": ["XXX"], "exchanges": [],
                   "calendar_type": "global", "country_code": "MM"},
        },
    })
    monkeypatch.setattr(countries_mod, "load_countries", lambda *a, **kw: fake)
    assert countries_mod.countries_for_currency("XXX") == ["AA", "MM", "ZZ"]


def test_events_for_date():
    events = market_events_for_date(date(2026, 1, 29))
    us_events = [e for e in events if e.market == "US"]
    assert len(us_events) > 0
    assert us_events[0].type == "central_bank"


def test_events_filter_by_market():
    events = market_events_for_date(date(2026, 1, 29), market="US")
    assert all(e.market == "US" for e in events)


# ── New model fields tests ──────────────────────────────────────

def test_country_weekend_days_default():
    country = get_country("US")
    assert country.weekend_days == [5, 6]


def test_country_weekend_days_israel():
    country = get_country("IL")
    assert country.weekend_days == [4, 5]


def test_country_isda_centers():
    country = get_country("US")
    assert "NYSE" in country.isda_centers


def test_country_trading_hours():
    country = get_country("US")
    assert country.trading_hours is not None
    assert country.trading_hours.open == "09:30"
    assert country.trading_hours.close == "16:00"


def test_country_trading_hours_lunch():
    country = get_country("JP")
    assert country.trading_hours is not None
    assert country.trading_hours.lunch_start == "11:30"
    assert country.trading_hours.lunch_end == "12:30"


def test_new_countries_exist():
    """Verify new countries added for rates coverage are loadable."""
    for code in ["DK", "VN", "SA", "AE", "AR", "EG", "NG", "RO", "KZ", "BD", "LK"]:
        country = get_country(code)
        assert country.country_code is not None


def test_cn_covers_cnh():
    """CN country should list both CNY and CNH."""
    country = get_country("CN")
    assert "CNY" in country.currencies
    assert "CNH" in country.currencies
