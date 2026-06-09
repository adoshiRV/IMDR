"""Import central bank events from Bloomberg Excel export into calendar.cb_events.

Reads multi-sheet Excel files (varying formats across sheets), normalizes
columns, applies a rolling date window, and upserts to the database.

Usage:
    python -m scripts.calendar.import_cb_events --file "path/to/file.xlsx"
    python -m scripts.calendar.import_cb_events --file "path/to/file.xlsx" --months-back 2 --months-forward 2
    python -m scripts.calendar.import_cb_events --file "path/to/file.xlsx" --all  # no date filter
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import structlog
from sqlalchemy import text
from sqlalchemy.orm import Session

from imdr.config.settings import get_settings
from imdr.connectors.mssql import MSSQLConnector
from imdr.utils.logging import configure_logging

log = structlog.get_logger(__name__)

# Bloomberg country code → our standard market code mapping
_BBG_COUNTRY_MAP: dict[str, str] = {
    "JN": "JP",
    "EC": "EU",
    "SW": "SE",
    "SZ": "CH",
    "SK": "KR",
    "MA": "MY",
    "PO": "PL",
    "FI": "FI",    # Finland — no separate market, maps to EU
    "SI": "SG",
    "SP": "ES",    # Spain — maps to EU
    "NE": "NL",    # Netherlands — maps to EU
    "WW": "WW",    # Worldwide — keep as-is
    "GE": "DE",    # Germany — maps to EU
    "IT": "IT",    # Italy — maps to EU
    "FR": "FR",    # France — maps to EU
    "PD": "PH",    # Philippines
}

# Canonical column names used by sheets 3 & 4 (2018-2023, 2023-2026)
_CANONICAL_COLS = [
    "country_region", "flag", "country_code", "ticker", "category",
    "event", "event_date", "event_datetime", "period", "survey",
    "actual", "prior", "revised", "relevance", "frequency", "month", "survey_a",
]

# Column mapping for sheet 1 (2008-2012)
_SHEET1_COL_MAP = {
    "Date Time": "event_datetime",
    "Country Code": "country_code",
    "Event": "event",
    "Period": "period",
    "Survey": "survey",
    "Actual": "actual",
    "Prior": "prior",
    "Revised": "revised",
    "Relevance": "relevance",
    "Ticker": "ticker",
}


def _normalize_sheet1(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize sheet 1 (2008-2012) format."""
    df = df.rename(columns=_SHEET1_COL_MAP)
    # Extract date from datetime
    if "event_datetime" in df.columns:
        df["event_date"] = pd.to_datetime(df["event_datetime"], errors="coerce").dt.date
    df["category"] = "Central Banks"  # Sheet 1 doesn't have category
    df["frequency"] = None
    return df


def _normalize_sheet234(df: pd.DataFrame, has_header: bool = True) -> pd.DataFrame:
    """Normalize sheets 2-4 (2012-2026) format."""
    if not has_header:
        df.columns = _CANONICAL_COLS[:len(df.columns)]
    else:
        col_map = {
            "Country/Region": "country_region",
            "Flag": "flag",
            "C": "country_code",
            "Ticker": "ticker",
            "Category": "category",
            "Event": "event",
            "Date": "event_date",
            "Date Time": "event_datetime",
            "Period": "period",
            "Surv(M)": "survey",
            "Actual": "actual",
            "Prior": "prior",
            "Revised": "revised",
            "S": "relevance",
            "Freq.": "frequency",
            "Month": "month",
            "Surv(A)": "survey_a",
        }
        df = df.rename(columns=col_map)

    # Parse dates
    if "event_date" in df.columns:
        df["event_date"] = pd.to_datetime(df["event_date"], errors="coerce").dt.date
    if "event_datetime" in df.columns:
        df["event_datetime"] = pd.to_datetime(df["event_datetime"], errors="coerce")

    return df


def _map_country_code(code: str) -> str:
    """Map Bloomberg country code to our standard market code."""
    if pd.isna(code):
        return "XX"
    code = str(code).strip().upper()
    return _BBG_COUNTRY_MAP.get(code, code)


def _safe_str(val) -> str | None:
    """Ensure a value is either a string or None — never NaN/float."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if pd.isna(val):
        return None
    s = str(val).strip()
    return s if s and s != "nan" else None


def _clean_string_val(val) -> str | None:
    """Clean survey/actual/prior/revised fields."""
    if pd.isna(val):
        return None
    s = str(val).strip()
    if s in ("--", "", "nan"):
        return None
    return s[:20]  # Truncate to DB column width


def _parse_period(val) -> date | None:
    """Parse period field to date, handling various formats."""
    if pd.isna(val):
        return None
    if isinstance(val, datetime):
        d = val.date()
        return d if d.year >= 1900 else None
    if isinstance(val, date):
        return val if val.year >= 1900 else None
    s = str(val).strip()
    if s in ("--", "", "nan", "NaT"):
        return None
    # Skip short month names like "Dec", "Jan" — not actual dates
    if len(s) <= 4 and not s.isdigit():
        return None
    try:
        d = pd.to_datetime(s).date()
        return d if d.year >= 1900 else None
    except Exception:
        return None


def load_and_normalize(file_path: Path) -> pd.DataFrame:
    """Load all sheets from Excel file and normalize to common schema."""
    sheets = pd.read_excel(file_path, sheet_name=None)
    frames: list[pd.DataFrame] = []

    for name, df in sheets.items():
        log.info("processing_sheet", sheet=name, rows=len(df))

        if "Country Code" in df.columns:
            # Sheet 1 format (2008-2012)
            normalized = _normalize_sheet1(df)
        elif "Country/Region" in df.columns or "C" in df.columns:
            # Sheets 3 & 4 format (has proper headers)
            normalized = _normalize_sheet234(df, has_header=True)
        else:
            # Sheet 2 format (no header row — data starts at row 0)
            normalized = _normalize_sheet234(df, has_header=False)

        frames.append(normalized)

    combined = pd.concat(frames, ignore_index=True)

    # Normalize country codes
    combined["country_code"] = combined["country_code"].apply(_map_country_code)

    # Rename reserved-word columns to match DB schema
    combined = combined.rename(columns={
        "event": "event_name",
        "prior": "prior_value",
        "period": "period_value",
    })

    # Clean string fields
    for col in ("survey", "actual", "prior_value", "revised"):
        if col in combined.columns:
            combined[col] = combined[col].apply(_clean_string_val)

    # Clean event text
    combined["event_name"] = combined["event_name"].astype(str).str.strip().str[:500]

    # Clean ticker
    if "ticker" in combined.columns:
        combined["ticker"] = combined["ticker"].apply(
            lambda v: None if pd.isna(v) else str(v).strip()[:50] or None,
        )

    # Parse period
    if "period_value" in combined.columns:
        combined["period_value"] = combined["period_value"].apply(_parse_period)

    # Parse relevance as float
    if "relevance" in combined.columns:
        combined["relevance"] = pd.to_numeric(combined["relevance"], errors="coerce")

    # Clean frequency
    if "frequency" in combined.columns:
        combined["frequency"] = combined["frequency"].apply(
            lambda v: None if pd.isna(v) else str(v).strip()[:5] or None,
        )

    # Clean category
    if "category" in combined.columns:
        combined["category"] = combined["category"].fillna("Unknown").astype(str).str.strip()[:50]

    # Drop rows without a valid event_date
    combined = combined.dropna(subset=["event_date"])

    log.info("loaded_all_sheets", total_rows=len(combined))
    return combined


def filter_date_window(
    df: pd.DataFrame, months_back: int, months_forward: int,
) -> pd.DataFrame:
    """Filter to rolling window: [today - months_back, today + months_forward]."""
    today = date.today()
    start = today - timedelta(days=months_back * 31)
    end = today + timedelta(days=months_forward * 31)

    mask = df["event_date"].apply(lambda d: start <= d <= end if d else False)
    filtered = df[mask].copy()
    log.info(
        "date_window_filter",
        start=str(start), end=str(end),
        before=len(df), after=len(filtered),
    )
    return filtered


def _load_country_id_map(session: Session) -> dict[str, int]:
    """Build country_code → country_id map from dbo.dim_country (52 rows)."""
    rows = session.execute(
        text("SELECT country_code, id FROM [dbo].[dim_country]"),
    ).fetchall()
    return {str(cc).upper(): int(cid) for cc, cid in rows}


def upsert_events(session: Session, df: pd.DataFrame) -> int:
    """Upsert events to calendar.cb_events using MERGE.

    Returns number of rows affected.
    """
    if df.empty:
        log.info("no_events_to_upsert")
        return 0

    # Resolve all country codes up-front; reuse for every row.
    country_id_map = _load_country_id_map(session)
    unknown_country_codes: set[str] = set()

    inserted = 0
    updated = 0
    skipped = 0

    for _, row in df.iterrows():
        event_date = row["event_date"]
        country_code = _safe_str(row.get("country_code")) or "XX"
        country_id = country_id_map.get(country_code.upper())
        if country_id is None:
            # Country isn't in dim_country; skip this row and log once per code.
            if country_code not in unknown_country_codes:
                unknown_country_codes.add(country_code)
                log.warning("unknown_country_code_in_cb_events", country_code=country_code)
            skipped += 1
            continue

        event_text = _safe_str(row.get("event_name")) or ""
        ticker = row.get("ticker")
        if pd.isna(ticker):
            ticker = None
        event_datetime = row.get("event_datetime")

        # Convert pandas Timestamp to Python datetime
        if pd.notna(event_datetime) and isinstance(event_datetime, pd.Timestamp):
            event_datetime = event_datetime.to_pydatetime().replace(tzinfo=timezone.utc)
        elif pd.isna(event_datetime):
            event_datetime = None

        period_value = row.get("period_value")
        if pd.isna(period_value) if period_value is not None else True:
            period_value = None

        # Legacy ODBC driver can't bind date objects — convert to ISO strings
        event_date_str = str(event_date) if event_date else None
        if event_datetime is None:
            event_dt_str = None
        elif isinstance(event_datetime, str):
            event_dt_str = event_datetime
        else:
            event_dt_str = event_datetime.isoformat()
        period_str = str(period_value) if period_value else None

        # Check if row exists (by ticker if present, else by event text).
        # Dedupe key uses country_id, matching the unique indexes on cb_events.
        if ticker:
            existing = session.execute(
                text("""
                    SELECT id FROM [calendar].[cb_events]
                    WHERE event_date = :event_date
                      AND country_id = :country_id
                      AND ticker = :ticker
                """),
                {"event_date": event_date_str, "country_id": country_id, "ticker": ticker},
            ).fetchone()
        else:
            existing = session.execute(
                text("""
                    SELECT id FROM [calendar].[cb_events]
                    WHERE event_date = :event_date
                      AND country_id = :country_id
                      AND event_name = :event_name
                      AND ticker IS NULL
                """),
                {"event_date": event_date_str, "country_id": country_id, "event_name": event_text},
            ).fetchone()

        params = {
            "event_date": event_date_str,
            "event_datetime": event_dt_str,
            "country_id": country_id,
            "category": _safe_str(row.get("category")) or "Unknown",
            "event_name": _safe_str(event_text) or "",
            "ticker": _safe_str(ticker),
            "period_value": period_str,
            "survey": _safe_str(row.get("survey")),
            "actual": _safe_str(row.get("actual")),
            "prior_value": _safe_str(row.get("prior_value")),
            "revised": _safe_str(row.get("revised")),
            "relevance": float(row["relevance"]) if pd.notna(row.get("relevance")) else None,
            "frequency": row.get("frequency") if pd.notna(row.get("frequency")) else None,
            "source": "bloomberg",
            "is_estimated": 0,
        }

        if existing:
            params["id"] = existing[0]
            session.execute(
                text("""
                    UPDATE [calendar].[cb_events]
                    SET event_datetime = :event_datetime,
                        category = :category,
                        event_name = :event_name,
                        period_value = :period_value,
                        survey = :survey,
                        actual = :actual,
                        prior_value = :prior_value,
                        revised = :revised,
                        relevance = :relevance,
                        frequency = :frequency,
                        source = :source,
                        is_estimated = :is_estimated,
                        updated_at = SYSDATETIMEOFFSET()
                    WHERE id = :id
                """),
                params,
            )
            updated += 1
        else:
            session.execute(
                text("""
                    INSERT INTO [calendar].[cb_events]
                        (event_date, event_datetime, country_id, category, event_name,
                         ticker, period_value, survey, actual, prior_value, revised, relevance, frequency,
                         source, is_estimated)
                    VALUES
                        (:event_date, :event_datetime, :country_id, :category, :event_name,
                         :ticker, :period_value, :survey, :actual, :prior_value, :revised, :relevance, :frequency,
                         :source, :is_estimated)
                """),
                params,
            )
            inserted += 1

    session.commit()
    log.info("upsert_complete", inserted=inserted, updated=updated, skipped=skipped)
    return inserted + updated


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import CB events from Bloomberg Excel")
    parser.add_argument(
        "--file", type=str, required=True,
        help="Path to Bloomberg CB events Excel file",
    )
    parser.add_argument(
        "--months-back", type=int, default=1,
        help="Months to look back from today (default: 1)",
    )
    parser.add_argument(
        "--months-forward", type=int, default=1,
        help="Months to look forward from today (default: 1)",
    )
    parser.add_argument(
        "--all", action="store_true", dest="load_all",
        help="Load all data without date filtering",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Parse and filter only, don't write to DB",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = get_settings()
    configure_logging(settings)

    file_path = Path(args.file)
    if not file_path.exists():
        log.error("file_not_found", path=str(file_path))
        sys.exit(1)

    log.info("starting_import", file=str(file_path))

    # Load and normalize all sheets
    df = load_and_normalize(file_path)

    # Apply date window filter
    if not args.load_all:
        df = filter_date_window(df, args.months_back, args.months_forward)

    log.info("rows_to_load", count=len(df))

    if args.dry_run:
        log.info("dry_run_complete")
        print(f"\nDry run: {len(df)} rows would be loaded")
        print(f"\nCountry distribution:\n{df['country_code'].value_counts().to_string()}")
        print(f"\nCategory distribution:\n{df['category'].value_counts().to_string()}")
        print(f"\nDate range: {df['event_date'].min()} to {df['event_date'].max()}")
        return

    # Connect and upsert
    connector = MSSQLConnector(settings)

    with Session(connector.engine) as session:
        count = upsert_events(session, df)

    log.info("import_complete", rows_affected=count)
    print(f"\nImport complete: {count} rows affected")


if __name__ == "__main__":
    main()
