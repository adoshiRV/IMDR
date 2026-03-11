"""FX Vol Citi Velocity Historical Backfiller.

Target table: [fx].[fact_vol]
Modes: range, catchup, gaps
Source: Citi Velocity Historical Data API (OAuth2)

Edit the variables below and run:
    python -m scripts.fx.citi.fx_vol_citi_historical
"""

from __future__ import annotations

import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import structlog

from imdr.config.settings import get_settings
from imdr.connectors.mssql import MSSQLConnector
from imdr.domains.fx.pipeline_vol import FXVolPipeline
from imdr.reporting.run_report import RunReport
from imdr.universe.fx import get_fx_universe
from imdr.utils.logging import configure_logging

log = structlog.get_logger(__name__)

# ============================================================================
# CONFIGURE HERE
# ============================================================================

MODE = "range"  # "range" | "catchup" | "gaps"

# range: start and end dates (YYYY-MM-DD)
START = "2024-01-01"
END = "2024-01-31"

# catchup: how many calendar days back from today
LOOKBACK_DAYS = 30

# gaps: path to a text file with one YYYY-MM-DD date per line
GAPS_FILE = "data/gaps/fx_vol_gaps.txt"

# 0 = unlimited (for gaps mode, limits number of dates processed)
MAX_DAYS = 0

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
    label: str,
) -> int:
    """Run a single pipeline call and return rows loaded."""
    log.info("processing", label=label, start=str(start.date()), end=str(end.date()))
    pipeline = FXVolPipeline(
        connector=connector,
        settings=settings,
        universe=universe,
        start=start,
        end=end,
    )
    return pipeline.run()


def main() -> int:
    settings = get_settings()
    configure_logging(settings)

    universe = get_fx_universe()
    connector = MSSQLConnector(settings)
    report = RunReport(pipeline_name="fx.vol_citi_historical")

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
                connector, settings, universe, start, end,
                label=f"range {START}\u2192{END}",
            )

        elif MODE == "catchup":
            now = datetime.now(timezone.utc)
            end = (now - timedelta(days=1)).replace(
                hour=23, minute=59, second=0, microsecond=0,
            )
            start = (now - timedelta(days=LOOKBACK_DAYS)).replace(
                hour=0, minute=0, second=0, microsecond=0,
            )
            start, end = _skip_weekends(start, end)
            total_rows = _run_pipeline(
                connector, settings, universe, start, end,
                label=f"catchup {LOOKBACK_DAYS}d",
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
                        label=f"gap {i + 1}/{len(dates)} ({dt.date()})",
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
            "total_rows": total_rows,
            "elapsed_secs": round(elapsed, 1),
        })
        report.finish()

        # Flush RunReport to JSONL
        if settings.run_log_dir:
            ts = datetime.now(timezone.utc)
            log_path = (
                Path(settings.run_log_dir)
                / "fx"
                / "fact_vol"
                / f"fx_vol_citi_historical_{ts:%Y%m%d_%H%M%S}.jsonl"
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
