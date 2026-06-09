"""Load curated holiday calendars from the Bloomberg-sourced master spreadsheet
into ``calendar.market_holidays`` with ``vendor_id = BBG``.

The master file ("Calendar pasted.xlsx") has a single sheet ``master_config``
with this layout:

  Row 6  : market display names ("Federal Reserve Board", "US Govt Bond Market", ...)
  Row 9  : 2-char calendar codes (FD, GT, WL, KD, YO, AU, JN, TE, SK, RB, I6,
           TH, MA, HK, SI, TA, ID, PH)
  Row 10 : "DATES" header row
  Row 11+: holiday dates per calendar column (sparse — each column has a
           different number of dates)

The loader is idempotent — re-running with the same data is a no-op (MERGE
on (calendar_id, holiday_date, vendor_id) natural key). Use
``--load-batch <tag>`` to distinguish snapshots over time.

Usage:
    python -m scripts.calendar.load_market_holidays_xlsx \\
        --xlsx "Z:\\...\\Calendar pasted.xlsx"
    python -m scripts.calendar.load_market_holidays_xlsx \\
        --xlsx "..." --load-batch bbg_xlsx_2026_05 --dry-run
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import structlog
from sqlalchemy import text
from sqlalchemy.orm import Session

from imdr.config.settings import get_settings
from imdr.connectors.mssql import MSSQLConnector
from imdr.utils.logging import configure_logging

log = structlog.get_logger(__name__)

VENDOR_CODE = "BBG"  # Excel master is Bloomberg-sourced
SHEET_NAME = "master_config"
CALENDAR_CODE_ROW = 9  # 0-indexed
DATA_START_ROW = 11    # 0-indexed


def parse_xlsx(xlsx_path: Path) -> dict[str, list[date]]:
    """Return {calendar_code: [holiday_date, ...]}.

    Reads the sparse rectangular layout, drops NaTs, and de-duplicates per
    column so a stray duplicate in the source doesn't upset the unique
    constraint downstream.
    """
    df = pd.read_excel(xlsx_path, sheet_name=SHEET_NAME, header=None)
    if df.shape[0] < DATA_START_ROW:
        msg = f"{xlsx_path} has only {df.shape[0]} rows; expected ≥ {DATA_START_ROW}"
        raise ValueError(msg)

    code_row = df.iloc[CALENDAR_CODE_ROW]
    out: dict[str, list[date]] = {}
    for col_idx, code in enumerate(code_row):
        if not isinstance(code, str):
            continue
        code = code.strip()
        if not code:
            continue
        col = df.iloc[DATA_START_ROW:, col_idx].dropna()
        dates: set[date] = set()
        for v in col:
            if isinstance(v, (datetime, pd.Timestamp)):
                dates.add(v.date() if hasattr(v, "date") else v)
            elif isinstance(v, date):
                dates.add(v)
            # silently skip strings, numbers, etc — only real dates count
        if dates:
            out[code] = sorted(dates)
    return out


def lookup_ids(session: Session) -> tuple[dict[str, int], int]:
    """Return ({calendar_code: id}, vendor_id_for_BBG)."""
    cal_rows = session.execute(text("""
        SELECT calendar_code, id FROM calendar.dim_calendar
    """)).all()
    cal_map = {code: cid for code, cid in cal_rows}

    vendor_id = session.execute(text("""
        SELECT id FROM dbo.dim_vendor WHERE vendor_code = :code
    """), {"code": VENDOR_CODE}).scalar()
    if vendor_id is None:
        msg = f"vendor_code {VENDOR_CODE!r} not in dbo.dim_vendor — run migration 031 first"
        raise RuntimeError(msg)
    return cal_map, vendor_id


def upsert_holidays(
    session: Session,
    cal_map: dict[str, int],
    vendor_id: int,
    parsed: dict[str, list[date]],
    load_batch: str,
    dry_run: bool,
) -> tuple[int, int, list[str]]:
    """Insert any (calendar_id, holiday_date, vendor_id) rows that don't already
    exist. Returns (inserted, skipped, missing_calendar_codes).
    """
    inserted = 0
    skipped = 0
    missing: list[str] = []
    for code, dates in parsed.items():
        cal_id = cal_map.get(code)
        if cal_id is None:
            missing.append(code)
            log.warning("calendar_code_not_in_dim_calendar", code=code, dates=len(dates))
            continue

        rows = [
            {"cal_id": cal_id, "vendor_id": vendor_id, "d": d, "batch": load_batch}
            for d in dates
        ]

        if dry_run:
            existing = session.execute(text("""
                SELECT COUNT(*) FROM calendar.market_holidays
                WHERE calendar_id = :cal_id AND vendor_id = :vendor_id
            """), {"cal_id": cal_id, "vendor_id": vendor_id}).scalar() or 0
            new = max(0, len(dates) - existing)
            inserted += new
            skipped += min(existing, len(dates))
            log.info(
                "dry_run_calendar",
                code=code, would_insert=new, already_in_db=existing,
            )
            continue

        # MERGE-style insert: only add rows not already present.
        result = session.execute(text("""
            INSERT INTO calendar.market_holidays
                (calendar_id, vendor_id, holiday_date, load_batch)
            SELECT :cal_id, :vendor_id, :d, :batch
            WHERE NOT EXISTS (
                SELECT 1 FROM calendar.market_holidays
                WHERE calendar_id = :cal_id
                  AND vendor_id   = :vendor_id
                  AND holiday_date = :d
            )
        """), rows)
        # rowcount under fast_executemany may be -1; recompute explicitly.
        new = session.execute(text("""
            SELECT COUNT(*) FROM calendar.market_holidays
            WHERE calendar_id = :cal_id AND vendor_id = :vendor_id
              AND load_batch = :batch
        """), {"cal_id": cal_id, "vendor_id": vendor_id, "batch": load_batch}).scalar() or 0
        skipped += max(0, len(dates) - new)
        inserted += new
        log.info("loaded_calendar", code=code, inserted=new, skipped=len(dates) - new)

    return inserted, skipped, missing


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--xlsx", type=Path, required=True, help="Path to Calendar pasted.xlsx")
    p.add_argument(
        "--load-batch", default=None,
        help="Tag stamped on inserted rows. Defaults to bbg_xlsx_<YYYYMMDD>.",
    )
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    settings = get_settings()
    configure_logging(settings)

    if not args.xlsx.exists():
        log.error("xlsx_not_found", path=str(args.xlsx))
        return 2

    load_batch = args.load_batch or f"bbg_xlsx_{date.today():%Y%m%d}"

    parsed = parse_xlsx(args.xlsx)
    log.info(
        "parsed_xlsx",
        path=str(args.xlsx),
        calendars=len(parsed),
        total_dates=sum(len(v) for v in parsed.values()),
    )

    connector = MSSQLConnector(settings)
    try:
        with connector.session() as session:
            cal_map, vendor_id = lookup_ids(session)
            inserted, skipped, missing = upsert_holidays(
                session, cal_map, vendor_id, parsed, load_batch, args.dry_run,
            )
            if args.dry_run:
                session.rollback()
    finally:
        connector.dispose()

    log.info(
        "load_complete",
        dry_run=args.dry_run,
        inserted=inserted,
        skipped_existing=skipped,
        missing_calendar_codes=missing,
        load_batch=load_batch,
    )
    return 0 if not missing else 1


if __name__ == "__main__":
    sys.exit(main())
