"""FX Universe — currencies, pair conventions, provider series, market hours, vol config."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

import yaml
from pydantic import BaseModel

from imdr.universe.base import BaseUniverse, ExpectedRange

if TYPE_CHECKING:
    from imdr.schemas.fx_vol import FXCurrencyPairCreate

_UNIVERSE_PATH = Path(__file__).parent / "fx.yml"


@dataclass(frozen=True)
class VolQualityParsed:
    """Parsed vol quality config — per-(strike, vol_type) hard ranges.

    Statistical params (n_mad, trailing_months, pct_threshold) are in
    pipelines.yml under fx.vol.cleaning — single source of truth.
    """

    ranges: dict[tuple[str, str], tuple[float, float]] = field(default_factory=dict)
    abs_change_thresholds: dict[str, float] = field(default_factory=dict)
    abs_change_vol_types: dict[str, float] = field(default_factory=dict)
    pct_thresholds: dict[str, dict[str, float]] = field(default_factory=dict)


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


class CurrenciesConfig(BaseModel):
    g10: list[str] = []
    em_ndf: list[str] = []
    em_deliverable: list[str] = []


class VolQualityConfig(BaseModel):
    """Per-(strike, vol_type) hard ranges from fx.yml.

    Statistical params (n_mad, trailing_months, pct_threshold) are in
    pipelines.yml under fx.vol.cleaning.
    """

    ranges: dict[str, dict[str, dict[str, float]]] = {}
    abs_change_thresholds: dict[str, float] = {}
    abs_change_vol_types: dict[str, float] = {}
    pct_thresholds: dict[str, dict[str, float]] = {}


class VolConfig(BaseModel):
    pairs: list[list[str]]
    strikes: list[str]
    tenors: list[str]
    vol_types: dict[str, list[str]]  # strike→types mapping, _default key
    tag_template: str
    quality: VolQualityConfig = VolQualityConfig()


class FXRateConfig(BaseModel):
    """Config block for the Citi Velocity FX rate pipeline.

    Spot + forward outrights + forward points over a curated tenor grid.
    See docs/fx/fx_rate_schema.md for per-column semantics.
    """

    pairs: list[list[str]]                       # [[base, quote], ...] in Citi ordering
    spot_only_pairs: list[list[str]] = []        # excluded from forward fetch
    tenors: list[str]                            # SPOT first, then forward tenors
    spot_tag_template: str
    outright_tag_template: str
    points_tag_template: str
    expected_ranges: dict[str, ExpectedRange] = {}


class FXUniverseConfig(BaseModel):
    currencies: CurrenciesConfig
    classifications: dict[str, str]
    pair_priority: list[str]
    market_hours: MarketHoursConfig
    series: dict[str, SeriesConfig]
    providers: dict[str, ProviderConfig]
    expected_ranges: dict[str, ExpectedRange] = {}
    vol: VolConfig | None = None
    fx_rate: FXRateConfig | None = None


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

    def currency_from_symbol(self, symbol: str) -> str:
        """Extract the non-USD currency from a compact symbol.

        Examples: EURUSD → EUR, USDCNH → CNH, USDJPY → JPY.
        """
        compact = symbol.replace(".", "").upper()
        first, second = compact[:3], compact[3:]
        known = set(self.all_currencies)
        if first != "USD" and first in known:
            return first
        if second != "USD" and second in known:
            return second
        msg = f"Cannot resolve non-USD currency from symbol '{symbol}'"
        raise ValueError(msg)

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

    @property
    def expected_ranges(self) -> dict[str, ExpectedRange]:
        return self._config.expected_ranges

    def expected_range_for(self, symbol: str) -> ExpectedRange | None:
        """Get hard bounds for a symbol, or None if not configured."""
        return self._config.expected_ranges.get(symbol)

    # ── Vol surface methods ────────────────────────────────────

    def _vol_config(self) -> VolConfig:
        if self._config.vol is None:
            raise RuntimeError("Vol config not present in fx.yml")
        return self._config.vol

    def vol_pairs(self) -> list[tuple[str, str]]:
        """Return list of (ccy1, ccy2) tuples for vol surface ingestion."""
        return [tuple(p) for p in self._vol_config().pairs]

    def vol_strikes(self) -> list[str]:
        return self._vol_config().strikes

    def vol_tenors(self) -> list[str]:
        return self._vol_config().tenors

    def vol_types_for_strike(self, strike: str) -> list[str]:
        """Return vol_types for a given strike (ATM has 3, others have 1)."""
        vt = self._vol_config().vol_types
        return vt.get(strike, vt.get("_default", ["IMPLIED"]))

    def build_vol_tags(self, ccy1: str, ccy2: str) -> list[str]:
        """Build all Citi vol tags for a single currency pair."""
        cfg = self._vol_config()
        tags: list[str] = []
        for strike in cfg.strikes:
            for tenor in cfg.tenors:
                for vol_type in self.vol_types_for_strike(strike):
                    tag = cfg.tag_template.format(
                        ccy1=ccy1, ccy2=ccy2,
                        strike=strike, tenor=tenor, vol_type=vol_type,
                    )
                    tags.append(tag)
        return tags

    def build_all_vol_tags(self) -> list[str]:
        """Build all Citi vol tags for all pairs."""
        tags: list[str] = []
        for ccy1, ccy2 in self.vol_pairs():
            tags.extend(self.build_vol_tags(ccy1, ccy2))
        return tags

    def vol_quality_config(self) -> VolQualityParsed:
        """Parse vol quality config into a flat structure for quality checks.

        Flattens nested YAML: {ATM: {IMPLIED: {min, max}}} →
        {("ATM", "IMPLIED"): (0.5, 80.0)}
        """
        cfg = self._vol_config().quality
        ranges: dict[tuple[str, str], tuple[float, float]] = {}
        for strike, vol_types in cfg.ranges.items():
            for vol_type, bounds in vol_types.items():
                ranges[(strike, vol_type)] = (bounds["min"], bounds["max"])
        return VolQualityParsed(
            ranges=ranges,
            abs_change_thresholds=dict(cfg.abs_change_thresholds),
            abs_change_vol_types=dict(cfg.abs_change_vol_types),
            pct_thresholds={k: dict(v) for k, v in cfg.pct_thresholds.items()},
        )

    def vol_pair_create_entries(self) -> list[FXCurrencyPairCreate]:
        """Build FXCurrencyPairCreate entries for dim seeding."""
        from imdr.schemas.fx_vol import FXCurrencyPairCreate

        entries: list[FXCurrencyPairCreate] = []
        for ccy1, ccy2 in self.vol_pairs():
            # Determine ccy_class from the non-USD currency
            non_usd = ccy1 if ccy1 != "USD" else ccy2
            ccy_class = self._config.classifications.get(non_usd, "g10")
            entries.append(FXCurrencyPairCreate(
                base_ccy=ccy1, quote_ccy=ccy2, ccy_class=ccy_class,
            ))
        return entries

    # ── FX rate (spot + forward) methods ───────────────────────

    def _fx_rate_config(self) -> FXRateConfig:
        if self._config.fx_rate is None:
            raise RuntimeError("fx_rate config not present in fx.yml")
        return self._config.fx_rate

    def fx_rate_pairs(self) -> list[tuple[str, str]]:
        """All (ccy1, ccy2) pairs in Citi ordering."""
        return [tuple(p) for p in self._fx_rate_config().pairs]

    def fx_rate_tenors(self) -> list[str]:
        return list(self._fx_rate_config().tenors)

    def fx_rate_forward_tenors(self) -> list[str]:
        """Tenors excluding SPOT — used for forward outright + forward point fetches."""
        return [t for t in self.fx_rate_tenors() if t != "SPOT"]

    def fx_rate_spot_only_pairs(self) -> set[tuple[str, str]]:
        return {tuple(p) for p in self._fx_rate_config().spot_only_pairs}

    def build_fx_rate_spot_tag(self, ccy1: str, ccy2: str) -> str:
        return self._fx_rate_config().spot_tag_template.format(ccy1=ccy1, ccy2=ccy2)

    def build_fx_rate_outright_tags(self, ccy1: str, ccy2: str) -> list[str]:
        tmpl = self._fx_rate_config().outright_tag_template
        return [tmpl.format(ccy1=ccy1, ccy2=ccy2, tenor=t) for t in self.fx_rate_forward_tenors()]

    def build_fx_rate_point_tags(self, ccy1: str, ccy2: str) -> list[str]:
        tmpl = self._fx_rate_config().points_tag_template
        return [tmpl.format(ccy1=ccy1, ccy2=ccy2, tenor=t) for t in self.fx_rate_forward_tenors()]

    def build_all_fx_rate_tags(self) -> list[str]:
        """All Citi tags needed for an fx_rate daily ingest."""
        tags: list[str] = []
        spot_only = self.fx_rate_spot_only_pairs()
        for ccy1, ccy2 in self.fx_rate_pairs():
            tags.append(self.build_fx_rate_spot_tag(ccy1, ccy2))
            if (ccy1, ccy2) in spot_only:
                continue
            tags.extend(self.build_fx_rate_outright_tags(ccy1, ccy2))
            tags.extend(self.build_fx_rate_point_tags(ccy1, ccy2))
        return tags

    def fx_rate_pair_code(self, ccy1: str, ccy2: str) -> str:
        """Compact pair code used as a key in expected_ranges (e.g. EURUSD)."""
        return f"{ccy1}{ccy2}".upper()

    def fx_rate_expected_range(self, ccy1: str, ccy2: str) -> ExpectedRange | None:
        return self._fx_rate_config().expected_ranges.get(self.fx_rate_pair_code(ccy1, ccy2))

    def fx_rate_expected_ranges(self) -> dict[str, ExpectedRange]:
        """All per-pair expected ranges, keyed by compact pair_code."""
        return dict(self._fx_rate_config().expected_ranges)

    def fx_rate_pair_create_entries(self) -> list[FXCurrencyPairCreate]:
        """Build FXCurrencyPairCreate entries for dim seeding (fx_rate universe)."""
        from imdr.schemas.fx_vol import FXCurrencyPairCreate

        entries: list[FXCurrencyPairCreate] = []
        for ccy1, ccy2 in self.fx_rate_pairs():
            non_usd = ccy1 if ccy1 != "USD" else ccy2
            ccy_class = self._config.classifications.get(non_usd, "g10")
            entries.append(FXCurrencyPairCreate(
                base_ccy=ccy1, quote_ccy=ccy2, ccy_class=ccy_class,
            ))
        return entries

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
