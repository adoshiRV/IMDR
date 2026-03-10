"""
Tag discovery via Citi Velocity Tag Listing & Tag Browsing APIs.

Strategy:
  - taglisting: fetch PAR tags per pair/ccy, cache to data/cache/rates/rates_tags.json
  - tagbrowsing: explore tree structure, discover quote types / currencies
  - All discovery functions parse cached tags locally (0 API calls after initial fetch)

Ported from RATES_data/src/taglisting.py — uses IMDR infrastructure.
"""
from __future__ import annotations

import json
import structlog
from collections import defaultdict
from pathlib import Path
from typing import Any

from imdr.connectors.citi_velocity import CitiVelocityClient
from imdr.universe.rates import RatesUniverse, get_rates_universe

_CACHE_DIR = Path("data/cache/rates")
_CACHE_PATH = _CACHE_DIR / "rates_tags.json"

_log = structlog.get_logger("RatesTagDiscovery")


class RatesTagDiscovery:
    """Tag discovery and catalog validation via Citi Velocity taglisting/tagbrowsing APIs."""

    def __init__(
        self,
        client: CitiVelocityClient,
        universe: RatesUniverse | None = None,
        cache_path: Path = _CACHE_PATH,
    ) -> None:
        self._client = client
        self._universe = universe or get_rates_universe()
        self._cache_path = cache_path

    # ── Tag Listing — fetch + cache ──────────────────────────────

    def fetch_all_par_tags(self, force: bool = False) -> list[str]:
        """Fetch PAR tags for all OIS pairs and SWAP_LIBOR currencies.

        Caches to data/cache/rates/rates_tags.json. Subsequent calls read from cache.
        """
        if not force and self._cache_path.exists():
            with open(self._cache_path, "r") as f:
                cached = json.load(f)
            _log.info("tags_cache_loaded", count=len(cached["tags"]))
            return cached["tags"]

        all_tags: list[str] = []
        api_calls = 0

        # OIS: query PAR per ccy/index pair
        ois_pairs = self._universe.ccy_index_pairs(target_only=False)
        _log.info("ois_tag_fetch_start", n_pairs=len(ois_pairs))
        for ccy, idx in ois_pairs:
            prefix = f"RATES.OIS.{ccy}_{idx}.PAR"
            resp = self._client.fetch_taglisting(prefix=prefix)
            api_calls += 1
            if resp.get("status") != "OK":
                _log.warning("ois_tag_fetch_warn", prefix=prefix, msg=resp.get("message", "error"))
                continue
            tags = resp.get("tags", [])
            _log.info("ois_tags_fetched", ccy=ccy, index=idx, count=len(tags))
            all_tags.extend(tags)

        # SWAP_LIBOR: query PAR per currency
        swap_ccys = self._universe.swap_currencies(target_only=False)
        _log.info("swap_tag_fetch_start", n_ccys=len(swap_ccys))
        for ccy in swap_ccys:
            prefix = f"RATES.SWAP_LIBOR.{ccy}.PAR"
            resp = self._client.fetch_taglisting(prefix=prefix)
            api_calls += 1
            if resp.get("status") != "OK":
                _log.warning("swap_tag_fetch_warn", prefix=prefix, msg=resp.get("message", "error"))
                continue
            tags = resp.get("tags", [])
            _log.info("swap_tags_fetched", ccy=ccy, count=len(tags))
            all_tags.extend(tags)

        _log.info("tags_fetched_total", count=len(all_tags), api_calls=api_calls)

        # Cache
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._cache_path, "w") as f:
            json.dump({"tags": all_tags, "count": len(all_tags), "api_calls": api_calls}, f, indent=2)

        return all_tags

    # ── Discovery from cached tags ───────────────────────────────

    def discover_ois(self, tags: list[str] | None = None) -> dict[str, Any]:
        """Parse cached tags → OIS pairs, quote types, maturities."""
        tags = tags or self.fetch_all_par_tags()
        ois_tags = [t for t in tags if t.startswith("RATES.OIS.")]

        seen_pairs: set[str] = set()
        pairs: list[dict[str, str]] = []
        qt_mats: dict[str, set[str]] = defaultdict(set)

        for tag in ois_tags:
            parts = tag.split(".")
            if len(parts) != 5:
                continue
            try:
                ccy, idx = parts[2].split("_", 1)
            except ValueError:
                continue
            key = f"{ccy}_{idx}"
            if key not in seen_pairs:
                seen_pairs.add(key)
                pairs.append({"ccy": ccy, "index": idx})
            qt_mats[parts[3]].add(parts[4])

        return {
            "pairs": pairs,
            "quote_types": {qt: sorted(mats) for qt, mats in sorted(qt_mats.items())},
        }

    def discover_swap_libor(self, tags: list[str] | None = None) -> dict[str, Any]:
        """Parse cached tags → SWAP_LIBOR currencies, quote types, maturities."""
        tags = tags or self.fetch_all_par_tags()
        swap_tags = [t for t in tags if t.startswith("RATES.SWAP_LIBOR.")]

        ccys: set[str] = set()
        qt_mats: dict[str, set[str]] = defaultdict(set)

        for tag in swap_tags:
            parts = tag.split(".")
            if len(parts) != 5:
                continue
            ccys.add(parts[2])
            qt_mats[parts[3]].add(parts[4])

        return {
            "currencies": sorted(ccys),
            "quote_types": {qt: sorted(mats) for qt, mats in sorted(qt_mats.items())},
        }

    def discover_all(self, force: bool = False) -> dict[str, Any]:
        """Fetch PAR tags (if not cached), then parse everything locally."""
        tags = self.fetch_all_par_tags(force=force)
        return {
            "total_tags": len(tags),
            "ois": self.discover_ois(tags),
            "swap_libor": self.discover_swap_libor(tags),
        }

    # ── Tag Browsing ─────────────────────────────────────────────

    def browse(self, prefix: str = "") -> dict[str, Any]:
        """Browse the tag tree hierarchy one level at a time."""
        resp = self._client.fetch_tagbrowsing(prefix)
        if resp.get("status") != "OK":
            raise RuntimeError(f"Tagbrowsing failed: {resp}")
        return resp

    # ── Validation ───────────────────────────────────────────────

    def validate_catalog(self) -> dict[str, Any]:
        """Cross-reference universe config against discovered tags.

        Returns {matched, unmatched, uncataloged} counts.
        """
        tags = self.fetch_all_par_tags()

        # Build set of prefixes from discovered tags
        discovered_prefixes: set[str] = set()
        for tag in tags:
            parts = tag.split(".")
            if len(parts) >= 4:
                # prefix = everything before quote type
                discovered_prefixes.add(".".join(parts[:3]))

        # Build set of catalog prefixes
        catalog_prefixes: set[str] = set()
        for c in self._universe.all_curves():
            citi = c.providers.get("citi", {})
            prefix = citi.get("prefix")
            if prefix:
                catalog_prefixes.add(prefix)

        matched = catalog_prefixes & discovered_prefixes
        unmatched = catalog_prefixes - discovered_prefixes
        uncataloged = discovered_prefixes - catalog_prefixes

        result = {
            "matched": len(matched),
            "unmatched": len(unmatched),
            "uncataloged": len(uncataloged),
            "unmatched_prefixes": sorted(unmatched),
            "uncataloged_prefixes": sorted(uncataloged),
        }
        _log.info("catalog_validation", **result)
        return result
