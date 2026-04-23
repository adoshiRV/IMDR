# BBG Feed — Data Formats

Three storage layers:

1. **Per-series CSVs** — the consumer-facing outputs.
2. **`_Raw/*.rda`** — per-domain raw Bloomberg blobs (one file per domain, overwritten each run).
3. **`BBG_ASIA/{YYYY-MM-DD}/...`** — date-stamped snapshot tree for the Asia cutoff.

## CSV format

Every per-series CSV has a **3-row header**, then data rows in reverse-chronological order. Example (`FX/JPY/FX_JPY.csv`):

| row | col 1 | col 2 | col 3 | col 4 | ... |
|---|---|---|---|---|---|
| 0 | `Ticker` | `JPY curncy` | `JPY1W curncy` | `JPY1M curncy` | ... |
| 1 | `Tenor` | `FX_JPY_SPOT` | `FX_JPY_1W` | `FX_JPY_1M` | ... |
| 2 | `Maturity` | `0` | `0.020833333` | `0.083333333` | ... |
| 3 | `23/04/2026` | 159.55 | 159.4146 | 159.1444 | ... |
| 4 | `22/04/2026` | 159.48 | 159.3863 | 159.0474 | ... |
| ... (one row per business day, latest first) | | | | | |

**Column semantics**:

| Header row | Meaning |
|---|---|
| 0 — `Ticker` | Literal Bloomberg ticker (mixed case: `CURNCY`, `Curncy`, `curncy`, `Index`, `INDEX`, `index` all appear) |
| 1 — `Tenor` | RV internal tenor alias, `{Type}_{Ccy}_{Tenor}` |
| 2 — `Maturity` | Years fraction (for SPOT = 0, 1W ≈ 0.0208, 1M ≈ 0.0833, 3M = 0.25, 1Y = 1, 2Y = 2) |

**Date column**: `dd/mm/yyyy` as a string in column 0 of rows 3+.

### Things to know before parsing

- The separator is `,` but **no quoting** is applied on write (`quote=F` in R), so a ticker containing a comma would break the parser. None observed in current configs.
- Numeric columns are plain R prints — they may come out as integer (`0`, `1`, `2`) or long-form floats (`0.020833333`) — parse as float unconditionally.
- Encoding is default locale (Windows-1252 typically). No BOM.
- **Line endings** are Windows (`\r\n`).
- Row counts per file range from **315** (HKD — 7 tenors) to **1,899** (CNO — 9 tenors) for FX. Sizes vary by how long each pair has been tracked.

### Missing ticker = column missing

If the config adds a new ticker after the CSV already exists, it may show up as a new column with NAs back-filled. When a ticker is removed, the column persists in history but stops updating. The R script uses `na.locf` so the last known value propagates.

## `.rda` raw caches

Each refresher saves the full Bloomberg response before splitting into CSVs:

| File | Written by | Contents |
|---|---|---|
| `FX/_Raw/fx.rda` | `FX/bbg_refresh.R` | `bbg_fx_list`: named list-of-xts, keyed by Bloomberg ticker, each `xts` has `date | px_last` columns |
| `IRS/_Raw/irs.rda` | `pull data from bbg.R` | `temp_data` / `bbg_ir_list` — same shape |
| `Credit/_Raw/credit.rda` | `Credit/bbg_refresh_credit.R` | same |
| `BONDS/_Raw/bond.rda` | `BONDS/bbg_refresh_bonds.R` | same, with **2 fields**: `px_last` + `yld_ytm_mid` |
| `Vol/_Raw/fxVols.rda` | `Vol/volFct.R` | FX vol chain |
| `Vol/_Raw/fxVols.EURUSD.rda` | `Vol/volFct.R` | Per-pair override for EURUSD specifically |
| `Vol/_Raw/flag.Rda` | `Vol/vol.R` | Vol pipeline's independent concurrency lock (separate from the main `flag.Rda`) |
| `FUTURES/_Raw/*.rda` | various futures scripts | |

**Overwrite policy**: every run blows away the previous `.rda`. No history of raw data is retained. If you want audit / replay, you need to snapshot these yourself.

**Lookback on raw fetch**:
- FX: `Sys.Date() - 90` to `Sys.Date()` (90 days)
- IRS / OIS / BASIS / CCS: `Sys.Date() - 100` to `Sys.Date()` (100 days)
- Credit: `Sys.Date() - 1000` to `Sys.Date()` (~2.7 years)
- Commodities: `Sys.Date() - 10` to `Sys.Date()` (10 days)

### Loading `.rda` from Python

```python
import pyreadr
result = pyreadr.read_r(r"Z:\Business\Research\Dashboard\DataSources\BBG\FX\_Raw\fx.rda")
# result is an OrderedDict: {ticker_name: DataFrame(columns=['date', 'ticker_name'])}
```

`pyreadr` is in the `imdr` conda env (we use it for other vendor integrations — verify before assuming).

Alternatively, via R subprocess:

```r
load("Z:/.../_Raw/fx.rda")
# creates a global `bbg_fx_list` in the session
```

## `BBG_ASIA/{YYYY-MM-DD}/...` tree

Created by [RatesFxAsia.R](../../../../../../Business/Research/Dashboard/DataSources/BBG/RatesFxAsia.R), invoked from `master.R` during the `16:30–17:55 SGT` window.

**Structure**:
```
BBG_ASIA/
  2026-04-22/
    FX/
      AUD/
        FX_AUD.csv        ← first 4 rows of live FX/AUD/FX_AUD.csv
      EUR/
        FX_EUR.csv
      ... (one folder per FX ccy)
    IRS/
      EUR-EURIBOR-3M/
        PAR/
          IRS_PAR_EUR-EURIBOR-3M.csv
      ...
    OIS/
    BASIS/
    CCS/
    Credit/
      CDS_ASIA_IG/
        ...
      ...
```

**Contents**: each ASIA CSV contains exactly the first 4 lines of the live CSV — the 3 header rows + today's data row — but only if today's date matches. If the live CSV's latest row is stale, it's skipped with a console `print()` (not an error).

Available snapshots:
```
2026-04-09, 2026-04-10, 2026-04-13, 2026-04-14, 2026-04-15, 2026-04-16,
2026-04-17, 2026-04-20, 2026-04-21, 2026-04-22
```
(i.e. business days only; no weekend directories.)

## FX ticker conventions (seen in `FX data file.xlsx`)

| Category | Ccy codes | Ticker style | Notes |
|---|---|---|---|
| Deliverable G10 | AUD, EUR, GBP, JPY, NZD, SEK, NOK, CHF, CAD, PLN, ILS | `XXX{tenor} CURNCY` (e.g. `AUD1M CURNCY`) | Forward **points**; need conversion to outright |
| Metals | XAU, XAG | `XAU{tenor} BGN CURNCY` / `XAUSR{tenor} BGN CURNCY` | Bloomberg Generic; `SR` = spot-ref |
| HKD deliverable | HKD | `HKD+{tenor} FMD CURNCY` | `FMD` = outright forward (no conversion) |
| NDF pairs — IDR | IDR | `IHN+{tenor} CURNCY` (and `IDR BSYN CURNCY` for spot) | NDF; already outright |
| NDF pairs — INR | INR | `IRN+{tenor} CURNCY` (and `INR BSYN CURNCY`) | NDF; already outright |
| NDF pairs — KRW | KRW | `KWN+{tenor} CURNCY` (and `KRW BSYN CURNCY`) | NDF; already outright |
| NDF pairs — PHP | PHP | `PPN+{tenor} CURNCY` (and `PHP BSYN CURNCY`) | NDF; already outright |
| NDF pairs — TWD | TWD | `NTN+{tenor} CURNCY` | NDF; already outright |
| CNY variants | CNY (deliverable) | `CCN+{tenor}` for forwards | |
| | CNH (offshore) | `CNH+{tenor} CURNCY` | |
| | CNO (onshore) | `CCO+{tenor} CURNCY` | |
| Onshore EM variants | MYO, IDO, INF, CNF, THO | custom `MRO+`, `IHO`, `INF`, `CNF`, `THO` | Onshore equivalents; mapped in the probe script via `{onshore: offshore}` dict |
| MXN | MXN | Mix of plain and `BGN Curncy` | |
| Aggregates | `MS` | 58 tickers across Asia spot + 1M | Special `MS` row in config; not written to per-ccy folders |
| Aggregates | `MSVOL` | 18 ATM 1M vol tickers | Special `MSVOL` row; not written to per-ccy folders |

See [fx_pipeline.md](fx_pipeline.md) for ticker-to-output-column semantics and the FxSwap→FxFwd transformation.

## IRS ticker conventions (seen in `refresh_R_bbg.xlsx`)

Types: `IRS | OIS | BASIS | CCS | Commodities | Vol`

Within each type, `Ccy` is either:
- A single-currency code (`AUD`, `EUR`, `USD`) — straight IRS/OIS curve
- A compound code like `AUD-BBSW-6M.AUD-BBSW-3M` — **basis spread** between two tenors/indices
- A compound code like `SGD-SOR-ON.USD-SOFR-ON` — **cross-currency basis**
- Special aggregates: `MS` (used by dashboards, not per-ccy folders)

Spot columns:
- `Type` — `IRS | OIS | BASIS | CCS | Commodities | Vol`
- `Ccy` — curve identifier (composite for basis)
- `spotorfwd` — `PAR` (always, in current config)
- `cleaning` — `Y | N` flag for post-processing (only used when a `clean.{iden}` function is defined; currently all commented-out)
- `Tickers` through `Unnamed: N` — up to 35 ticker columns (NA if unused)

See [rates_pipeline.md](rates_pipeline.md) for the tenor layout and output semantics.
