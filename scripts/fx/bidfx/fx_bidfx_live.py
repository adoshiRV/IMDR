"""FX BidFX Live Hourly Runner.

Target table: [FX].[fact_ohlc]
Schedule: Hourly (via Windows Task Scheduler or cron)
Source: BidFX Historical Tick API (basic auth)

Usage:
    python -m scripts.fx.bidfx.fx_bidfx_live
    python -m scripts.fx.bidfx.fx_bidfx_live --hour 2026-03-09T13:00:00
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import structlog

from imdr.config.settings import get_settings
from imdr.connectors.mssql import MSSQLConnector
from imdr.domains.fx.extractors_ohlc import PairCache
from imdr.domains.fx.ingest import HourResult, process_hour
from imdr.utils.time_windows import HourWindow, last_full_utc_hour
from imdr.market_calendar.holidays import holiday_hits_for_timestamp
from imdr.notifications.email import send_outlook_email
from imdr.notifications.formatters.fx_ingest import FXIngestFormatter
from imdr.reporting.run_report import RunReport
from imdr.universe.fx import get_fx_universe
from imdr.utils.logging import configure_logging

log = structlog.get_logger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="FX BidFX Live Hourly Ingest")
    parser.add_argument(
        "--hour",
        type=str,
        default=None,
        help="Override hour to process (ISO format, e.g. 2026-03-09T13:00:00). Default: last full UTC hour.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = get_settings()
    configure_logging(settings)

    universe = get_fx_universe()
    connector = MSSQLConnector(settings)
    report = RunReport(pipeline_name="fx.bidfx_live")

    # Determine hour window
    if args.hour:
        start = datetime.fromisoformat(args.hour).replace(tzinfo=timezone.utc)
        window = HourWindow(start=start, end=start + timedelta(hours=1))
    else:
        window = last_full_utc_hour()

    log.info("fx_bidfx_live_start", window=str(window))

    # Check if FX market is open
    if not universe.is_fx_open(window.start):
        log.info("fx_market_closed", window=str(window))
        report.info("market", "FX market closed — skipping")
        report.finish()
        return 0

    # Load pair cache
    pair_cache = None
    if settings.cache_dir:
        cache_path = Path(settings.cache_dir) / "fx" / "bidfx_pair_availability.json"
        pair_cache = PairCache.load(cache_path)

    try:
        # Process the hour
        t0 = time.perf_counter()
        result = process_hour(
            window=window,
            universe=universe,
            settings=settings,
            connector=connector,
            report=report,
            pair_cache=pair_cache,
        )
        elapsed_secs = time.perf_counter() - t0

        # Save pair cache
        if pair_cache is not None:
            pair_cache.save()

        # Holiday check
        holiday_hits = holiday_hits_for_timestamp(
            universe.active_currencies, window.start,
        )
        if holiday_hits:
            report.info("holidays", f"Holiday hits: {len(holiday_hits)}", details={
                "hits": [{"currency": h.currency, "country_code": h.country_code, "name": h.name}
                         for h in holiday_hits],
            })

        # Send email
        if settings.email_enabled and settings.email_to:
            _send_report_email(result, holiday_hits, settings, report, elapsed_secs, n_symbols=len(universe.active_currencies))

        report.finish()

        # Flush RunReport to JSONL
        if settings.run_log_dir:
            log_path = Path(settings.run_log_dir) / "fx" / "fact_ohlc" / f"fx_bidfx_live_{window.start:%Y%m%d_%H%M}.jsonl"
            report.flush_jsonl(log_path)

        log.info("fx_bidfx_live_complete", bars=result.bars_approved)
        return 0

    except Exception:
        log.exception("fx_bidfx_live_failed")
        report.error("pipeline", "Live ingest failed")
        report.finish()
        return 1
    finally:
        connector.dispose()


def _send_report_email(
    result: HourResult,
    holiday_hits: list,
    settings: object,
    report: RunReport,
    elapsed_secs: float = 0.0,
    n_symbols: int = 0,
) -> None:
    """Build and send the ingest report email."""
    formatter = FXIngestFormatter()
    subject = formatter.format_subject(
        pipeline_name="fx.bidfx_live",
        window_start=result.window.start,
        bars_approved=result.bars_approved,
        bars_produced=result.bars_produced,
        has_errors=report.has_errors,
    )
    body = formatter.format_body(
        pipeline_name="fx.bidfx_live",
        window_start=result.window.start,
        window_end=result.window.end,
        bars_produced=result.bars_produced,
        bars_approved=result.bars_approved,
        bars_dropped=result.bars_dropped,
        bars=result.bars,
        missing_ccy=result.missing_ccy,
        holiday_hits=[
            {"currency": h.currency, "country_code": h.country_code, "name": h.name}
            for h in holiday_hits
        ],
        anomalies=result.anomalies,
        diagnostics=result.diagnostics,
        quality_flags=result.quality_flags,
        elapsed_secs=elapsed_secs,
        n_symbols=n_symbols,
    )
    send_outlook_email(
        to=settings.email_to,  # type: ignore[attr-defined]
        subject=subject,
        html_body=body,
        importance=2 if report.has_errors else 1,
    )



if __name__ == "__main__":
    sys.exit(main())
