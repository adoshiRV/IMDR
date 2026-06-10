"""KOSIS / KOSTAT Industrial Production + Capacity Utilisation fetcher.

Sources (KOSTAT orgId=101):
  - **DT_1JH20202** — 전산업생산지수(계절조정지수) All-Industry Production Index,
    SA, monthly, 2020=100. 5 cuts (Total + Industrial + Services + Construction +
    Public Administration).
  - **DT_1F32002** — 제조업 평균가동률 Manufacturing Average Capacity Utilisation
    Rate, monthly, %.

Cell mapping: 1.4 Macro Core (output gap leg) + 2.3 Domestic Costs
(capacity-utilisation leg).

Indicators (6):
  KOSTAT.IIP.ALL.SA.KR             Index of all industry production, SA
  KOSTAT.IIP.INDUSTRY.SA.KR        Industrial production, SA
  KOSTAT.IIP.SERVICES.SA.KR        Service Industry production, SA
  KOSTAT.IIP.CONSTRUCTION.SA.KR    Construction production, SA
  KOSTAT.IIP.PUBLIC.SA.KR          Public administration, SA
  KOSTAT.CAP_UTIL.MFG.KR           Manufacturing average capacity utilisation rate

Usage:
    C:/Users/adoshi/.conda/envs/imdr/python.exe scripts/econ/kr/kosis/kosis_industrial.py
    python -m scripts.econ.kr.kosis.kosis_industrial
"""

from __future__ import annotations

import datetime

from imdr.domains.econ.kosis_http import fetch_kosis_table, make_session, parse_kosis_period
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

_IIP_CUTS = {
    "1":  ("ALL",          "Index of all industry production"),
    "1B": ("INDUSTRY",     "Industrial production"),
    "1C": ("SERVICES",     "Service Industry production"),
    "1D": ("CONSTRUCTION", "Construction production"),
    "1E": ("PUBLIC",       "Public administration"),
}


def run_fetch(since, until):
    session = make_session()
    since_dt = datetime.date.fromisoformat(since) if since else None
    until_dt = datetime.date.fromisoformat(until) if until else None
    now = datetime.datetime.now(UTC)
    today = datetime.date.today()
    indicators, observations = [], []

    # IIP table
    print("  Fetching IIP DT_1JH20202 ...", end=" ", flush=True)
    rows = fetch_kosis_table(
        session, org_id="101", tbl_id="DT_1JH20202",
        obj_l1="ALL", itm_id="ALL", prd_se="M",
        start_prd_de="200001", end_prd_de=today.strftime("%Y%m"),
    )
    print(f"{len(rows)} rows")
    for c1, (suffix, display) in _IIP_CUTS.items():
        sub = [r for r in rows if (r.get("C1") or "").split(".")[-1] == c1]
        if not sub: continue
        code = f"KOSTAT.IIP.{suffix}.SA.KR"
        indicators.append(IndicatorRow(
            imdr_code=code, vendor_name="KOSIS",
            source_code=f"101/DT_1JH20202/C1={c1}",
            display_name=f"Korea — {display}, SA, 2020=100 (KOSTAT)",
            unit="index", frequency="MONTHLY", country_iso="KR",
            category="gdp", is_seasonally_adjusted=True, bbg_ticker=None,
        ))
        for r in sub:
            ymd = parse_kosis_period(r.get("PRD_DE"), "M")
            if ymd is None: continue
            d = datetime.date(*ymd)
            if since_dt and d < since_dt: continue
            if until_dt and d > until_dt: continue
            try: v = float(r["DT"]) if r.get("DT") not in (None, "") else None
            except (TypeError, ValueError): v = None
            observations.append(ObservationRow(
                imdr_code=code, obs_date=d, vintage=0,
                release_date=now, value=v, ingested_at=now,
            ))

    # Mfg Capacity Util
    print("  Fetching Mfg Capacity Util DT_1F32002 ...", end=" ", flush=True)
    rows = fetch_kosis_table(
        session, org_id="101", tbl_id="DT_1F32002",
        obj_l1="ALL", itm_id="ALL", prd_se="M",
        start_prd_de="198001", end_prd_de=today.strftime("%Y%m"),
    )
    print(f"{len(rows)} rows")
    sub = [r for r in rows if r.get("ITM_ID") == "T50"]
    code = "KOSTAT.CAP_UTIL.MFG.KR"
    if sub:
        indicators.append(IndicatorRow(
            imdr_code=code, vendor_name="KOSIS",
            source_code="101/DT_1F32002/ITM_ID=T50",
            display_name="Korea — Manufacturing Average Capacity Utilisation Rate, % (KOSTAT)",
            unit="pct", frequency="MONTHLY", country_iso="KR",
            category="gdp", is_seasonally_adjusted=False, bbg_ticker=None,
        ))
        for r in sub:
            ymd = parse_kosis_period(r.get("PRD_DE"), "M")
            if ymd is None: continue
            d = datetime.date(*ymd)
            if since_dt and d < since_dt: continue
            if until_dt and d > until_dt: continue
            try: v = float(r["DT"]) if r.get("DT") not in (None, "") else None
            except (TypeError, ValueError): v = None
            observations.append(ObservationRow(
                imdr_code=code, obs_date=d, vintage=0,
                release_date=now, value=v, ingested_at=now,
            ))

    return indicators, observations


def main() -> int:
    return run_main(
        vendor="kosis",
        topic="industrial",
        fetch_fn=run_fetch,
        description=__doc__.splitlines()[0] if __doc__ else "",
        country_code="KR",
    )


if __name__ == "__main__":
    import sys
    sys.exit(main())
