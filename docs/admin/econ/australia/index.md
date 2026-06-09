# Australia — Econ Documentation

Last updated: 2026-06-10

AU macroeconomic data. **Status: DB-LIVE (manual load) — 379 indicators / 339,631 obs. ABS 15 fetchers across 18 dataflows (141 indicators) + RBA 5 fetchers via CSV snapshot (78 indicators) + AOFM 5 fetchers (157 indicators) + FRED OECD mirror (3 indicators). 14 of 16 wiring-map cells ✅. Second-most-populated country after Indonesia.**

> **Phase G blocker lifted 2026-06-10.** AOFM data is now in DB (157 indicators / 268,195 obs). Production promotion can proceed with explicit user sign-off. AOFM refresh is manual-monthly via Edge (corp TLS-inspection blocks Chrome/Playwright on `*.gov.au/sites/default/files/*.xlsx`; Edge uses Schannel and is unaffected). See [`_playground/aofm.md`](_playground/aofm.md).

- **ABS (Australian Bureau of Statistics)** — CPI, GDP, labour, retail, trade. SDMX API.
- **RBA (Reserve Bank of Australia)** — Excel statistical tables for rates, yields, FX, monetary aggregates. Akamai-protected — Playwright required.

Some AU coverage is already filled via FRED's OECD-mirror feeds (see [`../united_states/_playground/fred.md`](../united_states/_playground/fred.md)). Native ABS/RBA ingest would replace the OECD mirrors with source-of-truth.

## Access paths

| Path | Auth | Speed | Coverage | Status |
|---|---|---|---|---|
| **ABS SDMX API** | None | Fast | Real-economy series (CPI, GDP, Labour Force + Underutilisation, WPI, PPI_FD, Retail Trade, BOP, BOP_GOODS, ITPI, ANA_EXP, Job Vacancies, CAPEX, Lending, RPPI) | **DB-LIVE** — 18 dataflows, 141 indicators. IIP probed 2026-06-10, load pending. See [`_playground/abs.md`](_playground/abs.md). |
| **RBA statistical tables** — CSV snapshots in `playground/econ/rba/discovery/samples/` | None | Static snapshot (Akamai blocks live HTTP) | F1+F2 rates (11 series), F11.1 FX/TWI (19 series), D3 monetary aggregates (14 series), D2 credit aggregates (14 series), E1+E2 balance-sheet ratios (16 series), A2 cash-rate event log (4 series) | **DB-LIVE** — 5 fetchers, 78 indicators via CSV snapshot. Live refresh deferred (Playwright required). See [`_playground/rba.md`](_playground/rba.md). |
| **RBA statistical tables** — `rba.gov.au/statistics/tables/` (live) | None | Slow (Playwright) | Full RBA stats coverage: balance sheet, OMO, AGS holdings, forecasts, Chart Pack, E-tables | **Discovery only** — live refresh of the 3 loaded tables + E-tables / A2 pending Playwright stabilisation. |
| **RBA historical data** — `rba.gov.au/statistics/historical-data.html` | None | Slow (Playwright) | Long-run series back to 1969 / 1949 | **Discovery only** |
| **AOFM Data Hub** — `aofm.gov.au/data-hub` | None | Manual Edge download (Chrome blocked by corp TLS-inspection) | AGS outstanding, issuance, buybacks, holdings by investor category (**only source**), secondary turnover, term-premium estimates | **DB-LIVE** — 157 indicators / 268,195 obs. 5 fetchers. Manual monthly refresh via Edge. See [`_playground/aofm.md`](_playground/aofm.md). |
| **ASX bond market data** — `asx.com.au/markets/.../bonds` | None (delayed) / subscriber (Austraclear) | Mixed | Exchange-traded AGB + TIB prices, yield-curve data, monthly bond market updates; subscriber-tier Austraclear debt/repo activity | **Discovery only** |
| **FRED OECD mirror** | FRED API key | Fast | Headline AU series via OECD | Live (partial) |

## Playground

- [`_playground/abs.md`](_playground/abs.md) — ABS SDMX playground: 15 fetchers live across 18 dataflows (CPI, GDP, Labour + LF_UNDER, WPI, PPI_FD, Retail, BOP, BOP_GOODS, ITPI imp+exp, ANA_EXP, JV, CAPEX, Lending, RPPI). 141 indicators DB-loaded. IIP probed 2026-06-10 (`discovery/probe_iip.py`); load is the next econ-side build.
- [`_playground/rba.md`](_playground/rba.md) — RBA playground: 5 fetchers (rates F1+F2, FX F11.1, monetary D3, credit/balance-sheet D2+E1+E2+A2) reading CSV snapshots. 78 indicators DB-loaded. Live-refresh pending Playwright stabilisation.
- [`_playground/aofm.md`](_playground/aofm.md) — AOFM playground: **DB-LIVE**. 5 fetchers, 157 indicators. Manual monthly refresh via Edge (Chrome blocked by corp TLS-inspection). Phase G blocker lifted.
- [`australia_indicator_inventory.md`](australia_indicator_inventory.md) — 4×4 wiring-map tracker, ABS dataflow inventory, RBA table inventory, identity checks, quality bar.
- [`au_cb_documents.md`](au_cb_documents.md) — download checklist for RBA / AOFM / Treasury / APRA / ABS document-style sources (Board minutes, SMP, FSR, Budget Papers, etc.). Document pipeline (not data pipeline). Discovery-only — none auto-ingested yet.

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
