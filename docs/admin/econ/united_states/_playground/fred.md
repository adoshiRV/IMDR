# FRED — `playground/econ/fred/`

**Status:** LIVE. 173 indicators × 82,820 obs in `econ.fact_indicator` as of 2026-06-05. Primary US econ vendor.

FRED (Federal Reserve Economic Data, St. Louis Fed). REST API, dual-key rotation, ~170 hand-curated series organised into 13 buckets in `seed.yml`.

## Contents

| File | Purpose |
|---|---|
| `fetch.py` | Pull seed indicators from FRED API, write parquet, print preview. Supports vintage dates, release calendar, incremental updates. |
| `connector.py` | `FredClient` — REST wrapper around observations / release / updates / search endpoints with retry + structured logging. |
| `search.py` | Discovery CLI: interactive search of the FRED catalogue, filter/order by tags and search rank. |
| `validate_and_seed.py` | One-shot validation. Iterates hand-curated FRED IDs, validates against `/series`, writes verified `seed.yml` grouped by bucket. |
| `validate_series.py` | Throttled (0.6s) sanity check that each proposed series ID exists. |
| `seed.yml` | 173 indicators grouped into 13 buckets (see below). |
| `sample_output/` | Date-tree parquet output for the canonical loader. |

## seed.yml — bucket breakdown

| Bucket | Count | Examples |
|---|---|---|
| rates | 35 | DGS10, FEDFUNDS, SOFR, T10Y2Y |
| gdp | 27 | GDP, GDPC1, A191RP1Q027SBEA |
| cpi | 24 | CPIAUCSL, CPILFESL, headline + core |
| labour | 21 | UNRATE, PAYEMS, CIVPART |
| sentiment | 16 | UMCSENT, USACSCICP02STSAM (OECD CCI), business confidence |
| credit | 15 | BAA, AAA, credit-spread family |
| balance_sheet | 11 | WALCL, currency in circulation |
| housing | 5 | HOUST, CSUSHPISA, MORTGAGE30US |
| cb_balance_sheet | 5 | ECB / BoJ / BoE / SNB total assets |
| energy | 4 | DCOILWTICO, oil + gas reference |
| fx | 3 | DTWEXBGS, broad USD index |
| cb_facility | 3 | central-bank lending facilities |
| bop | 2 | NETFI, IEABC |
| liquidity | 2 | secured / unsecured overnight |

## OECD-mirror feeds

A subset of `seed.yml` rows are FRED-hosted OECD mirrors used for cross-country fields. Country mapped via `country_iso` in the seed entry. The wiring map (`../../macro_economy_wiring_map.md`) tracks which non-US countries are partially filled via these.

## Korea rates added 2026-06-05

4 Korea rate series wired into FRED ingest: Discount Rate, Call Money, 3M Interbank, 10Y Govt. These coexist with KOSIS-direct Korea rates — the FRED versions provide one-call cross-country comparison; the KOSIS versions are source-of-truth for KR.

## Gotchas

- **Dual-key rotation in the connector** (`IMDR_ECON_FRED_KEY` + `IMDR_ECON_FRED_KEY2`). Per-request round-robin, 0.5s throttle. Don't bypass this — the BOPBCA/MBST/CFSI replacement work hit a 429 storm without it.
- **Some series are discontinued.** `validate_series.py` catches these before they get into `seed.yml`. As of 2026-06-04 sweep: BOPBCA / MBST / CFSI all replaced.
- **FRED revisions are silent.** Re-pulling a historical observation can return a different value than yesterday's parquet. Vintage dates (`realtime_start`/`realtime_end`) are supported in `fetch.py` if we need point-in-time semantics — not used in current loader.

## Canonical loader

```bash
python -m scripts.migrations.load_econ_indicator_from_playground --vendor fred
```

Vendor-agnostic — same command pattern as KOSIS, HKMA, REB.
