# KOSIS — `playground/econ/kosis/`

**Status:** LIVE (2026-06-03). 20 production fetchers, 164 indicators / 47,748 obs in `econ.fact_indicator`.

KOSIS 공유서비스 OpenAPI is the canonical Korea data source for IMDR. Mirrors BOK ECOS 1:1 (`tblId = DT_{STAT_CODE}` for `orgId=301` tables) plus KOSTAT-native tables (CPI, EAPS labour, retail, wages).

For API mechanics see [`../kosis_openapi_reference.md`](../kosis_openapi_reference.md). This note covers what lives in `playground/econ/kosis/`.

## Shared infrastructure

- **`_kosis_http.py`** — shared HTTP helper. TLS 1.2 pin (HTTPAdapter with `maximum_version = TLSVersion.TLSv1_2`), retry, period-cycle parser (`parse_kosis_period` handles M/Q/A/W). All fetchers route through this.
- **`capture_download.py`** — Playwright + network capture for download-URL discovery (used when a KOSIS table is not exposed on the OpenAPI and we have to fall back to the browser-download form).

## Fetchers (20)

Each `fetch_*.py` is a thin script that calls `_kosis_http.fetch_table()` with `orgId` + `tblId` + cuts and writes parquet pairs to `sample_output/{date}/`. Loaded into `econ.dim_indicator` via the canonical loader (`python -m scripts.migrations.load_econ_indicator_from_playground --vendor kosis`).

| Fetcher | Source | Table | What it pulls |
|---|---|---|---|
| `fetch_bop.py` | BOK 301 | `DT_301Y013` | Balance of Payments — refactored Playwright→OpenAPI 2026-06-05 |
| `fetch_cpi.py` | KOSTAT 101 | `DT_1J22042` | CPI headline + 14 subcategories |
| `fetch_ppi.py` | BOK 404 | `DT_404Y014` | PPI headline + subcategories |
| `fetch_gdp.py` | BOK 200 | `DT_200Y102` | Quarterly GDP expenditure components |
| `fetch_tot.py` | BOK 403 | `DT_403Y005` | Terms of Trade |
| `fetch_bank_rates.py` | BOK 121 | `DT_121Y002` | Bank deposit rates (NOT Base Rate — that lives elsewhere) |
| `fetch_reb_housing.py` | BOK 408 (REB mirror) | weekly indices | Korea apartment sale + jeonse indices (KOSIS-side mirror) |
| `fetch_labour.py` | KOSTAT | `DT_1DA7001S` | EAPS labour force, employment, unemployment |
| `fetch_retail.py` | KOSTAT | `DT_1K41013` | Retail sales |
| `fetch_fiscal.py` | BOK 200 | `DT_200Y154` | Public Sector Revenue/Expenditure (2-axis C1+C2) |
| `fetch_trade_prices.py` | BOK 401/402 | `DT_401Y015`, `DT_402Y014` | Import + Export prices × Won/USD basis |
| `fetch_lending.py` | BOK 514/151 | `DT_514Y001`, `DT_151Y005` | Lending Stance Survey + HH Loans monthly |
| `fetch_balance_sheets.py` | BOK 151 + FSS | `DT_151Y001`, `DT_376_10_…` | HH Credit + NPL (FSS NPL stale to 2016) |
| `fetch_wages.py` | KOSTAT | `DT_1YL15006` | Annual wages |
| `fetch_trade_indices.py` | BOK 403 | `DT_403Y001-004` | Trade Value + Volume |
| `fetch_money_*.py` | BOK | various | Money aggregates |
| `fetch_iip.py` | BOK 301 | various | International Investment Position |
| `fetch_consumer_survey.py` | BOK | various | Consumer sentiment |
| `fetch_bsi.py` | BOK | various | Business Survey Index |
| `fetch_corp_debt.py` | BOK | various | Corporate debt |

## Subdirs

- `discovery/` — `probe_*.json` capture from `capture_download.py` runs; used to nail down `(orgId, tblId, itmId)` triples for new tables.
- `sample_output/` — date-tree parquet output (`{YYYY}/{MM}/{DD}/{vendor}_{table}_{cut}_{dim|fact}.parquet`). Consumed by the loader.

## Gotchas

- **TLS 1.2 required** — handshake gets reset on TLS 1.3 from our network. Symptom: `ConnectionResetError [WinError 10054]`.
- **40k row per-call cap** — large tables must be paged via `prdInterval` / `startPrdDe`+`endPrdDe`.
- **Throttle by TLS reset, not HTTP 429.** Auth errors return HTTP 200 + `{err, errMsg}`.
- **Two `orgId`s in play:** BOK is `orgId=301`; KOSTAT-native tables (CPI, EAPS, retail, wages) use `orgId=101` or others.
- **Coverage-plan correction:** `DT_404Y014` is PPI not CPI; real CPI is KOSTAT `DT_1J22042`. `DT_121Y002` is bank deposit rates not BOK Base Rate.

## Next moves

- Wire daily-scrape production scripts under `scripts/econ/kosis/` once user signs off ([[feedback-no-prod-wiring-without-permission]]).
- KR wiring map cells remaining: see [`../kosis_kr_coverage_plan.md`](../kosis_kr_coverage_plan.md).
