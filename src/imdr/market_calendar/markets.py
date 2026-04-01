"""Market definitions loader and utilities."""

from __future__ import annotations

from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml
from pydantic import BaseModel

_MARKETS_PATH = Path(__file__).parent / "markets.yml"


class TradingHoursConfig(BaseModel):
    """Equity-style trading hours in local market time."""

    open: str       # "HH:MM" local time
    close: str      # "HH:MM" local time
    lunch_start: str | None = None
    lunch_end: str | None = None


class MarketConfig(BaseModel):
    timezone: str
    currencies: list[str]
    exchanges: list[str]
    calendar_type: str
    country_code: str
    weekend_days: list[int] = [5, 6]                    # Python weekday: 5=Sat, 6=Sun
    isda_centers: list[str] = []                         # ISDA financial center codes
    trading_hours: TradingHoursConfig | None = None      # None = 24h / OTC market


class MarketsConfig(BaseModel):
    markets: dict[str, MarketConfig]


@lru_cache(maxsize=1)
def load_markets(config_path: Path = _MARKETS_PATH) -> MarketsConfig:
    """Load and cache market definitions from YAML."""
    with open(config_path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return MarketsConfig.model_validate(raw)


def get_market(market_code: str, config_path: Path = _MARKETS_PATH) -> MarketConfig:
    """Get a specific market's config by code (e.g. 'US', 'EU')."""
    config = load_markets(config_path)
    if market_code not in config.markets:
        available = ", ".join(config.markets.keys())
        msg = f"Market '{market_code}' not found. Available: {available}"
        raise KeyError(msg)
    return config.markets[market_code]


def market_local_date(market_code: str, utc_dt: datetime | None = None) -> date:
    """Get the local date for a market at a given UTC datetime."""
    if utc_dt is None:
        utc_dt = datetime.now(ZoneInfo("UTC"))
    market = get_market(market_code)
    tz = ZoneInfo(market.timezone)
    return utc_dt.astimezone(tz).date()


def markets_for_currency(ccy: str) -> list[str]:
    """Find all markets associated with a currency."""
    config = load_markets()
    return [
        code
        for code, market in config.markets.items()
        if ccy.upper() in market.currencies
    ]
