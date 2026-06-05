# New Zealand — Econ Documentation

Last updated: 2026-06-05

NZ macroeconomic data. **Status: pre-prod.** Two vendors discovered, neither loaded.

- **RBNZ (Reserve Bank of New Zealand)** — XLSX/CSV statistical tables. JS challenge — Playwright required.
- **Stats NZ** — multi-interface (REST API, bulk CSV, legacy Infoshare). API-based discovery validated.

Per [[feedback-js-rendered-dont-bail]], Stats NZ release pages render data via JS — one Playwright pass with `networkidle` + 2s settle yields 6 download URLs.

## Access paths

| Path | Auth | Speed | Coverage | Status |
|---|---|---|---|---|
| **RBNZ statistics** | None | Slow (Playwright) | Rates / FX / monetary aggregates / banking | **Discovery only** |
| **Stats NZ — Price indexes** — `stats.govt.nz/topics/price-indexes/` | None | Fast | CPI (Q + monthly from early 2027), SPI, HLPI, PPI, CGPI, FEPI, labour cost index, overseas trade indexes | **Discovery only** |
| **Stats NZ Infoshare / bulk CSV** | None | Fast | Long-run CSV time series across all topics | **Discovery only** |
| **data.govt.nz / MBIE** | None | Mixed | Selected employment, fuel/oil/gas/energy, reserves, and MRTE datasets | **Discovery only** |
| **FRED OECD mirror** | FRED API key | Fast | Headline NZ series via OECD | Live (partial) |

## Pre-prod

- [`_playground/rbnz.md`](_playground/rbnz.md) — RBNZ statistical-tables explorer (persistent Playwright profile).
- [`_playground/statsnz.md`](_playground/statsnz.md) — Stats NZ source discovery (3 interfaces probed).

## Loading status

Per [[project-econ-loaded]]: "Stats NZ (301/1622)" — 301 indicators discovered, 1622 cells of metadata captured, **0 loaded** to `econ.fact_indicator`. Parquet exists at `playground/econ/statsnz/sample_output/`. One `--vendor statsnz` away once parquet schema matches `schema_prototype.py`.

## Policy & fiscal document sources

Document-style sources (not time-series). rbnz.govt.nz currently blocks request-based crawlers (HTTP 403) — Playwright with persistent profile needed.

| Source | URL | Cadence | Notes |
|---|---|:---:|---|
| **RBNZ Monetary Policy Statement** | rbnz.govt.nz/monetary-policy/monetary-policy-statement | quarterly | Forecast anchor + committee reasoning. |
| **RBNZ OCR decisions archive** | rbnz.govt.nz/monetary-policy/monetary-policy-decisions | per meeting | Past decisions + media releases. |
| **RBNZ speeches** | rbnz.govt.nz/hub/publications/speech | regular | Governor / chief economist. |
| **RBNZ release-information schedule** | rbnz.govt.nz/news-and-events/how-we-release-information | reference | Crawler scheduling anchor. |

## Related

- [`../macro_economy_wiring_map.md`](../macro_economy_wiring_map.md) — NZ coverage state (mostly via FRED OECD).
- [`../onboarding_new_country.md`](../onboarding_new_country.md) — onboarding playbook.
