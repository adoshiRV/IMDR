"""KOSIS BOK Terms of Trade fetcher (DT_403Y005).

Source: Bank of Korea (orgId=301), 교역조건지수 — Terms of Trade Indices,
base 2020=100.

The table publishes 2 ToT measures, both monthly:
  TERMS_TRADE_TYPE.A   순상품교역조건지수   Net barter terms of trade index
  TERMS_TRADE_TYPE.B   소득교역조건지수    Income terms of trade index

Cell mapping: 3.1 Terms of Trade.

Usage:
    C:/Users/adoshi/.conda/envs/imdr/python.exe scripts/econ/kr/kosis/kosis_tot.py
    python -m scripts.econ.kr.kosis.kosis_tot
"""

from __future__ import annotations

import datetime

from imdr.domains.econ.kosis_http import fetch_kosis_table, make_session, parse_kosis_period
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

# C1 suffix → (imdr suffix, display)
_CUTS: dict[str, tuple[str, str]] = {
    "A": ("NET_BARTER", "Net barter terms of trade (commodity TOT)"),
    "B": ("INCOME",     "Income terms of trade"),
}


def run_fetch(
    since: str | None,
    until: str | None,
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    session = make_session()
    since_dt = datetime.date.fromisoformat(since) if since else None
    until_dt = datetime.date.fromisoformat(until) if until else None
    now = datetime.datetime.now(UTC)

    print("  Fetching ToT: DT_403Y005 (BOK, orgId=301) ...", end=" ", flush=True)
    rows = fetch_kosis_table(
        session,
        org_id="301",
        tbl_id="DT_403Y005",
        obj_l1="ALL",
        itm_id="ALL",
        prd_se="M",
        start_prd_de="198801",
        end_prd_de=datetime.date.today().strftime("%Y%m"),
    )
    print(f"{len(rows)} rows")

    by_suffix: dict[str, list[dict]] = {}
    for r in rows:
        c1 = r.get("C1") or ""
        suffix = c1.split(".")[-1]
        by_suffix.setdefault(suffix, []).append(r)

    indicators: list[IndicatorRow] = []
    observations: list[ObservationRow] = []

    for c1_suffix, (suffix, display) in _CUTS.items():
        sub = by_suffix.get(c1_suffix, [])
        if not sub:
            print(f"  WARN: no rows for {c1_suffix}")
            continue
        imdr_code = f"BOK.TOT.{suffix}.LEVEL.KR"
        indicators.append(IndicatorRow(
            imdr_code=imdr_code,
            vendor_name="KOSIS",
            source_code=f"301/DT_403Y005/...{c1_suffix}",
            display_name=f"Korea {display}, 2020=100 (BOK)",
            unit="index",
            frequency="MONTHLY",
            country_iso="KR",
            category="bop",
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
        topic="tot",
        fetch_fn=run_fetch,
        description=__doc__.splitlines()[0] if __doc__ else "",
        country_code="KR",
    )


if __name__ == "__main__":
    import sys
    sys.exit(main())
