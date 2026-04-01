"""Equity Universe — index levels from Citi Velocity."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from imdr.universe.base import BaseUniverse

_UNIVERSE_PATH = Path(__file__).parent / "equity.yml"


class EquityUniverse(BaseUniverse):
    """Equity index universe for EQUITY.EQUITY_INDEX level data."""

    def __init__(self, raw: dict) -> None:
        self._raw = raw

    # ── BaseUniverse interface ─────────────────────────────────

    def instruments(self) -> list[str]:
        """All index tickers."""
        return [e["ticker"] for e in self._all_entries()]

    def api_symbols(self) -> list[str]:
        """All Citi Velocity tags."""
        tpl = self._raw["tag_template"]
        return [tpl.format(ticker=t) for t in self.instruments()]

    # ── Index helpers ──────────────────────────────────────────

    def _all_entries(self) -> list[dict]:
        """Flatten all region lists into a single list."""
        entries: list[dict] = []
        for region_entries in self._raw["indices"].values():
            entries.extend(region_entries)
        return entries

    def regions(self) -> list[str]:
        """Available region keys."""
        return list(self._raw["indices"].keys())

    def indices_for_region(self, region: str) -> list[dict]:
        """Return index entries for a region."""
        return self._raw["indices"].get(region, [])

    def tag_for_ticker(self, ticker: str) -> str:
        """Build Citi tag for a ticker."""
        return self._raw["tag_template"].format(ticker=ticker)

    def ticker_to_display(self) -> dict[str, str]:
        """Return {ticker: display_name} mapping."""
        return {e["ticker"]: e["display_name"] for e in self._all_entries()}

    def ticker_to_currency(self) -> dict[str, str]:
        """Return {ticker: currency} mapping."""
        return {e["ticker"]: e["currency"] for e in self._all_entries()}

    def tag_to_ticker(self) -> dict[str, str]:
        """Return {citi_tag: ticker} reverse mapping."""
        tpl = self._raw["tag_template"]
        return {tpl.format(ticker=e["ticker"]): e["ticker"]
                for e in self._all_entries()}


@lru_cache(maxsize=1)
def get_equity_universe(config_path: Path = _UNIVERSE_PATH) -> EquityUniverse:
    """Load and cache the equity universe from YAML."""
    with open(config_path) as f:
        raw = yaml.safe_load(f)
    return EquityUniverse(raw)
