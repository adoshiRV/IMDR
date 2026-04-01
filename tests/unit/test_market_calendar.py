"""Tests for market calendar module."""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from imdr.market_calendar.events import market_events_for_date
from imdr.market_calendar.markets import get_market, load_markets, market_local_date, markets_for_currency


def test_load_markets():
    config = load_markets()
    assert "US" in config.markets
    assert "EU" in config.markets
    assert "JP" in config.markets


def test_get_market_us():
    market = get_market("US")
    assert market.timezone == "America/New_York"
    assert "USD" in market.currencies
    assert "NYSE" in market.exchanges


def test_get_market_eu():
    market = get_market("EU")
    assert market.calendar_type == "target2"
    assert "EUR" in market.currencies


def test_market_local_date():
    # 2026-03-09 23:30 UTC = 2026-03-10 in Tokyo
    utc_dt = datetime(2026, 3, 9, 23, 30, tzinfo=ZoneInfo("UTC"))
    local = market_local_date("JP", utc_dt)
    assert local == date(2026, 3, 10)


def test_markets_for_currency():
    markets = markets_for_currency("USD")
    assert "US" in markets

    markets = markets_for_currency("EUR")
    assert "EU" in markets

    markets = markets_for_currency("JPY")
    assert "JP" in markets


def test_events_for_date():
    events = market_events_for_date(date(2026, 1, 29))
    us_events = [e for e in events if e.market == "US"]
    assert len(us_events) > 0
    assert us_events[0].type == "central_bank"


def test_events_filter_by_market():
    events = market_events_for_date(date(2026, 1, 29), market="US")
    assert all(e.market == "US" for e in events)


# ── New model fields tests ──────────────────────────────────────

def test_market_weekend_days_default():
    market = get_market("US")
    assert market.weekend_days == [5, 6]


def test_market_weekend_days_israel():
    market = get_market("IL")
    assert market.weekend_days == [4, 5]


def test_market_isda_centers():
    market = get_market("US")
    assert "NYSE" in market.isda_centers


def test_market_trading_hours():
    market = get_market("US")
    assert market.trading_hours is not None
    assert market.trading_hours.open == "09:30"
    assert market.trading_hours.close == "16:00"


def test_market_trading_hours_lunch():
    market = get_market("JP")
    assert market.trading_hours is not None
    assert market.trading_hours.lunch_start == "11:30"
    assert market.trading_hours.lunch_end == "12:30"


def test_new_markets_exist():
    """Verify new markets added for rates coverage are loadable."""
    for code in ["DK", "VN", "SA", "AE", "AR", "EG", "NG", "RO", "KZ", "BD", "LK"]:
        market = get_market(code)
        assert market.country_code is not None


def test_cn_covers_cnh():
    """CN market should list both CNY and CNH."""
    market = get_market("CN")
    assert "CNY" in market.currencies
    assert "CNH" in market.currencies
