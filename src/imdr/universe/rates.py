"""Rates Universe — curves, maturities, tag generation, benchmark metadata."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

from imdr.universe.base import BaseUniverse

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


class RatesUniverseConfig(BaseModel):
    currencies: CurrenciesConfig
    classifications: dict[str, str]
    target_groups: list[str]
    maturities: dict[str, list[str]]
    instruments: dict[str, InstrumentConfig]
    curves: list[CurveEntry]
    providers: dict[str, ProviderConfig]


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

        Absorbs logic from RATES_data ois.py / swaps.py tag generators.
        """
        prefix = self.citi_prefix(ccy, curve)
        if tenors is None:
            tenors = self.maturities_for_curve(ccy, curve)
        return [f"{prefix}.{quote}.{t}" for t in tenors]

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


@lru_cache(maxsize=1)
def get_rates_universe(config_path: Path = _UNIVERSE_PATH) -> RatesUniverse:
    """Load and cache the Rates universe from YAML."""
    with open(config_path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    config = RatesUniverseConfig.model_validate(raw)
    return RatesUniverse(config)
