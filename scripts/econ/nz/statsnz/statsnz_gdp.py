"""Stats NZ — quarterly GDP fetcher.

Pulls the headline real + nominal GDP totals + key expenditure components
+ production-side total + deflator from the GDP information-release CSV.

Release-page asset:
  `gross-domestic-product-{Month-YYYY-quarter}.csv`

Direct httpx GET; ~20 MB CSV with 97k rows and 1,004 series. We filter
client-side to the 14-indicator macro pair below.

Coverage: 14 indicators x ~155 quarters each = ~2,170 obs.
Cell 1.4 (Macro Core). Identity check (Phase 4):
  GDP-E ~= HH_FCE + Gov_FCE + Gross_capital_form + Inventories + (Exports - Imports)
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

# 14 indicators: GDP totals + expenditure decomp + external trade.
_GDP_SPECS = {
    s.source_code: s
    for s in [
        # --- Headline GDP totals ---
        StatsNZSeries("SNEQ.SG02RSC00B15", "STATSNZ.GDP.E_REAL_SA.NZ",
                      "Real GDP - expenditure measure, SA (chain-vol)",
                      "nzd_mn", "QUARTERLY", "gdp", is_sa=True),
        StatsNZSeries("SNEQ.SG02RSC31B15PC", "STATSNZ.GDP.E_REAL_QOQ_SA.NZ",
                      "Real GDP - expenditure measure, QoQ % change, SA",
                      "pct", "QUARTERLY", "gdp", is_sa=True),
        StatsNZSeries("SNEQ.SG02NSC00B15", "STATSNZ.GDP.E_NOMINAL_SA.NZ",
                      "Nominal GDP - expenditure measure, SA",
                      "nzd_mn", "QUARTERLY", "gdp", is_sa=True),
        StatsNZSeries("SNEQ.SG01RSC00B01", "STATSNZ.GDP.P_REAL_SA.NZ",
                      "Real GDP - production measure, SA (chain-vol)",
                      "nzd_mn", "QUARTERLY", "gdp", is_sa=True),
        StatsNZSeries("SNEQ.SG08NSC00B15", "STATSNZ.GDP.DEFLATOR_SA.NZ",
                      "GDP implicit price deflator, SA",
                      "index", "QUARTERLY", "gdp", is_sa=True),
        # --- Expenditure decomposition (chain-vol SA) ---
        StatsNZSeries("SNEQ.SG02RSC30P30E", "STATSNZ.GDP.HH_FCE_REAL_SA.NZ",
                      "Households Final Consumption Expenditure, SA (chain-vol)",
                      "nzd_mn", "QUARTERLY", "gdp", is_sa=True),
        StatsNZSeries("SNEQ.SG02RSC30P30C", "STATSNZ.GDP.GOVT_FCE_REAL_SA.NZ",
                      "General Government Final Consumption Expenditure, SA (chain-vol)",
                      "nzd_mn", "QUARTERLY", "gdp", is_sa=True),
        StatsNZSeries("SNEQ.SG02RSC00P50", "STATSNZ.GDP.GROSS_CAPITAL_FORM_REAL_SA.NZ",
                      "Gross Capital Formation, SA (chain-vol)",
                      "nzd_mn", "QUARTERLY", "gdp", is_sa=True),
        StatsNZSeries("SNEQ.SG02RSC00P52", "STATSNZ.GDP.INVENTORIES_REAL_SA.NZ",
                      "Changes in Inventories, SA (chain-vol)",
                      "nzd_mn", "QUARTERLY", "gdp", is_sa=True),
        StatsNZSeries("SNEQ.SG02RSC00B21", "STATSNZ.GDP.GNE_REAL_SA.NZ",
                      "Gross National Expenditure, SA (chain-vol)",
                      "nzd_mn", "QUARTERLY", "gdp", is_sa=True),
        # --- External account totals (chain-vol SA) ---
        StatsNZSeries("SNEQ.SG06RSC00P60", "STATSNZ.GDP.EXPORTS_GS_REAL_SA.NZ",
                      "Exports of Goods and Services, SA (chain-vol)",
                      "nzd_mn", "QUARTERLY", "gdp", is_sa=True),
        StatsNZSeries("SNEQ.SG06RSC00P70", "STATSNZ.GDP.IMPORTS_GS_REAL_SA.NZ",
                      "Imports of Goods and Services, SA (chain-vol)",
                      "nzd_mn", "QUARTERLY", "gdp", is_sa=True),
        StatsNZSeries("SNEQ.SG06RSC00P61", "STATSNZ.GDP.EXPORTS_GOODS_REAL_SA.NZ",
                      "Exports of Goods, SA (chain-vol)",
                      "nzd_mn", "QUARTERLY", "gdp", is_sa=True),
        StatsNZSeries("SNEQ.SG06RSC00P71", "STATSNZ.GDP.IMPORTS_GOODS_REAL_SA.NZ",
                      "Imports of Goods, SA (chain-vol)",
                      "nzd_mn", "QUARTERLY", "gdp", is_sa=True),
    ]
}


def _url(release: str) -> str:
    quarter_title = "Gross-domestic-product-" + "-".join(
        w.capitalize() if w != "quarter" else "quarter" for w in release.split("-")
    )
    return (
        f"{_BASE}/Gross-domestic-product/"
        f"{quarter_title}/Download-data/gross-domestic-product-{release}.csv"
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
    indicators, observations = rows_to_indicator_observations(rows, _GDP_SPECS)
    print(f"  -> {len(rows)} CSV rows -> {len(indicators)} indicators, {len(observations)} obs")
    return indicators, observations


def main() -> int:
    return run_main(
        vendor="statsnz",
        topic="gdp",
        fetch_fn=run_fetch,
        description="Stats NZ GDP - release december-2025-quarter; 14 quarterly indicators (real+nominal+deflator+5 expenditure decomp+4 external account)",
        country_code="NZ",
    )


if __name__ == "__main__":
    sys.exit(main())
