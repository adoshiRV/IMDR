"""Rates Citi Velocity Hourly Intraday Runner.

Target table: [rates].[fact_observation]  (frequency_id = HOURLY)
Schedule:     Hourly (via scripts.imdr_hourly)
Source:       Citi Velocity Historical Data API, HOURLY frequency

Uses the dedicated hourly Citi OAuth credentials (IMDR_CITI_HOURLY_CLIENT_*)
and a separate tag-quota file so intraday pulls don't eat into the daily
pipelines' shared 95K budget on the primary key. Each OAuth client has its
own Citi-side 100K/24h rolling bucket; G4 RFR par = 176 tags/call × 24
runs/day = ~4,224 tags/day — well under the hourly key's limit.

Window strategy: each run pulls the full current-day window (00:00 → 23:59 UTC)
at HOURLY frequency. Citi's API returns empty bodies for narrow sub-hour
windows, and the uq_rates_fact_obs constraint (includes frequency_id) makes
the MERGE upsert idempotent — re-fetching earlier hours is a no-op on
already-loaded rows and catches any late-arriving datapoints.

Covers all 12 active RFR curves:
  G10:  USD SOFR, EUR EUROSTR, GBP SONIA, JPY TONAR, CHF SARON,
        AUD AONIA, CAD CORRA, NZD NZIONA, NOK NOWA, SEK STINA
  APAC: SGD SORA, THB THOR

Two quote types per curve:
  par: full tenor grid (44 tenors per curve)
  fwd: forward-starting rates (28 combos per curve)

Budget: 12 × (44+28) = 864 tags/call × 24 runs = ~20,736 tags/day
(~22% of the hourly OAuth client's 95K budget).

Note on publish cadence: each RFR starts showing hourly datapoints when its
home market opens — Asia first (JPY/SGD/THB/AUD/NZD from ~00:00 UTC),
Europe mid-morning (EUR ~06:00 UTC, GBP ~07:00 UTC BST / ~08:00 GMT),
Americas (USD SOFR / CAD CORRA from ~00:00 UTC via overnight trading).
Early-morning UTC runs return partial coverage; the MERGE upsert (natural
key includes frequency_id) fills in hours as the day progresses. PAR quotes
on active curves are protected from empty-combo caching (see
src/imdr/domains/rates/cache.py:_PROTECTED_QUOTES). ROLL_CARRY (`rc`) is
not served at HOURLY frequency — Citi returns type=ERROR for it.

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
from imdr.market_calendar.calendar import is_trading_day
from imdr.universe.rates import get_rates_universe
from imdr.utils.logging import configure_logging

log = structlog.get_logger(__name__)

# All 12 active RFR curves (G10 + APAC Asia). Full tenor grid + forwards.
DEFAULT_CURVES: list[tuple[str, str]] = [
    # G10
    ("USD", "SOFR"),
    ("EUR", "EUROSTR"),
    ("GBP", "SONIA"),
    ("JPY", "TONAR"),
    ("CHF", "SARON"),
    ("AUD", "AONIA"),
    ("CAD", "CORRA"),
    ("NZD", "NZIONA"),
    ("NOK", "NOWA"),
    ("SEK", "STINA"),
    # APAC
    ("SGD", "SORA"),
    ("THB", "THOR"),
]

DEFAULT_QUOTES = ["par", "fwd"]

# Separate quota file from the daily pipeline — different OAuth client =
# different Citi-side rolling 24h bucket.
HOURLY_QUOTA_FILE = "data/cache/citi_tag_quota_hourly.json"

# Anchor market codes (from src/imdr/market_calendar/markets.yml) checked for
# "all closed" skip — weekends + universal holidays (New Year's, Christmas).
# If all four are non-trading, no meaningful rates data will publish that day.
# Good Friday only closes US/UK/EU (JP still trades), so the run still fires.
_ANCHOR_MARKETS = ["US", "EU", "UK", "JP"]


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
        "--use-cache",
        action="store_true",
        help="Enable empty-combo cache (disabled by default for hourly — "
             "2-day stale window is too long for 24-runs-per-day cadence, "
             "and the hourly runner would pollute the shared cache used "
             "by the daily pipeline).",
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

    if not settings.citi_hourly_client_id or not settings.citi_hourly_client_secret:
        log.error("hourly_creds_missing",
                  msg="IMDR_CITI_HOURLY_CLIENT_ID/SECRET not set in .env")
        return 2

    start, end = _target_window(args.date)

    # Skip if every anchor rates market is non-trading (weekend or holiday).
    # Uses the project's canonical calendar — weekends from markets.yml +
    # holidays via the `holidays` library, same source as dim_trading_day.
    day = start.date()
    closed = [m for m in _ANCHOR_MARKETS if not is_trading_day(m, day)]
    if len(closed) == len(_ANCHOR_MARKETS):
        log.info("all_anchor_markets_closed_skip",
                 date=day.isoformat(),
                 weekday=start.strftime("%A"),
                 closed_markets=closed)
        return 0

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
            use_cache=args.use_cache,
            chunk_size=settings.bulk_batch_size,
            client_id=settings.citi_hourly_client_id,
            client_secret=settings.citi_hourly_client_secret,
            quota_tracker_path=HOURLY_QUOTA_FILE,
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
