"""Commodities SPOT Citi Velocity Daily EOD Runner.

Target table: [commodities].[fact_spot]
Schedule: Daily (via imdr_daily.py)
Source: Citi Velocity Historical Data API

Usage:
    python -m scripts.commodities.citi.cmdty_spot_citi_live
    python -m scripts.commodities.citi.cmdty_spot_citi_live --date 2026-03-25
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
from imdr.domains.commodities.pipeline_spot import CmdtySpotPipeline
from imdr.market_calendar.calendar import last_business_day
from imdr.reporting.run_report import RunReport
from imdr.universe.commodities import get_commodities_universe
from imdr.utils.logging import configure_logging

log = structlog.get_logger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Commodities SPOT Daily EOD Ingest")
    parser.add_argument("--date", type=str, default=None, help="Override date (YYYY-MM-DD)")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = get_settings()
    configure_logging(settings)
    universe = get_commodities_universe()
    report = RunReport(pipeline_name="commodities.spot_citi_live")

    if args.date:
        target = datetime.strptime(args.date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    else:
        target = last_business_day("US")

    start = target
    end = target.replace(hour=23, minute=59)

    log.info("cmdty_spot_live_start", date=str(target.date()))

    connector = MSSQLConnector(settings)
    try:
        t0 = time.perf_counter()
        pipeline = CmdtySpotPipeline(
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

        report.finish()
        if settings.run_log_dir:
            log_path = (
                Path(settings.run_log_dir)
                / "commodities" / "fact_spot"
                / f"cmdty_spot_citi_live_{target:%Y%m%d}.jsonl"
            )
            report.flush_jsonl(log_path)

        log.info("cmdty_spot_live_complete", date=str(target.date()),
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
                / "commodities" / "fact_spot"
                / f"cmdty_spot_citi_live_{target:%Y%m%d}.jsonl"
            )
            report.flush_jsonl(log_path)
        return 1
    except Exception:
        log.exception("cmdty_spot_live_failed")
        report.error("pipeline", "Daily commodity spot ingest failed")
        report.finish()
        return 1
    finally:
        connector.dispose()


if __name__ == "__main__":
    sys.exit(main())
