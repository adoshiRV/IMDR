"""KOSIS BOK PPI level fetcher (DT_404Y014).

Source: Bank of Korea (orgId=301), 생산자물가지수(기본분류) — Producer Price
Indices (Basic Groups), base 2020=100.

This table has 526 sub-classification rows (full BOK PPI tree). We pull only
the 6 top-level cuts: All-items plus the 5 tier-1 sectors. The full sub-tree
can be added later by extending ``_CUTS``.

Cuts pulled:
  *AA  Total          All items
  1AA  Agri-fmar      Agricultural / Forestry / Marine
  2AA  Mining         Mining products
  3AA  Manufacturing  Manufacturing products
  4AA  Utilities      Electric / Gas / Water / Waste
  5AA  Services       Services

Cell mapping: 2.2 Producer Prices.

Usage:
    C:/Users/adoshi/.conda/envs/imdr/python.exe scripts/econ/kosis/kosis_ppi.py
    python -m scripts.econ.kosis.kosis_ppi
"""

from __future__ import annotations

import datetime

from imdr.domains.econ.kosis_http import fetch_kosis_table, make_session, parse_kosis_period
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

# C1 suffix (last segment of the long C1 string) → (imdr suffix, display)
_CUTS: dict[str, tuple[str, str]] = {
    "*AA": ("TOTAL",    "Total PPI, all items"),
    "1AA": ("AGRI",     "Agricultural / Forestry / Marine"),
    "2AA": ("MINING",   "Mining products"),
    "3AA": ("MFG",      "Manufacturing products"),
    "4AA": ("UTIL",     "Electricity / Gas / Water / Waste"),
    "5AA": ("SVC",      "Services"),
}


def _discover_c1_codes(session) -> dict[str, str]:
    """Discovery call: one recent-month pull with objL1=ALL to learn the full
    prefixed C1 codes for each of our 6 cut suffixes. Returns suffix → full C1.

    PPI's full C1 looks like '13102134604ACC_CD.*AA' — the 13102134604ACC_CD.
    prefix is BOK's internal axis lookup-id and can rotate on table rebuilds,
    so we don't hardcode it.
    """
    rows = fetch_kosis_table(
        session,
        org_id="301",
        tbl_id="DT_404Y014",
        obj_l1="ALL",
        itm_id="ALL",
        prd_se="M",
        new_est_prd_cnt=1,
    )
    by_suffix: dict[str, str] = {}
    for r in rows:
        c1 = r.get("C1") or ""
        suffix = c1.split(".")[-1]
        if suffix in _CUTS and suffix not in by_suffix:
            by_suffix[suffix] = c1
    return by_suffix


def run_fetch(
    since: str | None,
    until: str | None,
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    session = make_session()
    since_dt = datetime.date.fromisoformat(since) if since else None
    until_dt = datetime.date.fromisoformat(until) if until else None
    now = datetime.datetime.now(UTC)

    print("  Discovering full C1 codes via 1-period pull ...", end=" ", flush=True)
    c1_map = _discover_c1_codes(session)
    print(f"got {len(c1_map)} of {len(_CUTS)} expected")
    missing = set(_CUTS) - set(c1_map)
    if missing:
        print(f"  WARN: suffix(es) not found in discovery pull: {missing}")

    indicators: list[IndicatorRow] = []
    observations: list[ObservationRow] = []

    for c1_suffix, (suffix, display) in _CUTS.items():
        full_c1 = c1_map.get(c1_suffix)
        if not full_c1:
            continue
        print(f"  Fetching PPI {suffix} ({c1_suffix}) ...", end=" ", flush=True)
        rows = fetch_kosis_table(
            session,
            org_id="301",
            tbl_id="DT_404Y014",
            obj_l1=full_c1,
            itm_id="ALL",
            prd_se="M",
            start_prd_de="199001",
            end_prd_de=datetime.date.today().strftime("%Y%m"),
        )
        print(f"{len(rows)} rows")

        imdr_code = f"BOK.PPI.{suffix}.LEVEL.KR"
        indicators.append(IndicatorRow(
            imdr_code=imdr_code,
            vendor_name="KOSIS",
            source_code=f"301/DT_404Y014/{full_c1}",
            display_name=f"Korea PPI — {display}, 2020=100 (BOK)",
            unit="index",
            frequency="MONTHLY",
            country_iso="KR",
            category="cpi",
            is_seasonally_adjusted=False,
            bbg_ticker=None,
        ))
        for r in rows:
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
        topic="ppi",
        fetch_fn=run_fetch,
        description=__doc__.splitlines()[0] if __doc__ else "",
    )


if __name__ == "__main__":
    import sys
    sys.exit(main())
