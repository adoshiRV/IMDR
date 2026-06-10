"""KOSIS BOK Deposit Money Bank Deposit Rates fetcher (DT_121Y002).

Source: Bank of Korea (orgId=301), 예금은행 수신금리(신규취급액 기준) —
Deposit money bank deposit rates (based on newly extended), % p.a.

The table publishes 27 sub-cuts of bank deposit-side funding rates. We pull
6 representative cuts:
  BEABAA1     Time ＆ Savings Deposits Except Debentures (headline)
  BEABAA211   Time Deposits
  BEABAA2211  CDs (91 Days) — the same rate that drives the chart's red line
  BEABAA222   Repurchase Agreements
  BEABAA22    Marketable Financial Instruments (composite)
  BEABAA224   Financial Debentures

NOTE: this table is DEPOSIT rates, NOT the BOK Base Rate (policy rate). The
BOK Base Rate is not on KOSIS — for it, use Citi `RATES.BENCH_RATES` once a
KR entry is added, or the BOK direct site. CD 91d here mirrors what's
already in `rates.fact_observation` curve_id=35 tenor=3M (Citi via market
data); the KOSIS feed offers a regulator-validated alternative.

Cell mapping: 4.3 Financial Conditions (loan-rate / funding-cost channel).

Usage:
    C:/Users/adoshi/.conda/envs/imdr/python.exe scripts/econ/kr/kosis/kosis_bank_rates.py
    python -m scripts.econ.kr.kosis.kosis_bank_rates
"""

from __future__ import annotations

import datetime

from imdr.domains.econ.kosis_http import fetch_kosis_table, make_session, parse_kosis_period
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

# C1 suffix → (imdr suffix, display)
_CUTS: dict[str, tuple[str, str]] = {
    "BEABAA1":    ("DEPOSITS_EX_DEBENT", "Bank deposits (ex financial debentures)"),
    "BEABAA211":  ("TIME_DEPOSITS",      "Bank time deposits"),
    "BEABAA2211": ("CD_91D",             "Bank CD rate, 91 days"),
    "BEABAA222":  ("REPO",               "Bank repurchase agreements"),
    "BEABAA22":   ("MARKET_FI",          "Bank marketable financial instruments (composite)"),
    "BEABAA224":  ("FIN_DEBENT",         "Bank financial debentures"),
}


def run_fetch(
    since: str | None,
    until: str | None,
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    session = make_session()
    since_dt = datetime.date.fromisoformat(since) if since else None
    until_dt = datetime.date.fromisoformat(until) if until else None
    now = datetime.datetime.now(UTC)

    print("  Fetching bank rates: DT_121Y002 (BOK, orgId=301) ...", end=" ", flush=True)
    rows = fetch_kosis_table(
        session,
        org_id="301",
        tbl_id="DT_121Y002",
        obj_l1="ALL",
        itm_id="ALL",
        prd_se="M",
        start_prd_de="199001",
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
        imdr_code = f"BOK.BANK_RATE.{suffix}.KR"
        indicators.append(IndicatorRow(
            imdr_code=imdr_code,
            vendor_name="KOSIS",
            source_code=f"301/DT_121Y002/...{c1_suffix}",
            display_name=f"Korea {display}, % p.a. (BOK)",
            unit="pct",
            frequency="MONTHLY",
            country_iso="KR",
            category="rates",
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
        topic="bank_rates",
        fetch_fn=run_fetch,
        description=__doc__.splitlines()[0] if __doc__ else "",
        country_code="KR",
    )


if __name__ == "__main__":
    import sys
    sys.exit(main())
