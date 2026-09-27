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
import re
import time
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd

from imdr.domains.econ.bi_seki import _infer_years, _parse_month

_BASE = "https://www.bi.go.id/id/publikasi/laporan/Documents/"
_REPO_ROOT = Path(__file__).resolve().parents[4]
_RAW_DIR = _REPO_ROOT / "data" / "econ" / "id" / "bi" / "seki_raw"
_UA = "Mozilla/5.0 IMDR-bi"
_THROTTLE_S = 2.0


def download_survey_zip(slug: str, force: bool = False) -> Path:
    """Download a BI survey ZIP archive and extract the single XLSX.

    Slug examples: 'SK', 'spe', 'SKDU' (case must match BI's actual URL).
    Cached as ``{slug.upper()}.xlsx`` under ``data/econ/id/bi/seki_raw/``.
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


# ---------------------------------------------------------------------------
# Per-edition archives (PMI, Survei Perbankan) — URL must be DISCOVERED
# ---------------------------------------------------------------------------
#
# `download_survey_zip` above works because SK / spe / SKDU are published at a
# STABLE slug (`.../Documents/SKDU.zip`) that always holds the latest edition.
#
# The Prompt Manufacturing Index and Survei Perbankan are NOT like that. Each
# edition gets its own filename, and BI is not consistent about it:
#
#     Data-Series-PMI-Triwulan-II-2026.zip          (Q2 2026)
#     PMI-Triwulan-I-2026.zip                       (Q1 2026 — no prefix!)
#     Data-Series-PMI-Tw-IV-2025.zip                (Q4 2025 — "Tw" not "Triwulan")
#     Data-Series-Survei-Perbank-Tw-IV-2025.zip     ("Perbank", truncated)
#
# So no slug template works, and one built from the current quarter would go
# silently stale the moment BI renamed the token again — the failure mode that
# killed `rbi_bulletin` for three weeks. The only durable approach is to read
# the href off the listing, which is what `discover_latest_data_series_zip`
# does.
#
# NOTE ON DUPLICATION: `scripts/econ/id/govt/_bi_aspnet.py` parses the same
# listing markup for Track B (documents). The overlap here is deliberately
# kept to the single `media__title` anchor pattern rather than importing it —
# `src/imdr/` must not depend on `scripts/`, and Track B needs FilingItem rows
# while Track A needs only one href. If a third caller appears, promote the
# listing parser into this layer and have Track B wrap it.

_LISTING_BASE = "https://www.bi.go.id/id/publikasi/laporan/default.aspx"
_BI_ROOT = "https://www.bi.go.id"

# Both row variants BI uses; the reports listing is the `box-list__hyperlink`
# one, but matching both makes this robust if BI swaps the template.
_DETAIL_HREF = re.compile(
    r'<a\s+href="(/id/publikasi/laporan/Pages/[^"]+\.aspx)"', re.I
)
_ZIP_HREF = re.compile(r'href="([^"]+\.zip)"', re.I)


def discover_latest_data_series_zip(kategori: str) -> tuple[str, str]:
    """Find the newest edition's data-series ZIP for a BI report category.

    `kategori` is one of BI's own `?Kategori=` values, e.g.
    ``"prompt manufacturing index"`` or ``"survei perbankan"`` (lower-case,
    literal spaces — see `scripts/econ/id/govt/_bi_aspnet.BI_REPORT_CATEGORIES`
    for the authoritative list of 21).

    Returns ``(zip_url, detail_url)``. Raises RuntimeError if the category has
    no editions or the newest edition carries no ZIP — both are real
    conditions worth failing loudly on rather than returning empty, per
    [[feedback-silent-fetcher-failure-detection]].

    The listing is date-ordered newest-first, so the first detail link is the
    current edition.
    """
    listing_url = f"{_LISTING_BASE}?Kategori={urllib.parse.quote(kategori)}"
    listing = _get_text(listing_url)
    m = _DETAIL_HREF.search(listing)
    if not m:
        raise RuntimeError(
            f"BI category {kategori!r} returned no detail links — the "
            f"?Kategori= filter or the listing template changed "
            f"({listing_url})"
        )
    detail_url = _BI_ROOT + m.group(1)
    detail = _get_text(detail_url)
    z = _ZIP_HREF.search(detail)
    if not z:
        raise RuntimeError(
            f"BI edition {detail_url} has no .zip attachment — BI may have "
            f"stopped publishing the data series for {kategori!r} (the PDF is "
            f"not a substitute)"
        )
    href = z.group(1)
    return (href if href.startswith("http") else _BI_ROOT + href), detail_url


def download_data_series_zip(kategori: str, cache_name: str,
                            force: bool = False) -> Path:
    """Discover + download the newest data-series XLSX for a BI category.

    Cached as ``{cache_name}.xlsx`` under ``data/econ/id/bi/seki_raw/``.
    Unlike `download_survey_zip` the URL is resolved at run time, so the
    cache filename is supplied by the caller rather than derived from a slug.
    """
    _RAW_DIR.mkdir(parents=True, exist_ok=True)
    out = _RAW_DIR / f"{cache_name}.xlsx"
    if out.exists() and not force:
        return out
    zip_url, _detail = discover_latest_data_series_zip(kategori)
    time.sleep(_THROTTLE_S)
    req = urllib.request.Request(zip_url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = resp.read()
    zf = zipfile.ZipFile(io.BytesIO(data))
    names = zf.namelist()
    if len(names) != 1:
        raise RuntimeError(
            f"BI data-series ZIP {zip_url} has {len(names)} entries "
            f"(expected exactly 1: {names!r})"
        )
    # The inner XLSX filename also varies per edition ("Tabel PMI-BI Tw II
    # 2026.xlsx"), which is why it is never used as the cache key.
    out.write_bytes(zf.read(names[0]))
    return out


def _get_text(url: str) -> str:
    time.sleep(_THROTTLE_S)
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8", errors="replace")


def forecast_periods(
    path: Path,
    sheet: str | int,
    *,
    year_row: int,
    month_row: int,
    first_data_col: int,
) -> set[datetime.date]:
    """Periods BI marks as a PROJECTION, not an actual.

    BI publishes the *next* quarter's estimate inside the current edition and
    flags it with a trailing asterisk in the period row, explained by a
    footnote ``* Ket : Angka Perkiraan`` ("estimated figure"). Concretely, the
    Q2-2026 PMI edition carries a ``III*`` column holding BI's Q3-2026
    forecast.

    Those columns parse exactly like actuals -- `_parse_month` reads "III*" as
    Q3 -- so a fetcher that does not filter them lands a forecast in
    `econ.fact_indicator` indistinguishable from a print, and it never gets
    corrected because the next edition writes the same period as an actual and
    the revision-aware loader treats the change as a legitimate vintage bump.

    Returns the set of period-start dates to exclude. Callers should drop
    observations on these dates rather than trying to reason about columns.

    ⚠️ **Only validated for the PMI / Survei Perbankan "Angka Perkiraan"
    convention** (the per-edition data-series archives reached via
    `download_data_series_zip`). Elsewhere in BI's output a trailing `*` /
    `**` can mean **preliminary** — a real observation that is merely
    provisional — which is a different thing entirely. `bi_seki._parse_month`
    documents that usage. Do NOT apply this to the stable-slug surveys
    (SK / SPE / SKDU) or to SEKI tables without first reading the sheet's own
    footnote: on a "preliminary" table this would silently discard genuine
    prints.
    """
    df = pd.read_excel(path, sheet_name=sheet, header=None, engine="openpyxl")
    if df.shape[0] <= max(year_row, month_row):
        return set()
    year_cells = list(df.iloc[year_row])
    month_cells = list(df.iloc[month_row])
    years = _infer_years(year_cells, month_cells)
    out: set[datetime.date] = set()
    for c in range(first_data_col, df.shape[1]):
        raw = month_cells[c] if c < len(month_cells) else None
        if not isinstance(raw, str) or "*" not in raw:
            continue
        month = _parse_month(raw)
        year = years[c] if c < len(years) else None
        if month is None or year is None:
            continue
        try:
            out.add(datetime.date(year, month, 1))
        except (TypeError, ValueError):
            continue
    return out
