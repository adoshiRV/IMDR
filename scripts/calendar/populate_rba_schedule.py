"""Populate RBA Cash Rate Target meeting dates in calendar.cb_events.

Source: RBA published + projected monetary-policy meeting schedule
(user-provided, 2026-08-10).

The 2026 meetings (11-Aug → 8-Dec) are already carried by the Bloomberg / BQL /
TradingEconomics feeds, so this script only seeds the forward calendar the feeds
have not rolled to yet:

  - 2027 (8 meetings): RBA *published* schedule  -> is_estimated = 0 (hard),
    event_datetime set to the 14:30 Sydney announcement (AEST/AEDT -> UTC).
  - 2028 (5 meetings): *projected* schedule (RBA had not published 2028 as of
    the seed date) -> is_estimated = 1, source = 'estimated', no event_datetime
    so downstream digests treat the date as SOFT (see
    docs/admin/calendar/cb_events_refresh.md).

Rows are written with vendor_id = NULL (a manual seed). The cb_events unique
keys are per-vendor (UX_cb_events_vendor_date_country_event), so these coexist
with the Bloomberg (vendor 4) / TE (vendor 73) rows that will eventually cover
the same dates. The IF NOT EXISTS guard keys on (event_date, country_id,
event_name) across ALL vendors, so re-running is idempotent AND a manual row is
not added once any feed already carries that meeting.

Idempotent — safe to re-run.

Usage:
    python -m scripts.calendar.populate_rba_schedule --dry-run
    python -m scripts.calendar.populate_rba_schedule
"""

from __future__ import annotations

import argparse
import sys
import time

import structlog
from sqlalchemy import text
from sqlalchemy.orm import Session

from imdr.config.settings import get_settings
from imdr.connectors.mssql import MSSQLConnector
from imdr.utils.logging import configure_logging

log = structlog.get_logger(__name__)

COUNTRY_CODE = "AU"
EVENT_NAME = "RBA Cash Rate Target"
CATEGORY = "Central banks / speakers"
RELEVANCE = 100.0
SOURCE_KNOWN = "rba_published_schedule"
SOURCE_PROJECTED = "estimated"

# (event_date, event_datetime_utc | None, is_estimated)
# event_datetime = 14:30 Sydney -> UTC: AEDT (UTC+11) = 03:30Z, AEST (UTC+10) = 04:30Z.
# AU DST: ends first Sun April, starts first Sun October.
RBA_MEETINGS: list[tuple[str, str | None, bool]] = [
    # --- 2027: RBA published schedule (known / hard) ---
    ("2027-02-09", "2027-02-09 03:30:00 +00:00", False),  # AEDT
    ("2027-03-23", "2027-03-23 03:30:00 +00:00", False),  # AEDT (before 4 Apr)
    ("2027-05-04", "2027-05-04 04:30:00 +00:00", False),  # AEST
    ("2027-06-22", "2027-06-22 04:30:00 +00:00", False),  # AEST
    ("2027-08-10", "2027-08-10 04:30:00 +00:00", False),  # AEST
    ("2027-09-28", "2027-09-28 04:30:00 +00:00", False),  # AEST (before 3 Oct)
    ("2027-11-02", "2027-11-02 03:30:00 +00:00", False),  # AEDT (after 3 Oct)
    ("2027-12-14", "2027-12-14 03:30:00 +00:00", False),  # AEDT
    # --- 2028: projected (RBA not yet published; soft) ---
    ("2028-02-09", None, True),
    ("2028-03-22", None, True),
    ("2028-05-06", None, True),
    ("2028-06-14", None, True),
    ("2028-08-16", None, True),
]


def _resolve_country_id(session: Session, country_code: str) -> int:
    """Look up dbo.dim_country.id for a country_code; raise if unknown."""
    row = session.execute(
        text("SELECT id FROM [dbo].[dim_country] WHERE country_code = :cc"),
        {"cc": country_code.upper()},
    ).fetchone()
    if row is None:
        msg = f"country_code {country_code!r} not found in dbo.dim_country"
        raise ValueError(msg)
    return int(row[0])


def _upsert_rba_events(session: Session, dry_run: bool) -> int:
    """Insert missing RBA meetings, keyed on (event_date, country_id, event_name)."""
    added = 0
    country_id: int | None = None if dry_run else _resolve_country_id(session, COUNTRY_CODE)

    for event_date, event_dt, is_estimated in RBA_MEETINGS:
        source = SOURCE_PROJECTED if is_estimated else SOURCE_KNOWN
        if dry_run:
            tag = "projected" if is_estimated else "known"
            when = event_dt or "(date only)"
            print(f"  [DRY] INSERT {COUNTRY_CODE} {event_date} [{tag}] {EVENT_NAME} @ {when}")
            added += 1
            continue

        result = session.execute(
            text("""
                IF NOT EXISTS (
                    SELECT 1 FROM [calendar].[cb_events]
                    WHERE event_date = :dt AND country_id = :country_id
                      AND event_name = :name
                )
                INSERT INTO [calendar].[cb_events]
                    (event_date, event_datetime, country_id, category,
                     event_name, relevance, is_estimated, source)
                VALUES
                    (:dt, :event_dt, :country_id, :category,
                     :name, :relevance, :is_estimated, :source)
            """),
            {
                "dt": event_date,
                "event_dt": event_dt,
                "country_id": country_id,
                "category": CATEGORY,
                "name": EVENT_NAME,
                "relevance": RELEVANCE,
                "is_estimated": 1 if is_estimated else 0,
                "source": source,
            },
        )
        added += result.rowcount
        log.info(
            "rba_event_upserted",
            date=event_date, is_estimated=is_estimated, rows=result.rowcount,
        )
    return added


def main() -> int:
    parser = argparse.ArgumentParser(description="Populate RBA meeting schedule (2027-2028)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings)

    if args.dry_run:
        print("=== DRY RUN — no DB writes ===\n")
        _upsert_rba_events(None, dry_run=True)
        print(f"\nTotal: {len(RBA_MEETINGS)} RBA meetings would be considered")
        return 0

    connector = MSSQLConnector(settings)
    t0 = time.perf_counter()
    try:
        with Session(connector.engine) as session:
            added = _upsert_rba_events(session, dry_run=False)
            session.commit()
        elapsed = time.perf_counter() - t0
        log.info("populate_complete", rba_events_added=added, elapsed=f"{elapsed:.1f}s")
        print(f"Done: {added} RBA meetings added ({elapsed:.1f}s)")
        return 0
    except Exception:
        log.exception("populate_failed")
        return 1
    finally:
        connector.dispose()


if __name__ == "__main__":
    sys.exit(main())
