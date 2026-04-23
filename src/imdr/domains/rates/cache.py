"""JSON file cache for empty (ccy, curve, quote) combos.

Tracks which API calls return 0 rows so they can be skipped on future runs.
Status-aware: active/reformed curves get a short stale window (2 days) so
transient holidays never lock out a curve for long.  Ceased curves get a
longer window (30 days) since they are genuinely dead.

Primary quotes (``par``, ``ssw``) for active curves are NEVER cached as
empty — these are the most important data points and a transient empty
response should never prevent future fetches.

History: The original 30-day flat stale window caused a 2-week silent data
outage for 20/39 rate curves after Easter 2026 (see incident report
``docs/admin/incidents/2026-04-14_rates_cache_silent_drop.md``).
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import structlog

_log = structlog.get_logger("CurveQuoteCache")

_CACHE_FILENAME = "empty_combos.json"

# Primary quote types — never cache as empty for active/reformed curves
_PROTECTED_QUOTES = frozenset({"par", "ssw"})

# Stale windows by curve status
_ACTIVE_STALE_DAYS = 2    # re-try after 2 days (survives any weekend/holiday)
_CEASED_STALE_DAYS = 30   # genuinely dead curves — re-try monthly


class CurveQuoteCache:
    """JSON-backed cache of (ccy, curve, quote) combos known to return 0 rows.

    The cache is status-aware:
    - **Active/reformed curves**: stale after 2 days, ``par``/``ssw`` never cached.
    - **Ceased curves**: stale after 30 days, all quotes cacheable.

    This prevents transient holiday blips from locking out live curves.
    """

    def __init__(self, cache_dir: str | Path, stale_days: int | None = None) -> None:
        self._path = Path(cache_dir) / "rates" / _CACHE_FILENAME
        # Legacy override — if caller passes explicit stale_days, use it for
        # backwards compat.  Otherwise use status-aware defaults.
        self._override_stale_days = stale_days
        # {f"{ccy}|{curve}|{quote}": "YYYY-MM-DD"}
        self._cache: dict[str, str] = {}
        self._dirty = False

    @staticmethod
    def _key(ccy: str, curve: str, quote: str) -> str:
        return f"{ccy}|{curve}|{quote}"

    def _stale_days_for(self, curve_status: str = "active") -> int:
        """Return stale window in days based on curve status."""
        if self._override_stale_days is not None:
            return self._override_stale_days
        if curve_status == "ceased":
            return _CEASED_STALE_DAYS
        return _ACTIVE_STALE_DAYS

    def load(self) -> None:
        """Read cache from JSON file if it exists."""
        if self._path.exists():
            with open(self._path) as f:
                self._cache = json.load(f)
        _log.info("cache_loaded", entries=len(self._cache), path=str(self._path))

    def should_skip(
        self, ccy: str, curve: str, quote: str, curve_status: str = "active"
    ) -> bool:
        """True if cached AND last_checked is within the stale window.

        Uses a short window (2 days) for active curves and a longer window
        (30 days) for ceased curves.
        """
        key = self._key(ccy, curve, quote)
        last_str = self._cache.get(key)
        if last_str is None:
            return False
        last_checked = date.fromisoformat(last_str)
        stale_days = self._stale_days_for(curve_status)
        should = (date.today() - last_checked) < timedelta(days=stale_days)
        if should:
            _log.warning(
                "cache_skip",
                ccy=ccy, curve=curve, quote=quote,
                cached_date=last_str, stale_days=stale_days,
            )
        return should

    def mark_empty(
        self, ccy: str, curve: str, quote: str, curve_status: str = "active"
    ) -> None:
        """Record combo as empty with today's date.

        Protected quotes (``par``, ``ssw``) for active/reformed curves are
        never cached — a transient empty response must not lock them out.
        """
        if curve_status != "ceased" and quote.lower() in _PROTECTED_QUOTES:
            _log.debug(
                "cache_skip_protected",
                ccy=ccy, curve=curve, quote=quote,
                reason="protected quote for active curve",
            )
            return
        self._cache[self._key(ccy, curve, quote)] = date.today().isoformat()
        self._dirty = True

    def mark_active(self, ccy: str, curve: str, quote: str) -> None:
        """Remove combo from cache — it now returns data."""
        key = self._key(ccy, curve, quote)
        if key in self._cache:
            del self._cache[key]
            self._dirty = True

    def clear_curve(self, ccy: str, curve: str) -> int:
        """Remove ALL cache entries for a given (ccy, curve). Returns count removed."""
        prefix = f"{ccy}|{curve}|"
        to_remove = [k for k in self._cache if k.startswith(prefix)]
        for k in to_remove:
            del self._cache[k]
        if to_remove:
            self._dirty = True
        return len(to_remove)

    def clear_all(self) -> int:
        """Remove all cache entries. Returns count removed."""
        count = len(self._cache)
        if count:
            self._cache.clear()
            self._dirty = True
        return count

    def save(self) -> None:
        """Write cache to JSON file."""
        if not self._dirty:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w") as f:
            json.dump(self._cache, f, indent=2, sort_keys=True)
        _log.info("cache_saved", entries=len(self._cache), path=str(self._path))
        self._dirty = False
