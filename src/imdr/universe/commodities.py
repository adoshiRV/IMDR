"""Commodities Universe — spot, EIA, and implied vol config."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from imdr.universe.base import BaseUniverse, ExpectedRange

if TYPE_CHECKING:
    from imdr.schemas.commodities import CommodityCreate, EIASeriesCreate

_UNIVERSE_PATH = Path(__file__).parent / "commodities.yml"

# Oil products use a different tag format (no .USD. segment)
_OIL_PRODUCTS = frozenset({"CR_IPE_BRENT", "CR_NYM_CL"})


class CommoditiesUniverse(BaseUniverse):
    """Commodity instrument universe for SPOT, EIA, and IMPLIED_VOL products."""

    def __init__(self, raw: dict) -> None:
        self._raw = raw

    # ── BaseUniverse interface ───────────────────────────────────

    def instruments(self) -> list[str]:
        """All commodity symbols."""
        return [c["symbol"] for c in self._raw["commodities"]]

    def api_symbols(self) -> list[str]:
        """All Citi Velocity tags across all three sub-products."""
        return list(self.spot_tags()) + self.build_eia_tags() + self.build_all_vol_tags()

    # ── Shared dimension ─────────────────────────────────────────

    def commodity_entries(self) -> list[dict]:
        """Raw commodity entries from YAML."""
        return self._raw["commodities"]

    def commodity_create_entries(self) -> list[CommodityCreate]:
        """Build CommodityCreate entries for dim seeding."""
        from imdr.schemas.commodities import CommodityCreate

        return [
            CommodityCreate(
                symbol=c["symbol"],
                display_name=c["display_name"],
                commodity_class=c["commodity_class"],
                spot_tag=c.get("spot_tag"),
            )
            for c in self._raw["commodities"]
        ]

    # ── SPOT ─────────────────────────────────────────────────────

    def spot_tags(self) -> dict[str, str]:
        """Return {tag: symbol} map for spot products."""
        return dict(self._raw["spot"]["tags"])

    def spot_commodity_symbols(self) -> list[str]:
        """Commodity symbols that have spot tags."""
        return list(self.spot_tags().values())

    # ── EIA ──────────────────────────────────────────────────────

    def eia_series(self) -> list[dict]:
        """Return list of {name, regions, units} dicts."""
        return self._raw["eia"]["series"]

    def build_eia_tags(self) -> list[str]:
        """Build all Citi EIA tags."""
        tpl = self._raw["eia"]["tag_template"]
        tags: list[str] = []
        for s in self.eia_series():
            for region in s["regions"]:
                tags.append(tpl.format(series=s["name"], region=region))
        return tags

    def eia_series_create_entries(self) -> list[EIASeriesCreate]:
        """Build EIASeriesCreate entries for dim seeding."""
        from imdr.schemas.commodities import EIASeriesCreate

        entries: list[EIASeriesCreate] = []
        for s in self.eia_series():
            for region in s["regions"]:
                entries.append(EIASeriesCreate(
                    series_name=s["name"],
                    region=region,
                    series_units=s.get("units", ""),
                ))
        return entries

    # ── IMPLIED_VOL ──────────────────────────────────────────────

    def vol_config(self) -> dict:
        """Raw vol config dict."""
        return self._raw["vol"]

    def vol_products(self) -> list[str]:
        """All products with vol surfaces."""
        cfg = self.vol_config()
        return cfg["precious_metals"]["products"] + cfg["oil"]["products"]

    def vol_precious_metals_products(self) -> list[str]:
        return self.vol_config()["precious_metals"]["products"]

    def vol_oil_products(self) -> list[str]:
        return self.vol_config()["oil"]["products"]

    def vol_strikes_for_product(self, product: str) -> list[str]:
        """Return valid strikes for a given product."""
        if product in _OIL_PRODUCTS:
            return ["ATM"]
        cfg = self.vol_config()["precious_metals"]["strikes"]
        strikes = list(cfg["standard"]) + list(cfg["exotic"])
        if product == "XPT":
            strikes += list(cfg["xpt_only"])
        return strikes

    def vol_tenors_for_product(self, product: str) -> list[str]:
        """Return valid tenors for a given product."""
        if product in _OIL_PRODUCTS:
            n = self.vol_config()["oil"]["contracts"]
            return [f"NEARBY{i:02d}_M" for i in range(1, n + 1)]
        return self.vol_config()["precious_metals"]["tenors"][product]

    def build_vol_tags(self, product: str) -> list[str]:
        """Build all Citi vol tags for a single product."""
        tags: list[str] = []
        if product in _OIL_PRODUCTS:
            tpl = self.vol_config()["oil"]["tag_template"]
            n = self.vol_config()["oil"]["contracts"]
            for i in range(1, n + 1):
                tags.append(tpl.format(product=product, nn=f"{i:02d}"))
        else:
            tpl = self.vol_config()["precious_metals"]["tag_template"]
            for strike in self.vol_strikes_for_product(product):
                for tenor in self.vol_tenors_for_product(product):
                    tags.append(tpl.format(product=product, strike=strike, tenor=tenor))
        return tags

    def build_all_vol_tags(self) -> list[str]:
        """Build all Citi vol tags for all products."""
        tags: list[str] = []
        for product in self.vol_products():
            tags.extend(self.build_vol_tags(product))
        return tags

    # ── Quality config ───────────────────────────────────────────

    def vol_quality_ranges(self) -> dict[str, tuple[float, float]]:
        """Return {strike: (min, max)} from quality config."""
        raw = self.vol_config().get("quality", {}).get("ranges", {})
        return {strike: (bounds["min"], bounds["max"]) for strike, bounds in raw.items()}

    def vol_range_for_strike(self, strike: str) -> ExpectedRange | None:
        """Get hard bounds for a strike, or None if not configured."""
        raw = self.vol_config().get("quality", {}).get("ranges", {})
        bounds = raw.get(strike)
        if bounds is None:
            return None
        return ExpectedRange(min=bounds["min"], max=bounds["max"])


@lru_cache(maxsize=1)
def get_commodities_universe(config_path: Path = _UNIVERSE_PATH) -> CommoditiesUniverse:
    """Load and cache the commodities universe from YAML."""
    with open(config_path) as f:
        raw = yaml.safe_load(f)
    return CommoditiesUniverse(raw)
