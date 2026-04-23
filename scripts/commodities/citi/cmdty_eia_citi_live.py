"""Commodities EIA Citi Velocity Weekly Runner.

Target table: [commodities].[fact_eia]
Schedule: Weekly (via imdr_weekly.py), targets last Wednesday publication
Source: Citi Velocity Historical Data API

Usage:
    python -m scripts.commodities.citi.cmdty_eia_citi_live
    python -m scripts.commodities.citi.cmdty_eia_citi_live --date 2026-03-19
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import structlog

from imdr.config.settings import get_settings
from imdr.connectors.citi_helpers import TagQuotaExceeded
from imdr.connectors.mssql import MSSQLConnector
from imdr.domains.commodities.pipeline_eia import CmdtyEIAPipeline
from imdr.reporting.run_report import RunReport
from imdr.universe.commodities import get_commodities_universe
from imdr.utils.logging import configure_logging

log = structlog.get_logger(__name__)


def _last_wednesday(ref: date) -> date:
    """Walk back to most recent Wednesday (EIA publication day)."""
    days_since = (ref.weekday() - 2) % 7
    if days_since == 0:
        days_since = 7  # If today is Wednesday, get last week's
    return ref - timedelta(days=days_since)


LOOKBACK_DAYS = 35  # covers ~5 weekly publications; absorbs missed scheduler runs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Commodities EIA Weekly Ingest")
    parser.add_argument("--date", type=str, default=None, help="Override date (YYYY-MM-DD)")
    parser.add_argument("--lookback", type=int, default=LOOKBACK_DAYS,
                        help="Days to look back (default: 35) — absorbs missed weekly runs")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = get_settings()
    configure_logging(settings)
    universe = get_commodities_universe()
    report = RunReport(pipeline_name="commodities.eia_citi_live")

    if args.date:
        target = datetime.strptime(args.date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    else:
        # Target the most recent Wednesday publication
        wed = _last_wednesday(date.today())
        target = datetime(wed.year, wed.month, wed.day, tzinfo=timezone.utc)

    end = target.replace(hour=23, minute=59)
    start = target - timedelta(days=args.lookback)

    log.info("cmdty_eia_live_start", date=str(target.date()))

    connector = MSSQLConnector(settings)
    try:
        t0 = time.perf_counter()
        pipeline = CmdtyEIAPipeline(
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

        # Coverage check: which configured EIA series got zero rows?
        all_series = [e.series_name for e in universe.eia_series_create_entries()]
        missing_series: list[str] = []
        if pipeline._raw_df is not None and not pipeline._raw_df.empty:
            loaded = set(pipeline._raw_df["series_name"].unique())
            missing_series = [s for s in all_series if s not in loaded]
        else:
            missing_series = all_series[:]

        if missing_series:
            report.error(
                "coverage",
                f"{len(missing_series)} EIA series returned zero rows across {args.lookback}-day window",
                details={
                    "missing_series": missing_series,
                    "window_start": str(start.date()),
                    "window_end": str(target.date()),
                },
            )

        report.finish()
        if settings.run_log_dir:
            log_path = (
                Path(settings.run_log_dir)
                / "commodities" / "fact_eia"
                / f"cmdty_eia_citi_live_{target:%Y%m%d}.jsonl"
            )
            report.flush_jsonl(log_path)

        log.info("cmdty_eia_live_complete", date=str(target.date()),
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
                / "commodities" / "fact_eia"
                / f"cmdty_eia_citi_live_{target:%Y%m%d}.jsonl"
            )
            report.flush_jsonl(log_path)
        return 1
    except Exception:
        log.exception("cmdty_eia_live_failed")
        report.error("pipeline", "Weekly EIA ingest failed")
        report.finish()
        return 1
    finally:
        connector.dispose()


if __name__ == "__main__":
    sys.exit(main())
