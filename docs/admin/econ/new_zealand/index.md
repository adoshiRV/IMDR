# New Zealand — Econ Documentation

Last updated: 2026-06-19

NZ macroeconomic data. **Status: Stats NZ Track A PROD-LIVE 2026-06-18 — 1,063 indicators × 154,731 obs in `econ.fact_indicator` (1914→2026), 9 of 16 cells.** 13 prod fetchers under `scripts/econ/nz/statsnz/` + orchestrator `scripts/econ/nz/nz_monthly.py`, **wired into `scripts/imdr_monthly.py:PIPELINES` 2026-06-18** (runs on the weekly Windows-task cadence). Two access paths: release-page CSV (CPI/GDP/BoP) + **Infoshare** Playwright (PPI/CGPI/OTI/HLPI/LCI/QES/ECT/OMT/RTS/HLFS). Track B (RBNZ CB events) planned — Cloudflare-gated, see prod-pipeline doc. See [`new_zealand_prod_pipeline.md`](new_zealand_prod_pipeline.md) for prod; [`new_zealand_indicator_inventory.md`](new_zealand_indicator_inventory.md) for the 4×4 tracker.

- **RBNZ (Reserve Bank of New Zealand)** — 78 XLSX statistical tables (B/C/D/E/F/H/J/L/M/R/S/T series). Akamai-gated — Playwright required. 7,000 req/day cap. Owns cells 3.3 (foreign holdings), 3.4 (FX/TWI/reserves), 4.1-4.4 (monetary/financial).
- **Stats NZ** — three live interfaces: ADE SDMX API (`api.data.stats.govt.nz`, subscription key required), Infoshare (deep history, stateful ASP.NET — Playwright + `.sch` Export Direct), release pages (latest snapshot only, JS-rendered). Owns cells 1.1, 1.3, 1.4 (real-econ + labour), 2.1-2.4, 3.1, 3.2, 3.3 (flow side).
- **NZDMO** — sovereign debt manager (`debtmanagement.treasury.govt.nz`). AOFM-analogue but narrower — owns issuance/outstanding/tender results (cell 1.2 debt-stock); does NOT publish foreign holdings (that's RBNZ D30).
- **NZ Treasury** — Fiscal Time Series XLSX 1972→, monthly FSGNZ, BEFU/HYEFU semi-annual XLSX. Owns cell 1.2 revenue/expenditure + 1.4 forecasts.
- **BIS** — full NZ coverage on WS_EER / WS_CBPOL / WS_DSR / WS_CREDIT_GAP / WS_TC. Reuses `_bis_sdmx.py` helper.
- **FRED OECD mirror** — Tier-2 fallback; ~14 NZ-tagged series; existing ⚠ partial coverage in cells 1.4, 2.4, 4.4.

Per [[feedback-js-rendered-dont-bail]], every `www.stats.govt.nz` and `www.rbnz.govt.nz/-/media/...` URL is JS-rendered or Akamai-gated — Playwright with `networkidle` + 2s settle on each. Per [[feedback-no-anti-detection-research]] + [[feedback-slow-down]], no stealth plugins, no aggressive parallelism.

## Access paths

| Path | Auth | Speed | Coverage | Status |
|---|---|---|---|---|
| **RBNZ data-file-index** — `rbnz.govt.nz/statistics/series/data-file-index-page` | None (Akamai gate) | Slow (Playwright persistent context) | 78 XLSX tables — rates / FX / monetary aggregates / banking / sector lending | **Discovery resolved — 0 loaded** |
| **Stats NZ ADE SDMX API** — `api.data.stats.govt.nz/rest/...` | `Ocp-Apim-Subscription-Key` header | Fast | Recent & heavily-used dataflows (CPI / GDP / HLFS / BoP likely migrated; full scope confirmed post-signup) | **Discovery resolved — 0 loaded** |
| **Stats NZ Infoshare Export Direct** — `infoshare.stats.govt.nz/infoshare/exportdirect.aspx` | None | Slow (Playwright + `.sch` upload) | All historical series (CPI back to 1949, PPI to 1977, OTI to 1957) | **Discovery resolved — 0 loaded** |
| **Stats NZ release-page CSV** — `stats.govt.nz/information-releases/...` | None | Slow (Playwright) | Latest period only — already what existing `fetch.py` does | **1 CPI parquet sample on disk** |
| **NZDMO data hub** — `debtmanagement.treasury.govt.nz/investor-resources/data` | None | Fast (direct XLSX) | Nominal bonds + T-bills + IIB tender + issuance history + repurchases | **Discovery resolved — 0 loaded** |
| **NZ Treasury** — `treasury.govt.nz/publications/...` + `budget.govt.nz/budget/{YYYY}/data-library.htm` | None | Fast | Fiscal Time Series 1972→, FSGNZ monthly, BEFU/HYEFU XLSX | **Discovery resolved — 0 loaded** |
| **BIS SDMX-JSON** — `stats.bis.org/api/v2/data/...` | None | Fast | WS_EER + WS_CBPOL + WS_DSR + WS_CREDIT_GAP + WS_TC | **Discovery resolved — 0 loaded** |
| **FRED OECD mirror** | FRED API key | Fast | Headline NZ series via OECD | Live (partial — 4 cells ⚠) |

## Indicator inventory + phase plan

- [`new_zealand_indicator_inventory.md`](new_zealand_indicator_inventory.md) — **canonical** 4×4 tracker + vendor cascade per cell + Phase 2-9 build plan (gated).

## Pre-prod

- [`_playground/rbnz.md`](_playground/rbnz.md) — RBNZ statistical-tables explorer (persistent Playwright profile).
- [`_playground/statsnz.md`](_playground/statsnz.md) — Stats NZ source discovery (3 interfaces probed).

## Loading status

Per [[project-econ-loaded]]: still **0 indicators in `econ.fact_indicator`** (DB load gated). 13 Stats NZ playground fetchers (~1,000 indicators) smoke-verified to parquet under `playground/econ/statsnz/`. Two live access paths: release-page CSV (`_statsnz_common.py`) for CPI/GDP/BoP, and **Infoshare via Playwright** (`_infoshare.py`) for everything else — the Infoshare Export-Direct `.sch` path was NOT needed; the browse-tree → select-all → CSV mechanism works (see [[reference-statsnz-infoshare-recipe]]).

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
