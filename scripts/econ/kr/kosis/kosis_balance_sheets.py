"""KOSIS BOK + FSS Balance-Sheet aggregates fetcher.

Sources:
  - **BOK orgId=301, DT_151Y001** — 가계신용(업권별, 분기) Household Credit
    by Sector (quarterly). Headline KRW-billion stock of household debt.
  - **FSS orgId=376, DT_376_10_SDMA051V_3** — Domestic banks Non-Performing
    Loans + Total Loans, quarterly. The headline NPL ratio + supporting
    levels.

Cell mapping: 4.2 Balance Sheets → ⚠ → ✅.

Indicators:
  Household Credit (2, quarterly):
    BOK.HH_CREDIT.TOTAL.KR        Total credit to households (loans + ABS etc.)
    BOK.HH_CREDIT.LOANS.KR        Loans to households (subset of total)

  Bank Asset Quality (3, quarterly):
    FSS.BANK.LOANS_TOTAL.KR       Domestic banks — Total Loans (level)
    FSS.BANK.NPL_LEVEL.KR         Domestic banks — Non-performing Loans (level)
    FSS.BANK.NPL_RATIO.KR         Domestic banks — NPL ratio (%)

Usage:
    C:/Users/adoshi/.conda/envs/imdr/python.exe scripts/econ/kr/kosis/kosis_balance_sheets.py
    python -m scripts.econ.kr.kosis.kosis_balance_sheets
"""

from __future__ import annotations

import datetime

from imdr.domains.econ.kosis_http import fetch_kosis_table, make_session, parse_kosis_period
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

# (table_spec, c1_target → (imdr_code_full, display, unit, category))
_HH_CREDIT_CUTS: dict[str, tuple[str, str, str, str]] = {
    "1000000": ("BOK.HH_CREDIT.TOTAL.KR",  "Korea — Credit to Households, total (BOK quarterly, KRW bn)",
                "krw_bn", "balance_sheet"),
    "1100000": ("BOK.HH_CREDIT.LOANS.KR",  "Korea — Loans to Households (BOK quarterly, KRW bn)",
                "krw_bn", "balance_sheet"),
}

_NPL_CUTS: dict[str, tuple[str, str, str, str]] = {
    "A.01_A": ("FSS.BANK.LOANS_TOTAL.KR",  "Korea — Domestic Banks Total Loans (FSS quarterly, KRW bn)",
                "krw_bn", "balance_sheet"),
    "A.02_B": ("FSS.BANK.NPL_LEVEL.KR",    "Korea — Domestic Banks Non-performing Loans, level (FSS quarterly, KRW bn)",
                "krw_bn", "balance_sheet"),
    "A.08_H": ("FSS.BANK.NPL_RATIO.KR",    "Korea — Domestic Banks NPL Ratio (FSS quarterly, % of total loans)",
                "pct", "balance_sheet"),
}


def _filter_and_emit(
    rows: list[dict],
    cuts: dict[str, tuple[str, str, str, str]],
    src_template: str,
    since_dt: datetime.date | None,
    until_dt: datetime.date | None,
    now: datetime.datetime,
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    indicators: list[IndicatorRow] = []
    observations: list[ObservationRow] = []
    for c1_target, (imdr_code, display, unit, category) in cuts.items():
        sub = [r for r in rows if (r.get("C1") or "").split(".")[-1] == c1_target.split(".")[-1]
               and (r.get("C1") or "").endswith(c1_target)]
        if not sub:
            print(f"  WARN: no rows for C1={c1_target} ({imdr_code})")
            continue
        indicators.append(IndicatorRow(
            imdr_code=imdr_code,
            vendor_name="KOSIS",
            source_code=src_template.format(c1=c1_target),
            display_name=display,
            unit=unit,
            frequency="QUARTERLY",
            country_iso="KR",
            category=category,
            is_seasonally_adjusted=False,
            bbg_ticker=None,
        ))
        for r in sub:
            ymd = parse_kosis_period(r.get("PRD_DE"), "Q")
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
    end_q = f"{today.year}{((today.month - 1) // 3) + 1:02d}"

    indicators: list[IndicatorRow] = []
    observations: list[ObservationRow] = []

    print("  Fetching Household Credit DT_151Y001 (BOK) ...", end=" ", flush=True)
    rows = fetch_kosis_table(
        session,
        org_id="301",
        tbl_id="DT_151Y001",
        obj_l1="ALL",
        itm_id="ALL",
        prd_se="Q",
        start_prd_de="19601",
        end_prd_de=end_q,
    )
    print(f"{len(rows)} rows")
    sub_ind, sub_obs = _filter_and_emit(
        rows, _HH_CREDIT_CUTS, "301/DT_151Y001/C1={c1}",
        since_dt, until_dt, now,
    )
    indicators.extend(sub_ind)
    observations.extend(sub_obs)

    print("  Fetching Bank NPL DT_376_10_SDMA051V_3 (FSS) ...", end=" ", flush=True)
    rows = fetch_kosis_table(
        session,
        org_id="376",
        tbl_id="DT_376_10_SDMA051V_3",
        obj_l1="ALL",
        itm_id="ALL",
        prd_se="Q",
        start_prd_de="19601",
        end_prd_de=end_q,
    )
    print(f"{len(rows)} rows")
    sub_ind, sub_obs = _filter_and_emit(
        rows, _NPL_CUTS, "376/DT_376_10_SDMA051V_3/C1={c1}",
        since_dt, until_dt, now,
    )
    indicators.extend(sub_ind)
    observations.extend(sub_obs)

    return indicators, observations


def main() -> int:
    return run_main(
        vendor="kosis",
        topic="balance_sheets",
        fetch_fn=run_fetch,
        description=__doc__.splitlines()[0] if __doc__ else "",
        country_code="KR",
    )


if __name__ == "__main__":
    import sys
    sys.exit(main())
