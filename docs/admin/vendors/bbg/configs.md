# BBG Feed — Config Files

All ticker universes are defined in Excel files (`openxlsx::read.xlsx` on the R side). Each file has its own schema. Understanding these schemas is the first step to any IMDR integration.

## `FX/FX data file.xlsx`

**Shape**: 30 rows × up to 60 columns.

**Schema**:
| Col 0 | Col 1 | Cols 2..59 |
|---|---|---|
| `Type` | `Ccy` | `Tickers` | `Unnamed: 3` | `Unnamed: 4` ... |

`Type` is always `FX` for this file.
`Ccy` is either a single-currency code or a special aggregate.

### Row-by-row inventory (30 rows)

| Row | Ccy | Ticker count | Example first ticker | Notes |
|---:|---|---:|---|---|
| 0 | `MS` | 58 | `AUD CURNCY`, `AUD1M CURNCY`, ... | Asia SPOT+1M aggregate; not written to per-ccy folders |
| 1 | `MSVOL` | 18 | `AUDUSDV1M CURNCY` | Asia 1M ATM vol aggregate |
| 2 | `AUD` | 8 | `AUD CURNCY`, `AUD1W CURNCY`, ... | G10, fwd-points |
| 3 | `CNH` | 8 | `CNH CURNCY`, `CNH+1W CURNCY`, ... | Offshore CNH |
| 4 | `EUR` | 8 | `EUR CURNCY`, `EUR1W CURNCY`, ... | |
| 5 | `GBP` | 8 | `GBP CURNCY`, `GBP1W CURNCY`, ... | |
| 6 | `CHF` | 8 | `CHF CURNCY`, `CHF1W CURNCY`, ... | |
| 7 | `NOK` | 8 | `NOK CURNCY`, `NOK1W CURNCY`, ... | |
| 8 | `SEK` | 8 | `SEK CURNCY`, `SEK1W CURNCY`, ... | |
| 9 | `HKD` | 7 | `HKD CURNCY`, `HKD+1M FMD CURNCY`, ... | `FMD` = outright; no SPOT-adjust conversion |
| 10 | `IDR` | 8 | `IDR BSYN CURNCY`, `IHN+1W CURNCY`, ... | NDF; IHN+ tickers already outright |
| 11 | `INR` | 8 | `INR BSYN CURNCY`, `IRN+1W CURNCY`, ... | NDF |
| 12 | `JPY` | 8 | `JPY CURNCY`, `JPY1W CURNCY`, ... | Fwd-points divided by 100 (2-dp pair) |
| 13 | `KRW` | 8 | `KRW BSYN CURNCY`, `KWN+1W CURNCY`, ... | NDF |
| 14 | `NZD` | 8 | `NZD CURNCY`, `NZD1W CURNCY`, ... | G10, fwd-points |
| 15 | `PHP` | 8 | `PHP BSYN CURNCY`, `PPN+1W CURNCY`, ... | NDF |
| 16 | `SGD` | 14 | `SGD CURNCY`, `SGD1W CURNCY`, ... | Deep tenor grid |
| 17 | `THB` | 8 | `THB CURNCY`, `THB1W CURNCY`, ... | Fwd-points divided by 100 (2-dp pair) |
| 18 | `TWD` | 8 | `TWD CURNCY`, `NTN+1W CURNCY`, ... | NDF |
| 19 | `MYR` | 8 | `MYR CURNCY`, `MRN+1W CURNCY`, ... | NDF onshore |
| 20 | `CNY` | 8 | `CNY CURNCY`, `CCN+1W BGN CURNCY`, ... | Deliverable CNY |
| 21 | `CAD` | 14 | `CAD CURNCY`, `CAD1W CURNCY`, ... | Deep tenor grid |
| 22 | `PLN` | 13 | `PLN CURNCY`, `PLN1W CURNCY`, ... | |
| 23 | `XAU` | 6 | `XAU CURNCY`, `XAUSR1M BGN CURNCY`, ... | Gold; thin tenor grid |
| 24 | `XAG` | 5 | `XAG CURNCY`, `XAGSR1M BGN CURNCY`, ... | Silver; thinnest grid |
| 25 | `CNO` | 8 | `CNY CURNCY`, `CCO+1W CURNCY`, ... | Onshore CNY (uses offshore spot ticker!) |
| 26 | `MXN` | 8 | `MXN CURNCY`, `MXN1W BGN Curncy`, ... | Mixed case in tickers |
| 27 | `IDO` | 7 | `IDR BSYN CURNCY`, `IHO1W CURNCY`, ... | Onshore IDR |
| 28 | `ILS` | 9 | `ILS CURNCY`, `ILS1W CURNCY`, ... | |
| 29 | `MYO` | 6 | `MYR CURNCY`, `MRO+1M CURNCY`, ... | Onshore MYR |

**Total unique tickers** across 30 rows: ~200 (after deduplication).

## `refresh_R_bbg.xlsx`

**Shape**: 52 rows × 39 columns.

**Schema**:
| Col 0 | Col 1 | Col 2 | Col 3 | Cols 4..38 |
|---|---|---|---|---|
| `Type` | `Ccy` | `spotorfwd` | `cleaning` | `Tickers` ... |

### Type distribution

| Type | # rows | Example Ccy values |
|---|---:|---|
| `IRS` | 19 | `USD-LIBOR-3M`, `EUR-EURIBOR-6M`, `HKD-HIBOR-3M`, `KRW-91D_CD-3M`, `TWD-TAIBOR-3M`, `CNY-REPO-7D`, `CNY-SHIBOR-3M`, `MYR-KLIBOR-3M`, `MYO-KLIBOR-3M` |
| `OIS` | 14 | `USD-FEDFUNDS-ON`, `USD-SOFR-ON`, `EUR-ESTR-ON`, `GBP-SONIA-ON`, `JPY-TONAR-ON-JSCC`, `NZD-NZOCRS-ON`, `SGD-SOR-ON`, `CHF-SARON-ON`, `CAD-CORRA-ON`, `AUD-AONIA-ON`, `THO-THOR-ON`, `THB-THOR-ON`, `INR-MIBOR-ON`, `ILS-SHIR-ON` |
| `BASIS` | 12 | `AUD-BBSW-6M.AUD-BBSW-3M`, `AUD-BBSW-1M.AUD-BBSW-3M`, `AUD-BBSW-3M.AUD-AONIA-ON`, `AUD-BBSW-3M.USD-SOFR-ON`, `USD-SOFR-ON.USD-FEDFUNDS-ON`, `USD-LIBOR-3M.USD-SOFR-ON`, `EUR-ESTR-ON.USD-SOFR-ON`, `EUR-EURIBOR-3M.USD-LIBOR-3M`, `SGD-SOR-ON.USD-SOFR-ON`, `JPY-TONAR-ON.USD-SOFR-ON`, `KRW-91D_CD-3M.USD-SOFR-ON`, `ILS-SHIR-ON.USD-SOFR-ON`, `HKD-HIBOR-3M.USD-SOFR-ON`, `AUD-AONIA-ON.USD-SOFR-ON`, `LCH.JSCC` |
| `CCS` | 5 | `CNH-FIXED.USD-SOFR-ON`, `INR-FIXED.USD-SOFR-ON`, `KRW-FIXED.USD-SOFR-ON`, `PHP-FIXED.USD-SOFR-ON`, `THB-FIXED.USD-SOFR-ON`, `TWD-FIXED.USD-SOFR-ON`, `MYR` |
| `Commodities` | 1 | `MS` (aggregate row) |
| `Vol` | 1 | `MS` (aggregate row) |

### `spotorfwd` column

All 52 rows currently have `PAR`. The column exists because the CSV output path is `{Type}\{Ccy}\{spotorfwd}\{Type}_{spotorfwd}_{Ccy}.csv`, and in principle `FWD` curves could be added.

### `cleaning` column

`Y | N` flag. When `Y`, the script would call a function named `clean.{iden}` (where `iden = {Type}_{spotorfwd}_{Ccy}`) — e.g., `clean.IRS_PAR_CNY` — to apply post-processing. **All cleaning functions are commented out** in current code. The one preserved example (commented) interpolates `CCSWNI6` as the mean of `CCSWNI5` and `CCSWNI7`.

## `Credit/Credit.xlsx`

**Schema**: `Type | Ccy | Other | Tickers...`

- `Type` — `Credit`
- `Ccy` — the CDS series or index name (e.g., `CDS_ASIA_IG`, `CDX5y`, `CDS_EUROPE`)
- `Other` — sub-identifier (e.g., tenor or currency qualifier)

Output path: `Credit/{Ccy}/{Other}/{Ccy}_{Other}.csv`.

Series inventory:
- `CDS_ASIA_IG`, `CDS_CHINA`, `CDS_EUROPE`, `CDS_INDO`, `CDS_KOREA`, `CDS_MALAY`, `CDX5y`

## `BONDS/Bonds data file.xlsx`

**Schema**: `Type | Ccy | Other | Tickers...`

- `Type` — `BONDS` (I think)
- `Ccy` — `AUD`, `CNY`, `IDR`, `INR`, `JPY`, `KRW`, `MYR`, `SGD`, `THB`, `USD`
- `Other` — bond series identifier (e.g., `LINKER`)

**Two fields fetched** (unique to bonds): `px_last` + `yld_ytm_mid`.

## `FUTURES/*.xlsx` (multiple)

Futures has its own directory of config files:
- `Futures Data File.xlsx` — main futures universe
- `BBG futures roll adjustments.xls` — roll adjustment config
- `CTD futs.xlsx` — cheapest-to-deliver
- `ED_FF_IR_KE_KAA_SFR_Xm_YM file.xlsx` — monthly Eurodollar / FF / IR / KE / KAA / SFR / XM1 / YM1 codes
- `rolled futs.xlsx` — roll-adjusted futures
- `spot_Xm_YM file.xlsx` — spot XM1/YM1 pricing
- `XCTK.xlsm` — crude futures extras

Futures ticker codes: `BC, CL, CO, ED, ER, ES, FF, FV, GC, HC, HG, HI, HJA, HU, IH, INB, INO, INT, IR, JB, KAA, KE, KM, NK, NQ, PA, PL, QZ, RX, SFR, SI, TU, TY, UB, US, UX, UXY, WN, XCTK, XM, XU, XUC, YM`.

## `Vol/_inputs/ccypairsForPnL.csv`

A flat list of currency pairs for which vol surfaces are refreshed. Drives the `runVol()` call in `Vol/vol.R`. Pair codes like `AUDUSD`, `EURGBP`, `CNHJPY`, `XAUUSD`. 94 pair folders exist under `Vol/` (some are legacy and may not be in the CSV).

## `FIXINGS/...`

**No Excel config** — the ticker→series mapping is a hardcoded R named-vector `bbgIndexMap` inside [`FIXINGS/IrFixings.R`](../../../../../../Business/Research/Dashboard/DataSources/BBG/FIXINGS/IrFixings.R). Approximately 40 fixings mapped, covering: USD-CPURNSA, THB-THOR-ON, CAD-CORRA-ON, CHF-SARON-ON, NOK-NOWA-ON, PLN-NBP-ON, SEK-STIBOR-ON, GBP-SONIA-ON, EUR-ESTR-ON, USD-SOFR-ON, USD-FEDFUNDS-ON, USD-LIBOR-3M, USD-LIBOR-6M, CAD-CDOR-3M, CHF-LIBOR-6M, NIBOR-3M/6M, WIBR-3M/6M, EUR-EURIBOR-3M/6M, NZD-NZOCRS/BKBM, AUD-AONIA/BBSW-1M/3M/6M, JPY-TONAR/LIBOR/DTIBOR, CNY-SHIBOR/REPO, HKD-HIBOR-1M/3M, KRW-91D_CD-3M, INR-MIBOR-ON, MYR-KLIBOR-3M, SGD-SOR-ON/3M/6M, THB-THBFIX-6M, TWD-TAIBOR-3M, ILS-SHIR-ON.

## Listed / `Listed/Input/`

Listed positions are sourced from `Listed/Input/*` files copied in daily by `CopyListedInput.R` (see [scheduling_and_health.md](scheduling_and_health.md)). The actual refresh logic is in [listedFct.R](../../../../../../Business/Research/Dashboard/DataSources/BBG/Listed/listedFct.R) which we haven't deep-dived — not priority for IMDR.

## Suggested IMDR universe ingestion

When we seed IMDR dim tables from these configs, parse:

1. `FX data file.xlsx` → 28 FX pairs (skip `MS` and `MSVOL` aggregates) → `dim_currency_pair` entries + tenor mappings. Respect onshore/offshore distinction (`CNO`/`CNH`/`CNY`, `MYO`/`MYR`, `IDO`/`IDR`, `THO`/`THB`, `INF`/`INR`, `CNF`/`CNO`).
2. `refresh_R_bbg.xlsx` → 52 rates-side series (skip `MS`) → tenor basis, cross-currency basis, IRS curves, OIS benchmarks.
3. `Credit/Credit.xlsx` → CDS series (not currently in IMDR).
4. `BONDS/Bonds data file.xlsx` → individual bond tickers (not currently in IMDR).

Skip `FUTURES/*` and `Vol/` on first pass; scope them separately if needed.
