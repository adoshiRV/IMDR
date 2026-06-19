"""DPIIT/OEA Wholesale Price Index — headline + first-level sub-aggregates.

Source: Office of Economic Adviser (under DPIIT) at
``eaindustry.nic.in/indx_download_1112/monthly_index_YYYYMM.xls``.

Each monthly XLS carries the FULL back-history (Apr 2012 → latest) on
Base 2011-12=100. We pull only the headline + 7 first-level aggregates
(~8 indicators × 169 mo ≈ 1,350 obs). The ~860 commodity-level rows
are deferred — promotable as a second fetcher if commodity granularity
is needed.

Cell mapping (see docs/admin/econ/india/in_coverage_plan.md):
  1.2 Producer prices — INDIA.WPI.HEADLINE.LEVEL.IN
  1.5 Energy passthrough — FUEL_POWER / CRUDE_NG
"""
from __future__ import annotations

import datetime
import re
import warnings

import httpx
import xlrd

from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

warnings.filterwarnings("ignore")

UTC = datetime.timezone.utc

_BASE = "https://eaindustry.nic.in"
_INDEX_DIR = f"{_BASE}/indx_download_1112"
_LIST_URL = f"{_BASE}/download_data_1112.asp"
_UA = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 Chrome/120 Safari/537.36"),
    "Referer": _BASE + "/",
}

_CODE_MAP: dict[str, tuple[str, str]] = {
    "1000000000": ("HEADLINE",     "India WPI — All Commodities (DPIIT/OEA Base 2011-12)"),
    "1100000000": ("PRIMARY",      "India WPI — Primary Articles (DPIIT/OEA Base 2011-12)"),
    "1101000000": ("FOOD_ART",     "India WPI — Food Articles (DPIIT/OEA Base 2011-12)"),
    "1102000000": ("NONFOOD_ART",  "India WPI — Non-Food Articles (DPIIT/OEA Base 2011-12)"),
    "1103000000": ("MINERALS",     "India WPI — Minerals (DPIIT/OEA Base 2011-12)"),
    "1104000000": ("CRUDE_NG",     "India WPI — Crude Petroleum & Natural Gas (DPIIT/OEA Base 2011-12)"),
    "1200000000": ("FUEL_POWER",   "India WPI — Fuel & Power (DPIIT/OEA Base 2011-12)"),
    "1300000000": ("MFG",          "India WPI — Manufactured Products (DPIIT/OEA Base 2011-12)"),
}

_INDX_RE = re.compile(r"INDX(\d{2})(\d{4})$")
_MONTH_FILE_RE = re.compile(r"monthly_index_(\d{6})\.xls")


def _discover_latest(client: httpx.Client) -> str:
    r = client.get(_LIST_URL, headers=_UA, timeout=30)
    r.raise_for_status()
    files = _MONTH_FILE_RE.findall(r.text)
    if not files:
        raise RuntimeError("no monthly_index_YYYYMM.xls link on DPIIT page")
    return f"{_INDEX_DIR}/monthly_index_{max(files)}.xls"


def _parse_month_col(label: str) -> datetime.date | None:
    m = _INDX_RE.match(label.strip())
    if not m:
        return None
    try:
        return datetime.date(int(m.group(2)), int(m.group(1)), 1)
    except ValueError:
        return None


def run_fetch(
    since: str | None,
    until: str | None,
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    since_dt = datetime.date.fromisoformat(since) if since else None
    until_dt = datetime.date.fromisoformat(until) if until else None
    now = datetime.datetime.now(UTC)

    with httpx.Client(timeout=120, follow_redirects=True) as c:
        url = _discover_latest(c)
        print(f"  latest WPI XLS: {url}")
        rf = c.get(url, headers=_UA)
        rf.raise_for_status()
        blob = rf.content
    print(f"  {len(blob)} bytes")

    wb = xlrd.open_workbook(file_contents=blob)
    ws = wb.sheet_by_index(0)

    header = ws.row_values(0)
    date_cols: list[tuple[int, datetime.date]] = []
    for j, h in enumerate(header):
        if not isinstance(h, str):
            continue
        dt = _parse_month_col(h)
        if dt is not None:
            date_cols.append((j, dt))
    print(f"  {len(date_cols)} monthly columns; "
          f"{date_cols[0][1]} → {date_cols[-1][1]}")

    indicators: list[IndicatorRow] = []
    observations: list[ObservationRow] = []
    seen: set[str] = set()

    for r in range(1, ws.nrows):
        cell = ws.cell_value(r, 1)
        code = str(int(cell)) if isinstance(cell, float) else str(cell).strip()
        mapped = _CODE_MAP.get(code)
        if mapped is None:
            continue
        stem, display = mapped
        imdr_code = f"INDIA.WPI.{stem}.LEVEL.IN"
        if imdr_code not in seen:
            # WPI is wholesale/producer prices, not consumer; no "ppi" category
            # exists yet in VALID_CATEGORIES — tracked in
            # docs/admin/econ/india/in_coverage_plan.md.
            indicators.append(IndicatorRow(
                imdr_code=imdr_code, vendor_name="DPIIT",
                source_code=f"DPIIT/OEA/WPI_2011_12/{code}",
                display_name=display,
                unit="index", frequency="MONTHLY",
                country_iso="IN", category="other",
                is_seasonally_adjusted=False, bbg_ticker=None,
            ))
            seen.add(imdr_code)
        for col, dt in date_cols:
            if since_dt and dt < since_dt:
                continue
            if until_dt and dt > until_dt:
                continue
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


def main() -> int:
    return run_main(vendor="dpiit", topic="wpi",
                    fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "",
                    country_code="IN")


if __name__ == "__main__":
    import sys
    sys.exit(main())
