"""BBG EconDashboards policy rates -> rates.fact_bench_rates.

Lands the 9 APAC central-bank policy rates that IMDR's rates benchmark model
did not previously cover (RBA, HKMA, BI, RBI, BoK, BNM, RBNZ, BSP, BoT). Source
is the EconDashboards SQLite (read-only staging); vendor = BBG (id 4). The
dim_central_bank rows are seeded by migrations/119_seed_rates_dim_central_bank_apac.sql
(run that first).

Excluded on purpose (per the rates-landing design):
  - US FDTR      -> already dim_central_bank id 3 (US_FED_FUNDS_TARGET), and the
                    fact_bench_rates key is (cb_id, obs_date) with no vendor_id,
                    so a BBG US row would collide with the Citi feed.
  - CN/JP/SG/TW  -> their "policy" tickers duplicate existing rates.fact_observation
                    curve points; not modelled as bench rates.

Usage:
    python -m scripts.rates.bbg_econdashboard_policy --no-load   # report only
    python -m scripts.rates.bbg_econdashboard_policy             # upsert
    python -m scripts.rates.bbg_econdashboard_policy --since 2024-01-01
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import select

from imdr.config.settings import get_settings
from imdr.connectors.mssql import MSSQLConnector
from imdr.domains.econ.bbg_econdashboard import read_ticker_observations
from imdr.domains.rates.pipeline_bench import BenchRatesRepository, CentralBankRepository
from imdr.models.vendor import DimVendor
from imdr.schemas.rates_bench import BenchRateCreate

# BBG ticker -> dim_central_bank.cb_code (seeded by migration 119).
TICKER_TO_CB: dict[str, str] = {
    "RBATCTR Index": "RBA_CASH_RATE",
    "HKBASE Index": "HKMA_BASE",
    "IDBIRRPO Index": "BI_RATE",
    "INRPYLDP Index": "RBI_REPO",
    "KORP7DR Index": "BOK_BASE_RATE",
    "MAOPRATE Index": "BNM_OPR",
    "NZOCR Index": "RBNZ_OCR",
    "PPCBON Index": "BSP_RRP",
    "BTRR1DAY Index": "BOT_REPO_1D",
}


def run(since: str | None, until: str | None, no_load: bool) -> int:
    obs = read_ticker_observations(list(TICKER_TO_CB), since=since, until=until)

    connector = MSSQLConnector(get_settings())
    with connector.session() as session:
        vendor = session.execute(
            select(DimVendor).where(DimVendor.vendor_code == "BBG")
        ).scalar_one_or_none()
        if vendor is None:
            print("ERROR: vendor 'BBG' not found in dbo.dim_vendor.", file=sys.stderr)
            return 2
        vendor_id = vendor.id
        cb_id_by_code = {cb.cb_code: cb.id for cb in CentralBankRepository(session).all()}

    missing = sorted({c for c in TICKER_TO_CB.values() if c not in cb_id_by_code})
    if missing:
        print(f"ERROR: central banks not seeded (run migration 119): {missing}", file=sys.stderr)
        return 2

    items: list[BenchRateCreate] = []
    print("Per-central-bank coverage:")
    for ticker, cb_code in TICKER_TO_CB.items():
        pts = obs.get(ticker, [])
        if not pts:
            print(f"  {cb_code:14s} ({ticker:16s}) -- no observations")
            continue
        cb_id = cb_id_by_code[cb_code]
        for obs_date, value in pts:
            items.append(BenchRateCreate(cb_id=cb_id, vendor_id=vendor_id, obs_date=obs_date, rate=value))
        lo, hi = pts[0][0], pts[-1][0]
        print(f"  {cb_code:14s} ({ticker:16s}) n={len(pts):4d}  {lo} -> {hi}  latest={pts[-1][1]}")

    print(f"\nTotal bench-rate rows: {len(items)}  (vendor_id={vendor_id} BBG)")
    if no_load:
        print("[--no-load] nothing written.")
        return 0
    with connector.session() as session:
        n = BenchRatesRepository(session).bulk_upsert(items)
    print(f"upserted {n} rows into rates.fact_bench_rates")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="BBG EconDashboards policy rates -> rates.fact_bench_rates")
    p.add_argument("--since", help="Earliest obs_date, YYYY-MM-DD.")
    p.add_argument("--until", help="Latest obs_date, YYYY-MM-DD.")
    p.add_argument("--no-load", action="store_true", help="Report only; no DB write.")
    args = p.parse_args()
    return run(args.since, args.until, args.no_load)


if __name__ == "__main__":
    sys.exit(main())
