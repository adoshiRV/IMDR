# BBG Feed — Scheduling and Health

## Task Scheduler entries

Created by [scheduler.R](../../../../../../Business/Research/Dashboard/DataSources/BBG/scheduler.R) using the `taskscheduleR` package. Each PC that participates runs `scheduler.R` once to populate its local Windows Task Scheduler, then those tasks fire on the schedule below:

| Task name | Schedule | Script |
|---|---|---|
| `update_bbg_9am` | Weekdays 09:30 | `master.R` |
| `update_bbg_11am` | Weekdays 11:00 | `master.R` |
| `update_bbg_1pm` | Weekdays 13:00 | `master.R` |
| `update_bbg_4pm` | Weekdays 16:00 | `master.R` |
| `update_bbg_6pm` | Weekdays 18:00 | `master.R` |
| `update_bbg_7pm` | Weekdays 19:00 | `master.R` |
| `CopyListedPosition_0920` | Weekdays 09:20 | `CopyListedInput.R` |
| `CopyListedPosition_1500` | Weekdays 15:00 | `CopyListedInput.R` |
| `Citi-Download` | Weekdays 21:10 | `Z:\...\DataSources\CITI\citioisupdate.R` |
| `A_B-daily-report` | Weekdays 10:00 | `Z:\...\Saswat\PCA-Deepak\Swaps test.R` |

All times local to the PC (which for Singapore desks = SGT).

### Reference batch times (used by `checkFilesStatus`)

`findRefBatchTime()` in [master.R](../../../../../../Business/Research/Dashboard/DataSources/BBG/master.R) uses a slightly different list — these are the **expected fresh-by** times for file staleness checks:

```
09:25, 11:00, 13:05, 17:00, 18:00, 19:00, 23:00
```

Note the mismatch between the scheduler (09:30) and the freshness check (09:25) — the 09:25 boundary is used so the 09:30 scheduler fire has its output timestamped **after** 09:25, marking files as fresh. The 13:05 freshness marker (vs 13:00 scheduler) accounts for batch runtime.

### Asia snap window

`RatesFxAsia.R` runs only if `now ∈ [16:30, 17:55] SGT`. Since a `master.R` fire exists at 16:00 (not inside the window), the **17:00 batch is too late** (17:55 < 17:00? No, 17:55 > 17:00, so 17:00 *is* inside the window — actually, 17:00 SGT batch should trigger the snap). But 18:00 and 19:00 fires are outside the window, so the snap is written once around 16:30–17:00 and not again.

> ⚠️ There is commented-out logic for a `19:00–20:00` SGT window pointing at a `RatesFxAsia_new.R`. Currently disabled.

## Multi-PC coordination

### `flag.Rda`

A serialized R object holding a single `POSIXct` timestamp. Path: `Z:\Business\Research\Dashboard\DataSources\BBG\flag.Rda`.

Lock protocol:
1. Read `flag`.
2. If `abs(now - flag) < 20 seconds` → another user just started, bail (but paradoxically still overwrite `flag` with `now`).
3. Else → overwrite `flag` with `now` and proceed with the full run.

**Failure modes**:
- Two PCs start within 20 s of each other: both see the other's timestamp within threshold, both bail. Neither runs. Next scheduled fire runs.
- PC-A starts at 09:30:00, PC-B starts at 09:30:19: PC-A writes flag and runs. PC-B reads PC-A's flag (within 20 s), bails. OK.
- PC-A starts at 09:30:00 and crashes 2 s later without writing: PC-B starts at 09:30:19 and bails because PC-A's earlier write is still within 20 s. The batch is missed.

### `mainUser = "spanda"` pattern

Inside `runMaster()`:
- If `login == spanda`: always run the full refresh, even if files are fresh.
- Otherwise: only run if `checkFilesStatus()` returns anything other than `SUCCESS`. This is the "backup" role.

**Implication**: if `spanda` is away and their PC is off, the backup PCs only kick in *after* they detect stale files — which means the first batch after `spanda` is off may see stale data until the next `master.R` fire.

### `rroy` is excluded

```r
if (currUser == 'rroy') {
    print(paste0(currUser, ' should not run master.R'))
}
```

No explicit `return()` though — the script continues into `runMaster()`. The print is the only guard. If `rroy` has the scheduler tasks installed, the run continues anyway. Effectively a soft hint, not a hard block.

## Logging

### Daily batch log — `log/BBGLog.log{YYYY-MM-DD}`

Written by the BBG scheduler wrapper (a .NET wrapper named `BBGScheduler.Program` — note this is a separate Windows service that invokes `master.R`; it is outside the R tree). Format:

```
2026-04-22 09:25:08,330 DEBUG BBGScheduler.Program - BBG Scheduler Started
2026-04-22 09:25:08,346 DEBUG BBGScheduler.Program - UserName : spanda
2026-04-22 09:25:09,437 DEBUG BBGScheduler.Program - Running RScript
2026-04-22 09:25:40,015 DEBUG BBGScheduler.Program - R Script Retuns: [2026-04-22 09:25:10]Start master.R|u=spanda
22APR2026_09:25:33.278 37664:41140 ERROR blpapi_platformtransporttcp.cpp:671 ... Connection failed
2026-04-22 09:25:33.278[ERROR]checkBbgFeed :  Error in blpConnect_Impl(...)
[1] "[2026-04-22 09:25:33.278]End BbgCheck|value=NA|user=spanda|batchStart=..."
[1] "  [2026-04-22 09:25:33.656] Issue in- Z:\\...\\BASIS\\...\\BASIS_PAR_AUD-BBSW-6M.AUD-BBSW-3M.csv"
[1] "  [2026-04-22 09:25:33.736] Issue in- Z:\\...\\IRS\\CNY-REPO-7D\\PAR\\IRS_PAR_CNY-REPO-7D.csv"
... (many more "Issue in-" lines)
```

So a health scanner needs to parse:
- `End BbgCheck|value=NA` → Bloomberg terminal offline.
- `[ERROR]` lines → per-script exceptions.
- `Issue in-` lines → per-file staleness reports.

### Heartbeat files — `log/bbgCheck/`

Every `master.R` run writes one CSV named:

```
[YYYY-MM-DD HHhMMmSSs][user][V={feed_value}].csv
```

The file contents are a single line reporting `value`, `user`, `batchStart`, `rVersion`. When `value = NA`, the terminal was offline at that moment.

**The `bbgCheck/` folder grows unbounded** — one file per run per user across all history. Useful as an audit trail; unfortunate for filesystem performance. As of writing it contains thousands of files.

## Freshness SLA in practice

| Check | What to do |
|---|---|
| "Is today's data in the CSVs?" | Read first 4 rows of `FX/{CCY}/FX_{CCY}.csv` or `{Type}/{Ccy}/PAR/{...}.csv`; row 3 (0-indexed) is the latest date. Compare vs today in `dd/mm/yyyy` format. |
| "Did the latest batch succeed?" | Find latest `log/bbgCheck/*.csv` — if `V=NA` in filename, terminal was offline. |
| "Which files didn't update this batch?" | Grep `log/BBGLog.log{today}` for `Issue in-`. |
| "Did the Asia snap run?" | Check `BBG_ASIA/{today}/FX/` exists and is non-empty. |

## Known health risks

1. **Bloomberg Terminal uptime on the primary PC** is a single point of failure for `spanda`'s role. Observed: 2026-04-22 09:25 batch failed with `blpConnect: Failed to start session` on `spanda` — no backfill until the next batch when a backup PC presumably recovered.
2. **No alerting** — failure is only visible by log inspection or by downstream consumers noticing stale data.
3. **`flag.Rda` stale after crash** — if PC-spanda crashes mid-run, the flag still shows a recent timestamp, blocking backups for up to 20 s. In practice 20 s is short enough this isn't a big issue.
4. **No weekend runs** — tasks scheduled `MON-FRI` only. Holiday handling is implicit (BBG returns previous-value fill via `NON_TRADING_WEEKDAYS`).
5. **Task Scheduler is local to each PC** — a PC that's rebooted and lost its scheduler entries silently drops out of the pool.

## What IMDR should do for health monitoring

See [imdr_integration_plan.md](imdr_integration_plan.md). Short version: parse `log/bbgCheck/` + `log/BBGLog.log{today}` during ingestion and surface as `RunReport` warnings; treat `mtime`-based staleness on target CSVs as the ingestion signal.
