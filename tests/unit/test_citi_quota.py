"""Tests for Citi Velocity tag quota tracker and related error handling."""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from imdr.connectors.citi_helpers import (
    TagQuotaBudgetExceeded,
    TagQuotaExceeded,
    fetch_and_parse_batched,
)
from imdr.connectors.citi_quota import TagQuotaTracker


# ── TagQuotaTracker ──────────────────────────────────────────────


class TestTagQuotaTracker:
    """Tests for the file-based rolling 24h quota tracker."""

    def test_creates_file_on_first_write(self, tmp_path: Path) -> None:
        tracker_path = tmp_path / "quota.json"
        tracker = TagQuotaTracker(quota_limit=100_000, tracker_path=tracker_path)

        assert not tracker_path.exists()
        tracker.record_usage("test_pipeline", 500)
        assert tracker_path.exists()

    def test_record_and_read_usage(self, tmp_path: Path) -> None:
        tracker = TagQuotaTracker(quota_limit=100_000, tracker_path=tmp_path / "q.json")
        tracker.record_usage("pipeline_a", 1000)
        tracker.record_usage("pipeline_b", 2000)

        assert tracker.current_usage() == 3000
        assert tracker.remaining() == 97_000

    def test_prunes_old_entries(self, tmp_path: Path) -> None:
        tracker_path = tmp_path / "q.json"
        tracker = TagQuotaTracker(quota_limit=100_000, tracker_path=tracker_path)

        # Manually write an entry 25 hours ago (should be pruned)
        old_ts = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
        recent_ts = datetime.now(timezone.utc).isoformat()
        tracker_path.write_text(json.dumps({
            "entries": [
                {"ts": old_ts, "pipeline": "old", "tags": 50_000},
                {"ts": recent_ts, "pipeline": "recent", "tags": 10_000},
            ]
        }))

        assert tracker.current_usage() == 10_000  # old entry pruned

    def test_remaining_never_negative(self, tmp_path: Path) -> None:
        tracker = TagQuotaTracker(quota_limit=1000, tracker_path=tmp_path / "q.json")
        tracker.record_usage("big", 5000)
        assert tracker.remaining() == 0  # clamped to 0, not -4000

    def test_check_budget_passes(self, tmp_path: Path) -> None:
        tracker = TagQuotaTracker(quota_limit=100_000, tracker_path=tmp_path / "q.json")
        tracker.record_usage("existing", 50_000)

        # Should not raise
        tracker.check_budget(40_000, "new_pipeline")

    def test_check_budget_raises(self, tmp_path: Path) -> None:
        tracker = TagQuotaTracker(quota_limit=100_000, tracker_path=tmp_path / "q.json")
        tracker.record_usage("existing", 80_000)

        with pytest.raises(TagQuotaBudgetExceeded) as exc_info:
            tracker.check_budget(30_000, "greedy_pipeline")

        err = exc_info.value
        assert err.needed == 30_000
        assert err.remaining_budget == 20_000

    def test_corrupted_file_resets(self, tmp_path: Path) -> None:
        tracker_path = tmp_path / "q.json"
        tracker_path.write_text("NOT VALID JSON!!!")

        tracker = TagQuotaTracker(quota_limit=100_000, tracker_path=tracker_path)
        assert tracker.current_usage() == 0  # gracefully reset

    def test_missing_file_returns_zero(self, tmp_path: Path) -> None:
        tracker = TagQuotaTracker(
            quota_limit=100_000,
            tracker_path=tmp_path / "nonexistent.json",
        )
        assert tracker.current_usage() == 0

    def test_entries_returns_pruned_list(self, tmp_path: Path) -> None:
        tracker = TagQuotaTracker(quota_limit=100_000, tracker_path=tmp_path / "q.json")
        tracker.record_usage("a", 100)
        tracker.record_usage("b", 200)

        entries = tracker.entries()
        assert len(entries) == 2
        assert entries[0]["pipeline"] == "a"
        assert entries[1]["pipeline"] == "b"

    def test_malformed_entries_skipped(self, tmp_path: Path) -> None:
        tracker_path = tmp_path / "q.json"
        tracker_path.write_text(json.dumps({
            "entries": [
                {"ts": datetime.now(timezone.utc).isoformat(), "pipeline": "good", "tags": 100},
                {"bad_key": "no_ts"},  # malformed — should be skipped
                {"ts": "not-a-date", "pipeline": "bad_ts", "tags": 50},  # bad ts
            ]
        }))

        tracker = TagQuotaTracker(quota_limit=100_000, tracker_path=tracker_path)
        assert tracker.current_usage() == 100  # only the valid entry counts


# ── TagQuotaBudgetExceeded ───────────────────────────────────────


class TestTagQuotaBudgetExceeded:
    """Verify TagQuotaBudgetExceeded is a subclass of TagQuotaExceeded."""

    def test_is_subclass(self) -> None:
        assert issubclass(TagQuotaBudgetExceeded, TagQuotaExceeded)

    def test_caught_by_parent_handler(self) -> None:
        with pytest.raises(TagQuotaExceeded):
            raise TagQuotaBudgetExceeded(
                "Budget exceeded", needed=50_000, remaining=10_000, current_usage=90_000,
            )

    def test_attributes(self) -> None:
        err = TagQuotaBudgetExceeded(
            "Budget exceeded", needed=50_000, remaining=10_000, current_usage=90_000,
        )
        assert err.needed == 50_000
        assert err.remaining_budget == 10_000
        assert err.current_usage == 90_000
        assert err.available == 10_000  # inherited from parent


# ── fetch_and_parse_batched with tracker ─────────────────────────


class TestFetchAndParseBatchedWithTracker:
    """Verify quota tracking is wired into the batch fetch loop."""

    def test_records_usage_per_batch(self, tmp_path: Path) -> None:
        tracker = TagQuotaTracker(quota_limit=100_000, tracker_path=tmp_path / "q.json")

        # Mock client that returns OK responses
        mock_client = MagicMock()
        mock_client.fetch_historical.return_value = {"status": "OK", "body": {}}
        mock_client.rate_limit_remaining = None

        # Parser that returns empty DataFrame
        def parser(resp: dict) -> pd.DataFrame:
            return pd.DataFrame()

        tags = [f"TAG.{i}" for i in range(250)]  # 3 batches of 100

        fetch_and_parse_batched(
            client=mock_client,
            tags=tags,
            start=datetime(2026, 3, 25, tzinfo=timezone.utc),
            end=datetime(2026, 3, 25, 23, 59, tzinfo=timezone.utc),
            frequency="DAILY",
            batch_size=100,
            rate_limit=0,  # no sleep in tests
            response_parser=parser,
            quota_tracker=tracker,
            pipeline_name="test_pipeline",
        )

        assert tracker.current_usage() == 250
        entries = tracker.entries()
        assert len(entries) == 3
        assert all(e["pipeline"] == "test_pipeline" for e in entries)

    def test_works_without_tracker(self) -> None:
        """Backward compat — no tracker passed, no error."""
        mock_client = MagicMock()
        mock_client.fetch_historical.return_value = {"status": "OK", "body": {}}
        mock_client.rate_limit_remaining = None

        result = fetch_and_parse_batched(
            client=mock_client,
            tags=["TAG.1"],
            start=datetime(2026, 3, 25, tzinfo=timezone.utc),
            end=datetime(2026, 3, 25, 23, 59, tzinfo=timezone.utc),
            frequency="DAILY",
            batch_size=100,
            rate_limit=0,
            response_parser=lambda r: pd.DataFrame(),
        )

        assert result.empty
