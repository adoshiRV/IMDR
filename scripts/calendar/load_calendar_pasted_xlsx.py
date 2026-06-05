"""Load curated holiday calendars from the 2026-05 BBG master refresh
("calendar_pasted.xlsx") into ``calendar.market_holidays`` with
``vendor_id = BBG``.

Differs from the older ``load_market_holidays_xlsx.py`` in two ways:

  * Sheet name is ``Sheet1`` (was ``master_config``).
  * Layout shifted up by one row — codes on row 8, "DATES" header on row 9,
    holiday dates from row 10 onwards.
  * Adds 9 calendars beyond the original 18: IB (Xetra), LS (LSE), NY (NYSE
    proper, distinct from YO), OK (Osaka), S5 (SIX), CA (Canada), SW (Sweden),
    NO (Norway), +P (Philippines FX Settlement). The dim_calendar rows for
    these land via migration 034.

Rather than hard-coding row offsets, this loader auto-detects them by
scanning for the row whose values are mostly the literal "DATES" — the row
above it holds the codes, the row below it is data. Survives further BBG
template tweaks of similar shape.

Usage:
    python -m scripts.calendar.load_calendar_pasted_xlsx \\
        --xlsx "Z:\\Business\\Personnel\\Arjun\\IMDR_MANUAL_UPLOADS\\May 2026\\calendar_pasted.xlsx"
    python -m scripts.calendar.load_calendar_pasted_xlsx \\
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

VENDOR_CODE = "BBG"  # Master xlsx is Bloomberg-sourced
DATES_MARKER = "DATES"


def _find_layout(df: pd.DataFrame) -> tuple[int, int]:
    """Return (codes_row_idx, data_start_row_idx) by scanning for the
    ``DATES`` header row. Header = the row whose non-null values are all
    the literal string "DATES". Codes = header_row - 1; data = header_row + 1.

    Raises ValueError if no such row exists in the first 30 rows.
    """
    for i in range(min(30, df.shape[0])):
        vals = df.iloc[i].dropna().tolist()
        if not vals:
            continue
        if all(isinstance(v, str) and v.strip() == DATES_MARKER for v in vals):
            return i - 1, i + 1
    msg = "couldn't locate the 'DATES' header row in the first 30 rows of the xlsx"
    raise ValueError(msg)


def parse_xlsx(xlsx_path: Path) -> dict[str, list[date]]:
    """Return {calendar_code: [holiday_date, ...]} from the workbook.

    Reads the first sheet (Excel sheet names have varied across templates),
    auto-detects the codes / data rows, drops NaTs, and de-duplicates per
    column.
    """
    xl = pd.ExcelFile(xlsx_path)
    sheet = xl.sheet_names[0]
    df = pd.read_excel(xl, sheet_name=sheet, header=None)
    code_row_idx, data_start_idx = _find_layout(df)

    code_row = df.iloc[code_row_idx]
    out: dict[str, list[date]] = {}
    for col_idx, code in enumerate(code_row):
        if not isinstance(code, str):
            continue
        code = code.strip()
        if not code:
            continue
        col = df.iloc[data_start_idx:, col_idx].dropna()
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
        msg = f"vendor_code {VENDOR_CODE!r} not in dbo.dim_vendor — apply migrations 031+034 first"
        raise RuntimeError(msg)
    return cal_map, vendor_id


def upsert_holidays(
    session: Session,
    cal_map: dict[str, int],
    vendor_id: int,
    parsed: dict[str, list[date]],
    load_batch: str,
    dry_run: bool,
) -> tuple[int, int, list[str], list[dict]]:
    """Insert any (calendar_id, holiday_date, vendor_id) rows that don't already
    exist. Returns (inserted, skipped, missing_calendar_codes, per_calendar)
    where per_calendar is a list of {code, in_file, inserted, skipped}."""
    inserted = 0
    skipped = 0
    missing: list[str] = []
    per_calendar: list[dict] = []
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
            per_calendar.append(
                {"code": code, "in_file": len(dates), "inserted": new, "skipped": min(existing, len(dates))}
            )
            log.info(
                "dry_run_calendar",
                code=code, would_insert=new, already_in_db=existing,
            )
            continue

        # Insert any rows not already present (idempotent re-runs).
        session.execute(text("""
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
        new = session.execute(text("""
            SELECT COUNT(*) FROM calendar.market_holidays
            WHERE calendar_id = :cal_id AND vendor_id = :vendor_id
              AND load_batch = :batch
        """), {"cal_id": cal_id, "vendor_id": vendor_id, "batch": load_batch}).scalar() or 0
        skipped += max(0, len(dates) - new)
        inserted += new
        per_calendar.append(
            {"code": code, "in_file": len(dates), "inserted": new, "skipped": len(dates) - new}
        )
        log.info("loaded_calendar", code=code, inserted=new, skipped=len(dates) - new)

    return inserted, skipped, missing, per_calendar


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--xlsx", type=Path, required=True, help="Path to calendar_pasted.xlsx")
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
            inserted, skipped, missing, _per_cal = upsert_holidays(
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
