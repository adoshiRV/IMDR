# Australia — Econ Documentation

Last updated: 2026-07-14

AU macroeconomic data. **Status: DB-LIVE (manual load) — 758 indicators / 523,708 obs (DB-verified 2026-07-14; up from 469 / 397,118 on 2026-06-19). ABS 20 fetchers / 22 dataflows (324 indicators, incl. new age/state labour breakdowns) + RBA 9 fetchers via CSV snapshot (119 indicators, incl. TIB + I2 ICP + F15 REER + F17 zero-coupon curve) + AOFM 5 fetchers (157 indicators) + Cotality (16 indicators — 6 daily + 10 monthly HVI) + SQM Research (33, rents+vacancy) + APRA MADIS (8, by-bank housing loans) + SEEK (90, job-ad+salary indices) + ANZ-Indeed (3, job ads) + FRED OECD mirror (3 indicators). 16 of 16 wiring-map cells ✅ (3.1 ToT closed 2026-06-11). Second-most-populated country after Indonesia.**

**2026-07-14 housing + labour tracking buildout:** 5 new sources (Cotality monthly, SQM Research, APRA MADIS, SEEK, ANZ-Indeed) + extended ABS labour age/state breakdowns — see [`australia_indicator_inventory.md`](australia_indicator_inventory.md) for the full detail and DB-verified counts.

> **Phase G blocker lifted 2026-06-10.** AOFM data is now in DB (157 indicators / 268,195 obs). Production promotion can proceed with explicit user sign-off. AOFM refresh is manual-monthly via Edge (corp TLS-inspection blocks Chrome/Playwright on `*.gov.au/sites/default/files/*.xlsx`; Edge uses Schannel and is unaffected). See [`_playground/aofm.md`](_playground/aofm.md).

- **ABS (Australian Bureau of Statistics)** — CPI, GDP, labour, retail, trade. SDMX API.
- **RBA (Reserve Bank of Australia)** — Excel statistical tables for rates, yields, FX, monetary aggregates. Akamai-protected — Playwright required.

Some AU coverage is already filled via FRED's OECD-mirror feeds (see [`../united_states/_playground/fred.md`](../united_states/_playground/fred.md)). Native ABS/RBA ingest would replace the OECD mirrors with source-of-truth.

## Access paths

| Path | Auth | Speed | Coverage | Status |
|---|---|---|---|---|
| **ABS SDMX API** | None | Fast | Real-economy series (CPI, **CPI_Q**, GDP, Labour Force + Underutilisation, WPI, PPI_FD, Retail Trade, BOP, BOP_GOODS, ITPI, ANA_EXP, Job Vacancies, CAPEX, Lending, RPPI, IIP) | **DB-LIVE** — 22 dataflows, 184 indicators (`CPI_Q` dataflow added 2026-06-19 — 6 SA quarterly analytical CPI series; IIP 33-series loaded 2026-06-10 closes cell 3.3 stock-side). See [`_playground/abs.md`](_playground/abs.md). |
| **RBA statistical tables** — CSV snapshots in `playground/econ/rba/discovery/samples/` | None | Static snapshot (Akamai blocks live HTTP) | F1+F2 rates (11 series), F11.1 FX/TWI (19 series), D3 monetary aggregates (14 series), D2 credit aggregates (14 series), E1+E2 balance-sheet ratios (16 series), A2 cash-rate event log (4 series) | **DB-LIVE** — 5 fetchers, 78 indicators via CSV snapshot. Live refresh deferred (Playwright required). See [`_playground/rba.md`](_playground/rba.md). |
| **RBA statistical tables** — `rba.gov.au/statistics/tables/` (live) | None | Slow (Playwright) | Full RBA stats coverage: balance sheet, OMO, AGS holdings, forecasts, Chart Pack, E-tables | **Discovery only** — live refresh of the 3 loaded tables + E-tables / A2 pending Playwright stabilisation. |
| **RBA historical data** — `rba.gov.au/statistics/historical-data.html` | None | Slow (Playwright) | Long-run series back to 1969 / 1949 | **Discovery only** |
| **AOFM Data Hub** — `aofm.gov.au/data-hub` | None | Manual Edge download (Chrome blocked by corp TLS-inspection) | AGS outstanding, issuance, buybacks, holdings by investor category (**only source**), secondary turnover, term-premium estimates | **DB-LIVE** — 157 indicators / 268,195 obs. 5 fetchers. Manual monthly refresh via Edge. See [`_playground/aofm.md`](_playground/aofm.md). |
| **ASX bond market data** — `asx.com.au/markets/.../bonds` | None (delayed) / subscriber (Austraclear) | Mixed | Exchange-traded AGB + TIB prices, yield-curve data, monthly bond market updates; subscriber-tier Austraclear debt/repo activity | **Discovery only** — a separate undocumented `asx_rate_tracker.py` (5 indicators, cash-rate-implied probabilities) is already DB-live since 2026-06-15; not narrated further here. |
| **Cotality (formerly CoreLogic)** — `cotality.com/au/our-data/indices` | None | Fast (Playwright render) | Daily + monthly Home Value Index, 5-8 capitals + aggregate | **DB-LIVE** — 16 indicators (6 daily + 10 monthly, added 2026-07-14). 2 fetchers. See [`_playground/cotality.md`](_playground/cotality.md). |
| **SQM Research** — `sqmresearch.com.au` | None | Fast (inline JSON in page HTML) | Weekly asking rents + monthly vacancy rates, 8 capitals + national | **DB-LIVE** (NEW 2026-07-14) — 33 indicators / 21,729 obs. 1 fetcher, new vendor. See [`_playground/sqm.md`](_playground/sqm.md). |
| **APRA MADIS** — `apra.gov.au/monthly-authorised-deposit-taking-institution-statistics` | None | Fast (plain XLSX download) | By-bank (CBA/WBC/NAB/ANZ) housing loan books, owner-occ + investor | **DB-LIVE** (NEW 2026-07-14) — 8 indicators / 696 obs. 1 fetcher. See [`_playground/apra.md`](_playground/apra.md). |
| **SEEK** — `au.seek.com/about/news/article/seek-employment-data` | None | Fast (plain XLSX download) | Advertised Job Index + Advertised Salary Index, national + state (+ industry for salary) | **DB-LIVE** (NEW 2026-07-14) — 90 indicators / 14,526 obs. 1 fetcher, new vendor. See [`_playground/seek.md`](_playground/seek.md). |
| **ANZ-Indeed Job Ads** — `anz.com.au/newsroom/media/release-dates/` | None | Fast (plain XLSX download) | Australian Job Ads index, national, since 1975 | **DB-LIVE** (NEW 2026-07-14) — 3 indicators / 1,854 obs. 1 fetcher. See [`_playground/anz.md`](_playground/anz.md). |
| **FRED OECD mirror** | FRED API key | Fast | Headline AU series via OECD | Live (partial) |

## Playground

- [`_playground/abs.md`](_playground/abs.md) — ABS SDMX playground: fetchers live across 22 dataflows (CPI, **CPI_Q**, GDP, Labour + LF_UNDER (extended 2026-07-14 with age/state breakdowns), WPI, PPI_FD, Retail, BOP, BOP_GOODS, ITPI imp+exp, ANA_EXP, JV, CAPEX, Lending, RPPI, IIP, Building Approvals). **324 indicators DB-loaded** (DB-verified 2026-07-14; see doc for count-reconciliation notes).
- [`_playground/cotality.md`](_playground/cotality.md) — Cotality (formerly CoreLogic) playground: Daily + **Monthly (NEW 2026-07-14)** Home Value Index. 16 indicators DB-loaded (6 daily + 10 monthly).
- [`_playground/sqm.md`](_playground/sqm.md) — SQM Research playground (NEW 2026-07-14): weekly asking rents + monthly vacancy rates, 8 capitals + national. 33 indicators DB-loaded, new vendor.
- [`_playground/apra.md`](_playground/apra.md) — APRA MADIS playground (NEW 2026-07-14): by-bank (CBA/WBC/NAB/ANZ) housing loan books. 8 indicators DB-loaded.
- [`_playground/seek.md`](_playground/seek.md) — SEEK playground (NEW 2026-07-14): Advertised Job Index + Advertised Salary Index. 90 indicators DB-loaded, new vendor.
- [`_playground/anz.md`](_playground/anz.md) — ANZ-Indeed Job Ads playground (NEW 2026-07-14): national job-ads index since 1975. 3 indicators DB-loaded.
- [`_playground/rba.md`](_playground/rba.md) — RBA playground: 9 fetchers (rates F1+F2, FX F11.1, monetary D3, credit/balance-sheet D2+E1+E2+A2, ICP, REER, zero-coupon curve) reading CSV snapshots. 119 indicators DB-loaded. Live-refresh pending Playwright stabilisation.
- [`_playground/aofm.md`](_playground/aofm.md) — AOFM playground: **DB-LIVE**. 5 fetchers, 157 indicators. Manual monthly refresh via Edge (Chrome blocked by corp TLS-inspection). Phase G blocker lifted.
- [`australia_indicator_inventory.md`](australia_indicator_inventory.md) — 4×4 wiring-map tracker, ABS dataflow inventory, RBA table inventory, identity checks, quality bar, DB-verified total counts.
- [`au_cb_documents.md`](au_cb_documents.md) — download checklist for RBA / AOFM / Treasury / APRA / ABS document-style sources (Board minutes, SMP, FSR, Budget Papers, etc.). Document pipeline (not data pipeline). **Phase J PROD-BUILT 2026-06-11 ✅** — promoted to [`scripts/econ/au/govt/`](../../../scripts/econ/au/govt/) with 8 official streams writing to `research.dim_report` + `research.fact_chunk` + Qdrant + SharePoint via `imdr.research.filings.ingest_filing`. 9 reports / 201 chunks live in DB. Migration 092 applied (apra/treasury_au/nab seeded). Final scheduler gate (`scripts/imdr_daily.py:PIPELINES` registration) pending explicit OK. Sell-side AU streams (Westpac CCI, NAB BSI) explicitly excluded — covered by sell-side ingest path.

## Quick links

| Doc | Purpose |
|---|---|
| [`australia_govt_prod_pipeline.md`](australia_govt_prod_pipeline.md) | Phase J prod-pipeline reference — architecture, fetcher table, archive layout, idempotency, smoke checks |
| [`au_cb_documents.md`](au_cb_documents.md) | Agency inventory + per-stream crawl recipes |
| [`../../development/au_govt_filings.md`](../../development/au_govt_filings.md) | Phase J execution tracker — scope, bugs fixed, smoke results, DB state |
| [`australia_indicator_inventory.md`](australia_indicator_inventory.md) | Track A 4×4 wiring-map tracker (758 indicators / 16 of 16 cells ✅, DB-verified 2026-07-14) |

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
