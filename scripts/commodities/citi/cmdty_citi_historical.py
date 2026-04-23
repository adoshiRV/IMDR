"""Commodities Citi Velocity Historical Backfiller.

Supports all three sub-products: SPOT, EIA, IMPLIED_VOL.
Modes: range, catchup, gaps.

Edit the variables below and run:
    python -m scripts.commodities.citi.cmdty_citi_historical
"""
from __future__ import annotations

import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import structlog

from imdr.config.settings import get_settings
from imdr.connectors.mssql import MSSQLConnector
from imdr.market_calendar.calendar import last_business_day
from imdr.reporting.run_report import RunReport
from imdr.universe.commodities import get_commodities_universe
from imdr.utils.logging import configure_logging

log = structlog.get_logger(__name__)

# ============================================================================
# CONFIGURE HERE
# ============================================================================

MODE = "range"  # "range" | "catchup" | "gaps"
PRODUCT = "vol"  # "spot" | "eia" | "vol"

# range: start and end dates (YYYY-MM-DD)
START = "2026-04-01"
END = "2026-04-13"

# catchup: how many calendar days back from today
LOOKBACK_DAYS = 30

# gaps: path to a text file with one YYYY-MM-DD date per line
GAPS_FILE = "data/gaps/cmdty_gaps.txt"

# 0 = unlimited (for gaps mode, limits number of dates processed)
MAX_DAYS = 0

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


def _build_pipeline(product: str, connector, settings, universe, start, end, chunk_size=None):
    """Build the appropriate pipeline for the given product."""
    if product == "spot":
        from imdr.domains.commodities.pipeline_spot import CmdtySpotPipeline
        return CmdtySpotPipeline(
            connector=connector, settings=settings,
            universe=universe, start=start, end=end,
        )
    elif product == "eia":
        from imdr.domains.commodities.pipeline_eia import CmdtyEIAPipeline
        return CmdtyEIAPipeline(
            connector=connector, settings=settings,
            universe=universe, start=start, end=end,
        )
    elif product == "vol":
        from imdr.domains.commodities.pipeline_vol import CmdtyImpliedVolPipeline
        return CmdtyImpliedVolPipeline(
            connector=connector, settings=settings,
            universe=universe, start=start, end=end,
            chunk_size=chunk_size,
        )
    else:
        raise ValueError(f"Unknown product: {product}")


def _run_pipeline(connector, settings, universe, start, end, label, chunk_size=None):
    log.info("processing", label=label, start=str(start.date()), end=str(end.date()))
    pipeline = _build_pipeline(PRODUCT, connector, settings, universe, start, end, chunk_size)
    rows = pipeline.run()
    quality = getattr(pipeline, "_quality_results", [])
    return rows, quality


def main() -> int:
    settings = get_settings()
    configure_logging(settings)
    universe = get_commodities_universe()
    connector = MSSQLConnector(settings)
    report = RunReport(pipeline_name=f"commodities.{PRODUCT}_citi_historical")

    log.info("historical_start", mode=MODE, product=PRODUCT)

    try:
        t0 = time.perf_counter()
        total_rows = 0
        all_quality: list[dict] = []
        start: datetime | None = None
        end: datetime | None = None

        if MODE == "range":
            start = datetime.strptime(START, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            end = datetime.strptime(END, "%Y-%m-%d").replace(
                hour=23, minute=59, tzinfo=timezone.utc,
            )
            start, end = _skip_weekends(start, end)
            total_rows, all_quality = _run_pipeline(
                connector, settings, universe, start, end,
                label=f"range {START}\u2192{END}",
                chunk_size=settings.bulk_batch_size,
            )

        elif MODE == "catchup":
            end = last_business_day("US").replace(hour=23, minute=59, second=0, microsecond=0)
            start = (end - timedelta(days=LOOKBACK_DAYS)).replace(hour=0, minute=0, second=0, microsecond=0)
            start, end = _skip_weekends(start, end)
            total_rows, all_quality = _run_pipeline(
                connector, settings, universe, start, end,
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
            start = dates[0] if dates else None
            end = dates[-1] if dates else None

            for i, dt in enumerate(dates):
                try:
                    rows, qr = _run_pipeline(
                        connector, settings, universe,
                        start=dt,
                        end=dt.replace(hour=23, minute=59),
                        label=f"gap {i + 1}/{len(dates)} ({dt.date()})",
                        chunk_size=settings.bulk_batch_size,
                    )
                    total_rows += rows
                    all_quality.extend(qr)
                except Exception:
                    log.exception("gap_date_failed", date=str(dt.date()))
                    report.error("gap", f"Failed for {dt.date()}")

        else:
            print(f"ERROR: Unknown MODE '{MODE}'. Use: range, catchup, gaps")
            return 1

        elapsed = time.perf_counter() - t0

        report.info("pipeline", f"Historical complete: {total_rows} rows", details={
            "mode": MODE,
            "product": PRODUCT,
            "total_rows": total_rows,
            "elapsed_secs": round(elapsed, 1),
        })

        report.finish()

        if settings.run_log_dir:
            ts = datetime.now(timezone.utc)
            log_path = (
                Path(settings.run_log_dir)
                / "commodities"
                / f"fact_{PRODUCT if PRODUCT != 'vol' else 'implied_vol'}"
                / f"cmdty_{PRODUCT}_citi_historical_{ts:%Y%m%d_%H%M%S}.jsonl"
            )
            report.flush_jsonl(log_path)

        log.info("historical_complete", mode=MODE, product=PRODUCT,
                 total_rows=total_rows, elapsed=f"{elapsed:.1f}s")
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
