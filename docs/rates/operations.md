# Rates Domain - Operations Guide

Admin-facing guide for setting up, running, and troubleshooting the rates pipeline.

---

## Initial Setup

### Prerequisites

1. **IMDR database** with `[rates]` schema and tables already created (migration 003)
2. **Audit table** — `[audit].[pipeline_runs]` must exist (migration 001). Shared across all domains (FX, Rates). Run `migrations/001_create_pipeline_runs.sql` if not already created.
3. **Citi Velocity API credentials** — request from Citi relationship manager
4. **Python environment** — `imdr` conda env with all dependencies

### Credentials

Add to `.env` in the project root:

```
IMDR_CITI_CLIENT_ID=your_client_id_here
IMDR_CITI_CLIENT_SECRET=your_client_secret_here
```

These are read by `pydantic-settings` via the `IMDR_` prefix.

### Seed Dimension Table

Run once to populate `[rates].[dim_curve]` with 39 curve entries:

```bash
python -m scripts.migrations.seed_rates_dim_curve
```

This reads from `universe/rates.yml` and inserts missing rows. Safe to re-run.

---

## Running the Pipeline

### Daily EOD (Standalone Script)

```bash
# Default: last complete business day, all 6 quote types
python -m scripts.rates.citi.rates_citi_live

# Override date and quote types
python -m scripts.rates.citi.rates_citi_live --date 2026-03-10 --quotes par,spread,fwd,bfly

# Force all API calls (bypass empty combo cache)
python -m scripts.rates.citi.rates_citi_live --no-cache
```

| Flag | Default | Description |
|---|---|---|
| `--date` | last business day | Override date (YYYY-MM-DD) |
| `--quotes` | all 6 (from config) | Comma-separated: par, spread, fwd, bfly, ssw, rc |
| `--frequency` | `DAILY` | Data frequency |
| `--no-cache` | off | Disable empty combo cache — retry all API calls |

### Daily via Orchestrator

```bash
# Runs all daily pipelines (currently: rates_citi_live)
python -m scripts.imdr_daily
```

### Historical Backfill

Edit config at top of `scripts/rates/citi/rates_citi_historical.py`, then run:

```bash
python -m scripts.rates.citi.rates_citi_historical
```

Modes: `range` (START→END), `catchup` (last N days), `gaps` (dates from file).

### Full Historical Backfill Example

```python
# In scripts/rates/citi/rates_citi_historical.py:
MODE = "range"
START = "2021-01-01"
END = "2026-03-10"
QUOTES = "par"          # or "par,spread,fwd,bfly,ssw,rc"
```

```bash
python -m scripts.rates.citi.rates_citi_historical
```

**API budget for full backfill (par only):**
- 39 curves × 44 tenors (max) = 1,716 tags
- At 100 tags/batch = ~18 API requests per fetch
- With 1 sec rate limit = ~18 seconds per run
- Well within 10,000 daily call limit

### Generic Pipeline Runner (Ad-Hoc)

```bash
python -m scripts.run_pipeline rates.historical --start 2026-03-10 --end 2026-03-10 --quotes par
python -m scripts.run_pipeline rates.historical --start 2026-03-10 --end 2026-03-10 --frequency HOURLY
```

---

## Data Flow

```
CurveQuoteCache.load() → read data/cache/rates/empty_combos.json
    → skip cached empty combos (auto-retry after 30 days)
Citi Velocity API → CitiVelocityClient → CitiVelocityRatesExtractor
    → citi_response_to_df() → [ts, ccy, curve, quote, tenor, value]
    → CurveQuoteCache: mark_empty() / mark_active() → save()
    → auto-seed dim_curve + resolve curve_ids
    → Pydantic validation (RatesObservationCreate)
    → RatesObservationRepository.bulk_upsert() → SQL Server
    → parquet_write() → data/parquet/rates/ccy=.../curve=.../quote=.../YYYY-MM.parquet
    → SymbolRangeCheck: per-quote-type range validation (flag, don't block)
    → health checks: row count, nulls, duplicates, freshness
    → audit record in [audit].[pipeline_runs]
```

---

## Empty Combo Cache

With 6 quote types, the extractor makes 39 × 6 = 234 API calls per run. ~78% return 0 rows (ceased curves, unavailable quote types). The cache tracks these and skips them on future runs.

**Cache file:** `data/cache/rates/empty_combos.json`

- First run: all curve×quote calls, cache populated with empties (ceased curves, EM-only quotes)
- Subsequent runs: only active combos re-fetched (~4x faster)
- Active/reformed curves: stale after 2 days. Ceased curves: stale after 30 days
- Protected quotes (`par`, `ssw`) for active curves are never cached as empty
- Use `--no-cache` to bypass, or delete the JSON file to force a full refresh

---

## Quality Checks

After loading data, the pipeline runs per-quote-type range validation using ranges from `universe/rates.yml`:

| Quote | Min | Max |
|---|---|---|
| par | -3.0 | 20.0 |
| spread | -500.0 | 500.0 |
| fwd | -5.0 | 25.0 |
| bfly | -100.0 | 100.0 |
| ssw | -500.0 | 500.0 |
| rc | -200.0 | 200.0 |

Violations are logged as warnings (`quality_flag_quote_range`) but **never block** the pipeline. To adjust ranges, edit `expected_ranges` in `src/imdr/universe/rates.yml`.

**Note on `pct_threshold`**: The cleaning `PercentageChangeRule` currently uses a global 30% threshold for all quote types. This is a known limitation — BFLY, SSW, and RC values are naturally more volatile day-to-day than PAR or FWD, so a single threshold either over-flags PAR or under-flags BFLY. A per-quote-type calibration (e.g., PAR: 10-15%, FWD: 15-20%, BFLY/SSW/RC: 50-75%) would improve accuracy but requires data analysis to set appropriate bounds. Tracked for future implementation.

---

## Tag Discovery

Validate the universe config against what Citi actually serves:

```python
from imdr.config.settings import get_settings
from imdr.connectors.citi_velocity import CitiVelocityClient
from imdr.domains.rates.discovery import RatesTagDiscovery

settings = get_settings()
with CitiVelocityClient(settings) as client:
    discovery = RatesTagDiscovery(client)

    # Fetch and cache all PAR tags (first run hits API, subsequent reads cache)
    tags = discovery.fetch_all_par_tags(force=True)

    # Discover what's available
    result = discovery.discover_all()
    print(f"OIS pairs: {len(result['ois']['pairs'])}")
    print(f"SWAP_LIBOR currencies: {len(result['swap_libor']['currencies'])}")

    # Validate catalog against discovered tags
    validation = discovery.validate_catalog()
    print(f"Matched: {validation['matched']}")
    print(f"Unmatched (in catalog, not on API): {validation['unmatched_prefixes']}")
    print(f"Uncataloged (on API, not in catalog): {validation['uncataloged_prefixes']}")
```

Cache is stored at `data/cache/rates/rates_tags.json`.

---

## Parquet Archive

Data is archived to Hive-partitioned parquet alongside the SQL Server write:

```
data/parquet/rates/
  ccy=USD/
    curve=SOFR/
      quote=par/
        2024-01.parquet
        2024-01_manifest.json
        2024-02.parquet
```

### Reading Parquet Locally

```python
from imdr.domains.rates.store import read

# Full curve
df = read(ccy="USD", curve="SOFR", quote="par")

# Filtered
df = read(ccy="USD", curve="SOFR", quote="par", tenor="5Y", start="2024-01-01", end="2024-06-30")

# With benchmark annotation
df = read(ccy="USD", annotate_benchmark=True)
```

---

## Gap Detection

### Via Audit Table

```sql
-- Recent pipeline runs
SELECT TOP 20 *
FROM [audit].[pipeline_runs]
WHERE pipeline_name = 'rates.historical'
ORDER BY started_at DESC;

-- Failed runs
SELECT * FROM [audit].[pipeline_runs]
WHERE pipeline_name = 'rates.historical'
  AND run_status = 'failed'
ORDER BY started_at DESC;
```

### Via Observation Counts

```sql
-- Daily observation counts (should be consistent)
SELECT CAST(ts AS DATE) AS obs_date, COUNT(*) AS rows
FROM [rates].[fact_observation]
WHERE quote = 'par'
GROUP BY CAST(ts AS DATE)
ORDER BY obs_date DESC;
```

---

## Bench Rates (Central Bank Policy Rates)

### Overview

Flat leaf tags from `RATES.BENCH_RATES.*` — 10 configured central banks, ~8 return data daily (JPY_DISCOUNT and JPY_TARGET are known empty). Auto-seeds `rates.dim_central_bank` from `universe/rates.yml` on first run.

### Daily Live Ingest

```bash
# Default: last business day (US calendar)
python -m scripts.rates.citi.rates_bench_citi_live

# Specific date override
python -m scripts.rates.citi.rates_bench_citi_live --date 2026-04-15
```

Registered in `scripts/imdr_daily.py` (10 estimated tags). Sends email notification on completion.

### Historical Backfill

Edit config at top of `scripts/rates/citi/rates_bench_citi_historical.py`:

```bash
# Edit MODE, START, END, then run:
python -m scripts.rates.citi.rates_bench_citi_historical
```

Three modes: `range` (date range), `catchup` (N days back), `gaps` (file of dates).

### Generic Runner

```bash
python -m scripts.run_pipeline rates.bench_rates --start 2026-04-01 --end 2026-04-15
```

### Health Checks

| Check | Threshold |
|---|---|
| Row count | min 5 |
| Null check | cb_id, vendor_id, obs_date, rate |
| Duplicate check | cb_id + obs_date unique |
| Freshness | max 48h staleness |
| Value range | rate: [-2.0, 20.0] |

---

## Troubleshooting

| Problem | Cause | Fix |
|---|---|---|
| `Token fetch failed (status=401)` | Bad credentials | Check `IMDR_CITI_CLIENT_ID` / `IMDR_CITI_CLIENT_SECRET` in `.env` |
| `Token fetch failed (status=403)` | Scope mismatch | Verify `IMDR_CITI_SCOPE=/api` |
| `Citi API error (status=429)` | Rate limit exceeded | Increase `IMDR_CITI_RATE_LIMIT_SEC` (default 1.0) |
| `transform_skipped_unmapped_curves` | Curve not in dim_curve | Re-run `seed_rates_dim_curve.py` |
| `API status not OK` | Citi downtime or bad tags | Check Citi status; verify tags via `discovery.browse()` |
| `0 rows loaded` for a curve | Curve ceased or no data in range | Normal for ceased curves (e.g. LIBOR after Jun 2023) |
| Large `rows_loaded` discrepancy | Duplicate or overlapping re-runs | Upsert is idempotent — safe to re-run |
| Parquet read returns empty | Wrong filters or no data written | Check `data/parquet/rates/` directory structure |
| `quality_flag_quote_range` | Values outside expected range for a quote type | Check flagged quote; widen range in `rates.yml` if legitimate |
| Cache skipping too many combos | Stale cache entries | Run with `--no-cache` or delete `data/cache/rates/empty_combos.json` |
