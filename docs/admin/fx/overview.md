# FX Domain — Operational Reference

Everything about how the FX domain works: architecture, pipeline, scripts, quality checks, and configuration.

For schema details (tables, columns, constraints), see `docs/fx/schema.md`.

---

## Architecture

### Module Map (`src/imdr/domains/fx/`)

| Module | Purpose |
|---|---|
| `extractors.py` | BidFX API tick fetching (ThreadPoolExecutor), bar building from ticks. Key class: `BidFXExtractor` |
| `ingest.py` | Core pipeline: `process_hour()` 7-step orchestrator, post-ingest quality checks, anomaly prescreening |
| `clean_fx_fact_ohlc.py` | Cleaning rules (ABC + 5 implementations) and `CleaningRunner` for batch corrections |
| `repository.py` | Data access layer: `FXOHLCRepository` with `bulk_upsert()`, `get_last_close()`, `delete_range()`, `count_by_hour()` |
| `time_utils.py` | `HourWindow` dataclass, `align_to_hour()`, `last_full_utc_hour()`, `iter_hour_windows()` |
| `pipeline.py` | Legacy FX spot rate pipeline (CSV/API); not the main OHLC pipeline |
| `pipeline_ohlc.py` | `FXOHLCPipeline` — thin `BasePipeline` wrapper around `process_hour()` for scheduled audit trail |

### Supporting Modules

| Module | Purpose |
|---|---|
| `src/imdr/universe/fx.py` + `fx.yml` | Universe config: currencies, classifications, series, providers, market hours, expected ranges |
| `src/imdr/healthchecks/quality.py` | Domain-agnostic quality check classes used by post-ingest checks |
| `src/imdr/connectors/reader.py` | `AnalyticalReader` for raw SQL queries (used by quality checks and cleaning) |

---

## Ingest Pipeline

`process_hour()` in `src/imdr/domains/fx/ingest.py` — the core function called by both live and historical scripts.

### 7-Step Flow

| Step | What | Details |
|---|---|---|
| 1. **Extract** | Fetch ticks from BidFX, build OHLC bars | `BidFXExtractor.extract()` — threaded per-series fetching |
| 2. **Validate** | Pydantic validation | Each bar validated against `FXFactOHLCCreate` schema |
| 3. **Missing currencies** | Compare expected vs produced symbols | Logs missing symbols as warning |
| 4. **Anomaly prescreen** | Compare `close_px` to previous hour | Uses `settings.anomaly_pct_threshold`; flags but does NOT drop |
| 5. **Write to MSSQL** | Upsert to `[fx].[fact_ohlc]` | Via `FXOHLCRepository.bulk_upsert()` |
| 6. **Quality checks** | Run 5 post-ingest checks (see below) | Scoped to just-ingested hour; flags stored in audit |
| 7. **Parquet archive** | Write bars to parquet file | Path: `{parquet_batch_dir}/fx/fact_ohlc/{YYYY}/{MM}/{DD}/fx_ohlc_{YYYYMMDD}_{HHMM}.parquet` |

### Anomaly Prescreen (Step 4)

For each bar, fetch previous hour's `close_px` via `FXOHLCRepository.get_last_close()`. If `|pct_change| >= threshold`, flag as anomaly. Bars are flagged but never dropped — principle: flag, don't block.

Threshold configured via `IMDR_ANOMALY_PCT_THRESHOLD` env var (pydantic-settings).

---

## Scripts & CLI

### Live Ingestion — `scripts/fx/bidfx/fx_bidfx_live.py`

Processes a single hour. Designed for scheduled (hourly) execution.

```bash
python -m scripts.fx.bidfx.fx_bidfx_live
python -m scripts.fx.bidfx.fx_bidfx_live --hour 2026-03-09T13:00:00
```

- Checks if FX market is open before running
- Sends email report on completion
- Saves/loads pair availability cache

### Historical Backfill — `scripts/fx/bidfx/fx_bidfx_historical.py`

Batch backfill of multiple hours. Configure by editing variables at the top of the script:

```python
MODE = "range"       # range | catchup | rewrite | gaps
START = "2024-10-16T17:00:00"
END = "2024-10-16T18:00:00"
LOOKBACK_HOURS = 48  # for catchup mode
GAPS_FILE = "data/gaps/gaps.txt"  # for gaps mode
MAX_HOURS = 0        # 0 = unlimited
```

| Mode | Behaviour |
|---|---|
| `range` | Fetch all hours between START and END |
| `catchup` | Fetch last N hours (LOOKBACK_HOURS) |
| `rewrite` | Delete existing data in range, then re-fetch |
| `gaps` | Re-fetch specific hours from a gaps file (one ISO timestamp per line) |

### Data Cleaning — `scripts/fx/clean/clean_fx_fact_ohlc.py`

Detect and correct data quality issues. Dry-run by default.

```bash
python -m scripts.fx.clean.clean_fx_fact_ohlc                           # dry-run, full table
python -m scripts.fx.clean.clean_fx_fact_ohlc --execute                 # apply corrections
python -m scripts.fx.clean.clean_fx_fact_ohlc --year 2026               # filter by year
python -m scripts.fx.clean.clean_fx_fact_ohlc --symbol USDKRW           # filter by symbol
python -m scripts.fx.clean.clean_fx_fact_ohlc --rule robust_outlier     # single rule only
python -m scripts.fx.clean.clean_fx_fact_ohlc --pct-threshold 3.0       # bar-to-bar % threshold
python -m scripts.fx.clean.clean_fx_fact_ohlc --n-mad 5.0               # MAD multiplier
python -m scripts.fx.clean.clean_fx_fact_ohlc --trailing-months 6       # rolling window
python -m scripts.fx.clean.clean_fx_fact_ohlc --emit-gaps data/gaps/cleaning_gaps.txt
```

| Flag | Default | Description |
|---|---|---|
| `--execute` | off | Apply corrections (default is dry-run preview) |
| `--year` | all | Filter to specific year |
| `--symbol` | all | Filter to specific symbol |
| `--rule` | all | Run single rule: `non_positive`, `hard_bound`, `pct_change`, `robust_outlier`, `bid_ask` |
| `--pct-threshold` | 5.0 | Bar-to-bar change threshold % |
| `--n-mad` | 4.0 | MAD multiplier for robust outlier |
| `--trailing-months` | 12 | Rolling window in months |
| `--batch-size` | 500 | UPDATE batch size |
| `--emit-gaps` | off | Write flagged timestamps to file for re-pull |

### Diagnostics Report — `scripts/fx/health/fx_ohlc_report.py`

Comprehensive health/quality report.

```bash
python -m scripts.fx.health.fx_ohlc_report                   # full report
python -m scripts.fx.health.fx_ohlc_report --year 2026       # filter by year
python -m scripts.fx.health.fx_ohlc_report --section health  # single section
python -m scripts.fx.health.fx_ohlc_report --section missing
python -m scripts.fx.health.fx_ohlc_report --section quality --sigma 3
python -m scripts.fx.health.fx_ohlc_report --basis-threshold 5.0
```

**Sections:**
1. **Health** — per-year row counts, null checks, duplicates, freshness
2. **Missing** — per-symbol coverage gaps, market-hours-aware analysis
3. **Quality** — positive values, bid/ask order, symbol ranges, distribution stats, statistical + robust outliers

---

## Data Quality & Outlier Detection

Quality checks run at two stages: **post-ingest** (per hour, as data lands) and **batch cleaning** (periodic sweep of the full table). Principle: **flag, don't block** — data is never rejected at ingest, always stored and flagged.

### Post-Ingest Checks (every hour)

After each hour is written to `[fx].[fact_ohlc]`, five checks run scoped to that hour. Flags are recorded in the audit table's `quality_flags` JSON field.

| # | Check | What it flags |
|---|---|---|
| 1 | **Positive value** | Any of the 9 price columns is non-positive |
| 2 | **Column order** | `bid > ask` |
| 3 | **Percentage change** | `close_px` moved >5% from previous bar (per symbol/series, `LAG()`) |
| 4 | **Symbol range** | `close_px` outside per-symbol hard bounds from `fx.yml` |
| 5 | **Robust statistical outlier** | `close_px` deviates beyond 4 MAD from rolling median |

Implementation: `_build_quality_checks()` in `src/imdr/domains/fx/ingest.py`, using check classes from `src/imdr/healthchecks/quality.py`.

### Robust Outlier Detection (Median + MAD)

Used by both post-ingest checks and batch cleaning. Operates **per (symbol, series)** — e.g. USDTHB SPOT and USDTHB NDF_1M are evaluated independently.

**Parameters:** 4 MAD threshold, 12-month trailing window, minimum 100 observations.

**Algorithm:**

1. **Trailing window (12 months / 360 days):** For each data point, only the preceding 360 calendar days are considered. This lets "normal" adapt over time — if a pair trends from 35 to 30 over a year, the baseline shifts with it.

2. **Rolling median:** The median of `close_px` within the window. Median is robust — even if a fraction of the window contains corrupt values, the center estimate stays accurate. A mean would get dragged by outliers.

3. **MAD (Median Absolute Deviation):** For each value in the window, compute `|value - median|`. Then take the median of those absolute deviations. This gives a spread measure that's also robust to outliers, unlike standard deviation.

4. **Scaled MAD (robust sigma):** `MAD * 1.4826 ~ sigma` for normally distributed data. The constant `1.4826 = 1/inverse_normal_cdf(3/4)` converts MAD to a standard-deviation-equivalent scale.

5. **Robust z-score:** `z = |close_px - rolling_median| / (MAD * 1.4826)`

6. **Flagging threshold:** Rows with `z > 4.0` are flagged. In normal data, 4 sigma is roughly a 1-in-16,000 event.

**Example — USDTHB:** If the 12-month rolling median is ~35 and MAD is ~0.5 (robust sigma ~ 0.74):
- A corrupt value of 23.7 -> z ~ 15.3 -> **flagged**
- A legitimate move to 33.5 -> z ~ 2.0 -> **not flagged**

**Implementations:**
- Post-ingest: `RobustStatisticalOutlierCheck` in `src/imdr/healthchecks/quality.py` (SQL-based, runs on single hour)
- Batch cleaning: `RobustOutlierRule` in `src/imdr/domains/fx/clean_fx_fact_ohlc.py` (pandas-based, runs on full table with rolling window)

### Hard Bounds (safety net)

Per-symbol absolute bounds configured in `src/imdr/universe/fx.yml` under `expected_ranges`. These are deliberately wide "impossible value" guardrails (e.g. USDTHB: 20-60). The robust outlier detection handles real anomaly detection. Hard bounds only catch catastrophically wrong data like negative prices or order-of-magnitude errors.

### Batch Cleaning Rules

The cleaning script runs five rules over the full table:

| Rule | Detection | Correction |
|---|---|---|
| **Non-positive prices** | Any price column <= 0 | NULL all price columns |
| **Hard bound violation** | `close_px` outside per-symbol range | NULL all price columns |
| **Percentage change** | `close_px` moved >5% from previous bar (per symbol/series) | NULL all price columns |
| **Robust outlier** | z > 4 MAD (12-month rolling window) | NULL all price columns |
| **Bid/ask inversion** | `bid > ask` | Swap bid and ask |

Dry-run by default. Use `--execute` to apply, `--emit-gaps <path>` to write flagged timestamps for re-pulling.

---

## Market Hours

Configured in `src/imdr/universe/fx.yml`:

```yaml
market_hours:
  open_day: 6    # Sunday
  open_hour: 21
  close_day: 4   # Friday
  close_hour: 21
```

- **Opens:** Sunday 21:00 UTC
- **Closes:** Friday 21:00 UTC
- **Saturday:** Always closed
- **Sunday before 21:00:** Closed
- **Monday-Thursday:** Always open

Implementation: `FXUniverse.is_fx_open(dt)` in `src/imdr/universe/fx.py`.

---

## Parquet Archive

Approved bars are archived to parquet after DB write:

```
{parquet_batch_dir}/fx/fact_ohlc/{YYYY}/{MM}/{DD}/fx_ohlc_{YYYYMMDD}_{HHMM}.parquet
```

Example: `data/parquet/fx/fact_ohlc/2026/03/10/fx_ohlc_20260310_1300.parquet`

All timestamps (folder hierarchy, filename, `ts` column inside) are **UTC**.

---

## Configuration — `src/imdr/universe/fx.yml`

### Currencies & Classifications

| Classification | Currencies | Series |
|---|---|---|
| **G10** | USD, EUR, GBP, JPY, CHF, AUD, NZD, CAD, NOK, SEK, CNH | SPOT + FORWARD_1M |
| **EM NDF** | INR, KRW, TWD, THB, IDR, PHP | SPOT + NDF_1M |
| **EM Deliverable** | SGD | SPOT + FORWARD_1M |

### Series

| Series | Tenor | Deal Type |
|---|---|---|
| `SPOT` | SPOT | SPOT |
| `FORWARD_1M` | 1M | FORWARD |
| `NDF_1M` | 1M | NDF |

### Providers

- **BidFX** — G10: SPOT + FORWARD_1M; EM NDF: SPOT + NDF_1M; EM Deliverable: SPOT + FORWARD_1M. Auth: basic. API: `https://data.app.bidfx.com/api/price/historical/v1/fx`
- **CitiVelocity** — SPOT only across all classifications. Auth: bearer.

### Expected Ranges (hard bounds)

Per-symbol min/max for `close_px`. Used by both `SymbolRangeCheck` (post-ingest) and `HardBoundViolationRule` (batch cleaning).

```yaml
AUDUSD:  { min: 0.3,     max: 3.0 }
EURUSD:  { min: 0.3,     max: 3.0 }
GBPUSD:  { min: 0.3,     max: 3.0 }
NZDUSD:  { min: 0.3,     max: 3.0 }
USDCAD:  { min: 0.5,     max: 2.5 }
USDCHF:  { min: 0.5,     max: 2.5 }
USDSGD:  { min: 0.5,     max: 2.5 }
USDCNH:  { min: 5.0,     max: 9.0 }
USDJPY:  { min: 60.0,    max: 200.0 }
USDINR:  { min: 50.0,    max: 100.0 }
USDKRW:  { min: 800.0,   max: 1600.0 }
USDNOK:  { min: 5.0,     max: 15.0 }
USDSEK:  { min: 5.0,     max: 15.0 }
USDPHP:  { min: 40.0,    max: 70.0 }
USDTHB:  { min: 20.0,    max: 60.0 }
USDTWD:  { min: 25.0,    max: 40.0 }
USDIDR:  { min: 10000.0, max: 20000.0 }
```

These are wide safety-net bounds. Real anomaly detection is handled by the robust outlier check (median + MAD).

### Pair Convention Priority

```
EUR > GBP > AUD > NZD > USD > CAD > CHF > NOK > SEK > JPY
```

Higher-priority currency is the base. Example: `EURUSD` (not USDEUR), `USDJPY` (not JPYUSD).

---

## FX Vol Domain

### Module Map (`src/imdr/domains/fx/`)

| Module | Purpose |
|---|---|
| `extractors_vol.py` | Citi Velocity vol surface fetching, tag→DataFrame translation |
| `pipeline_vol.py` | `FXVolPipeline` — `BasePipeline` wrapper: extract → transform → load → quality checks |
| `repository_vol.py` | Data access: `FXVolRepository` with `bulk_upsert()`, `count_by_date()` |
| `store_vol.py` | Parquet archive for vol observations |
| `vol_translate.py` | Citi tag ↔ internal schema translation for vol surfaces |
| `clean_fx_fact_vol.py` | 3 cleaning rules for `[fx].[fact_vol]` |

### FX Vol Scripts

| Script | Purpose |
|---|---|
| `scripts/fx/citi/fx_vol_citi_live.py` | Daily EOD vol ingest + email report |
| `scripts/fx/citi/fx_vol_citi_historical.py` | Historical backfill of vol data |
| `scripts/fx/health/fx_vol_report.py` | Diagnostic report (health, coverage, quality) |
| `scripts/fx/clean/clean_fx_fact_vol.py` | Batch cleaning CLI (dry-run default) |

### FX Vol Diagnostics — `scripts/fx/health/fx_vol_report.py`

```bash
python -m scripts.fx.health.fx_vol_report                    # full report
python -m scripts.fx.health.fx_vol_report --year 2026        # filter by year
python -m scripts.fx.health.fx_vol_report --section health   # single section
python -m scripts.fx.health.fx_vol_report --section coverage
python -m scripts.fx.health.fx_vol_report --section quality --sigma 4
```

**Sections:**
1. **Health** — per-year row counts, null checks, duplicates, freshness, value ranges
2. **Coverage** — per-pair date coverage, strike×tenor grid completeness, row counts
3. **Quality** — composite range checks (strike+vol_type bounds), robust outliers, percentage change, distribution

### FX Vol Cleaning — `scripts/fx/clean/clean_fx_fact_vol.py`

```bash
python -m scripts.fx.clean.clean_fx_fact_vol                           # dry-run, full table
python -m scripts.fx.clean.clean_fx_fact_vol --execute                 # apply corrections
python -m scripts.fx.clean.clean_fx_fact_vol --year 2026               # filter by year
python -m scripts.fx.clean.clean_fx_fact_vol --pair 1                  # filter by pair_id
python -m scripts.fx.clean.clean_fx_fact_vol --rule robust_outlier     # single rule
python -m scripts.fx.clean.clean_fx_fact_vol --n-mad 5.0               # MAD multiplier
```

| Rule | Detection | Correction |
|---|---|---|
| **Hard bound violation** | `value` outside per-(strike, vol_type) bounds from `fx.yml` | NULL value |
| **Robust outlier** | z > N MAD (12-month rolling, group by pair_id+strike+tenor) | NULL value |
| **Percentage change** | Day-over-day > threshold (group by pair_id+strike+tenor) | NULL value |

### FX Vol Quality Ranges

Configured in `src/imdr/universe/fx.yml` under `vol.quality.ranges`. Per-(strike, vol_type) bounds:
- **ATM IMPLIED**: 0.5–80.0
- **ATM REALISED**: 0.5–80.0
- **ATM SPREAD**: -40.0–40.0
- **Risk reversals (25RR, 10RR)**: -20.0–20.0
- **Strangles (25STR, 10STR)**: 0.0–20.0
- **Strike calls/puts**: 0.5–100.0

---

## Live vs Historical — Key Differences

| Aspect | Live (`fx_bidfx_live.py`) | Historical (`fx_bidfx_historical.py`) |
|---|---|---|
| **Scope** | Single hour | Multiple hours (batch) |
| **Window** | `last_full_utc_hour()` or `--hour` | Configured via MODE/START/END/LOOKBACK |
| **Market check** | Yes — skip if closed | Yes — skip closed hours in loop |
| **Output** | Per-hour email report | Single summary email for batch |
| **Pair cache** | Load/save per script run | Load once, save after batch |
| **Use case** | Scheduled hourly ingestion | Backfill, catchup, re-pull, gap-fill |
