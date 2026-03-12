# Data Cleaning Framework

Technical reference for the IMDR cleaning system — architecture, rules, cascading prevention, and the statistical reasoning behind each design decision.

---

## Architecture Overview

```
scripts/imdr_clean.py                  # Cross-domain orchestrator
  ├── scripts/fx/clean/clean_fx_fact_ohlc.py      # FX OHLC (5 rules)
  ├── scripts/fx/clean/clean_fx_fact_vol.py        # FX Vol  (3 rules)
  └── scripts/rates/clean/clean_rates_fact_observation.py  # Rates (3 rules)

src/imdr/healthchecks/cleaning.py      # Shared infrastructure
  ├── CleaningRule (ABC)               # detect() + build_update_sql() + build_action()
  ├── CleaningRunner                   # Orchestrator: snapshot detect-all → apply-all
  ├── CleaningAction                   # Single row correction (proposed or applied)
  └── CleaningResult                   # Aggregate result per rule

src/imdr/domains/fx/clean_fx_fact_ohlc.py          # FX OHLC rule implementations
src/imdr/domains/fx/clean_fx_fact_vol.py            # FX Vol rule implementations
src/imdr/domains/rates/clean_rates_fact_observation.py  # Rates rule implementations
```

### Design Principles

1. **Flag, don't block** — cleaning runs post-ingest. Data is never rejected at ingest time.
2. **NULL, don't delete** — bad values are set to NULL, preserving the row and its metadata (timestamps, keys). This is critical for the interpolation-stabilized outlier detection.
3. **Idempotent** — running cleaning N times produces the same result as running it once. No cascading, no data erosion.
4. **Dry-run by default** — every cleaning script defaults to reporting what it *would* change without writing. Requires explicit `--execute` to apply.
5. **Domain-agnostic runner** — `CleaningRunner` doesn't know about FX or Rates. Each domain implements its own `CleaningRule` subclasses.

---

## Rule Catalog

### FX OHLC (`[fx].[fact_ohlc]`)

| Rule | Class | Action | Value Column | Partition |
|------|-------|--------|-------------|-----------|
| `non_positive` | `NonPositivePriceRule` | NULL all price columns | all 9 price cols | — |
| `hard_bound` | `HardBoundViolationRule` | NULL all price columns | `close_px` | `symbol` |
| `pct_change` | `PercentageChangeRule` | NULL all price columns | `close_px` | `symbol, series` |
| `robust_outlier` | `RobustOutlierRule` | NULL all price columns | `close_px` | `symbol, series` |
| `bid_ask` | `BidAskInversionRule` | Swap bid and ask | `bid, ask` | — |

**Defaults** (from `pipelines.yml` → `fx.ohlc.cleaning`): `n_mad: 6.0`, `trailing_months: 3`, `pct_threshold: 5.0`, `--min-obs 100`

### FX Vol (`[fx].[fact_vol]`)

| Rule | Class | Action | Value Column | Partition |
|------|-------|--------|-------------|-----------|
| `hard_bound` | `HardBoundViolationRule` | NULL value | `value` | `strike, vol_type` |
| `robust_outlier` | `RobustOutlierRule` | NULL value | `value` | `pair_id, strike, tenor, vol_type` |
| `pct_change` | `PercentageChangeRule` | NULL value | `value` | `pair_id, strike, tenor, vol_type` |

**Defaults** (from `pipelines.yml` → `fx.vol.cleaning`): `n_mad: 4.0`, `trailing_months: 12`, `pct_threshold: 30.0` (fallback), `--min-obs 30`

**FX Vol `pct_change` uses 3-tier filtering** (2026-03-12):

| Tier | Scope | Logic | Config |
|------|-------|-------|--------|
| 1 — Absolute change | Signed/small strikes (25RR, 10RR, 25STR, 10STR) | Uses absolute vol-point thresholds (2.0, 3.0, 1.0, 2.0 respectively) instead of percentage change | Hardcoded in rule |
| 2 — Class×tenor pct | ccy_class × tenor matrix | Different pct thresholds per combination (e.g., G10 1W: 75%, G10 10Y: 15%, EM NDF 1W: 100%) | `fx.yml` → `vol.quality.pct_thresholds` |
| 3 — Fallback pct | Any unmapped class×tenor combo | `pct_threshold: 30.0` from `pipelines.yml` | `pipelines.yml` → `fx.vol.cleaning` |

Additional: `min_abs_prev=0.5` skips rows where the previous value is near zero (avoids division blow-up on ATM SPREAD). The rule JOINs `[fx].[dim_currency_pair]` to resolve `ccy_class`.

**Note**: The generic `PercentageChangeCheck` in `quality.py` (used by pipeline post-ingest quality checks) applies `min_abs_value=0.5` but does NOT implement the full class×tenor logic — it is diagnostic, not cleaning.

**Critical**: `vol_type` must be in the partition for both `robust_outlier` and `pct_change`. Without it, IMPLIED (~6-10), SPREAD (~-0.14), and REALISED values are mixed, causing hundreds of false flags. This was a bug found 2026-03-11.

### Rates (`[rates].[fact_observation]`)

| Rule | Class | Action | Value Column | Partition |
|------|-------|--------|-------------|-----------|
| `hard_bound` | `HardBoundViolationRule` | NULL value | `value` | `quote` |
| `robust_outlier` | `RobustOutlierRule` | NULL value | `value` | `curve_id, quote, tenor` |
| `pct_change` | `PercentageChangeRule` | NULL value | `value` | `curve_id, quote, tenor` |

**Defaults** (from `pipelines.yml` → `rates.historical.cleaning`): `n_mad: 4.0`, `trailing_months: 12`, `pct_threshold: 30.0`, `--min-obs 30`

---

## Cascading Prevention

The core challenge: cleaning modifies the data that subsequent cleaning rules (or re-runs of the same rules) operate on. Without careful design, this creates cascading false positives — where fixing one problem creates another.

Three separate mechanisms prevent three distinct cascading pathways.

### Problem 1: pct_change LAG() Gap Comparison

**Scenario**: Hour 11 value is NULL'd by hard_bound rule. On re-run, the pct_change rule's `LAG()` window function skips the NULL'd row (because the CTE had `WHERE close_px IS NOT NULL`). It now compares hour 12 directly to hour 10, skipping the gap. A normal 2-hour drift of 0.3% looks like a 0.6% jump when compressed into one step — potentially exceeding the threshold.

**Example (FX OHLC, USDJPY, hourly bars)**:
```
Hour 10: close_px = 150.20
Hour 11: close_px = NULL  (cleaned by hard_bound)
Hour 12: close_px = 150.50
```

With `WHERE close_px IS NOT NULL` in CTE:
- `LAG()` for hour 12 returns 150.20 (hour 10)
- pct_change = (150.50 - 150.20) / 150.20 × 100 = 0.20%
- With enough of these, some will exceed the 5% threshold — false positive

Without the filter (fixed version):
- `LAG()` for hour 12 returns NULL (hour 11's value)
- `WHERE prev_val IS NOT NULL` in outer query skips this row
- No comparison, no false positive

**Fix**: Removed `WHERE [value] IS NOT NULL` from the inner CTE of `PercentageChangeRule.detect()`. NULL rows stay in the `LAG()` window and act as **chain-breakers** — they terminate the comparison chain. The outer query filters: `WHERE [value] IS NOT NULL AND prev_val IS NOT NULL`.

**Why chain-breaking is correct**: If the previous value was bad enough to NULL, we have no reliable baseline for percentage comparison. Skipping is safer than comparing across an unknown gap.

**Files changed**:
- `src/imdr/domains/fx/clean_fx_fact_ohlc.py` — `PercentageChangeRule.detect()` inner CTE
- `src/imdr/domains/fx/clean_fx_fact_vol.py` — `PercentageChangeRule.detect()` inner CTE
- `src/imdr/domains/rates/clean_rates_fact_observation.py` — `PercentageChangeRule.detect()` inner CTE

### Problem 2: Intra-Run Rule Ordering

**Scenario**: `CleaningRunner` runs rules sequentially: detect rule A → execute rule A → detect rule B → execute rule B. Rule B sees the database *after* rule A has already written NULLs. Rule B's detection is contaminated by rule A's modifications.

**Example**: hard_bound NULLs 50 rows. robust_outlier then runs on the modified data — with 50 fewer data points, the rolling statistics shift, and borderline values get newly flagged.

**Fix**: Refactored `CleaningRunner.run()` to **snapshot-based execution**:

```
Phase 1 (detect): For each rule, run detect() on the UNMODIFIED database. Store results.
Phase 2 (apply):  For each rule, apply corrections in batch.
```

All rules see the same original data. No rule's detection is influenced by another rule's corrections.

**File changed**: `src/imdr/healthchecks/cleaning.py` — `CleaningRunner.run()`

### Problem 3: Cross-Run Robust Outlier Distribution Shift

This is the most subtle and important problem. The first two fixes handle pct_change gaps and intra-run ordering. But even with those fixes, running `imdr_clean --execute` and then re-running a dry-run would still show **new** robust_outlier flags.

**Root cause**: The rolling median + MAD computation operates on the current data. After NULLing extreme outliers, the distribution of remaining values is tighter (lower variance). The MAD shrinks, the threshold (n_mad × MAD × 1.4826) shrinks, and previously-borderline values now exceed it.

**Concrete example**:

```
Original window (3-month rolling):
  Values: [100, 101, 99, 200, 102, 98, 100, 101, 103, 115, ...]
  Median: ~101
  Deviations from median: [1, 0, 2, 99, 1, 3, 1, 0, 2, 14, ...]
  MAD: ~2
  Robust sigma: 2 × 1.4826 = 2.97
  Threshold at 6 MAD: 6 × 2.97 = 17.8
  → 200 flagged (z = 99/2.97 = 33.3), 115 NOT flagged (z = 14/2.97 = 4.7)

After cleaning (200 → NULL, excluded from rolling window):
  Values: [100, 101, 99, 102, 98, 100, 101, 103, 115, ...]
  Median: ~101
  Deviations: [1, 0, 2, 1, 3, 1, 0, 2, 14, ...]
  MAD: ~1
  Robust sigma: 1 × 1.4826 = 1.48
  Threshold at 6 MAD: 6 × 1.48 = 8.9
  → 115 NOW flagged (z = 14/1.48 = 9.5) ← NEW FALSE POSITIVE
```

The value 115 is a legitimate market move that was "masked" by the extreme outlier (200) inflating the MAD. After removing 200, the MAD contracts and 115 looks extreme. Each pass erodes more data.

**Why naive approaches fail**:

| Approach | Why it doesn't work |
|----------|-------------------|
| Include NULLs as NaN in DataFrame | `rolling().median()` skips NaN → same stats as excluding NULLs entirely |
| Re-run until convergence | Each pass tightens the distribution; borderline legitimate values get progressively wiped out |
| Wider MAD threshold | Delays the problem by a pass or two; doesn't eliminate it |
| Skip robust_outlier on re-runs | Loses the ability to detect new actual outliers from fresh data |

**Fix: Interpolation-stabilized stats computation**

The key insight: we need the rolling window to see a **complete time series** regardless of how many values have been cleaned. Instead of skipping NaN or excluding NULLs, we interpolate them with sensible estimates.

```python
# 1. Fetch ALL rows including NULLs (SQL: WHERE 1=1 instead of WHERE value IS NOT NULL)
# 2. Convert to float — NULLs become NaN
vals = grp[value_col].astype(float)

# 3. Interpolate NaN for stats computation only
vals_for_stats = vals.interpolate(method="time")

# 4. Compute rolling stats on the INTERPOLATED series
roll_median = vals_for_stats.rolling(window, min_periods=min_obs).median()
abs_dev = (vals_for_stats - roll_median).abs()
roll_mad = abs_dev.rolling(window, min_periods=min_obs).median()
robust_sigma = roll_mad * 1.4826

# 5. Flag using ORIGINAL values against interpolated stats
robust_z = (vals - roll_median).abs() / robust_sigma.replace(0, float("nan"))
mask = (robust_z > n_mad) & vals.notna()
```

**How `interpolate(method="time")` works**: For each NaN, pandas linearly interpolates between the nearest non-NaN neighbors, weighted by their timestamps. If hour 11 (value NULL'd) sits between hour 10 (150.20) and hour 12 (150.50), the interpolated value is ~150.35.

**Why this makes cleaning idempotent**:

1. **Before cleaning**: No NaN values. `vals_for_stats == vals`. Rolling stats computed on raw data. Outliers flagged.
2. **After cleaning** (outliers NULL'd): NaN values at cleaned positions. `vals_for_stats` has interpolated values at those positions — typically very close to the rolling median (since interpolation blends neighbors). Rolling median barely changes. Rolling MAD barely changes. Same threshold → same flags. But the flagged rows are already NULL → `vals.notna()` filter skips them → zero new flags.

**Why interpolated values don't distort stats**: A NULL'd outlier at 200 between neighbors 101 and 103 gets interpolated to ~102. This value:
- Is very close to the median (~101) → deviation ≈ 1 → neutral contribution to MAD
- Does not inflate or deflate the rolling statistics
- Effectively acts as if the outlier "never existed" in the distribution — which is exactly what we want

**Edge cases**:
- **Leading NaNs** (start of series): `interpolate(method="time")` cannot extrapolate → stays NaN → `min_periods` handles this naturally
- **Consecutive NaNs**: Interpolation bridges across multiple NaN gaps → produces a smooth gradient between neighbors
- **All NaN in group**: `interpolate()` returns all NaN → `rolling().median()` returns NaN → no flags → correct behavior

**Files changed**:
- `src/imdr/domains/fx/clean_fx_fact_ohlc.py` — `RobustOutlierRule.detect()`
- `src/imdr/domains/fx/clean_fx_fact_vol.py` — `RobustOutlierRule.detect()`
- `src/imdr/domains/rates/clean_rates_fact_observation.py` — `RobustOutlierRule.detect()`

---

## Robust Outlier Detection — Statistical Background

### The Estimator: Median + MAD

The robust outlier rule uses rolling **median** and **Median Absolute Deviation (MAD)** rather than mean and standard deviation. Why:

| Property | Mean + StdDev | Median + MAD |
|----------|--------------|-------------|
| Breakdown point | 0% (one extreme value corrupts both) | 50% (up to half the data can be corrupted) |
| Influence of outliers | Unbounded (a single extreme point pulls the mean arbitrarily) | Zero (outliers don't affect the median or MAD) |
| Efficiency (normal data) | 100% | ~37% (trades efficiency for robustness) |
| Appropriate for | Clean, known-distribution data | Contaminated data, unknown distribution |

For market data with potential corruption, the median + MAD is the correct choice. We accept the lower statistical efficiency because our data has an unknown contamination rate.

### MAD Scale Factor (1.4826)

The MAD is scaled by 1.4826 to make it comparable to standard deviation under a normal distribution:

```
σ ≈ 1.4826 × MAD
```

This means "6 MAD" is roughly equivalent to "6 sigma" for normally-distributed data, making the threshold intuitive.

### Rolling Window Parameters

These values are stored in `pipelines.yml` under each pipeline's `cleaning:` section.

| Parameter | FX OHLC | FX Vol / Rates | Rationale |
|-----------|---------|---------------|-----------|
| `trailing_months` | 3 | 12 | FX spot has regime shifts every few months; vol/rates are more stable |
| `n_mad` | 6.0 | 4.0 | FX spot is noisier (hourly bars); vol/rates are daily and smoother |
| `min_obs` | 100 | 30 | FX spot has ~720 bars/month; vol/rates have ~22 obs/month |
| `min_obs` | 100 | 30 | FX spot has ~720 bars/month; vol/rates have ~22 obs/month |

**Tuning history** (FX OHLC, 2026-03-11):

| Window | MAD | Flagged rows | % of data | Notes |
|--------|-----|-------------|-----------|-------|
| 1 month | 4 | 15,407 | 1.43% | Over-flagging: regime shifts treated as outliers |
| 1 month | 6 | 8,234 | 0.77% | Still high |
| 3 month | 4 | 8,891 | 0.83% | Better, but still catching real moves |
| 3 month | 6 | 5,365 | 0.50% | Sweet spot: concentrated in noisy 2021-22, clean 2023+ |
| 3 month | 8 | 3,012 | 0.28% | Too lenient: misses some genuine corruption |

Selected: **3-month window, 6 MAD** — flags ~0.50% of FX OHLC data.

---

## FX Vol: vol_type Partitioning Bug (2026-03-11)

### Bug

Both `RobustOutlierRule` and `PercentageChangeRule` in `clean_fx_fact_vol.py` originally partitioned by `[pair_id, strike, tenor]` — missing `vol_type`. This mixed three fundamentally different value scales:

| vol_type | Typical range | Example |
|----------|--------------|---------|
| IMPLIED | 5–15 | ATM implied vol for EURUSD |
| REALISED | 5–15 | Realised vol |
| SPREAD | -1 to +1 | Implied minus realised |

Computing a rolling median across these mixed scales is nonsensical. SPREAD values near -0.14 look like extreme outliers relative to IMPLIED values near 8.0 → 315 false flags on a dataset with only 1,530 rows.

### Fix

Added `vol_type` to both:
- `RobustOutlierRule`: `group_cols = ["pair_id", "strike", "tenor", "vol_type"]`
- `PercentageChangeRule`: `PARTITION BY [pair_id], [strike], [tenor], [vol_type]`

After fix: zero false flags on the 1,530-row dataset.

---

## Execution Flow

### Single-Domain Cleaning

```
CLI script (e.g., clean_fx_fact_ohlc.py)
  │
  ├── Parse args (--execute, --year, --symbol, --rule, --n-mad, etc.)
  ├── Build rule instances with domain-specific config
  ├── Build WHERE clause from filters
  ├── Create CleaningRunner(connector, reader, rules, table, dry_run)
  │
  └── runner.run(where, params)
        │
        ├── Phase 1: DETECT (all rules, unmodified data)
        │     for each rule:
        │       rule.detect(reader, table, where, params) → DataFrame
        │       for each row: rule.build_action(row) → CleaningAction
        │       → CleaningResult(actions=[...])
        │
        └── Phase 2: APPLY (if --execute)
              for each rule with actions:
                ids = [action.row_id for action in result.actions]
                _execute_batches(rule, ids)
                  → rule.build_update_sql(batch_of_ids)
                  → session.execute(sql)  # batched in groups of 500
```

### Cross-Domain Cleaning (`imdr_clean`)

```
scripts/imdr_clean.py
  │
  ├── Forward CLI args (--execute, --year) to each sub-script
  │
  ├── subprocess: python -m scripts.fx.clean.clean_fx_fact_ohlc [args]
  ├── subprocess: python -m scripts.fx.clean.clean_fx_fact_vol [args]
  └── subprocess: python -m scripts.rates.clean.clean_rates_fact_observation [args]
```

Each domain runs in its own subprocess — one failure does not block others.

---

## Dashboard Integration

The weekly health dashboard (`scripts/imdr_health_dashboard.py`) includes cleaning dry-run previews, health checks, and quality checks for each domain. To avoid parameter drift and duplicated code, the dashboard **imports** all builders from the cleaning CLI scripts — each cleaning CLI is the single diagnostic tool for its domain:

```python
# Dashboard imports — single source of truth (all from cleaning CLIs)
from scripts.fx.clean.clean_fx_fact_ohlc import (
    build_cleaning_rules as ohlc_cleaning_rules,
    build_health_checks as ohlc_health_checks,
    build_quality_checks as ohlc_quality_checks,
)
from scripts.fx.clean.clean_fx_fact_vol import (
    build_cleaning_rules as vol_cleaning_rules,
    build_health_checks as vol_health_checks,
    build_quality_checks as vol_quality_checks,
)
from scripts.rates.clean.clean_rates_fact_observation import (
    build_cleaning_rules as rates_cleaning_rules,
    build_health_checks as rates_health_checks,
    build_quality_checks as rates_quality_checks,
)
```

**Builder functions** (public API for each domain cleaning CLI):

| Script | Exported Builders | Config source |
|--------|-------------------|---------------|
| `clean_fx_fact_ohlc.py` | `build_cleaning_rules()`, `build_health_checks()`, `build_quality_checks()` | `pipelines.yml` → `fx.ohlc.cleaning` (6.0 MAD, 3mo, 5.0%) |
| `clean_fx_fact_vol.py` | `build_cleaning_rules()`, `build_health_checks()`, `build_quality_checks()` | `pipelines.yml` → `fx.vol.cleaning` (4.0 MAD, 12mo, 30.0%) |
| `clean_rates_fact_observation.py` | `build_cleaning_rules()`, `build_health_checks()`, `build_quality_checks()` | `pipelines.yml` → `rates.historical.cleaning` (4.0 MAD, 12mo, 30.0%) |

Each cleaning CLI supports `--section clean|health|coverage|quality|all` to run any combination of diagnostics from a single entry point. The separate report scripts (`scripts/{domain}/health/*_report.py`) have been removed — all diagnostic functionality (health checks, coverage, quality checks, cleaning) is consolidated in the cleaning CLIs.

All cleaning params are config-driven via `pipelines.yml`. CLI `--n-mad` / `--trailing-months` / `--pct-threshold` / `--min-obs` override config when provided. Builder signatures use `None` defaults — `None` means "read from config".

Health check and quality check builders follow the same pattern — `build_health_checks()` reads `max_staleness_hours` from `pipelines.yml`, and `build_quality_checks()` uses domain-specific universe YAML.

---

## Changelog

| Date | Change | Scope |
|------|--------|-------|
| 2026-03-11 | Tuned FX OHLC defaults from 1mo/4MAD to 3mo/6MAD | `clean_fx_fact_ohlc.py` |
| 2026-03-11 | Fixed FX Vol vol_type partitioning bug | `clean_fx_fact_vol.py` |
| 2026-03-11 | Added pct_change NULL chain-breakers | All 3 domains |
| 2026-03-11 | Refactored CleaningRunner to snapshot execution | `cleaning.py` |
| 2026-03-11 | Added interpolation-stabilized robust outlier detection | All 3 domains |
| 2026-03-11 | Created `imdr_clean.py` cross-domain orchestrator | `scripts/imdr_clean.py` |
| 2026-03-11 | Config-driven cleaning params from `pipelines.yml` | All 3 builders + `clean_cli.py` |
| 2026-03-11 | Fixed email HTML table rendering (`Markup()` wrapping) | `weekly_dashboard.py` + template |
| 2026-03-11 | Unified quality + cleaning params — both read from `pipelines.yml` | All 3 quality builders + dashboard |
| 2026-03-11 | Fixed FX Vol health check range — derived from `fx.yml` per-(strike,vol_type) bounds | `clean_fx_fact_vol.py` |
| 2026-03-11 | Removed redundant vol quality params from `fx.yml` / `VolQualityParsed` | `fx.yml`, `fx.py` |
| 2026-03-12 | Aligned grouping columns and `min_obs` across pipeline quality checks, health reports, and cleaning for FX Vol. Made `min_obs` configurable via `pipelines.yml` for all domains. Refactored OHLC clean script to use shared `add_common_clean_args()`. | All 3 domains, `pipeline_config.py`, `pipelines.yml` |
| 2026-03-12 | FX Vol `PercentageChangeRule` 3-tier filtering: strike-aware absolute thresholds (Tier 1), class×tenor pct matrix from `fx.yml` (Tier 2), fallback 30% from `pipelines.yml` (Tier 3). Added `min_abs_prev=0.5` to skip near-zero denominators. Fixed `ts_column` to use `obs_date`. Aligned `min_obs` with rolling window params. | `clean_fx_fact_vol.py`, `fx.yml` |
