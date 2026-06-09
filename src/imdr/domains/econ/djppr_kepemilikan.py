"""DJPPR Indonesia ``Kepemilikan SBN`` parser library.

DJPPR (Direktorat Jenderal Pengelolaan Pembiayaan dan Risiko, Indonesia's
Ministry of Finance debt-management directorate) publishes the daily
ownership of tradable IDR-denominated government securities (SBN) broken
down by **investor category** — banks, Bank Indonesia (net + gross),
mutual funds, insurance + pension, foreign holders (incl. foreign
official), individuals, and other. BI SEKI Table IV.4 only carries the
instrument totals and BI's own holdings; the full investor split is
DJPPR-exclusive.

This module owns three concerns:

1. **listing** — pull the per-year XLSX + per-month PDF index from the
   DJPPR listing API (no Playwright at runtime — the API is a plain
   public JSON endpoint).
2. **XLSX parser** — 12 monthly sheets, INSTITUSI rows × daily columns
   triplet (SUN / SBSN / TOTAL).
3. **PDF parser** — same logical table rendered as PyMuPDF tables.
   Carry-over label logic because PyMuPDF merges consecutive label cells.

The portal switched format in **January 2025**: XLSX for 2007–2024
annual files, PDF for monthly snapshots from 2025 onward. Both formats
emit the same canonical ``(obs_date, category, instrument, value)``
tuples.

Pre-2016 legacy XLSX (bilingual labels, BUMN/Swasta/Non-Rekap/BPD bank
taxonomy, SUN-only) is NOT handled here — tracked at IMD-42.
"""

from __future__ import annotations

import datetime
import json
import re
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import pandas as pd

# ---------------------------------------------------------------------------
# Listing API (replaces the Playwright discovery probe at runtime)
# ---------------------------------------------------------------------------

PORTAL_PAGE_URL = (
    "https://djppr.kemenkeu.go.id/kepemilikansbndomestikyangdapatdiperdagangkan"
)
LISTING_API_URL = (
    "https://api-djppr.kemenkeu.go.id/web/api/v1/page"
    "?url=kepemilikansbndomestikyangdapatdiperdagangkan"
)

_INDONESIAN_MONTH_TO_INT = {
    "januari": 1, "februari": 2, "maret": 3, "april": 4, "mei": 5, "juni": 6,
    "juli": 7, "agustus": 8, "september": 9, "oktober": 10, "november": 11,
    "desember": 12, "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6,
    "jul": 7, "agt": 8, "ags": 8, "sep": 9, "okt": 10, "nov": 11, "des": 12,
}

_UA = "Mozilla/5.0 IMDR-djppr"
_THROTTLE_S = 1.0


@dataclass(frozen=True)
class ListingEntry:
    """One published file in the DJPPR Kepemilikan SBN library."""

    title: str
    description: str
    link: str
    year: int | None
    granularity: str          # "daily" | "monthly" | "unknown"
    period_end_iso: str | None


def _parse_deskripsi(text: str) -> tuple[str, str | None]:
    """Return ``(granularity, period_end_iso)`` from a description string.

    Examples:
      "Data Harian s.d. 5 Juni 2026"      → ("daily",   "2026-06-05")
      "Data Bulanan: Jan 2003 s.d. Des"   → ("monthly", None)
    """
    t = text.strip().lower()
    granularity = (
        "daily" if "harian" in t
        else "monthly" if "bulanan" in t
        else "unknown"
    )
    period_end_iso = None
    m = re.search(r"(\d{1,2})\s+([a-z]+)\s+(\d{4})", t)
    if m:
        day = int(m.group(1))
        month = _INDONESIAN_MONTH_TO_INT.get(m.group(2))
        year = int(m.group(3))
        if month:
            try:
                period_end_iso = datetime.date(year, month, day).isoformat()
            except ValueError:
                pass
    return granularity, period_end_iso


def fetch_listing() -> list[ListingEntry]:
    """Hit the listing API and flatten its repeater into ListingEntry rows.

    The API returns ``Data.PageContentLive`` as a double-stringified JSON
    blob describing the page layout. Inside that tree there is exactly
    one widget with ``widgetType == "repeater"``; its ``data`` array is
    the list of downloadable files.
    """
    req = urllib.request.Request(LISTING_API_URL, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=60) as resp:
        body = resp.read().decode("utf-8")
    payload = json.loads(body)
    content = json.loads(payload["Data"]["PageContentLive"])

    def walk(node):
        if isinstance(node, list):
            for x in node:
                yield from walk(x)
        elif isinstance(node, dict):
            if node.get("widgetType") == "repeater":
                yield node
            for v in node.values():
                yield from walk(v)

    repeater = next(walk(content), None)
    if repeater is None:
        return []

    out: list[ListingEntry] = []
    for row in repeater.get("data") or []:
        if not isinstance(row, dict):
            continue
        title = row.get("@judul") or ""
        deskripsi = row.get("@deskripsi") or ""
        link = row.get("@link") or ""
        if not (title and link):
            continue
        year_match = re.search(r"(\d{4})", title)
        granularity, period_end_iso = _parse_deskripsi(deskripsi)
        out.append(ListingEntry(
            title=title,
            description=deskripsi,
            link=link,
            year=int(year_match.group(1)) if year_match else None,
            granularity=granularity,
            period_end_iso=period_end_iso,
        ))
    return out


def download(url: str, cache_dir: Path) -> tuple[Path, str]:
    """Download a media URL with content-type sniffing.

    Returns ``(path, file_ext)`` where ``file_ext`` is ``"xlsx"`` or
    ``"pdf"``. Cached: a second call for the same URL re-uses the
    on-disk copy.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    # The URL itself is content-type-agnostic; sniff the magic bytes after
    # download to decide the extension.
    stem = "media_" + re.sub(r"[^A-Za-z0-9-]+", "_", url.rsplit("/", 1)[-1])
    for ext in ("xlsx", "pdf"):
        path = cache_dir / f"{stem}.{ext}"
        if path.exists():
            return path, ext
    time.sleep(_THROTTLE_S)
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = resp.read()
    ext = "pdf" if data[:4] == b"%PDF" else "xlsx"
    path = cache_dir / f"{stem}.{ext}"
    path.write_bytes(data)
    return path, ext


# ---------------------------------------------------------------------------
# Canonical taxonomy
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Category:
    code: str
    display: str
    indonesian: str
    is_subline: bool


# 12 canonical investor categories × 3 instruments = 36 indicators.
# Stable order: aggregates → sub-rows; matches the row order in source files.
CATEGORIES: list[Category] = [
    Category("BANK",             "Banks (total)",         "BANK*",                              False),
    Category("BANK_CONV",        "Conventional banks",    "Bank Konvensional",                  True),
    Category("BANK_SHARIA",      "Islamic banks",         "Bank Syariah",                       True),
    Category("BI_NET",           "Bank Indonesia (net)",  "Bank Indonesia (net)",               False),
    Category("BI_GROSS",         "Bank Indonesia (gross)","Bank Indonesia (gross)",             True),
    Category("MF",               "Mutual funds",          "Reksadana",                          False),
    Category("INSUR_PENSION",    "Insurance + pension",   "Asuransi dan Dana Pensiun",          False),
    Category("FOREIGN",          "Foreign (non-resident)","Non Residen",                        False),
    Category("FOREIGN_OFFICIAL", "Foreign official",      "Pemerintah & Bank Sentral Asing",    True),
    Category("INDIVIDUAL",       "Individuals (retail)",  "Individu",                           False),
    Category("OTHER",            "Other",                 "Lain-lain",                          False),
    Category("TOTAL",            "Total",                 "TOTAL",                              False),
]

INSTRUMENTS: tuple[str, ...] = ("SUN", "SBSN", "TOTAL")


def imdr_code(category: str, instrument: str) -> str:
    return f"DJPPR.SBN.HOLD.{category}.{instrument}.IDR.ID"


def display_name(category: Category, instrument: str) -> str:
    return (
        f"Indonesia SBN — {category.display} — {instrument} holdings "
        f"(DJPPR Kepemilikan SBN, Triliun Rp)"
    )


# Label matching is substring-on-lowercased. ORDER IS LOAD-BEARING:
# FOREIGN_OFFICIAL must come BEFORE any pattern containing "bank" because the
# label "Pemerintah & Bank Sentral Negara Asing" (= foreign central bank)
# contains the word "bank" and would otherwise be miscategorised as a domestic
# bank. Never add a generic "bank" fallback — only the specific labels.
_LABEL_MATCHERS: tuple[tuple[str, str], ...] = (
    ("FOREIGN_OFFICIAL", "pemerintah & bank sentral"),
    ("FOREIGN_OFFICIAL", "termasuk pemerintah"),
    ("BANK_CONV",        "bank konvensional"),
    ("BANK_SHARIA",      "bank syariah"),
    ("BI_GROSS",         "bank indonesia (gross"),
    ("BI_NET",           "bank indonesia"),
    ("BANK",             "bank*"),
    ("MF",               "reksadana"),
    ("INSUR_PENSION",    "asuransi"),
    ("FOREIGN",          "non residen"),
    ("FOREIGN",          "non-residen"),
    ("INDIVIDUAL",       "individu"),
    ("OTHER",            "lain-lain"),
    ("TOTAL",            "total"),
)

_WS_RE = re.compile(r"\s+")


def classify_label(raw: str) -> str | None:
    """Return the canonical CATEGORY code for a row label, or None if unknown.

    Strips Indonesian leading dashes (used for sub-lines) before matching.
    """
    if not raw:
        return None
    norm = _WS_RE.sub(" ", str(raw).lower().strip()).lstrip("- ").strip()
    for code, pat in _LABEL_MATCHERS:
        if pat in norm:
            return code
    return None


# ---------------------------------------------------------------------------
# Number parsing — Indonesian / European format
# ---------------------------------------------------------------------------

_NUM_OK_RE = re.compile(r"^[-()0-9.,\s]+$")


def parse_id_number(s) -> float | None:
    """Parse Indonesian-format number string to float.

    Conventions: thousand separator ``.``, decimal separator ``,``,
    negatives parenthesised ``(x,xx)``. ``"-"`` alone means zero (used
    for e.g. Bank Syariah SUN, which can't hold conventional bonds).
    """
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s)
    raw = str(s).strip()
    if not raw or raw == "-" or raw.lower() in {"nan", "n/a", "na"}:
        return None
    if not _NUM_OK_RE.match(raw):
        return None
    negative = raw.startswith("(") and raw.endswith(")")
    if negative:
        raw = raw[1:-1]
    raw = raw.replace(".", "").replace(",", ".")
    try:
        v = float(raw)
    except ValueError:
        return None
    return -v if negative else v


# ---------------------------------------------------------------------------
# XLSX parser  (2016-2024 annual files; layout = 12 sheets, daily cols)
# ---------------------------------------------------------------------------

ParsedObs = tuple[datetime.date, str, str, float]


def _coerce_date(cell) -> datetime.date | None:
    if cell is None or (isinstance(cell, float) and pd.isna(cell)):
        return None
    if isinstance(cell, datetime.datetime):
        return cell.date()
    if isinstance(cell, datetime.date):
        return cell
    try:
        return pd.to_datetime(cell).date()
    except Exception:  # noqa: BLE001
        return None


def _xlsx_find_section_a(df: pd.DataFrame) -> tuple[int, int] | None:
    """Locate ``(date_row_idx, sub_header_row_idx)`` for Section A.

    Section A (absolute values, Triliun Rupiah) starts at a row whose first
    cell begins with "INSTITUSI" and whose next row contains SUN/SBSN.
    """
    for r in range(min(20, df.shape[0])):
        c0 = df.iat[r, 0]
        if not isinstance(c0, str):
            continue
        if c0.strip().upper().startswith("INSTITUSI") and r + 1 < df.shape[0]:
            nxt = [
                str(df.iat[r + 1, c]).strip().upper()
                for c in range(min(6, df.shape[1]))
                if df.iat[r + 1, c] is not None
            ]
            if "SUN" in nxt and "SBSN" in nxt:
                return r, r + 1
    return None


def _xlsx_section_b_start(df: pd.DataFrame) -> int:
    """Row index where Section B (percentages) begins, or len(df) if absent."""
    for r in range(df.shape[0]):
        c0 = df.iat[r, 0]
        if isinstance(c0, str) and c0.strip().startswith("B."):
            return r
    return df.shape[0]


def _xlsx_date_columns(
    df: pd.DataFrame, date_row: int,
) -> list[tuple[int, datetime.date]]:
    out: list[tuple[int, datetime.date]] = []
    for c in range(1, df.shape[1]):
        d = _coerce_date(df.iat[date_row, c])
        if d is not None:
            out.append((c, d))
    return out


def parse_xlsx_sheet(df: pd.DataFrame) -> list[ParsedObs]:
    """Parse one monthly sheet (Section A only) into observation tuples."""
    secA = _xlsx_find_section_a(df)
    if secA is None:
        return []
    date_row, sub_row = secA
    secB_row = _xlsx_section_b_start(df)
    date_cols = _xlsx_date_columns(df, date_row)
    if not date_cols:
        return []
    out: list[ParsedObs] = []
    seen_bi_net = False
    for r in range(sub_row + 1, secB_row):
        raw_label = df.iat[r, 0]
        if not isinstance(raw_label, str):
            continue
        cat = classify_label(raw_label)
        if cat is None:
            continue
        # BI_NET row appears FIRST, BI_GROSS row second — both labels share
        # the prefix "Bank Indonesia", so flip BI_NET → BI_GROSS on the
        # second encounter.
        if cat == "BI_NET":
            if seen_bi_net:
                cat = "BI_GROSS"
            else:
                seen_bi_net = True
        for col_idx, obs_date in date_cols:
            for offset, instr in enumerate(INSTRUMENTS):
                if col_idx + offset >= df.shape[1]:
                    continue
                v = parse_id_number(df.iat[r, col_idx + offset])
                if v is None:
                    continue
                out.append((obs_date, cat, instr, v))
    return out


def parse_xlsx(path: Path) -> Iterator[ParsedObs]:
    xl = pd.ExcelFile(path)
    for sheet in xl.sheet_names:
        df = pd.read_excel(path, sheet_name=sheet, header=None)
        yield from parse_xlsx_sheet(df)


# ---------------------------------------------------------------------------
# PDF parser  (2025+ monthly snapshots; PyMuPDF table extraction)
# ---------------------------------------------------------------------------

_PDF_DATE_RE = re.compile(r"(\d{1,2})[- ]([A-Za-z]{3,4})[- ](\d{2,4})")
_PDF_MON_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "mei": 5, "jun": 6,
    "jul": 7, "aug": 8, "agt": 8, "ags": 8, "sep": 9, "oct": 10, "okt": 10,
    "nov": 11, "dec": 12, "des": 12,
}


def _pdf_parse_date(s) -> datetime.date | None:
    if s is None:
        return None
    m = _PDF_DATE_RE.search(str(s).strip())
    if not m:
        return None
    day = int(m.group(1))
    month = _PDF_MON_MAP.get(m.group(2).lower()[:3])
    if month is None:
        return None
    year_raw = int(m.group(3))
    year = year_raw + 2000 if year_raw < 100 else year_raw
    try:
        return datetime.date(year, month, day)
    except ValueError:
        return None


def _pdf_date_columns(
    header_row: list, sub_header_row: list,
) -> list[tuple[int, datetime.date]]:
    """Return [(col_index, date)] for each date cell in the header row.

    A date column spans 3 sub-columns (SUN / SBSN / TOTAL); we confirm by
    checking the next row starts with SUN at the same column index.
    """
    out: list[tuple[int, datetime.date]] = []
    for c, cell in enumerate(header_row):
        d = _pdf_parse_date(cell)
        if d is None:
            continue
        if c + 2 < len(sub_header_row):
            triple = [str(sub_header_row[c + k]).strip().upper() for k in range(3)]
            if "SUN" in triple[0]:
                out.append((c, d))
    return out


def _pdf_emit_row(
    label: str,
    value_cells: list,
    date_cols: list[tuple[int, datetime.date]],
    bi_net_seen: list[bool],
    sub_idx: int,
) -> list[ParsedObs]:
    """Emit observations for one logical row given an already-known label.

    ``sub_idx`` is the line offset within each value cell — when a label
    block had multiple labels but the data was in *one* row, every label
    reads a different ``\\n``-line of the cell. When labels and data are in
    *separate* rows (PyMuPDF's later carry-over rows), ``sub_idx`` is 0.
    """
    cat = classify_label(label)
    if cat is None:
        return []
    if cat == "BI_NET":
        if bi_net_seen[0]:
            cat = "BI_GROSS"
        else:
            bi_net_seen[0] = True
    out: list[ParsedObs] = []
    for col_idx, obs_date in date_cols:
        for offset, instr in enumerate(INSTRUMENTS):
            if col_idx + offset >= len(value_cells):
                continue
            vc = value_cells[col_idx + offset]
            if vc is None:
                continue
            vc_lines = [s.strip() for s in str(vc).split("\n")]
            if sub_idx >= len(vc_lines):
                continue
            v = parse_id_number(vc_lines[sub_idx])
            if v is None:
                continue
            out.append((obs_date, cat, instr, v))
    return out


def parse_pdf(path: Path) -> Iterator[ParsedObs]:
    """Yield observation tuples from every page's Section-A table.

    PyMuPDF's ``find_tables(strategy="lines")`` recovers the daily table
    cleanly except for one quirk: runs of contiguous row labels get merged
    into the first row's label cell, leaving subsequent rows with
    ``label=None``. We pop labels off a queue to recover the mapping.
    """
    import fitz  # PyMuPDF — local import to avoid pulling at module load
    doc = fitz.open(path)
    bi_net_seen = [False]
    try:
        for page in doc:
            tables = page.find_tables(strategy="lines")
            if not tables.tables:
                continue
            section_a = tables.tables[0]
            rows = section_a.extract()
            if len(rows) < 3:
                continue

            # Header detection tolerates both page-1 layout (col 0 = INSTITUSI)
            # and later pages (col 0 = first date directly).
            date_cols: list[tuple[int, datetime.date]] = []
            data_start = 0
            for hdr_idx in range(min(3, len(rows) - 1)):
                cand = _pdf_date_columns(rows[hdr_idx], rows[hdr_idx + 1])
                if cand:
                    date_cols = cand
                    data_start = hdr_idx + 2
                    break
            if not date_cols:
                continue

            bi_net_seen[0] = False
            pending_labels: list[str] = []
            for r_idx in range(data_start, len(rows)):
                row = rows[r_idx]
                if not row:
                    continue
                label = row[0]
                if isinstance(label, str) and label.strip():
                    label_lines = [s.strip() for s in label.split("\n") if s.strip()]
                    if not label_lines:
                        continue
                    first_label = label_lines[0]
                    pending_labels = label_lines[1:]

                    # If value cells are themselves multi-line, the extra
                    # labels read different sub-lines of the SAME row.
                    sample_val = row[1] if len(row) > 1 else None
                    multi_value_lines = (
                        isinstance(sample_val, str) and "\n" in sample_val
                    )
                    if multi_value_lines:
                        for sub_idx, lab in enumerate(label_lines):
                            yield from _pdf_emit_row(
                                lab, row, date_cols, bi_net_seen, sub_idx,
                            )
                        pending_labels = []
                    else:
                        # Drop parenthetical continuations like "(net, tidak
                        # termasuk...)" that aren't real categories.
                        pending_labels = [
                            lab for lab in pending_labels
                            if not lab.startswith("(") and classify_label(lab) is not None
                        ]
                        yield from _pdf_emit_row(
                            first_label, row, date_cols, bi_net_seen, 0,
                        )
                else:
                    # No label on this row — pop the next queued label.
                    if not pending_labels:
                        continue
                    next_lab = pending_labels.pop(0)
                    yield from _pdf_emit_row(
                        next_lab, row, date_cols, bi_net_seen, 0,
                    )
    finally:
        doc.close()
