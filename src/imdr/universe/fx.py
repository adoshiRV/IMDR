"""FX Universe — currencies, pair conventions, provider series, market hours."""

from __future__ import annotations

from datetime import datetime
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel

from imdr.universe.base import BaseUniverse

_UNIVERSE_PATH = Path(__file__).parent / "fx.yml"


class SeriesConfig(BaseModel):
    tenor: str
    deal_type: str


class ProviderConfig(BaseModel):
    g10: list[str] = []
    em_ndf: list[str] = []
    em_deliverable: list[str] = []
    auth_type: str = "basic"
    base_url: str = ""

    model_config = {"extra": "allow"}


class MarketHoursConfig(BaseModel):
    open_day: int  # 0=Monday, 6=Sunday
    open_hour: int
    close_day: int
    close_hour: int


class ExpectedRange(BaseModel):
    """Hard bounds for a symbol — prices outside these are corrupt."""

    min: float
    max: float


class CurrenciesConfig(BaseModel):
    g10: list[str] = []
    em_ndf: list[str] = []
    em_deliverable: list[str] = []


class FXUniverseConfig(BaseModel):
    currencies: CurrenciesConfig
    classifications: dict[str, str]
    pair_priority: list[str]
    market_hours: MarketHoursConfig
    series: dict[str, SeriesConfig]
    providers: dict[str, ProviderConfig]
    expected_ranges: dict[str, ExpectedRange] = {}


class FXUniverse(BaseUniverse):
    """FX instrument universe with pair conventions, classifications, and provider mappings."""

    def __init__(self, config: FXUniverseConfig) -> None:
        self._config = config
        self._priority = {ccy: i for i, ccy in enumerate(config.pair_priority)}

    @property
    def g10(self) -> list[str]:
        return self._config.currencies.g10

    @property
    def em_ndf(self) -> list[str]:
        return self._config.currencies.em_ndf

    @property
    def em_deliverable(self) -> list[str]:
        return self._config.currencies.em_deliverable

    @property
    def all_currencies(self) -> list[str]:
        return self.g10 + self.em_ndf + self.em_deliverable

    @property
    def active_currencies(self) -> list[str]:
        """All non-USD currencies (USD is always the counter)."""
        return [c for c in self.all_currencies if c != "USD"]

    def instruments(self) -> list[str]:
        """All FX pairs in dotted notation (e.g. 'EUR.USD')."""
        pairs = []
        for ccy in self.active_currencies:
            base, quote = self._order_pair(ccy, "USD")
            pairs.append(f"{base}.{quote}")
        return pairs

    def api_symbols(self) -> list[str]:
        """All FX pairs in compact format (e.g. 'EURUSD')."""
        return [self.compact_symbol(p) for p in self.instruments()]

    @staticmethod
    def compact_symbol(dotted: str) -> str:
        """'EUR.USD' -> 'EURUSD'"""
        return dotted.replace(".", "")

    @staticmethod
    def dotted_symbol(compact: str) -> str:
        """'EURUSD' -> 'EUR.USD'"""
        return f"{compact[:3]}.{compact[3:]}"

    def _order_pair(self, ccy1: str, ccy2: str) -> tuple[str, str]:
        """Order a pair according to market convention priority."""
        p1 = self._priority.get(ccy1, 999)
        p2 = self._priority.get(ccy2, 999)
        if p1 <= p2:
            return ccy1, ccy2
        return ccy2, ccy1

    def candidates_for(self, symbol: str) -> list[str]:
        """Return [primary, flipped] compact symbols for pair resolution.

        If BidFX doesn't have USDTRY, try TRYUSD.
        """
        compact = symbol.replace(".", "")
        base, quote = compact[:3], compact[3:]
        flipped = f"{quote}{base}"
        return [compact, flipped]

    def classification_for(self, ccy: str) -> str:
        """Get classification (g10, em_ndf, em_deliverable) for a currency."""
        cls = self._config.classifications.get(ccy.upper())
        if cls is None:
            msg = f"Currency '{ccy}' not found in universe classifications"
            raise KeyError(msg)
        return cls

    def provider_series(self, provider: str, ccy: str) -> list[str]:
        """Which series a provider should fetch for a given currency's classification."""
        prov = self._config.providers.get(provider)
        if prov is None:
            msg = f"Provider '{provider}' not found in universe"
            raise KeyError(msg)
        cls = self.classification_for(ccy)
        return getattr(prov, cls, [])

    def series_config(self, series_name: str) -> SeriesConfig:
        """Get tenor/deal_type for a series name."""
        cfg = self._config.series.get(series_name)
        if cfg is None:
            msg = f"Series '{series_name}' not found in universe"
            raise KeyError(msg)
        return cfg

    def provider_config(self, provider: str) -> ProviderConfig:
        """Get full provider configuration."""
        prov = self._config.providers.get(provider)
        if prov is None:
            msg = f"Provider '{provider}' not found in universe"
            raise KeyError(msg)
        return prov

    def expected_range_for(self, symbol: str) -> ExpectedRange | None:
        """Get hard bounds for a symbol, or None if not configured."""
        return self._config.expected_ranges.get(symbol)

    def is_fx_open(self, dt: datetime) -> bool:
        """Check if the FX market is open at a given UTC datetime.

        FX market opens Sunday 21:00 UTC and closes Friday 21:00 UTC.
        """
        mh = self._config.market_hours
        weekday = dt.weekday()  # 0=Monday, 6=Sunday
        hour = dt.hour

        # Sunday: only open from 21:00 onwards
        if weekday == mh.open_day:
            return hour >= mh.open_hour

        # Friday: only open until 21:00
        if weekday == mh.close_day:
            return hour < mh.close_hour

        # Saturday: always closed
        if weekday == 5:
            return False

        # Monday through Thursday: always open
        return True


@lru_cache(maxsize=1)
def get_fx_universe(config_path: Path = _UNIVERSE_PATH) -> FXUniverse:
    """Load and cache the FX universe from YAML."""
    with open(config_path) as f:
        raw = yaml.safe_load(f)
    config = FXUniverseConfig.model_validate(raw)
    return FXUniverse(config)
