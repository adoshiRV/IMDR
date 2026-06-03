# Rates Domain — Operational Reference

Everything about how the Rates domain works: architecture, pipeline, scripts, data quality, and configuration.

For schema details (tables, columns, constraints), see [`rates_schema.md`](rates_schema.md).
For Citi Velocity API details, see [`docs/admin/vendors/citi/api_reference.md`](../admin/vendors/citi/api_reference.md).
For pipeline operations (setup, running, troubleshooting), see [`rates_operations.md`](rates_operations.md).

---

## Architecture

### Module Map (`src/imdr/domains/rates/`)

| Module | Purpose |
|---|---|
| `extractors.py` | `CitiVelocityRatesExtractor` — batched tag fetching (100 tags/batch) with rate limiting, empty combo cache integration |
| `pipeline.py` | `RatesHistoricalPipeline` — `BasePipeline` wrapper: extract → transform → load → parquet archive → quality checks |
| `cache.py` | `CurveQuoteCache` — JSON-backed cache of empty (ccy, curve, quote) combos to skip wasted API calls |
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
| `src/imdr/universe/rates.py` + `rates.yml` | Universe config: 43 curves (16 OIS + 23 SWAP_LIBOR + 4 BASIS_SWAPS), 22 currencies, maturities, instruments, benchmarks, expected ranges |
| `src/imdr/models/rates.py` | SQLAlchemy ORM: `RatesCurve`, `RatesObservation`, `RatesCacheEmptyCombo` (reserved for future DB cache) |
| `src/imdr/schemas/rates.py` | Pydantic schemas: `RatesCurveCreate`, `RatesObservationCreate` |
| `src/imdr/healthchecks/quality.py` | `SymbolRangeCheck` — per-quote-type range validation (shared with FX) |

---

## Ingest Pipeline

`RatesHistoricalPipeline` in `src/imdr/domains/rates/pipeline.py` — the core pipeline called via `run_pipeline`.

### 5-Step Flow

| Step | What | Details |
|---|---|---|
| 1. **Extract** | Fetch time series from Citi Velocity API | `CitiVelocityRatesExtractor.extract()` — batched by 100 tags, 1s rate limit. Empty combo cache skips known-empty `(ccy, curve, quote)` combos (~78% of calls) |
| 2. **Transform** | Resolve curve IDs, validate observations | Auto-seeds `dim_curve`, maps `(ccy, curve)` → `curve_id`, Pydantic validation on each row |
| 3. **Load** | Upsert to `[rates].[fact_observation]` | Via `RatesObservationRepository.bulk_upsert()` — idempotent MERGE on `(curve_id, ts, quote, tenor)` |
| 4. **Post-load** | Archive + quality checks | Parquet archive + `SymbolRangeCheck` per-quote-type range validation (flags, doesn't block) |
| 5. **Health checks** | Structural data validation | Row count, null check, duplicate check, freshness check |

### Data Flow

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

## Scripts & CLI

### Daily EOD — `scripts/rates/citi/rates_citi_live.py`

The primary daily script. Designed for scheduled (EOD) execution via Task Scheduler or cron.

```bash
# Default: fetch last complete business day, par rates
python -m scripts.rates.citi.rates_citi_live

# Override date
python -m scripts.rates.citi.rates_citi_live --date 2026-03-07

# Multiple quote types
python -m scripts.rates.citi.rates_citi_live --quotes par,spread,fwd,bfly
```

| Flag | Default | Description |
|---|---|---|
| `--date` | last business day | Override date (YYYY-MM-DD) |
| `--quotes` | from `pipelines.yml` | Comma-separated: par, spread, fwd, bfly, ssw, rc |
| `--frequency` | `DAILY` | Data frequency |
| `--no-cache` | off | Disable empty combo cache (retry all API calls) |

**Behavior:**
- Default date: yesterday, skipping weekends (Sun→Fri, Sat→Fri)
- Weekend dates: logs and exits 0 (non-fatal)
- Default quotes: loaded from `pipelines.yml` → `rates.historical.default_quotes` (all 6 types)
- Empty combo cache: skips known-empty `(ccy, curve, quote)` combos to avoid wasted API calls. Use `--no-cache` to force-retry all
- RunReport JSONL: `{run_log_dir}/rates/fact_observation/rates_citi_live_{YYYYMMDD}.jsonl`
- Called by `scripts/imdr_daily.py` orchestrator

### Daily EOD — `scripts/rates/citi/rates_basis_swaps_citi_live.py`

Sibling daily runner for tenor-basis curves. Pulls only the `basis_swaps`-instrument curves with `status != ceased` (EUR + AUD 3s6s), quote `basis` only, with a 5-trading-day lookback. Registered in `imdr_daily.py` at `estimated_tags: 40`. See [`vendors/citi/exploration/rates_basis_swaps.md`](../vendors/citi/exploration/rates_basis_swaps.md).

### Historical Backfill — `scripts/rates/citi/rates_basis_swaps_citi_historical.py`

Multi-year backfill for all 4 basis-swap curves (incl. ceased USD/GBP for their 2015→2025-02 history). Defaults `USE_HOURLY_CREDS=True` to dodge the daily creds' per-tag 10-call/24h cap when chunking ≥10 years.

### Historical Backfill — `scripts/rates/citi/rates_citi_historical.py`

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
python -m scripts.rates.citi.rates_citi_historical
```

| Mode | Behavior |
|---|---|
| `range` | Single pipeline call for START→END (skips weekends) |
| `catchup` | Fetch last N calendar days (LOOKBACK_DAYS) from today |
| `gaps` | Read dates from file, one pipeline call per date (partial failure isolation) |

**Examples:**

```bash
# 5-year backfill, par rates only (edit MODE="range", START, END, then run)
python -m scripts.rates.citi.rates_citi_historical

# Re-pull specific gap dates (edit MODE="gaps", GAPS_FILE)
python -m scripts.rates.citi.rates_citi_historical
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

### BASIS_SWAPS Tags

```
RATES.BASIS_SWAPS.{BASIS}.{CCY}.{START}.{TENOR}.{QUOTE}
```

Quote is **LAST**, not after the prefix — driven by `instruments.basis_swaps.tag_format: "tenor_first"` in rates.yml.

Example: `RATES.BASIS_SWAPS.3S6S_BASIS.AUD.SPOT.10Y.BASIS_SPREAD` — AUD 3s6s 10Y spread.
Full exploration: [`vendors/citi/exploration/rates_basis_swaps.md`](../vendors/citi/exploration/rates_basis_swaps.md).

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
| `basis` | `BASIS_SPREAD` | Tenor basis (3s6s) / x-ccy basis | Single: `10Y` | 6.88 bps |

`basis` is shared between Citi tenor-basis (via the `basis_swaps` instrument) and BBG cross-currency basis (`extractors_bbg.py`); curve identity disambiguates.

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

**43 curves** across **22 currencies**, split by instrument:

- **RFR (OIS):** 16 curves — SOFR, FEDFUND, EUROSTR, EONIA, SONIA, TONAR (x3), SARON, AONIA, NZIONA, CORRA, NOWA, STINA, SORA, THOR
- **IBOR (SWAP_LIBOR):** 23 curves — LIBOR, EURIBOR, GBP_LIBOR, JPY_LIBOR, CHF_LIBOR, BBSW, BKBM, CDOR, NIBOR, STIBOR, SOR, THBFIX, CNH_HIBOR, SHIBOR, NDIRS, HIBOR, JIBOR, MIFOR, CD, KLIBOR, PHIREF, TAIBOR, VND_REF
- **Basis (BASIS_SWAPS):** 4 curves — 3S6S_BASIS for USD/EUR/GBP/AUD. USD + GBP wired as `ceased` (cessation 2025-02-21 post-LIBOR); EUR + AUD active.

### Maturities

- **OIS:** 44 tenors — 1D, 1W, 2W, 3W, 1M–11M, 1Y, 15M, 18M, 21M, 2Y–20Y, 25Y, 30Y, 35Y, 40Y, 45Y, 50Y
- **SWAP_LIBOR:** 36 tenors — 1W, 1M–11M, 1Y–20Y, 25Y, 30Y, 40Y, 50Y
- **BASIS_SWAPS:** 20 tenors — 3M, 6M, 9M, 1Y, 18M, 2Y–12Y, 15Y, 20Y, 25Y, 30Y (AUD missing 3M)

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

**With empty combo cache:** After the first run, ~78% of the 234 (39 curves × 6 quotes) API calls are skipped (ceased curves, unavailable quote types). Only ~51 actual API calls per daily run.

---

## Empty Combo Cache

### Problem

With 6 quote types, the extractor makes 39 × 6 = 234 API calls per run. ~78% return 0 rows (ceased curves like LIBOR, unavailable quote types like `bfly` for certain instruments). This wastes time and API budget.

### Solution

`CurveQuoteCache` (`src/imdr/domains/rates/cache.py`) tracks which `(ccy, curve, quote)` combos are known to return 0 rows in a JSON file:

```
data/cache/rates/empty_combos.json
```

### How It Works

1. **First run** (empty cache): all 234 calls made, cache populated with ~183 empties
2. **Subsequent runs**: `should_skip()` checks the cache → skips known-empty combos → only ~51 API calls
3. **Auto-retry**: entries older than 30 days are automatically retried (in case data becomes available)
4. **Active removal**: if a previously-empty combo returns data, it's removed from cache immediately
5. **`--no-cache` flag**: bypasses the cache entirely, forces all 234 API calls

### Cache File Format

```json
{
  "AUD|AONIA|bfly": "2026-03-11",
  "AUD|AONIA|rc": "2026-03-11",
  "AUD|AONIA|spread": "2026-03-11",
  ...
}
```

Each key is `{ccy}|{curve}|{quote}`, value is the date last confirmed empty (ISO format).

### Maintenance

- **Delete the JSON file** to force a full refresh on next run
- **Edit individual entries** to force retry of specific combos
- **Stale entries** (>30 days) are retried automatically — no manual intervention needed
- Migration `migrations/003_create_cache_empty_combo.sql` is reserved for future DB-backed cache

---

## Quality Checks

### Per-Quote Expected Ranges

Each quote type has different valid value ranges. These are configured in `src/imdr/universe/rates.yml`:

```yaml
expected_ranges:
  par:    { min: -3.0, max: 20.0 }
  spread: { min: -500.0, max: 500.0 }
  fwd:    { min: -5.0, max: 25.0 }
  bfly:   { min: -100.0, max: 100.0 }
  ssw:    { min: -500.0, max: 500.0 }
  rc:     { min: -200.0, max: 200.0 }
```

These ranges use the same `ExpectedRange` model as FX (`src/imdr/universe/base.py`), loaded via `RatesUniverse.expected_ranges`.

### How It Works

After loading data to SQL and writing parquet, the pipeline runs `SymbolRangeCheck` (from `src/imdr/healthchecks/quality.py`):

1. Builds a dynamic SQL CASE expression checking each quote type against its configured range
2. Executes a single query scoped to the current run's date range
3. **Flags but doesn't block** — violations are logged as warnings, not pipeline failures
4. Results appear in structured logs: `quality_flag_quote_range` (warning) or `quality_passed_quote_range` (info)

### Health Checks vs Quality Checks vs Cleaning

| Term | When | What | Failure Mode | Tool |
|------|------|------|-------------|------|
| **Health Checks** | Post-load (inline) + batch report Section 1 | Structural: row counts, nulls, duplicates, freshness | Can FAIL the pipeline run | ORM-based `HealthCheck` classes via `HealthCheckRunner` |
| **Quality Checks** | Post-load (inline) + batch report Section 3 | Analytical: per-quote range violations, statistical outliers, distribution anomalies | Flag only — never blocks | SQL-based `QualityCheck` classes via `AnalyticalReader` |
| **Cleaning** | Batch only (weekly ops) | Detect + correct corrupt rows: NULL bad values | Dry-run by default, `--execute` to apply | `CleaningRule` subclasses via `CleaningRunner` |

**Principle**: Flag, don't block — data is never rejected at ingest. Health checks can fail a pipeline run (audit trail), but quality checks and cleaning only flag/correct after the fact.

### Diagnostics & Cleaning — `scripts/rates/clean/clean_rates_fact_observation.py`

The cleaning script is the single diagnostic tool for rates. Use `--section` to run health, coverage, or quality checks without applying any corrections.

```bash
python -m scripts.rates.clean.clean_rates_fact_observation --section all                    # full report
python -m scripts.rates.clean.clean_rates_fact_observation --section all --year 2026        # filter by year
python -m scripts.rates.clean.clean_rates_fact_observation --section health                 # health checks only
python -m scripts.rates.clean.clean_rates_fact_observation --section coverage               # coverage analysis
python -m scripts.rates.clean.clean_rates_fact_observation --section quality                # quality checks
```

**Sections (`--section clean|health|coverage|quality|all`, default: clean):**
1. **Health** — per-year row counts, null checks, duplicates, freshness
2. **Coverage** — per-curve date coverage, tenor completeness per curve×quote, quote type distribution, row counts
3. **Quality** — per-quote-type range checks, robust statistical outliers (group by curve_id+quote+tenor), distribution stats

### Cleaning

Detect and correct data quality issues. Dry-run by default.

```bash
python -m scripts.rates.clean.clean_rates_fact_observation                           # dry-run, full table
python -m scripts.rates.clean.clean_rates_fact_observation --execute                 # apply corrections
python -m scripts.rates.clean.clean_rates_fact_observation --year 2026               # filter by year
python -m scripts.rates.clean.clean_rates_fact_observation --curve 1                 # filter by curve_id
python -m scripts.rates.clean.clean_rates_fact_observation --quote par               # filter by quote type
python -m scripts.rates.clean.clean_rates_fact_observation --rule robust_outlier     # single rule
python -m scripts.rates.clean.clean_rates_fact_observation --n-mad 5.0               # MAD multiplier
```

| Rule | Detection | Correction |
|---|---|---|
| **Hard bound violation** | `value` outside per-quote-type bounds from `rates.yml` | NULL value |
| **Robust outlier** | z > N MAD (12-month rolling, group by curve_id+quote+tenor) | NULL value |
| **Percentage change** | Observation-over-observation > threshold (group by curve_id+quote+tenor) | NULL value |

### Adjusting Ranges

Edit `src/imdr/universe/rates.yml` → `expected_ranges` section. Changes take effect on next pipeline run (no restart needed — universe is loaded fresh each run).

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
| `quality_flag_quote_range` warning | Observation values outside expected range for a quote type | Check the flagged quote type in logs; adjust `expected_ranges` in `rates.yml` if the range is too narrow |
| `cache_skipped` too high | Cache is aggressively skipping combos that now have data | Run with `--no-cache` to force refresh, or delete `data/cache/rates/empty_combos.json` |
| New curve not being fetched | Curve added to universe but cached as empty from before | Delete the cache file or wait 30 days for auto-retry |

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
