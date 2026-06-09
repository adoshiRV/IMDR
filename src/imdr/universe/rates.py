"""Rates Universe — curves, maturities, tag generation, benchmark metadata."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

from imdr.domains.rates.schema import CITI_TO_QUOTE, MULTI_TENOR_QUOTES
from imdr.universe.base import BaseUniverse, ExpectedRange

_UNIVERSE_PATH = Path(__file__).parent / "rates.yml"


# ── Pydantic config models ───────────────────────────────────────

class CurrenciesConfig(BaseModel):
    g10: list[str] = []
    asia: list[str] = []
    other: list[str] = []


class RateLimitConfig(BaseModel):
    requests_per_second: int = 1
    max_concurrent: int = 1
    max_tags_per_request: int = 100
    max_daily_calls: int = 10000


class ProviderConfig(BaseModel):
    auth_type: str = "bearer"
    base_url: str = ""
    rate_limit: RateLimitConfig = RateLimitConfig()
    token_expiry_seconds: int = 3600


class InstrumentConfig(BaseModel):
    tag_prefix: str
    description: str = ""
    tag_format: str = ""
    quote_types: dict[str, str] = {}
    maturities: str = ""
    ccy_index_pairs: dict[str, str | list[str]] = {}
    currencies: list[str] = []


class CurveEntry(BaseModel):
    ccy: str
    curve: str
    type: str
    status: str
    maturities: str
    providers: dict[str, dict[str, str]]
    primary_from: str | None = None
    cessation: str | None = None
    supersedes: str | None = None
    superseded_by: str | None = None
    notes: str | None = None


class VolQualityConfig(BaseModel):
    ranges: dict[str, ExpectedRange] = {}
    pct_change_threshold: float = 50.0
    n_mad: float = 4.0
    trailing_months: int = 12
    min_obs: int = 30


class VolConfig(BaseModel):
    currencies: list[str] = []
    rfr_currencies: list[str] = []
    option_expiries: list[str] = []
    swap_tenors: list[str] = []
    atm_quote_types: list[str] = []
    atm_rfr_quote_types_default: list[str] = []
    atm_rfr_quote_types_usd: list[str] = []
    realized_windows: list[str] = []
    realized_freqs: list[str] = []
    vol_ratio_windows: list[str] = []
    tag_cache: str = "data/cache/rates/rates_vol_tree.json"
    quality: VolQualityConfig = VolQualityConfig()


class BenchRateEntry(BaseModel):
    cb_code: str
    display_name: str
    currency: str
    country_code: str
    citi_tag: str


class RatesUniverseConfig(BaseModel):
    currencies: CurrenciesConfig
    classifications: dict[str, str]
    target_groups: list[str]
    maturities: dict[str, list[str]]
    instruments: dict[str, InstrumentConfig]
    curves: list[CurveEntry]
    providers: dict[str, ProviderConfig]
    expected_ranges: dict[str, ExpectedRange] = {}
    multi_tenor_combos: dict[str, list[list[str]]] = {}
    bench_rates: list[BenchRateEntry] = []
    vol: VolConfig = VolConfig()


# ── Universe class ───────────────────────────────────────────────

class RatesUniverse(BaseUniverse):
    """Rates instrument universe — curves, maturities, tag generation, benchmark metadata."""

    def __init__(self, config: RatesUniverseConfig) -> None:
        self._config = config
        # Build prefix → curve lookup for fast resolution
        self._prefix_to_curve: dict[str, CurveEntry] = {}
        for c in config.curves:
            citi = c.providers.get("citi", {})
            prefix = citi.get("prefix")
            if prefix:
                self._prefix_to_curve[prefix] = c

    # ── BaseUniverse ABC ─────────────────────────────────────────

    def instruments(self) -> list[str]:
        """All curve identifiers as 'CCY.CURVE' strings."""
        return [f"{c.ccy}.{c.curve}" for c in self._config.curves]

    def api_symbols(self) -> list[str]:
        """All Citi tag prefixes for active curves."""
        return [
            c.providers["citi"]["prefix"]
            for c in self._config.curves
            if "citi" in c.providers
        ]

    # ── Expected ranges ─────────────────────────────────────────

    @property
    def expected_ranges(self) -> dict[str, ExpectedRange]:
        return self._config.expected_ranges

    def expected_range_for(self, quote: str) -> ExpectedRange | None:
        """Get hard bounds for a quote type, or None if not configured."""
        return self._config.expected_ranges.get(quote)

    # ── Curve lookups ────────────────────────────────────────────

    def all_curves(self) -> list[CurveEntry]:
        return self._config.curves

    def get_curve(self, ccy: str, curve: str) -> CurveEntry:
        for c in self._config.curves:
            if c.ccy == ccy.upper() and c.curve == curve.upper():
                return c
        raise KeyError(f"Curve not found: {ccy}/{curve}")

    def curves_for_ccy(self, ccy: str) -> list[CurveEntry]:
        return [c for c in self._config.curves if c.ccy == ccy.upper()]

    # ── Maturity lookups ─────────────────────────────────────────

    def maturities(self, key: str) -> list[str]:
        """Get maturity list by key ('ois' or 'swap_libor')."""
        mats = self._config.maturities.get(key)
        if mats is None:
            raise KeyError(f"Unknown maturity key: {key}")
        return mats

    def maturities_for_curve(self, ccy: str, curve: str) -> list[str]:
        c = self.get_curve(ccy, curve)
        return self.maturities(c.maturities)

    # ── Currency lookups ─────────────────────────────────────────

    def target_currencies(self) -> list[str]:
        """Currencies in target groups (g10 + asia by default)."""
        groups = self._config.target_groups
        ccys: list[str] = []
        seen: set[str] = set()
        for group in groups:
            for ccy in getattr(self._config.currencies, group, []):
                if ccy not in seen:
                    seen.add(ccy)
                    ccys.append(ccy)
        return ccys

    def classification_for(self, ccy: str) -> str:
        cls = self._config.classifications.get(ccy.upper())
        if cls is None:
            raise KeyError(f"Currency '{ccy}' not in classifications")
        return cls

    # ── Benchmark helpers ────────────────────────────────────────

    def primary_curve(self, ccy: str) -> str | None:
        """Return the primary (current benchmark) curve name for a currency."""
        for c in self._config.curves:
            if c.ccy == ccy.upper() and c.primary_from and c.status == "active":
                return c.curve
        # Fallback: first active RFR curve
        for c in self._config.curves:
            if c.ccy == ccy.upper() and c.type == "rfr" and c.status == "active":
                return c.curve
        return None

    # ── Provider / prefix lookups ────────────────────────────────

    def citi_prefix(self, ccy: str, curve: str) -> str:
        c = self.get_curve(ccy, curve)
        return c.providers["citi"]["prefix"]

    def resolve_prefix(self, prefix: str) -> tuple[str, str] | None:
        """Map a Citi tag prefix to (ccy, curve), or None if not found."""
        entry = self._prefix_to_curve.get(prefix)
        if entry:
            return entry.ccy, entry.curve
        return None

    # ── Tag generation ───────────────────────────────────────────

    def build_tags(
        self,
        ccy: str,
        curve: str,
        quote: str = "PAR",
        tenors: list[str] | None = None,
    ) -> list[str]:
        """Build Citi tags for a curve + quote type.

        For single-tenor quotes (PAR, SWAP_SPREAD, ROLL_CARRY) uses the
        maturity list.  For multi-tenor quotes (FWD, CURVES, BFLY) uses
        the ``multi_tenor_combos`` config to build multi-part tags, e.g.
        ``RATES.OIS.USD_SOFR.FWD.5Y.5Y``.

        Returns ``[]`` when the curve's instrument doesn't declare the
        requested ``quote`` — lets the extractor loop over (curve, quote)
        without producing nonsense tags for mismatched combos.
        """
        prefix = self.citi_prefix(ccy, curve)
        instr = self._instrument_for_curve(ccy, curve)

        # Skip quotes not declared for this instrument. Lets the extractor
        # loop over (curve x quote) without producing nonsense tags for
        # mismatched combos (e.g. PAR on a basis_swaps curve).
        if instr is not None and instr.quote_types:
            if quote not in instr.quote_types.values():
                return []

        # Multi-tenor quote types need combo-based tag generation
        internal_qt = CITI_TO_QUOTE.get(quote, quote.lower())
        if internal_qt in MULTI_TENOR_QUOTES and tenors is None:
            combos = self._config.multi_tenor_combos.get(internal_qt, [])
            return [f"{prefix}.{quote}.{'.'.join(legs)}" for legs in combos]

        # Single-tenor
        if tenors is None:
            tenors = self.maturities_for_curve(ccy, curve)

        # Some instruments (basis_swaps) put the quote AFTER the tenor.
        if instr is not None and instr.tag_format == "tenor_first":
            return [f"{prefix}.{t}.{quote}" for t in tenors]
        return [f"{prefix}.{quote}.{t}" for t in tenors]

    def _instrument_for_curve(self, ccy: str, curve: str) -> "InstrumentConfig | None":
        """Look up the instrument config a curve belongs to (via providers.citi.instrument)."""
        c = self.get_curve(ccy, curve)
        instr_key = c.providers.get("citi", {}).get("instrument")
        if not instr_key:
            return None
        return self._config.instruments.get(instr_key)

    def multi_tenor_combos_for(self, quote: str) -> list[list[str]]:
        """Return the configured multi-tenor combos for a quote type (e.g. 'fwd')."""
        return self._config.multi_tenor_combos.get(quote.lower(), [])

    def build_all_tags(
        self,
        quote: str = "PAR",
        target_only: bool = True,
    ) -> list[str]:
        """Build tags for all curves (optionally filtered to target currencies)."""
        target_ccys = set(self.target_currencies()) if target_only else None
        tags: list[str] = []
        for c in self._config.curves:
            if target_ccys and c.ccy not in target_ccys:
                continue
            tags.extend(self.build_tags(c.ccy, c.curve, quote))
        return tags

    # ── OIS ccy/index pair helpers ───────────────────────────────

    def ccy_index_pairs(self, target_only: bool = True) -> list[tuple[str, str]]:
        """Return all OIS (ccy, index) pairs from instrument config."""
        ois_cfg = self._config.instruments.get("ois")
        if not ois_cfg:
            return []
        target_ccys = set(self.target_currencies()) if target_only else None
        pairs: list[tuple[str, str]] = []
        for ccy, indexes in ois_cfg.ccy_index_pairs.items():
            if target_ccys and ccy not in target_ccys:
                continue
            if isinstance(indexes, str):
                pairs.append((ccy, indexes))
            else:
                for idx in indexes:
                    pairs.append((ccy, idx))
        return pairs

    def swap_currencies(self, target_only: bool = True) -> list[str]:
        """Return all SWAP_LIBOR currencies from instrument config."""
        swap_cfg = self._config.instruments.get("swap_libor")
        if not swap_cfg:
            return []
        if target_only:
            target = set(self.target_currencies())
            return [c for c in swap_cfg.currencies if c in target]
        return swap_cfg.currencies

    # ── Swaption Vol helpers ──────────────────────────────────────

    @property
    def vol(self) -> VolConfig:
        return self._config.vol

    def vol_currencies(self) -> list[str]:
        return self._config.vol.currencies

    def _load_vol_tag_cache(self) -> dict[str, list[str]]:
        """Load the authoritative tag listing from the exploration cache.

        Returns {ccy: [tag, tag, ...]} mapping.
        """
        if not hasattr(self, "_vol_tag_cache"):
            cache_path = Path(self._config.vol.tag_cache)
            if cache_path.exists():
                raw = json.loads(cache_path.read_text(encoding="utf-8"))
                self._vol_tag_cache: dict[str, list[str]] = raw.get("_tag_listings", {})
            else:
                self._vol_tag_cache = {}
        return self._vol_tag_cache

    def build_vol_tags(self, ccy: str) -> list[str]:
        """Return exact Citi tags for a currency from the exploration cache.

        The cache (data/cache/rates/rates_vol_tree.json) is the source of truth.
        The API has per-data_type grid variations that a cartesian product cannot
        model accurately (ATM.NORMAL uses ANNUAL/DAILY, RFR types have extra
        expiries, some ccys have non-standard swap grids).
        """
        cache = self._load_vol_tag_cache()
        return cache.get(ccy, [])

    def vol_surface_create_entries(self) -> list[dict[str, Any]]:
        """Derive dimension-seed entries from the actual tag cache.

        Parses every cached tag to extract unique surface identifiers.
        Returns list of dicts matching RatesVolSurfaceCreate fields.
        """
        from imdr.domains.rates.vol_translate import citi_rates_vol_tag_to_internal

        rfr_set = set(self._config.vol.rfr_currencies)
        seen: set[tuple[str, str, str, str, str]] = set()
        entries: list[dict[str, Any]] = []

        for ccy in self._config.vol.currencies:
            for tag in self.build_vol_tags(ccy):
                parsed = citi_rates_vol_tag_to_internal(tag)
                if parsed is None:
                    continue
                key = (parsed["ccy"], parsed["data_type"], parsed["quote_type"],
                       parsed["vol_window"], parsed["freq"])
                if key in seen:
                    continue
                seen.add(key)
                entries.append({
                    "ccy": parsed["ccy"],
                    "data_type": parsed["data_type"],
                    "quote_type": parsed["quote_type"],
                    "vol_window": parsed["vol_window"],
                    "freq": parsed["freq"],
                    "is_rfr": parsed["ccy"] in rfr_set and "_RFR" in parsed["data_type"],
                })

        return entries

    def vol_quality_ranges(self) -> dict[tuple[str, str], tuple[float, float]]:
        """Parse vol quality ranges into a flat dict for CompositeRangeCheck.

        Returns {(data_type, quote_type): (min, max)} mapping.
        For REALIZED/VOL_RATIO, key is (data_type, '').
        """
        result: dict[tuple[str, str], tuple[float, float]] = {}
        for key, rng in self._config.vol.quality.ranges.items():
            parts = key.split(".", 1)
            dt = parts[0]
            qt = parts[1] if len(parts) > 1 else ""
            result[(dt, qt)] = (rng.min, rng.max)
        return result

    # ── Bench Rates helpers ──────────────────────────────────────

    def bench_rates_tags(self) -> list[str]:
        """Return all Citi tags for central bank policy rates."""
        return [e.citi_tag for e in self._config.bench_rates]

    def bench_rates_entries(self) -> list[BenchRateEntry]:
        """Return all bench rate entries from config."""
        return self._config.bench_rates

    def bench_rates_tag_to_cb_code(self) -> dict[str, str]:
        """Return {citi_tag: cb_code} mapping for tag resolution."""
        return {e.citi_tag: e.cb_code for e in self._config.bench_rates}


@lru_cache(maxsize=1)
def get_rates_universe(config_path: Path = _UNIVERSE_PATH) -> RatesUniverse:
    """Load and cache the Rates universe from YAML."""
    with open(config_path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    config = RatesUniverseConfig.model_validate(raw)
    return RatesUniverse(config)
