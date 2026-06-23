# BEA — `playground/econ/us/bea/`

**Status:** Discovery built (playground). Dry-run clean; BoP identity (CA = goods + services + primary income + secondary income) verified diff=0. Vendor row (`BEA`) pending migration 105 — not yet loaded into `econ.fact_indicator`. No `scripts/econ/us/` entry. Not wired into any orchestrator.

Bureau of Economic Analysis (BEA) JSON API. GET `https://apps.bea.gov/api/data`, key `IMDR_ECON_BEA_KEY`, `method=GetData`. Covers NIPA (GDP/national accounts + personal income), ITA (international transactions), and IIP (international investment position).

## Contents

| File | Purpose |
|---|---|
| `connector.py` | `BeaClient` — GET JSON wrapper; raises on HTTP errors and on BEA application errors (HTTP 200 with `BEAAPI.Results.Error`). `bea_period_to_date()` maps `2025Q1` / `2025M05` / `2025` formats. `parse_data_value()` strips commas and maps `(NA)` / `(D)` to `None`. |
| `fetch_gdp.py` | 13 series from T10101 (% chg SAAR) + T10105 (levels USD bn). Cell 1.4. |
| `fetch_personal_income.py` | 6 series from T20600 (income/DPI/saving-rate) + T20804 (PCE price index). Cells 1.1 + 2.4. |
| `fetch_ita.py` | 9 series from ITA dataset — current account decomp + financial account. Cells 3.2 + 3.3. |
| `fetch_iip.py` | 8 series from IIP dataset — net IIP + assets/liabilities by type (end-of-period stock). Cell 3.3. |

## Series breakdown

### `fetch_gdp` — 13 series (category `gdp`, quarterly, SA)

**T10101** — percent change from preceding period (SAAR), unit `pct_saar`:

| SeriesCode | IMDR code |
|---|---|
| A191RL | BEA.GDP.REAL_PCHG_SAAR.US |
| DPCERL | BEA.GDP.PCE_REAL_PCHG_SAAR.US |
| A006RL | BEA.GDP.GPDI_REAL_PCHG_SAAR.US |
| A020RL | BEA.GDP.EXP_REAL_PCHG_SAAR.US |
| A021RL | BEA.GDP.IMP_REAL_PCHG_SAAR.US |
| A822RL | BEA.GDP.GOVT_REAL_PCHG_SAAR.US |

**T10105** — levels, billions of current dollars, unit `usd_bn`:

| SeriesCode | IMDR code | Note |
|---|---|---|
| A191RC | BEA.GDP.LEVEL_USD_BN.US | |
| DPCERC | BEA.GDP.PCE_LEVEL_USD_BN.US | |
| A006RC | BEA.GDP.GPDI_LEVEL_USD_BN.US | |
| A019RC | BEA.GDP.NETEXP_LEVEL_USD_BN.US | Net exports level |
| B020RC | BEA.GDP.EXP_LEVEL_USD_BN.US | Exports level |
| B021RC | BEA.GDP.IMP_LEVEL_USD_BN.US | Imports level |
| A822RC | BEA.GDP.GOVT_LEVEL_USD_BN.US | |

Note: T10101 has no net-exports % change line (net exports is a residual); exports (A020RL) and imports (A021RL) % change are pulled individually instead. Exports/imports levels use `B020RC`/`B021RC` in T10105, not `A020RC`/`A021RC`.

### `fetch_personal_income` — 6 series (monthly)

**T20600** — levels (category `gdp`, unit `usd_bn` or `pct`):

| SeriesCode | IMDR code | Unit |
|---|---|---|
| A065RC | BEA.INCOME.PI_USD_BN.US | usd_bn |
| A067RC | BEA.INCOME.DPI_USD_BN.US | usd_bn |
| A072RC | BEA.INCOME.SAVING_RATE.US | pct |
| A067RX | BEA.INCOME.REAL_DPI_USD_BN.US | usd_bn (chained 2017 $) |

**T20804** — PCE price index (category `cpi`, unit `index`, 2017=100):

| SeriesCode | IMDR code |
|---|---|
| DPCERG | BEA.CPI.PCE_PRICE_IDX.US |
| DPCCRG | BEA.CPI.PCE_CORE_PRICE_IDX.US |

### `fetch_ita` — 9 series (category `bop`, unit `usd_mn`, quarterly QNSA)

Current account (cell 3.2):

| Indicator | IMDR code |
|---|---|
| BalCurrAcct | BEA.BOP.CA_TOTAL.US |
| BalGds | BEA.BOP.CA_GOODS.US |
| BalGdsServ | BEA.BOP.CA_GOODS_SVCS.US |
| BalServ | BEA.BOP.CA_SERVICES.US |
| BalPrimInc | BEA.BOP.CA_PRIM_INCOME.US |
| BalSecInc | BEA.BOP.CA_SEC_INCOME.US |

Financial account (cell 3.3):

| Indicator | IMDR code |
|---|---|
| NetLendBorrFinAcct | BEA.BOP.FA_NET_LEND_BORR.US |
| FinAssetsExclFinDeriv | BEA.BOP.FA_US_ASSETS.US |
| FinLiabsExclFinDeriv | BEA.BOP.FA_US_LIABS.US |

Identity check in dry-run: `BalCurrAcct ≈ BalGds + BalServ + BalPrimInc + BalSecInc` — diff=0.

### `fetch_iip` — 8 series (category `bop`, unit `usd_mn`, quarterly QNSA, Component=Pos)

| TypeOfInvestment | IMDR code |
|---|---|
| Net | BEA.IIP.NET.US |
| NetExclFinDeriv | BEA.IIP.NET_EXCL_DERIV.US |
| FinAssets | BEA.IIP.TOTAL_ASSETS.US |
| FinLiabs | BEA.IIP.TOTAL_LIABS.US |
| DiInvAssets | BEA.IIP.DI_ASSETS.US |
| DiInvLiabs | BEA.IIP.DI_LIABS.US |
| PfInvAssets | BEA.IIP.PF_ASSETS.US |
| PfInvLiabs | BEA.IIP.PF_LIABS.US |

## Gotchas

- **Errors return HTTP 200.** The connector checks `BEAAPI.Error` (top-level, e.g. bad API key / unknown dataset) and `BEAAPI.Results.Error` (in-results, e.g. bad parameter value). Both raise `RuntimeError`. Do not rely on HTTP status alone.
- **`DataValue` strings carry commas and special codes.** `parse_data_value()` strips commas from large numbers (`"1,234,567"`), and maps `(NA)` (missing) and `(D)` (suppressed/confidential) to `None`.
- **T10101 has no net-exports % change line.** Net exports is a residual in the NIPA identity; BEA does not publish it as a standalone `RL` series in T10101. Exports (`A020RL`) and imports (`A021RL`) are pulled individually.
- **ITA uses `AreaOrCountry=AllCountries` to get the US aggregate.** The ITA dataset is structured with a country dimension; the US total requires the `AllCountries` parameter value, not `UnitedStates`.

## Canonical loader

```bash
python -m playground.econ.us.bea.fetch_gdp
python -m playground.econ.us.bea.fetch_personal_income
python -m playground.econ.us.bea.fetch_ita
python -m playground.econ.us.bea.fetch_iip
# After vendor registration (migration 105):
python -m scripts.migrations.load_econ_indicator_from_playground --vendor bea
```

## Related

- [us_coverage_plan.md](../us_coverage_plan.md) — cells + build order
- [united_states_indicator_inventory.md](../united_states_indicator_inventory.md) — playground fetcher inventory
