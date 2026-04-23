"""Rates Citi Velocity Hourly Intraday Runner.

Target table: [rates].[fact_observation]  (frequency_id = HOURLY)
Schedule:     Hourly (via scripts.imdr_hourly)
Source:       Citi Velocity Historical Data API, HOURLY frequency

Uses the PRIMARY Citi OAuth credentials — the secondary `hourly` key is
FX-entitlement-only and returns "User is not entitled to this data" for
RATES.* tags. Budget impact against the shared 95K bucket: G4 RFR par =
176 tags/call × 24 runs/day = ~4,224 tags/day (~4.5% of the daily budget).

Window strategy: each run pulls the full current-day window (00:00 → 23:59 UTC)
at HOURLY frequency. Citi's API returns empty bodies for narrow sub-hour
windows, and the uq_rates_fact_obs constraint (includes frequency_id) makes
the MERGE upsert idempotent — re-fetching earlier hours is a no-op on
already-loaded rows and catches any late-arriving datapoints.

Covers G4 RFR par curves: USD SOFR, EUR EUROSTR, GBP SONIA, JPY TONAR.

Note on publish cadence: each RFR starts showing hourly datapoints when its
home market opens — JPY TONAR from ~00:00 UTC, EUR EUROSTR from ~06:00 UTC,
GBP SONIA from ~07:00 UTC (BST) / ~08:00 UTC (GMT), USD SOFR from ~00:00 UTC.
Early-morning UTC runs will return partial coverage; this is expected and
the MERGE upsert (natural key includes frequency_id) fills in hours as the
day progresses. PAR quotes on active curves are protected from empty-combo
caching (see src/imdr/domains/rates/cache.py:_PROTECTED_QUOTES).

Usage:
    python -m scripts.rates.citi.rates_citi_live_hourly
    python -m scripts.rates.citi.rates_citi_live_hourly --date 2026-04-23
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone

import structlog

from imdr.config.settings import get_settings
from imdr.connectors.citi_helpers import TagQuotaExceeded
from imdr.connectors.mssql import MSSQLConnector
from imdr.domains.rates.pipeline import RatesHistoricalPipeline
from imdr.universe.rates import get_rates_universe
from imdr.utils.logging import configure_logging

log = structlog.get_logger(__name__)

# G4 RFR par curves — conservative intraday scope, ~176 tags/call.
DEFAULT_CURVES: list[tuple[str, str]] = [
    ("USD", "SOFR"),
    ("EUR", "EUROSTR"),
    ("GBP", "SONIA"),
    ("JPY", "TONAR"),
]

DEFAULT_QUOTES = ["par"]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Rates Citi Velocity Hourly Intraday Ingest")
    p.add_argument(
        "--date",
        default=None,
        help="Override date (YYYY-MM-DD, UTC). Default: today UTC.",
    )
    p.add_argument(
        "--quotes",
        default=None,
        help="Comma-separated quote types. Default: par.",
    )
    p.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable empty-combo cache (retry all API calls).",
    )
    return p.parse_args()


def _target_window(date_arg: str | None) -> tuple[datetime, datetime]:
    """Full-day UTC window for the target date (defaults to today UTC).

    Citi returns empty responses for narrow sub-hour windows, so we always
    pull the whole day at HOURLY frequency and rely on MERGE idempotency.
    """
    if date_arg:
        day = datetime.strptime(date_arg, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    else:
        day = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    start = day
    end = day.replace(hour=23, minute=59)
    return start, end


def main() -> int:
    args = parse_args()
    settings = get_settings()
    configure_logging(settings)

    start, end = _target_window(args.date)

    if args.quotes is not None:
        quotes = [q.strip() for q in args.quotes.split(",")]
    else:
        quotes = DEFAULT_QUOTES

    log.info(
        "rates_citi_hourly_start",
        start=start.isoformat(),
        end=end.isoformat(),
        curves=len(DEFAULT_CURVES),
        quotes=quotes,
    )

    connector = MSSQLConnector(settings)
    try:
        t0 = time.perf_counter()
        pipeline = RatesHistoricalPipeline(
            connector=connector,
            settings=settings,
            universe=get_rates_universe(),
            start=start,
            end=end,
            quotes=quotes,
            frequency="HOURLY",
            curves=DEFAULT_CURVES,
            use_cache=not args.no_cache,
            chunk_size=settings.bulk_batch_size,
        )
        rows = pipeline.run()
        elapsed = time.perf_counter() - t0

        log.info(
            "rates_citi_hourly_complete",
            rows=rows,
            extraction_errors=len(pipeline._extraction_errors),
            quota_used=pipeline._quota_usage,
            elapsed=f"{elapsed:.1f}s",
        )
        return 0

    except TagQuotaExceeded as e:
        log.error(
            "rates_citi_hourly_tag_quota_exceeded",
            current_usage=getattr(e, "current_usage", None),
            available=getattr(e, "available", None),
        )
        return 1
    except Exception:
        log.exception("rates_citi_hourly_failed")
        return 1
    finally:
        connector.dispose()


if __name__ == "__main__":
    sys.exit(main())
