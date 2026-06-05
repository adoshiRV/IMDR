"""KOSIS / KOSTAT CPI change-rate fetcher (DT_1J22042).

Source: Statistics Korea (KOSTAT, orgId=101), 월별 소비자물가 등락률
(Monthly Consumer Price Index change rates).

The table publishes pct-change rates (MoM / YoY / YTD) for 5 CPI cuts:
  C1=0  총지수                    Headline CPI
  C1=1  생활물가지수                Living-cost CPI (necessaries basket)
  C1=2  신선식품지수                Fresh food CPI
  C1=3  농산물및석유류제외지수        CPI excl. agri + petroleum (trimmed core)
  C1=4  식료품및에너지제외지수        CPI excl. food + energy (standard core)

Each cut × 3 change-rate items (T02 MoM, T03 YoY, T04 YTD) = 15 indicators.

Cell mapping: 2.4 CPI Pressure + start of 2.1 Input Costs (fresh food + energy
sub-cuts feed input-cost analysis indirectly).

Usage:
    C:/Users/adoshi/.conda/envs/imdr/python.exe scripts/econ/kosis/kosis_cpi.py
    C:/Users/adoshi/.conda/envs/imdr/python.exe scripts/econ/kosis/kosis_cpi.py --since 2020-01-01 --no-parquet
    python -m scripts.econ.kosis.kosis_cpi
"""

from __future__ import annotations

import datetime

from imdr.domains.econ.kosis_http import fetch_kosis_table, make_session, parse_kosis_period
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

# C1 code → (suffix, display_suffix)
_CUTS: dict[str, tuple[str, str]] = {
    "0": ("HEADLINE",   "Headline CPI"),
    "1": ("LIVING",     "Living-cost CPI"),
    "2": ("FRESH_FOOD", "Fresh-food CPI"),
    "3": ("EXAGRI_OIL", "CPI excl. agri + petroleum (trimmed core)"),
    "4": ("EXFOOD_NRG", "CPI excl. food + energy (standard core)"),
}

# ITM_ID → (suffix, display_suffix, kind)
_ITEMS: dict[str, tuple[str, str]] = {
    "T02": ("MOM",  "MoM %"),
    "T03": ("YOY",  "YoY %"),
    "T04": ("YTD",  "YTD %"),
}


def run_fetch(
    since: str | None,
    until: str | None,
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    session = make_session()
    since_dt = datetime.date.fromisoformat(since) if since else None
    until_dt = datetime.date.fromisoformat(until) if until else None
    now = datetime.datetime.now(UTC)

    print("  Fetching CPI: DT_1J22042 (KOSTAT, orgId=101) ...", end=" ", flush=True)
    rows = fetch_kosis_table(
        session,
        org_id="101",
        tbl_id="DT_1J22042",
        obj_l1="ALL",
        itm_id="ALL",
        prd_se="M",
        start_prd_de="200001",
        end_prd_de=datetime.date.today().strftime("%Y%m"),
    )
    print(f"{len(rows)} rows")

    indicators: list[IndicatorRow] = []
    observations: list[ObservationRow] = []

    for c1_code, (cut_suffix, cut_display) in _CUTS.items():
        for itm_id, (item_suffix, item_display) in _ITEMS.items():
            imdr_code = f"KOSTAT.CPI.{cut_suffix}.{item_suffix}.KR"
            display = f"Korea {cut_display}, {item_display} (KOSTAT)"
            indicators.append(IndicatorRow(
                imdr_code=imdr_code,
                vendor_name="KOSIS",
                source_code=f"101/DT_1J22042/C1={c1_code}/ITM_ID={itm_id}",
                display_name=display,
                unit="pct",
                frequency="MONTHLY",
                country_iso="KR",
                category="cpi",
                is_seasonally_adjusted=False,
                bbg_ticker=None,
            ))
            obs_count = 0
            for r in rows:
                if r.get("C1") != c1_code or r.get("ITM_ID") != itm_id:
                    continue
                ymd = parse_kosis_period(r.get("PRD_DE"), "M")
                if ymd is None:
                    continue
                obs_date = datetime.date(*ymd)
                if since_dt and obs_date < since_dt:
                    continue
                if until_dt and obs_date > until_dt:
                    continue
                try:
                    value = float(r["DT"]) if r.get("DT") not in (None, "") else None
                except (TypeError, ValueError):
                    value = None
                observations.append(ObservationRow(
                    imdr_code=imdr_code,
                    obs_date=obs_date,
                    vintage=0,
                    release_date=now,
                    value=value,
                    ingested_at=now,
                ))
                obs_count += 1
            if obs_count == 0:
                # No rows for this (C1, ITM) cross — pop the indicator so we don't
                # emit an empty series.
                indicators.pop()

    return indicators, observations


def main() -> int:
    return run_main(
        vendor="kosis",
        topic="cpi",
        fetch_fn=run_fetch,
        description=__doc__.splitlines()[0] if __doc__ else "",
    )


if __name__ == "__main__":
    import sys
    sys.exit(main())
