"""KOSIS / KOSTAT Wages fetcher (DT_1YL15006).

Source: Statistics Korea (orgId=101), 월평균 임금 및 임금상승률(시도) —
Average Monthly Wage and Wage Growth Rate by Region (Annual).

We pull C1=00 (전국, national) × both items:
  T001  Regular Workers' Monthly Average Wage (KRW)
  T002  Wage Growth Rate (% YoY)

Cell mapping: 2.3 Domestic Costs (wage leg) → ❓ → ✅ (sparse — annual only,
no monthly wage series available on KOSIS at the headline level; the
sub-cuts by region are available but not pulled at this stage).

Usage:
    C:/Users/adoshi/.conda/envs/imdr/python.exe scripts/econ/kosis/kosis_wages.py
    python -m scripts.econ.kosis.kosis_wages
"""

from __future__ import annotations

import datetime

from imdr.domains.econ.kosis_http import fetch_kosis_table, make_session, parse_kosis_period
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

# ITM_ID → (suffix, display, unit)
_ITEMS: dict[str, tuple[str, str, str]] = {
    "T001": ("WAGE_LEVEL",  "Regular Workers' Monthly Average Wage", "krw"),
    "T002": ("WAGE_YOY",    "Wage Growth Rate (YoY %)",              "pct"),
}


def run_fetch(
    since: str | None,
    until: str | None,
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    session = make_session()
    since_dt = datetime.date.fromisoformat(since) if since else None
    until_dt = datetime.date.fromisoformat(until) if until else None
    now = datetime.datetime.now(UTC)

    print("  Fetching Wages: DT_1YL15006 (KOSTAT, orgId=101) ...", end=" ", flush=True)
    rows = fetch_kosis_table(
        session,
        org_id="101",
        tbl_id="DT_1YL15006",
        obj_l1="ALL",
        itm_id="ALL",
        prd_se="A",
        start_prd_de="2008",
        end_prd_de=str(datetime.date.today().year),
    )
    print(f"{len(rows)} rows")

    indicators: list[IndicatorRow] = []
    observations: list[ObservationRow] = []

    for itm_id, (suffix, display, unit) in _ITEMS.items():
        sub = [r for r in rows if r.get("ITM_ID") == itm_id and r.get("C1") == "00"]
        if not sub:
            print(f"  WARN: no national (C1=00) rows for {itm_id} ({suffix})")
            continue
        imdr_code = f"KOSTAT.WAGE.{suffix}.NATIONAL.KR"
        indicators.append(IndicatorRow(
            imdr_code=imdr_code,
            vendor_name="KOSIS",
            source_code=f"101/DT_1YL15006/C1=00/ITM_ID={itm_id}",
            display_name=f"Korea — {display}, national (KOSTAT, annual)",
            unit=unit,
            frequency="ANNUAL",
            country_iso="KR",
            category="labour",
            is_seasonally_adjusted=False,
            bbg_ticker=None,
        ))
        for r in sub:
            ymd = parse_kosis_period(r.get("PRD_DE"), "A")
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

    return indicators, observations


def main() -> int:
    return run_main(
        vendor="kosis",
        topic="wages",
        fetch_fn=run_fetch,
        description=__doc__.splitlines()[0] if __doc__ else "",
    )


if __name__ == "__main__":
    import sys
    sys.exit(main())
