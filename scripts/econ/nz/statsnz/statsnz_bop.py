"""Stats NZ — Balance of Payments + International Investment Position fetcher.

Pulls the headline current-account decomposition (Table 1, NSA actual), the
seasonally-adjusted current account (Table 4), the key international ratios
(Table 18, year-ended-in-quarter %), and the IIP functional breakdown
(Table 2) from the single BoP/IIP release-page CSV.

Release-page asset:
  `balance-of-payments-and-international-investment-position-{Month-YYYY-quarter}.csv`

Direct `httpx` GET; ~33 MB CSV with ~224k rows across BOP + IIP subjects.
We filter client-side to the 32-indicator macro set below.

Coverage: 32 indicators. Cells 3.2 (Current Account) + 3.3 (Capital Account /
IIP). Identity checks (run post-load):
  CA balance ~= goods bal + services bal + primary income bal + secondary income bal
  Net IIP    = total assets - total liabilities
"""

from __future__ import annotations

import sys

from imdr.domains.econ.statsnz_common import (
    StatsNZClient,
    StatsNZSeries,
    parse_release_csv,
    rows_to_indicator_observations,
)
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main


_BASE = "https://www.stats.govt.nz/assets/Uploads"
# Latest published release — bump each quarter as Stats NZ publishes. The CSV
# carries full history, so this only pins which release-page asset to fetch.
_DEFAULT_RELEASE = "march-2026-quarter"

# 32 indicators: current account (NSA + SA) + key ratios + IIP functional split.
_BOP_SPECS = {
    s.source_code: s
    for s in [
        # --- Current account, NSA actual (Table 1) ---
        StatsNZSeries("BOPQ.S06AC100000000D", "STATSNZ.BOP.CURRENT_ACCOUNT_BAL.NZ",
                      "Current account balance (NSA)", "nzd_mn", "QUARTERLY", "bop"),
        StatsNZSeries("BOPQ.S06AC1000000D11", "STATSNZ.BOP.GOODS_BAL.NZ",
                      "Goods balance (NSA)", "nzd_mn", "QUARTERLY", "bop"),
        StatsNZSeries("BOPQ.S06AC1000000A11", "STATSNZ.BOP.GOODS_EXPORTS.NZ",
                      "Goods exports (fob, NSA)", "nzd_mn", "QUARTERLY", "bop"),
        StatsNZSeries("BOPQ.S06AD1000000A11", "STATSNZ.BOP.GOODS_IMPORTS.NZ",
                      "Goods imports (fob, NSA)", "nzd_mn", "QUARTERLY", "bop"),
        StatsNZSeries("BOPQ.S06AC1000000D12", "STATSNZ.BOP.SERVICES_BAL.NZ",
                      "Services balance (NSA)", "nzd_mn", "QUARTERLY", "bop"),
        StatsNZSeries("BOPQ.S06AC1000000A12", "STATSNZ.BOP.SERVICES_EXPORTS.NZ",
                      "Services exports (NSA)", "nzd_mn", "QUARTERLY", "bop"),
        StatsNZSeries("BOPQ.S06AD1000000A12", "STATSNZ.BOP.SERVICES_IMPORTS.NZ",
                      "Services imports (NSA)", "nzd_mn", "QUARTERLY", "bop"),
        StatsNZSeries("BOPQ.S06AC1000000D21", "STATSNZ.BOP.PRIMARY_INCOME_BAL.NZ",
                      "Primary income balance (NSA)", "nzd_mn", "QUARTERLY", "bop"),
        StatsNZSeries("BOPQ.S06AC1000000A21", "STATSNZ.BOP.PRIMARY_INCOME_INFLOW.NZ",
                      "Primary income inflow (NSA)", "nzd_mn", "QUARTERLY", "bop"),
        StatsNZSeries("BOPQ.S06AD1000000A21", "STATSNZ.BOP.PRIMARY_INCOME_OUTFLOW.NZ",
                      "Primary income outflow (NSA)", "nzd_mn", "QUARTERLY", "bop"),
        StatsNZSeries("BOPQ.S06AC1000000D22", "STATSNZ.BOP.SECONDARY_INCOME_BAL.NZ",
                      "Secondary income balance (NSA)", "nzd_mn", "QUARTERLY", "bop"),
        StatsNZSeries("BOPQ.S06AC1000000A22", "STATSNZ.BOP.SECONDARY_INCOME_INFLOW.NZ",
                      "Secondary income inflow (NSA)", "nzd_mn", "QUARTERLY", "bop"),
        StatsNZSeries("BOPQ.S06AD1000000A22", "STATSNZ.BOP.SECONDARY_INCOME_OUTFLOW.NZ",
                      "Secondary income outflow (NSA)", "nzd_mn", "QUARTERLY", "bop"),
        StatsNZSeries("BOPQ.S06AC000000000E", "STATSNZ.BOP.CAPITAL_ACCOUNT_BAL.NZ",
                      "Capital account balance (NSA)", "nzd_mn", "QUARTERLY", "bop"),
        # --- Current account, seasonally adjusted (Table 4) ---
        StatsNZSeries("BOPQ.S06SC300000000D", "STATSNZ.BOP.CURRENT_ACCOUNT_BAL_SA.NZ",
                      "Current account balance, SA", "nzd_mn", "QUARTERLY", "bop", is_sa=True),
        StatsNZSeries("BOPQ.S06SC20000000D1", "STATSNZ.BOP.GOODS_SERVICES_BAL_SA.NZ",
                      "Goods and services balance, SA", "nzd_mn", "QUARTERLY", "bop", is_sa=True),
        StatsNZSeries("BOPQ.S06SC4000000D11", "STATSNZ.BOP.GOODS_BAL_SA.NZ",
                      "Goods balance, SA", "nzd_mn", "QUARTERLY", "bop", is_sa=True),
        # --- Key international ratios (Table 18, year-ended-in-quarter %) ---
        StatsNZSeries("BOPQ.S06AR00CABTOGDP", "STATSNZ.BOP.CA_TO_GDP.NZ",
                      "Current account balance to GDP (year-ended %)", "pct", "QUARTERLY", "bop"),
        StatsNZSeries("BOPQ.S06AR0NIIPTOGDP", "STATSNZ.IIP.NET_IIP_TO_GDP.NZ",
                      "Net IIP to GDP (%)", "pct", "QUARTERLY", "bop"),
        StatsNZSeries("BOPQ.S06AR0NEXDTOGDP", "STATSNZ.IIP.NET_EXT_DEBT_TO_GDP.NZ",
                      "Net external debt to GDP (%)", "pct", "QUARTERLY", "bop"),
        # --- International investment position (Table 2, NZ$m end-of-quarter) ---
        StatsNZSeries("IIPQ.S06AA100000000Q", "STATSNZ.IIP.NET_IIP.NZ",
                      "Net international investment position", "nzd_mn", "QUARTERLY", "bop"),
        StatsNZSeries("IIPQ.S06AA100000000P", "STATSNZ.IIP.ASSETS_TOTAL.NZ",
                      "NZ international assets, total", "nzd_mn", "QUARTERLY", "bop"),
        StatsNZSeries("IIPQ.S06AA00000000P1", "STATSNZ.IIP.ASSETS_DIRECT.NZ",
                      "Assets - direct investment", "nzd_mn", "QUARTERLY", "bop"),
        StatsNZSeries("IIPQ.S06AA00000000P2", "STATSNZ.IIP.ASSETS_PORTFOLIO.NZ",
                      "Assets - portfolio investment", "nzd_mn", "QUARTERLY", "bop"),
        StatsNZSeries("IIPQ.S06AA00000000P3", "STATSNZ.IIP.ASSETS_FIN_DERIV.NZ",
                      "Assets - financial derivatives", "nzd_mn", "QUARTERLY", "bop"),
        StatsNZSeries("IIPQ.S06AA00000000P4", "STATSNZ.IIP.ASSETS_OTHER.NZ",
                      "Assets - other investment", "nzd_mn", "QUARTERLY", "bop"),
        StatsNZSeries("IIPQ.S06AA00000000P5", "STATSNZ.IIP.ASSETS_RESERVE.NZ",
                      "Assets - reserve assets (official reserves)", "nzd_mn", "QUARTERLY", "bop"),
        StatsNZSeries("IIPQ.S06AL100000000P", "STATSNZ.IIP.LIABILITIES_TOTAL.NZ",
                      "NZ international liabilities, total", "nzd_mn", "QUARTERLY", "bop"),
        StatsNZSeries("IIPQ.S06AL00000000P1", "STATSNZ.IIP.LIABILITIES_DIRECT.NZ",
                      "Liabilities - direct investment", "nzd_mn", "QUARTERLY", "bop"),
        StatsNZSeries("IIPQ.S06AL00000000P2", "STATSNZ.IIP.LIABILITIES_PORTFOLIO.NZ",
                      "Liabilities - portfolio investment", "nzd_mn", "QUARTERLY", "bop"),
        StatsNZSeries("IIPQ.S06AL00000000P3", "STATSNZ.IIP.LIABILITIES_FIN_DERIV.NZ",
                      "Liabilities - financial derivatives", "nzd_mn", "QUARTERLY", "bop"),
        StatsNZSeries("IIPQ.S06AL00000000P4", "STATSNZ.IIP.LIABILITIES_OTHER.NZ",
                      "Liabilities - other investment", "nzd_mn", "QUARTERLY", "bop"),
    ]
}


def _url(release: str) -> str:
    title = "Balance-of-payments-and-international-investment-position-" + "-".join(
        w.capitalize() if w != "quarter" else "quarter" for w in release.split("-")
    )
    return (
        f"{_BASE}/Balance-of-payments/"
        f"{title}/Download-data/"
        f"balance-of-payments-and-international-investment-position-{release}.csv"
    )


def run_fetch(
    since: str | None = None,
    until: str | None = None,
    *,
    release: str = _DEFAULT_RELEASE,
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    _ = since, until  # accepted for CLI uniformity; CSV gives full history.
    url = _url(release)
    print(f"[*] fetching {url}")
    with StatsNZClient() as c:
        text = c.fetch_csv(url)
    _, rows = parse_release_csv(text)
    indicators, observations = rows_to_indicator_observations(rows, _BOP_SPECS)
    print(f"  -> {len(rows)} CSV rows -> {len(indicators)} indicators, {len(observations)} obs")
    return indicators, observations


def main() -> int:
    return run_main(
        vendor="statsnz",
        topic="bop",
        fetch_fn=run_fetch,
        description="Stats NZ BoP/IIP - release december-2025-quarter; 32 quarterly indicators (current account NSA+SA + ratios + IIP functional split)",
        country_code="NZ",
    )


if __name__ == "__main__":
    sys.exit(main())
