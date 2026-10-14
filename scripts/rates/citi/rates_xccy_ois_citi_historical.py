"""G10 Cross-Currency OIS Basis — Citi Velocity Historical Backfiller.

Target table: [rates].[fact_observation]  (quote='basis')
Source: Citi Velocity Historical Data API (OAuth2)

Curves: 90 directional G10 pairs (10 currencies x 9 counterparts) under
RATES.XCCY_OIS_SWAP.{CCY1}.{CCY2}.SPOT — BASE_LEG only. See
docs/admin/vendors/citi/exploration/rates_xccy_ois.md for the full tag
format and sample data.

DO NOT re-run the full 2010-> range: Citi hard-caps each (OAuth client,
tag) pair at 10 calls per rolling 24h, independent of the overall tag
quota budget. CHUNK_MONTHS=12 over a 16-year range is 17 calls/tag —
7 past the cap. The 08-Oct-2026 backfill hit this at chunk 11 (all
curves zero-rowed from 2020 onward) and needed a second pass on the
non-hourly client, scoped to 2019-12-30 -> today (7 chunks), to fill
the gap. Data is loaded through 2026-10-08; only re-run for a narrow
date range, and prefer the non-hourly client if the hourly one has
touched these tags in the last 24h.

Edit the variables below and run:
    python -m scripts.rates.citi.rates_xccy_ois_citi_historical
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

# Memory shows some Citi G10 curves (e.g. GBP SONIA OIS) serve back to
# 2010-11, further than the naive 2015 floor — let empty periods return
# gracefully rather than assume a true start date.
START = "2010-01-01"
END = "2026-10-08"

# Quote types — basis is the only quote supported by xccy_ois_swap instrument.
QUOTES = ["basis"]

FREQUENCY = "DAILY"

# Chunk a long range into N-month windows to keep per-request response sizes
# tractable and give clearer progress logs / resumability on transient failures.
CHUNK_MONTHS = 12

MERGE_BATCH_SIZE = 2500

# Route through the dedicated hourly Citi OAuth client + tag-quota bucket so a
# multi-chunk backfill doesn't eat into the daily pipelines' per-tag 10/24h cap.
USE_HOURLY_CREDS = True
HOURLY_QUOTA_FILE = "data/cache/citi_tag_quota_hourly.json"

# ============================================================================


def _xccy_ois_curves(universe) -> list[tuple[str, str]]:
    """All (ccy, curve) tuples wired under the xccy_ois_swap instrument."""
    return [
        (c.ccy, c.curve)
        for c in universe.all_curves()
        if c.providers.get("citi", {}).get("instrument") == "xccy_ois_swap"
    ]


def main() -> int:
    settings = get_settings()
    configure_logging(settings)

    universe = get_rates_universe()
    curves = _xccy_ois_curves(universe)
    if not curves:
        log.error("no_xccy_ois_curves_in_universe")
        return 1

    log.info("xccy_ois_historical_start",
             n_curves=len(curves),
             range=f"{START} -> {END}", quotes=QUOTES)

    connector = MSSQLConnector(settings)
    report = RunReport(pipeline_name="rates.xccy_ois_citi_historical")

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
            "n_curves": len(curves),
            "range": [START, END],
            "rows": total_rows,
            "elapsed_secs": round(elapsed, 1),
        })
        report.finish()

        if settings.run_log_dir:
            ts = datetime.now(timezone.utc)
            log_path = (
                Path(settings.run_log_dir) / "rates" / "fact_observation"
                / f"rates_xccy_ois_citi_historical_{ts:%Y%m%d_%H%M%S}.jsonl"
            )
            report.flush_jsonl(log_path)

        log.info("xccy_ois_historical_complete",
                 rows=total_rows, elapsed=f"{elapsed:.1f}s")
        return 0

    except Exception:
        log.exception("xccy_ois_historical_failed")
        report.error("pipeline", "XCCY OIS basis backfill failed")
        report.finish()
        return 1
    finally:
        connector.dispose()


if __name__ == "__main__":
    sys.exit(main())
