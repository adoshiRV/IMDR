"""KOSIS BOK Balance of Payments fetcher (DT_301Y013).

Source: Bank of Korea (orgId=301), 국제수지 — Balance of Payments,
monthly, USD millions. KOSIS mirrors ECOS series 301Y013 1:1.

The full table has 284 line items (BPM6 hierarchy: 6-char short codes
for Current Account, 12-char ``BOPF`` codes for Financial Account,
``BOPO`` for Errors & Omissions). We pull 24 top-level indicators
spanning all 5 BPM6 blocks. Per-cut iteration is required because
``objL1=ALL`` × 45 years × 12 months × 284 cuts ≫ 40k-cell cap.

Cells filled:
  - 3.2 Current Account: CA total + Goods/Services/Primary/Secondary balances
    + sub-cuts (exports, imports, travel, transport, construction, invest income)
  - 3.3 Capital Account: FA total + DI/PI/Derivatives/OI/Reserves
    (assets + liabilities sides for each), plus E&O

History: 1980-01 → present (45+ years monthly).

This replaces an earlier Playwright-based ``fetch_bop.py`` that pre-dated
the KOSIS OpenAPI key. The Playwright path is no longer needed — TLS 1.2
pinning via ``_kosis_http.py`` makes the REST endpoint reachable from
the same corp network.

Usage:
    C:/Users/adoshi/.conda/envs/imdr/python.exe scripts/econ/kr/kosis/kosis_bop.py
    C:/Users/adoshi/.conda/envs/imdr/python.exe scripts/econ/kr/kosis/kosis_bop.py --since 2000-01-01 --no-parquet
    python -m scripts.econ.kr.kosis.kosis_bop
"""

from __future__ import annotations

import datetime

from imdr.domains.econ.kosis_http import fetch_kosis_table, make_session, parse_kosis_period
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

# C1 suffix (last segment after ACC_ITEM.) → (imdr suffix, display_name, is_balance)
# Current Account family uses 6-char short codes;
# Financial Account uses 12-char BOPF/BOPO codes.
_CUTS: dict[str, tuple[str, str]] = {
    # --- Current Account top-level (5) ---
    "000000":       ("CA.TOTAL",           "Current Account, total"),
    "100000":       ("CA.GOODS",           "Current Account — Goods balance"),
    "200000":       ("CA.SERVICES",        "Current Account — Services balance"),
    "300000":       ("CA.PRIMARY_INC",     "Current Account — Primary income balance"),
    "400000":       ("CA.SECONDARY_INC",   "Current Account — Secondary income balance"),

    # --- Goods sub-cuts (2) ---
    "110000":       ("GOODS.EXPORTS",      "Goods exports (BoP basis)"),
    "120000":       ("GOODS.IMPORTS",      "Goods imports (BoP basis, FOB)"),

    # --- Services sub-cuts (3) — biggest line items ---
    "2B0000":       ("SVC.TRANSPORT",      "Services — Transport balance"),
    "2C0000":       ("SVC.TRAVEL",         "Services — Travel balance"),
    "2D0000":       ("SVC.CONSTRUCTION",   "Services — Construction balance"),

    # --- Primary income sub-cut (1) ---
    "3B0000":       ("PRIMARY.INVEST_INC", "Primary income — Investment income balance"),

    # --- Financial Account family (12) ---
    "BOPF00000000": ("FA.TOTAL",           "Financial Account, total (net)"),
    "BOPF10000000": ("FA.DI.NET",          "FA — Direct Investment, net"),
    "BOPF11000000": ("FA.DI.ASSETS",       "FA — Direct Investment, assets (outward FDI)"),
    "BOPF12000000": ("FA.DI.LIAB",         "FA — Direct Investment, liabilities (inward FDI)"),
    "BOPF20000000": ("FA.PI.NET",          "FA — Portfolio Investment, net"),
    "BOPF21000000": ("FA.PI.ASSETS",       "FA — Portfolio Investment, assets"),
    "BOPF22000000": ("FA.PI.LIAB",         "FA — Portfolio Investment, liabilities"),
    "BOPF33000000": ("FA.DERIV.NET",       "FA — Financial Derivatives, net assets"),
    "BOPF40000000": ("FA.OI.NET",          "FA — Other Investment, net"),
    "BOPF41000000": ("FA.OI.ASSETS",       "FA — Other Investment, assets"),
    "BOPF42000000": ("FA.OI.LIAB",         "FA — Other Investment, liabilities"),
    "BOPF50000000": ("FA.RESERVES",        "FA — Reserve Assets, transactional change"),

    # --- Errors & Omissions (1) ---
    "BOPO00000000": ("EO",                 "Errors and Omissions"),
}


def _discover_full_codes(session) -> dict[str, str]:
    """Discovery call: one recent-period pull with objL1=ALL to learn the full
    prefixed C1 codes for each cut suffix in ``_CUTS``.

    The prefix (e.g. ``13102134519ACC_ITEM.``) is BOK's internal axis
    lookup-id and can rotate on table rebuilds, so we don't hardcode it.
    """
    rows = fetch_kosis_table(
        session,
        org_id="301",
        tbl_id="DT_301Y013",
        obj_l1="ALL",
        itm_id="ALL",
        prd_se="M",
        new_est_prd_cnt=1,
    )
    by_suffix: dict[str, str] = {}
    for r in rows:
        c1 = r.get("C1") or ""
        suffix = c1.split(".")[-1] if "." in c1 else c1
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
    c1_map = _discover_full_codes(session)
    print(f"got {len(c1_map)} of {len(_CUTS)} expected")
    missing = set(_CUTS) - set(c1_map)
    if missing:
        print(f"  WARN: suffix(es) not found in discovery pull: {sorted(missing)}")

    indicators: list[IndicatorRow] = []
    observations: list[ObservationRow] = []

    for c1_suffix, (cut_suffix, display) in _CUTS.items():
        full_c1 = c1_map.get(c1_suffix)
        if not full_c1:
            continue
        print(f"  Fetching BoP {cut_suffix} ({c1_suffix}) ...", end=" ", flush=True)
        rows = fetch_kosis_table(
            session,
            org_id="301",
            tbl_id="DT_301Y013",
            obj_l1=full_c1,
            itm_id="ALL",
            prd_se="M",
            start_prd_de="198001",
            end_prd_de=datetime.date.today().strftime("%Y%m"),
        )
        print(f"{len(rows)} rows")

        imdr_code = f"BOK.BOP.{cut_suffix}.KR"
        indicators.append(IndicatorRow(
            imdr_code=imdr_code,
            vendor_name="KOSIS",
            source_code=f"301/DT_301Y013/{full_c1}",
            display_name=f"Korea — {display} (BOK, USD mn)",
            unit="usd_mn",
            frequency="MONTHLY",
            country_iso="KR",
            category="bop",
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
        topic="bop",
        fetch_fn=run_fetch,
        description=__doc__.splitlines()[0] if __doc__ else "",
        country_code="KR",
    )


if __name__ == "__main__":
    import sys
    sys.exit(main())
