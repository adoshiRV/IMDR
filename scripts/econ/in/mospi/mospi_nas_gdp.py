"""MOSPI National Accounts — annual + quarterly GDP/GVA/expenditure.

Source: MOSPI "Provisional Estimates of Annual GDP" press release.
Statements.xls (legacy .xls — xlrd) contains:

  Statement1A-2A  — annual GDP/GVA + expenditure components × 4 FYs,
                    real (constant 2022-23 prices) rows 1-40 and
                    nominal (current prices) rows 43-84.
  Statements 5A-8A — quarterly real levels × Q1-Q4 across FYs 2022-23
                    to 2025-26 (16 quarters).

Emits 30+ indicators × small N each (~250 obs from a single release).
Old 2011-12 base back-history (>2022) lives in earlier press releases
and is deferred — promote when MOSPI ships a re-spliced series.

Cell mapping (see docs/admin/econ/india/in_coverage_plan.md):
  1.1 Output gap / activity — GDP / GVA headline + sectoral
  2.2 Capex / investment   — GFCF
  3.1 External demand      — Exports / Imports
"""
from __future__ import annotations

import datetime
import io
import re
import warnings

import httpx
import xlrd

from imdr.domains.econ.mospi import HEADERS, list_releases, fetch_attachment
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

warnings.filterwarnings("ignore")

UTC = datetime.timezone.utc

_ANNUAL_LABELS: dict[str, str] = {
    "GVA at Basic Prices":                              "GVA_BASIC",
    "Net Taxes on Products":                            "NET_TAXES",
    "Gross Domestic Product (GDP)":                     "GDP",
    "Gross Domestic Product (GDP) ":                    "GDP",
    "Net Domestic Product (NDP)":                       "NDP",
    "Private Final Consumption Expenditure (PFCE)":     "PFCE",
    "Government Final Consumption Expenditure (GFCE)":  "GFCE",
    "Gross Fixed Capital Formation (GFCF)":             "GFCF",
    "Changes in Stocks (CIS)":                          "CIS",
    "Exports":                                          "EXPORTS",
    "Imports":                                          "IMPORTS",
    "Gross National Income (GNI)":                      "GNI",
    "Net National Income (NNI)":                        "NNI",
}

_QUARTERLY_LABELS: dict[str, str] = {
    "1. Primary Sector":                                  "GVA_PRIMARY",
    "2. Secondary Sector":                                "GVA_SECONDARY",
    "3. Tertiary Sector":                                 "GVA_TERTIARY",
    "GVA at Basic Prices":                                "GVA_BASIC",
    "Net Taxes":                                          "NET_TAXES",
    "GDP":                                                "GDP",
    "1. Private Final Consumption Expenditure (PFCE)":    "PFCE",
    "2. Government Final Consumption Expenditure (GFCE)": "GFCE",
    "3. Gross Fixed Capital Formation (GFCF)":            "GFCF",
    "6. Exports":                                         "EXPORTS",
    "7. Imports":                                         "IMPORTS",
}

_FY_RE = re.compile(r"(\d{4})-(\d{2})")


def _parse_fy(cell_text) -> datetime.date | None:
    if not cell_text:
        return None
    m = _FY_RE.search(str(cell_text))
    if not m:
        return None
    return datetime.date(int(m.group(1)), 4, 1)


def _fetch_latest_gdp_xls(client: httpx.Client) -> tuple[str, bytes]:
    for item in list_releases(client, "Provisional Estimates of Annual GDP"):
        attach = item.get("file_two") or {}
        path = (attach.get("path") or "").lower()
        if not path.endswith((".xls", ".xlsx")):
            continue
        return item["title"], fetch_attachment(client, attach["path"])
    raise RuntimeError("no GDP release with XLS found")


def _parse_annual(
    wb, header_row_idx: int, base_label: str, now: datetime.datetime,
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    indicators: list[IndicatorRow] = []
    observations: list[ObservationRow] = []
    ws = wb.sheet_by_name("Statement1A-2A")
    header_row = ws.row_values(header_row_idx)
    fy_cols: list[tuple[int, datetime.date]] = []
    for j, val in enumerate(header_row):
        dt = _parse_fy(val)
        if dt is not None:
            fy_cols.append((j, dt))
    if not fy_cols:
        print(f"  [annual {base_label}] no FY columns in header row {header_row_idx}")
        return indicators, observations

    n_rows_max = 40 if base_label == "REAL_2022_23" else ws.nrows
    for r in range(header_row_idx + 1, n_rows_max):
        label = str(ws.cell_value(r, 2)).strip() if r < ws.nrows else ""
        if not label or label.startswith(("Share in GDP", "Domestic", "Expenditure Components")):
            continue
        stem = _ANNUAL_LABELS.get(label) or _ANNUAL_LABELS.get(label.rstrip())
        if stem is None:
            continue
        imdr_code = f"INDIA.GDP_NAS.{stem}.{base_label}.ANNUAL.IN"
        unit_label = "constant prices 2022-23" if base_label == "REAL_2022_23" else "current prices"
        indicators.append(IndicatorRow(
            imdr_code=imdr_code, vendor_name="MOSPI",
            source_code=f"MOSPI/NAS/Statement1A-2A/{base_label}/{stem}",
            display_name=f"India NAS {label} — annual ({unit_label}, INR crore)",
            unit="inr_cr", frequency="ANNUAL", country_iso="IN",
            category="gdp", is_seasonally_adjusted=False, bbg_ticker=None,
        ))
        for col, dt in fy_cols:
            v = ws.cell_value(r, col) if col < ws.ncols else None
            try:
                value = float(v)
            except (ValueError, TypeError):
                continue
            observations.append(ObservationRow(
                imdr_code=imdr_code, obs_date=dt, vintage=0,
                release_date=now, value=value, ingested_at=now,
            ))
    return indicators, observations


def _parse_quarterly(
    wb, now: datetime.datetime,
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    indicators: list[IndicatorRow] = []
    observations: list[ObservationRow] = []
    ws = wb.sheet_by_name("Statements 5A-8A")
    fy_row = ws.row_values(3)
    q_row = ws.row_values(5)

    q_cols: list[tuple[int, datetime.date]] = []
    current_fy: datetime.date | None = None
    qmap = {"Q1": 4, "Q2": 7, "Q3": 10, "Q4": 1}
    for j in range(ws.ncols):
        fy_val = str(fy_row[j]).strip() if j < len(fy_row) else ""
        if fy_val:
            dt = _parse_fy(fy_val)
            if dt is not None:
                current_fy = dt
        q_val = str(q_row[j]).strip() if j < len(q_row) else ""
        if q_val in qmap and current_fy:
            year_off = 1 if q_val == "Q4" else 0
            q_cols.append((j, datetime.date(current_fy.year + year_off, qmap[q_val], 1)))
    print(f"  [quarterly] {len(q_cols)} quarterly columns mapped")
    if not q_cols:
        return indicators, observations

    # Row labels live in col 1 (col 0 is bullet indent); data starts at col 2.
    for r in range(6, min(30, ws.nrows)):
        label = str(ws.cell_value(r, 1)).strip()
        stem = _QUARTERLY_LABELS.get(label)
        if stem is None:
            continue
        imdr_code = f"INDIA.GDP_NAS.{stem}.REAL_2022_23.QUARTERLY.IN"
        indicators.append(IndicatorRow(
            imdr_code=imdr_code, vendor_name="MOSPI",
            source_code=f"MOSPI/NAS/Statement5/REAL_2022_23/{stem}",
            display_name=f"India NAS {label} — quarterly real (constant 2022-23 prices, INR crore)",
            unit="inr_cr", frequency="QUARTERLY", country_iso="IN",
            category="gdp", is_seasonally_adjusted=False, bbg_ticker=None,
        ))
        for col, dt in q_cols:
            v = ws.cell_value(r, col) if col < ws.ncols else None
            try:
                value = float(v)
            except (ValueError, TypeError):
                continue
            observations.append(ObservationRow(
                imdr_code=imdr_code, obs_date=dt, vintage=0,
                release_date=now, value=value, ingested_at=now,
            ))
    return indicators, observations


def run_fetch(
    since: str | None,
    until: str | None,
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    since_dt = datetime.date.fromisoformat(since) if since else None
    until_dt = datetime.date.fromisoformat(until) if until else None
    now = datetime.datetime.now(UTC)

    with httpx.Client(timeout=60, follow_redirects=True) as c:
        print("  fetching latest GDP release...")
        title, blob = _fetch_latest_gdp_xls(c)
        print(f"    {title}")
        print(f"    {len(blob)} bytes")

    wb = xlrd.open_workbook(file_contents=blob)
    indicators: list[IndicatorRow] = []
    observations: list[ObservationRow] = []
    seen: set[str] = set()

    # Statement 5 lists labels (GDP / GVA_BASIC / NET_TAXES) twice — once
    # under the sector cut, once under the expenditure cut. Same numbers
    # both sides by construction; dedup on (imdr_code, obs_date).
    seen_obs: set[tuple[str, datetime.date]] = set()

    for inds, obs in (
        _parse_annual(wb, 2, "REAL_2022_23", now),
        _parse_annual(wb, 44, "NOMINAL", now),
        _parse_quarterly(wb, now),
    ):
        for i in inds:
            if i.imdr_code not in seen:
                indicators.append(i)
                seen.add(i.imdr_code)
        for o in obs:
            if since_dt and o.obs_date < since_dt:
                continue
            if until_dt and o.obs_date > until_dt:
                continue
            key = (o.imdr_code, o.obs_date)
            if key in seen_obs:
                continue
            seen_obs.add(key)
            observations.append(o)
    return indicators, observations


def main() -> int:
    return run_main(vendor="mospi", topic="nas_gdp",
                    fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "",
                    country_code="IN")


if __name__ == "__main__":
    import sys
    sys.exit(main())
