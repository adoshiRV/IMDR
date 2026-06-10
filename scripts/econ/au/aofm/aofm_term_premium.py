"""Parse AOFM ``term premium.xlsx`` → econ.fact_indicator.

AOFM publishes a daily decomposition of AGS zero-coupon yields into
risk-neutral expected-rate + term-premium components, derived from a
Kim-Wright-style affine term structure model. Two sheets carry the
same series under two estimation methods:

  - TermPremiumOLS — Ordinary Least Squares fit
  - TermPremiumBC  — Bias-Corrected (the published one; we ingest this)

Column families (10 tenors each, FY1..FY10, in % per annum):
  FY{n}  — Fitted yield at n-year tenor (the curve itself)
  TP{n}  — Term-premium component
  RNY{n} — Risk-neutral expected-rate component (FY = TP + RNY)

Headline desk-screen reads TP10 (the AU 10y term premium) — RBA cites
this in MP reviews. We ingest all 30 series; downstream analytics can
select.

Frequency: DAILY since 1992-07-01.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from imdr.domains.econ.aofm_xlsx import XLSX_DIR, coerce_date, coerce_float, make_indicator, make_observation
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main


XLSX_PATH = XLSX_DIR / "term premium.xlsx"
SHEET = "TermPremiumBC"

# Column structure: c0 = DATE; c1..c10 = FY1..FY10; c11..c20 = TP1..TP10; c21..c30 = RNY1..RNY10
_FAMILIES = [
    ("FY",  "FITTED_YIELD",        "AOFM fitted yield {tenor}Y (bias-corrected, %)"),
    ("TP",  "TERM_PREMIUM",        "AOFM term premium {tenor}Y (bias-corrected, %)"),
    ("RNY", "RISK_NEUTRAL_YIELD",  "AOFM risk-neutral expected yield {tenor}Y (bias-corrected, %)"),
]


def run_fetch(since: str | None, until: str | None) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    import datetime as _dt
    since_d = _dt.date.fromisoformat(since) if since else None
    until_d = _dt.date.fromisoformat(until) if until else None

    if not XLSX_PATH.exists():
        print(f"  ERROR: {XLSX_PATH} not on disk — manual download required")
        return [], []

    df = pd.read_excel(XLSX_PATH, sheet_name=SHEET, header=None)
    # Header row contains 'DATE' in c0. Data starts the row after.
    header_row = None
    for r in range(5):
        if str(df.iat[r, 0]).strip().upper() == "DATE":
            header_row = r; break
    if header_row is None:
        raise RuntimeError("could not find DATE header row")
    data_start = header_row + 1

    indicators: list[IndicatorRow] = []
    observations: list[ObservationRow] = []

    # 30 columns: c1..c30 → FY1..FY10, TP1..TP10, RNY1..RNY10
    for col in range(1, 31):
        # Resolve family + tenor from header label
        label = str(df.iat[header_row, col]).strip()
        family_prefix = None
        for prefix in ("FY", "TP", "RNY"):
            if label.startswith(prefix) and label[len(prefix):].isdigit():
                family_prefix = prefix
                tenor = int(label[len(prefix):])
                break
        if family_prefix is None:
            print(f"  WARN col {col} unexpected label {label!r}; skipping")
            continue
        family = next(f for f in _FAMILIES if f[0] == family_prefix)
        _, code_root, display_tpl = family
        imdr_code = f"AOFM.TERM_PREMIUM.{code_root}_{tenor}Y.AU"
        source_code = f"AOFM.term_premium_BC.{label}"
        ind = make_indicator(
            imdr_code=imdr_code, source_code=source_code,
            display_name=display_tpl.format(tenor=tenor),
            unit="pct", frequency="DAILY", category="rates",
        )
        kept = 0
        for r in range(data_start, df.shape[0]):
            d = coerce_date(df.iat[r, 0])
            if d is None:
                continue
            if since_d and d < since_d: continue
            if until_d and d > until_d: continue
            v = coerce_float(df.iat[r, col])
            observations.append(make_observation(imdr_code=imdr_code, obs_date=d, value=v))
            kept += 1
        if kept == 0:
            print(f"  WARN {imdr_code:<45s} 0 obs")
            continue
        indicators.append(ind)
        print(f"  {imdr_code:<50s} {kept:>6} obs")
    return indicators, observations


def main() -> int:
    return run_main(vendor="aofm", topic="term_premium", fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "",
                    country_code="AU")


if __name__ == "__main__":
    sys.exit(main())
