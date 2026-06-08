"""Helper for BI survey-publication XLSX archives (SK, SPE, SKDU).

Unlike SEKI tables (which use line-number indexing in col 0), BI's
periodic-survey publications package historical time series as XLSX
wrapped in single-file ZIP archives published at:

    https://www.bi.go.id/id/publikasi/laporan/Documents/{SLUG}.zip

Slugs:
  SK   — Survei Konsumen (Consumer Survey, monthly)
  spe  — Survei Penjualan Eceran (Retail Sales Survey, monthly)
  SKDU — Survei Kegiatan Dunia Usaha (Business Survey, quarterly)

These share the SEKI wide-format DNA (year row + period row + data rows)
BUT labels are NOT in a fixed ``line_item_col`` — fetchers index targets
by ROW INDEX, not line number. Different surveys use different period
encodings (months, Roman quarters); ``bi_seki._parse_month`` handles them.
"""

from __future__ import annotations

import datetime
import io
import time
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd

from imdr.domains.econ.bi_seki import _infer_years, _parse_month


_BASE = "https://www.bi.go.id/id/publikasi/laporan/Documents/"
_REPO_ROOT = Path(__file__).resolve().parents[4]
_RAW_DIR = _REPO_ROOT / "data" / "econ" / "bi" / "seki_raw"
_UA = "Mozilla/5.0 IMDR-bi"
_THROTTLE_S = 2.0


def download_survey_zip(slug: str, force: bool = False) -> Path:
    """Download a BI survey ZIP archive and extract the single XLSX.

    Slug examples: 'SK', 'spe', 'SKDU' (case must match BI's actual URL).
    Cached as ``{slug.upper()}.xlsx`` under ``data/econ/bi/seki_raw/``.
    """
    _RAW_DIR.mkdir(parents=True, exist_ok=True)
    out = _RAW_DIR / f"{slug.upper()}.xlsx"
    if out.exists() and not force:
        return out
    url = f"{_BASE}{slug}.zip"
    time.sleep(_THROTTLE_S)
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = resp.read()
    zf = zipfile.ZipFile(io.BytesIO(data))
    names = zf.namelist()
    if len(names) != 1:
        raise RuntimeError(
            f"BI survey ZIP {url} has {len(names)} entries (expected exactly 1: "
            f"{names!r}) — BI may have changed the archive structure"
        )
    out.write_bytes(zf.read(names[0]))
    return out


def parse_survey_rows(
    path: Path,
    sheet: str | int,
    *,
    rows: list[int],
    year_row: int,
    month_row: int,
    first_data_col: int,
) -> dict[int, list[tuple[datetime.date, float | None]]]:
    """Extract per-row time series from a survey XLSX.

    For each row_index in ``rows``, iterate columns starting at
    ``first_data_col`` and yield (period_start_date, value) tuples using
    the year row + month row for date inference.

    Returns dict keyed by row_index → list of (date, value). Skips
    columns where year or month is missing.
    """
    # XLSX extracted from the survey ZIP — pin openpyxl explicitly (SEKI
    # tables are .xls / xlrd; the asymmetry would otherwise be implicit).
    df = pd.read_excel(path, sheet_name=sheet, header=None, engine="openpyxl")
    if df.shape[0] <= max(year_row, month_row, *rows):
        return {}
    year_cells = list(df.iloc[year_row])
    month_cells = list(df.iloc[month_row])
    years = _infer_years(year_cells, month_cells)
    months = [_parse_month(v) for v in month_cells]

    out: dict[int, list[tuple[datetime.date, float | None]]] = {}
    for r in rows:
        series: list[tuple[datetime.date, float | None]] = []
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
            try:
                obs_date = datetime.date(year, month, 1)
            except (TypeError, ValueError):
                continue
            series.append((obs_date, value))
        out[r] = series
    return out
