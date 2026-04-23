# BBG Feed — FX Pipeline

Script: [`FX/bbg_refresh.R`](../../../../../../Business/Research/Dashboard/DataSources/BBG/FX/bbg_refresh.R).
Config: [`FX/FX data file.xlsx`](../../../../../../Business/Research/Dashboard/DataSources/BBG/FX/FX%20data%20file.xlsx).
Output: `FX/{CCY}/FX_{CCY}.csv` (per-ccy) + `FX/_Raw/fx.rda` (raw blob).

## End-to-end flow

1. Read `FX data file.xlsx` — 30 rows (28 per-ccy + `MS` + `MSVOL` aggregates).
2. Build `tickersAll = unique(union over all rows)` → single list of distinct Bloomberg tickers.
3. Call `Rblpapi::bdh(tickersAll, "px_last", Sys.Date()-90, Sys.Date(), options=...)` once — returns a named list of `xts` objects keyed by ticker.
4. Save the entire list to `FX/_Raw/fx.rda` (overwriting previous).
5. For each config row:
   a. Slice the blob: `temp_data[ticker_i] = bbg_fx_list[[ticker_i]]` for each ticker in this row (gracefully handling missing tickers with a `cat("missing...")` warning).
   b. Merge on `date`, apply `na.locf` (last-observation-carried-forward).
   c. **Apply FxSwap→FxFwd conversion** (see below).
   d. Read existing `FX/{CCY}/FX_{CCY}.csv`, keep first 3 header rows.
   e. Parse existing data rows, drop any rows with `date >= min(new_dates)`.
   f. Prepend new rows (reverse-chrono), rewrite the file with `write.table(..., sep=",", row.names=F, col.names=F, quote=F)`.

Total elapsed per full run: ~30 seconds for the BBG fetch, ~a few seconds for the 30 row writes.

## The FxSwap→FxFwd conversion (subtle, important)

Bloomberg returns **forward points** (not outright rates) for deliverable G10 pairs. The R script converts these to outright by `outright = spot + points / {divisor}` where the divisor depends on the currency. After this step, the CSVs store **outright forward levels** in all tenor columns.

The R logic:

```r
# JPY and THB quote at 2 decimal places → pip = 0.01 → divide by 100
if (ref_ccy == "THB" || ref_ccy == "JPY") {
    for (icol in 3:9) {     # only tenor cols (not spot)
        merged_data[, icol] = merged_data[, 2] + merged_data[, icol] / 100
    }
}
# G10 + metals + MXN + ILS + IDO quote at 4 decimal places → pip = 0.0001 → divide by 10000
else if (ref_ccy %in% c("AUD","EUR","GBP","XAU","CAD","NZD","SGD","NOK","SEK","CHF",
                         "XAG","PLN","RUB","MXN","ILS","IDO")) {
    for (icol in 3:ncol(merged_data)) {
        merged_data[, icol] = merged_data[, 2] + merged_data[, icol] / 10000
    }
}
# else: no conversion — for NDFs (IDR/INR/KRW/PHP/TWD/MYR), HKD (FMD tickers are outright),
#       CNH/CNO/CNY, MYO (onshore MYR), XAU (wait — XAU is in the list above).
```

### Currency → conversion table

| Ccy | Conversion | Why |
|---|---|---|
| AUD, EUR, GBP, NZD, SEK, NOK, CHF, CAD, PLN, ILS | `spot + points / 10000` | G10 4-dp fwd points |
| JPY, THB | `spot + points / 100` | 2-dp quote |
| XAU, XAG | `spot + points / 10000` | Metals quoted in 4-dp |
| MXN | `spot + points / 10000` | |
| IDO (onshore IDR) | `spot + points / 10000` | Explicitly in G10 list |
| HKD | none | Tickers are `FMD` (outright) — not fwd points |
| CNY, CNH, CNO, CNF | none | Tickers `CCN+`, `CNH+`, `CCO+` return outright |
| IDR (offshore NDF) | none | NDF tickers return outright |
| INR (offshore NDF), INF (onshore) | none | NDF; onshore spot + NDF forwards |
| KRW (NDF) | none | |
| PHP (NDF) | none | |
| TWD (NDF) | none | |
| MYR, MYO | none | NDF |

⚠️ **The G10 list in the R code omits `MXN` in the IRS variant at line 252** but includes it — inconsistent with the older `run_v0` function at line 71 which omits MXN. Current code is correct for MXN.

## Ticker semantics per pair

### Deliverable G10 (example: EUR)
```
EUR CURNCY        → spot EUR/USD
EUR1W CURNCY      → 1-week forward points (4-dp pips)
EUR1M CURNCY      → 1-month forward points
EUR3M CURNCY      → 3-month forward points
EUR6M CURNCY      → 6-month forward points
EUR9M CURNCY      → 9-month forward points
EUR12M CURNCY     → 12-month forward points
EUR2Y CURNCY      → 2-year forward points
```
After conversion, CSV columns show: spot, 1W outright, 1M outright, ... 2Y outright. Dividing by 10000 (pips), adding to spot.

### JPY / THB — different divisor
```
JPY CURNCY, JPY1W, JPY1M, JPY3M, JPY6M, JPY9M, JPY12M, JPY2Y
```
Fwd points divided by 100 (since JPY quotes at 2 dp: `USDJPY = 159.55`, not `1.5955`).

### HKD — outright native
```
HKD CURNCY            → spot
HKD+1M FMD CURNCY     → outright 1M forward (FMD = Forward Mid Direct)
HKD+3M FMD, +6M FMD, +9M FMD, +12M FMD, +2Y FMD
```
No conversion needed.

### NDF pairs (example: KRW)
```
KRW BSYN CURNCY       → NDF spot (BSYN = Bloomberg Synthetic)
KWN+1W CURNCY         → 1W NDF outright
KWN+1M, KWN+3M, KWN+6M, KWN+9M, KWN+12M, KWN+2Y
```
Note the ticker prefix is `KWN+` (not `KRW+`) — Bloomberg's NDF code convention. Same pattern for:
- IHN+ (IDR NDF)
- IRN+ (INR NDF)
- KWN+ (KRW NDF)
- PPN+ (PHP NDF)
- NTN+ (TWD NDF)
- MRN+ (MYR NDF)

Onshore EM variants use a different prefix:
- IHO (IDR onshore)
- IRO / INF (INR onshore)
- CCO+ (CNY onshore / CNO)
- MRO+ (MYR onshore / MYO)
- THO (THB onshore / `THO+` for fwds)
- CCN+ (CNY deliverable)

### Metals (XAU / XAG)
```
XAU CURNCY            → spot
XAUSR1M BGN CURNCY    → 1M SR (spot-ref) outright, BBG Generic
XAUSR3M, XAUSR6M, XAUSR12M, XAUSR2Y
```

## `MS` and `MSVOL` aggregate rows

Special rows in the config that don't map to per-ccy CSVs — instead, they dump a list of tickers intended for downstream dashboards (notably `volDashboard.R`).

- **`MS` row** (58 tickers): Asia-focused — AUD, CNH, INR, IDR, KRW, MYR, PHP, THB, TWD, SGD — each with spot + 1M forward.
- **`MSVOL` row** (18 tickers): Asia + metals + MXN 1M ATM vol tickers.

These tickers **still flow through the same `bdh()` call** at the top of the script (since `tickersAll` is built from *all* rows). They just don't get their own output CSV in the standard `FX/{CCY}/` tree.

## Output CSV: example `FX/HKD/FX_HKD.csv`

```
Ticker,HKD curncy,HKD+1M FMD curncy,HKD+3M FMD curncy,HKD+6M FMD curncy,HKD+9M FMD curncy,HKD+12M FMD curncy,HKD+2Y FMD curncy
Tenor,FX_HKD_SPOT,FX_HKD_1M,FX_HKD_3M,FX_HKD_6M,FX_HKD_9M,FX_HKD_12M,FX_HKD_2Y
Maturity,0,0.083333333,0.25,0.5,0.75,1,2
23/04/2026,7.8322,7.8233,7.8059,7.7813,7.7652,7.7488,7.6841
22/04/2026,7.8332,7.8237,7.8068,7.7821,7.7664,7.7498,7.6838
...
```

7 columns: SPOT + 6 tenors (1M, 3M, 6M, 9M, 12M, 2Y) — thinner grid than most FX pairs because HKD forwards are typically less actively quoted at weekly tenors.

## Inventory summary (from probe of 30 pairs, as of 2026-04-22)

All 30 pairs present, all latest row `22/04/2026`. Row counts (history depth):

- Largest history: `CNO` 1,899 rows (~5 years), `PHP` 1,775, `NZD` 1,736, `TWD` 1,505, `KRW` 1,368, `IDR` 1,360, `SEK` 1,335
- Shortest: `HKD` 315, `MYO` 316, `ILS` 395, `CHF` 441, `MYR` 526, `CNY` 527, `THB` 522, `NOK` 559, `XAU` 580, `XAG` 656

Tenor grid depth:
- 14 tenors: `SGD`, `CAD`
- 13 tenors: `PLN`
- 10 tenors: `ILS`
- 9 tenors: standard G10 Asia (AUD/CNH/EUR/GBP/CHF/NOK/SEK/JPY/NZD/KRW/IDR/INR/THB/PHP/TWD/MYR/CNY/CNO/MXN)
- 8 tenors: `HKD`, `IDO`
- 7 tenors: `MYO`, `XAU`
- 6 tenors: `XAG`

## Things to be careful of when ingesting

1. **Don't assume "forward points"** — the CSVs are outright levels post-conversion.
2. **JPY/THB divisor** — if we want fwd points back out, `points = (outright − spot) × 100` for these, `× 10000` for G10.
3. **Missing ticker fall-through** — when a ticker is absent in the BBG response, the R script warns but continues; the merged column for that ticker contains only NAs until backfilled by `na.locf`. For IMDR we'd want to reject the row rather than silently accept backfilled data.
4. **Writing mid-row creates inconsistent state** — if two runs land close together (race condition past the flag check), the CSV can have mixed-generation rows.
5. **The BBG_ASIA snap takes `first4rows` from the live CSV** — it doesn't re-fetch from BBG, so it only reflects whatever the last `master.R` run produced.
6. **Case sensitivity** — tickers in the config are inconsistently cased (`CURNCY` vs `Curncy` vs `curncy`). BBG accepts any case. The CSV headers preserve whatever case was in the config.
