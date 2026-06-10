# RBA — `playground/econ/rba/`

Last updated: 2026-06-10

**Status:** DB-LIVE (manual load) — **9 fetchers, 119 indicators** (added TIB + I2 ICP + F15 REER + F17 zero-coupon curve 2026-06-10). Data sourced from Playwright-captured CSV snapshots in `playground/econ/rba/discovery/samples/`, NOT live HTTP (Akamai blocks direct requests). Live-refresh deferred.

Reserve Bank of Australia statistical tables (rba.gov.au/statistics). Excel + CSV downloads only — no JSON API.

## Contents

| File | Purpose |
|---|---|
| `_rba_csv.py` | CSV parser — handles RBA's per-table header layouts, produces tidy long-form dataframes. |
| `_rba_common.py` | Shared helpers mirroring `_abs_common.py` (parquet writer, indicator-key builder). |
| `fetch_rates.py` | RBA F1 + F2 — money market rates (cash rate, BBSW 1m/3m/6m, OIS 1m/3m/6m) + govt bond yields (2y/3y/5y/10y) + **10y indexed-bond real yield (TIB)** so breakeven inflation is computable as nominal − real. **12 indicators.** Daily cadence. |
| `fetch_icp.py` | **NEW 2026-06-10** — RBA I2 Index of Commodity Prices. 21 series across 7 sub-indices (Total / Rural / Non-rural / Base metals / Bulk exports / Total-w-spot / Bulk-spot) × 3 currencies (A$ / SDR / US$). Monthly since 1982. Cell 3.4 commodity-FX driver. CSV pulled via `fetch_d2_e_tables.py`. |
| `fetch_reer.py` | **NEW 2026-06-10** — RBA F15 Real Exchange Rate Measures. 3 quarterly series (Real TWI + Real import-weighted + Real export-weighted), since 1970. Closes cell 3.4 REER sub-bullet. |
| `fetch_zerocoupon.py` | **NEW 2026-06-10** — RBA F17 Zero-coupon AGB curve. 16 daily series: 8 desk tenors (0.25Y / 0.5Y / 1Y / 2Y / 3Y / 5Y / 7Y / 10Y) × yields + forward rates. Daily since 2017. Discount factors deferred (computable from yields). Cell 4.3 Financial Conditions. |
| `fetch_fx.py` | RBA F11.1 — AUD/USD + TWI + 17 AUD crosses. 19 indicators. Daily cadence. |
| `fetch_monetary.py` | RBA D3 — M1/M3/Broad money/Money base, NSA + SA. 14 indicators. Monthly cadence. |
| `fetch_d2_e_tables.py` | **Discovery/Playwright fetcher** — pulls D2 + E1 + E2 + A2 + **I1 + I2** CSVs into `discovery/samples/`. Not a loader; `fetch_credit_balsheet.py` and `fetch_icp.py` parse and load. E3 deliberately omitted: RBA publishes "Household Balance Sheets – Distribution" only as XLS (`e03hist.xls`), no CSV version exists. |
| `fetch_credit_balsheet.py` | RBA D2 (14 credit aggregates: owner-occupier housing / investor housing / business / personal / total credit / narrow credit × NSA+SA) + E1+E2 (16 balance-sheet and ratio series) + A2 (4 cash-rate event-log series). 34 indicators. Cells 4.1 / 4.2 / 4.4. |
| `explore.py` | Discovery — extracts table links from `rba.gov.au/statistics`. |
| `discovery/webfetch_inventory.md` | "RBA Statistical Tables — Inventory" — table-by-table catalogue. |
| `discovery/samples/` | CSV snapshots per table — **source of truth for current load**. |
| `profile_d2/` | Fresh Playwright profile used by `fetch_d2_e_tables.py` — wiped + re-created each run. |
| `sample_output/` | Parquet snapshots per fetcher (loaded into DB via canonical loader). |

## Loaded tables

| Table | Topic | Cadence | Indicators |
|---|---|:---:|:---:|
| **F1 + F2** | Cash rate, BBSW 1m/3m/6m, OIS 1m/3m/6m, govt bonds 2y/3y/5y/10y + **TIB 10y real yield** (breakeven-inflation enabler) | Daily | 12 |
| **F11.1** | AUD/USD + TWI + 17 AUD crosses | Daily | 19 |
| **D3** | M1/M3/Broad money/Money base (NSA + SA) | Monthly | 14 |
| **D2** | Credit aggregates — owner-occupier housing / investor housing / business / personal / total credit / narrow credit × NSA+SA | Monthly | 14 |
| **E1 + E2** | Household total assets/liabilities/net worth + business loans/liabilities + 8 gearing ratios (debt-to-income 177.0%, housing-DTI 133.7%, etc.) | Quarterly | 16 |
| **A2** | Cash Rate Target + administered rate event log | Event | 4 |
| **I2** | Index of Commodity Prices: 7 sub-indices (Total/Rural/Non-rural/Base metals/Bulk export/Total-w-spot/Bulk-spot) × A$/SDR/US$ | Monthly | 21 |
| **F15** | Real Exchange Rate Measures (TWI + import-weighted + export-weighted), Index Mar-1995=100 | Quarterly | 3 |
| **F17** | Zero-coupon AGB curve: yields + forward rates @ 8 tenors (0.25Y / 0.5Y / 1Y / 2Y / 3Y / 5Y / 7Y / 10Y) | Daily | 16 |

**Discovered but deferred** — `f16-data.csv` (Indicative Mid Rates of Selected Australian Government Securities) contains per-ISIN yields for ~62 individual AGBs (51 nominal Treasury Bonds + 11 Treasury Indexed Bonds). Better fit for a future `dbo.dim_bond_instrument` schema than `econ.dim_indicator` — each ISIN is an instrument, not a macro indicator. Snapshot is in `discovery/samples/f16-data.csv` for when that schema lands.

## Transport

Current load: static CSV snapshots from `discovery/samples/`. Parsers in `_rba_csv.py` handle RBA's varied header layouts.

Live refresh: Playwright-based, headed. `fetch_d2_e_tables.py` uses a fresh-per-run `profile_d2/` (Chrome channel) and that pattern is what the next live-refresh wiring should standardise on. GET to `rba.gov.au/statistics` without a warmed profile = 403 / Akamai JS challenge. Per `feedback_no_anti_detection_research.md` — do NOT add stealth plugins, automation-hiding flags, or aggressive parallelism. If a profile breaks, wipe + warm a fresh one (see `fetch_d2_e_tables.py:43-46`).

## Next moves

1. Live-refresh stabilisation: confirm Playwright profile in `profile/` survives a fresh checkout, then wire all 5 loaded fetchers to pull live CSV before canonical loader runs.
2. Production scheduler wiring requires explicit user OK.

## Related

- [`abs.md`](abs.md) — sibling AU vendor (real-economy side)
