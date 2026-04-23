# Bloomberg (BBG) Feed — System Documentation

This documents the **existing** Bloomberg data-refresh system that lives on the shared Z: drive (`Z:\Business\Research\Dashboard\DataSources\BBG\`, which maps to `\\RVSG-FS01\shared\Business\Research\Dashboard\DataSources\BBG\`). It is **not** part of the IMDR codebase today; IMDR ingestion is planned — see [imdr_integration_plan.md](imdr_integration_plan.md).

> **Scope**: this is a field-walk of the R-based multi-PC fetcher operated by the research team. The goal is to capture exactly how it works so IMDR can consume the outputs cleanly without disturbing the existing pipeline.

## The one-paragraph summary

Multiple PCs on the research team each run a Windows Task Scheduler job several times a day. Each job invokes [master.R](../../../../../../Business/Research/Dashboard/DataSources/BBG/master.R), which (a) confirms the local Bloomberg Terminal is alive via a tiny `bdh` probe, (b) acquires a lock via `flag.Rda`, (c) if it wins the lock, calls domain-specific R refreshers that pull data via `Rblpapi::bdh()`, (d) the refreshers save both a raw blob (`_Raw/*.rda`) and append to per-series CSVs with a 3-row header. At 16:30 SGT, [RatesFxAsia.R](../../../../../../Business/Research/Dashboard/DataSources/BBG/RatesFxAsia.R) also snapshots today's row into a date-stamped `BBG_ASIA\{YYYY-MM-DD}\...` tree for the Asia cutoff.

## Pipeline inventory

| Domain | Fetcher script | Config | Output tree |
|---|---|---|---|
| **FX** (spot + outrights) | `FX/bbg_refresh.R` | `FX/FX data file.xlsx` | `FX/{CCY}/FX_{CCY}.csv` |
| **IRS / OIS / BASIS / CCS** | `pull data from bbg.R` | `refresh_R_bbg.xlsx` | `{Type}/{Ccy}/PAR/{Type}_PAR_{Ccy}.csv` |
| **IR fixings** | `FIXINGS/IrFixings.R` | hardcoded `bbgIndexMap` | `FIXINGS/_Out/...` |
| **Credit** | `Credit/bbg_refresh_credit.R` | `Credit/Credit.xlsx` | `Credit/{Ccy}/{Series}/*.csv` |
| **Bonds** | `BONDS/bbg_refresh_bonds.R` | `BONDS/Bonds data file.xlsx` | `BONDS/{CCY}/...` |
| **Futures** | `FUTURES/bbg_refresh_futures.R` + 3 helpers | `FUTURES/Futures Data File.xlsx` etc. | `FUTURES/{CODE}/...` |
| **FX vol** | `Vol/vol.R` → `Vol/volFct.R` | `Vol/_inputs/ccypairsForPnL.csv` | `Vol/{CCYPAIR}/V_{CCYPAIR}.csv` + 25B/10B/25R/10R |
| **Listed** | `Listed/listed.R` → `Listed/listedFct.R` | `Listed/Input/...` | `Listed/bond_MKT=*.csv` |
| **ASIA snapshot** | `RatesFxAsia.R` | all of the above | `BBG_ASIA/{YYYY-MM-DD}/{Type}/{Ccy}/...` |

## Documentation map

| Doc | Topic |
|---|---|
| [architecture.md](architecture.md) | `master.R` orchestration, multi-PC coordination, `flag.Rda` lock |
| [scheduling_and_health.md](scheduling_and_health.md) | Task Scheduler times, BBG terminal dependency, log + heartbeat conventions |
| [data_formats.md](data_formats.md) | CSV 3-header-row layout, `.rda` cache, `BBG_ASIA` tree |
| [configs.md](configs.md) | The Excel ticker-config files — schema and quirks |
| [fx_pipeline.md](fx_pipeline.md) | FX deep dive: FxSwap→FxFwd math, NDF handling, MS/MSVOL aggregates |
| [rates_pipeline.md](rates_pipeline.md) | IRS / OIS / BASIS / CCS — 52-row universe |
| [vol_pipeline.md](vol_pipeline.md) | FX vol — 5 strike slices × 94 pair folders |
| [other_pipelines.md](other_pipelines.md) | Credit / Bonds / Futures / Fixings / Listed (briefer) |
| [quirks_and_gotchas.md](quirks_and_gotchas.md) | Known issues and subtle behaviours before IMDR touches this |
| [imdr_integration_plan.md](imdr_integration_plan.md) | Proposed path for IMDR-side ingestion |

## Why this matters for IMDR

1. **Coverage** — The BBG feed covers currencies (MYR/MYO onshore, MXN, ILS, IDO onshore) and instruments (LIBOR variants, SHIBOR, KLIBOR, TAIBOR, MIBOR, CPI fixings) that our Citi-only ingestion does not.
2. **Redundancy** — For FX SPOT and swap curves already on Citi, BBG is a second source for cross-validation.
3. **Legacy compatibility** — Several internal dashboards and research notebooks already consume these CSVs. If IMDR replaces BBG as primary, we still need to keep this tree alive (or mirror from IMDR back to disk).
4. **Asia cutoffs** — The `BBG_ASIA/{YYYY-MM-DD}/` tree gives us a ~16:30 SGT snap which Citi doesn't publish in the same form. Useful for Asia-hour P&L marks.

## Read ordering

If you're new to this system, read in this order:
1. [architecture.md](architecture.md) — understand the fetcher orchestration
2. [data_formats.md](data_formats.md) — understand the file shape you'll be parsing
3. [configs.md](configs.md) — understand the universe
4. Whichever domain-specific doc you need (fx / rates / vol / other)
5. [quirks_and_gotchas.md](quirks_and_gotchas.md) before writing IMDR code that touches any of this
6. [imdr_integration_plan.md](imdr_integration_plan.md) for the proposed roadmap

## Source references

All paths below are relative to `Z:\Business\Research\Dashboard\DataSources\BBG\`:
- `master.R` — top-level orchestrator
- `scheduler.R` — Task Scheduler setup
- `setup.R` — R package installation bootstrap
- `FX/bbg_refresh.R`, `pull data from bbg.R`, `Vol/vol.R`, etc. — per-domain refreshers
- `RatesFxAsia.R` — Asia-cutoff snapshotter
- `log/BBGLog.log{YYYY-MM-DD}` — daily batch logs
- `log/bbgCheck/` — per-run heartbeat files
- `flag.Rda` — multi-PC concurrency flag
- `_Raw/*.rda` per domain — raw Bloomberg `bdh()` output cache
