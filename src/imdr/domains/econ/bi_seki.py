"""Bank Indonesia SEKI XLSX scraper.

SEKI = Statistik Ekonomi dan Keuangan Indonesia. BI publishes monthly /
quarterly statistical tables as XLSX files at a stable URL pattern:

    https://www.bi.go.id/SEKI/tabel/TABEL{N}_{M}.xls

These are wide-format tables with:
  - year row (sparse, one label per year-start or year-end)
  - month row (Jan/Feb/.../Des or Q1..Q4 / I..IV)
  - data rows: col 0 = line-item number, col 2 = Indonesian label, col 3+ = values

For SEKI Section IV (fiscal) tables there is no month row and each value
column is a single year (parse via ``parse_seki_annual_sheet``).

Auth: NONE (public XLSX). Throttle: 2s between downloads.
"""

from __future__ import annotations

import datetime
import time
import urllib.request
from pathlib import Path

import pandas as pd


_BASE = "https://www.bi.go.id/SEKI/tabel/"
_REPO_ROOT = Path(__file__).resolve().parents[4]
_RAW_DIR = _REPO_ROOT / "data" / "econ" / "bi" / "seki_raw"
_UA = "Mozilla/5.0 IMDR-bi"
_THROTTLE_S = 2.0

_MONTH_LABEL_TO_INT = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "mei": 5, "may": 5,
    "jun": 6, "jul": 7, "agu": 8, "ags": 8, "aug": 8, "sep": 9,
    "okt": 10, "oct": 10, "nov": 11, "des": 12, "dec": 12,
}

# Quarter labels → starting month. BoP / national-accounts SEKI tables use
# 'Q1'..'Q4'; SKDU Business Survey uses Roman numerals 'I'..'IV'.
_QUARTER_LABEL_TO_MONTH = {
    "q1": 1, "q2": 4, "q3": 7, "q4": 10,
    "i": 1, "ii": 4, "iii": 7, "iv": 10,
}


def download_seki(table_id: str, force: bool = False) -> Path:
    """Download a SEKI XLSX table by ID (e.g. 'TABEL1_1', 'TABEL5_1').

    Caches under ``data/econ/bi/seki_raw/``. Pass force=True to refetch.
    """
    _RAW_DIR.mkdir(parents=True, exist_ok=True)
    path = _RAW_DIR / f"{table_id}.xls"
    if path.exists() and not force:
        return path
    url = _BASE + f"{table_id}.xls"
    time.sleep(_THROTTLE_S)
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=60) as resp:
        path.write_bytes(resp.read())
    return path


def _parse_month(raw) -> int | None:
    """Map a SEKI period label to a month-of-year integer.

    Handles monthly ('Jan'..'Des'), quarterly ('Q1'..'Q4', with optional
    '*'/'**' preliminary suffix), and Roman-numeral ('I'..'IV') headers.
    """
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    s = str(raw).strip().lower()
    s = s.rstrip("*").strip()
    if s in _QUARTER_LABEL_TO_MONTH:
        return _QUARTER_LABEL_TO_MONTH[s]
    return _MONTH_LABEL_TO_INT.get(s[:3])


def _infer_years(year_row: list, month_row: list) -> list[int | None]:
    """Map every column to a year by rolling month-by-month.

    SEKI places the year label irregularly: sometimes at the January
    column, sometimes at the December column (TABEL1_1.xls 2024 block
    has 2024 at col 196 = Dec). Naive forward-fill mislabels 11 of 12
    months in those years.

    The robust walk advances a (year, month) cursor: when month
    transitions Dec→Jan we increment year, and explicit year labels
    serve as sanity-check anchors. Columns whose month is missing
    return None (caller skips them).
    """
    n = max(len(year_row), len(month_row))
    out: list[int | None] = [None] * n

    anchors: list[tuple[int, int]] = []
    string_cols: list[int] = []
    for c, y in enumerate(year_row):
        if y is None or (isinstance(y, float) and pd.isna(y)):
            continue
        try:
            yi = int(float(y))
        except (TypeError, ValueError):
            string_cols.append(c)
            continue
        if 1900 <= yi <= 2100:
            anchors.append((c, yi))
    if not anchors:
        return out
    # Stop at the first string-marker column AFTER the first year anchor.
    # Survey XLSX append English-label / growth-rate sub-sections at the
    # right end (e.g. "Perubahan", "DESCRIPTION") — without trimming, the
    # month-rollover walker keeps incrementing year past the true end.
    first_anchor_col = anchors[0][0]
    stop_cols = [c for c in string_cols if c > first_anchor_col]
    if stop_cols:
        n = min(n, stop_cols[0])
        out = out[:n]

    first_col, first_year = anchors[0]
    first_month = _parse_month(month_row[first_col]) if first_col < len(month_row) else None
    if first_month is None:
        # Year label sits on a non-month column — fall back to forward-fill.
        cursor_year: int | None = None
        for c in range(n):
            if c < len(month_row) and _parse_month(month_row[c]) is not None:
                for ac, ay in anchors:
                    if ac <= c:
                        cursor_year = ay
                    else:
                        break
                out[c] = cursor_year
        return out

    # Roll forward from the first month-bearing anchor.
    cur_year = first_year
    cur_month = first_month
    out[first_col] = cur_year
    for c in range(first_col + 1, n):
        m = _parse_month(month_row[c]) if c < len(month_row) else None
        if m is None:
            continue
        if m < cur_month:
            cur_year += 1
        cur_month = m
        for ac, ay in anchors:
            if ac == c:
                cur_year = ay
                break
        out[c] = cur_year
    # Walk LEFT from first anchor for any preceding months.
    cur_year = first_year
    cur_month = first_month
    for c in range(first_col - 1, -1, -1):
        m = _parse_month(month_row[c]) if c < len(month_row) else None
        if m is None:
            continue
        if m > cur_month:
            cur_year -= 1
        cur_month = m
        for ac, ay in anchors:
            if ac == c:
                cur_year = ay
                break
        out[c] = cur_year
    return out


def parse_seki_annual_sheet(
    path: Path,
    sheet: str | int,
    *,
    year_row: int = 4,
    data_start_row: int = 6,
    label_col: int = 2,
    line_item_col: int = 0,
    first_data_col: int = 3,
) -> dict[int, list[tuple[datetime.date, float | None, str]]]:
    """Parse an annual SEKI sheet (each data column = one year).

    Used for SEKI Section IV fiscal tables (4.1 Revenue, 4.2 Spending,
    4.3 Financing). Annual observations anchor to Jan 1 of the year.

    Years come from year_row directly — no walking needed. We stop at
    the first non-strictly-advancing year to skip the English-label
    tail that SEKI fiscal sheets append.
    """
    df = pd.read_excel(path, sheet_name=sheet, header=None, engine="xlrd")
    if df.shape[0] <= max(year_row, data_start_row):
        return {}
    year_cells = list(df.iloc[year_row])
    years: list[int | None] = []
    last_valid: int | None = None
    stop = False
    for v in year_cells:
        if stop:
            years.append(None)
            continue
        if v is None or (isinstance(v, float) and pd.isna(v)):
            years.append(None)
            continue
        try:
            yi = int(float(v))
        except (TypeError, ValueError):
            years.append(None)
            continue
        if not (1900 <= yi <= 2100):
            years.append(None)
            continue
        if last_valid is not None and yi <= last_valid:
            stop = True
            years.append(None)
            continue
        last_valid = yi
        years.append(yi)

    out: dict[int, list[tuple[datetime.date, float | None, str]]] = {}
    for r in range(data_start_row, df.shape[0]):
        line = df.iat[r, line_item_col]
        if pd.isna(line):
            continue
        try:
            line_no = int(float(line))
        except (TypeError, ValueError):
            continue
        label = df.iat[r, label_col]
        label_str = str(label).strip() if not pd.isna(label) else ""
        series: list[tuple[datetime.date, float | None, str]] = []
        for c in range(first_data_col, df.shape[1]):
            year = years[c] if c < len(years) else None
            if year is None:
                continue
            val = df.iat[r, c]
            if isinstance(val, str) and val.strip() in ("-", "", "na", "NA"):
                value = None
            else:
                try:
                    value = float(val) if not pd.isna(val) else None
                except (TypeError, ValueError):
                    value = None
            series.append((datetime.date(year, 1, 1), value, label_str))
        if series:
            out[line_no] = series
    return out


def parse_seki_wide_sheet(
    path: Path,
    sheet: str | int,
    *,
    year_row: int = 3,
    month_row: int = 4,
    data_start_row: int = 5,
    label_col: int = 2,
    line_item_col: int = 0,
    first_data_col: int = 3,
) -> dict[int, list[tuple[datetime.date, float | None, str]]]:
    """Parse a SEKI wide-format XLSX sheet into per-line-item time series.

    Returns dict keyed by line_item number → list of (date, value, label).

    Default offsets match the I.1 (Money Supply) sheet shape and most other
    SEKI tables. Pass overrides if a specific table differs (e.g. I.25 uses
    (4,5,6); I.26/I.28 use (3,4,5)).
    """
    df = pd.read_excel(path, sheet_name=sheet, header=None, engine="xlrd")
    if df.shape[0] <= max(year_row, month_row, data_start_row):
        return {}
    years = _infer_years(list(df.iloc[year_row]), list(df.iloc[month_row]))
    months = [_parse_month(v) for v in df.iloc[month_row]]

    out: dict[int, list[tuple[datetime.date, float | None, str]]] = {}
    for r in range(data_start_row, df.shape[0]):
        line = df.iat[r, line_item_col]
        if pd.isna(line):
            continue
        try:
            line_no = int(float(line))
        except (TypeError, ValueError):
            continue
        label = df.iat[r, label_col]
        label_str = str(label).strip() if not pd.isna(label) else ""
        series: list[tuple[datetime.date, float | None, str]] = []
        for c in range(first_data_col, df.shape[1]):
            year = years[c] if c < len(years) else None
            month = months[c] if c < len(months) else None
            if year is None or month is None:
                continue
            val = df.iat[r, c]
            if isinstance(val, str) and val.strip() in ("-", "", "na", "NA"):
                value = None
            else:
                try:
                    value = float(val) if not pd.isna(val) else None
                except (TypeError, ValueError):
                    value = None
            series.append((datetime.date(year, month, 1), value, label_str))
        if series:
            out[line_no] = series
    return out
