"""Equity Index Citi Velocity Daily EOD Runner.

Target table: [equities].[fact_index_level]
Schedule: Daily (via imdr_daily.py)
Source: Citi Velocity Historical Data API

Usage:
    python -m scripts.equity.citi.equity_index_citi_live
    python -m scripts.equity.citi.equity_index_citi_live --date 2026-03-25
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import structlog

from imdr.config.settings import get_settings
from imdr.connectors.citi_helpers import TagQuotaExceeded
from imdr.connectors.mssql import MSSQLConnector
from imdr.domains.equity.pipeline_index import EquityIndexPipeline
from imdr.market_calendar.calendar import last_business_day
from imdr.market_calendar.holidays import holiday_hits_for_timestamp
from imdr.notifications.email import send_outlook_email
from imdr.notifications.formatters.equity_ingest import EquityIngestFormatter
from imdr.reporting.run_report import RunReport
from imdr.universe.equity import get_equity_universe
from imdr.utils.logging import configure_logging

log = structlog.get_logger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Equity Index Daily EOD Ingest")
    parser.add_argument("--date", type=str, default=None, help="Override date (YYYY-MM-DD)")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = get_settings()
    configure_logging(settings)
    universe = get_equity_universe()
    report = RunReport(pipeline_name="equity.index_citi_live")

    if args.date:
        target = datetime.strptime(args.date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    else:
        # Provisional: anchors on US/GT (SIFMA Govt Bond) per project-wide default.
        # Equity intent suggests "NY" (NYSE); follow-up tracked in
        # docs/admin/development/per_script_calendar_intent.md.
        target = last_business_day("US", "GT")

    start = target
    end = target.replace(hour=23, minute=59)

    log.info("equity_index_live_start", date=str(target.date()))

    connector = MSSQLConnector(settings)
    try:
        t0 = time.perf_counter()
        pipeline = EquityIndexPipeline(
            connector=connector, settings=settings,
            universe=universe, start=start, end=end,
        )
        result = pipeline.run()
        elapsed = time.perf_counter() - t0

        report.info("pipeline", f"Loaded {result} rows", details={
            "date": str(target.date()),
            "rows_loaded": result,
            "elapsed_secs": round(elapsed, 1),
            "quota_usage": pipeline._quota_usage,
        })

        if pipeline._extraction_errors:
            report.warning("extraction_errors",
                f"{len(pipeline._extraction_errors)} error(s)",
                details={"errors": pipeline._extraction_errors})

        # Holiday detection
        holiday_hits = holiday_hits_for_timestamp(universe.target_currencies(), target)
        if holiday_hits:
            report.info("holidays", f"Holiday hits: {len(holiday_hits)}", details={
                "hits": [{"currency": h.currency, "country_code": h.country_code,
                          "name": h.name} for h in holiday_hits],
            })

        # Send email notification
        if settings.email_enabled and settings.email_to:
            _send_report_email(
                settings=settings,
                report=report,
                target=target,
                result=result,
                holiday_hits=holiday_hits,
                elapsed_secs=elapsed,
                quota_usage=pipeline._quota_usage,
            )

        report.finish()
        if settings.run_log_dir:
            log_path = (
                Path(settings.run_log_dir)
                / "equities" / "fact_index_level"
                / f"equity_index_citi_live_{target:%Y%m%d}.jsonl"
            )
            report.flush_jsonl(log_path)

        log.info("equity_index_live_complete", date=str(target.date()),
                 rows=result, elapsed=f"{elapsed:.1f}s")
        return 0

    except TagQuotaExceeded as e:
        log.error("tag_quota_exceeded",
                  current_usage=getattr(e, "current_usage", None),
                  available=getattr(e, "available", None))
        report.error("tag_quota", f"Tag quota exceeded: {e}",
                     details={"current_usage": getattr(e, "current_usage", None),
                              "available": getattr(e, "available", None)})
        report.finish()
        if settings.run_log_dir:
            log_path = (
                Path(settings.run_log_dir)
                / "equities" / "fact_index_level"
                / f"equity_index_citi_live_{target:%Y%m%d}.jsonl"
            )
            report.flush_jsonl(log_path)
        return 1
    except Exception:
        log.exception("equity_index_live_failed")
        report.error("pipeline", "Daily equity index ingest failed")
        report.finish()
        return 1
    finally:
        connector.dispose()


def _send_report_email(
    settings: object,
    report: RunReport,
    target: datetime,
    result: int,
    holiday_hits: list,
    elapsed_secs: float,
    quota_usage: int | None = None,
) -> None:
    """Build and send the equity index ingest report email."""
    formatter = EquityIngestFormatter()
    has_errors = report.has_errors

    subject = formatter.format_subject(
        pipeline_name="equity.index_citi_live",
        run_date=target,
        rows_loaded=result,
        has_errors=has_errors,
    )
    body = formatter.format_body(
        pipeline_name="equity.index_citi_live",
        run_date=target,
        rows_loaded=result,
        holiday_hits=[
            {"currency": h.currency, "country_code": h.country_code, "name": h.name}
            for h in holiday_hits
        ],
        has_errors=has_errors,
        elapsed_secs=elapsed_secs,
        quota_usage=quota_usage,
    )
    send_outlook_email(
        to=settings.email_to,  # type: ignore[attr-defined]
        subject=subject,
        html_body=body,
        importance=2 if has_errors else 1,
    )


if __name__ == "__main__":
    sys.exit(main())
