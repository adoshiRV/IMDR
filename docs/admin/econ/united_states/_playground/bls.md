# BLS — `playground/econ/us/bls/`

**Status:** Discovery built (playground). Dry-run clean. Vendor row (`BLS`) pending migration 105 — not yet loaded into `econ.fact_indicator`. No `scripts/econ/us/` entry. Not wired into any orchestrator.

Bureau of Labor Statistics (BLS) Public Data API v2. POST-JSON endpoint, single registration key, 500 queries/day, 50 series/query, 20-year window per query. Primary release-day source for US CPI, PPI, employment, wages, and trade prices.

## Contents

| File | Purpose |
|---|---|
| `connector.py` | `BlsClient` — POST JSON wrapper with year-range chunking (20-yr cap), 0.5s throttle. `bls_period_to_date()` maps M01..M12, Q01..Q04 to obs_date. |
| `fetch_cpi.py` | 9 CPI-U series — headline + core + 5 components. Cell 2.4. |
| `fetch_ppi.py` | 6 PPI series — final demand headline + 3 splits + 2 stage-of-processing. Cell 2.2. |
| `fetch_employment_situation.py` | 6 Employment Situation series — payrolls, unemp rate, LFPR, AHE, employment/unemployment levels. Cell 1.4. |
| `fetch_eci_jolts.py` | 6 series across 2 cadences — ECI quarterly (×2) + productivity quarterly (×1) + JOLTS monthly (×3). Cell 2.3. |
| `fetch_import_export_prices.py` | 2 series — import price (EIUIR) + export price (EIUIQ). Cells 2.1 + 3.1. |

## Series breakdown

### `fetch_cpi` — 9 series (category `cpi`, unit `index`, monthly)

| BLS ID | IMDR code | Description | SA |
|---|---|---|:---:|
| CUSR0000SA0 | BLS.CPI.HEADLINE_SA.US | CPI-U All Items | yes |
| CUUR0000SA0 | BLS.CPI.HEADLINE_NSA.US | CPI-U All Items | no |
| CUSR0000SA0L1E | BLS.CPI.CORE_SA.US | CPI-U Less Food & Energy (Core) | yes |
| CUUR0000SA0L1E | BLS.CPI.CORE_NSA.US | CPI-U Less Food & Energy (Core) | no |
| CUSR0000SAF1 | BLS.CPI.FOOD_SA.US | CPI-U Food | yes |
| CUSR0000SA0E | BLS.CPI.ENERGY_SA.US | CPI-U Energy | yes |
| CUSR0000SAH1 | BLS.CPI.SHELTER_SA.US | CPI-U Shelter | yes |
| CUSR0000SAS | BLS.CPI.SERVICES_SA.US | CPI-U Services | yes |
| CUSR0000SACL1E | BLS.CPI.CORE_GOODS_SA.US | CPI-U Core Goods (Commodities less Food & Energy) | yes |

### `fetch_ppi` — 6 series (category `other`, unit `index`, monthly)

| BLS ID | IMDR code | Description | SA |
|---|---|---|:---:|
| WPSFD4 | BLS.PPI.FD_SA.US | PPI Final Demand | yes |
| WPSFD49116 | BLS.PPI.FD_EX_FE_SA.US | PPI Final Demand ex Food & Energy | yes |
| WPSFD41 | BLS.PPI.FD_GOODS_SA.US | PPI Final Demand Goods | yes |
| WPSFD42 | BLS.PPI.FD_SERVICES_SA.US | PPI Final Demand Services | yes |
| WPSID61 | BLS.PPI.INTERMED_PROCESSED.US | PPI Intermediate Demand Processed Goods | no |
| WPSID62 | BLS.PPI.INTERMED_UNPROCESSED.US | PPI Intermediate Demand Unprocessed Goods | no |

### `fetch_employment_situation` — 6 series (category `labour`, monthly, all SA)

| BLS ID | IMDR code | Unit |
|---|---|---|
| CES0000000001 | BLS.LABOUR.PAYROLLS_SA.US | th_persons |
| LNS14000000 | BLS.LABOUR.UNEMP_RATE_SA.US | pct |
| LNS11300000 | BLS.LABOUR.LFPR_SA.US | pct |
| CES0500000003 | BLS.LABOUR.AHE_PRIV_SA.US | usd (per hour) |
| LNS12000000 | BLS.LABOUR.EMP_LEVEL_SA.US | th_persons |
| LNS13000000 | BLS.LABOUR.UNEMP_LEVEL_SA.US | th_persons |

### `fetch_eci_jolts` — 6 series (category `labour`)

| BLS ID | IMDR code | Frequency | Unit |
|---|---|:---:|---|
| CIU1010000000000A | BLS.ECI.TOTAL_COMP.US | QUARTERLY | index |
| CIU2020000000000A | BLS.ECI.WAGES_SALARIES.US | QUARTERLY | index |
| PRS85006092 | BLS.PRODUCTIVITY.NONFARM.US | QUARTERLY | index |
| JTS000000000000000QUR | BLS.JOLTS.QUITS_RATE.US | MONTHLY | pct |
| JTS000000000000000JOL | BLS.JOLTS.JOB_OPENINGS.US | MONTHLY | th_persons |
| JTS000000000000000HIR | BLS.JOLTS.HIRES_RATE.US | MONTHLY | pct |

### `fetch_import_export_prices` — 2 series (category `other`, unit `index`, monthly, NSA)

| BLS ID | IMDR code | Description |
|---|---|---|
| EIUIR | BLS.IMPORT_PRICE.ALL.US | Import Price Index All Commodities |
| EIUIQ | BLS.EXPORT_PRICE.ALL.US | Export Price Index All Commodities |

The export/import ratio (EIUIQ ÷ EIUIR) is computed downstream to close cell 3.1 (the only ❌ in the US wiring map before this build). Both legs are landed here.

## Gotchas

- **Silent empty on bad series IDs.** BLS returns `REQUEST_SUCCEEDED` with an empty `data[]` array for a bad or retired series ID — it does not 400 or surface an error. All fetchers print a `WARN {sid}: 0 rows` line to catch this; validate IDs with `validate_series.py` before adding.
- **Period M13 / Q05 are annual averages.** `bls_period_to_date()` returns `None` for these; the fetchers skip them.
- **20-year window cap.** `BlsClient.fetch_series()` automatically chunks the year range into ≤20-year spans. Pulling from 1990 → today requires 2 API calls per series batch.
- **Import/export price indexes are NSA.** BLS does not publish SA versions of EIUIR/EIUIQ — both carry `is_seasonally_adjusted=False`.

## Canonical loader

```bash
python -m playground.econ.us.bls.fetch_cpi
python -m playground.econ.us.bls.fetch_ppi
python -m playground.econ.us.bls.fetch_employment_situation
python -m playground.econ.us.bls.fetch_eci_jolts
python -m playground.econ.us.bls.fetch_import_export_prices
# After vendor registration (migration 105):
python -m scripts.migrations.load_econ_indicator_from_playground --vendor bls
```

## Related

- [us_coverage_plan.md](../us_coverage_plan.md) — cells + build order
- [united_states_indicator_inventory.md](../united_states_indicator_inventory.md) — playground fetcher inventory
