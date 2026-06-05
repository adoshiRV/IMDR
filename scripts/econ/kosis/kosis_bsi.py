"""KOSIS BOK Business Sentiment Index (BSI) fetcher.

Sources (BOK orgId=301):
  - **DT_512Y007** — 업종별 기업경기실사지수 (실적) BSI Realised, monthly,
    diffusion-index form (>100 = expansionary)
  - **DT_512Y008** — 업종별 기업경기실사지수 (전망) BSI Outlook (forward-looking),
    monthly

Each table is 2-axis: C1 = BSI question (Business Condition, Sales, Production,
Profitability, etc.) × C2 = Business Type (All Industries, Manufacturing, etc.).

We pull C1=AA (Business Condition — the headline BSI) × C2 ∈ {99988 All
Industries, C0000 Manufacturing} for both realised + outlook = 4 indicators.

Cell mapping: 1.1 Private Demand (BSI as sentiment leg) +
1.4 Macro Core (BSI Manufacturing as cycle nowcast).

Indicators (4, monthly 2009-08 → present):
  BOK.BSI.REALISED.ALL.KR      BSI Business Condition, All Industries, Realised
  BOK.BSI.REALISED.MFG.KR      BSI Business Condition, Manufacturing, Realised
  BOK.BSI.OUTLOOK.ALL.KR       BSI Business Condition, All Industries, Outlook
  BOK.BSI.OUTLOOK.MFG.KR       BSI Business Condition, Manufacturing, Outlook

Usage:
    C:/Users/adoshi/.conda/envs/imdr/python.exe scripts/econ/kosis/kosis_bsi.py
    python -m scripts.econ.kosis.kosis_bsi
"""

from __future__ import annotations

import datetime

from imdr.domains.econ.kosis_http import fetch_kosis_table, make_session, parse_kosis_period
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

# Realised uses C1 prefix 'A' (AA = Business Condition), Outlook uses 'B' (BA = Business Condition).
_TABLES = [
    ("DT_512Y007", "REALISED", "Realised", "AA"),
    ("DT_512Y008", "OUTLOOK",  "Outlook",  "BA"),
]

_C2_TARGETS = {
    "99988": ("ALL", "All Industries"),
    "C0000": ("MFG", "Manufacturing"),
}


def _discover_full_codes(session, tbl_id, c1_target):
    """1-period discovery to learn full prefixed C1 + C2 codes."""
    rows = fetch_kosis_table(
        session, org_id="301", tbl_id=tbl_id,
        obj_l1="ALL", itm_id="ALL", prd_se="M",
        new_est_prd_cnt=1, extra_params={"objL2": "ALL"},
    )
    c1_full = None
    c2_map: dict[str, str] = {}
    for r in rows:
        c1 = r.get("C1") or ""
        if c1.split(".")[-1] == c1_target and c1_full is None:
            c1_full = c1
        c2 = r.get("C2") or ""
        suf2 = c2.split(".")[-1]
        if suf2 in _C2_TARGETS and suf2 not in c2_map:
            c2_map[suf2] = c2
    return c1_full, c2_map


def run_fetch(since, until):
    session = make_session()
    since_dt = datetime.date.fromisoformat(since) if since else None
    until_dt = datetime.date.fromisoformat(until) if until else None
    now = datetime.datetime.now(UTC)
    today = datetime.date.today()
    inds, obs = [], []
    for tbl_id, kind_suffix, kind_display, c1_target in _TABLES:
        print(f"  Discovering {tbl_id} prefixes ...", end=" ", flush=True)
        c1_full, c2_map = _discover_full_codes(session, tbl_id, c1_target)
        print(f"C1={c1_full and c1_full.split('.')[-1]}, C2s={list(c2_map.keys())}")
        if not c1_full or not c2_map:
            print(f"  WARN: could not discover prefixes for {tbl_id}")
            continue
        for c2_target, (sector_suffix, sector_display) in _C2_TARGETS.items():
            full_c2 = c2_map.get(c2_target)
            if not full_c2:
                continue
            print(f"  Fetching {tbl_id} BSI {kind_display} × {sector_display} ...", end=" ", flush=True)
            rows = fetch_kosis_table(
                session, org_id="301", tbl_id=tbl_id,
                obj_l1=c1_full, itm_id="ALL", prd_se="M",
                start_prd_de="200908", end_prd_de=today.strftime("%Y%m"),
                extra_params={"objL2": full_c2},
            )
            print(f"{len(rows)} rows")
            if not rows:
                continue
            code = f"BOK.BSI.{kind_suffix}.{sector_suffix}.KR"
            inds.append(IndicatorRow(
                imdr_code=code, vendor_name="KOSIS",
                source_code=f"301/{tbl_id}/C1=AA/C2={c2_target}",
                display_name=f"Korea — BSI Business Condition, {sector_display}, {kind_display} (BOK monthly, >100=expansionary)",
                unit="index", frequency="MONTHLY", country_iso="KR",
                category="sentiment", is_seasonally_adjusted=False, bbg_ticker=None,
            ))
            for r in rows:
                ymd = parse_kosis_period(r.get("PRD_DE"), "M")
                if ymd is None:
                    continue
                d = datetime.date(*ymd)
                if since_dt and d < since_dt:
                    continue
                if until_dt and d > until_dt:
                    continue
                try:
                    v = float(r["DT"]) if r.get("DT") not in (None, "") else None
                except (TypeError, ValueError):
                    v = None
                obs.append(ObservationRow(imdr_code=code, obs_date=d, vintage=0,
                                          release_date=now, value=v, ingested_at=now))
    return inds, obs


def main() -> int:
    return run_main(
        vendor="kosis",
        topic="bsi",
        fetch_fn=run_fetch,
        description=__doc__.splitlines()[0] if __doc__ else "",
    )


if __name__ == "__main__":
    import sys
    sys.exit(main())
