"""Parse AOFM ``portfolio_aggregate_-_dealt_4.xlsx`` → econ.fact_indicator.

This is the monthly snapshot of AOFM's debt-portfolio book by instrument
category (Treasury Bonds, Treasury Indexed Bonds, Treasury Notes, Repos,
plus legacy "Other Borrowings"). Two sheets carry the same instrument set
on different measurement bases:

  - FaceValue   — par-value outstanding (no MTM)
  - MarketValue — market value outstanding (with MTM)

Sign convention: AOFM stores liabilities as **negative** (they are owed
by the Australian government). We preserve the raw sign — downstream
analytics should treat AUD-outstanding magnitudes by ``abs(value)`` when
the sign would mislead. (Two BoP measures in our own `econ.fact_indicator`
already use this convention.)

Skipped columns: small legacy "Other Borrowings" sub-items (Federal
Airport Corp Loan, Snowy Mountains Hydro-Electric, Tax Free Stock,
Overdue Loans, State Debt Raisings) — kept only the aggregate.
The 57-column "by-bond-line" detail lives in
``portfolio_aggregate_-_treasury_bonds_-_settlement.xlsx`` etc. and is
out of scope for econ (would need a separate bond-instrument schema).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from imdr.domains.econ.aofm_xlsx import XLSX_DIR, coerce_date, coerce_float, make_indicator, make_observation
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main


XLSX_PATH = XLSX_DIR / "portfolio_aggregate_-_dealt_4.xlsx"


# (col_index, imdr_code_suffix, display_name) — same column set for both sheets.
_COLUMNS = [
    (1,  "TB",         "Treasury Bonds outstanding"),
    (2,  "TIB_CI",     "Treasury Indexed Bonds (Capital Indexed) outstanding"),
    (3,  "TN",         "Treasury Notes outstanding"),
    (4,  "TOTAL_MAIN", "Total AUD Main Funding Instruments outstanding"),
    (5,  "TIB_II",     "Treasury Indexed Bonds (Interest Indexed) outstanding"),
    (6,  "REPO",       "Repurchase Agreements outstanding"),
    (7,  "TOTAL_OTHER_FUNDING", "Total AUD Other Funding Instruments outstanding"),
    (13, "TOTAL_OTHER_BORROWINGS", "Total AUD Other Borrowings outstanding (legacy)"),
]

# (sheet, metric_code, display_suffix) — applied to each column above
_SHEETS = [
    ("FaceValue",   "FACE",   "(face value)"),
    ("MarketValue", "MARKET", "(market value)"),
]


def _find_data_start(df: pd.DataFrame) -> int:
    """Find the first row whose col 0 is a date (data row), past the header block."""
    for r in range(20):
        if r >= df.shape[0]:
            break
        d = coerce_date(df.iat[r, 0])
        if d is not None:
            return r
    raise RuntimeError("could not locate first data row")


def _parse_sheet(path: Path, sheet: str) -> dict[int, list]:
    df = pd.read_excel(path, sheet_name=sheet, header=None)
    start = _find_data_start(df)
    out: dict[int, list] = {}
    for r in range(start, df.shape[0]):
        d = coerce_date(df.iat[r, 0])
        if d is None:
            continue
        for col_idx in {c[0] for c in _COLUMNS}:
            if col_idx >= df.shape[1]:
                continue
            out.setdefault(col_idx, []).append((d, df.iat[r, col_idx]))
    return out


def run_fetch(since: str | None, until: str | None) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    import datetime as _dt
    since_d = _dt.date.fromisoformat(since) if since else None
    until_d = _dt.date.fromisoformat(until) if until else None

    if not XLSX_PATH.exists():
        print(f"  ERROR: {XLSX_PATH} not on disk — manual download required")
        return [], []

    indicators: list[IndicatorRow] = []
    observations: list[ObservationRow] = []
    parsed: dict[str, dict[int, list]] = {}

    for sheet, metric_code, display_suffix in _SHEETS:
        parsed[sheet] = _parse_sheet(XLSX_PATH, sheet)
        for col_idx, suffix, display in _COLUMNS:
            imdr_code = f"AOFM.PORTFOLIO.{suffix}_{metric_code}.AU"
            source_code = f"AOFM.portfolio_aggregate_dealt.{sheet}.c{col_idx}"
            ind = make_indicator(
                imdr_code=imdr_code, source_code=source_code,
                display_name=f"AOFM portfolio — {display} {display_suffix} (AUD, raw — liability sign)",
                unit="aud", frequency="MONTHLY", category="instr_outstand",
            )
            kept = 0
            for d, raw in parsed[sheet].get(col_idx, []):
                if since_d and d < since_d: continue
                if until_d and d > until_d: continue
                v = coerce_float(raw)
                observations.append(make_observation(imdr_code=imdr_code, obs_date=d, value=v))
                kept += 1
            if kept == 0:
                print(f"  WARN {imdr_code:<50s} 0 obs")
                continue
            indicators.append(ind)
            print(f"  {imdr_code:<55s} {kept:>5} obs")
    return indicators, observations


def main() -> int:
    return run_main(vendor="aofm", topic="portfolio_aggregate", fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "",
                    country_code="AU")


if __name__ == "__main__":
    sys.exit(main())
