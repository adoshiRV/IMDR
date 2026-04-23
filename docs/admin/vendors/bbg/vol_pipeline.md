# BBG Feed — Vol Pipeline

Scripts: [`Vol/vol.R`](../../../../../../Business/Research/Dashboard/DataSources/BBG/Vol/vol.R) → [`Vol/volFct.R`](../../../../../../Business/Research/Dashboard/DataSources/BBG/Vol/volFct.R).
Inputs: `Vol/_inputs/ccypairsForPnL.csv` — flat list of pairs to refresh.
Raw cache: `Vol/_Raw/fxVols.rda`, `Vol/_Raw/fxVols.EURUSD.rda`.
Outputs: `Vol/{CCYPAIR}/V_{CCYPAIR}.csv`, `Vol/{CCYPAIR}/{OTM}_{CCYPAIR}.csv` where `OTM ∈ {V, 25B, 25R, 10B, 10R}`.

## Key difference from FX/Rates scripts

The Vol pipeline has its own concurrency flag at `Vol/_Raw/flag.Rda` — **separate** from the main `flag.Rda`. And its own batch-time list:

```r
batchTimes = c("09:20", "13:00", "17:00", "19:00", "23:00")
```

This differs from the master scheduler's `09:30, 11:00, 13:00, 16:00, 18:00, 19:00`. The vol script uses its own cadence.

The vol script is **not** called from `master.R` — it's an independent flow. Evidence: it's not in the `rFiles` list inside `runMaster_()`. It's sourced from [`RatesFxAsia.R`](../../../../../../Business/Research/Dashboard/DataSources/BBG/RatesFxAsia.R) (indirectly) or scheduled separately.

## How it decides to run

```r
batchTime = max(batchTimes < now)        # last batch time before now
mtime = file.info("Vol/GBPUSD/V_GBPUSD.csv")$mtime
if (mtime > batchTime) {
    bRunBatch = FALSE       # GBPUSD already updated this batch — nothing to do
}

flag = readRDS("Vol/_Raw/flag.Rda")
if (abs(difftime(flag, Sys.time(), "secs")) < 20) {
    bRunBatch = FALSE       # another PC just ran — skip
}

if (bRunBatch) {
    runVol(ccypairs, path, otms, MODE, useCase)
}
```

So it uses **`GBPUSD` vol file mtime as the freshness proxy** for the whole batch. If GBPUSD was updated after the last batch time, assume the full batch already ran.

## Five output files per pair

For each currency pair in `ccypairs`, 5 output files:

| File | OTM key | Meaning |
|---|---|---|
| `V_{pair}.csv` | `V` | ATM vol |
| `25B_{pair}.csv` | `25B` | 25-delta butterfly |
| `10B_{pair}.csv` | `10B` | 10-delta butterfly |
| `25R_{pair}.csv` | `25R` | 25-delta risk reversal |
| `10R_{pair}.csv` | `10R` | 10-delta risk reversal |

The CSV shape is the same 3-header-row format as FX/Rates, with columns per tenor (1W, 1M, 2M, 3M, 6M, 9M, 1Y, 2Y, typically).

## Pair coverage (94 folders under `Vol/`)

Grouped by base ccy:

- **G10 vs USD**: AUDUSD, EURUSD, GBPUSD, NZDUSD (in dedicated folders)
- **JPY crosses**: AUDJPY, CADJPY, CHFJPY, CNHJPY, EURJPY, GBPJPY, NOKJPY, NZDJPY, SEKJPY, SGDJPY, TWDJPY
- **CNH crosses**: AUDCNH, CADCNH, CHFCNH, EURCNH, GBPCNH, NZDCNH, SGDCNH, USDCNH
- **AUD crosses**: AUDCAD, AUDCHF, AUDKRW, AUDNOK, AUDNZD, AUDSEK, AUDSGD, AUDTWD, AUDUSD
- **CAD crosses**: CADNOK, CADSEK, CADSGD
- **CHF crosses**: CHFNOK, CHFSEK, CHFSGD, CHFTWD
- **KRW crosses**: CNHKRW, EURKRW, JPYKRW, SGDKRW
- **TWD crosses**: CNHTWD, EURTWD, SGDTWD, TWDINR, TWDJPY, TWDKRW
- **SGD crosses**: EURSGD, GBPSGD, NZDSGD, SGDCNH, SGDINR, SGDJPY, SGDKRW, SGDNOK, SGDSEK, SGDTWD
- **NOK/SEK crosses**: CHFNOK, CHFSEK, NOKJPY, NOKSEK, SEKJPY
- **NZD crosses**: NZDCAD, NZDCHF, NZDCNH, NZDJPY, NZDNOK, NZDSEK, NZDSGD, NZDTWD, NZDUSD
- **GBP crosses**: GBPAUD, GBPCAD, GBPCHF, GBPCNH, GBPINR, GBPJPY, GBPNOK, GBPNZD, GBPPHP, GBPSEK, GBPSGD, GBPTWD, GBPUSD
- **EUR crosses**: EURAUD, EURCAD, EURCHF, EURCNH, EURGBP, EURINR, EURJPY, EURKRW, EURNOK, EURNZD, EURSEK, EURSGD, EURTWD, EURUSD
- **USD EM**: USDCAD, USDCHF, USDCNH, USDHKD, USDIDR, USDINR, USDJPY, USDKRW, USDNOK, USDPHP, USDSEK, USDSGD, USDTHB, USDTWD
- **Metals**: XAGUSD, XAUEUR, XAUJPY, XAUUSD
- **Inconsistent**: `MS` folder (dashboard aggregate)
- **Legacy**: `_Old` — archive

## Modes

```r
MODE <<- 'Updater'    # APPEND to existing files (default)
# MODE <<- 'Creator'  # NEW file for a new pair — only used when adding a pair
```

Use-case filter: `useCase = 'ForPnL'` — the `ccypairsForPnL.csv` list is a subset curated for PnL systems. Other curated lists may exist (e.g., `ForDashboard`).

## Raw cache specifics

`Vol/_Raw/fxVols.rda` — all fetched vol tickers, list-of-xts.

`Vol/_Raw/fxVols.EURUSD.rda` — a **per-pair override** for EURUSD. This exists because EURUSD vol has special handling (possibly tick-level data or different tenor grid). Single-file override pattern suggests it's a temporary hack.

`Vol/_Raw/flag.Rda` — 20-sec concurrency lock (mirrors main pattern).

## What's not clear without reading `volFct.R`

- Which Bloomberg field is used — likely `px_last`.
- Exact Bloomberg ticker patterns for each OTM. Typical pattern:
  - ATM: `{pair}V{tenor} Curncy` (e.g., `EURUSDV1M Curncy`)
  - 25B: `{pair}25B{tenor} Curncy` (butterfly 25d)
  - 25R: `{pair}25R{tenor} Curncy` (risk reversal 25d)
  - 10B, 10R: analogous
- How new pairs are added (`MODE='Creator'` path).
- Whether there's a `calendar.cb_events`-style market holiday filter (likely not).

If we want to ingest these into IMDR, a deeper read of `volFct.R` is needed.

## Relationship to IMDR `rates.fact_swaption_vol`

Different scope:
- IMDR `rates.fact_swaption_vol` is the **interest-rate** swaption vol cube (11 currencies, ATM/ATM_RFR/REALIZED). See [../../../rates/swaption_vol_schema.md](../../../rates/swaption_vol_schema.md).
- BBG Vol is **FX** vol (95+ pairs × 5 strikes). Closer analogue in IMDR is the existing `fx.yml` FX vol pipeline (17 pairs × 90 tags via Citi, see [../../../../fx/fx_vol_pipeline.md](../../../fx/fx_vol_pipeline.md)).

BBG Vol could supplement our Citi FX vol ingest by:
1. Adding the 77 FX cross pairs IMDR doesn't currently cover.
2. Providing a G10 cross vs USD comparison source.

## Status for IMDR

**Not prioritized.** FX vol is well-covered by Citi. BBG vol would be primarily useful for:
- Cross-pair vol (FX-FX crosses not via USD).
- PnL reconciliation against the existing `ccypairsForPnL` dashboard.

Recommend deferring vol ingest until after core FX + Rates BBG ingestion is stable.
