# Weekly Data Operations

Personal runbook for weekly data quality maintenance. Run from the project root with the `imdr` conda env active.

---

## The Cycle

Every week (ideally Monday morning), run through these steps per domain:

| Step | What | Why |
|------|------|-----|
| 1 | **Report** — run diagnostics for the past week | See coverage gaps, health check status, quality flags |
| 2 | **Dry-run clean** — detect issues without writing | Understand what the cleaning rules would correct |
| 3 | **Re-pull** — re-ingest flagged hours from source | Give the source a second chance before NULLing data |
| 4 | **Re-check** — report + dry-run again | Confirm what improved and what's still bad |
| 5 | **Execute** — NULL the remaining outliers | Apply corrections to genuinely corrupt rows |

---

## FX Domain

### Step 1: Diagnostic Report

Full report (all years):

```bash
python -m scripts.diagnostics.fx_ohlc_report
```

Filter to recent data:

```bash
python -m scripts.diagnostics.fx_ohlc_report --year 2026
```

Run a single section:

```bash
python -m scripts.diagnostics.fx_ohlc_report --section health
python -m scripts.diagnostics.fx_ohlc_report --section missing
python -m scripts.diagnostics.fx_ohlc_report --section quality
python -m scripts.diagnostics.fx_ohlc_report --section quality --sigma 3
```

**What to look for:**
- Health checks: any FAIL results (null counts, row counts off)
- Missing data: symbols with low coverage % or large gaps
- Quality: outlier counts per symbol — a few is normal, hundreds means something upstream broke

### Step 2: Dry-Run Clean

Scan the full table:

```bash
python -m scripts.clean_fx_fact_ohlc
```

Filter to a specific year or symbol:

```bash
python -m scripts.clean_fx_fact_ohlc --year 2026
python -m scripts.clean_fx_fact_ohlc --symbol USDKRW
python -m scripts.clean_fx_fact_ohlc --rule hard_bound
```

Tune robust outlier sensitivity:

```bash
python -m scripts.clean_fx_fact_ohlc --n-mad 5.0 --trailing-months 6
```

**What to look for:**
- `non_positive`: should be near zero — these are clearly broken
- `hard_bound`: check the `pct_change` in the output — a +400% jump is corruption, a -2% drift near the boundary might be real
- `robust_outlier`: should be a small number (tens, not thousands) — if it's huge, the rolling window params may need tuning
- `bid_ask`: minor inversions (bid barely > ask) are common in EM NDFs — large inversions are suspect

### Step 3: Re-Pull Flagged Hours

Generate a gaps file from the dry run:

```bash
python -m scripts.clean_fx_fact_ohlc --emit-gaps data/gaps/cleaning_gaps.txt
```

Then edit `scripts/fx_bidfx_historical.py`:

```python
MODE = "gaps"
GAPS_FILE = "data/gaps/cleaning_gaps.txt"
```

Run the backfiller:

```bash
python -m scripts.fx_bidfx_historical
```

This re-fetches ticks from BidFX for each flagged hour and upserts fresh bars. If the source data was transiently bad, this often fixes it.

**Alternative — re-pull a specific hour manually:**

```bash
python -m scripts.run_pipeline fx.ohlc --hour 2026-03-09T13:00:00
```

### Step 4: Re-Check

Run the report and dry-run clean again:

```bash
python -m scripts.diagnostics.fx_ohlc_report --year 2026
python -m scripts.clean_fx_fact_ohlc --year 2026
```

Compare the counts to Step 2. Rows that disappeared were fixed by re-pull. Rows that remain are genuinely corrupt at the source.

### Step 5: Execute Corrections

Once satisfied that the remaining flagged rows are truly bad:

```bash
python -m scripts.clean_fx_fact_ohlc --execute
```

Or scoped:

```bash
python -m scripts.clean_fx_fact_ohlc --execute --year 2026
python -m scripts.clean_fx_fact_ohlc --execute --rule hard_bound --symbol USDKRW
```

This NULLs all price columns for non-positive/hard-bound/robust-outlier rows, and swaps bid/ask for inversions.

---

## Cleaning Rules Reference

| Rule | What it detects | Action | Severity |
|------|----------------|--------|----------|
| `non_positive` | Any price column <= 0 | NULL all prices | Always corrupt |
| `hard_bound` | `close_px` outside per-symbol hard bounds (from `fx.yml`) | NULL all prices | Check `pct_change` — sudden jumps are corrupt, gradual drift near boundary may be real |
| `pct_change` | `close_px` moved >5% from previous bar (per symbol+series) | NULL all prices | Catches sudden jumps; tune with `--pct-threshold` |
| `robust_outlier` | `close_px` deviates > N MADs from rolling median (per symbol+series) | NULL all prices | Rolling 12-month window, expanding for first 12 months. Catches spikes, ignores long-term drift |
| `bid_ask` | `bid > ask` | Swap bid and ask | Common in EM NDFs, usually minor |

---

## Quick Reference

```bash
# Full weekly cycle — FX
python -m scripts.diagnostics.fx_ohlc_report --year 2026
python -m scripts.clean_fx_fact_ohlc --year 2026
python -m scripts.clean_fx_fact_ohlc --year 2026 --emit-gaps data/gaps/cleaning_gaps.txt
# edit fx_bidfx_historical.py → MODE="gaps", GAPS_FILE="data/gaps/cleaning_gaps.txt"
python -m scripts.fx_bidfx_historical
python -m scripts.diagnostics.fx_ohlc_report --year 2026
python -m scripts.clean_fx_fact_ohlc --year 2026
python -m scripts.clean_fx_fact_ohlc --year 2026 --execute
```

---

## Rates Domain

Rates has a simpler maintenance cycle — no tick-level cleaning rules. The main concern is coverage gaps (missed API fetches).

For full architecture and troubleshooting, see `docs/admin/rates/overview.md`.

### Step 1: Diagnostic Report

Check pipeline runs and daily row counts:

```sql
-- Failed runs in past week
SELECT * FROM [audit].[pipeline_runs]
WHERE pipeline_name = 'rates.historical'
  AND started_at >= DATEADD(DAY, -7, GETDATE())
  AND run_status = 'failed'
ORDER BY started_at DESC;

-- Daily par row counts (expect ~1,000-1,700 per business day)
SELECT CAST(ts AS DATE) AS obs_date, COUNT(*) AS rows
FROM [rates].[fact_observation]
WHERE quote = 'par'
  AND ts >= DATEADD(DAY, -7, GETDATE())
GROUP BY CAST(ts AS DATE)
ORDER BY obs_date DESC;

-- Active curves missing data in past week
SELECT c.ccy, c.curve
FROM [rates].[dim_curve] c
WHERE c.curve_status = 'active'
  AND c.id NOT IN (
    SELECT DISTINCT curve_id FROM [rates].[fact_observation]
    WHERE ts >= DATEADD(DAY, -7, GETDATE())
  );
```

**What to look for:**
- Failed pipeline runs — check logs for token or rate limit errors
- Days with significantly fewer rows than usual — indicates partial fetch
- Active curves with zero observations — may need `seed_rates_dim_curve.py` re-run

### Step 2: Re-Pull Missing Dates

```bash
# Single date
python -m scripts.run_pipeline rates.historical --start 2026-03-05 --end 2026-03-05 --quotes par

# Date range, all quote types
python -m scripts.run_pipeline rates.historical --start 2026-03-03 --end 2026-03-07 --quotes par,spread,fwd,bfly,ssw,rc
```

Upsert is idempotent — safe to re-run dates that already have data.

### Step 3: Validate

```sql
-- Confirm row counts recovered
SELECT CAST(ts AS DATE) AS obs_date, COUNT(*) AS rows
FROM [rates].[fact_observation]
WHERE quote = 'par'
  AND ts >= DATEADD(DAY, -7, GETDATE())
GROUP BY CAST(ts AS DATE)
ORDER BY obs_date DESC;
```

### Quick Reference

```bash
# Full weekly cycle — Rates
# 1. Run diagnostic SQL queries above
# 2. Re-pull any gap dates:
python -m scripts.run_pipeline rates.historical --start YYYY-MM-DD --end YYYY-MM-DD --quotes par
# 3. Verify row counts recovered
```
