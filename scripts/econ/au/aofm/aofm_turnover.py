"""Parse AOFM turnover XLSX files → econ.fact_indicator.

Covers four files:

  - ``new_turnover_-_treasury_bonds.xlsx``         Region + Counterparty
  - ``new_turnover_-_treasury_indexed_bonds.xlsx`` Region + Counterparty
  - ``turnover_-_treasury_bonds.xlsx``             By Tenor + By Category
  - ``turnover_-_treasury_indexed_bonds.xlsx``     By Tenor + By Category

"new_turnover" is the current AOFM publication (since Jan-2026, monthly,
raw AUD). The "Counterparty" sheet has the most analytically useful
investor-type breakdown (Bank Inter-Dealer / Bank Customer / Public
Entity / Pension / Insurance / Fund Manager / Hedge Fund / Retail /
Corporate).

The legacy "turnover" files run from 2016-07 in AUD millions:
"By Tenor" (5 buckets) is monthly; "By Category" (10 entity types) is
quarterly. We keep both for the longer history.
"""
from __future__ import annotations

import datetime as _dt
import sys
from pathlib import Path

import pandas as pd

from imdr.domains.econ.aofm_xlsx import XLSX_DIR, coerce_date, coerce_float, make_indicator, make_observation
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MMM_YY_RE = __import__("re").compile(r"^([A-Za-z]{3})-(\d{2})$")
_MMM_MAP = {"jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,
            "jul":7,"aug":8,"sep":9,"oct":10,"nov":11,"dec":12}


def _parse_period(v) -> _dt.date | None:
    """Accept datetime/Timestamp or 'Mmm-YY' strings (e.g. 'Jan-26').

    The Mmm-YY check runs FIRST because pandas.to_datetime would parse
    'Jan-26' as 26-January of year 0001 (wrong). Only fall through to
    ``coerce_date`` when the string is NOT in Mmm-YY format.
    """
    if isinstance(v, str):
        m = _MMM_YY_RE.match(v.strip())
        if m:
            mon = _MMM_MAP.get(m.group(1).lower())
            if mon is None:
                return None
            yy = int(m.group(2))
            year = 2000 + yy if yy < 80 else 1900 + yy
            return _dt.date(year, mon, 1)
    return coerce_date(v)


def _emit_series(
    df: pd.DataFrame, *,
    header_row: int, data_start: int,
    date_col: int, col_indexes: list[int],
    indicators: list[IndicatorRow], observations: list[ObservationRow],
    since_d: _dt.date | None, until_d: _dt.date | None,
    code_prefix: str, source_prefix: str, unit: str, frequency: str,
    label_overrides: dict[int, str] | None = None,
) -> None:
    label_overrides = label_overrides or {}
    for col in col_indexes:
        if col >= df.shape[1]:
            continue
        raw_label = label_overrides.get(col) or str(df.iat[header_row, col])
        suffix = (raw_label.upper()
                  .replace(" ", "_").replace("-", "_").replace("(", "")
                  .replace(")", "").replace(",", "").replace("'", "")
                  .replace("__", "_").strip("_"))
        imdr_code = f"{code_prefix}.{suffix}.AU"
        source_code = f"{source_prefix}.c{col}"
        ind = make_indicator(
            imdr_code=imdr_code, source_code=source_code,
            display_name=f"{code_prefix} — {raw_label.strip()} ({unit}, AOFM)",
            unit=unit, frequency=frequency, category="other",
        )
        kept = 0
        for r in range(data_start, df.shape[0]):
            d = _parse_period(df.iat[r, date_col])
            if d is None:
                continue
            if since_d and d < since_d: continue
            if until_d and d > until_d: continue
            v = coerce_float(df.iat[r, col])
            observations.append(make_observation(imdr_code=imdr_code, obs_date=d, value=v))
            kept += 1
        if kept == 0:
            print(f"  WARN {imdr_code:<55s} 0 obs")
            continue
        indicators.append(ind)
        print(f"  {imdr_code:<60s} {kept:>5} obs")


# ---------------------------------------------------------------------------
# File definitions
# ---------------------------------------------------------------------------

# Sheet config: (file_basename, sheet, header_row, data_start, date_col, col_range, code_prefix, unit, frequency)
_SHEETS = [
    # NEW turnover — TB
    ("new_turnover_-_treasury_bonds.xlsx",
     "Region", 3, 4, 1, list(range(2, 8)),
     "AOFM.TB_TURNOVER_REGION", "aud", "MONTHLY"),
    ("new_turnover_-_treasury_bonds.xlsx",
     "Counterparty", 3, 4, 0, list(range(1, 12)),
     "AOFM.TB_TURNOVER_CPTY", "aud", "MONTHLY"),

    # NEW turnover — TIB
    ("new_turnover_-_treasury_indexed_bonds.xlsx",
     "Region", 3, 4, 1, list(range(2, 8)),
     "AOFM.TIB_TURNOVER_REGION", "aud", "MONTHLY"),
    ("new_turnover_-_treasury_indexed_bonds.xlsx",
     "Counterparty", 3, 4, 0, list(range(1, 12)),
     "AOFM.TIB_TURNOVER_CPTY", "aud", "MONTHLY"),

    # LEGACY turnover — TB
    ("turnover_-_treasury_bonds.xlsx",
     "By Tenor", 1, 2, 0, list(range(1, 7)),
     "AOFM.TB_TURNOVER_TENOR_LEGACY", "aud_mn", "MONTHLY"),
    ("turnover_-_treasury_bonds.xlsx",
     "By Category", 1, 2, 0, list(range(1, 12)),
     "AOFM.TB_TURNOVER_CATEGORY_LEGACY", "aud_mn", "QUARTERLY"),

    # LEGACY turnover — TIB
    ("turnover_-_treasury_indexed_bonds.xlsx",
     "By Tenor", 1, 2, 0, list(range(1, 6)),
     "AOFM.TIB_TURNOVER_TENOR_LEGACY", "aud_mn", "MONTHLY"),
    ("turnover_-_treasury_indexed_bonds.xlsx",
     "By Category", 1, 2, 0, list(range(1, 12)),
     "AOFM.TIB_TURNOVER_CATEGORY_LEGACY", "aud_mn", "QUARTERLY"),
]


def run_fetch(since: str | None, until: str | None) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    since_d = _dt.date.fromisoformat(since) if since else None
    until_d = _dt.date.fromisoformat(until) if until else None

    indicators: list[IndicatorRow] = []
    observations: list[ObservationRow] = []

    for file_name, sheet, header_row, data_start, date_col, col_range, code_prefix, unit, frequency in _SHEETS:
        path = XLSX_DIR / file_name
        if not path.exists():
            print(f"  SKIP {file_name} (not on disk)")
            continue
        print(f"\n--- {file_name} / {sheet} ---")
        df = pd.read_excel(path, sheet_name=sheet, header=None)
        _emit_series(
            df, header_row=header_row, data_start=data_start, date_col=date_col,
            col_indexes=col_range, indicators=indicators, observations=observations,
            since_d=since_d, until_d=until_d,
            code_prefix=code_prefix, source_prefix=f"AOFM.{file_name}.{sheet}",
            unit=unit, frequency=frequency,
        )
    return indicators, observations


def main() -> int:
    return run_main(vendor="aofm", topic="turnover", fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "",
                    country_code="AU")


if __name__ == "__main__":
    sys.exit(main())
