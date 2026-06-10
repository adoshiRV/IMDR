"""Indonesia econ — MONTHLY+QUARTERLY+SEMIANNUAL+ANNUAL+DAILY orchestrator.

Runs every Indonesia prod fetcher (BPS + BI + BIS + DJPPR). Higher-cadence
series (BIS daily policy rate, BPS monthly CPI/PPI/trade/labour, BI monthly
money/reserves/credit/banking rates, DJPPR daily SBN ownership) and lower-
cadence ones (BPS quarterly GDP, BPS semi-annual Sakernas, BI quarterly
BoP/SKDU, BI annual fiscal) all live under one monthly trigger because
fetchers are idempotent (MERGE on PK): running them monthly costs extra
API calls but catches every release window without per-cadence scheduling.

Indonesia has no WEEKLY-cadence series — no companion id_weekly.py is needed.

After all fetchers finish, the shared country runner queries
econ.fact_indicator for ID rows touched in this run and emails a
consolidated report.

To wire into scripts/imdr_monthly.py:PIPELINES (pending explicit user
sign-off per the no-prod-wiring durable rule).

Usage:
    python -m scripts.econ.id.id_monthly
"""

from __future__ import annotations

import sys

from scripts.econ._country_runner import run


# Order is by vendor + topic alpha; sequential because some vendors (BPS,
# BI SEKI portal) throttle aggressive concurrency and BIS is fast enough
# that parallelism wouldn't materially help.
PIPELINES: list[list[str]] = [
    # BIS first (smallest, fastest, no auth)
    [sys.executable, "-m", "scripts.econ.id.bis.bis_indonesia"],
    # BPS (10 fetchers, REST JSON)
    [sys.executable, "-m", "scripts.econ.id.bps.bps_cpi"],
    [sys.executable, "-m", "scripts.econ.id.bps.bps_cpi_groups"],
    [sys.executable, "-m", "scripts.econ.id.bps.bps_gdp"],
    [sys.executable, "-m", "scripts.econ.id.bps.bps_gdp_components"],
    [sys.executable, "-m", "scripts.econ.id.bps.bps_ip"],
    [sys.executable, "-m", "scripts.econ.id.bps.bps_labour"],
    [sys.executable, "-m", "scripts.econ.id.bps.bps_ppi"],
    [sys.executable, "-m", "scripts.econ.id.bps.bps_prices_current"],
    [sys.executable, "-m", "scripts.econ.id.bps.bps_sakernas"],
    [sys.executable, "-m", "scripts.econ.id.bps.bps_trade"],
    # BI (14 fetchers, SEKI XLSX + Survey ZIPs)
    [sys.executable, "-m", "scripts.econ.id.bi.bi_bank_bs"],
    [sys.executable, "-m", "scripts.econ.id.bi.bi_bank_credit"],
    [sys.executable, "-m", "scripts.econ.id.bi.bi_bank_rates"],
    [sys.executable, "-m", "scripts.econ.id.bi.bi_bop"],
    [sys.executable, "-m", "scripts.econ.id.bi.bi_business_survey"],
    [sys.executable, "-m", "scripts.econ.id.bi.bi_consumer_survey"],
    [sys.executable, "-m", "scripts.econ.id.bi.bi_fiscal"],
    [sys.executable, "-m", "scripts.econ.id.bi.bi_fx_reserves"],
    [sys.executable, "-m", "scripts.econ.id.bi.bi_monetary_base"],
    [sys.executable, "-m", "scripts.econ.id.bi.bi_money_supply"],
    [sys.executable, "-m", "scripts.econ.id.bi.bi_retail_sales"],
    [sys.executable, "-m", "scripts.econ.id.bi.bi_sbn"],
    [sys.executable, "-m", "scripts.econ.id.bi.bi_sbn_position"],
    [sys.executable, "-m", "scripts.econ.id.bi.bi_skdu_macro"],
    [sys.executable, "-m", "scripts.econ.id.bi.bi_sulni"],
    # DJPPR (1 fetcher, listing-API + per-file XLSX/PDF — runs late because
    # it pulls ~30 files via HTTP and is the slowest single step)
    [sys.executable, "-m", "scripts.econ.id.djppr.djppr_sbn_ownership"],
]


def main() -> int:
    return run(
        run_name="Monthly",
        country_code="ID",
        country_label="ID",
        country_name="Indonesia",
        orchestrator_path="scripts.econ.id.id_monthly",
        pipelines=PIPELINES,
        frequency_scope=["MONTHLY", "QUARTERLY", "SEMIANNUAL", "ANNUAL", "DAILY"],
    )


if __name__ == "__main__":
    sys.exit(main())
