"""Daily Bloomberg BQL economic-calendar refresh.

Reads the upstream BQL SQLite database (``BQL.EconData.DB`` on the STIRT
dashboard share, refreshed ~daily) and idempotently upserts it into
``calendar.cb_events`` under the BBG vendor lane. Sibling of
``scripts.calendar.te_calendar_refresh``; together BQL + TE are the two
canonical event sources.

The upsert is idempotent on (vendor_id, event_date, country_id, event_name),
so re-runs naturally:
  - INSERT new events that appear in the file
  - UPDATE survey/actual/etc. as values fill in and get revised
  - leave unchanged events alone (apart from an updated_at touch)

Defaults to a rolling T-7 → T+21 window (the full history is backfilled once
via --all; daily, only recent actuals/revisions change). Pass --all to read the
whole file.

Usage
-----
    # Dry run — read + dedup + classify what would change, write nothing.
    python -m scripts.calendar.bql_calendar_refresh --dry-run

    # Live run — rolling T-7 → T+21 window (the daily default).
    python -m scripts.calendar.bql_calendar_refresh

    # Full reload of the entire file (initial backfill / periodic catch-up).
    python -m scripts.calendar.bql_calendar_refresh --all

    # Point at a different copy of the SQLite DB.
    python -m scripts.calendar.bql_calendar_refresh --db "path/to/BQL.EconData.DB"
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import structlog
from sqlalchemy.orm import Session

from imdr.config.settings import get_settings
from imdr.connectors.mssql import MSSQLConnector
from imdr.market_calendar.bql_econdata import DEFAULT_DB, default_window, refresh
from imdr.utils.logging import configure_logging

log = structlog.get_logger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Read + dedup + classify changes, but write nothing.",
    )
    parser.add_argument(
        "--db", type=Path, default=DEFAULT_DB,
        help=f"Path to the BQL SQLite DB (default: {DEFAULT_DB}).",
    )
    parser.add_argument(
        "--all", action="store_true", dest="load_all",
        help="Read the entire file (full backfill) instead of the rolling window.",
    )
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings)

    if not args.db.exists():
        log.error("bql.db_not_found", path=str(args.db))
        return 1

    d1, d2 = (None, None) if args.load_all else default_window()

    t0 = time.perf_counter()
    connector = MSSQLConnector(settings)
    try:
        with Session(connector.engine) as session:
            result = refresh(session, db_path=args.db, d1=d1, d2=d2, dry_run=args.dry_run)
    finally:
        connector.engine.dispose()
    elapsed = time.perf_counter() - t0

    print()
    print(f"=== BQL calendar refresh ({'DRY RUN' if args.dry_run else 'LIVE'}) ===")
    print(f"  db:                       {args.db}")
    print(f"  window:                   {'ALL' if args.load_all else f'{d1} -> {d2}'}")
    print(f"  elapsed:                  {elapsed:.2f}s")
    print(f"  deduped events:           {result.parsed}")
    print(f"  skipped unknown country:  {result.skipped_unknown_country}")
    print(f"  inserted:                 {result.inserted}")
    print(f"  updated (actual changed): {result.updated_actual}")
    print(f"  updated (other fields):   {result.updated_other}")
    print(f"  unchanged:                {result.unchanged}")
    print(f"  errored (row skipped):    {result.errored}")
    print()

    log.info(
        "bql.refresh_done",
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
