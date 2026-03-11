# Weekly Data Operations

Personal runbook for weekly data quality maintenance. Run from the project root with the `imdr` conda env active.

---

## All Together

Cross-domain tools that operate on FX OHLC, FX Vol, and Rates in one shot.

### The Cycle

Every week (ideally Monday morning):

| Step | What | Why |
|------|------|-----|
| 1 | **Dashboard email** — automated health + cleaning preview | See coverage gaps, health checks, quality flags across all domains |
| 2 | **Dry-run clean** — detect issues without writing | Understand what the cleaning rules would correct |
| 3 | **Re-pull** — re-ingest flagged data from source | Give the source a second chance before NULLing data |
| 4 | **Re-check** — dry-run again | Confirm what improved and what's still bad |
| 5 | **Execute** — NULL the remaining outliers | Apply corrections to genuinely corrupt rows |

### Quick Reference

```bash
# Step 1: Dashboard email (automated via imdr_weekly.py, or run manually)
python -m scripts.imdr_health_dashboard
python -m scripts.imdr_health_dashboard --no-email    # preview only
python -m scripts.imdr_health_dashboard --year 2026

# Step 2: Dry-run clean — all domains
python -m scripts.imdr_clean
python -m scripts.imdr_clean --year 2026

# Step 3: Re-pull — see domain-specific sections below

# Step 4: Re-check
python -m scripts.imdr_clean --year 2026

# Step 5: Execute — all domains
python -m scripts.imdr_clean --execute
python -m scripts.imdr_clean --execute --year 2026
```

### Automated Dashboard Email

The weekly health dashboard consolidates Steps 1–2 (report + dry-run clean) for **all three domains** into a single HTML email. It runs health checks, coverage analysis, quality checks, and a cleaning dry-run preview for FX OHLC, FX Vol, and Rates.

Registered in `scripts/imdr_weekly.py` — runs automatically via the weekly scheduler.

**Email contents (per domain):**

| Section | What |
|---------|------|
| Health Checks | Rolling 30-day window PASS/FAIL with check-level detail |
| Coverage | Domain-specific coverage tables (symbols, pairs, curves, gaps, grid completeness) |
| Quality Checks | All quality check results with summary DataFrames and top flagged rows |
| Cleaning Dry-Run | Per-rule row counts, unique/overlap analysis, total flagged |

**What to do after reading the email:**
- If health checks **FAIL** — investigate immediately (missing data, stale ingestion, duplicates). Health checks use a 30-day rolling window — a FAIL means recent data has issues, not historical.
- If cleaning flags are high — run Steps 3–5 (re-pull, re-check, execute) per domain below
- If everything passes with low cleaning flags — no action needed
- For per-year historical diagnostics, use the individual report scripts (see domain sections below)

**Module map:**

| File | Purpose |
|------|---------|
| `scripts/imdr_health_dashboard.py` | Thin orchestrator — imports builders from domain scripts, formats, sends |
| `scripts/fx/health/fx_ohlc_report.py` | FX OHLC `build_health_checks()`, `build_quality_checks()` |
| `scripts/fx/clean/clean_fx_fact_ohlc.py` | FX OHLC `build_cleaning_rules()` (defaults from `pipelines.yml`) |
| `scripts/fx/health/fx_vol_report.py` | FX Vol `build_health_checks()`, `build_quality_checks()` |
| `scripts/fx/clean/clean_fx_fact_vol.py` | FX Vol `build_cleaning_rules()` (defaults from `pipelines.yml`) |
| `scripts/rates/health/rates_fact_observation_report.py` | Rates `build_health_checks()`, `build_quality_checks()` |
| `scripts/rates/clean/clean_rates_fact_observation.py` | Rates `build_cleaning_rules()` (defaults from `pipelines.yml`) |
| `src/imdr/config/pipelines.yml` | Single source of truth for cleaning + health check params |
| `src/imdr/healthchecks/reporter.py` | `run_health_window()` (30-day rolling) + `run_health_section()` (per-year) |
| `src/imdr/healthchecks/dashboard.py` | Data model: `CoverageData`, `DomainReport`, `WeeklyDashboard` |
| `src/imdr/notifications/formatters/weekly_dashboard.py` | Formatter + DataFrame→inline-CSS HTML |
| `src/imdr/notifications/templates/weekly_dashboard.html` | Jinja2 template (3 domains × 4 sections) |

### Cross-Domain Cleaning (`imdr_clean`)

Runs each domain's cleaning script in sequence via subprocess, forwarding common flags.

```bash
python -m scripts.imdr_clean                        # dry-run all
python -m scripts.imdr_clean --execute              # execute all
python -m scripts.imdr_clean --year 2026            # scoped dry-run
python -m scripts.imdr_clean --execute --year 2026  # scoped execute
```

Domain-specific flags (`--symbol`, `--pair`, `--curve`) are **not supported** here — use the individual domain scripts for those.

### Robust Outlier Tuning

**Defaults** (from `pipelines.yml` → `fx.ohlc.cleaning`): `n_mad: 6.0`, `trailing_months: 3`. Calibrated via a parameter sweep across 1- and 3-month windows with MAD thresholds 3–8. The 3-month/6-MAD combination flags ~5,400 rows (0.50% of FX OHLC data), concentrated in genuinely noisy 2021–22 data, with zero false positives in 2023+ clean periods. The previous 1-month/4-MAD defaults flagged ~15,400 rows (1.43%) — most of which were legitimate regime shifts rather than data errors.

**Interpreting z-scores:**
- z > 20: clearly bad data — NULL without hesitation
- z 8–20: suspicious — review before executing
- z 4–8: likely real market moves — leave alone at default threshold

### Cleaning Idempotency & Cascading Prevention

Running `imdr_clean --execute` and then re-running a dry-run should produce **zero new flags**. Three mechanisms ensure this:

#### 1. pct_change NULL chain-breakers (2026-03-11)

**Problem**: After NULLing a bad row, `LAG()` in the pct_change rule skipped the NULL'd row and compared across the gap. A normal 2-hour drift between hours 10 and 12 (skipping NULL'd hour 11) looked like a spike → false positive.

**Fix**: Removed `WHERE [value] IS NOT NULL` from the inner CTE of `PercentageChangeRule.detect()`. NULL rows stay in the `LAG()` window. When `LAG()` returns NULL (from a cleaned neighbor), `WHERE prev_val IS NOT NULL` in the outer query skips that row. The NULL acts as a natural chain-breaker.

Applied to all 3 domains:
- `src/imdr/domains/fx/clean_fx_fact_ohlc.py` — `PercentageChangeRule`
- `src/imdr/domains/fx/clean_fx_fact_vol.py` — `PercentageChangeRule`
- `src/imdr/domains/rates/clean_rates_fact_observation.py` — `PercentageChangeRule`

#### 2. Snapshot-based execution (2026-03-11)

**Problem**: `CleaningRunner.run()` ran detect→execute for each rule sequentially. Later rules saw a modified database (with NULLs from earlier rules), causing intra-run cascading.

**Fix**: Refactored `CleaningRunner.run()` in `src/imdr/healthchecks/cleaning.py` to detect-all-then-apply-all. Phase 1 detects all rules on unmodified data. Phase 2 applies all corrections at once. All rules see the original snapshot.

#### 3. Interpolation-stabilized robust outlier detection (2026-03-11)

**Problem**: After NULLing extreme outliers, the rolling median/MAD distribution tightened (fewer points, less variance). Previously-borderline values then exceeded the new threshold → progressive data erosion on each re-run.

**Root cause**: `rolling().median()` skips NaN. Whether NULL'd rows are excluded from the DataFrame or included as NaN, the rolling stats are computed on the same non-NaN values — and the distribution shifts either way.

**Why naive approaches don't work**:
- Including NULLs as NaN: `rolling().median()` skips NaN → same stats as excluding them
- Re-running until convergence: each pass tightens the distribution, eroding legitimate market moves
- Wider thresholds: delays the problem but doesn't fix it

**Fix**: Interpolate NaN values for stats computation only. The `RobustOutlierRule.detect()` method now:
1. Fetches all rows including NULLs (`WHERE 1=1` instead of `WHERE [value] IS NOT NULL`)
2. Creates an interpolated copy: `vals_for_stats = vals.interpolate(method="time")`
3. Computes rolling median/MAD on the interpolated series (complete, stable time series)
4. Computes robust_z using **original** values against the interpolated stats
5. Flags only rows where `robust_z > threshold AND value is not NaN`

**Why this works**:
- **Stable stats**: Interpolated values fill NULL gaps with time-weighted linear estimates between neighbors. A NULL'd outlier at 200 between values 101 and 103 gets interpolated to ~102 — a neutral fill that doesn't distort the median or MAD.
- **Idempotent**: After cleaning, re-running produces the same NaN pattern → same interpolated values → same rolling stats → same flags (already NULL'd) → zero new flags.
- **No schema changes**: Pure computation change in the detect() method.

Applied to all 3 domains:
- `src/imdr/domains/fx/clean_fx_fact_ohlc.py` — `RobustOutlierRule`
- `src/imdr/domains/fx/clean_fx_fact_vol.py` — `RobustOutlierRule`
- `src/imdr/domains/rates/clean_rates_fact_observation.py` — `RobustOutlierRule`

---

## FX OHLC Domain

For full architecture, see `docs/admin/fx/overview.md`.

### Report

```bash
python -m scripts.fx.health.fx_ohlc_report
python -m scripts.fx.health.fx_ohlc_report --year 2026
python -m scripts.fx.health.fx_ohlc_report --section health
python -m scripts.fx.health.fx_ohlc_report --section missing
python -m scripts.fx.health.fx_ohlc_report --section quality --sigma 3  # override config
```

**What to look for:**
- Health checks: any FAIL results (null counts, row counts off)
- Missing data: symbols with low coverage % or large gaps
- Quality: outlier counts per symbol — a few is normal, hundreds means something upstream broke

### Clean

```bash
python -m scripts.fx.clean.clean_fx_fact_ohlc
python -m scripts.fx.clean.clean_fx_fact_ohlc --year 2026
python -m scripts.fx.clean.clean_fx_fact_ohlc --symbol USDKRW
python -m scripts.fx.clean.clean_fx_fact_ohlc --rule hard_bound
python -m scripts.fx.clean.clean_fx_fact_ohlc --n-mad 8.0 --trailing-months 6
python -m scripts.fx.clean.clean_fx_fact_ohlc --execute --year 2026
```

**What to look for:**
- `non_positive`: should be near zero — these are clearly broken
- `hard_bound`: check the `pct_change` in the output — a +400% jump is corruption, a -2% drift near the boundary might be real
- `robust_outlier`: should be in the low thousands across all years — if it's >10k, the rolling window params may need tuning
- `bid_ask`: minor inversions (bid barely > ask) are common in EM NDFs — large inversions are suspect

### Re-Pull

Generate a gaps file from the dry run:

```bash
python -m scripts.fx.clean.clean_fx_fact_ohlc --emit-gaps data/gaps/cleaning_gaps.txt
```

Then edit `scripts/fx/bidfx/fx_bidfx_historical.py`:

```python
MODE = "gaps"
GAPS_FILE = "data/gaps/cleaning_gaps.txt"
```

Run the backfiller:

```bash
python -m scripts.fx.bidfx.fx_bidfx_historical
```

This re-fetches ticks from BidFX for each flagged hour and upserts fresh bars. If the source data was transiently bad, this often fixes it.

**Alternative — re-pull a specific hour manually:**

```bash
python -m scripts.run_pipeline fx.ohlc --hour 2026-03-09T13:00:00
```

### Cleaning Rules

| Rule | What it detects | Action | Severity |
|------|----------------|--------|----------|
| `non_positive` | Any price column <= 0 | NULL all prices | Always corrupt |
| `hard_bound` | `close_px` outside per-symbol hard bounds (from `fx.yml`) | NULL all prices | Check `pct_change` — sudden jumps are corrupt, gradual drift near boundary may be real |
| `pct_change` | `close_px` moved >5% from previous bar (per symbol+series) | NULL all prices | NULL chain-breaker: NULL'd neighbors cause `LAG()` to return NULL → skip, no false cascade |
| `robust_outlier` | `close_px` deviates > N MADs from rolling median (per symbol+series) | NULL all prices | Default: 3-month/6 MAD. Interpolation-stabilized: NULL'd rows filled with time-weighted interpolation for stats only → idempotent across runs |
| `bid_ask` | `bid > ask` | Swap bid and ask | Common in EM NDFs, usually minor |

### Quick Reference

```bash
python -m scripts.fx.health.fx_ohlc_report --year 2026
python -m scripts.fx.clean.clean_fx_fact_ohlc --year 2026
python -m scripts.fx.clean.clean_fx_fact_ohlc --year 2026 --emit-gaps data/gaps/cleaning_gaps.txt
# edit fx/bidfx/fx_bidfx_historical.py → MODE="gaps", GAPS_FILE="data/gaps/cleaning_gaps.txt"
python -m scripts.fx.bidfx.fx_bidfx_historical
python -m scripts.fx.health.fx_ohlc_report --year 2026
python -m scripts.fx.clean.clean_fx_fact_ohlc --year 2026
python -m scripts.fx.clean.clean_fx_fact_ohlc --year 2026 --execute
```

---

## FX Vol Domain

For full architecture, see `docs/admin/fx/overview.md` (FX Vol section).

### Report

```bash
python -m scripts.fx.health.fx_vol_report --year 2026
python -m scripts.fx.health.fx_vol_report --section coverage
python -m scripts.fx.health.fx_vol_report --section quality --sigma 3  # override config
```

**What to look for:**
- Health checks: any FAIL results (null counts, row counts off)
- Coverage: pairs with fewer dates than expected, incomplete strike×tenor grids
- Quality: outlier counts per pair — a few is normal, hundreds means upstream data issue

### Clean

```bash
python -m scripts.fx.clean.clean_fx_fact_vol
python -m scripts.fx.clean.clean_fx_fact_vol --year 2026
python -m scripts.fx.clean.clean_fx_fact_vol --pair 1
python -m scripts.fx.clean.clean_fx_fact_vol --rule hard_bound
python -m scripts.fx.clean.clean_fx_fact_vol --execute --year 2026
```

**What to look for:**
- `hard_bound`: values outside per-(strike, vol_type) bounds from `fx.yml`
- `robust_outlier`: should be in the low thousands or less — if huge, check trailing window params
- `pct_change`: day-over-day jumps (threshold 30% by default — vol is naturally more volatile)

### Re-Pull

Re-run historical backfill for specific dates in `scripts/fx/citi/fx_vol_citi_historical.py`.

### Cleaning Rules

| Rule | What it detects | Action | Severity |
|------|----------------|--------|----------|
| `hard_bound` | `value` outside per-(strike, vol_type) bounds | NULL value | Check vol_type — ATM IMPLIED has wider range than risk reversals |
| `robust_outlier` | z > N MAD (rolling, per pair_id+strike+tenor+vol_type) | NULL value | Groups by vol_type to avoid mixing IMPLIED/SPREAD/REALISED. Interpolation-stabilized for idempotency |
| `pct_change` | Day-over-day move > 30% (per pair_id+strike+tenor+vol_type) | NULL value | Vol is volatile — threshold higher than FX spot. Partitions by vol_type. NULL chain-breaker prevents cascade |

### Quick Reference

```bash
python -m scripts.fx.health.fx_vol_report --year 2026
python -m scripts.fx.clean.clean_fx_fact_vol --year 2026
# Re-pull if needed via fx_vol_citi_historical.py
python -m scripts.fx.health.fx_vol_report --year 2026
python -m scripts.fx.clean.clean_fx_fact_vol --year 2026
python -m scripts.fx.clean.clean_fx_fact_vol --year 2026 --execute
```

---

## Rates Domain

For full architecture, see `docs/admin/rates/overview.md`.

### Report

```bash
python -m scripts.rates.health.rates_fact_observation_report --year 2026
python -m scripts.rates.health.rates_fact_observation_report --section coverage
python -m scripts.rates.health.rates_fact_observation_report --section quality --sigma 3  # override config
```

**What to look for:**
- Health checks: any FAIL results (row counts, nulls, freshness)
- Coverage: curves with fewer dates than expected, missing quote types or tenors
- Quality: per-quote-type range violations, outlier counts per curve

### Clean

```bash
python -m scripts.rates.clean.clean_rates_fact_observation
python -m scripts.rates.clean.clean_rates_fact_observation --year 2026
python -m scripts.rates.clean.clean_rates_fact_observation --curve 1 --quote par
python -m scripts.rates.clean.clean_rates_fact_observation --rule hard_bound
python -m scripts.rates.clean.clean_rates_fact_observation --execute --year 2026
```

**What to look for:**
- `hard_bound`: values outside per-quote-type bounds (par: -3 to 20, spread: -500 to 500, etc.)
- `robust_outlier`: should be a small number — check if specific curves dominate
- `pct_change`: observation-over-observation jumps (tune with `--pct-threshold`)

### Re-Pull

```bash
# Single date
python -m scripts.run_pipeline rates.historical --start 2026-03-05 --end 2026-03-05 --quotes par

# Date range, all quote types
python -m scripts.run_pipeline rates.historical --start 2026-03-03 --end 2026-03-07 --quotes par,spread,fwd,bfly,ssw,rc
```

Upsert is idempotent — safe to re-run dates that already have data.

### Cleaning Rules

| Rule | What it detects | Action | Severity |
|------|----------------|--------|----------|
| `hard_bound` | `value` outside per-quote-type bounds from `rates.yml` | NULL value | Check quote type — spread/ssw have wider ranges than par |
| `robust_outlier` | z > N MAD (12-month rolling, per curve_id+quote+tenor) | NULL value | Rolling window adapts. Interpolation-stabilized for idempotency; check which curves dominate |
| `pct_change` | Observation-over-observation move > threshold | NULL value | NULL chain-breaker prevents cascade. Rates can have large moves during central bank events — review before executing |

### Quick Reference

```bash
python -m scripts.rates.health.rates_fact_observation_report --year 2026
python -m scripts.rates.clean.clean_rates_fact_observation --year 2026
# Re-pull any gap dates:
python -m scripts.run_pipeline rates.historical --start YYYY-MM-DD --end YYYY-MM-DD --quotes par
python -m scripts.rates.health.rates_fact_observation_report --year 2026
python -m scripts.rates.clean.clean_rates_fact_observation --year 2026
python -m scripts.rates.clean.clean_rates_fact_observation --year 2026 --execute
```

---

## Scripts Map

### Top-Level Orchestrators (`scripts/`)

| Script | Purpose | Scheduling |
|--------|---------|------------|
| `imdr_hourly.py` | Runs hourly pipelines (FX OHLC from BidFX) | Task Scheduler |
| `imdr_daily.py` | Runs daily pipelines (Rates from Citi, FX Vol from Citi) | Task Scheduler |
| `imdr_weekly.py` | Runs weekly pipelines (health dashboard email) | Task Scheduler |
| `imdr_monthly.py` | (empty — template for future monthly jobs) | — |
| `imdr_quarterly.py` | (empty — template for future quarterly jobs) | — |
| `imdr_clean.py` | Cross-domain cleaning dry-run/execute | Manual |
| `imdr_health_dashboard.py` | Consolidated health/coverage/quality email for all domains | Via `imdr_weekly.py` |
| `run_pipeline.py` | Generic pipeline runner (4 registered: `fx.spot_rates`, `fx.ohlc`, `fx.vol`, `rates.historical`) | Manual / ad-hoc |

### FX Domain (`scripts/fx/`)

| Script | Purpose | Scheduling |
|--------|---------|------------|
| `fx/bidfx/fx_bidfx_live.py` | Hourly FX OHLC ingest from BidFX | Via `imdr_hourly.py` |
| `fx/bidfx/fx_bidfx_historical.py` | Backfill FX OHLC (range, catchup, rewrite, gaps modes) | Manual |
| `fx/citi/fx_vol_citi_live.py` | Daily EOD FX vol ingest from Citi Velocity | Via `imdr_daily.py` |
| `fx/citi/fx_vol_citi_historical.py` | Backfill FX vol | Manual |
| `fx/citi/fx_citivelocity_live.py` | Legacy spot rates from Citi (deprecated) | — |
| `fx/citi/fx_citivelocity_historical.py` | Legacy spot rates backfill (deprecated) | — |
| `fx/clean/clean_fx_fact_ohlc.py` | FX OHLC cleaning (5 rules) | Manual / via `imdr_clean.py` |
| `fx/clean/clean_fx_fact_vol.py` | FX Vol cleaning (3 rules) | Manual / via `imdr_clean.py` |
| `fx/health/fx_ohlc_report.py` | FX OHLC diagnostic report (health, coverage, quality) | Manual |
| `fx/health/fx_vol_report.py` | FX Vol diagnostic report | Manual |

### Rates Domain (`scripts/rates/`)

| Script | Purpose | Scheduling |
|--------|---------|------------|
| `rates/citi/rates_citi_live.py` | Daily EOD rates ingest from Citi Velocity | Via `imdr_daily.py` |
| `rates/citi/rates_citi_historical.py` | Backfill rates (date range, quote types) | Manual |
| `rates/clean/clean_rates_fact_observation.py` | Rates cleaning (3 rules) | Manual / via `imdr_clean.py` |
| `rates/health/rates_fact_observation_report.py` | Rates diagnostic report | Manual |

### Exploration (`scripts/explore/`) — one-time, cached, DO NOT re-run

| Script | Purpose |
|--------|---------|
| `explore/explore_rates_categories.py` | Citi Velocity rates catalog discovery |
| `explore/explore_fx_vol.py` | Citi Velocity FX vol surface discovery |
| `explore/explore_other_categories.py` | Citi Velocity FX/equity/commodities discovery |

### Migrations (`scripts/migrations/`) — one-time

| Script | Purpose |
|--------|---------|
| `migrations/convert_fx_fact_ohlc_parquet.py` | Convert legacy parquet to canonical format |
| `migrations/load_fx_fact_ohlc.py` | Load converted parquet into DB |
| `migrations/seed_rates_dim_curve.py` | Seed `dim_curve` (now automated in pipeline) |
