# Australia — Econ Documentation

Last updated: 2026-06-05

AU macroeconomic data. **Status: pre-prod.** Two vendors discovered, neither loaded.

- **ABS (Australian Bureau of Statistics)** — CPI, GDP, labour, retail, trade. SDMX API.
- **RBA (Reserve Bank of Australia)** — Excel statistical tables for rates, yields, FX, monetary aggregates. Akamai-protected — Playwright required.

Some AU coverage is already filled via FRED's OECD-mirror feeds (see [`../united_states/_playground/fred.md`](../united_states/_playground/fred.md)). Native ABS/RBA ingest would replace the OECD mirrors with source-of-truth.

## Access paths

| Path | Auth | Speed | Coverage | Status |
|---|---|---|---|---|
| **ABS SDMX API** | None | Fast | Real-economy series (CPI workbooks, monthly + quarterly, capital-city detail, analytical series incl. trimmed mean) | **Discovery only** |
| **RBA statistical tables** — `rba.gov.au/statistics/tables/` | None | Slow (Playwright) | Monetary / FX / rates, financial aggregates, balance sheet, OMO, AGS holdings, RBA forecasts, Chart Pack | **Discovery only** |
| **RBA historical data** — `rba.gov.au/statistics/historical-data.html` | None | Slow (Playwright) | Long-run series for OMO, balance sheet, exchange rates, AGS yields, zero-coupon rates, banking fees back to 1969 / 1949 | **Discovery only** |
| **AOFM Data Hub** — `aofm.gov.au/data-hub` | None | Mixed (XLSX + CSV) | AGS outstanding, issuance, buybacks, holdings, secondary turnover, term-premium estimates, swap transactions, non-resident holdings | **Discovery only** |
| **ASX bond market data** — `asx.com.au/markets/.../bonds` | None (delayed) / subscriber (Austraclear) | Mixed | Exchange-traded AGB + TIB prices, yield-curve data, monthly bond market updates; subscriber-tier Austraclear debt/repo activity | **Discovery only** |
| **FRED OECD mirror** | FRED API key | Fast | Headline AU series via OECD | Live (partial) |

## Pre-prod

- [`_playground/abs.md`](_playground/abs.md) — ABS SDMX exploration (CPI workbook fetcher prototyped).
- [`_playground/rba.md`](_playground/rba.md) — RBA statistical-tables explorer (Akamai bypass via persistent Playwright profile).

## Policy & fiscal document sources

Document-style sources (not time-series). Note: rba.gov.au currently blocks request-based crawlers (HTTP 403) — Playwright with persistent profile needed, same Akamai layer as the stats tables.

| Source | URL | Cadence | Notes |
|---|---|:---:|---|
| **RBA Board minutes** | rba.gov.au/monetary-policy/rba-board-minutes/ | per meeting | Primary meeting-by-meeting narrative. |
| **RBA Statement on Monetary Policy** | rba.gov.au/publications/smp/ | quarterly | Forecast anchor. |
| **RBA Financial Stability Review** | rba.gov.au/publications/fsr/ | semi-annual | Systemic-risk + housing/credit stress. |
| **RBA speeches** | rba.gov.au/speeches/ | regular | Governor / deputy / senior staff. |
| **AOFM (debt management)** | aofm.gov.au | regular | Bond issuance, auction calendar, debt-supply context. |
| **Treasury MYEFO** | budget.gov.au/myefo/ | event-driven | Mid-year fiscal update; budget windows. |

## Related

- [`../macro_economy_wiring_map.md`](../macro_economy_wiring_map.md) — AU coverage state (mostly via FRED OECD).
- [`../onboarding_new_country.md`](../onboarding_new_country.md) — onboarding playbook when AU goes native.
