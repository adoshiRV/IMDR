# BBG Feed — Architecture

## High-level flow

```
┌─────────────┐       ┌─────────────┐       ┌─────────────┐
│  PC-spanda  │       │  PC-backup1 │       │  PC-backup2 │   ← each runs Windows Task Scheduler
│  master.R   │       │  master.R   │       │  master.R   │     jobs at 09:30, 11, 13, 16, 18, 19
└──────┬──────┘       └──────┬──────┘       └──────┬──────┘
       │                     │                      │
       └─────────── flag.Rda (20-sec lock) ─────────┘
                             │
                             ▼
                  ┌──────────────────────┐
                  │  checkBbgFeed()      │   bdh("EUR Curncy", "LAST_PRICE", today-10, today)
                  │  → logs to           │   writes heartbeat CSV to log/bbgCheck/
                  │    log/bbgCheck/     │
                  └──────────┬───────────┘
                             │ if BBG alive → fork to domain refreshers
      ┌──────────┬───────────┼──────────┬──────────┬──────────┬──────────┐
      ▼          ▼           ▼          ▼          ▼          ▼          ▼
  FX/           pull data  IrFixings  listed.R   Credit/    BONDS/    FUTURES/ (×4)
  bbg_refresh.R from       .R                    bbg_refresh bbg_refresh  (incl. CTD,
  (FX)          bbg.R                            _credit.R   _bonds.R    rolled,
                (IRS/OIS/                                                ED_FF...)
                BASIS/CCS)
      │          │           │          │         │          │         │
      ▼          ▼           ▼          ▼         ▼          ▼         ▼
  FX/_Raw/   IRS/_Raw/   (per-fixing)  Listed/ Credit/_Raw/ BONDS/_Raw/ FUTURES/_Raw/
  fx.rda     irs.rda                  Raw/    credit.rda   bond.rda    futures.rda
      │          │                      │          │          │         │
      ▼          ▼                      ▼          ▼          ▼         ▼
  FX/{CCY}/  {Type}/{CCY}/          Listed/   Credit/{CCY}/  BONDS/{CCY}/  FUTURES/{CODE}/
  FX_{CCY}   PAR/{Type}_PAR_        *.csv     {Series}/      ...          ...
  .csv       {Ccy}.csv

                             ▼ (16:30–17:55 SGT only)
                     RatesFxAsia.R
                             │
                             ▼
                 BBG_ASIA/{YYYY-MM-DD}/{Type}/{CCY}/...csv
                 (snapshot of first 4 rows from each CSV = today's row only)
```

## The orchestrator — [master.R](../../../../../../Business/Research/Dashboard/DataSources/BBG/master.R)

Three main functions, called from the bottom-of-file main block:

### `runMaster()` — entry point

```r
mainUser = "spanda"
currUser = Sys.info()['login']
bIsMainUser = (currUser == mainUser)

if (bIsMainUser == FALSE) {
    # I'm a backup — only run if the primary hasn't already finished
    prevStatus = checkFilesStatus()
    if (prevStatus != "SUCCESS") {
        Sys.sleep(1)        # brief stagger to avoid racing the primary
        runMaster_()
        outStatus = checkFilesStatus(T)
    } else {
        outStatus = "SUCCESS"    # primary already done — nothing to do
    }
} else {
    # I'm the primary — always run
    runMaster_()
    outStatus = checkFilesStatus(T)
}
```

**Roles**:
- `mainUser = spanda` always runs `runMaster_()`.
- All other users check whether the file outputs are fresh; if so they skip, otherwise they run as a backup.
- `rroy` is explicitly blocked (`print('rroy should not run master.R')` guard).

### `runMaster_()` — the actual work

The sequence:

1. **Lock**: read `flag.Rda`, which holds a single `Sys.time()` timestamp. If the last write was within the last **20 seconds**, treat as "another user just started" and bail. Otherwise overwrite `flag.Rda` with `Sys.time()` to claim the slot.

   ⚠️ **Subtle bug**: the current code writes `flag = Sys.time(); saveRDS(flag, ...)` in *both* branches (the "bail" branch and the "take over" branch). So two users starting within 20 s could both write their own timestamp but only one continues — correct in practice, but the bail-branch write is pointless.

2. **BBG probe** — `checkBbgFeed()`:
   ```r
   Rblpapi::blpConnect(host = "localhost", port = 8194L)
   bbgData = Rblpapi::bdh("EUR Curncy", "LAST_PRICE", Sys.Date()-10, Sys.Date())
   resout = bbgData[1, "LAST_PRICE"]
   ```
   Writes heartbeat CSV to `log/bbgCheck/[timestamp][user][V=rate].csv`. If `blpConnect` fails, `resout = NA` and the whole batch is skipped.

3. **Dispatch refreshers** — a `foreach(iF = 1:nFiles) %do% { source(rFiles[iF]) }` loop. The `%dopar%` variant exists but is dead code (`if(1==2)`). The scripts called, in order:
   - `FX/bbg_refresh.R`
   - `pull data from bbg.R` (IRS + OIS + BASIS + CCS)
   - `FIXINGS/IrFixings.R`
   - `Listed/listed.R`
   - `Credit/bbg_refresh_credit.R`
   - `BONDS/bbg_refresh_bonds.R`
   - `FUTURES/bbg_refresh_futures.R`
   - `FUTURES/CTD futs daily update.R`
   - `FUTURES/ED_FF_IR_KE_KAA_SFR_Xm_YM daily update.R`
   - `FUTURES/rolled futs daily update.R`

4. **Asia snap** — if current local time is within `16:30–17:55 SGT`, source `RatesFxAsia.R`, which copies today's row from each FX/IRS/OIS/BASIS/Credit CSV into a date-stamped `BBG_ASIA/{YYYY-MM-DD}/{Type}/{CCY}/...csv` tree.

### `checkFilesStatus()` / `findFilesTimestamp()` — did the batch succeed?

Compares each target CSV's `mtime` against `findRefBatchTime()` (the most recent batch time strictly before now, from the list `09:25, 11:00, 13:05, 17:00, 18:00, 19:00, 23:00`). If **all** CSVs have `mtime >= refBatchTime`: `SUCCESS`. If **none** do: `FAILED_FULL`. Anything in between: `FAILED_PARTIAL`.

**Freshness check detail**:
- For IRS/OIS/BASIS/CCS, the check iterates `refresh_R_bbg.xlsx` rows (excluding `MS` and `MSVOL` aggregate rows) and checks `{type}\{ccy}\PAR\{type}_PAR_{ccy}.csv`.
- For FX, the check iterates `FX/FX data file.xlsx` rows (same exclusions) and checks `FX\{ccy}\FX_{ccy}.csv`.
- The "other" domains (Credit, Bonds, Futures, Fixings, Listed, Vol) are **not** included in this freshness check. Their health is only implicit via the lack of errors in `BBGLog.log{date}`.

## Per-domain refresher shape

All domain refreshers follow the same pattern:

1. Read ticker config from an Excel file (`Type | Ccy | [spotorfwd | cleaning] | Tickers[]`).
2. Union all tickers across all rows into `tickersAll`.
3. Single `Rblpapi::bdh()` call for all tickers with:
   - `periodicitySelection = "DAILY"`
   - `nonTradingDayFillOption = "NON_TRADING_WEEKDAYS"`
   - `nonTradingDayFillMethod = "PREVIOUS_VALUE"`
   - Lookback: 90–1000 days depending on domain (FX: 90, IRS: 100, Credit: 1000)
4. Save raw list-of-xts to `_Raw/{domain}.rda` (overwrites the previous blob each run).
5. For each config row:
   - Slice the raw blob for this row's tickers.
   - Merge on `date` column with `na.locf` fill.
   - Apply domain-specific transforms (FX: FxSwap→FxFwd conversion; see [fx_pipeline.md](fx_pipeline.md)).
   - Read existing CSV, preserve first 3 header rows, drop old rows ≥ min(new_dates), append new rows in reverse-chronological order.
   - Rewrite CSV with `dd/mm/yyyy` date formatting.

## Dependencies

- **Bloomberg Terminal** installed and running on each PC (Rblpapi connects via `localhost:8194`).
- **R 4.1.2+** with packages: `bizdays`, `zoo`, `Rblpapi`, `openxlsx`, `data.table`, `parallel`, `doFuture`, `zip`, `taskscheduleR`.
- `Z:\Business\Personnel\Saswat\gen r functions\install_or_load_pkg.R` — shared helper for lazy-install-and-load.
- Network access to the `\\RVSG-FS01\shared` fileshare (Z: drive).
- Windows Task Scheduler for cron-equivalent scheduling.

## Why this design is the way it is

- **Multi-PC redundancy without shared infra**: each PC is independent, coordinated only through a single `flag.Rda` file on the shared drive. No message broker, no central scheduler service.
- **Bloomberg Terminal license tied to a PC**: each PC has its own desktop license; running from multiple PCs doesn't consume extra data quota but gives fallback if one terminal is offline.
- **`mainUser` pattern**: avoids running the same queries from every PC every batch, which would multiply load and create file-write races.
- **Single `.rda` per domain per run**: keeps the raw Bloomberg response around for debugging (`bBbgOnOff = FALSE` in the scripts re-reads from disk instead of re-querying BBG).

## What is *not* in this architecture

- ❌ No database — everything is flat-file on Z drive.
- ❌ No real error alerting — failures are `cat()`-ed to the log file and silently `tryCatch`-ed per-row.
- ❌ No audit trail of individual ticker values — only the final merged CSV.
- ❌ No atomic writes — CSV is rewritten in place; a crash mid-write corrupts it.
- ❌ No retry logic — if BBG is down at 09:25, the 09:30 batch is gone; no auto-retry until 11:00.
- ❌ No test coverage.
