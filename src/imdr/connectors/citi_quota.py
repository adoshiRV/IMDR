"""Citi Velocity rolling 24-hour tag quota tracker.

Persists cumulative tag usage to a JSON file so that separate subprocess
pipelines (rates, fx vol, rates vol) share a single view of the 100K
rolling quota.  Uses ``filelock`` for cross-process safety.

Usage:
    tracker = TagQuotaTracker()
    tracker.check_budget(needed=15_000, pipeline="rates.citi_live")
    # ... inside fetch loop ...
    tracker.record_usage("rates.citi_live", tags=100)
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import structlog
from filelock import FileLock

_log = structlog.get_logger("citi_quota")

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_PATH = _PROJECT_ROOT / "data" / "cache" / "citi_tag_quota.json"
_WINDOW_HOURS = 24


class TagQuotaTracker:
    """File-based rolling 24h tag quota tracker.

    Parameters
    ----------
    quota_limit : int
        Maximum tags allowed within the rolling window (default 95_000,
        a 5K safety margin below the Citi 100K hard limit).
    tracker_path : Path | None
        JSON file to persist usage entries.  ``None`` → default
        ``data/cache/citi_tag_quota.json``.
    """

    def __init__(
        self,
        quota_limit: int = 95_000,
        tracker_path: Path | str | None = None,
    ) -> None:
        self._limit = quota_limit
        self._path = Path(tracker_path) if tracker_path else _DEFAULT_PATH
        self._lock_path = self._path.with_suffix(".lock")
        self._lock = FileLock(self._lock_path, timeout=10)

    # ── Public API ────────────────────────────────────────────────

    def record_usage(self, pipeline: str, tags: int) -> None:
        """Append a usage entry (thread/process safe)."""
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "pipeline": pipeline,
            "tags": tags,
        }
        with self._lock:
            entries = self._read_entries()
            entries.append(entry)
            self._write_entries(entries)

        _log.debug(
            "quota_recorded",
            pipeline=pipeline,
            tags=tags,
            cumulative=self.current_usage(),
        )

    def current_usage(self) -> int:
        """Sum of tags within the rolling 24h window."""
        with self._lock:
            entries = self._read_entries()
        return sum(e["tags"] for e in entries)

    def remaining(self) -> int:
        """Tags remaining before hitting the quota limit."""
        return max(0, self._limit - self.current_usage())

    def check_budget(self, needed: int, pipeline: str) -> None:
        """Raise if ``needed`` tags would exceed the remaining budget.

        Call this *before* starting extraction so no partial API calls
        are wasted.
        """
        from imdr.connectors.citi_helpers import TagQuotaBudgetExceeded

        avail = self.remaining()
        if needed > avail:
            raise TagQuotaBudgetExceeded(
                f"Pipeline {pipeline} needs {needed:,} tags but only "
                f"{avail:,} remain (limit={self._limit:,}, "
                f"used={self.current_usage():,})",
                needed=needed,
                remaining=avail,
                current_usage=self.current_usage(),
            )
        _log.info(
            "quota_budget_ok",
            pipeline=pipeline,
            needed=needed,
            remaining=avail,
        )

    def entries(self) -> list[dict[str, Any]]:
        """Return current (pruned) entries — for inspection / reporting."""
        with self._lock:
            return self._read_entries()

    # ── Internal ──────────────────────────────────────────────────

    def _read_entries(self) -> list[dict[str, Any]]:
        """Read JSON, prune entries older than 24h.  Caller holds lock."""
        if not self._path.exists():
            return []

        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            _log.warning("quota_file_corrupted_resetting", path=str(self._path))
            return []

        cutoff = datetime.now(timezone.utc) - timedelta(hours=_WINDOW_HOURS)
        pruned: list[dict[str, Any]] = []
        for e in raw.get("entries", []):
            try:
                ts = datetime.fromisoformat(e["ts"])
                if ts >= cutoff:
                    pruned.append(e)
            except (KeyError, ValueError):
                continue  # skip malformed entries

        # Write back pruned list to keep the file clean
        if len(pruned) != len(raw.get("entries", [])):
            self._write_entries(pruned)

        return pruned

    def _write_entries(self, entries: list[dict[str, Any]]) -> None:
        """Write entries to JSON.  Caller holds lock."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps({"entries": entries}, indent=2),
            encoding="utf-8",
        )
