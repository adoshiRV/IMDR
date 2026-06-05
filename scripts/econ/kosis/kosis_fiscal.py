"""KOSIS BOK Public Sector Revenue/Expenditure fetcher (DT_200Y154).

Source: Bank of Korea (orgId=301), 공공부문의 부문별 총수입 총지출
저축투자차액(명목 연간) — Public Sector Revenue, Expenditure and Saving-
Investment Difference by Sector (Nominal, Annual), KRW billions.

This is a **2-axis** KOSIS table (C1 + C2), unlike all earlier KOSIS
fetchers which were single-axis. C1 = institutional sector (6 cuts),
C2 = SNA flow account item (50 cuts). We pull General Government
(C1=1) × 7 headline aggregates = 7 indicators, annual 2007 → present.

Headline C2 codes pulled:
  1400  Total expenditure
  1401  Total revenue
  1309  Net lending (+) / Net borrowing (-)  ← fiscal balance
  1222  Final consumption expenditure  ← government consumption (in KRW)
  1204  Taxes on production and imports  ← indirect taxes
  1211  Current taxes on income, wealth, etc. receivable  ← direct taxes
  1226  Saving gross

Cell mapping: 1.2 Fiscal Demand → ❌ → ✅.

Notes:
- History only from 2007 (BPM/SNA revision boundary).
- Annual cadence — fiscal aggregates are not published monthly at this
  detail; for monthly fiscal, see MOEF's Monthly Treasury Statement
  (different vendor, not yet wired).

Usage:
    C:/Users/adoshi/.conda/envs/imdr/python.exe scripts/econ/kosis/kosis_fiscal.py
    python -m scripts.econ.kosis.kosis_fiscal
"""

from __future__ import annotations

import datetime

from imdr.domains.econ.kosis_http import fetch_kosis_table, make_session, parse_kosis_period
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

# Headline C2 codes (after the BOK lookup-id prefix) → (suffix, display)
_C2_TARGETS: dict[str, tuple[str, str]] = {
    "1401": ("REVENUE_TOTAL",        "General Government — Total Revenue"),
    "1400": ("EXPENDITURE_TOTAL",    "General Government — Total Expenditure"),
    "1309": ("NET_LENDING",          "General Government — Net Lending / Net Borrowing"),
    "1222": ("CONSUMPTION_FINAL",    "General Government — Final Consumption Expenditure"),
    "1204": ("TAX_PRODUCTION",       "General Government — Taxes on Production and Imports (indirect)"),
    "1211": ("TAX_INCOME",           "General Government — Current Taxes on Income and Wealth (direct)"),
    "1226": ("SAVING_GROSS",         "General Government — Gross Saving"),
}

# C1 = '1' → General Government (the headline cut)
_C1_TARGET = "1"


def run_fetch(
    since: str | None,
    until: str | None,
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    session = make_session()
    since_dt = datetime.date.fromisoformat(since) if since else None
    until_dt = datetime.date.fromisoformat(until) if until else None
    now = datetime.datetime.now(UTC)

    print("  Fetching Public Sector Fiscal: DT_200Y154 (BOK, orgId=301) ...", end=" ", flush=True)
    rows = fetch_kosis_table(
        session,
        org_id="301",
        tbl_id="DT_200Y154",
        obj_l1="ALL",
        itm_id="ALL",
        prd_se="A",
        start_prd_de="2007",
        end_prd_de=str(datetime.date.today().year),
        extra_params={"objL2": "ALL"},
    )
    print(f"{len(rows)} rows")

    # Filter to General Government (C1=1) × headline C2 codes.
    indicators: list[IndicatorRow] = []
    observations: list[ObservationRow] = []

    for c2_code, (suffix, display) in _C2_TARGETS.items():
        sub = [
            r for r in rows
            if (r.get("C1") or "").split(".")[-1] == _C1_TARGET
            and (r.get("C2") or "").split(".")[-1] == c2_code
        ]
        if not sub:
            print(f"  WARN: no rows for C1=1 × C2={c2_code} ({suffix})")
            continue
        imdr_code = f"BOK.FISCAL.{suffix}.KR"
        indicators.append(IndicatorRow(
            imdr_code=imdr_code,
            vendor_name="KOSIS",
            source_code=f"301/DT_200Y154/C1=1/C2={c2_code}",
            display_name=f"Korea — {display} (BOK SNA, annual, KRW bn)",
            unit="krw_bn",
            frequency="ANNUAL",
            country_iso="KR",
            category="gdp",
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
        topic="fiscal",
        fetch_fn=run_fetch,
        description=__doc__.splitlines()[0] if __doc__ else "",
    )


if __name__ == "__main__":
    import sys
    sys.exit(main())
