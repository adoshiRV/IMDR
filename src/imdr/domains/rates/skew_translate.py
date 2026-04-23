"""Rates swaption skew Excel parser — Barclays/S&P vol surface files.

Parses column headers of the form:
    USDSW{EXPIRY}{TENOR}F Normalised vol ATM {STRIKE} bp

Example: USDSW9M1YF Normalised vol ATM -200 bp
  → ccy=USD, option_expiry=9M, swap_tenor=1Y, strike_offset=-200

Also provides read_skew_files() which reads multiple Excel files,
auto-detects option_expiry from headers, and returns a single long DataFrame.
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pandas as pd
import structlog

_log = structlog.get_logger("skew_translate")

COLUMNS = ["ts", "ccy", "option_expiry", "swap_tenor", "strike_offset", "vol"]

# Matches: USDSW9M1YF Normalised vol ATM -200 bp  or  USDSW1Y10YF Normalised vol ATM +50 bp
# Groups:  ccy_code(USD), expiry(\d+[MY]), tenor(\d+Y), strike(-200|+50 etc.)
_HEADER_RE = re.compile(
    r"^(?P<ccy>[A-Z]{3})SW"
    r"(?P<expiry>\d+[MY])"
    r"(?P<tenor>\d+Y)F\s+"
    r"Normalised vol ATM\s+"
    r"(?P<strike>[+-]?\d+)\s*bp$"
)


def parse_skew_column(header: str) -> dict | None:
    """Parse a Barclays skew column header into structured fields.

    Returns None for unparseable headers (e.g. 'Date').
    """
    m = _HEADER_RE.match(header.strip())
    if not m:
        return None
    return {
        "ccy": m.group("ccy"),
        "option_expiry": m.group("expiry"),
        "swap_tenor": m.group("tenor"),
        "strike_offset": int(m.group("strike")),
    }


def _read_single_file(path: Path) -> pd.DataFrame:
    """Read one Excel file's 'Series' sheet into a long-format DataFrame."""
    df_wide = pd.read_excel(path, sheet_name="Series", engine="openpyxl")

    if "Date" not in df_wide.columns:
        _log.warning("no_date_column", path=str(path))
        return pd.DataFrame(columns=COLUMNS)

    records: list[dict] = []
    parsed_cols: list[tuple[str, dict]] = []

    for col in df_wide.columns:
        if col == "Date":
            continue
        meta = parse_skew_column(col)
        if meta is None:
            _log.warning("unparseable_column", column=col, path=str(path))
            continue
        parsed_cols.append((col, meta))

    if not parsed_cols:
        _log.warning("no_parseable_columns", path=str(path))
        return pd.DataFrame(columns=COLUMNS)

    # Auto-detect expiry from first parsed column
    detected_expiry = parsed_cols[0][1]["option_expiry"]
    _log.info(
        "file_parsed",
        path=path.name,
        option_expiry=detected_expiry,
        n_columns=len(parsed_cols),
        n_rows=len(df_wide),
    )

    for _, row in df_wide.iterrows():
        ts = row["Date"]
        if pd.isna(ts):
            continue
        for col_name, meta in parsed_cols:
            val = row[col_name]
            if pd.isna(val):
                continue
            records.append({
                "ts": pd.Timestamp(ts),
                "ccy": meta["ccy"],
                "option_expiry": meta["option_expiry"],
                "swap_tenor": meta["swap_tenor"],
                "strike_offset": meta["strike_offset"],
                "vol": float(val),
            })

    return pd.DataFrame(records, columns=COLUMNS)


def read_skew_files(
    paths: list[Path],
    start: date | None = None,
    end: date | None = None,
) -> pd.DataFrame:
    """Read multiple Barclays skew Excel files into a single long DataFrame.

    Parameters
    ----------
    paths : list of Path to .xlsx files
    start, end : optional date range filter (inclusive)

    Returns
    -------
    pd.DataFrame with columns defined in COLUMNS
    """
    if not paths:
        return pd.DataFrame(columns=COLUMNS)

    frames: list[pd.DataFrame] = []
    for p in paths:
        _log.info("reading_file", path=str(p))
        df = _read_single_file(Path(p))
        if not df.empty:
            frames.append(df)

    if not frames:
        return pd.DataFrame(columns=COLUMNS)

    result = pd.concat(frames, ignore_index=True)

    # Apply date filter
    if start is not None:
        result = result[result["ts"].dt.date >= start]
    if end is not None:
        result = result[result["ts"].dt.date <= end]

    result = result.sort_values(
        ["ccy", "option_expiry", "swap_tenor", "strike_offset", "ts"]
    ).reset_index(drop=True)

    _log.info("read_complete", total_rows=len(result), n_files=len(paths))
    return result
