# BBG Feed — Rates Pipeline (IRS / OIS / BASIS / CCS)

Script: [`pull data from bbg.R`](../../../../../../Business/Research/Dashboard/DataSources/BBG/pull%20data%20from%20bbg.R).
Config: [`refresh_R_bbg.xlsx`](../../../../../../Business/Research/Dashboard/DataSources/BBG/refresh_R_bbg.xlsx).
Raw cache: `IRS/_Raw/irs.rda`.
Outputs: `{Type}/{Ccy}/{spotorfwd}/{Type}_{spotorfwd}_{Ccy}.csv` — e.g. `IRS/USD-LIBOR-3M/PAR/IRS_PAR_USD-LIBOR-3M.csv`.

## Why one script for four types?

Bloomberg treats tenor basis, cross-currency basis, swap curves, and OIS curves as simple ticker pulls — there's nothing structurally different, just the ticker prefix. So a single `bdh()` fetch with a Union of all 52 rows' tickers is the simplest approach. The `Type` column is just a folder-name discriminator.

## End-to-end flow (same shape as FX pipeline)

1. Read `refresh_R_bbg.xlsx` — 52 rows, schema `Type | Ccy | spotorfwd | cleaning | Tickers...`.
2. Build `tickersAll = unique(union)` across all rows.
3. `bdh(tickersAll, "px_last", Sys.Date()-100, Sys.Date(), options=...)` — 100-day lookback (not 90 like FX).
4. Save to `IRS/_Raw/irs.rda` (even though the file contains IRS + OIS + BASIS + CCS — name is historical).
5. For each row, slice + merge + na.locf → write to `{Type}/{Ccy}/{spotorfwd}/{Type}_{spotorfwd}_{Ccy}.csv`.

## `Type = IRS` (19 rows)

Standard IBOR-style swap curves.

| Row # | Ccy | First ticker | Notes |
|---|---|---|---|
| 1 | `CNY-REPO-7D` | `CNRR007 Index` | Chinese repo fixing |
| 2 | `HKD-HIBOR-3M` | `HIHD03M Index` | |
| 3 | `KRW-91D_CD-3M` | `KWCDC Curncy` | Korean 91-day CD benchmark |
| 4 | `NZD-BKBM-3M` | `NDBB3M Curncy` | NZ Bank Bill Mid |
| 5 | `CNY-SHIBOR-3M` | `SHIF3M INDEX` | |
| 6 | `MYR-KLIBOR-3M` | `KLIB3M INDEX` | |
| 7 | `AUD-BBSW-3M` | `BBSW 3M INDEX` | |
| 8 | `AUD-BBSW-6M` | `SD0302P 6M BLC3 Curncy` | |
| 12 | `EUR-EURIBOR-6M` | `EUR006M Index` | |
| 14 | `MYO-KLIBOR-3M` | `KLIB3M Index` | Onshore MYR (same ticker as MYR? ambiguous) |
| 15 | `TWD-TAIBOR-3M` | `TAIBOR3M index` | |
| 17 | `EUR-EURIBOR-3M` | `EUR003M Index` | |
| 18 | `SEK-STIBOR-3M` | `SKSW1 CMPN Curncy` | |
| 19 | `PLN-WIBOR-6M` | `WIBR3M Index` | |
| 20 | `KRO-91D_CD-3M` | `KWCDC Curncy` | Onshore KRW variant — same ticker as KRW? |
| 23 | `NOK-NIBOR-6M` | `NIBOR3M Index` | |
| 24 | `MS` | `CCSWNI5 CMPN CURNCY` | Aggregate — not per-ccy |

> ⚠️ `MYR-KLIBOR-3M` and `MYO-KLIBOR-3M` both use `KLIB3M Index` — onshore/offshore MYR fixings are the same Bloomberg series in this config. Check with the research team whether that's intentional or a config error.
>
> Same for `KRW-91D_CD-3M` and `KRO-91D_CD-3M` both using `KWCDC Curncy`.

## `Type = OIS` (14 rows)

Overnight-index swap curves.

| Ccy | First ticker |
|---|---|
| `INR-MIBOR-ON` | `IN00O/N Index` |
| `SGD-SOR-ON` | `SIBCSORA Index` |
| `JPY-TONAR-ON-JSCC` | `MUTKCALM Index` (JSCC-cleared variant) |
| `NZD-NZOCRS-ON` | `NZOCRS Index` |
| `USD-FEDFUNDS-ON` | `FEDL01 Index` |
| `EUR-ESTR-ON` | `ESTRON Index` |
| `USD-SOFR-ON` | — (see config) |
| `CHF-SARON-ON` | — |
| `CAD-CORRA-ON` | — |
| `GBP-SONIA-ON` | — |
| `AUD-AONIA-ON` | — |
| `THO-THOR-ON` | — (onshore THB) |
| `THB-THOR-ON` | — |
| `ILS-SHIR-ON` | — |

## `Type = BASIS` (12 rows)

Tenor-basis and cross-currency basis quotes. The `Ccy` is a compound `{leg1}.{leg2}` label.

| Ccy | First ticker | What it is |
|---|---|---|
| `AUD-BBSW-6M.AUD-BBSW-3M` | `ADBBCFF BGN Curncy` | AUD 6s3s basis |
| `AUD-BBSW-1M.AUD-BBSW-3M` | `ADBBCAC TPRA Curncy` | AUD 1s3s |
| `AUD-BBSW-3M.AUD-AONIA-ON` | `ADBBCO1 CMPN Curncy` | AUD BBSW vs AONIA |
| `AUD-BBSW-3M.USD-SOFR-ON` | — | AUD-USD cross-ccy basis |
| `USD-SOFR-ON.USD-FEDFUNDS-ON` | `USSFVFC BGN Curncy` | SOFR vs FF |
| `USD-LIBOR-3M.USD-SOFR-ON` | — | LIBOR vs SOFR |
| `EUR-ESTR-ON.USD-SOFR-ON` | — | EUR-USD |
| `EUR-EURIBOR-3M.USD-LIBOR-3M` | — | EUR vs USD 3M |
| `SGD-SOR-ON.USD-SOFR-ON` | `SDSF66M Curncy` | SGD-USD |
| `JPY-TONAR-ON.USD-SOFR-ON` | — | JPY-USD |
| `KRW-91D_CD-3M.USD-SOFR-ON` | — | KRW-USD |
| `ILS-SHIR-ON.USD-SOFR-ON` | — | |
| `HKD-HIBOR-3M.USD-SOFR-ON` | — | |
| `AUD-AONIA-ON.USD-SOFR-ON` | — | |
| `LCH.JSCC` | — | LCH/JSCC clearing basis (JPY) |

## `Type = CCS` (5–7 rows)

Cross-currency swap fixed vs SOFR.

| Ccy | Meaning |
|---|---|
| `CNH-FIXED.USD-SOFR-ON` | CNH CCS |
| `INR-FIXED.USD-SOFR-ON` | INR CCS |
| `KRW-FIXED.USD-SOFR-ON` | KRW CCS |
| `PHP-FIXED.USD-SOFR-ON` | PHP CCS |
| `THB-FIXED.USD-SOFR-ON` | THB CCS |
| `TWD-FIXED.USD-SOFR-ON` | TWD CCS |
| `MYR` | MYR CCS (different ccy code) |

## `Type = Commodities | Vol` (aggregate rows)

One row each, both with `Ccy = MS`. Not written to per-ccy folders — they feed downstream dashboards via the shared `tickersAll` fetch.

## Output CSV shape (example)

`IRS/USD-LIBOR-3M/PAR/IRS_PAR_USD-LIBOR-3M.csv`:

```
Ticker,US0003M Index,USSW1 CMPN Curncy,USSW2 CMPN Curncy,USSW3 CMPN Curncy,...
Tenor,IRS_USD-LIBOR-3M_FIXING,IRS_USD-LIBOR-3M_1Y,IRS_USD-LIBOR-3M_2Y,IRS_USD-LIBOR-3M_3Y,...
Maturity,0,1,2,3,...
22/04/2026,5.31,4.55,4.12,3.98,...
...
```

**No spot+points→outright conversion** (that's FX-only). IRS rates are already rates (in %).

## Output CSV shape — BASIS example

`BASIS/USD-SOFR-ON.USD-FEDFUNDS-ON/PAR/BASIS_PAR_USD-SOFR-ON.USD-FEDFUNDS-ON.csv`:

Spread expressed in basis points, one row per business day.

## Notable missing rows to cross-check

From the `log/BBGLog.log2026-04-22` "Issue in-" lines, we can see what the freshness check expects. Counting unique paths reveals the checker iterates 52 rows (matching the config). But note the log also shows:
- `CCS/MYR/PAR/CCS_PAR_MYR.csv` — no such ticker row # visible in the snippet I read, possibly out-of-scope or row 30+ of config.
- Special: `BASIS/LCH.JSCC/PAR/BASIS_PAR_LCH.JSCC.csv` — a single-token ccy name with a dot.

## Post-processing / cleaning

The `cleaning` column allows per-row custom post-processing via `clean.{Type}_{spotorfwd}_{Ccy}()` functions. **All currently disabled** (commented out). One example retained in the source as documentation:

```r
clean.IRS_PAR_CNY = function(mergeddata) {
    mergeddata[,"CCSWNI6 CMPN CURNCY"] = (mergeddata[,"CCSWNI5 CMPN CURNCY"] +
                                           mergeddata[,"CCSWNI7 CMPN CURNCY"]) / 2
    return(mergeddata)
}
```

Linear interpolation of a missing tenor from its neighbours. Disabled because the underlying ticker is now available directly.

## Where the heavy lifting happens

Looking at the script carefully, the actual logic is in a legacy `run_v0()` function and a newer `run()` function — **the newer `run()` was inferred from the FX script pattern and may not have been updated for rates recently**. The rates script has more legacy debug blocks and commented-out sections than the FX one. When porting to IMDR, trust the behaviour observed in the CSVs over the R source code.
