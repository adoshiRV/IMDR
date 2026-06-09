"""FX Rate Citi Velocity Historical Backfiller.

Target table: [fx].[fact_fx_rate]
Modes: range, catchup, gaps
Source: Citi Velocity Historical Data API

Edit CONFIGURE HERE variables and run:
    python -m scripts.fx.citi.fx_rate_citi_historical
"""

from __future__ import annotations

import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import structlog

from imdr.config.settings import get_settings
from imdr.connectors.mssql import MSSQLConnector
from imdr.domains.fx.pipeline_rate import FXRatePipeline
from imdr.reporting.run_report import RunReport
from imdr.universe.fx import get_fx_universe
from imdr.utils.logging import configure_logging

log = structlog.get_logger(__name__)

# ============================================================================
# CONFIGURE HERE
# ============================================================================

MODE = "range"  # "range" | "catchup" | "gaps"

# range mode
START = "2007-01-01"
END = "2026-05-04"

# catchup mode
LOOKBACK_DAYS = 5

# gaps mode
GAPS_FILE = "data/gaps/fx_rate_gaps.txt"

MAX_DAYS = 0  # 0 = unlimited

# Optional: restrict to specific (ccy1, ccy2) pairs. None = all fx_rate pairs in fx.yml.
PAIRS: list[tuple[str, str]] | None = None  # None = all Citi-eligible (excludes bbg_only)

# In range mode, run the full date span as a single pipeline call rather than
# day-by-day. Much faster for multi-year backfills (one Citi POST per tag-batch).
BULK_RANGE = True

# ============================================================================


def _business_days(start: datetime, end: datetime) -> list[datetime]:
    days: list[datetime] = []
    cur = start
    while cur <= end:
        if cur.weekday() < 5:
            days.append(cur)
        cur += timedelta(days=1)
    return days


def _parse_dates_from_file(path: Path) -> list[datetime]:
    dates: list[datetime] = []
    for line in path.read_text().strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        dt = datetime.strptime(line, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        if dt.weekday() < 5:
            dates.append(dt)
    return sorted(dates)


def main() -> int:
    settings = get_settings()
    configure_logging(settings)

    universe = get_fx_universe()
    report = RunReport(pipeline_name="fx.citi_rate_historical")

    if MODE == "range":
        start_dt = datetime.strptime(START, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        end_dt = datetime.strptime(END, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        days = _business_days(start_dt, end_dt)
    elif MODE == "catchup":
        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        days = _business_days(today - timedelta(days=LOOKBACK_DAYS), today)
    elif MODE == "gaps":
        days = _parse_dates_from_file(Path(GAPS_FILE))
    else:
        log.error("unknown_mode", mode=MODE)
        return 1

    if MAX_DAYS:
        days = days[:MAX_DAYS]

    log.info("fx_rate_historical_start", mode=MODE, n_days=len(days), bulk=(MODE == "range" and BULK_RANGE))

    total_rows = 0
    connector = MSSQLConnector(settings)
    try:
        if MODE == "range" and BULK_RANGE and days:
            t0 = time.perf_counter()
            pipeline = FXRatePipeline(
                connector=connector,
                settings=settings,
                universe=universe,
                start=days[0],
                end=days[-1].replace(hour=23, minute=59),
                pairs=PAIRS,
                chunk_size=settings.bulk_batch_size,
            )
            try:
                total_rows = pipeline.run()
                log.info(
                    "bulk_range_complete",
                    start=str(days[0].date()), end=str(days[-1].date()),
                    rows=total_rows, n_days=len(days),
                    elapsed=f"{time.perf_counter() - t0:.1f}s",
                )
            except Exception as e:
                report.error("range", f"Bulk range failed: {e}",
                             details={"error": str(e)})
                log.exception("bulk_range_failed")
                return 1
        else:
            for i, day in enumerate(days, start=1):
                t0 = time.perf_counter()
                pipeline = FXRatePipeline(
                    connector=connector,
                    settings=settings,
                    universe=universe,
                    start=day,
                    end=day.replace(hour=23, minute=59),
                    pairs=PAIRS,
                    chunk_size=settings.bulk_batch_size,
                )
                try:
                    rows = pipeline.run()
                except Exception as e:
                    report.warning(
                        "day_failed", f"Day {day.date()} failed: {e}",
                        details={"date": str(day.date()), "error": str(e)},
                    )
                    log.exception("day_failed", date=str(day.date()))
                    continue

                total_rows += rows
                log.info(
                    "day_complete",
                    date=str(day.date()), rows=rows,
                    elapsed=f"{time.perf_counter() - t0:.1f}s",
                    progress=f"{i}/{len(days)}",
                )

        report.info(
            "pipeline",
            f"Backfill complete: {total_rows} total rows over {len(days)} days",
            details={"mode": MODE, "n_days": len(days), "total_rows": total_rows},
        )
        report.finish()
        if settings.run_log_dir:
            log_path = (
                Path(settings.run_log_dir) / "fx" / "fact_fx_rate"
                / f"fx_rate_citi_historical_{datetime.now(timezone.utc):%Y%m%d_%H%M%S}.jsonl"
            )
            report.flush_jsonl(log_path)
        log.info("fx_rate_historical_complete", total_rows=total_rows, n_days=len(days))
        return 0
    finally:
        connector.dispose()


if __name__ == "__main__":
    sys.exit(main())
