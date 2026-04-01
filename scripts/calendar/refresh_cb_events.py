"""Monthly CB events refresh — Bloomberg import + scrape/validate + upsert.

Combines:
1. Bloomberg Excel import (existing load_and_normalize)
2. Web scrapers for Asia EM central banks (PBOC, RBI, CBC, BSP, MAS)
3. Validation report comparing both sources
4. Merged upsert with provenance tracking (source, is_estimated)

Usage:
    python -m scripts.calendar.refresh_cb_events --bloomberg-file "path.xlsx"
    python -m scripts.calendar.refresh_cb_events --bloomberg-file "path.xlsx" --dry-run
    python -m scripts.calendar.refresh_cb_events --scrape-only --year 2026
    python -m scripts.calendar.refresh_cb_events --scrape-only --year 2026 --dry-run
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import structlog
from sqlalchemy import text
from sqlalchemy.orm import Session

from imdr.config.settings import get_settings
from imdr.connectors.mssql import MSSQLConnector
from imdr.market_calendar.cb_scrapers import scrape_all
from imdr.utils.logging import configure_logging

log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Validation report
# ---------------------------------------------------------------------------

def _build_validation_report(
    bloomberg_events: list[dict],
    scraped_events: list[dict],
) -> list[dict]:
    """Compare Bloomberg vs scraped events, return report rows."""
    report = []

    # Index Bloomberg by (country, date)
    bbg_by_key: dict[tuple, dict] = {}
    for e in bloomberg_events:
        key = (e["country_code"], e["event_date"])
        bbg_by_key[key] = e

    matched_bbg_keys: set[tuple] = set()

    for se in scraped_events:
        key = (se["country_code"], se["event_date"])
        exact = bbg_by_key.get(key)

        if exact:
            matched_bbg_keys.add(key)
            report.append({
                "country": se["country_code"],
                "date": se["event_date"],
                "event": se["event_name"],
                "status": "MATCH",
                "detail": f"Bloomberg: {exact['event_name']}",
            })
            continue

        # Check +-3 day window for date mismatch
        near = None
        for delta in range(-3, 4):
            if delta == 0:
                continue
            nearby_key = (se["country_code"], se["event_date"] + timedelta(days=delta))
            if nearby_key in bbg_by_key:
                near = (nearby_key, bbg_by_key[nearby_key])
                matched_bbg_keys.add(nearby_key)
                break

        if near:
            nk, ne = near
            report.append({
                "country": se["country_code"],
                "date": se["event_date"],
                "event": se["event_name"],
                "status": "DATE_MISMATCH",
                "detail": f"Bloomberg has {ne['event_date']} ({ne['event_name']})",
            })
        else:
            report.append({
                "country": se["country_code"],
                "date": se["event_date"],
                "event": se["event_name"],
                "status": "SCRAPED_ONLY",
                "detail": "Not in Bloomberg",
            })

    # Bloomberg-only events for the same countries
    scraped_countries = {e["country_code"] for e in scraped_events}
    for key, be in bbg_by_key.items():
        if key not in matched_bbg_keys and be["country_code"] in scraped_countries:
            report.append({
                "country": be["country_code"],
                "date": be["event_date"],
                "event": be["event_name"],
                "status": "BLOOMBERG_ONLY",
                "detail": "Not in scraped sources",
            })

    report.sort(key=lambda r: (r["country"], r["date"]))
    return report


def _print_report(report: list[dict]) -> None:
    """Print tabular validation report."""
    if not report:
        print("\n  No events to compare.\n")
        return

    print(f"\n{'='*80}")
    print(f"  {'Country':<8} {'Date':<12} {'Event':<40} {'Status':<16}")
    print(f"{'='*80}")
    for r in report:
        d = r["date"].isoformat() if isinstance(r["date"], date) else str(r["date"])
        evt = r["event"][:38]
        print(f"  {r['country']:<8} {d:<12} {evt:<40} {r['status']:<16}")
        if r["status"] != "MATCH":
            print(f"  {'':>8} {'':>12} -> {r['detail']}")
    print(f"{'='*80}")

    counts = {}
    for r in report:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    print(f"  Summary: {counts}")
    print()


# ---------------------------------------------------------------------------
# Upsert with provenance
# ---------------------------------------------------------------------------

def _upsert_scraped_events(session: Session, events: list[dict], dry_run: bool) -> int:
    """Upsert scraped/generated CB events with source tracking."""
    added = 0
    for e in events:
        dt = str(e["event_date"])
        country = e["country_code"]
        name = e["event_name"]
        ticker = e.get("ticker")
        category = e.get("category", "Central Banks")
        relevance = e.get("relevance")
        source = e.get("source", "unknown")
        is_estimated = 1 if e.get("is_estimated") else 0

        if dry_run:
            est_tag = " (estimated)" if is_estimated else ""
            print(f"  [DRY] {country} {dt}: {name}{est_tag} [{source}]")
            added += 1
            continue

        if ticker:
            result = session.execute(
                text("""
                    IF NOT EXISTS (
                        SELECT 1 FROM [calendar].[cb_events]
                        WHERE event_date = :dt AND country_code = :country
                          AND ticker = :ticker
                    )
                    INSERT INTO [calendar].[cb_events]
                        (event_date, country_code, category, event_name,
                         ticker, relevance, source, is_estimated)
                    VALUES (:dt, :country, :category, :name,
                            :ticker, :relevance, :source, :is_estimated)
                    ELSE
                    UPDATE [calendar].[cb_events]
                    SET source = COALESCE(:source, source),
                        is_estimated = :is_estimated,
                        updated_at = SYSDATETIMEOFFSET()
                    WHERE event_date = :dt AND country_code = :country
                      AND ticker = :ticker
                      AND (source IS NULL OR source = 'estimated')
                """),
                {"dt": dt, "country": country, "category": category,
                 "name": name, "ticker": ticker, "relevance": relevance,
                 "source": source, "is_estimated": is_estimated},
            )
        else:
            result = session.execute(
                text("""
                    IF NOT EXISTS (
                        SELECT 1 FROM [calendar].[cb_events]
                        WHERE event_date = :dt AND country_code = :country
                          AND event_name = :name
                    )
                    INSERT INTO [calendar].[cb_events]
                        (event_date, country_code, category, event_name,
                         relevance, source, is_estimated)
                    VALUES (:dt, :country, :category, :name,
                            :relevance, :source, :is_estimated)
                    ELSE
                    UPDATE [calendar].[cb_events]
                    SET source = COALESCE(:source, source),
                        is_estimated = :is_estimated,
                        updated_at = SYSDATETIMEOFFSET()
                    WHERE event_date = :dt AND country_code = :country
                      AND event_name = :name
                      AND (source IS NULL OR source = 'estimated')
                """),
                {"dt": dt, "country": country, "category": category,
                 "name": name, "relevance": relevance,
                 "source": source, "is_estimated": is_estimated},
            )
        added += result.rowcount

    if not dry_run:
        session.commit()
    return added


# ---------------------------------------------------------------------------
# Bloomberg loader (wraps existing import_cb_events)
# ---------------------------------------------------------------------------

def _load_bloomberg(file_path: Path) -> list[dict]:
    """Load Bloomberg Excel and convert to event dicts."""
    # Import here to avoid circular dependency
    from scripts.calendar.import_cb_events import (
        filter_date_window,
        load_and_normalize,
    )

    df = load_and_normalize(file_path)
    # Use wide window — 12 months forward
    df = filter_date_window(df, months_back=1, months_forward=12)

    events = []
    for _, row in df.iterrows():
        import pandas as pd

        ticker = row.get("ticker")
        if pd.isna(ticker):
            ticker = None

        events.append({
            "country_code": str(row.get("country_code", "XX")),
            "event_date": row["event_date"],
            "event_name": str(row.get("event_name", "")),
            "ticker": str(ticker) if ticker else None,
            "category": str(row.get("category", "Unknown")),
            "relevance": float(row["relevance"]) if pd.notna(row.get("relevance")) else None,
            "source": "bloomberg",
            "is_estimated": False,
        })

    log.info("bloomberg_loaded", count=len(events))
    return events


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Monthly CB events refresh — Bloomberg + scrape + validate",
    )
    parser.add_argument("--bloomberg-file", type=str, help="Path to Bloomberg Excel file")
    parser.add_argument("--scrape-only", action="store_true", help="Skip Bloomberg, scrape only")
    parser.add_argument("--year", type=int, default=date.today().year, help="Target year for scrapers")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.bloomberg_file and not args.scrape_only:
        parser.error("Provide --bloomberg-file or --scrape-only")

    settings = get_settings()
    configure_logging(settings)

    t0 = time.perf_counter()

    # Step 1: Load Bloomberg (if provided)
    bbg_events: list[dict] = []
    if args.bloomberg_file:
        path = Path(args.bloomberg_file)
        if not path.exists():
            log.error("bloomberg_file_not_found", path=str(path))
            return 1
        bbg_events = _load_bloomberg(path)

    # Step 2: Scrape/generate Asia EM events
    scraped_events = scrape_all(args.year)

    # Step 3: Validation report
    if bbg_events and scraped_events:
        print("\n=== Validation Report: Bloomberg vs Scraped ===")
        report = _build_validation_report(bbg_events, scraped_events)
        _print_report(report)
    elif scraped_events:
        print(f"\n=== Scraped {len(scraped_events)} events (no Bloomberg file) ===")

    # Step 4: Upsert
    if args.dry_run:
        print("=== DRY RUN ===\n")
        if bbg_events:
            print(f"Bloomberg events: {len(bbg_events)} (would use existing import path)")
        print(f"\nScraped events:")
        _upsert_scraped_events(None, scraped_events, dry_run=True)
        print(f"\nTotal scraped: {len(scraped_events)}")
        return 0

    connector = MSSQLConnector(settings)
    try:
        with Session(connector.engine) as session:
            # Upsert Bloomberg via existing importer
            bbg_count = 0
            if bbg_events and args.bloomberg_file:
                from scripts.calendar.import_cb_events import (
                    load_and_normalize,
                    filter_date_window,
                    upsert_events,
                )

                df = load_and_normalize(Path(args.bloomberg_file))
                df = filter_date_window(df, months_back=1, months_forward=12)
                bbg_count = upsert_events(session, df)

            # Upsert scraped events
            scraped_count = _upsert_scraped_events(session, scraped_events, dry_run=False)

        elapsed = time.perf_counter() - t0
        log.info(
            "refresh_complete",
            bloomberg=bbg_count, scraped=scraped_count,
            elapsed=f"{elapsed:.1f}s",
        )
        print(f"Done: {bbg_count} Bloomberg + {scraped_count} scraped ({elapsed:.1f}s)")
        return 0

    except Exception:
        log.exception("refresh_failed")
        return 1
    finally:
        connector.dispose()


if __name__ == "__main__":
    sys.exit(main())
