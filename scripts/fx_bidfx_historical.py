"""FX BidFX Historical Backfiller.

Target table: [FX].[fact_ohlc]
Modes: range, catchup, rewrite, gaps
Source: BidFX Historical Tick API (basic auth)

Edit the variables below and run:
    python -m scripts.fx_bidfx_historical
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import structlog

from imdr.config.settings import get_settings
from imdr.connectors.mssql import MSSQLConnector
from imdr.domains.fx.extractors import PairCache
from imdr.domains.fx.ingest import HourResult, process_hour
from imdr.domains.fx.repository import FXOHLCRepository
from imdr.domains.fx.time_utils import HourWindow, iter_hour_windows
from imdr.market_calendar.holidays import holiday_hits_for_timestamp
from imdr.notifications.email import send_outlook_email
from imdr.notifications.formatters.fx_ingest import FXIngestFormatter
from imdr.reporting.run_report import RunReport
from imdr.universe.fx import get_fx_universe
from imdr.utils.logging import configure_logging

log = structlog.get_logger(__name__)

# ============================================================================
# CONFIGURE HERE
# ============================================================================

MODE = "range"  # "range" | "catchup" | "rewrite" | "gaps"

# range / rewrite: ISO datetimes (UTC)
START = "2026-03-04T00:00:00"
END = "2026-03-04T01:00:00"

# catchup: how many hours back from now
LOOKBACK_HOURS = 48

# gaps: path to a text file with one ISO timestamp per line
GAPS_FILE = "data/gaps/gaps.txt"

# 0 = unlimited
MAX_HOURS = 0

# ============================================================================


def _compute_windows(mode: str, connector: MSSQLConnector) -> list[HourWindow]:
    """Compute hour windows based on mode."""
    now = datetime.now(timezone.utc)

    if mode == "range":
        start = datetime.fromisoformat(START).replace(tzinfo=timezone.utc)
        end = datetime.fromisoformat(END).replace(tzinfo=timezone.utc)
        return iter_hour_windows(start, end)

    if mode == "catchup":
        end = now.replace(minute=0, second=0, microsecond=0)
        start = end - timedelta(hours=LOOKBACK_HOURS)
        return iter_hour_windows(start, end)

    if mode == "rewrite":
        start = datetime.fromisoformat(START).replace(tzinfo=timezone.utc)
        end = datetime.fromisoformat(END).replace(tzinfo=timezone.utc)
        # Delete existing data in range first
        with connector.session() as session:
            repo = FXOHLCRepository(session)
            deleted = repo.delete_range(start, end)
            log.info("rewrite_deleted", start=str(start), end=str(end), rows=deleted)
        return iter_hour_windows(start, end)

    if mode == "gaps":
        gaps_path = Path(GAPS_FILE)
        if not gaps_path.exists():
            print(f"ERROR: Gaps file not found: {gaps_path}")
            sys.exit(1)
        windows = []
        for line in gaps_path.read_text().strip().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            ts = datetime.fromisoformat(line).replace(tzinfo=timezone.utc)
            windows.append(HourWindow(start=ts, end=ts + timedelta(hours=1)))
        return windows

    return []


def main() -> int:
    settings = get_settings()
    configure_logging(settings)

    universe = get_fx_universe()
    connector = MSSQLConnector(settings)
    report = RunReport(pipeline_name="fx.bidfx_historical")

    windows = _compute_windows(MODE, connector)
    if not windows:
        log.info("no_windows_to_process")
        return 0

    # Apply max hours limit
    if MAX_HOURS > 0:
        windows = windows[:MAX_HOURS]

    log.info("historical_start", mode=MODE, windows=len(windows))

    # Load pair cache
    pair_cache = None
    if settings.cache_dir:
        cache_path = Path(settings.cache_dir) / "fx" / "bidfx_pair_availability.json"
        pair_cache = PairCache.load(cache_path)

    all_results: list[HourResult] = []
    try:
        for i, w in enumerate(windows):
            # Skip closed hours
            if not universe.is_fx_open(w.start):
                log.debug("skipping_closed_hour", window=str(w))
                continue

            log.info("processing_hour", window=str(w), progress=f"{i + 1}/{len(windows)}")
            result = process_hour(
                window=w,
                universe=universe,
                settings=settings,
                connector=connector,
                report=report,
                pair_cache=pair_cache,
            )
            all_results.append(result)

        # Save pair cache
        if pair_cache is not None:
            pair_cache.save()

        # Summary
        total_bars = sum(r.bars_approved for r in all_results)
        total_drops = sum(r.bars_dropped for r in all_results)
        all_missing = set()
        for r in all_results:
            all_missing.update(r.missing_ccy)

        log.info(
            "historical_complete",
            mode=MODE,
            hours_processed=len(all_results),
            total_bars=total_bars,
            total_drops=total_drops,
        )

        # One summary email for the entire backfill
        if settings.email_enabled and settings.email_to and all_results:
            _send_summary_email(all_results, settings, report)

        report.finish()

        # Flush RunReport to JSONL
        if settings.run_log_dir:
            ts = datetime.now(timezone.utc)
            log_path = Path(settings.run_log_dir) / "fx" / "fact_ohlc" / f"fx_bidfx_historical_{ts:%Y%m%d_%H%M%S}.jsonl"
            report.flush_jsonl(log_path)

        return 0

    except Exception:
        log.exception("historical_failed")
        report.error("pipeline", "Historical backfill failed")
        report.finish()
        return 1
    finally:
        connector.dispose()


def _send_summary_email(
    results: list[HourResult],
    settings: object,
    report: RunReport,
) -> None:
    """Build and send the historical summary email."""
    total_bars = sum(r.bars_approved for r in results)
    total_produced = sum(r.bars_produced for r in results)
    total_drops = sum(r.bars_dropped for r in results)
    all_missing: set[str] = set()
    all_anomalies: list[dict] = []
    for r in results:
        all_missing.update(r.missing_ccy)
        all_anomalies.extend(r.anomalies)

    first_window = results[0].window
    last_window = results[-1].window

    formatter = FXIngestFormatter()
    subject = formatter.format_subject(
        pipeline_name="fx.bidfx_historical",
        window_start=first_window.start,
        bars_approved=total_bars,
        has_errors=report.has_errors,
        is_historical=True,
    )
    body = formatter.format_body(
        pipeline_name="fx.bidfx_historical",
        window_start=first_window.start,
        window_end=last_window.end,
        bars_produced=total_produced,
        bars_approved=total_bars,
        bars_dropped=total_drops,
        missing_ccy=sorted(all_missing),
        anomalies=all_anomalies,
        is_historical=True,
        hours_processed=len(results),
        total_bars=total_bars,
    )
    send_outlook_email(
        to=settings.email_to,  # type: ignore[attr-defined]
        subject=subject,
        html_body=body,
        importance=2 if report.has_errors else 1,
    )


if __name__ == "__main__":
    sys.exit(main())
