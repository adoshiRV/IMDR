"""Top-level runner for daily vendor feeds.

``run_vendor_feed_daily(name)`` is what ``scripts/run_vendor_feed.py``
(and therefore ``scripts/imdr_daily.py``) calls.  It owns the lifecycle:
acquire → load → archive → email → RunReport flush.  Returns 0/1 for
shell exit.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog

from imdr.config.settings import Settings, get_settings
from imdr.connectors.mssql import MSSQLConnector
from imdr.notifications.email import send_outlook_email
from imdr.notifications.formatters.vendor_fetch_failure import VendorFetchFailureFormatter
from imdr.reporting.run_report import RunReport
from imdr.utils.logging import configure_logging
from imdr.vendors.base import FetchResult, VendorFeed
from imdr.vendors.exceptions import VendorError
from imdr.vendors.registry import get_feed

log = structlog.get_logger(__name__)

_ARCHIVE_SUBDIR = "old"


def run_vendor_feed_daily(name: str, *, headless: bool = True) -> int:
    """Execute one vendor feed end-to-end.

    Returns 0 on full success, 1 on any failure (and sends a failure email).
    """
    feed = get_feed(name)
    settings = get_settings()
    configure_logging(settings)
    report = RunReport(pipeline_name=feed.staleness_pipeline_name)

    connector: MSSQLConnector | None = None
    result: FetchResult | None = None
    t_start = time.perf_counter()

    try:
        # ── Phase 1: acquire ──────────────────────────────────────────────
        try:
            result = feed.acquirer.fetch(headless=headless, report=report)
        except VendorError as exc:
            _handle_failure(settings, feed, report, phase="acquire", exc=exc)
            return 1

        # ── Phase 2: load ─────────────────────────────────────────────────
        connector = MSSQLConnector(settings)
        pipeline = feed.pipeline_builder(list(result.saved_files), connector, settings)
        try:
            rows = pipeline.run()
        except Exception as exc:
            _handle_failure(settings, feed, report, phase="load", exc=exc)
            return 1

        elapsed = time.perf_counter() - t_start
        report.info(
            "vendor_fetch.load",
            f"Loaded {rows} rows from {len(result.saved_files)} file(s)",
            details={"rows_loaded": rows, "elapsed_s": round(elapsed, 1)},
        )

        # ── Phase 3: archive + success email ──────────────────────────────
        archive_dir = result.saved_files[0].parent / _ARCHIVE_SUBDIR
        moved = _archive_files(list(result.saved_files), archive_dir)
        report.info(
            "vendor_fetch.archive",
            f"Archived {len(moved)} file(s)",
            details={"archive_dir": str(archive_dir)},
        )

        _send_success_email(
            settings=settings,
            feed=feed,
            result=result,
            pipeline=pipeline,
            rows_loaded=rows,
            elapsed_s=elapsed,
        )
        return 0

    finally:
        report.finish()
        _flush_report(settings, feed, report)
        if connector is not None:
            connector.dispose()


# ── Failure handling ──────────────────────────────────────────────────────

def _handle_failure(
    settings: Settings,
    feed: VendorFeed,
    report: RunReport,
    *,
    phase: str,
    exc: BaseException,
) -> None:
    error_type = type(exc).__name__
    message = str(exc) or error_type
    report.error(
        f"vendor_fetch.{phase}",
        message,
        details={"error_type": error_type, "feed": feed.name, "phase": phase},
    )
    log.exception("vendor_feed_failed", feed=feed.name, phase=phase, error_type=error_type)
    _send_failure_email(
        settings=settings,
        feed=feed,
        phase=phase,
        error_type=error_type,
        error_message=message,
    )


def _send_failure_email(
    *,
    settings: Settings,
    feed: VendorFeed,
    phase: str,
    error_type: str,
    error_message: str,
    details: dict[str, Any] | None = None,
) -> None:
    if not (settings.email_enabled and settings.email_to):
        return
    formatter = VendorFetchFailureFormatter()
    send_outlook_email(
        to=settings.email_to,
        subject=formatter.format_subject(feed_name=feed.name, error_type=error_type),
        html_body=formatter.format_body(
            feed_name=feed.name,
            vendor_code=feed.vendor_code,
            phase=phase,
            error_type=error_type,
            error_message=error_message,
            details=details,
        ),
        importance=2,
    )


def _send_success_email(
    *,
    settings: Settings,
    feed: VendorFeed,
    result: FetchResult,
    pipeline: Any,
    rows_loaded: int,
    elapsed_s: float,
) -> None:
    if not (settings.email_enabled and settings.email_to):
        return
    fmt = feed.success_formatter
    ctx: dict[str, Any] = {
        "rows_loaded": rows_loaded,
        "rows_extracted": rows_loaded,
        "n_files": len(result.saved_files),
        "file_names": [f.name for f in result.saved_files],
        "has_errors": False,
        "elapsed_secs": elapsed_s,
        "feed": feed.name,
    }
    if feed.success_context_builder is not None:
        try:
            ctx.update(feed.success_context_builder(pipeline, rows_loaded))
        except Exception:
            log.warning("success_context_builder_failed", feed=feed.name, exc_info=True)

    # Success formatters use **kwargs so unused keys are safe.
    subject = fmt.format_subject(**ctx)
    body = fmt.format_body(**ctx)
    send_outlook_email(to=settings.email_to, subject=subject, html_body=body, importance=1)


# ── File archival ────────────────────────────────────────────────────────

def _archive_files(files: list[Path], archive_dir: Path) -> list[Path]:
    """Move files to archive_dir; stamp each with the UTC run date."""
    archive_dir.mkdir(parents=True, exist_ok=True)
    run_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    moved: list[Path] = []
    for src in files:
        if not src.exists():
            continue
        dst = archive_dir / f"{src.stem}_{run_date}{src.suffix}"
        if dst.exists():
            ts = datetime.now(timezone.utc).strftime("%H%M%S")
            dst = archive_dir / f"{src.stem}_{run_date}_{ts}{src.suffix}"
        src.replace(dst)
        moved.append(dst)
    return moved


# ── RunReport flush ──────────────────────────────────────────────────────

def _flush_report(settings: Settings, feed: VendorFeed, report: RunReport) -> None:
    if not settings.run_log_dir:
        return
    ts = datetime.now(timezone.utc)
    path = (
        Path(settings.run_log_dir)
        / "vendors"
        / feed.name
        / f"{feed.name}_{ts:%Y%m%d_%H%M%S}.jsonl"
    )
    try:
        report.flush_jsonl(path)
    except Exception:
        log.warning("run_log_flush_failed", path=str(path), exc_info=True)
