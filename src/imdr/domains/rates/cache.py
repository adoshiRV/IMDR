"""JSON file cache for empty (ccy, curve, quote) combos.

Tracks which API calls return 0 rows so they can be skipped on future runs.
Stale entries (>stale_days old) are automatically retried.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import structlog

_log = structlog.get_logger("CurveQuoteCache")

_CACHE_FILENAME = "empty_combos.json"


class CurveQuoteCache:
    """JSON-backed cache of (ccy, curve, quote) combos known to return 0 rows."""

    def __init__(self, cache_dir: str | Path, stale_days: int = 30) -> None:
        self._path = Path(cache_dir) / "rates" / _CACHE_FILENAME
        self._stale_days = stale_days
        # {f"{ccy}|{curve}|{quote}": "YYYY-MM-DD"}
        self._cache: dict[str, str] = {}
        self._dirty = False

    @staticmethod
    def _key(ccy: str, curve: str, quote: str) -> str:
        return f"{ccy}|{curve}|{quote}"

    def load(self) -> None:
        """Read cache from JSON file if it exists."""
        if self._path.exists():
            with open(self._path) as f:
                self._cache = json.load(f)
        _log.info("cache_loaded", entries=len(self._cache), path=str(self._path))

    def should_skip(self, ccy: str, curve: str, quote: str) -> bool:
        """True if cached AND last_checked is within stale_days."""
        last_str = self._cache.get(self._key(ccy, curve, quote))
        if last_str is None:
            return False
        last_checked = date.fromisoformat(last_str)
        return (date.today() - last_checked) < timedelta(days=self._stale_days)

    def mark_empty(self, ccy: str, curve: str, quote: str) -> None:
        """Record combo as empty with today's date."""
        self._cache[self._key(ccy, curve, quote)] = date.today().isoformat()
        self._dirty = True

    def mark_active(self, ccy: str, curve: str, quote: str) -> None:
        """Remove combo from cache — it now returns data."""
        key = self._key(ccy, curve, quote)
        if key in self._cache:
            del self._cache[key]
            self._dirty = True

    def save(self) -> None:
        """Write cache to JSON file."""
        if not self._dirty:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w") as f:
            json.dump(self._cache, f, indent=2, sort_keys=True)
        _log.info("cache_saved", entries=len(self._cache), path=str(self._path))
        self._dirty = False
