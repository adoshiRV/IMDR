# Rates Domain — Operational Reference

Everything about how the Rates domain works: architecture, pipeline, scripts, data quality, and configuration.

For schema details (tables, columns, constraints), see `docs/rates/schema.md`.
For Citi Velocity API details, see `docs/rates/citi_velocity_api.md`.
For pipeline operations (setup, running, troubleshooting), see `docs/rates/operations.md`.

---

## Architecture

### Module Map (`src/imdr/domains/rates/`)

| Module | Purpose |
|---|---|
| `extractors.py` | `CitiVelocityRatesExtractor` — batched tag fetching (100 tags/batch) with rate limiting |
| `pipeline.py` | `RatesHistoricalPipeline` — `BasePipeline` wrapper: extract → transform → load → parquet archive |
| `repository.py` | Data access: `RatesCurveRepository` (dimension CRUD), `RatesObservationRepository` (bulk upsert, counts) |
| `store.py` | Hive-partitioned parquet store: `write()` (atomic, dedup) and `read()` (filtered, benchmark-annotated) |
| `schema.py` | Tenor encoding/decoding, quote type mappings (internal ↔ Citi), validation |
| `translate.py` | Citi tag ↔ internal schema translation, API response → DataFrame |
| `utils.py` | Citi x-axis timestamp parser, date formatters |
| `discovery.py` | `RatesTagDiscovery` — tag listing/browsing, catalog validation, cache management |

### Supporting Modules

| Module | Purpose |
|---|---|
| `src/imdr/connectors/citi_velocity.py` | `CitiVelocityClient` — httpx client for all 5 Citi API endpoints, auto-refreshing OAuth2 token |
| `src/imdr/universe/rates.py` + `rates.yml` | Universe config: 39 curves, 22 currencies, maturities, instruments, benchmarks |
| `src/imdr/models/rates.py` | SQLAlchemy ORM: `RatesCurve`, `RatesObservation` |
| `src/imdr/schemas/rates.py` | Pydantic schemas: `RatesCurveCreate`, `RatesObservationCreate` |

---

## Ingest Pipeline

`RatesHistoricalPipeline` in `src/imdr/domains/rates/pipeline.py` — the core pipeline called via `run_pipeline`.

### 4-Step Flow

| Step | What | Details |
|---|---|---|
| 1. **Extract** | Fetch time series from Citi Velocity API | `CitiVelocityRatesExtractor.extract()` — batched by 100 tags, 1s rate limit between batches |
| 2. **Transform** | Resolve curve IDs, validate observations | Maps `(ccy, curve)` → `curve_id` via `dim_curve`, Pydantic validation on each row |
| 3. **Load** | Upsert to `[rates].[fact_observation]` | Via `RatesObservationRepository.bulk_upsert()` — idempotent MERGE on `(curve_id, ts, quote, tenor)` |
| 4. **Post-load** | Archive to Hive-partitioned parquet | Writes to `data/parquet/rates/ccy={CCY}/curve={CURVE}/quote={QUOTE}/{YYYY-MM}.parquet` with manifest |

### Data Flow

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

## Scripts & CLI

### Daily EOD — `scripts/rates_citi_live.py`

The primary daily script. Designed for scheduled (EOD) execution via Task Scheduler or cron.

```bash
# Default: fetch last complete business day, par rates
python -m scripts.rates_citi_live

# Override date
python -m scripts.rates_citi_live --date 2026-03-07

# Multiple quote types
python -m scripts.rates_citi_live --quotes par,spread,fwd,bfly
```

| Flag | Default | Description |
|---|---|---|
| `--date` | last business day | Override date (YYYY-MM-DD) |
| `--quotes` | `par` | Comma-separated: par, spread, fwd, bfly, ssw, rc |
| `--frequency` | `DAILY` | Data frequency |

**Behavior:**
- Default date: yesterday, skipping weekends (Sun→Fri, Sat→Fri)
- Weekend dates: logs and exits 0 (non-fatal)
- RunReport JSONL: `{run_log_dir}/rates/fact_observation/rates_citi_live_{YYYYMMDD}.jsonl`
- Called by `scripts/imdr_daily.py` orchestrator

### Historical Backfill — `scripts/rates_citi_historical.py`

Batch backfill of date ranges. Configure by editing variables at the top of the script:

```python
MODE = "range"          # "range" | "catchup" | "gaps"
START = "2024-01-01"    # YYYY-MM-DD
END = "2024-01-31"
LOOKBACK_DAYS = 30      # for catchup mode
GAPS_FILE = "data/gaps/rates_gaps.txt"  # one YYYY-MM-DD per line
MAX_DAYS = 0            # 0 = unlimited
QUOTES = "par"          # comma-separated
FREQUENCY = "DAILY"
```

Run:

```bash
python -m scripts.rates_citi_historical
```

| Mode | Behavior |
|---|---|
| `range` | Single pipeline call for START→END (skips weekends) |
| `catchup` | Fetch last N calendar days (LOOKBACK_DAYS) from today |
| `gaps` | Read dates from file, one pipeline call per date (partial failure isolation) |

**Examples:**

```bash
# 5-year backfill, par rates only (edit MODE="range", START, END, then run)
python -m scripts.rates_citi_historical

# Re-pull specific gap dates (edit MODE="gaps", GAPS_FILE)
python -m scripts.rates_citi_historical
```

### Generic Pipeline Runner — `scripts/run_pipeline.py`

Still available for ad-hoc runs:

```bash
python -m scripts.run_pipeline rates.historical --start 2026-03-10 --end 2026-03-10 --quotes par
```

### Orchestrator — `scripts/imdr_daily.py`

Top-level daily scheduler entry point. Calls `rates_citi_live` (and future daily pipelines) via subprocess:

```bash
python -m scripts.imdr_daily
```

To add more daily pipelines, edit the `PIPELINES` list in `imdr_daily.py`.

### Curve Seeding — `scripts/migrations/seed_rates_dim_curve.py`

One-time (or re-runnable) script to populate `[rates].[dim_curve]` with 39 curve entries from `universe/rates.yml`:

```bash
python -m scripts.migrations.seed_rates_dim_curve
```

Safe to re-run — only inserts missing rows.

---

## Citi Velocity API

### Client — `src/imdr/connectors/citi_velocity.py`

Single class `CitiVelocityClient` wrapping all 5 Citi API endpoint types via httpx:

| # | Method | Endpoint | Purpose |
|---|---|---|---|
| 1 | `get_token()` | `/markets/cv/api/oauth2/token` | OAuth2 client_credentials → Bearer token |
| 2 | `fetch_historical()` | `/markets/analytics/.../data` | Time series data by tag (1-100 tags/request) |
| 3 | `fetch_metadata()` | `/markets/analytics/.../data` | Series metadata (modification times, ranges) |
| 4 | `fetch_taglisting()` | `/markets/analytics/.../taglisting` | List tags by prefix + optional regex |
| 5 | `fetch_tagbrowsing()` | `/markets/analytics/.../tagbrowsing` | Explore tag tree hierarchy |

**Token management:** Auto-caches token (1hr TTL), auto-refreshes 60s before expiry. No manual token passing needed.

**Rate limits:** 1 request/sec, 100 tags/request, 10,000 daily calls. Enforced by extractor via `citi_rate_limit_sec` setting.

### Credentials

Set in `.env` (read by pydantic-settings with `IMDR_` prefix):

```
IMDR_CITI_CLIENT_ID=your_client_id
IMDR_CITI_CLIENT_SECRET=your_client_secret
```

### Tag Discovery

Interactive validation of universe config against live API:

```python
from imdr.config.settings import get_settings
from imdr.connectors.citi_velocity import CitiVelocityClient
from imdr.domains.rates.discovery import RatesTagDiscovery

settings = get_settings()
with CitiVelocityClient(settings) as client:
    discovery = RatesTagDiscovery(client)
    tags = discovery.fetch_all_par_tags(force=True)
    result = discovery.discover_all()
    validation = discovery.validate_catalog()
    print(f"Matched: {validation['matched']}")
    print(f"Unmatched: {validation['unmatched_prefixes']}")
    print(f"Uncataloged: {validation['uncataloged_prefixes']}")
```

Cache: `data/cache/rates/rates_tags.json` (first run hits API, subsequent reads cache).

---

## Tag Structure

### OIS Tags

```
RATES.OIS.{CCY}_{INDEX}.{QUOTE_TYPE}.{MATURITY}
```

Examples:
- `RATES.OIS.USD_SOFR.PAR.5Y` — USD SOFR par 5Y
- `RATES.OIS.USD_SOFR.CURVES.2Y.10Y` — 2s10s spread
- `RATES.OIS.USD_SOFR.FWD.5Y.5Y` — 5y5y forward
- `RATES.OIS.USD_SOFR.BFLY.2Y.5Y.10Y` — 2s5s10s butterfly

### SWAP_LIBOR Tags

```
RATES.SWAP_LIBOR.{CCY}.{QUOTE_TYPE}.{MATURITY}
```

No index component. Special case: `CNY_NDIRS` (underscore in currency).

---

## Quote Types

| Internal Code | Citi Code | Meaning | Tenor Shape | Example |
|---|---|---|---|---|
| `par` | `PAR` | Par swap rate | Single: `5Y` | 3.85% |
| `ssw` | `SWAP_SPREAD` | Swap spread vs govies | Single: `10Y` | 0.15% |
| `rc` | `ROLL_CARRY` | Roll & carry | Single: `5Y` | 0.05% |
| `spread` | `CURVES` | Curve spread (e.g. 2s10s) | 2-tenor: `2ys10ys` | -0.50% |
| `fwd` | `FWD` | Forward starting swap | 2-tenor: `5ys5ys` | 4.10% |
| `bfly` | `BFLY` | Butterfly | 3-tenor: `2ys5ys10ys` | 0.12% |

---

## Tenor Encoding

Multi-tenor quotes store legs as lowercase with `s` separator:

| Quote | Storage | Display | Example |
|---|---|---|---|
| par / ssw / rc | Uppercase passthrough | Same | `5Y` |
| spread | `{leg1}s{leg2}s` | Numeric + `s` | `2ys10ys` → `2s10s` |
| fwd | `{leg1}s{leg2}s` | Concatenated | `5ys5ys` → `5y5y` |
| bfly | `{leg1}s{leg2}s{leg3}s` | Numeric + `s` | `2ys5ys10ys` → `2s5s10s` |

---

## Parquet Archive

Data is archived to Hive-partitioned parquet alongside the SQL Server write:

```
data/parquet/rates/
  ccy=USD/
    curve=SOFR/
      quote=par/
        2024-01.parquet         # [ts, tenor, value] — partition cols implicit
        2024-01_manifest.json   # fetch metadata for gap detection
        2024-02.parquet
      quote=spread/
        2024-01.parquet
    curve=LIBOR/
      quote=par/
        2023-01.parquet
  ccy=EUR/
    curve=EUROSTR/
      ...
```

**Why Hive partitioning (differs from FX):**
- FX access pattern is time-first ("give me the 08:00 bar"). Date-partitioned flat parquet is fine.
- Rates access pattern is curve-first ("give me USD SOFR par"). Hive partitioning by `(ccy, curve, quote)` avoids scanning all curves to find one.
- Monthly files per partition (~1K rows each) are right-sized.

### Reading Parquet Locally

```python
from imdr.domains.rates.store import read

df = read(ccy="USD", curve="SOFR", quote="par")
df = read(ccy="USD", curve="SOFR", quote="par", tenor="5Y", start="2024-01-01", end="2024-06-30")
df = read(ccy="USD", annotate_benchmark=True)
```

### Write Behavior

- **Atomic writes:** temp file + replace — no partial files on failure
- **Dedup:** `keep='last'` on `(ts, tenor)` — re-runs safely overwrite
- **Manifests:** JSON sidecar with fetch metadata (tags requested, rows received, timestamp)

---

## Universe — `src/imdr/universe/rates.yml`

### Coverage

**39 curves** across **22 currencies**, split by type:

- **RFR (OIS):** 16 curves — SOFR, FEDFUND, EUROSTR, EONIA, SONIA, TONAR (x3), SARON, AONIA, NZIONA, CORRA, NOWA, STINA, SORA, THOR
- **IBOR (SWAP_LIBOR):** 23 curves — LIBOR, EURIBOR, GBP_LIBOR, JPY_LIBOR, CHF_LIBOR, BBSW, BKBM, CDOR, NIBOR, STIBOR, SOR, THBFIX, CNH_HIBOR, SHIBOR, NDIRS, HIBOR, JIBOR, MIFOR, CD, KLIBOR, PHIREF, TAIBOR, VND_REF

### Maturities

- **OIS:** 44 tenors — 1D, 1W, 2W, 3W, 1M–11M, 1Y, 15M, 18M, 21M, 2Y–20Y, 25Y, 30Y, 35Y, 40Y, 45Y, 50Y
- **SWAP_LIBOR:** 36 tenors — 1W, 1M–11M, 1Y–20Y, 25Y, 30Y, 40Y, 50Y

### Benchmark Transitions

| Currency | Primary RFR | Primary From | Supersedes | Superseded Status |
|---|---|---|---|---|
| USD | SOFR | 2023-07-01 | LIBOR | Ceased 2023-06-30 |
| EUR | EUROSTR | 2022-01-03 | EONIA | Ceased |
| GBP | SONIA | 2022-01-01 | GBP_LIBOR | Ceased 2024-03-28 |
| JPY | TONAR | 2022-01-01 | JPY_LIBOR | Ceased 2021-12-31 |
| CHF | SARON | 2022-01-01 | CHF_LIBOR | Ceased 2021-12-31 |
| CAD | CORRA | 2024-06-28 | CDOR | Ceased 2024-06-28 |
| SGD | SORA | 2023-07-01 | SOR | Ceased 2023-06-30 |
| THB | THOR | 2023-07-01 | THBFIX | Ceased 2023-06-30 |

---

## Configuration — Settings

### ODBC Driver

The project uses the legacy `SQL Server` ODBC driver (set via `IMDR_MSSQL_DRIVER=SQL+Server` in `.env`). This driver does not support `setinputsizes` for `DATETIMEOFFSET` columns, so the engine is configured with `use_setinputsizes=False` in `src/imdr/connectors/mssql.py`. Without this, any ORM INSERT with timezone-aware datetime values (e.g. audit records) will fail with `Invalid precision value (0)`.

### Citi Velocity

Citi Velocity settings in `src/imdr/config/settings.py` (all prefixed `IMDR_` in `.env`):

| Setting | Default | Description |
|---|---|---|
| `citi_host` | `api.citivelocity.com` | API base host |
| `citi_client_id` | (required) | OAuth2 client ID |
| `citi_client_secret` | (required) | OAuth2 client secret |
| `citi_scope` | `/api` | OAuth2 scope |
| `citi_rate_limit_sec` | `1.0` | Seconds between batched API calls |
| `citi_batch_size` | `100` | Tags per historical request |
| `citi_token_ttl` | `3600` | Token TTL in seconds |
| `citi_timeout` | `60` | HTTP timeout in seconds |

---

## API Budget

**Daily EOD update (par only, all 39 curves):**
- 39 curves x 44 tenors (max) = 1,716 tags
- At 100 tags/batch = ~18 API requests
- With 1s rate limit = ~18 seconds

**Full backfill (par only, 5 years):**
- Same per-fetch: ~18 requests
- Well within 10,000 daily call limit

**All 6 quote types add multi-tenor tags** but the total stays comfortably within daily limits.

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
-- Daily observation counts (should be consistent day to day)
SELECT CAST(ts AS DATE) AS obs_date, COUNT(*) AS rows
FROM [rates].[fact_observation]
WHERE quote = 'par'
GROUP BY CAST(ts AS DATE)
ORDER BY obs_date DESC;

-- Per-curve counts
SELECT c.ccy, c.curve, COUNT(*) AS obs_count
FROM [rates].[fact_observation] o
JOIN [rates].[dim_curve] c ON o.curve_id = c.id
GROUP BY c.ccy, c.curve
ORDER BY c.ccy, c.curve;
```

---

## Troubleshooting

| Problem | Cause | Fix |
|---|---|---|
| `Token fetch failed (status=401)` | Bad credentials | Check `IMDR_CITI_CLIENT_ID` / `IMDR_CITI_CLIENT_SECRET` in `.env` |
| `Token fetch failed (status=403)` | Scope mismatch | Verify `IMDR_CITI_SCOPE=/api` |
| `Citi API error (status=429)` | Rate limit exceeded | Increase `IMDR_CITI_RATE_LIMIT_SEC` (default 1.0) |
| `Invalid precision value (0) (SQLBindParameter)` | Legacy `SQL Server` ODBC driver can't bind DATETIMEOFFSET via `setinputsizes` | Ensure `use_setinputsizes=False` is set on the engine in `src/imdr/connectors/mssql.py` |
| `audit_record_creation_failed` | Usually the precision error above | Same fix — affects any ORM INSERT with tz-aware datetime columns |
| `transform_skipped_unmapped_curves` | Curve not in dim_curve | Re-run `seed_rates_dim_curve.py` |
| `API status not OK` | Citi downtime or bad tags | Check Citi status; verify tags via `discovery.browse()` |
| `0 rows loaded` for a curve | Curve ceased or no data in range | Normal for ceased curves (e.g. LIBOR after Jun 2023) |
| Large `rows_loaded` discrepancy | Duplicate or overlapping re-runs | Upsert is idempotent — safe to re-run |
| Parquet read returns empty | Wrong filters or no data written | Check `data/parquet/rates/` directory structure |

---

## Weekly Maintenance

Follow the same cycle as FX (report → re-pull → validate):

### Step 1: Diagnostic Report

```sql
-- Coverage check: daily row counts for the past week
SELECT CAST(ts AS DATE) AS obs_date, quote, COUNT(*) AS rows
FROM [rates].[fact_observation]
WHERE ts >= DATEADD(DAY, -7, GETDATE())
GROUP BY CAST(ts AS DATE), quote
ORDER BY obs_date DESC, quote;

-- Failed pipeline runs in past week
SELECT * FROM [audit].[pipeline_runs]
WHERE pipeline_name = 'rates.historical'
  AND started_at >= DATEADD(DAY, -7, GETDATE())
  AND run_status = 'failed'
ORDER BY started_at DESC;

-- Curves with 0 observations in past week (excluding ceased)
SELECT c.ccy, c.curve, c.curve_status
FROM [rates].[dim_curve] c
WHERE c.curve_status = 'active'
  AND c.id NOT IN (
    SELECT DISTINCT curve_id FROM [rates].[fact_observation]
    WHERE ts >= DATEADD(DAY, -7, GETDATE())
  );
```

### Step 2: Re-Pull Missing Dates

If the diagnostic report shows gaps, re-run the pipeline for those dates:

```bash
# Re-pull a specific date
python -m scripts.run_pipeline rates.historical --start 2026-03-05 --end 2026-03-05 --quotes par

# Re-pull a range
python -m scripts.run_pipeline rates.historical --start 2026-03-03 --end 2026-03-07 --quotes par,spread,fwd,bfly,ssw,rc
```

Upsert is idempotent — safe to re-run dates that already have data.

### Step 3: Validate

After re-pull, confirm the gaps are filled:

```sql
-- Verify row counts recovered
SELECT CAST(ts AS DATE) AS obs_date, COUNT(*) AS rows
FROM [rates].[fact_observation]
WHERE quote = 'par'
  AND ts >= DATEADD(DAY, -7, GETDATE())
GROUP BY CAST(ts AS DATE)
ORDER BY obs_date DESC;

-- Expected: ~39 curves x 44 tenors = ~1,716 par rows per business day
-- (Fewer for ceased curves and currencies with fewer tenors)
```

### Quick Reference

```bash
# Weekly maintenance cycle — Rates
# 1. Check audit for failures
#    SELECT * FROM [audit].[pipeline_runs] WHERE pipeline_name = 'rates.historical' AND run_status = 'failed' AND started_at >= DATEADD(DAY, -7, GETDATE());
# 2. Check daily row counts
#    SELECT CAST(ts AS DATE) AS obs_date, COUNT(*) FROM [rates].[fact_observation] WHERE quote = 'par' AND ts >= DATEADD(DAY, -7, GETDATE()) GROUP BY CAST(ts AS DATE) ORDER BY obs_date;
# 3. Re-pull any gaps
python -m scripts.run_pipeline rates.historical --start YYYY-MM-DD --end YYYY-MM-DD --quotes par
# 4. Verify row counts recovered (re-run step 2 query)
```
