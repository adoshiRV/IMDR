# Census — `playground/econ/us/census/`

**Status:** Discovery built (playground). Dry-run clean. Vendor row (`CENSUS`) pending migration 105 — not yet loaded into `econ.fact_indicator`. No `scripts/econ/us/` entry. Not wired into any orchestrator.

US Census Bureau EITS (Economic Indicator Time Series) API and intltrade sub-endpoints. GET `https://api.census.gov/data/timeseries/eits/{program}`, key `IMDR_ECON_CENSUS_KEY`. Response is a **2-D array** (row 0 = header, rows 1..N = data) — the connector zips header + rows into list-of-dicts.

## Contents

| File | Purpose |
|---|---|
| `connector.py` | `CensusClient` — GET wrapper for EITS (`get_eits`) and intltrade (`get_intltrade`). Builds query string manually to preserve `+` in `time=from+YYYY` (standard `urlencode` turns `+` into `%2B` which breaks the range operator). |
| `fetch_retail.py` | 3 MARTS retail sales series — total SA, total NSA, ex-auto SA. Cell 1.1. |
| `fetch_trade.py` | 3 intltrade series — goods exports, imports, derived balance. Cell 1.3. |
| `fetch_housing.py` | 4 New Residential Construction series — starts/permits × total/single-family. Cell 1.1 (housing leg). |

## Series breakdown

### `fetch_retail` — 3 series (program `marts`, unit `usd_mn`, monthly)

| category_code | SA | IMDR code | category |
|---|:---:|---|---|
| 44000 (Total Retail & Food Services) | yes | CENSUS.RETAIL.TOTAL_SA.US | other |
| 44000 | no | CENSUS.RETAIL.TOTAL_NSA.US | other |
| 44X72 (Ex-Motor Vehicles & Parts) | yes | CENSUS.RETAIL.EX_AUTO_SA.US | other |

`data_type_code=SM` (Sales, $mn). The API returns a `error_data` column; rows where `error_data=yes` are standard-error rows — the fetcher skips them.

### `fetch_trade` — 3 series (program `intltrade`, unit `usd_mn`, monthly)

| IMDR code | Source | category |
|---|---|---|
| CENSUS.TRADE.EXPORTS_GOODS.US | intltrade/exports/enduse, E_ENDUSE='-', CTY_NAME='TOTAL FOR ALL COUNTRIES' | bop |
| CENSUS.TRADE.IMPORTS_GOODS.US | intltrade/imports/enduse, I_ENDUSE='-', CTY_NAME='TOTAL FOR ALL COUNTRIES' | bop |
| CENSUS.TRADE.BALANCE_GOODS.US | derived: exports − imports | bop |

The intltrade API has no FT-900 summary endpoint. The `E_ENDUSE='-'` / `I_ENDUSE='-'` filter selects the "total all end-uses" aggregate; `CTY_NAME='TOTAL FOR ALL COUNTRIES'` selects the world total. API values are in actual USD — the fetcher converts to $mn (`× 1e-6`). The balance series is derived in-code (not fetched from the API).

### `fetch_housing` — 4 series (program `resconst`, unit `units_th`, monthly, SA)

| category_code | data_type_code | IMDR code | category |
|---|---|---|---|
| ASTARTS | TOTAL | CENSUS.HOUSING.STARTS_TOTAL_SA.US | housing |
| ASTARTS | SINGLE | CENSUS.HOUSING.STARTS_SF_SA.US | housing |
| APERMITS | TOTAL | CENSUS.HOUSING.PERMITS_TOTAL_SA.US | housing |
| APERMITS | SINGLE | CENSUS.HOUSING.PERMITS_SF_SA.US | housing |

Values are SAAR (thousands of units). The API does not accept `geo_level_code` as a filter parameter — the fetcher downloads all geographic rows and filters to `geo_level_code='US'` post-download.

## Gotchas

- **`time=from+YYYY` uses a literal `+` as a range operator.** Standard URL encoding converts `+` to `%2B`, which breaks the Census range syntax and returns a 400 or empty result. The connector builds the query string manually via `urllib.parse.urlencode` with a custom `quote_via` that preserves `+`.
- **`error_data=yes` rows in EITS are standard-error rows, not data rows.** The MARTS fetcher skips them. Not present in resconst responses but the flag is checked defensively.
- **`geo_level_code` is not a filter parameter in resconst.** The full national + regional dataset is downloaded; filtering to `US` happens in Python.
- **intltrade values are in raw USD (not $mn).** The `fetch_trade` fetcher applies `× 1e-6` to convert to `usd_mn` before storing.

## Canonical loader

```bash
python -m playground.econ.us.census.fetch_retail
python -m playground.econ.us.census.fetch_trade
python -m playground.econ.us.census.fetch_housing
# After vendor registration (migration 105):
python -m scripts.migrations.load_econ_indicator_from_playground --vendor census
```

## Related

- [us_coverage_plan.md](../us_coverage_plan.md) — cells + build order
- [united_states_indicator_inventory.md](../united_states_indicator_inventory.md) — playground fetcher inventory
