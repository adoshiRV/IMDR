"""Daily TradingEconomics economic-calendar refresh.

Single polite GET to https://tradingeconomics.com/calendar, parse the
7-day forward window, and upsert into `calendar.cb_events` with vendor_id
pointing at the `tradingeconomics` row in dim_vendor (id=73 today).

Designed for once-a-day end-of-day runs. The upsert is idempotent on
(vendor_id, event_date, country_id, event_name), so re-runs naturally:
  - INSERT new events that appear in the window
  - UPDATE actuals/forecasts/consensus when they fill in post-release
  - leave unchanged events alone (apart from updated_at touch)

Usage
-----
    # Dry run — fetches the page, parses, classifies what would change,
    # writes nothing to the DB.
    python -m scripts.calendar.te_calendar_refresh --dry-run

    # Live run — fetch + parse + upsert.
    python -m scripts.calendar.te_calendar_refresh

    # Replay a saved HTML snapshot (offline testing, no network hit):
    python -m scripts.calendar.te_calendar_refresh --html-file path/to/te.html
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import date
from pathlib import Path

import structlog
from sqlalchemy.orm import Session

from imdr.config.settings import get_settings
from imdr.connectors.mssql import MSSQLConnector
from imdr.market_calendar.te_scraper import default_window, refresh
from imdr.utils.logging import configure_logging

log = structlog.get_logger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch + parse + classify changes, but write nothing.",
    )
    parser.add_argument(
        "--html-file",
        type=Path,
        default=None,
        help="Replay a saved /calendar HTML snapshot instead of hitting the site.",
    )
    parser.add_argument(
        "--d1",
        type=date.fromisoformat,
        default=None,
        help="Window start (YYYY-MM-DD). Defaults to today minus 7 days.",
    )
    parser.add_argument(
        "--d2",
        type=date.fromisoformat,
        default=None,
        help="Window end (YYYY-MM-DD). Defaults to today plus 21 days.",
    )
    args = parser.parse_args()

    # Default to rolling 4-week window unless overridden
    if args.html_file is None and args.d1 is None and args.d2 is None:
        args.d1, args.d2 = default_window()

    settings = get_settings()
    configure_logging(settings)

    html_override: str | None = None
    if args.html_file:
        if not args.html_file.exists():
            log.error("html_file_not_found", path=str(args.html_file))
            return 1
        html_override = args.html_file.read_text(encoding="utf-8")
        log.info("html_replay", path=str(args.html_file), bytes=len(html_override))

    t0 = time.perf_counter()

    connector = MSSQLConnector(settings)
    try:
        with Session(connector.engine) as session:
            result = refresh(
                session,
                d1=args.d1,
                d2=args.d2,
                dry_run=args.dry_run,
                html_override=html_override,
            )
    finally:
        connector.engine.dispose()

    elapsed = time.perf_counter() - t0

    print()
    print(f"=== TE calendar refresh ({'DRY RUN' if args.dry_run else 'LIVE'}) ===")
    if args.d1 and args.d2:
        print(f"  window:                   {args.d1} -> {args.d2} ({(args.d2 - args.d1).days + 1} days)")
    print(f"  elapsed:                  {elapsed:.2f}s")
    print(f"  parsed events:            {result.parsed}")
    print(f"  skipped unknown country:  {result.skipped_unknown_country}")
    print(f"  inserted:                 {result.inserted}")
    print(f"  updated (actual changed): {result.updated_actual}")
    print(f"  updated (other fields):   {result.updated_other}")
    print(f"  unchanged:                {result.unchanged}")
    print(f"  errored (row skipped):    {result.errored}")
    print()

    log.info(
        "te.refresh_done",
        dry_run=args.dry_run,
        elapsed=round(elapsed, 2),
        parsed=result.parsed,
        skipped_unknown_country=result.skipped_unknown_country,
        inserted=result.inserted,
        updated_actual=result.updated_actual,
        updated_other=result.updated_other,
        unchanged=result.unchanged,
        errored=result.errored,
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
