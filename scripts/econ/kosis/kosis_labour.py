"""KOSIS / KOSTAT Economically Active Population Survey fetcher (DT_1DA7001S).

Source: Statistics Korea (KOSTAT, orgId=101), 성별 경제활동인구 총괄 —
labour-force headline indicators by sex (and farm/non-farm cuts).

We pull 8 headline series (Total population side, monthly):
  T10  Population 15+ ('000)
  T20  Economically active population ('000)
  T30  Employed persons ('000)
  T40  Unemployed persons ('000)
  T50  Economically inactive population ('000)
  T60  Labor Force Participation Rate (%)
  T80  Unemployment Rate (%)
  T90  Employment-to-Population ratio (%)

C1=0 selects the all-population cut (Total, no sex/farm split). 8
indicators × monthly = ~30 years of monthly history when fully run.

Cell mapping: 1.4 Macro Core (labour leg) → ⚠ → ✅.

Usage:
    C:/Users/adoshi/.conda/envs/imdr/python.exe scripts/econ/kosis/kosis_labour.py
    python -m scripts.econ.kosis.kosis_labour
"""

from __future__ import annotations

import datetime

from imdr.domains.econ.kosis_http import fetch_kosis_table, make_session, parse_kosis_period
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

# ITM_ID → (imdr_suffix, display, unit, category)
_ITEMS: dict[str, tuple[str, str, str, str]] = {
    "T10": ("POP_15_OVER",     "Population aged 15 and over",         "th_persons", "labour"),
    "T20": ("ACTIVE_POP",      "Economically active population",      "th_persons", "labour"),
    "T30": ("EMPLOYED",        "Employed persons",                    "th_persons", "labour"),
    "T40": ("UNEMPLOYED",      "Unemployed persons",                  "th_persons", "labour"),
    "T50": ("INACTIVE",        "Economically inactive population",    "th_persons", "labour"),
    "T60": ("LFPR",            "Labor Force Participation Rate",      "pct",         "labour"),
    "T80": ("UNEMP_RATE",      "Unemployment Rate",                   "pct",         "labour"),
    "T90": ("EMP_POP_RATIO",   "Employment-to-Population Ratio",      "pct",         "labour"),
}


def run_fetch(
    since: str | None,
    until: str | None,
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    session = make_session()
    since_dt = datetime.date.fromisoformat(since) if since else None
    until_dt = datetime.date.fromisoformat(until) if until else None
    now = datetime.datetime.now(UTC)

    print("  Fetching EAPS labour: DT_1DA7001S (KOSTAT, orgId=101) ...", end=" ", flush=True)
    rows = fetch_kosis_table(
        session,
        org_id="101",
        tbl_id="DT_1DA7001S",
        obj_l1="ALL",
        itm_id="ALL",
        prd_se="M",
        start_prd_de="199001",
        end_prd_de=datetime.date.today().strftime("%Y%m"),
    )
    print(f"{len(rows)} rows")

    indicators: list[IndicatorRow] = []
    observations: list[ObservationRow] = []

    for itm_id, (suffix, display, unit, category) in _ITEMS.items():
        # Keep only the Total (C1=0) cut for headline series.
        sub = [r for r in rows if r.get("ITM_ID") == itm_id and r.get("C1") == "0"]
        if not sub:
            print(f"  WARN: no Total rows for {itm_id} ({suffix})")
            continue
        imdr_code = f"KOSTAT.LABOUR.{suffix}.KR"
        indicators.append(IndicatorRow(
            imdr_code=imdr_code,
            vendor_name="KOSIS",
            source_code=f"101/DT_1DA7001S/C1=0/ITM_ID={itm_id}",
            display_name=f"Korea {display} (KOSTAT EAPS, monthly, all population)",
            unit=unit,
            frequency="MONTHLY",
            country_iso="KR",
            category=category,
            is_seasonally_adjusted=False,
            bbg_ticker=None,
        ))
        for r in sub:
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

    return indicators, observations


def main() -> int:
    return run_main(
        vendor="kosis",
        topic="labour",
        fetch_fn=run_fetch,
        description=__doc__.splitlines()[0] if __doc__ else "",
    )


if __name__ == "__main__":
    import sys
    sys.exit(main())
