"""Populate Asia EM calendar gaps for 2026.

Source: imdr_asia_em_calendar_2026.xlsx audit (2026-03-24).

Part 1 — calendar.market_holidays (vendor=MANUAL):
  - Fix IN May 1 holiday name (Buddha Purnima → Maharashtra Day)
  - Add 4 missing IN holidays (is_custom=1)
  - Writes under the India rates calendar (calendar_code = 'RB')

Part 2 — cb_events:
  - CN PBOC LPR (12 monthly)
  - SG MAS Monetary Policy Statement (4 quarterly, Apr/Jul/Oct estimated)
  - TW CBC Quarterly Rate Decision (4 quarterly, confirmed)
  - PH BSP Overnight Reverse Repurchase Rate (6 meetings, confirmed)
  - IN RBI Repurchase Rate (4 missing bimonthly, confirmed)

Migrated 2026-05-13 (Phase D Step 9): Part 1 used to write to the legacy
``calendar.dim_trading_day`` table, which is scheduled for removal. The new
target is ``calendar.market_holidays`` keyed by ``(calendar_id, vendor_id,
holiday_date)``. Custom overrides go in under the MANUAL vendor with
``is_custom=1`` so they coexist with BBG-sourced holidays for the same
calendar without conflicting on the unique key.

Idempotent — safe to re-run.

Usage:
    python -m scripts.calendar.populate_asia_em_2026
    python -m scripts.calendar.populate_asia_em_2026 --dry-run
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

# ---------------------------------------------------------------------------
# Part 1: India holiday fixes
# ---------------------------------------------------------------------------

# Calendar code for India's rates calendar (RBI). Same code is used for the
# BBG-sourced rows in market_holidays; our MANUAL overrides land alongside.
_IN_CALENDAR_CODE = "RB"

HOLIDAY_NAME_FIXES = [
    # (calendar_code, date, old_name, new_name)
    (_IN_CALENDAR_CODE, "2026-05-01", "Buddha Purnima", "Maharashtra Day"),
]

MISSING_HOLIDAYS = [
    # (calendar_code, date, holiday_name)
    (_IN_CALENDAR_CODE, "2026-03-26", "Shri Ram Navami"),
    (_IN_CALENDAR_CODE, "2026-04-14", "Dr. Baba Saheb Ambedkar Jayanti"),
    (_IN_CALENDAR_CODE, "2026-09-14", "Ganesh Chaturthi"),
    (_IN_CALENDAR_CODE, "2026-11-10", "Diwali Balipratipada"),
]

# ---------------------------------------------------------------------------
# Part 2: CB events
# ---------------------------------------------------------------------------

CB_EVENTS = [
    # (country_code, event_date, event_name, ticker, category, relevance)
    # CN PBOC LPR — 12 monthly (~20th, shifted if weekend)
    ("CN", "2026-01-20", "PBOC 1Y/5Y Loan Prime Rate", None, "Central Banks", 95.0),
    ("CN", "2026-02-20", "PBOC 1Y/5Y Loan Prime Rate", None, "Central Banks", 95.0),
    ("CN", "2026-03-20", "PBOC 1Y/5Y Loan Prime Rate", None, "Central Banks", 95.0),
    ("CN", "2026-04-20", "PBOC 1Y/5Y Loan Prime Rate", None, "Central Banks", 95.0),
    ("CN", "2026-05-20", "PBOC 1Y/5Y Loan Prime Rate", None, "Central Banks", 95.0),
    ("CN", "2026-06-22", "PBOC 1Y/5Y Loan Prime Rate", None, "Central Banks", 95.0),
    ("CN", "2026-07-20", "PBOC 1Y/5Y Loan Prime Rate", None, "Central Banks", 95.0),
    ("CN", "2026-08-20", "PBOC 1Y/5Y Loan Prime Rate", None, "Central Banks", 95.0),
    ("CN", "2026-09-21", "PBOC 1Y/5Y Loan Prime Rate", None, "Central Banks", 95.0),
    ("CN", "2026-10-20", "PBOC 1Y/5Y Loan Prime Rate", None, "Central Banks", 95.0),
    ("CN", "2026-11-20", "PBOC 1Y/5Y Loan Prime Rate", None, "Central Banks", 95.0),
    ("CN", "2026-12-21", "PBOC 1Y/5Y Loan Prime Rate", None, "Central Banks", 95.0),
    # SG MAS — quarterly (Apr/Jul/Oct dates estimated)
    ("SG", "2026-01-29", "MAS Monetary Policy Statement", None, "Central Banks", 94.0),
    ("SG", "2026-04-14", "MAS Monetary Policy Statement", None, "Central Banks", 94.0),
    ("SG", "2026-07-14", "MAS Monetary Policy Statement", None, "Central Banks", 94.0),
    ("SG", "2026-10-14", "MAS Monetary Policy Statement", None, "Central Banks", 94.0),
    # TW CBC — quarterly (confirmed from CBC website)
    ("TW", "2026-03-19", "CBC Quarterly Rate Decision", None, "Central Banks", 93.0),
    ("TW", "2026-06-18", "CBC Quarterly Rate Decision", None, "Central Banks", 93.0),
    ("TW", "2026-09-17", "CBC Quarterly Rate Decision", None, "Central Banks", 93.0),
    ("TW", "2026-12-17", "CBC Quarterly Rate Decision", None, "Central Banks", 93.0),
    # PH BSP — 6 meetings (confirmed from BSP website)
    ("PH", "2026-02-19", "BSP Overnight Reverse Repurchase Rate", None, "Central Banks", 92.0),
    ("PH", "2026-04-23", "BSP Overnight Reverse Repurchase Rate", None, "Central Banks", 92.0),
    ("PH", "2026-06-18", "BSP Overnight Reverse Repurchase Rate", None, "Central Banks", 92.0),
    ("PH", "2026-08-27", "BSP Overnight Reverse Repurchase Rate", None, "Central Banks", 92.0),
    ("PH", "2026-10-22", "BSP Overnight Reverse Repurchase Rate", None, "Central Banks", 92.0),
    ("PH", "2026-12-17", "BSP Overnight Reverse Repurchase Rate", None, "Central Banks", 92.0),
    # IN RBI — 4 missing bimonthly (confirmed from RBI website)
    ("IN", "2026-06-05", "RBI Repurchase Rate", "INRPYLDP Index", "Unknown", 94.7),
    ("IN", "2026-08-05", "RBI Repurchase Rate", "INRPYLDP Index", "Unknown", 94.7),
    ("IN", "2026-10-07", "RBI Repurchase Rate", "INRPYLDP Index", "Unknown", 94.7),
    ("IN", "2026-12-04", "RBI Repurchase Rate", "INRPYLDP Index", "Unknown", 94.7),
]


def _resolve_calendar_id(session: Session, calendar_code: str) -> int:
    """Look up the dim_calendar.id for a calendar_code; raise if missing."""
    row = session.execute(
        text("SELECT id FROM calendar.dim_calendar WHERE calendar_code = :cc"),
        {"cc": calendar_code},
    ).fetchone()
    if row is None:
        msg = f"calendar_code {calendar_code!r} not found in calendar.dim_calendar"
        raise ValueError(msg)
    return int(row[0])


def _resolve_vendor_id(session: Session, vendor_code: str = "MANUAL") -> int:
    """Look up the dim_vendor.id for a vendor_code; raise if missing."""
    row = session.execute(
        text("SELECT id FROM dbo.dim_vendor WHERE vendor_code = :vc"),
        {"vc": vendor_code},
    ).fetchone()
    if row is None:
        msg = f"vendor_code {vendor_code!r} not found in dbo.dim_vendor"
        raise ValueError(msg)
    return int(row[0])


def _fix_holiday_names(session: Session, dry_run: bool) -> int:
    """Update mis-named holidays in calendar.market_holidays for the MANUAL vendor.

    Matches on (calendar_id, vendor=MANUAL, date, old_name). BBG-sourced rows
    (vendor=BBG) for the same calendar/date are left alone — vendor-specific
    naming differences are intentional and surface in `vendor_disagreements()`.
    """
    fixed = 0
    if not dry_run:
        manual_vendor_id = _resolve_vendor_id(session, "MANUAL")

    for cc, dt, old_name, new_name in HOLIDAY_NAME_FIXES:
        if dry_run:
            print(f"  [DRY] UPDATE calendar={cc} {dt}: '{old_name}' -> '{new_name}'")
            fixed += 1
            continue
        cal_id = _resolve_calendar_id(session, cc)
        result = session.execute(
            text("""
                UPDATE calendar.market_holidays
                SET holiday_name = :new_name, is_custom = 1,
                    updated_at = SYSDATETIMEOFFSET()
                WHERE calendar_id = :cal_id
                  AND vendor_id = :vendor_id
                  AND holiday_date = :dt
                  AND holiday_name = :old_name
            """),
            {
                "cal_id": cal_id, "vendor_id": manual_vendor_id,
                "dt": dt, "new_name": new_name, "old_name": old_name,
            },
        )
        fixed += result.rowcount
        log.info(
            "holiday_name_fixed",
            calendar_code=cc, date=dt, old=old_name, new=new_name,
            rows=result.rowcount,
        )
    return fixed


def _add_missing_holidays(session: Session, dry_run: bool) -> int:
    """Insert missing custom holidays into calendar.market_holidays under MANUAL vendor.

    Idempotent: skips dates where a MANUAL row already exists for the same
    (calendar_id, holiday_date). Does not deduplicate against BBG rows —
    different vendors disagreeing on a holiday is meaningful, not a conflict.
    """
    added = 0
    if not dry_run:
        manual_vendor_id = _resolve_vendor_id(session, "MANUAL")

    for cc, dt, name in MISSING_HOLIDAYS:
        if dry_run:
            print(f"  [DRY] INSERT holiday calendar={cc} {dt}: {name}")
            added += 1
            continue
        cal_id = _resolve_calendar_id(session, cc)
        result = session.execute(
            text("""
                MERGE calendar.market_holidays AS tgt
                USING (SELECT :cal_id AS calendar_id,
                              :vendor_id AS vendor_id,
                              :dt AS holiday_date) AS src
                    ON tgt.calendar_id = src.calendar_id
                   AND tgt.vendor_id = src.vendor_id
                   AND tgt.holiday_date = src.holiday_date
                WHEN NOT MATCHED THEN
                    INSERT (calendar_id, vendor_id, holiday_date,
                            holiday_name, is_custom, load_batch)
                    VALUES (:cal_id, :vendor_id, :dt, :name, 1,
                            'populate_asia_em_2026');
            """),
            {
                "cal_id": cal_id, "vendor_id": manual_vendor_id,
                "dt": dt, "name": name,
            },
        )
        added += result.rowcount
        log.info(
            "holiday_added",
            calendar_code=cc, date=dt, name=name, rows=result.rowcount,
        )
    return added


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


def _upsert_cb_events(session: Session, dry_run: bool) -> int:
    """Insert missing CB events into cb_events keyed on (event_date, country_id, …)."""
    added = 0
    country_id_cache: dict[str, int] = {}
    for country, dt, name, ticker, category, relevance in CB_EVENTS:
        if dry_run:
            print(f"  [DRY] INSERT cb_event {country} {dt}: {name}")
            added += 1
            continue

        # Resolve country_code → country_id once per code.
        if country not in country_id_cache:
            country_id_cache[country] = _resolve_country_id(session, country)
        country_id = country_id_cache[country]

        if ticker:
            # Unique key: (event_date, country_id, ticker)
            result = session.execute(
                text("""
                    IF NOT EXISTS (
                        SELECT 1 FROM [calendar].[cb_events]
                        WHERE event_date = :dt AND country_id = :country_id
                          AND ticker = :ticker
                    )
                    INSERT INTO [calendar].[cb_events]
                        (event_date, country_id, category, event_name,
                         ticker, relevance)
                    VALUES (:dt, :country_id, :category, :name, :ticker, :relevance)
                """),
                {"dt": dt, "country_id": country_id, "category": category,
                 "name": name, "ticker": ticker, "relevance": relevance},
            )
        else:
            # Unique key: (event_date, country_id, event_name)
            result = session.execute(
                text("""
                    IF NOT EXISTS (
                        SELECT 1 FROM [calendar].[cb_events]
                        WHERE event_date = :dt AND country_id = :country_id
                          AND event_name = :name
                    )
                    INSERT INTO [calendar].[cb_events]
                        (event_date, country_id, category, event_name,
                         relevance)
                    VALUES (:dt, :country_id, :category, :name, :relevance)
                """),
                {"dt": dt, "country_id": country_id, "category": category,
                 "name": name, "relevance": relevance},
            )
        added += result.rowcount
        log.info("cb_event_added", country=country, date=dt, event_name=name)
    return added


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Populate Asia EM calendar gaps for 2026"
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings)

    if args.dry_run:
        print("=== DRY RUN — no DB writes ===\n")
        print("Holiday name fixes:")
        _fix_holiday_names(None, dry_run=True)
        print("\nMissing holidays:")
        _add_missing_holidays(None, dry_run=True)
        print("\nCB events:")
        _upsert_cb_events(None, dry_run=True)
        total = (
            len(HOLIDAY_NAME_FIXES)
            + len(MISSING_HOLIDAYS)
            + len(CB_EVENTS)
        )
        print(f"\nTotal: {total} operations")
        return 0

    connector = MSSQLConnector(settings)
    t0 = time.perf_counter()

    try:
        with Session(connector.engine) as session:
            fixed = _fix_holiday_names(session, dry_run=False)
            added_hols = _add_missing_holidays(session, dry_run=False)
            session.commit()

            added_cb = _upsert_cb_events(session, dry_run=False)
            session.commit()

        elapsed = time.perf_counter() - t0
        log.info(
            "populate_complete",
            holiday_fixes=fixed,
            holidays_added=added_hols,
            cb_events_added=added_cb,
            elapsed=f"{elapsed:.1f}s",
        )
        print(
            f"Done: {fixed} name fixes, {added_hols} holidays added, "
            f"{added_cb} CB events added ({elapsed:.1f}s)"
        )
        return 0

    except Exception:
        log.exception("populate_failed")
        return 1
    finally:
        connector.dispose()


if __name__ == "__main__":
    sys.exit(main())
