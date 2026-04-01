"""Populate Asia EM calendar gaps for 2026.

Source: imdr_asia_em_calendar_2026.xlsx audit (2026-03-24).

Part 1 — dim_trading_day:
  - Fix IN May 1 holiday name (Buddha Purnima → Maharashtra Day)
  - Add 4 missing IN holidays (is_custom=1)

Part 2 — cb_events:
  - CN PBOC LPR (12 monthly)
  - SG MAS Monetary Policy Statement (4 quarterly, Apr/Jul/Oct estimated)
  - TW CBC Quarterly Rate Decision (4 quarterly, confirmed)
  - PH BSP Overnight Reverse Repurchase Rate (6 meetings, confirmed)
  - IN RBI Repurchase Rate (4 missing bimonthly, confirmed)

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

HOLIDAY_NAME_FIXES = [
    # (market_code, date, old_name, new_name)
    ("IN", "2026-05-01", "Buddha Purnima", "Maharashtra Day"),
]

MISSING_HOLIDAYS = [
    # (market_code, date, holiday_name)
    ("IN", "2026-03-26", "Shri Ram Navami"),
    ("IN", "2026-04-14", "Dr. Baba Saheb Ambedkar Jayanti"),
    ("IN", "2026-09-14", "Ganesh Chaturthi"),
    ("IN", "2026-11-10", "Diwali Balipratipada"),
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


def _fix_holiday_names(session: Session, dry_run: bool) -> int:
    """Update mis-named holidays in dim_trading_day."""
    fixed = 0
    for mc, dt, old_name, new_name in HOLIDAY_NAME_FIXES:
        if dry_run:
            print(f"  [DRY] UPDATE {mc} {dt}: '{old_name}' -> '{new_name}'")
            fixed += 1
            continue
        result = session.execute(
            text("""
                UPDATE [calendar].[dim_trading_day]
                SET holiday_name = :new_name, is_custom = 1
                WHERE market_code = :mc AND calendar_date = :dt
                  AND holiday_name = :old_name
            """),
            {"mc": mc, "dt": dt, "new_name": new_name, "old_name": old_name},
        )
        fixed += result.rowcount
        log.info("holiday_name_fixed", market=mc, date=dt, old=old_name, new=new_name)
    return fixed


def _add_missing_holidays(session: Session, dry_run: bool) -> int:
    """Insert missing custom holidays into dim_trading_day."""
    added = 0
    for mc, dt, name in MISSING_HOLIDAYS:
        if dry_run:
            print(f"  [DRY] INSERT holiday {mc} {dt}: {name}")
            added += 1
            continue
        result = session.execute(
            text("""
                MERGE [calendar].[dim_trading_day] AS tgt
                USING (SELECT :mc AS market_code, :dt AS calendar_date) AS src
                    ON tgt.market_code = src.market_code
                   AND tgt.calendar_date = src.calendar_date
                WHEN NOT MATCHED THEN
                    INSERT (market_code, calendar_date, is_weekend, is_holiday,
                            is_trading_day, holiday_name, is_custom)
                    VALUES (:mc, :dt, 0, 1, 0, :name, 1)
                WHEN MATCHED AND tgt.is_holiday = 0 THEN
                    UPDATE SET is_holiday = 1, is_trading_day = 0,
                               holiday_name = :name, is_custom = 1;
            """),
            {"mc": mc, "dt": dt, "name": name},
        )
        added += result.rowcount
        log.info("holiday_added", market=mc, date=dt, name=name)
    return added


def _upsert_cb_events(session: Session, dry_run: bool) -> int:
    """Insert missing CB events into cb_events."""
    added = 0
    for country, dt, name, ticker, category, relevance in CB_EVENTS:
        if dry_run:
            print(f"  [DRY] INSERT cb_event {country} {dt}: {name}")
            added += 1
            continue

        if ticker:
            # Unique key: (event_date, country_code, ticker)
            result = session.execute(
                text("""
                    IF NOT EXISTS (
                        SELECT 1 FROM [calendar].[cb_events]
                        WHERE event_date = :dt AND country_code = :country
                          AND ticker = :ticker
                    )
                    INSERT INTO [calendar].[cb_events]
                        (event_date, country_code, category, event_name,
                         ticker, relevance)
                    VALUES (:dt, :country, :category, :name, :ticker, :relevance)
                """),
                {"dt": dt, "country": country, "category": category,
                 "name": name, "ticker": ticker, "relevance": relevance},
            )
        else:
            # Unique key: (event_date, country_code, event_name)
            result = session.execute(
                text("""
                    IF NOT EXISTS (
                        SELECT 1 FROM [calendar].[cb_events]
                        WHERE event_date = :dt AND country_code = :country
                          AND event_name = :name
                    )
                    INSERT INTO [calendar].[cb_events]
                        (event_date, country_code, category, event_name,
                         relevance)
                    VALUES (:dt, :country, :category, :name, :relevance)
                """),
                {"dt": dt, "country": country, "category": category,
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
