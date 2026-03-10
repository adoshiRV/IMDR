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
# Default: last complete business day, par rates
python -m scripts.rates_citi_live

# Override date and quote types
python -m scripts.rates_citi_live --date 2026-03-10 --quotes par,spread,fwd,bfly
```

### Daily via Orchestrator

```bash
# Runs all daily pipelines (currently: rates_citi_live)
python -m scripts.imdr_daily
```

### Historical Backfill

Edit config at top of `scripts/rates_citi_historical.py`, then run:

```bash
python -m scripts.rates_citi_historical
```

Modes: `range` (START→END), `catchup` (last N days), `gaps` (dates from file).

### Full Historical Backfill Example

```python
# In scripts/rates_citi_historical.py:
MODE = "range"
START = "2021-01-01"
END = "2026-03-10"
QUOTES = "par"          # or "par,spread,fwd,bfly,ssw,rc"
```

```bash
python -m scripts.rates_citi_historical
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
Citi Velocity API → CitiVelocityClient → CitiVelocityRatesExtractor
    → citi_response_to_df() → [ts, ccy, curve, quote, tenor, value]
    → resolve curve_ids from dim_curve
    → Pydantic validation (RatesObservationCreate)
    → RatesObservationRepository.bulk_upsert() → SQL Server
    → parquet_write() → data/parquet/rates/ccy=.../curve=.../quote=.../YYYY-MM.parquet
    → audit record in [audit].[pipeline_runs]
```

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
