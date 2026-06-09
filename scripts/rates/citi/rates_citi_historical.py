"""Rates Citi Velocity Historical Backfiller.

Target table: [rates].[fact_observation]
Modes: range, catchup, gaps
Source: Citi Velocity Historical Data API (OAuth2)

Edit the variables below and run:
    python -m scripts.rates.citi.rates_citi_historical
"""

from __future__ import annotations

import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import structlog

from imdr.config.pipeline_config import get_pipeline_config
from imdr.config.settings import get_settings
from imdr.connectors.mssql import MSSQLConnector
from imdr.domains.rates.pipeline import RatesHistoricalPipeline
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
START = "2024-05-05"
END = "2025-05-05"

# catchup: how many calendar days back from today
LOOKBACK_DAYS = 30

# gaps: path to a text file with one YYYY-MM-DD date per line
GAPS_FILE = "data/gaps/rates_gaps.txt"

# 0 = unlimited (for gaps mode, limits number of dates processed)
MAX_DAYS = 0

# Quote types (None = read from pipelines.yml default_quotes; or comma-separated override)
# QUOTES: str | None = None

QUOTES = "par,fwd"

# Data frequency
FREQUENCY = "HOURLY"

# When True, route through the dedicated hourly Citi OAuth client + tag-quota
# bucket so a HOURLY backfill doesn't eat into the daily pipelines' budget.
USE_HOURLY_CREDS = True
HOURLY_QUOTA_FILE = "data/cache/citi_tag_quota_hourly.json"

# Chunk a long range into N-month windows. Citi's HOURLY API silently
# downsamples to ~1 point/day when a single request spans >~6 months;
# probed thresholds: 1/2/3/4/6M preserve 12 hrs/day; 12M collapses.
# Set to 0 to disable chunking (one bulk call across full range).
CHUNK_MONTHS = 3

# Per-MERGE batch size for the DB load phase. 0 = use settings.bulk_batch_size
# (5000). Smaller value = lower TempDB peak, more frequent commits.
MERGE_BATCH_SIZE = 2500

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
    quotes: list[str],
    frequency: str,
    label: str,
    chunk_size: int | None = None,
) -> int:
    """Run a single pipeline call and return rows loaded."""
    log.info("processing", label=label, start=str(start.date()), end=str(end.date()))
    pipeline = RatesHistoricalPipeline(
        connector=connector,
        settings=settings,
        universe=universe,
        start=start,
        end=end,
        quotes=quotes,
        frequency=frequency,
        use_cache=False,
        chunk_size=chunk_size,
        client_id=settings.citi_hourly_client_id if USE_HOURLY_CREDS else None,
        client_secret=settings.citi_hourly_client_secret if USE_HOURLY_CREDS else None,
        quota_tracker_path=HOURLY_QUOTA_FILE if USE_HOURLY_CREDS else None,
    )
    return pipeline.run()


def main() -> int:
    settings = get_settings()
    configure_logging(settings)

    universe = get_rates_universe()
    connector = MSSQLConnector(settings)
    report = RunReport(pipeline_name="rates.citi_historical")
    if QUOTES is not None:
        quotes = [q.strip() for q in QUOTES.split(",")]
    else:
        pipeline_config = get_pipeline_config("rates.historical")
        quotes = pipeline_config.default_quotes or ["par"]

    log.info("historical_start", mode=MODE, quotes=quotes, frequency=FREQUENCY)

    try:
        t0 = time.perf_counter()
        total_rows = 0

        if MODE == "range":
            start = datetime.strptime(START, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            end = datetime.strptime(END, "%Y-%m-%d").replace(
                hour=23, minute=59, tzinfo=timezone.utc,
            )
            start, end = _skip_weekends(start, end)

            if CHUNK_MONTHS and CHUNK_MONTHS > 0:
                step = timedelta(days=int(CHUNK_MONTHS * 30.4375))
                chunks: list[tuple[datetime, datetime]] = []
                cur = start
                while cur <= end:
                    chunk_end = min(cur + step - timedelta(days=1), end)
                    chunk_end = chunk_end.replace(hour=23, minute=59)
                    chunks.append((cur, chunk_end))
                    cur = chunk_end + timedelta(minutes=1)
                    cur = cur.replace(hour=0, minute=0, second=0, microsecond=0)

                log.info("chunked_range", n_chunks=len(chunks), chunk_months=CHUNK_MONTHS)
                for i, (cs, ce) in enumerate(chunks, start=1):
                    cs2, ce2 = _skip_weekends(cs, ce)
                    rows = _run_pipeline(
                        connector, settings, universe, cs2, ce2, quotes, FREQUENCY,
                        label=f"chunk {i}/{len(chunks)} {cs2.date()} -> {ce2.date()}",
                        chunk_size=(MERGE_BATCH_SIZE or settings.bulk_batch_size),
                    )
                    total_rows += rows
            else:
                total_rows = _run_pipeline(
                    connector, settings, universe, start, end, quotes, FREQUENCY,
                    label=f"range {START} -> {END}",
                    chunk_size=settings.bulk_batch_size,
                )

        elif MODE == "catchup":
            end = last_business_day("US", "GT").replace(
                hour=23, minute=59, second=0, microsecond=0,
            )
            start = (end - timedelta(days=LOOKBACK_DAYS)).replace(
                hour=0, minute=0, second=0, microsecond=0,
            )
            start, end = _skip_weekends(start, end)
            total_rows = _run_pipeline(
                connector, settings, universe, start, end, quotes, FREQUENCY,
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
                        quotes=quotes,
                        frequency=FREQUENCY,
                        label=f"gap {i + 1}/{len(dates)} ({dt.date()})",
                        chunk_size=(MERGE_BATCH_SIZE or settings.bulk_batch_size),
                    )
                    total_rows += rows
                except Exception:
                    log.exception("gap_date_failed", date=str(dt.date()))
                    report.error("gap", f"Failed for {dt.date()}")
                    # Continue to next date

        else:
            print(f"ERROR: Unknown MODE '{MODE}'. Use: range, catchup, gaps")
            return 1

        elapsed = time.perf_counter() - t0

        report.info("pipeline", f"Historical complete: {total_rows} rows", details={
            "mode": MODE,
            "quotes": quotes,
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
                / "fact_observation"
                / f"rates_citi_historical_{ts:%Y%m%d_%H%M%S}.jsonl"
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
