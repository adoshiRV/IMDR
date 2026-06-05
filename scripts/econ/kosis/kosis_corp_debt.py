"""KOSIS BOK Corporate Financial Health fetcher (DT_501Y007).

Source: BOK orgId=301, **DT_501Y007** — 자산/자본 지표(제11차 한국표준산업분류)
Corporate Asset/Capital Indicators (annual, %). This is a **3-axis** table:
  - C1: business type (129 industries — A01..S99)
  - C2: enterprise scale (All / Large / SME / etc.)
  - C3: financial ratio (13 ratios — equity / current / quick / debt / etc.)

We pull **Manufacturing (C1=C) × All Enterprises (C2=A) × all 13 ratios**
= 13 indicators. Manufacturing is the most representative sector for Korea's
corp balance sheet (semi-conductors, autos, ships, chemicals).

Cell mapping: 4.2 Balance Sheets (corporate-debt sub-bullet).

History: annual, typically 2009 → most-recent-completed year.

Usage:
    C:/Users/adoshi/.conda/envs/imdr/python.exe scripts/econ/kosis/kosis_corp_debt.py
    python -m scripts.econ.kosis.kosis_corp_debt
"""

from __future__ import annotations

import datetime

from imdr.domains.econ.kosis_http import fetch_kosis_table, make_session, parse_kosis_period
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

# C1=C (Manufacturing) × C2=A (All Enterprises). C3 enumerated from discovery.
_C1_TARGET = "C"        # Manufacturing
_C2_TARGET = "A"        # All Enterprises

# C3 → (imdr_suffix, display) — all 13 ratios in DT_501Y007
_C3_LABELS: dict[str, tuple[str, str]] = {
    "701":  ("EQUITY_TO_ASSETS",        "Stockholders' equity to total assets"),
    "702":  ("CURRENT_RATIO",           "Current ratio"),
    "703":  ("QUICK_RATIO",             "Quick ratio"),
    "7041": ("CASH_RATIO",              "Cash ratio"),
    "7051": ("NONCURRENT_LIAB_RATIO_A", "Non-current liabilities ratio (variant A)"),
    "7061": ("FIXED_RATIO",             "Non-current assets to equity + non-current liabilities (fixed ratio)"),
    "707":  ("DEBT_RATIO",              "Debt ratio (total liab / total equity)"),
    "708":  ("CURRENT_LIAB_RATIO",      "Current liabilities ratio"),
    "7091": ("NONCURRENT_LIAB_RATIO_B", "Non-current liabilities ratio (variant B)"),
    "710":  ("BORROWINGS_TO_ASSETS",    "Total borrowings + bonds payable to total assets"),
    "711":  ("BORROWINGS_TO_SALES",     "Total borrowings + bonds payable to sales"),
    "712":  ("RECEIVABLES_PAYABLES",    "Receivables to payables"),
    "713":  ("NET_WC_TO_ASSETS",        "Net working capital to total assets"),
}


def _discover_full_codes(session):
    """1-period × ALL discovery — find full prefixed C1=C + C2=A codes."""
    rows = fetch_kosis_table(
        session, org_id="301", tbl_id="DT_501Y007",
        obj_l1="ALL", itm_id="ALL", prd_se="A",
        new_est_prd_cnt=1, extra_params={"objL2": "ALL", "objL3": "ALL"},
    )
    c1_full = c2_full = None
    for r in rows:
        c1 = r.get("C1") or ""; c2 = r.get("C2") or ""
        if c1.split(".")[-1] == _C1_TARGET and c1_full is None: c1_full = c1
        if c2.split(".")[-1] == _C2_TARGET and c2_full is None: c2_full = c2
        if c1_full and c2_full: break
    return c1_full, c2_full


def run_fetch(since, until):
    session = make_session()
    since_dt = datetime.date.fromisoformat(since) if since else None
    until_dt = datetime.date.fromisoformat(until) if until else None
    now = datetime.datetime.now(UTC)
    today_year = datetime.date.today().year

    print("  Discovering C1/C2 prefixes ...", end=" ", flush=True)
    c1_full, c2_full = _discover_full_codes(session)
    print(f"C1={c1_full and c1_full.split('.')[-1]}, C2={c2_full and c2_full.split('.')[-1]}")
    if not c1_full or not c2_full:
        print("  ERR: discovery did not surface C1=C and C2=A")
        return [], []

    print("  Fetching Corp Debt DT_501Y007 (Mfg × All Enterprises × all C3 ratios) ...", end=" ", flush=True)
    rows = fetch_kosis_table(
        session, org_id="301", tbl_id="DT_501Y007",
        obj_l1=c1_full, itm_id="ALL", prd_se="A",
        start_prd_de="2009", end_prd_de=str(today_year),
        extra_params={"objL2": c2_full, "objL3": "ALL"},
    )
    print(f"{len(rows)} rows")

    inds, obs = [], []
    # Discover what C3 codes are present + label everything we can.
    c3_seen: dict[str, str] = {}
    for r in rows:
        c3 = (r.get("C3") or "").split(".")[-1]
        nm = r.get("C3_NM_ENG") or r.get("C3_NM") or ""
        if c3 and c3 not in c3_seen:
            c3_seen[c3] = nm

    for c3, display in c3_seen.items():
        # Find a stable imdr suffix — use labelled if known, otherwise C3 code itself
        if c3 in _C3_LABELS:
            suffix, _ = _C3_LABELS[c3]
        else:
            # Clean the display for use as suffix
            suffix = c3.upper()
        sub = [r for r in rows if (r.get("C3") or "").split(".")[-1] == c3]
        if not sub: continue
        code = f"BOK.CORP_FIN.{suffix}.MFG.KR"
        unit = "pct"  # All 13 ratios are %
        inds.append(IndicatorRow(
            imdr_code=code, vendor_name="KOSIS",
            source_code=f"301/DT_501Y007/C1={_C1_TARGET}/C2={_C2_TARGET}/C3={c3}",
            display_name=f"Korea — Mfg Corporates — {display} (BOK Annual)",
            unit=unit, frequency="ANNUAL", country_iso="KR",
            category="balance_sheet", is_seasonally_adjusted=False, bbg_ticker=None,
        ))
        for r in sub:
            ymd = parse_kosis_period(r.get("PRD_DE"), "A")
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
        topic="corp_debt",
        fetch_fn=run_fetch,
        description=__doc__.splitlines()[0] if __doc__ else "",
    )


if __name__ == "__main__":
    import sys
    sys.exit(main())
