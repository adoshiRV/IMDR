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
