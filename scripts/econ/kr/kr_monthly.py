"""Korea econ — MONTHLY+QUARTERLY+ANNUAL(+DAILY backstop) orchestrator.

Runs every Korean prod fetcher that publishes at monthly cadence or slower.
Annual and quarterly series live here too: their fetchers are idempotent
(MERGE on PK), so running them monthly is wasted work on the API side but
catches every release window without per-cadence scheduling overhead.

Excludes the weekly fetchers (see scripts.econ.kr.kr_weekly).

After all fetchers finish, the shared country runner queries econ.fact_indicator
for MONTHLY/QUARTERLY/ANNUAL KR rows touched in this run and emails a
consolidated report.

Wired into scripts/imdr_monthly.py:PIPELINES.

Usage:
    python -m scripts.econ.kr.kr_monthly
"""

from __future__ import annotations

import sys

from scripts.econ._country_runner import run


# Order is by topic alpha; the runner is sequential because KOSIS rate-limits
# concurrent connections from the same key.
PIPELINES: list[list[str]] = [
    # BIS WS_CBPOL D.KR — BOK Base Rate (policy rate). DAILY series, but it
    # changes only on MPC decisions; the monthly run is the backstop and
    # imdr_daily.py carries the 24h-latency path (mirrors Indonesia's
    # bis_indonesia wiring). See docs/admin/econ/econ_to_prod.md §G.3.
    [sys.executable, "-m", "scripts.econ.kr.bis.bis_korea"],
    [sys.executable, "-m", "scripts.econ.kr.kosis.kosis_balance_sheets"],
    [sys.executable, "-m", "scripts.econ.kr.kosis.kosis_bank_rates"],
    [sys.executable, "-m", "scripts.econ.kr.kosis.kosis_bop"],
    [sys.executable, "-m", "scripts.econ.kr.kosis.kosis_bsi"],
    [sys.executable, "-m", "scripts.econ.kr.kosis.kosis_consumer_survey"],
    [sys.executable, "-m", "scripts.econ.kr.kosis.kosis_corp_debt"],
    [sys.executable, "-m", "scripts.econ.kr.kosis.kosis_cpi"],
    [sys.executable, "-m", "scripts.econ.kr.kosis.kosis_fiscal"],
    [sys.executable, "-m", "scripts.econ.kr.kosis.kosis_gdp"],
    [sys.executable, "-m", "scripts.econ.kr.kosis.kosis_industrial"],
    [sys.executable, "-m", "scripts.econ.kr.kosis.kosis_labour"],
    [sys.executable, "-m", "scripts.econ.kr.kosis.kosis_lending"],
    [sys.executable, "-m", "scripts.econ.kr.kosis.kosis_money_aggregates"],
    [sys.executable, "-m", "scripts.econ.kr.kosis.kosis_ppi"],
    [sys.executable, "-m", "scripts.econ.kr.kosis.kosis_retail"],
    [sys.executable, "-m", "scripts.econ.kr.kosis.kosis_tot"],
    [sys.executable, "-m", "scripts.econ.kr.kosis.kosis_trade_indices"],
    [sys.executable, "-m", "scripts.econ.kr.kosis.kosis_trade_prices"],
    [sys.executable, "-m", "scripts.econ.kr.kosis.kosis_wages"],
]


def main() -> int:
    return run(
        run_name="Monthly",
        country_code="KR",
        country_label="KR",
        country_name="Korea",
        orchestrator_path="scripts.econ.kr.kr_monthly",
        pipelines=PIPELINES,
        frequency_scope=["MONTHLY", "QUARTERLY", "ANNUAL", "DAILY"],
    )


if __name__ == "__main__":
    sys.exit(main())
