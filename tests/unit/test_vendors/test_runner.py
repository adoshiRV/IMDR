from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from imdr.vendors.base import FetchResult, VendorFeed
from imdr.vendors.exceptions import NoEmailFound
from imdr.vendors.registry import VENDOR_FEEDS, register_feed


def _fetch_result(files: list[Path]) -> FetchResult:
    now = datetime(2026, 4, 23, 12, 0, tzinfo=timezone.utc)
    return FetchResult(
        vendor="test", feed="runner_test",
        saved_files=files, bytes_downloaded=len(files) * 10,
        started_at=now, finished_at=now,
    )


@pytest.fixture
def _register_test_feed() -> Any:
    """Register a fake feed for the test, clean up after."""
    acquirer = MagicMock()
    acquirer.name = "runner_test"

    pipeline = MagicMock()
    pipeline.run.return_value = 42
    pipeline._raw_df = None

    def builder(files: list[Path], connector: Any, settings: Any) -> Any:
        return pipeline

    formatter = MagicMock()
    formatter.format_subject.return_value = "ok subj"
    formatter.format_body.return_value = "<html/>"

    feed = VendorFeed(
        name="runner_test",
        vendor_code="test",
        acquirer=acquirer,
        pipeline_builder=builder,
        success_formatter=formatter,
        staleness_pipeline_name="test.runner",
    )
    register_feed(feed)
    try:
        yield {"feed": feed, "acquirer": acquirer, "pipeline": pipeline, "formatter": formatter}
    finally:
        VENDOR_FEEDS.pop("runner_test", None)


@pytest.fixture
def _patched_runner_deps(tmp_path: Path) -> Any:
    """Patch side-effecting pieces inside runner: MSSQL connector, email send, settings."""
    settings = MagicMock()
    settings.email_enabled = True
    settings.email_to = "ops@example.com"
    settings.run_log_dir = ""

    with (
        patch("imdr.vendors.runner.get_settings", return_value=settings),
        patch("imdr.vendors.runner.configure_logging"),
        patch("imdr.vendors.runner.MSSQLConnector") as mock_conn_cls,
        patch("imdr.vendors.runner.send_outlook_email") as mock_send,
    ):
        connector = MagicMock()
        mock_conn_cls.return_value = connector
        yield {"settings": settings, "connector": connector, "send": mock_send}


class TestRunnerHappyPath:
    def test_success_flow_returns_zero(
        self, tmp_path: Path, _register_test_feed: Any, _patched_runner_deps: Any
    ) -> None:
        from imdr.vendors.runner import run_vendor_feed_daily

        # Create real files on disk so _archive_files can move them.
        drop = tmp_path / "drop"
        drop.mkdir()
        f1 = drop / "a.xlsx"
        f1.write_bytes(b"x")
        f2 = drop / "b.xlsx"
        f2.write_bytes(b"y")

        _register_test_feed["acquirer"].fetch.return_value = _fetch_result([f1, f2])

        rc = run_vendor_feed_daily("runner_test", headless=True)
        assert rc == 0

        # Pipeline was built + run.
        _register_test_feed["pipeline"].run.assert_called_once()

        # Files were archived (moved out of drop/).
        assert not f1.exists() and not f2.exists()
        archive = drop / "old"
        assert archive.exists()
        assert len(list(archive.glob("*.xlsx"))) == 2

        # Success email sent (not failure).
        assert _patched_runner_deps["send"].called
        sent_subject = _patched_runner_deps["send"].call_args.kwargs["subject"]
        assert sent_subject == "ok subj"
        assert _patched_runner_deps["send"].call_args.kwargs["importance"] == 1


class TestRunnerFailurePaths:
    def test_acquire_failure_sends_failure_email(
        self, tmp_path: Path, _register_test_feed: Any, _patched_runner_deps: Any
    ) -> None:
        from imdr.vendors.runner import run_vendor_feed_daily

        _register_test_feed["acquirer"].fetch.side_effect = NoEmailFound("nope")
        # Pipeline should NEVER be built.
        _register_test_feed["pipeline"].run.side_effect = AssertionError("pipeline must not run")

        rc = run_vendor_feed_daily("runner_test", headless=True)
        assert rc == 1

        _register_test_feed["pipeline"].run.assert_not_called()

        # Failure email: importance 2, subject from VendorFetchFailureFormatter.
        send = _patched_runner_deps["send"]
        assert send.called
        kwargs = send.call_args.kwargs
        assert kwargs["importance"] == 2
        assert "FAILED" in kwargs["subject"]
        assert "NoEmailFound" in kwargs["subject"]

    def test_load_failure_sends_failure_email_and_no_archive(
        self, tmp_path: Path, _register_test_feed: Any, _patched_runner_deps: Any
    ) -> None:
        from imdr.vendors.runner import run_vendor_feed_daily

        drop = tmp_path / "drop"
        drop.mkdir()
        f1 = drop / "a.xlsx"
        f1.write_bytes(b"x")
        _register_test_feed["acquirer"].fetch.return_value = _fetch_result([f1])
        _register_test_feed["pipeline"].run.side_effect = RuntimeError("boom in load")

        rc = run_vendor_feed_daily("runner_test", headless=True)
        assert rc == 1

        # File NOT archived — it stays in the drop folder.
        assert f1.exists()
        assert not (drop / "old").exists()

        send = _patched_runner_deps["send"]
        assert send.called
        assert send.call_args.kwargs["importance"] == 2
        assert "RuntimeError" in send.call_args.kwargs["subject"]
