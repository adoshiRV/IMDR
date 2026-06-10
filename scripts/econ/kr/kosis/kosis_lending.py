"""KOSIS BOK Lending fetcher — survey stance + household loans.

Sources (orgId=301):
  - **DT_514Y001** — 대출행태서베이(대출태도) Lending Attitude Survey,
    quarterly. BOK's SLOOS-equivalent — positive = easing, negative =
    tightening. 9 cuts; we keep the 5 bank-side (overall + 4 borrower types).
  - **DT_151Y005** — 예금취급기관 가계대출(용도별, 월) Household Loans by
    Purpose at Depository Institutions, monthly. KRW billions. 9 cuts; we
    keep the 3 top-level (total + housing + other).

Cell mapping: 4.1 Demand Transmission → ⚠ → ✅.

Indicators:
  Lending-Stance Survey (5, quarterly):
    BOK.LEND_STANCE.BANK_OVERALL.KR     Bank — overall lending attitude
    BOK.LEND_STANCE.BANK_LARGE_CORP.KR  Bank — Large Corporations
    BOK.LEND_STANCE.BANK_SME.KR         Bank — Small/Medium Enterprises
    BOK.LEND_STANCE.BANK_HH.KR          Bank — General Households
    BOK.LEND_STANCE.BANK_HH_HOUSING.KR  Bank — Household housing
  Household Loans (3, monthly):
    BOK.LOANS.HH.DEP_TOTAL.KR           Depository Corporations — total
    BOK.LOANS.HH.HOUSING.KR             Depository Corps — housing-related
    BOK.LOANS.HH.OTHER.KR               Depository Corps — non-housing

Usage:
    C:/Users/adoshi/.conda/envs/imdr/python.exe scripts/econ/kr/kosis/kosis_lending.py
    python -m scripts.econ.kr.kosis.kosis_lending
"""

from __future__ import annotations

import datetime

from imdr.domains.econ.kosis_http import fetch_kosis_table, make_session, parse_kosis_period
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

# Each spec: (tbl_id, prd_se, start_prd, c1_target → (imdr_suffix, display, unit, category))
_LENDING_STANCE = {
    "tbl_id": "DT_514Y001",
    "prd_se": "Q",
    "start_prd": "20021",
    "unit": "index",
    "category": "sentiment",
    "cuts": {
        "AA":   ("LEND_STANCE.BANK_OVERALL",       "Bank — Overall Lending Attitude"),
        "AA01": ("LEND_STANCE.BANK_LARGE_CORP",    "Bank — Large Corporations"),
        "AA02": ("LEND_STANCE.BANK_SME",           "Bank — Small/Medium Enterprises"),
        "AA03": ("LEND_STANCE.BANK_HH",            "Bank — General Households"),
        "AA04": ("LEND_STANCE.BANK_HH_HOUSING",    "Bank — Household Housing"),
    },
}

_HH_LOANS = {
    "tbl_id": "DT_151Y005",
    "prd_se": "M",
    "start_prd": "200301",
    "unit": "krw_bn",
    "category": "credit",
    "cuts": {
        "1110000": ("LOANS.HH.DEP_TOTAL",     "Household Loans — Depository Corporations, total"),
        "11100A0": ("LOANS.HH.HOUSING",       "Household Loans — Housing-related, Depository Corps"),
        "11100B0": ("LOANS.HH.OTHER",         "Household Loans — Non-Housing, Depository Corps"),
    },
}


def _pull_and_emit(
    session,
    spec: dict,
    since_dt: datetime.date | None,
    until_dt: datetime.date | None,
    now: datetime.datetime,
    end_prd: str,
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    tbl_id = spec["tbl_id"]
    print(f"  Fetching {tbl_id} (prdSe={spec['prd_se']}) ...", end=" ", flush=True)
    rows = fetch_kosis_table(
        session,
        org_id="301",
        tbl_id=tbl_id,
        obj_l1="ALL",
        itm_id="ALL",
        prd_se=spec["prd_se"],
        start_prd_de=spec["start_prd"],
        end_prd_de=end_prd,
    )
    print(f"{len(rows)} rows")

    indicators: list[IndicatorRow] = []
    observations: list[ObservationRow] = []

    freq_for_prd = {"M": "MONTHLY", "Q": "QUARTERLY", "A": "ANNUAL"}[spec["prd_se"]]

    for c1_target, (suffix, display) in spec["cuts"].items():
        sub = [r for r in rows if (r.get("C1") or "").split(".")[-1] == c1_target]
        if not sub:
            print(f"  WARN: no rows for {tbl_id} C1={c1_target} ({suffix})")
            continue
        imdr_code = f"BOK.{suffix}.KR"
        indicators.append(IndicatorRow(
            imdr_code=imdr_code,
            vendor_name="KOSIS",
            source_code=f"301/{tbl_id}/C1={c1_target}",
            display_name=f"Korea — {display} (BOK)",
            unit=spec["unit"],
            frequency=freq_for_prd,
            country_iso="KR",
            category=spec["category"],
            is_seasonally_adjusted=False,
            bbg_ticker=None,
        ))
        for r in sub:
            ymd = parse_kosis_period(r.get("PRD_DE"), spec["prd_se"])
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


def run_fetch(
    since: str | None,
    until: str | None,
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    session = make_session()
    since_dt = datetime.date.fromisoformat(since) if since else None
    until_dt = datetime.date.fromisoformat(until) if until else None
    now = datetime.datetime.now(UTC)
    today = datetime.date.today()

    indicators: list[IndicatorRow] = []
    observations: list[ObservationRow] = []

    # Lending Stance Survey (quarterly).
    end_prd_q = f"{today.year}{((today.month - 1) // 3) + 1:02d}"
    sub_ind, sub_obs = _pull_and_emit(
        session, _LENDING_STANCE, since_dt, until_dt, now, end_prd_q,
    )
    indicators.extend(sub_ind)
    observations.extend(sub_obs)

    # Household Loans (monthly).
    end_prd_m = today.strftime("%Y%m")
    sub_ind, sub_obs = _pull_and_emit(
        session, _HH_LOANS, since_dt, until_dt, now, end_prd_m,
    )
    indicators.extend(sub_ind)
    observations.extend(sub_obs)

    return indicators, observations


def main() -> int:
    return run_main(
        vendor="kosis",
        topic="lending",
        fetch_fn=run_fetch,
        description=__doc__.splitlines()[0] if __doc__ else "",
        country_code="KR",
    )


if __name__ == "__main__":
    import sys
    sys.exit(main())
