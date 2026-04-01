"""Rates Swaption Vol Citi Velocity Historical Backfiller.

Target table: [rates].[fact_swaption_vol]
Modes: range, catchup, gaps
Source: Citi Velocity Historical Data API (OAuth2)

Uses batch API calls (full date range per call), matching rates_citi_historical
pattern. The API returns per-tag time series, so one call covers the entire
date range — no need for day-by-day loops.

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
from imdr.market_calendar.calendar import last_business_day
from imdr.reporting.run_report import RunReport
from imdr.universe.rates import get_rates_universe
from imdr.utils.logging import configure_logging

log = structlog.get_logger(__name__)

# ============================================================================
# CONFIGURE HERE
# ============================================================================

MODE = "range"  # "range" | "catchup" | "gaps"

# range: start and end dates (YYYY-MM-DD)
START = "2025-06-01"
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
    """Adjust start/end to skip leading/trailing weekends."""
    while start.weekday() >= 5 and start <= end:
        start += timedelta(days=1)
    while end.weekday() >= 5 and end >= start:
        end -= timedelta(days=1)
    return start, end


def _parse_dates_from_file(path: Path) -> list[datetime]:
    """Read YYYY-MM-DD dates from a text file, one per line."""
    dates: list[datetime] = []
    for line in path.read_text().strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        dt = datetime.strptime(line, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        if dt.weekday() < 5:  # skip weekends
            dates.append(dt)
    return sorted(dates)


def _run_pipeline(
    connector: MSSQLConnector,
    settings: object,
    universe: object,
    start: datetime,
    end: datetime,
    currencies: list[str] | None,
    label: str,
    chunk_size: int | None = None,
) -> int:
    """Run a single pipeline call and return rows loaded."""
    log.info("processing", label=label, start=str(start.date()), end=str(end.date()))
    pipeline = RatesVolPipeline(
        connector=connector,
        settings=settings,  # type: ignore[arg-type]
        universe=universe,  # type: ignore[arg-type]
        start=start,
        end=end,
        currencies=currencies,
        chunk_size=chunk_size,
    )
    return pipeline.run()


def main() -> int:
    settings = get_settings()
    configure_logging(settings)
    universe = get_rates_universe()
    connector = MSSQLConnector(settings)
    report = RunReport(pipeline_name="rates.vol_citi_historical")

    log.info("historical_start", mode=MODE)

    try:
        t0 = time.perf_counter()
        total_rows = 0

        if MODE == "range":
            start = datetime.strptime(START, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            end = datetime.strptime(END, "%Y-%m-%d").replace(
                hour=23, minute=59, tzinfo=timezone.utc,
            )
            start, end = _skip_weekends(start, end)
            total_rows = _run_pipeline(
                connector, settings, universe, start, end, CURRENCIES,
                label=f"range {START} -> {END}",
                chunk_size=settings.bulk_batch_size,
            )

        elif MODE == "catchup":
            end = last_business_day("US").replace(
                hour=23, minute=59, second=0, microsecond=0,
            )
            start = (end - timedelta(days=LOOKBACK_DAYS)).replace(
                hour=0, minute=0, second=0, microsecond=0,
            )
            start, end = _skip_weekends(start, end)
            total_rows = _run_pipeline(
                connector, settings, universe, start, end, CURRENCIES,
                label=f"catchup {LOOKBACK_DAYS}d",
                chunk_size=settings.bulk_batch_size,
            )

        elif MODE == "gaps":
            gaps_path = Path(GAPS_FILE)
            if not gaps_path.exists():
                print(f"ERROR: Gaps file not found: {gaps_path}")
                return 1

            dates = _parse_dates_from_file(gaps_path)
            if MAX_DAYS > 0:
                dates = dates[:MAX_DAYS]

            log.info("gaps_loaded", dates=len(dates))

            for i, dt in enumerate(dates):
                try:
                    rows = _run_pipeline(
                        connector, settings, universe,
                        start=dt,
                        end=dt.replace(hour=23, minute=59),
                        currencies=CURRENCIES,
                        label=f"gap {i + 1}/{len(dates)} ({dt.date()})",
                        chunk_size=settings.bulk_batch_size,
                    )
                    total_rows += rows
                except Exception:
                    log.exception("gap_date_failed", date=str(dt.date()))
                    report.error("gap", f"Failed for {dt.date()}")

        else:
            print(f"ERROR: Unknown MODE '{MODE}'. Use: range, catchup, gaps")
            return 1

        elapsed = time.perf_counter() - t0

        report.info("pipeline", f"Historical complete: {total_rows} rows", details={
            "mode": MODE,
            "total_rows": total_rows,
            "elapsed_secs": round(elapsed, 1),
        })
        report.finish()

        # Flush RunReport to JSONL
        if settings.run_log_dir:
            ts = datetime.now(timezone.utc)
            log_path = (
                Path(settings.run_log_dir)
                / "rates"
                / "swaption_vol"
                / f"rates_vol_citi_historical_{ts:%Y%m%d_%H%M%S}.jsonl"
            )
            report.flush_jsonl(log_path)

        log.info(
            "historical_complete",
            mode=MODE,
            total_rows=total_rows,
            elapsed=f"{elapsed:.1f}s",
        )
        return 0

    except Exception:
        log.exception("historical_failed")
        report.error("pipeline", "Historical backfill failed")
        report.finish()
        return 1
    finally:
        connector.dispose()


if __name__ == "__main__":
    sys.exit(main())
