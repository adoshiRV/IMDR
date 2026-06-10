"""Parse AOFM ``foreign_holdings.xlsx`` → econ.fact_indicator.

The file has 3 data sheets — each is a monthly/quarterly time series of
non-resident participation in a slice of Australian Government Securities:

  - AGS          (Total AGS = Bonds + Indexed Bonds + Notes)
  - LongTermAGS  (Treasury Bonds + Treasury Indexed Bonds — excludes Notes)
  - ShortTermAGS (Treasury Notes)

Per sheet, the columns we extract (header on row 5):

  AGS / LongTermAGS / ShortTermAGS — common:
    - Non-Resident Holdings (raw AUD)
    - Total Outstanding (raw AUD)
    - Proportion Held by Non-Residents (ratio)
    - Owing to Net Transactions (A)         — attribution
    - Owing to Valuation (B)                — attribution
    - Total Change in Market Value (C)      — attribution

  AGS / LongTermAGS only (Notes don't have repo data):
    - Repo Outflow / Repo Inflow / Net Repo Outflow (AUD)
    - Total Held by Non-Residents Adjusted for Net Repo Outflow (AUD)
    - Proportion Adjusted (ratio)
    - Change in Net Repo Outflow (D)        — attribution
    - Net Transactions after Repo Adj (E)   — attribution

  LongTermAGS only:
    - Long-Term AGS Held by RBA (AUD; 'TBA' for historical → NaN)
    - Proportion Held by Non-Resident ex-RBA (ratio)

Frequency: the file appears quarterly historically; recent rows are
monthly. Treat all sheets as QUARTERLY for the dim (the sparse monthly
in-between rows still resolve to month-end dates and dedup by obs_date).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from imdr.domains.econ.aofm_xlsx import XLSX_DIR, coerce_date, coerce_float, make_indicator, make_observation
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main


XLSX_PATH = XLSX_DIR / "foreign_holdings.xlsx"


# (sheet, col_index, imdr_code_suffix, display_name, unit) tuples.
# The data starts on row 6 (0-indexed). Column 0 is obs_date.
_AGS = "AGS"
_LT = "LongTermAGS"
_ST = "ShortTermAGS"

_SERIES = [
    # ----- AGS sheet (total AGS = bonds + indexed bonds + notes) ---------------------
    (_AGS, 1,  "TOTAL_NONRES_HOLDINGS",       "AOFM total AGS held by non-residents (AUD)", "aud"),
    (_AGS, 2,  "TOTAL_OUTSTANDING",           "AOFM total AGS outstanding (AUD)",            "aud"),
    (_AGS, 3,  "TOTAL_NONRES_PROPORTION",     "AOFM proportion of total AGS held by non-residents", "ratio"),
    (_AGS, 4,  "TOTAL_REPO_OUTFLOW",          "AOFM total AGS repo outflow (AUD)",           "aud"),
    (_AGS, 5,  "TOTAL_REPO_INFLOW",           "AOFM total AGS repo inflow (AUD)",            "aud"),
    (_AGS, 6,  "TOTAL_NET_REPO_OUTFLOW",      "AOFM total AGS net repo outflow (AUD)",       "aud"),
    (_AGS, 7,  "TOTAL_NONRES_HOLDINGS_REPO_ADJ", "AOFM total AGS non-resident holdings adjusted for net repo (AUD)", "aud"),
    (_AGS, 8,  "TOTAL_NONRES_PROPORTION_REPO_ADJ", "AOFM total AGS proportion held by non-residents (repo-adjusted)", "ratio"),
    (_AGS, 9,  "TOTAL_ATTR_NET_TXN",          "AOFM total AGS attribution — net transactions (AUD)",   "aud"),
    (_AGS, 10, "TOTAL_ATTR_VALUATION",        "AOFM total AGS attribution — valuation (AUD)",          "aud"),
    (_AGS, 11, "TOTAL_ATTR_CHG_MV",           "AOFM total AGS attribution — total change in MV (AUD)", "aud"),
    (_AGS, 12, "TOTAL_ATTR_CHG_NET_REPO",     "AOFM total AGS attribution — change in net repo (AUD)", "aud"),
    (_AGS, 13, "TOTAL_ATTR_NET_TXN_REPO_ADJ", "AOFM total AGS attribution — net transactions repo-adjusted (AUD)", "aud"),

    # ----- LongTermAGS sheet (Treasury Bonds + Indexed Bonds) -----------------------
    (_LT, 1,  "LT_NONRES_HOLDINGS",           "AOFM long-term AGS held by non-residents (AUD)",         "aud"),
    (_LT, 2,  "LT_OUTSTANDING",               "AOFM long-term AGS outstanding (AUD)",                    "aud"),
    (_LT, 3,  "LT_HELD_BY_RBA",               "AOFM long-term AGS held by RBA (AUD; 'TBA' historical)",  "aud"),
    (_LT, 4,  "LT_NONRES_PROPORTION",         "AOFM proportion of long-term AGS held by non-residents",  "ratio"),
    (_LT, 5,  "LT_NONRES_PROPORTION_EX_RBA",  "AOFM proportion of long-term AGS held by non-residents (ex-RBA)", "ratio"),
    (_LT, 6,  "LT_REPO_OUTFLOW",              "AOFM long-term AGS repo outflow (AUD)",                   "aud"),
    (_LT, 7,  "LT_REPO_INFLOW",               "AOFM long-term AGS repo inflow (AUD)",                    "aud"),
    (_LT, 8,  "LT_NET_REPO_OUTFLOW",          "AOFM long-term AGS net repo outflow (AUD)",               "aud"),
    (_LT, 9,  "LT_NONRES_HOLDINGS_REPO_ADJ",  "AOFM long-term AGS non-resident holdings adjusted for net repo (AUD)", "aud"),
    (_LT, 10, "LT_NONRES_PROPORTION_REPO_ADJ", "AOFM long-term AGS proportion held by non-residents (repo-adjusted)", "ratio"),
    (_LT, 11, "LT_ATTR_NET_TXN",              "AOFM long-term AGS attribution — net transactions (AUD)",   "aud"),
    (_LT, 12, "LT_ATTR_VALUATION",            "AOFM long-term AGS attribution — valuation (AUD)",          "aud"),
    (_LT, 13, "LT_ATTR_CHG_MV",               "AOFM long-term AGS attribution — total change in MV (AUD)", "aud"),
    (_LT, 14, "LT_ATTR_CHG_NET_REPO",         "AOFM long-term AGS attribution — change in net repo (AUD)", "aud"),
    (_LT, 15, "LT_ATTR_NET_TXN_REPO_ADJ",     "AOFM long-term AGS attribution — net transactions repo-adjusted (AUD)", "aud"),

    # ----- ShortTermAGS sheet (Treasury Notes only) ----------------------------------
    (_ST, 1, "ST_NONRES_HOLDINGS",       "AOFM short-term AGS (notes) held by non-residents (AUD)", "aud"),
    (_ST, 2, "ST_OUTSTANDING",           "AOFM short-term AGS (notes) outstanding (AUD)",            "aud"),
    (_ST, 3, "ST_NONRES_PROPORTION",     "AOFM short-term AGS proportion held by non-residents",     "ratio"),
    (_ST, 4, "ST_ATTR_NET_TXN",          "AOFM short-term AGS attribution — net transactions (AUD)",  "aud"),
    (_ST, 5, "ST_ATTR_VALUATION",        "AOFM short-term AGS attribution — valuation (AUD)",         "aud"),
    (_ST, 6, "ST_ATTR_CHG_MV",           "AOFM short-term AGS attribution — total change in MV (AUD)", "aud"),
]

_DATA_START_ROW = 6  # row 0-5 are headers, data from row 6 onward


def _parse_sheet(path: Path, sheet: str) -> dict[int, list]:
    """Read one sheet, return ``{col_index: [(obs_date, raw_value), ...]}``."""
    df = pd.read_excel(path, sheet_name=sheet, header=None)
    out: dict[int, list] = {}
    for r in range(_DATA_START_ROW, df.shape[0]):
        d = coerce_date(df.iat[r, 0])
        if d is None:
            continue
        for c in range(1, df.shape[1]):
            out.setdefault(c, []).append((d, df.iat[r, c]))
    return out


def run_fetch(since: str | None, until: str | None) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    import datetime as _dt
    since_d = _dt.date.fromisoformat(since) if since else None
    until_d = _dt.date.fromisoformat(until) if until else None

    if not XLSX_PATH.exists():
        print(f"  ERROR: {XLSX_PATH} not on disk — manual download required")
        return [], []

    parsed: dict[str, dict[int, list]] = {}
    indicators: list[IndicatorRow] = []
    observations: list[ObservationRow] = []

    for sheet, col, suffix, display, unit in _SERIES:
        if sheet not in parsed:
            parsed[sheet] = _parse_sheet(XLSX_PATH, sheet)
        rows = parsed[sheet].get(col, [])
        imdr_code = f"AOFM.HOLDINGS.{suffix}.AU"
        source_code = f"AOFM.foreign_holdings.{sheet}.c{col}"
        ind = make_indicator(
            imdr_code=imdr_code, source_code=source_code, display_name=display,
            unit=unit, frequency="QUARTERLY", category="instr_outstand",
        )
        kept_obs = 0
        for d, raw in rows:
            if since_d and d < since_d:
                continue
            if until_d and d > until_d:
                continue
            v = coerce_float(raw)
            observations.append(make_observation(imdr_code=imdr_code, obs_date=d, value=v))
            kept_obs += 1
        if kept_obs == 0:
            print(f"  WARN {imdr_code:<45s} 0 obs (col not present?)")
            continue
        indicators.append(ind)
        print(f"  {imdr_code:<48s} {kept_obs:>5} obs")
    return indicators, observations


def main() -> int:
    return run_main(vendor="aofm", topic="foreign_holdings", fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "",
                    country_code="AU")


if __name__ == "__main__":
    sys.exit(main())
