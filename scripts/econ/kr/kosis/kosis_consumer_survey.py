"""KOSIS BOK Consumer Survey (CCI components) fetcher.

Source: BOK orgId=301, **DT_511Y002** — 소비자동향조사(전국, 월) Consumer
Tendency Survey, monthly, diffusion-index form (>100 = optimistic).
The composite CCSI is published outside this table; here we pull the
6 most-watched component indices on the C2=99988 (total respondent) cut.

Cell mapping: 1.1 Private Demand (consumer-confidence sub-bullet) +
2.3 Domestic Costs (inflation-expectations leg).

Indicators (6, monthly 2008-09 → present):
  BOK.CCI.LIVING_STD.KR        Living Standard of Household (current)
  BOK.CCI.ECON_SITUATION.KR    Domestic Economic Situation (current)
  BOK.CCI.EXP_LIVING_STD.KR    Expected Living Standard of Household
  BOK.CCI.EXP_ECON_SITUATION.KR Expected Domestic Economic Situation
  BOK.CCI.EXP_EMPLOYMENT.KR    Expected Employment Situation
  BOK.CCI.EXP_INTEREST_RATES.KR Expected Interest Rates

Usage:
    C:/Users/adoshi/.conda/envs/imdr/python.exe scripts/econ/kr/kosis/kosis_consumer_survey.py
    python -m scripts.econ.kr.kosis.kosis_consumer_survey
"""

from __future__ import annotations

import datetime

from imdr.domains.econ.kosis_http import fetch_kosis_table, make_session, parse_kosis_period
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

# C1 (CSI code) → (suffix, display)
_CUTS = {
    "FMAA": ("LIVING_STD",          "Living Standard of Household (current)"),
    "FMAB": ("ECON_SITUATION",      "Domestic Economic Situation (current)"),
    "FMBA": ("EXP_LIVING_STD",      "Expected Living Standard of Household"),
    "FMBB": ("EXP_ECON_SITUATION",  "Expected Domestic Economic Situation"),
    "FMBE": ("EXP_EMPLOYMENT",      "Expected Employment Situation"),
    "FMBG": ("EXP_INTEREST_RATES",  "Expected Interest Rates"),
}
_C2_TOTAL = "99988"


def _discover_full_codes(session):
    """1-period discovery pull to learn full prefixed C1 + C2 codes."""
    rows = fetch_kosis_table(
        session, org_id="301", tbl_id="DT_511Y002",
        obj_l1="ALL", itm_id="ALL", prd_se="M",
        new_est_prd_cnt=1, extra_params={"objL2": "ALL"},
    )
    c1_map: dict[str, str] = {}
    c2_total_full = None
    for r in rows:
        c1 = r.get("C1") or ""
        suf1 = c1.split(".")[-1]
        if suf1 in _CUTS and suf1 not in c1_map:
            c1_map[suf1] = c1
        c2 = r.get("C2") or ""
        if c2.split(".")[-1] == _C2_TOTAL and c2_total_full is None:
            c2_total_full = c2
    return c1_map, c2_total_full


def run_fetch(since, until):
    session = make_session()
    since_dt = datetime.date.fromisoformat(since) if since else None
    until_dt = datetime.date.fromisoformat(until) if until else None
    now = datetime.datetime.now(UTC)
    today = datetime.date.today()

    print("  Discovering C1/C2 prefixes ...", end=" ", flush=True)
    c1_map, c2_total_full = _discover_full_codes(session)
    print(f"got {len(c1_map)}/{len(_CUTS)} C1s + C2-total {'yes' if c2_total_full else 'NO'}")
    if c2_total_full is None:
        print("  ERR: could not find C2=99988 (Total) in discovery pull")
        return [], []

    inds, obs = [], []
    for c1_target, (suffix, display) in _CUTS.items():
        full_c1 = c1_map.get(c1_target)
        if not full_c1:
            print(f"  WARN: C1 suffix {c1_target} not in discovery pull")
            continue
        print(f"  Fetching CCI {suffix} ({c1_target}) ...", end=" ", flush=True)
        rows = fetch_kosis_table(
            session, org_id="301", tbl_id="DT_511Y002",
            obj_l1=full_c1, itm_id="ALL", prd_se="M",
            start_prd_de="200809", end_prd_de=today.strftime("%Y%m"),
            extra_params={"objL2": c2_total_full},
        )
        print(f"{len(rows)} rows")
        sub = rows
        if not sub: continue
        code = f"BOK.CCI.{suffix}.KR"
        inds.append(IndicatorRow(
            imdr_code=code, vendor_name="KOSIS",
            source_code=f"301/DT_511Y002/C1={c1_target}/C2={_C2_TOTAL}",
            display_name=f"Korea — {display} (BOK Consumer Tendency Survey, diffusion >100=optimistic)",
            unit="index", frequency="MONTHLY", country_iso="KR",
            category="sentiment", is_seasonally_adjusted=False, bbg_ticker=None,
        ))
        for r in sub:
            ymd = parse_kosis_period(r.get("PRD_DE"), "M")
            if ymd is None: continue
            d = datetime.date(*ymd)
            if since_dt and d < since_dt: continue
            if until_dt and d > until_dt: continue
            try: v = float(r["DT"]) if r.get("DT") not in (None, "") else None
            except (TypeError, ValueError): v = None
            obs.append(ObservationRow(imdr_code=code, obs_date=d, vintage=0,
                                      release_date=now, value=v, ingested_at=now))
    return inds, obs


def main() -> int:
    return run_main(
        vendor="kosis",
        topic="consumer_survey",
        fetch_fn=run_fetch,
        description=__doc__.splitlines()[0] if __doc__ else "",
        country_code="KR",
    )


if __name__ == "__main__":
    import sys
    sys.exit(main())
