"""Emit a SQL migration that overwrites calendar.dim_calendar.description with
the short BBG labels from the calendar_pasted.xlsx workbook.

The xlsx layout (May 2026 template) has three header rows:

    row N-2  description labels   ('Federal Reserve Board', 'NewYork', …)
    row N-1  (blank)
    row N    calendar codes        ('FD', 'YO', …)
    row N+1  'DATES' marker
    row N+2+ holiday dates per column

Layout is auto-detected by scanning for the 'DATES' marker, then walking up
two rows past a blank gutter row. Robust to small template tweaks.

Output is a SQL file with one UPDATE per calendar_code, plus a verification
SELECT. Run, then commit the output file as the migration.

Usage:
    python -m scripts.calendar.emit_calendar_descriptions_sql \\
        --xlsx "Z:\\Business\\Personnel\\Arjun\\IMDR_MANUAL_UPLOADS\\May 2026\\calendar_pasted.xlsx" \\
        --out migrations/042_backfill_calendar_descriptions.sql
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

DATES_MARKER = "DATES"


def find_layout(df: pd.DataFrame) -> tuple[int, int]:
    """Return (code_row_idx, description_row_idx).

    Scans for the row whose non-null values are all 'DATES'. Codes are on the
    row directly above; descriptions are on the nearest non-blank row above
    the codes row (handles the blank gutter row between them).
    """
    dates_row = None
    for i in range(min(30, df.shape[0])):
        vals = df.iloc[i].dropna().tolist()
        if vals and all(isinstance(v, str) and v.strip() == DATES_MARKER for v in vals):
            dates_row = i
            break
    if dates_row is None:
        raise ValueError("DATES marker row not found in first 30 rows")

    code_row = dates_row - 1

    desc_row = None
    for j in range(code_row - 1, max(-1, code_row - 6), -1):
        vals = df.iloc[j].dropna().tolist()
        # Count cells that look like description labels (non-empty strings,
        # not the DATES marker, not just dates).
        labels = [
            v for v in vals
            if isinstance(v, str) and v.strip() and v.strip() != DATES_MARKER
        ]
        if len(labels) >= 5:  # plausible header row
            desc_row = j
            break
    if desc_row is None:
        raise ValueError("description row not found above code row")

    return code_row, desc_row


def extract_code_to_description(df: pd.DataFrame) -> dict[str, str]:
    """Return {calendar_code: description} keyed by column alignment."""
    code_row_idx, desc_row_idx = find_layout(df)
    code_row = df.iloc[code_row_idx]
    desc_row = df.iloc[desc_row_idx]

    out: dict[str, str] = {}
    for col_idx, code in enumerate(code_row):
        if not isinstance(code, str) or not code.strip():
            continue
        code = code.strip()
        desc = desc_row.iloc[col_idx] if col_idx < len(desc_row) else None
        if isinstance(desc, str) and desc.strip():
            out[code] = desc.strip()
    return out


def emit_sql(mapping: dict[str, str], xlsx_path: Path) -> str:
    """Render the migration SQL."""
    lines: list[str] = []
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines.append("-- Migration 042: Backfill calendar.dim_calendar.description from BBG xlsx.")
    lines.append("--")
    lines.append("-- Source: " + str(xlsx_path))
    lines.append(f"-- Generated: {now_utc}")
    lines.append(f"-- Generator: scripts/calendar/emit_calendar_descriptions_sql.py")
    lines.append("--")
    lines.append("-- Overwrites the existing dim_calendar.description text with the short BBG")
    lines.append("-- label from row 6 of the xlsx (e.g. FD='Federal Reserve Board',")
    lines.append("-- YO='NewYork', TE='Target'). Per user direction 2026-05-12: source-of-truth")
    lines.append("-- is the BBG file even though the previous hand-written descriptions are more")
    lines.append("-- informative.")
    lines.append("--")
    lines.append("-- Any calendar_code not present in the xlsx is left unchanged.")
    lines.append("")
    for code in sorted(mapping.keys()):
        desc = mapping[code].replace("'", "''")  # T-SQL string escape
        # Escape `+` in calendar_code for the WHERE clause? Not needed — it's
        # just a literal char in varchar. SQL Server handles it fine.
        lines.append(f"UPDATE [calendar].[dim_calendar]")
        lines.append(f"    SET description = N'{desc}', updated_at = SYSDATETIMEOFFSET()")
        lines.append(f"    WHERE calendar_code = N'{code}';")
        lines.append("GO")
        lines.append("")

    lines.append("-- Verification:")
    lines.append("-- SELECT calendar_code, description FROM calendar.dim_calendar ORDER BY calendar_code;")
    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--xlsx", type=Path, required=True)
    p.add_argument(
        "--out", type=Path, required=True,
        help="Path to write the generated migration SQL.",
    )
    args = p.parse_args()

    if not args.xlsx.exists():
        print(f"NOT FOUND: {args.xlsx}", file=sys.stderr)
        return 2

    xl = pd.ExcelFile(args.xlsx)
    df = pd.read_excel(xl, sheet_name=xl.sheet_names[0], header=None)
    mapping = extract_code_to_description(df)

    print(f"Extracted {len(mapping)} (code, description) pairs:")
    for code in sorted(mapping.keys()):
        print(f"  {code:<5} -> {mapping[code]}")

    sql = emit_sql(mapping, args.xlsx)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(sql, encoding="utf-8")
    print(f"\nWrote: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
