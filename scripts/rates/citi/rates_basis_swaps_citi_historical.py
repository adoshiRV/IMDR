"""Tenor Basis Swaps — Citi Velocity Historical Backfiller.

Target table: [rates].[fact_observation]  (quote='basis')
Source: Citi Velocity Historical Data API (OAuth2)

Curves: USD/EUR/GBP/AUD 3s6s_basis (USD+GBP catalog ends 2025-02 post-LIBOR;
both wired as ``status: ceased`` so a backfill can capture their full history).

Edit the variables below and run:
    python -m scripts.rates.citi.rates_basis_swaps_citi_historical
"""
from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import structlog

from imdr.config.settings import get_settings
from imdr.connectors.mssql import MSSQLConnector
from imdr.domains.rates.pipeline import RatesHistoricalPipeline
from imdr.reporting.run_report import RunReport
from imdr.universe.rates import get_rates_universe
from imdr.utils.logging import configure_logging

log = structlog.get_logger(__name__)

# ============================================================================
# CONFIGURE HERE
# ============================================================================

# Full history range. USD/GBP data starts ~2015-01; EUR/AUD continue current.
START = "2015-01-01"
END = "2026-06-02"

# Quote types — basis is the only quote supported by basis_swaps instrument.
QUOTES = ["basis"]

FREQUENCY = "DAILY"

# Chunk a long range into N-month windows to keep per-request response sizes
# tractable. Citi handles a 10-yr × 20-tag pull in one shot, but chunking
# gives clearer progress logs and lets us resume on transient failures.
CHUNK_MONTHS = 12

MERGE_BATCH_SIZE = 2500

# Route through the dedicated hourly Citi OAuth client + tag-quota bucket so a
# multi-chunk backfill doesn't eat into the daily pipelines' per-tag 10/24h cap.
# Citi enforces the 10-call cap per (OAuth client, tag) — switching clients
# gives a fresh allowance.
USE_HOURLY_CREDS = True
HOURLY_QUOTA_FILE = "data/cache/citi_tag_quota_hourly.json"

# ============================================================================


def _basis_swap_curves(universe) -> list[tuple[str, str]]:
    """All (ccy, curve) tuples wired under the basis_swaps instrument."""
    return [
        (c.ccy, c.curve)
        for c in universe.all_curves()
        if c.providers.get("citi", {}).get("instrument") == "basis_swaps"
    ]


def main() -> int:
    settings = get_settings()
    configure_logging(settings)

    universe = get_rates_universe()
    curves = _basis_swap_curves(universe)
    if not curves:
        log.error("no_basis_swap_curves_in_universe")
        return 1

    log.info("basis_swaps_historical_start",
             curves=[f"{c}.{n}" for c, n in curves],
             range=f"{START} -> {END}", quotes=QUOTES)

    connector = MSSQLConnector(settings)
    report = RunReport(pipeline_name="rates.basis_swaps_citi_historical")

    try:
        start_dt = datetime.strptime(START, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        end_dt = datetime.strptime(END, "%Y-%m-%d").replace(
            hour=23, minute=59, tzinfo=timezone.utc,
        )

        # Chunk the range
        from datetime import timedelta
        step = timedelta(days=int(CHUNK_MONTHS * 30.4375))
        chunks: list[tuple[datetime, datetime]] = []
        cur = start_dt
        while cur <= end_dt:
            ce = min(cur + step - timedelta(days=1), end_dt).replace(hour=23, minute=59)
            chunks.append((cur, ce))
            cur = (ce + timedelta(minutes=1)).replace(
                hour=0, minute=0, second=0, microsecond=0,
            )

        total_rows = 0
        t0 = time.perf_counter()
        for i, (cs, ce) in enumerate(chunks, start=1):
            log.info("chunk_start", chunk=f"{i}/{len(chunks)}",
                     start=str(cs.date()), end=str(ce.date()))
            pipeline = RatesHistoricalPipeline(
                connector=connector,
                settings=settings,
                universe=universe,
                start=cs,
                end=ce,
                quotes=QUOTES,
                frequency=FREQUENCY,
                curves=curves,
                use_cache=False,
                chunk_size=MERGE_BATCH_SIZE,
                client_id=settings.citi_hourly_client_id if USE_HOURLY_CREDS else None,
                client_secret=settings.citi_hourly_client_secret if USE_HOURLY_CREDS else None,
                quota_tracker_path=HOURLY_QUOTA_FILE if USE_HOURLY_CREDS else None,
            )
            rows = pipeline.run()
            total_rows += rows
            log.info("chunk_done", chunk=f"{i}/{len(chunks)}", rows=rows, total=total_rows)

        elapsed = time.perf_counter() - t0
        report.info("pipeline", f"Backfill complete: {total_rows} rows", details={
            "curves": [f"{c}.{n}" for c, n in curves],
            "range": [START, END],
            "rows": total_rows,
            "elapsed_secs": round(elapsed, 1),
        })
        report.finish()

        if settings.run_log_dir:
            ts = datetime.now(timezone.utc)
            log_path = (
                Path(settings.run_log_dir) / "rates" / "fact_observation"
                / f"rates_basis_swaps_citi_historical_{ts:%Y%m%d_%H%M%S}.jsonl"
            )
            report.flush_jsonl(log_path)

        log.info("basis_swaps_historical_complete",
                 rows=total_rows, elapsed=f"{elapsed:.1f}s")
        return 0

    except Exception:
        log.exception("basis_swaps_historical_failed")
        report.error("pipeline", "Basis-swaps backfill failed")
        report.finish()
        return 1
    finally:
        connector.dispose()


if __name__ == "__main__":
    sys.exit(main())
