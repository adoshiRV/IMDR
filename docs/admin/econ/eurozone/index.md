# Eurozone — Econ Documentation

Last updated: 2026-06-05

EU macroeconomic data (Eurozone, `dbo.dim_country.country_code = 'EU'`, display name "Eurozone (TARGET2)"). **Status: pre-prod.** No native ingest; partial coverage via FRED's OECD-mirror feeds.

Two cleanest primary sources: **ECB SDW** (Statistical Data Warehouse) and **Eurostat**. ECB SDW is best-in-class — REST SDMX-JSON, no key, very clean dataflow/series structure. Plus document-source set on `ecb.europa.eu` that crawls cleanly.

## Access paths

| Path | Auth | Speed | Coverage | Status |
|---|---|---|---|---|
| **ECB SDW (Data Portal)** — `data-api.ecb.europa.eu/service/data/...` | None | Fast (REST SDMX-JSON) | Rates, FX, monetary aggregates, banking, BoP — euro-area + per-country | **Not onboarded** |
| **Eurostat API** — `ec.europa.eu/eurostat/api/dissemination/statistics/1.0/...` | None | Fast (REST JSON-stat) | Pan-EU CPI/HICP, GDP, labour, trade, fiscal | **Not onboarded** |
| **FRED OECD mirror** | FRED API key | Fast | Headline EU series | Live (partial) |

Eurostat time codes use SDMX patterns (`2024-Q1`, `2024M03`); both APIs are dataset-oriented (declare a dataflow, then filter dimensions).

## Policy & fiscal document sources

`ecb.europa.eu` is crawler-friendly — all archives below returned HTTP 200 on probe.

| Source | URL | Cadence | Notes |
|---|---|:---:|---|
| **ECB monetary policy decisions archive** | ecb.europa.eu/press/govcdec/mopo/html/index.en.html | per meeting | Governing Council rate decisions. |
| **ECB monetary policy accounts** | ecb.europa.eu/press/accounts/html/index.en.html | per meeting | Minutes-equivalent (discussion + options). |
| **ECB staff projections** | ecb.europa.eu/press/projections/html/index.en.html | quarterly | Forecast layer. |
| **ECB speeches & introductory statements** | ecb.europa.eu/press/pubbydate/html/index.en.html?name_of_publication=Speech | regular | President, Chief Economist, Governing Council. |

## Related

- [`../macro_economy_wiring_map.md`](../macro_economy_wiring_map.md) §7.2 — EU coverage state.
- [`../onboarding_new_country.md`](../onboarding_new_country.md) — onboarding playbook.
