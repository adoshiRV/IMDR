# BBG Feed — Quirks and Gotchas

Collected from reading the R sources, Excel configs, and actual files on disk. These are the things that will bite any IMDR integration if we don't handle them explicitly.

## Data-shape quirks

### 1. FX CSVs are outright levels, not forward points

The R script applies `outright = spot + points / divisor` where divisor is **100 for JPY/THB** and **10000 for G10 + metals + MXN + ILS + IDO**. NDFs and CNY-family use outright tickers directly.

**Implication**: If we want to store fwd points in IMDR (to match our existing `fx.fact_fx_rate.fwd_points` column), we have to invert:
```
fwd_points = (outright − spot) × divisor
```
And the divisor depends on the currency — we'd need a lookup table. Easier: read `_Raw/fx.rda` directly and skip the conversion.

### 2. 3-header-row CSV format is non-standard

Row 0 = Bloomberg ticker, row 1 = RV internal tenor alias, row 2 = maturity in years. Any parser must `skip=3`. Pandas's `read_csv` with `skiprows=3, header=None` is the cleanest approach — but then you lose the column names. Use `skiprows=3, header=None` + separately read the first 3 rows as the schema.

### 3. `dd/mm/yyyy` date format (UK/European)

Not ISO-8601, not US. `pd.to_datetime(s, format='%d/%m/%Y')` explicitly — default parsing may misinterpret `03/04/2026` as April 3rd vs March 4th depending on locale.

### 4. Missing ticker in BBG response → `na.locf` fill

When a ticker disappears from BBG's response, the R script prints `"missing {ticker}"` and continues. The merged column for that ticker gets NAs, then `na.locf` fills from the previous known value. **IMDR should reject NA-filled data, not accept it** — we can detect by comparing the freshness of individual ticker mtimes if we fetch from `.rda` directly.

### 5. Same ticker mapped to multiple "currencies"

Spotted in `refresh_R_bbg.xlsx`:
- `KWCDC Curncy` → both `KRW-91D_CD-3M` and `KRO-91D_CD-3M` (onshore variant — same ticker)
- `KLIB3M Index` → both `MYR-KLIBOR-3M` and `MYO-KLIBOR-3M`

Either the onshore/offshore distinction is irrelevant for these fixings (they're published as one series), or the config is wrong. Either way, don't double-count when aggregating.

### 6. Case-inconsistent ticker strings

Bloomberg treats tickers case-insensitively, but the CSVs preserve whatever case is in the config. Column names in `FX/HKD/FX_HKD.csv` are `HKD+1M FMD curncy` (lowercase), in `FX/JPY/FX_JPY.csv` are `JPY1W curncy`, while `FX/AUD/FX_AUD.csv` may mix cases. Use case-insensitive lookups.

## Concurrency / scheduling quirks

### 7. `flag.Rda` race is imperfect

Two PCs starting within 20 s of each other can both bail (both see a recent timestamp from the other). The code writes `flag = Sys.time()` even in the bail branch — which looks unintentional but effectively extends the "blocked" window. In practice rare enough not to matter.

### 8. `mainUser = "spanda"` is a single point of failure

If `spanda` is away and their Bloomberg terminal is off, the first batch after they leave sees backup users kick in after a staleness check. Gap of up to one batch cycle (~2 hours) of stale data is possible.

### 9. 4-minute skew between scheduler (09:30) and freshness check (09:25)

Intentional — files written after 09:30 are timestamped after 09:25, so the freshness check at any time after 09:25 (but before 09:30 finishes) gets the right answer. But the next freshness-check boundary is 11:00, so between 09:25 and 11:00 the effective window is wide.

### 10. Vol pipeline uses a **separate** flag file

`Vol/_Raw/flag.Rda` is independent of the main `flag.Rda`. Vol runs on its own cadence (`09:20, 13:00, 17:00, 19:00, 23:00`) and is not invoked by `master.R`. Check this separately if you need vol freshness.

## File/path quirks

### 11. `BASIS/LCH.JSCC` — literal dot in folder name

Most BASIS folders are `{leg1}.{leg2}` with a dot as separator, but `LCH.JSCC` is a clearing-venue basis quoted as a single token with an internal dot. Parse carefully — splitting on `.` gives wrong results.

### 12. `Credit/Credit.xlsx` has both caps and lowercase 'Credit' as the type

The config file's `Type` column is `Credit` (capital C), while folders are also `Credit/`. Consistent here, but some downstream scripts assume lowercase — grep if you hit issues.

### 13. `BBG_ASIA/{date}/FX/{CCY}/FX_{CCY}.csv` copies only **first 4 rows** of live

The Asia snap isn't a refetch — it's a `head -4` copy. If the live CSV was stale when the snap ran, the snap is stale. Also: if today's row is **not** present in the live CSV (e.g., BBG didn't return today's data), the snap is skipped silently (just a `print()` notice).

### 14. `_Raw/*.rda` overwrites each run

No historical raw blobs retained. If you want replay capability, snapshot these yourself (cron: `cp fx.rda fx.{date}.rda`).

### 15. `log/bbgCheck/` folder is unbounded

Thousands of files, one per `master.R` run × user × history. No rotation. Filesystem operations (`ls`) are slow.

## Config quirks

### 16. `MS` aggregate row

Special row in `FX data file.xlsx` (row 0, 58 tickers) and `refresh_R_bbg.xlsx` (row 25 etc., 1 ticker for IRS/Commodities/Vol types). The tickers **are fetched** (via `tickersAll`), but there's no corresponding per-ccy output folder. These feed dashboards only. The freshness check explicitly excludes them: `excludeCcies = c("MSVOL", "MS")`.

### 17. `MSVOL` aggregate

Row 1 of `FX data file.xlsx`, 18 tickers — all 1M ATM vol tickers for Asia + metals + MXN. Same exclusion in freshness check.

### 18. `FXSwap→FxFwd` list and G10 list are inconsistent across script versions

The FX script's `run_v0()` (legacy, disabled) has one list of G10 currencies. The active `run()` has an updated list including `MXN, ILS, IDO`. If anyone re-enables `run_v0()` for testing, MXN data will silently come out un-converted (points stored as if they were outright).

### 19. Cleaning functions are all commented out

The `cleaning` column of `refresh_R_bbg.xlsx` is `N` for all rows except one or two. When `Y`, the script would call `clean.{iden}()` but all such functions are commented out in the source. Effectively a dead feature. If IMDR reproduces this pipeline, we can drop the cleaning step unless we find a row with `Y` that breaks.

## BBG-side quirks

### 20. `blpConnect` to `localhost:8194` fails silently

If the Bloomberg Terminal isn't running on the PC, `blpConnect` raises an error. The outer `tryCatch` swallows it. `checkBbgFeed()` returns `NA`. `runMaster_()` sees `is.na(resCheckBbg)` and skips the whole batch **without retrying**. The next batch (2 hours later) is the earliest recovery.

Evidence: `BBGLog.log2026-04-22` at 09:25:
```
Connection failed
[ERROR]checkBbgFeed :  Error in blpConnect_Impl(host, port, appName): Failed to start session.
End BbgCheck|value=NA|user=spanda|batchStart=2026-04-22 09:25:16.175
(then all 52 IRS/OIS/BASIS/CCS CSVs + 28 FX CSVs flagged "Issue in-")
```

### 21. Non-trading-weekday fill can mask real gaps

BBG option `nonTradingDayFillOption=NON_TRADING_WEEKDAYS, nonTradingDayFillMethod=PREVIOUS_VALUE` returns weekend/holiday days with the previous-business-day value. This is fine for daily-close data but **silently fills regional holidays** — e.g., Chinese New Year week on a CNY curve shows "data" but it's stale.

Our IMDR calendar (`calendar.cb_events`, `dim_market`) would let us strip these out. BBG CSVs don't flag them.

### 22. `bdh` without `currency=USD` option returns native currency

For most instruments this is what we want. Commodities are explicitly coerced to USD:
```r
if (ref_type == "Commodities") {
    temp_data = bdh(tickers, "px_last", Sys.Date()-10, Sys.Date(), options = c('currency' = 'USD'))
}
```

For bonds, there's **no** explicit currency coercion — watch out when mixing currencies.

## Misc

### 23. 1-second sleep for backup users

Backup users call `Sys.sleep(1)` before running, ostensibly to let the main user's write complete first. 1 second is arbitrary and may be insufficient for the full `bdh` fetch (~30 s for FX + rates). In practice the `flag.Rda` already handles this, but the `Sys.sleep` is a belt-and-braces hack.

### 24. `cat()` + `print()` mixing is noisy

R's `cat` writes without newline; `print` adds quotes + newline. Log files alternate styles. Parsing downstream is fragile.

### 25. Scheduler creates tasks but never deletes them

`scheduler.R` uses `taskscheduler_create` without checking if the task already exists. Running `setup.R` twice creates duplicate scheduler entries. Use `taskscheduleR::taskscheduler_delete()` to clean up.

### 26. `setup.R` has a typo

```r
source("Z:/Business./Research/dashboard/DataSources/BBG/scheduler.R")
                  ^^^^^^^^^^
```
`Business.` (with trailing dot) and lowercase `dashboard` — will fail on case-sensitive filesystems. Works on NTFS because it's case-insensitive. If anyone ever tries running from Linux/WSL, this breaks.

### 27. Commented-out debug paths that could be re-enabled accidentally

Every refresher has `bDebug = FALSE` and `if (1==2)` dead code blocks. Editing `1==2` to `1==1` re-enables these paths — a footgun.

## How IMDR should respond to these

- **#1–#4**: Handle explicitly in the parser. Document the format.
- **#5–#6**: Deduplicate / normalize when seeding `dim_*` tables.
- **#7–#10, #20**: Observability — surface "BBG terminal down" and "stale file" as warnings in RunReport.
- **#11–#12**: Sanitize folder names during dim-seeding.
- **#13–#15**: Choose `.rda` as source of truth for IMDR (not CSVs) to avoid double-transformation and to get raw ticker-level data.
- **#16–#19**: Explicitly exclude MS/MSVOL; track cleaning=Y rows manually; pin to the `run()` (not `run_v0()`) convention.
- **#21**: Cross-reference with `calendar.dim_trading_day` to filter stale holiday fills.
- **#26**: Not our problem until we modify their tree — but documented so we don't repeat the mistake.
