"""Equity Universe — index levels and VIX family from Citi Velocity."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

import structlog

from imdr.market_calendar.countries import default_calendar
from imdr.schemas.equity import IndexCreate, VIX_TICKERS
from imdr.universe.base import BaseUniverse

_UNIVERSE_PATH = Path(__file__).parent / "equity.yml"

_log = structlog.get_logger("universe.equity")

# Equity data follows EXCHANGE calendars. The project-wide default for US is
# "GT" (SIFMA govt bond), which is wrong for equities -- tracked in
# docs/admin/development/per_script_calendar_intent.md.
_EQUITY_CALENDAR_OVERRIDES: dict[str, str] = {"US": "NY"}


class EquityUniverse(BaseUniverse):
    """Equity index universe for EQUITY.EQUITY_INDEX level data."""

    def __init__(self, raw: dict) -> None:
        self._raw = raw

    # ── BaseUniverse interface ─────────────────────────────────

    def instruments(self) -> list[str]:
        """All index tickers."""
        return [e["ticker"] for e in self._all_entries()]

    def api_symbols(self) -> list[str]:
        """All Citi Velocity tags (indices + VIX family)."""
        tpl = self._raw["tag_template"]
        all_tickers = self.instruments() + self.vix_tickers()
        return [tpl.format(ticker=t) for t in all_tickers]

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
        """Return {citi_tag: ticker} reverse mapping (indices + VIX family)."""
        tpl = self._raw["tag_template"]
        all_entries = self._all_entries() + self._vix_entries()
        return {tpl.format(ticker=e["ticker"]): e["ticker"]
                for e in all_entries}

    # ── VIX family helpers ──────────────────────────────────────

    def _vix_entries(self) -> list[dict]:
        """VIX family entries from YAML."""
        return self._raw.get("vix_family", [])

    def vix_tickers(self) -> list[str]:
        """Return VIX family tickers."""
        return [e["ticker"] for e in self._vix_entries()]

    def vix_api_symbols(self) -> list[str]:
        """Citi tags for VIX family only."""
        tpl = self._raw["tag_template"]
        return [tpl.format(ticker=t) for t in self.vix_tickers()]

    # ── Dimension seeding ───────────────────────────────────────

    def index_create_entries(self) -> list[IndexCreate]:
        """Build IndexCreate objects for dim_index seeding (non-VIX indices only)."""
        entries: list[IndexCreate] = []
        tpl = self._raw["tag_template"]
        for region, region_entries in self._raw["indices"].items():
            for e in region_entries:
                if e["ticker"] in VIX_TICKERS:
                    continue
                entries.append(IndexCreate(
                    ticker=e["ticker"],
                    display_name=e["display_name"],
                    currency=e["currency"],
                    region=region,
                    citi_tag=tpl.format(ticker=e["ticker"]),
                    country_code=e["country_code"],
                ))
        return entries

    def market_calendars(self) -> list[tuple[str, str]]:
        """Unique ``(country_code, calendar_code)`` pairs for the index set.

        Used to anchor the daily ingest on the union of every exchange in the
        universe rather than on one market -- see
        ``market_calendar.last_business_day_any``.

        US resolves to ``NY`` (NYSE), NOT the project-wide ``GT`` default
        (SIFMA govt bond): equity closes follow the exchange calendar. This is
        the mismatch filed in
        ``docs/admin/development/per_script_calendar_intent.md``.

        Countries with no calendar configured in ``DEFAULT_CALENDAR_BY_COUNTRY``
        (FR, PL here) are skipped -- they cannot contribute a trading day, and
        their exchanges are already represented by EU/TE. Skipping is safe
        because the anchor is a MAX: an absent market can only ever have made
        the anchor earlier, never later.
        """
        pairs: set[tuple[str, str]] = set()
        for e in self._all_entries():
            cc = e["country_code"]
            cal = _EQUITY_CALENDAR_OVERRIDES.get(cc)
            if cal is None:
                try:
                    cal = default_calendar(cc)
                except KeyError:
                    _log.debug("no_calendar_for_country", country_code=cc,
                               ticker=e["ticker"])
                    continue
            pairs.add((cc, cal))
        return sorted(pairs)

    def target_currencies(self) -> list[str]:
        """Unique currencies across all indices (for holiday detection)."""
        return sorted(set(
            e["currency"] for e in self._all_entries() + self._vix_entries()
        ))


@lru_cache(maxsize=1)
def get_equity_universe(config_path: Path = _UNIVERSE_PATH) -> EquityUniverse:
    """Load and cache the equity universe from YAML."""
    with open(config_path) as f:
        raw = yaml.safe_load(f)
    return EquityUniverse(raw)
