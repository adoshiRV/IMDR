"""Rates Swaption Vol Citi Velocity Historical Backfiller.

Target table: [rates].[fact_swaption_vol]
Modes: range, catchup, gaps
Source: Citi Velocity Historical Data API (OAuth2)

Edit the variables below and run:
    python -m scripts.rates.citi.rates_vol_citi_historical
"""

from __future__ import annotations

import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import structlog

from imdr.config.settings import get_settings
from imdr.connectors.mssql import MSSQLConnector
from imdr.domains.rates.pipeline_vol import RatesVolPipeline
from imdr.reporting.run_report import RunReport
from imdr.universe.rates import get_rates_universe
from imdr.utils.logging import configure_logging

log = structlog.get_logger(__name__)

# ============================================================================
# CONFIGURE HERE
# ============================================================================

MODE = "range"  # "range" | "catchup" | "gaps"

# range: start and end dates (YYYY-MM-DD)
START = "2008-01-01"
END = "2026-01-01"

# catchup: how many calendar days back from today
LOOKBACK_DAYS = 30

# gaps: path to a text file with one YYYY-MM-DD date per line
GAPS_FILE = "data/gaps/rates_vol_gaps.txt"

# 0 = unlimited (for gaps mode, limits number of dates processed)
MAX_DAYS = 0

# Optional: limit to specific currencies (None = all 11)
CURRENCIES: list[str] | None = None

# ============================================================================


def _skip_weekends(start: datetime, end: datetime) -> tuple[datetime, datetime]:
    while start.weekday() >= 5 and start <= end:
        start += timedelta(days=1)
    while end.weekday() >= 5 and end >= start:
        end -= timedelta(days=1)
    return start, end


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


def _run_pipeline(
    connector: MSSQLConnector,
    settings: object,
    universe: object,
    start: datetime,
    end: datetime,
    currencies: list[str] | None,
    report: RunReport,
) -> int:
    pipeline = RatesVolPipeline(
        connector=connector,
        settings=settings,  # type: ignore[arg-type]
        universe=universe,  # type: ignore[arg-type]
        start=start,
        end=end,
        currencies=currencies,
    )
    return pipeline.run()


def main() -> int:
    settings = get_settings()
    configure_logging(settings)
    universe = get_rates_universe()
    connector = MSSQLConnector(settings)
    report = RunReport(pipeline_name="rates.vol_citi_historical")

    try:
        total_rows = 0
        total_days = 0

        if MODE == "range":
            start = datetime.strptime(START, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            end = datetime.strptime(END, "%Y-%m-%d").replace(
                hour=23, minute=59, tzinfo=timezone.utc
            )
            start, end = _skip_weekends(start, end)

            log.info("backfill_range_start", start=str(start.date()), end=str(end.date()))

            # Process day by day to keep batch sizes manageable
            current = start
            while current <= end:
                if current.weekday() >= 5:
                    current += timedelta(days=1)
                    continue

                day_end = current.replace(hour=23, minute=59)
                t0 = time.perf_counter()
                rows = _run_pipeline(connector, settings, universe, current, day_end, CURRENCIES, report)
                elapsed = time.perf_counter() - t0

                total_rows += rows
                total_days += 1
                log.info(
                    "backfill_day_complete",
                    date=str(current.date()), rows=rows, elapsed=f"{elapsed:.1f}s",
                    cumulative_rows=total_rows, cumulative_days=total_days,
                )

                current += timedelta(days=1)

        elif MODE == "catchup":
            today = datetime.now(timezone.utc).date()
            start_date = today - timedelta(days=LOOKBACK_DAYS)
            current = datetime(start_date.year, start_date.month, start_date.day, tzinfo=timezone.utc)
            end = datetime(today.year, today.month, today.day, tzinfo=timezone.utc) - timedelta(days=1)
            end = end.replace(hour=23, minute=59)

            log.info("backfill_catchup_start", lookback_days=LOOKBACK_DAYS, start=str(current.date()))

            while current <= end:
                if current.weekday() >= 5:
                    current += timedelta(days=1)
                    continue
                day_end = current.replace(hour=23, minute=59)
                rows = _run_pipeline(connector, settings, universe, current, day_end, CURRENCIES, report)
                total_rows += rows
                total_days += 1
                current += timedelta(days=1)

        elif MODE == "gaps":
            dates = _parse_dates_from_file(Path(GAPS_FILE))
            if MAX_DAYS > 0:
                dates = dates[:MAX_DAYS]
            log.info("backfill_gaps_start", n_dates=len(dates))

            for dt in dates:
                day_end = dt.replace(hour=23, minute=59)
                rows = _run_pipeline(connector, settings, universe, dt, day_end, CURRENCIES, report)
                total_rows += rows
                total_days += 1

        else:
            log.error("unknown_mode", mode=MODE)
            return 1

        report.info("backfill", f"Completed {total_days} days, {total_rows} rows")
        report.finish()

        log.info("backfill_complete", mode=MODE, total_days=total_days, total_rows=total_rows)
        return 0

    except Exception:
        log.exception("backfill_failed")
        report.error("backfill", "Historical backfill failed")
        report.finish()
        return 1
    finally:
        connector.dispose()


if __name__ == "__main__":
    sys.exit(main())
