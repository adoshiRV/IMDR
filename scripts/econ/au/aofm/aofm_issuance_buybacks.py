"""Parse AOFM issuance + buyback files → econ.fact_indicator.

Per-tender transaction records aggregated to monthly totals. Files:

  Issuance:
    - treasury bonds - issuance.xlsx           (TB, since 1982)
    - Treasury Indexed Bonds - Issuance_0.xlsx (TIB, since 1985)
    - Treasury Notes - Issuance.xlsx           (TN, since 1989)

  Buybacks:
    - treasury bonds - buybacks.xlsx           (TB, since 2012)
    - treasury indexed bonds - buybacks.xlsx   (TIB, since 2014)

For each file we produce two monthly series:
  - Amount Allotted (or Repurchased)  — total face value transacted
  - Amount of Bids (or Offers)         — demand-side total

Bid-to-cover ratio is derivable downstream as Bids / Allotted.

Sign convention: issuance is positive (new debt issued); buybacks are
reported as positive face-value amounts (the action is "repurchased
this much face").
"""
from __future__ import annotations

import datetime as _dt
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

from imdr.domains.econ.aofm_xlsx import XLSX_DIR, coerce_date, coerce_float, make_indicator, make_observation
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main


# (file_basename, sheet, prefix_code, prefix_display, allotted_col, bids_col, date_col, header_row)
_FILES = [
    ("treasury bonds - issuance.xlsx", "Transactions",
     "TB_ISSUANCE", "Treasury Bonds issuance", 6, 7, 0, 1),
    ("Treasury Indexed Bonds - Issuance_0.xlsx", "Transactions",
     "TIB_ISSUANCE", "Treasury Indexed Bonds issuance", 6, 7, 0, 1),
    ("Treasury Notes - Issuance.xlsx", "Transactions",
     "TN_ISSUANCE", "Treasury Notes issuance", 5, 6, 0, 1),
    ("treasury bonds - buybacks.xlsx", "Transactions",
     "TB_BUYBACK", "Treasury Bonds buyback", 5, 6, 0, 1),
    ("treasury indexed bonds - buybacks.xlsx", "Transactions",
     "TIB_BUYBACK", "Treasury Indexed Bonds buyback", 5, 6, 0, 1),
]


def _aggregate_monthly(path: Path, sheet: str, date_col: int, value_col: int, header_row: int) -> dict[_dt.date, float]:
    df = pd.read_excel(path, sheet_name=sheet, header=None)
    out: dict[_dt.date, float] = defaultdict(float)
    for r in range(header_row + 1, df.shape[0]):
        d = coerce_date(df.iat[r, date_col])
        if d is None:
            continue
        v = coerce_float(df.iat[r, value_col])
        if v is None:
            continue
        month_start = _dt.date(d.year, d.month, 1)
        out[month_start] += v
    return dict(out)


def run_fetch(since: str | None, until: str | None) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    since_d = _dt.date.fromisoformat(since) if since else None
    until_d = _dt.date.fromisoformat(until) if until else None

    indicators: list[IndicatorRow] = []
    observations: list[ObservationRow] = []

    for file_name, sheet, prefix_code, prefix_display, allotted_col, bids_col, date_col, header_row in _FILES:
        path = XLSX_DIR / file_name
        if not path.exists():
            print(f"  SKIP {file_name} (not on disk)")
            continue
        print(f"\n--- {file_name} ---")
        for measure_label, col, suffix in [
            ("FACE_VALUE", allotted_col, "AMOUNT"),
            ("BIDS_OR_OFFERS", bids_col, "BIDS"),
        ]:
            try:
                monthly = _aggregate_monthly(path, sheet, date_col, col, header_row)
            except Exception as exc:
                print(f"  ERROR reading col {col}: {exc}")
                continue
            imdr_code = f"AOFM.{prefix_code}.{suffix}_MONTHLY.AU"
            source_code = f"AOFM.{file_name}.col{col}_monthly_sum"
            unit = "aud"
            ind = make_indicator(
                imdr_code=imdr_code, source_code=source_code,
                display_name=f"AOFM {prefix_display} monthly aggregate — {measure_label} (AUD)",
                unit=unit, frequency="MONTHLY", category="other",
            )
            kept = 0
            for d, v in sorted(monthly.items()):
                if since_d and d < since_d: continue
                if until_d and d > until_d: continue
                observations.append(make_observation(imdr_code=imdr_code, obs_date=d, value=v))
                kept += 1
            if kept == 0:
                print(f"  WARN {imdr_code:<48s} 0 obs")
                continue
            indicators.append(ind)
            print(f"  {imdr_code:<55s} {kept:>5} obs")
    return indicators, observations


def main() -> int:
    return run_main(vendor="aofm", topic="issuance_buybacks", fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "",
                    country_code="AU")


if __name__ == "__main__":
    sys.exit(main())
