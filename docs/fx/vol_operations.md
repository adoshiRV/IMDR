# FX Vol Domain - Operations Guide

User-facing guide for running, monitoring, and maintaining the FX vol pipeline.

For admin-level architecture details, see `docs/admin/fx/overview.md`.

---

## Pipeline Overview

The FX vol pipeline ingests daily implied volatility surfaces from Citi Velocity for 17 currency pairs across 11 strikes, 14 tenors, and 3 vol types (~1,530 rows/day).

**Table:** `[fx].[fact_vol]`
**Dimension:** `[fx].[dim_currency_pair]`
**Date column:** `obs_date`
**Value column:** `value` (vol in percentage points)

---

## Scripts

### Daily EOD — `scripts/fx/citi/fx_vol_citi_live.py`

```bash
python -m scripts.fx.citi.fx_vol_citi_live
python -m scripts.fx.citi.fx_vol_citi_live --date 2026-03-10
```

- Runs as part of `scripts/imdr_daily.py` orchestrator
- Sends email report on completion

### Historical Backfill — `scripts/fx/citi/fx_vol_citi_historical.py`

Configure by editing variables at the top of the script:

```python
MODE = "range"          # "range" | "catchup"
START = "2025-01-01"
END = "2025-12-31"
LOOKBACK_DAYS = 30      # for catchup mode
```

```bash
python -m scripts.fx.citi.fx_vol_citi_historical
```

---

## Diagnostics

Diagnostics are built into the cleaning CLI. Use `--section` to run specific checks without applying corrections.

```bash
python -m scripts.fx.clean.clean_fx_fact_vol --section all                          # full report (all years)
python -m scripts.fx.clean.clean_fx_fact_vol --section all --year 2026              # filter by year
python -m scripts.fx.clean.clean_fx_fact_vol --section health                       # health checks only
python -m scripts.fx.clean.clean_fx_fact_vol --section coverage                     # coverage analysis
python -m scripts.fx.clean.clean_fx_fact_vol --section quality                      # quality checks
```

### Section 1: Health

Per-year structural checks:
- **Row count** — minimum 50 rows per year
- **Null check** — `value` column must not be NULL
- **Duplicate check** — unique on (pair_id, obs_date, strike, tenor, vol_type)
- **Freshness** — data no older than 48 hours
- **Value range** — `value` between 0.1 and 200.0

### Section 2: Coverage

Custom SQL analysis:
- **Per-pair date coverage** — actual dates, first/last date, joins dim_currency_pair for labels
- **Strike×tenor grid completeness** — on the latest obs_date per pair
- **Row count by pair** — total rows and date range

### Section 3: Quality

Analytical checks using shared quality framework:
- **Composite range check** — per-(strike, vol_type) bounds from `fx.yml`
- **Percentage change** — day-over-day moves exceeding threshold (default 30%)
- **Robust statistical outlier** — MAD-based, group by pair_id+strike+tenor+vol_type
- **Distribution** — summary stats per strike

---

## Data Cleaning

Dry-run by default — shows what would change without writing.

```bash
python -m scripts.fx.clean.clean_fx_fact_vol                           # dry-run, full table
python -m scripts.fx.clean.clean_fx_fact_vol --execute                 # apply corrections
python -m scripts.fx.clean.clean_fx_fact_vol --year 2026               # filter by year
python -m scripts.fx.clean.clean_fx_fact_vol --pair 1                  # filter by pair_id
python -m scripts.fx.clean.clean_fx_fact_vol --rule robust_outlier     # single rule
python -m scripts.fx.clean.clean_fx_fact_vol --n-mad 5.0               # tune MAD threshold
python -m scripts.fx.clean.clean_fx_fact_vol --pct-threshold 50.0      # tune pct change threshold
python -m scripts.fx.clean.clean_fx_fact_vol --min-obs 50              # minimum observations for rolling stats
```

### Cleaning Rules

| Rule | Detection | Correction |
|---|---|---|
| `hard_bound` | `value` outside per-(strike, vol_type) bounds | NULL value |
| `robust_outlier` | z > N MAD (12-month rolling, per pair_id+strike+tenor+vol_type) | NULL value |
| `pct_change` | 3-tier day-over-day check (see below) | NULL value |

Pipeline quality checks, health reports, and cleaning all use identical grouping columns (`[pair_id, strike, tenor, vol_type]`) and thresholds — configured in `pipelines.yml` under `fx.vol`.

**`pct_change` 3-tier logic:**

1. **Tier 1 (absolute change)** — Signed/small strikes (25RR, 10RR, 25STR, 10STR) use absolute vol-point thresholds (2.0, 3.0, 1.0, 2.0) instead of percentage change. These strikes have values near zero where percentage change is meaningless.
2. **Tier 2 (class×tenor pct)** — For other strikes, thresholds vary by currency class and tenor (e.g., G10 1W: 75%, G10 10Y: 15%, EM NDF 1W: 100%). Configured in `fx.yml` under `vol.quality.pct_thresholds`.
3. **Tier 3 (fallback)** — Any class×tenor combination not in the matrix falls back to `pct_threshold: 30.0` from `pipelines.yml`.

Additionally, `min_abs_prev=0.5` skips rows where the previous value is near zero (avoids false flags on ATM SPREAD). The rule JOINs `[fx].[dim_currency_pair]` to resolve `ccy_class`.

---

## Quality Ranges

Configured in `src/imdr/universe/fx.yml` under `vol.quality.ranges`:

| Strike | Vol Type | Min | Max |
|---|---|---|---|
| ATM | IMPLIED | 0.5 | 80.0 |
| ATM | REALISED | 0.5 | 80.0 |
| ATM | SPREAD | -40.0 | 40.0 |
| 25RR, 10RR | IMPLIED | -20.0 | 20.0 |
| 25STR, 10STR | IMPLIED | 0.0 | 20.0 |
| STRIKE_C25, STRIKE_P25, STRIKE_C10, STRIKE_P10 | IMPLIED | 0.5 | 100.0 |

---

## Weekly Maintenance Cycle

Follow the 5-step cycle (same as FX OHLC):

```bash
# 1. Report (all diagnostic sections)
python -m scripts.fx.clean.clean_fx_fact_vol --section all --year 2026

# 2. Dry-run clean
python -m scripts.fx.clean.clean_fx_fact_vol --year 2026

# 3. Re-pull (if needed — edit fx_vol_citi_historical.py)
python -m scripts.fx.citi.fx_vol_citi_historical

# 4. Re-check
python -m scripts.fx.clean.clean_fx_fact_vol --section all --year 2026

# 5. Execute corrections
python -m scripts.fx.clean.clean_fx_fact_vol --year 2026 --execute
```

---

## Universe Configuration

- **17 pairs**: 10 G10+CNH + 7 EM, all quoted vs USD
- **11 strikes**: ATM, 25RR, 10RR, 25STR, 10STR, STRIKE_C25, STRIKE_P25, STRIKE_C10, STRIKE_P10
- **14 tenors**: ON, 1W, 2W, 1M, 2M, 3M, 6M, 9M, 1Y, 2Y, 3Y, 5Y, 7Y, 10Y
- **Vol types**: ATM has IMPLIED + REALISED + SPREAD; all others have IMPLIED only
- **Tag template**: `FX.VOL.{ccy1}.{ccy2}.{strike}.{tenor}.{vol_type}.CITI`

Configured in `src/imdr/universe/fx.yml` under `vol:` section.
