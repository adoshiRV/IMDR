"""KOSIS BOK Money Aggregates fetcher (M2 + Lf headline).

Sources (BOK orgId=301):
  - **DT_161Y007** — M2 상품별 구성내역 (말잔, 계절조정) — M2 by product type,
    end-of-period, seasonally-adjusted, KRW billions, monthly. We pull only
    `BBGS00` (M2 total).
  - **DT_171Y001** — Lf 상품별 구성내역 (말잔, 계절조정) — Lf liquidity
    aggregate by product type, end-of-period, SA, KRW billions, monthly.
    We pull only `LES0000` (Lf total).

For M1 the dedicated headline table is `DT_2KAA701` (KOSTAT mirror, index-form,
international comparison). KRW-billion M1 headline is `BBGS01` (Currency in
Circulation) + `BBGS02` (Demand Deposits) + `BBGS03` (Transferable Savings)
— composite, derive at query time.

Cell mapping: 4.4 Policy Reaction → fills the M-aggregate sub-bullet.

Indicators:
  BOK.MONEY.M2.LEVEL.KR    M2 total, end-of-period, SA, KRW bn
  BOK.MONEY.LF.LEVEL.KR    Lf (Liquidity Aggregates of Financial Inst.), EOP SA, KRW bn

Usage:
    C:/Users/adoshi/.conda/envs/imdr/python.exe scripts/econ/kr/kosis/kosis_money_aggregates.py
    python -m scripts.econ.kr.kosis.kosis_money_aggregates
"""

from __future__ import annotations

import datetime

from imdr.domains.econ.kosis_http import fetch_kosis_table, make_session, parse_kosis_period
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

# (tbl_id, c1_target → (imdr_code, display))
_M2_TARGETS = {
    "BBGS00": ("BOK.MONEY.M2.LEVEL.KR", "Korea M2 (broad money), end-of-period, seasonally adjusted, KRW bn (BOK)"),
}
_LF_TARGETS = {
    "LES0000": ("BOK.MONEY.LF.LEVEL.KR", "Korea Lf (Liquidity Aggregates of Financial Inst.), EOP SA, KRW bn (BOK)"),
}


def _pull_and_emit(session, tbl_id, targets, src_template, since_dt, until_dt, now):
    print(f"  Fetching {tbl_id} ...", end=" ", flush=True)
    rows = fetch_kosis_table(
        session,
        org_id="301",
        tbl_id=tbl_id,
        obj_l1="ALL",
        itm_id="ALL",
        prd_se="M",
        start_prd_de="198001",
        end_prd_de=datetime.date.today().strftime("%Y%m"),
    )
    print(f"{len(rows)} rows")
    inds, obs = [], []
    for c1_target, (imdr_code, display) in targets.items():
        sub = [r for r in rows if (r.get("C1") or "").split(".")[-1] == c1_target]
        if not sub:
            print(f"  WARN: no rows for {tbl_id}/C1={c1_target}")
            continue
        inds.append(IndicatorRow(
            imdr_code=imdr_code, vendor_name="KOSIS",
            source_code=src_template.format(c1=c1_target),
            display_name=display, unit="krw_bn", frequency="MONTHLY",
            country_iso="KR", category="cb_balance_sheet",
            is_seasonally_adjusted=True, bbg_ticker=None,
        ))
        for r in sub:
            ymd = parse_kosis_period(r.get("PRD_DE"), "M")
            if ymd is None: continue
            d = datetime.date(*ymd)
            if since_dt and d < since_dt: continue
            if until_dt and d > until_dt: continue
            try: v = float(r["DT"]) if r.get("DT") not in (None,"") else None
            except (TypeError, ValueError): v = None
            obs.append(ObservationRow(
                imdr_code=imdr_code, obs_date=d, vintage=0,
                release_date=now, value=v, ingested_at=now,
            ))
    return inds, obs


def run_fetch(since, until):
    session = make_session()
    since_dt = datetime.date.fromisoformat(since) if since else None
    until_dt = datetime.date.fromisoformat(until) if until else None
    now = datetime.datetime.now(UTC)
    inds, obs = [], []
    a, b = _pull_and_emit(session, "DT_161Y007", _M2_TARGETS, "301/DT_161Y007/C1={c1}", since_dt, until_dt, now)
    inds.extend(a); obs.extend(b)
    a, b = _pull_and_emit(session, "DT_171Y001", _LF_TARGETS, "301/DT_171Y001/C1={c1}", since_dt, until_dt, now)
    inds.extend(a); obs.extend(b)
    return inds, obs


def main() -> int:
    return run_main(
        vendor="kosis",
        topic="money_aggregates",
        fetch_fn=run_fetch,
        description=__doc__.splitlines()[0] if __doc__ else "",
        country_code="KR",
    )


if __name__ == "__main__":
    import sys
    sys.exit(main())
