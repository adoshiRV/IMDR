# New Product Playbook

Step-by-step guide for adding a new domain or product to IMDR.
Each step references existing patterns from FX OHLC, FX Vol, and Rates.

---

## Overview

```
 0. Blueprint Check     Cross-reference the IMDR Global Blueprint BEFORE anything else
 1. Data Source         Identify provider, API, auth, rate limits
 2. API Modules         Connector client + extractor class
 3. Connectors          Bulk merge spec, repository, dimension seeding
 4. Domain Documents    Universe YAML + Python, schemas, ORM models, SQL migrations
 5. Live & Historical   Pipeline class + live/historical CLI scripts + calendar integration
 6. Frequency           Register in scheduler (hourly/daily/weekly/etc.) + retry cron
 7. Health              Post-append checks (row count, nulls, dupes, freshness, range)
 8. Clean               Cleaning rules (hard bounds, outliers, pct change) + CLI script
 9. Quality             Quality checks (distribution, statistical, range) — in cleaning CLI
10. Emailers (ESSENTIAL) Formatter + Jinja2 template + wire into live script + dashboard
```

---

## Step 0: Blueprint Check

**Goal**: Cross-reference the IMDR Global Blueprint before writing any code.

The blueprint (`docs/IMDR_blueprint/RVCapital - IMDR Global Blueprint.pdf`) defines the full target schema for every domain. Before starting a new product, **read the relevant section of the blueprint** and ask questions until you fully understand:

**Checklist**:
- [ ] Which tables does the blueprint specify for this domain/schema?
- [ ] What columns, data types, and sources does it require?
- [ ] Which shared dimensions (`dbo.dim_*`) does it reference? Do they exist yet?
- [ ] Does the blueprint expect Bloomberg as primary source? If so, is Citi Velocity acceptable as supplementary or interim?
- [ ] Are there derived/calculated tables that depend on this product (e.g., `fact_swapspread` needs both `fact_ois` and `fact_govtbond`)?
- [ ] Does the blueprint table name match what we're about to build, or are we deviating? If deviating, document why.
- [ ] What other blueprint tables are upstream or downstream of this one?

**ASK QUESTIONS**. Do not assume — the blueprint encodes Harmeet's requirements and the desk's trading workflow. If something is unclear (source priority, column semantics, table relationships), ask before building. Getting the schema wrong is expensive to fix after data is loaded.

**Key principle**: The blueprint is the spec. Code is the implementation. They should match unless there's a documented reason they don't.

---

## Step 1: Data Source

**Goal**: Identify and document the external data source.

**Deliverables**:
- Provider name, API type (REST, WebSocket, CSV), auth method
- Tag/symbol naming convention and how to enumerate instruments
- Rate limits, batch sizes, historical availability
- Expected data shape (columns, types, granularity)

**Reference**: `docs/shared/citi_velocity_catalog.md` for Citi Velocity discovery notes.

**Tag quota** (Citi Velocity only): The API enforces a **100K cumulative tag limit on a rolling 24h window**. When estimating your new product's daily tag count, factor in existing pipelines (~55–60K/day). See `docs/admin/citi_tag_quota.md` for the full budget table and tracking architecture.

**Exploration scripts** (optional): `scripts/explore/explore_{domain}.py` to probe the API and cache results to `data/cache/`. Be aware that exploration scripts consume tags from the same 24h quota pool.

---

## Step 2: API Modules

**Goal**: Build the connector client and extractor.

### 2a. Connector Client

If using an existing provider (Citi Velocity, BidFX), reuse:
- `src/imdr/connectors/citi_velocity.py` -- `CitiVelocityClient`
- `src/imdr/connectors/citi_helpers.py` -- tag parsing, response normalization

If new provider, create `src/imdr/connectors/{provider}.py`:
- Context manager (`__enter__`/`__exit__`) for session lifecycle
- Auth handling (bearer token, basic, API key)
- Rate limiting / retry logic
- Returns raw JSON/DataFrame

### 2b. Extractor

Create `src/imdr/domains/{domain}/extractors.py` (or `extractors_{product}.py` if multiple products per domain).

```python
from imdr.connectors.citi_helpers import TagQuotaExceeded
from imdr.connectors.citi_quota import TagQuotaTracker

class MyExtractor:
    def __init__(self, client, settings, universe, quota_tracker=None):
        self._quota_tracker = quota_tracker
        self._errors: list[dict] = []     # accumulates non-fatal API errors

    def extract(self, start, end, **filters) -> pd.DataFrame:
        # 1. Pre-flight budget check (if Citi Velocity)
        if self._quota_tracker:
            estimated = sum(len(self._build_tags(sym)) for sym in symbols)
            self._quota_tracker.check_budget(estimated, "my_pipeline")

        # 2. Fetch loop with error separation
        for sym in symbols:
            try:
                df = fetch_and_parse_batched(..., quota_tracker=self._quota_tracker)
            except TagQuotaExceeded:
                raise   # NEVER swallow — must propagate
            except Exception as e:
                self._errors.append({"sym": sym, "error": str(e)})
```

**Rules**:
- Extractor does NOT own client lifecycle (injected)
- Always returns `pd.DataFrame` with standardized columns
- Handles batching internally (e.g., rates batches 100 tags per request)
- **`TagQuotaExceeded` must always be re-raised** — never caught by a generic `except Exception`. This ensures quota failures surface in emails and trigger the retry cron.
- **`_errors` list**: Accumulates non-quota API failures so the pipeline/email can report "X of Y failed" instead of silently returning 0 rows
- **`quota_tracker` parameter**: Optional; pass through to `fetch_and_parse_batched()` so tag usage is recorded to the shared quota file
- Logs via `structlog.get_logger()`

**Examples**:
| Domain | File | Class |
|--------|------|-------|
| FX OHLC | `src/imdr/domains/fx/extractors.py` | `BidFXExtractor` |
| FX Vol | `src/imdr/domains/fx/extractors_vol.py` | `CitiVelocityFXVolExtractor` |
| Rates | `src/imdr/domains/rates/extractors.py` | `CitiVelocityRatesExtractor` |

### 2c. Translate Module (Citi Velocity domains)

Create `src/imdr/domains/{domain}/translate.py` (or `vol_translate.py` for vol products).

This module maps between Citi API tag names and internal DataFrame columns. Every Citi-sourced extractor depends on it.

```python
# Define the canonical column order for this domain's DataFrames
COLUMNS = ["ts", "base_ccy", "quote_ccy", "strike", "tenor", "vol_type", "value"]

def citi_tag_to_internal(tag: str) -> dict | None:
    """Parse a Citi tag → internal field dict.

    'FX.VOL.EUR.USD.ATM.1M.IMPLIED.CITI'
    → {'base_ccy': 'EUR', 'quote_ccy': 'USD', 'strike': 'ATM', 'tenor': '1M', 'vol_type': 'IMPLIED'}

    Return None if the tag can't be parsed (unknown format, bad fields).
    This is the ONLY domain-specific piece — citi_response_to_rows() delegates to it.
    """

def citi_response_to_df(resp: dict, parse_x=parse_x_to_ts_utc, ...) -> pd.DataFrame:
    """Convert a raw Citi API response dict → DataFrame with COLUMNS.

    Uses citi_response_to_rows() from citi_helpers.py with your tag_parser.
    """
    from imdr.connectors.citi_helpers import citi_response_to_rows
    rows = citi_response_to_rows(resp, tag_parser=citi_tag_to_internal, parse_x=parse_x)
    return pd.DataFrame(rows, columns=COLUMNS) if rows else pd.DataFrame(columns=COLUMNS)
```

For rates-like products with **multi-tenor quotes** (spreads, butterflies), you also need a `schema.py`:

```python
# src/imdr/domains/{domain}/schema.py
QUOTE_TO_CITI = {"par": "PAR", "spread": "CURVES", "fwd": "CURVES", "bfly": "BFLY", ...}
SINGLE_TENOR_QUOTES = {"par", "ssw", "rc"}       # tag: RATES.OIS.USD_SOFR.PAR.5Y
MULTI_TENOR_QUOTES = {"spread", "fwd", "bfly"}    # tag: RATES.OIS.USD_SOFR.CURVES.2Y.10Y

def encode_tenor(legs: list[str], quote: str) -> str:
    """['2Y', '10Y'] + 'spread' → '2ys10ys'"""

def decode_tenor(tenor: str, quote: str) -> list[str]:
    """'2ys10ys' + 'spread' → ['2Y', '10Y']"""
```

**Examples**:

| Domain | Translate File | Schema File |
|--------|---------------|-------------|
| FX Vol | `src/imdr/domains/fx/vol_translate.py` | — |
| Rates | `src/imdr/domains/rates/translate.py` | `src/imdr/domains/rates/schema.py` |
| Rates Vol | `src/imdr/domains/rates/vol_translate.py` | — |

---

## Step 3: Connectors (DB Layer)

**Goal**: Define how data gets into the database.

### 3a. Bulk Merge Spec

Define in `src/imdr/domains/{domain}/repository.py`:

```python
from imdr.connectors.bulk import MergeSpec, bulk_merge

_MY_SPEC = MergeSpec(
    target_table="[{schema}].[{table}]",
    staging_name="#{schema}_{table}_staging",
    columns={"col": "SQL_TYPE", ...},
    natural_key=["col1", "col2"],     # MERGE ON clause
    value_columns=["value"],           # Updated on MATCHED
)
```

### 3b. Dimension Repository

For FK-linked fact tables, create a dimension repo:

```python
class MyDimRepository:
    def get_by_key(self, **natural_key) -> Model | None: ...
    def get_or_create(self, data: MyDimCreate) -> Model: ...
    def all(self) -> Sequence[Model]: ...
    def bulk_seed_from_universe(self, items: list[MyDimCreate]) -> int: ...
```

### 3c. Fact Repository

```python
class MyFactRepository:
    def bulk_upsert(self, items: list[MyFactCreate]) -> int:
        return bulk_merge(self._session, _MY_SPEC, items)
```

**Examples**:
| Domain | File | Classes |
|--------|------|---------|
| FX Vol | `src/imdr/domains/fx/repository_vol.py` | `FXCurrencyPairRepository`, `FXVolRepository` |
| Rates | `src/imdr/domains/rates/repository.py` | `RatesCurveRepository`, `RatesObservationRepository` |
| Rates Bench | `src/imdr/domains/rates/pipeline_bench.py` | `CentralBankRepository`, `BenchRatesRepository` (inline, auto-seeds `dim_central_bank`) |

---

## Step 4: Domain Documents

**Goal**: Define the data model, universe config, and database schema.

### 4a. Universe YAML

Create `src/imdr/universe/{domain}.yml`:

```yaml
# Instruments, classifications, provider mappings
instruments:
  group_a: [SYM1, SYM2]
  group_b: [SYM3]

# Hard bounds for corruption detection (health checks + quality)
expected_ranges:
  SYM1: {min: 0.5, max: 100.0}
  SYM2: {min: 0.01, max: 50.0}

# Provider config
providers:
  citi:
    auth_type: bearer
    tag_template: "DOMAIN.{sym}.{tenor}.CITI"
```

### 4b. Universe Python

Create `src/imdr/universe/{domain}.py`:

```python
class MyUniverse(BaseUniverse):
    def instruments(self) -> list[str]: ...
    def api_symbols(self) -> list[str]: ...
    def expected_range_for(self, sym) -> ExpectedRange | None: ...

@lru_cache
def get_my_universe() -> MyUniverse:
    return MyUniverse(_load_yaml("domain.yml"))
```

### 4c. Pydantic Schemas

Create `src/imdr/schemas/{domain}.py`:

```python
class MyDimCreate(BaseModel):       # For seeding dimensions
    ...
class MyFactCreate(BaseModel):      # For ingest (no id, no timestamps)
    ...
class MyFactResponse(MyFactCreate): # For reads (includes id, timestamps)
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: datetime
```

### 4d. ORM Models

Create `src/imdr/models/{domain}.py`:

```python
class MyFact(Base):
    __tablename__ = "fact_{product}"
    __table_args__ = (
        UniqueConstraint("col1", "col2", name="uq_{schema}_fact_{product}"),
        {"schema": "{domain}"},
    )
    # Columns...
```

**Rules**:
- All models inherit from `Base` (includes `id`, `created_at`, `updated_at`)
- Natural key via `UniqueConstraint` (not PK) -- enables upsert
- Schema in `__table_args__`
- Use `Numeric(18, 8)` for financial precision, `DATETIMEOFFSET` for UTC timestamps

### 4e. SQL Migrations

Create `migrations/NNN_create_{schema}_{table}.sql`:

```sql
IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = '{schema}')
    EXEC('CREATE SCHEMA [{schema}]');
GO

CREATE TABLE [{schema}].[{table}] (
    id         INT IDENTITY(1,1) PRIMARY KEY,
    ...
    created_at DATETIMEOFFSET NOT NULL DEFAULT SYSDATETIMEOFFSET(),
    updated_at DATETIMEOFFSET NOT NULL DEFAULT SYSDATETIMEOFFSET(),
    CONSTRAINT uq_{schema}_{table} UNIQUE (col1, col2)
);
CREATE INDEX ix_{schema}_{table}_{date_col} ON [{schema}].[{table}] ({date_col});
```

### 4f. Pipeline Config

Add to `src/imdr/config/pipelines.yml`:

```yaml
pipelines:
  {domain}.{product}:
    domain: {domain}
    target_schema: {schema}
    target_table: {table}
    date_column: {date_col}
    unique_columns: [col1, col2, ...]
    required_columns: [col1, col2, value, ...]
    health_checks:
      row_count_min: 10
      max_staleness_hours: 48
    cleaning:
      n_mad: 4.0
      trailing_months: 12
      pct_threshold: 30.0
    sources:
      {provider}:
        type: rest
        auth_type: bearer
```

---

## Step 5: Live & Historical

**Goal**: Build the pipeline class and CLI scripts.

### 5a. Pipeline Class

Create `src/imdr/domains/{domain}/pipeline.py`:

```python
from imdr.connectors.citi_quota import TagQuotaTracker

class MyPipeline(BasePipeline[pd.DataFrame, list[MyFactCreate], int]):
    pipeline_name = "{domain}.{product}"
    domain = "{domain}"

    def __init__(self, ...):
        super().__init__(connector)
        self._extraction_errors: list[dict] = []
        self._quota_usage: int | None = None

    def extract(self) -> pd.DataFrame:
        # Create a quota tracker — shared file across all subprocesses
        tracker = TagQuotaTracker(
            quota_limit=self._settings.citi_tag_quota_limit,
            tracker_path=self._settings.citi_tag_quota_file or None,
        )

        with Client(self._settings) as client:
            extractor = Extractor(client, ..., quota_tracker=tracker)
            df = extractor.extract(self._start, self._end)

        # Capture errors + quota usage for the live script / email
        self._extraction_errors = extractor._errors
        self._quota_usage = tracker.current_usage()
        return df

    def transform(self, raw: pd.DataFrame) -> list[MyFactCreate]:
        # 1. Auto-seed dimensions (idempotent)
        # 2. Build FK cache in same session
        # 3. Resolve FKs, validate via Pydantic
        return observations

    def load(self, data: list[MyFactCreate]) -> int:
        with self._connector.session() as session:
            return MyFactRepository(session).bulk_upsert(data)

    def post_load(self, result, data):
        # 1. Parquet archive (see Step 5a-ii below)
        # 2. Quality checks (flag, don't block) — see Steps 8–9

    def get_health_checks(self) -> list:
        # Return health checks (from step 7)
```

#### Parquet Store (`store.py`)

Create `src/imdr/domains/{domain}/store.py` (or `store_vol.py`). This writes a Hive-partitioned archive alongside the DB for disaster recovery and offline analysis.

```python
# src/imdr/domains/{domain}/store.py
from pathlib import Path

_BASE = Path("data/parquet/{domain}/{table}")

def write(df: pd.DataFrame, manifest: dict | None = None) -> list[Path]:
    """Write DataFrame to Hive-partitioned parquet. Returns list of files written."""
    written = []
    for group_key, group_df in df.groupby([...]):  # partition columns
        path = _BASE / f"{group_key}" / f"{month}.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)

        # Atomic write: temp file → os.replace()
        tmp = path.with_suffix(".tmp")
        group_df.drop_duplicates(subset=NATURAL_KEY, keep="last").to_parquet(tmp)
        os.replace(tmp, path)
        written.append(path)

    # Write manifest alongside
    if manifest:
        manifest_path = _BASE / f"{month}_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2))

    return written
```

**Partition schemes** (follow these conventions):

| Domain | Path Pattern | Group Key |
|--------|-------------|-----------|
| FX Vol | `data/parquet/fx/fact_vol/{BASE}_{QUOTE}/{YYYY-MM}.parquet` | `(base_ccy, quote_ccy, month)` |
| Rates | `data/parquet/rates/ccy={CCY}/curve={CURVE}/quote={QUOTE}/{YYYY-MM}.parquet` | `(ccy, curve, quote, month)` |
| Rates Vol | `data/parquet/rates/swaption_vol/{CCY}/{YYYY-MM}.parquet` | `(ccy, month)` |

**Rules**:
- Dedup via `drop_duplicates(subset=NATURAL_KEY, keep="last")` — newer fetches overwrite
- Atomic writes via `tmp` + `os.replace()` for crash safety
- Month-based files (not daily) to keep file count manageable
- Call from `post_load()`: `written = store.write(self._raw_df, manifest={...})`

### 5b. Live Script

Create `scripts/{domain}/{provider}/{domain}_{product}_live.py`:

```python
from imdr.connectors.citi_helpers import TagQuotaExceeded
from imdr.market_calendar.calendar import last_business_day
from imdr.market_calendar.holidays import holiday_hits_for_timestamp
from imdr.reporting.run_report import RunReport

def main():
    settings = get_settings()
    universe = get_my_universe()

    # ── RunReport lifecycle ──────────────────────────────────
    # RunReport is an in-memory event buffer flushed to JSONL.
    # The retry cron (imdr_retry.py) scans these JSONL logs for
    # "tag_quota" errors to auto-retry failed pipelines.
    report = RunReport(pipeline_name="{domain}.{product}_citi_live")

    # ── Target date via market calendar (see Step 5e) ────────
    target = last_business_day("US")  # or market_code for your domain
    start = target
    end = target.replace(hour=23, minute=59)

    # ── JSONL log path ───────────────────────────────────────
    log_path = Path(settings.run_log_dir) / "{domain}" / "{table}" / f"my_live_{target:%Y%m%d}.jsonl"

    connector = MSSQLConnector(settings)
    try:
        pipeline = MyPipeline(connector=connector, settings=settings,
                              universe=universe, start=start, end=end, ...)
        result = pipeline.run()

        # Log results to RunReport (3 methods: info, warning, error)
        report.info("pipeline", f"Loaded {result} rows", details={
            "date": str(target.date()), "rows_loaded": result,
            "quota_usage": pipeline._quota_usage,
        })

        # Surface extraction errors (non-quota API failures)
        if pipeline._extraction_errors:
            report.warning("extraction_errors",
                f"{len(pipeline._extraction_errors)} item(s) failed",
                details={"errors": pipeline._extraction_errors})

        # Holiday check (see Step 5e)
        my_ccys = universe.target_currencies()
        holiday_hits = holiday_hits_for_timestamp(my_ccys, target)
        if holiday_hits:
            report.info("holidays", f"Holiday hits: {len(holiday_hits)}", details={
                "hits": [{"currency": h.currency, "market_code": h.market_code,
                          "name": h.name} for h in holiday_hits],
            })

        # Email notification (see Step 10)
        if settings.email_enabled:
            _send_report_email(pipeline, report, target, result, holiday_hits, ...)

        report.finish()
        if settings.run_log_dir:
            report.flush_jsonl(log_path)
        return 0

    except TagQuotaExceeded as e:
        # Catch BEFORE generic Exception — category "tag_quota" is what
        # imdr_retry.py scans for.
        report.error("tag_quota", f"Tag quota exceeded: {e}",
            details={"current_usage": e.current_usage, "available": e.available})
        report.finish()
        if settings.run_log_dir:
            report.flush_jsonl(log_path)  # MUST flush — retry cron reads this
        return 1
    except Exception:
        log.exception("my_pipeline_failed")
        report.error("pipeline", "Daily ingest failed")
        report.finish()
        if settings.run_log_dir:
            report.flush_jsonl(log_path)
        return 1
    finally:
        connector.dispose()
```

**RunReport key points**:
- Three levels: `report.info()`, `report.warning()`, `report.error()` — each takes `(category, message, details={})`
- `report.has_errors` → drives email subject badge (`OK` vs `ERROR`)
- `report.finish()` → sets `finished_at` timestamp
- `report.flush_jsonl(path)` → appends header + events as newline-delimited JSON
- **Always flush on both success and failure** — the retry cron depends on it

### 5c. Historical Script

Create `scripts/{domain}/{provider}/{domain}_{product}_historical.py`:

```python
def main():
    # 1. Configure MODE (range, catchup, rewrite, gaps, cleanup)
    # 2. Compute date windows
    # 3. Loop: pipeline.run() per window
    # 4. Summary email
```

### 5d. Register in run_pipeline.py

Add factory to `scripts/run_pipeline.py`. The factory must accept `(MSSQLConnector, argparse.Namespace)` and return a `BasePipeline`:

```python
def _build_my_pipeline(connector: MSSQLConnector, args: argparse.Namespace) -> BasePipeline:
    settings = get_settings()
    universe = get_my_universe()
    start = datetime.strptime(args.start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end = datetime.strptime(args.end, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return MyPipeline(
        connector=connector, settings=settings, universe=universe,
        start=start, end=end, chunk_size=settings.bulk_batch_size,
        # domain-specific params from args (--quotes, --pairs, --currencies, etc.)
    )

PIPELINE_REGISTRY["domain.product"] = _build_my_pipeline
```

**Examples**:
| Domain | Live | Historical |
|--------|------|------------|
| FX OHLC | `scripts/fx/bidfx/fx_bidfx_live.py` | `scripts/fx/bidfx/fx_bidfx_historical.py` |
| FX Vol | `scripts/fx/citi/fx_vol_citi_live.py` | `scripts/fx/citi/fx_vol_citi_historical.py` |
| Rates | `scripts/rates/citi/rates_citi_live.py` | `scripts/rates/citi/rates_citi_historical.py` |
| Rates Bench | `scripts/rates/citi/rates_bench_citi_live.py` | `scripts/rates/citi/rates_bench_citi_historical.py` |

### 5e. Calendar Integration

**Goal**: Integrate the global trading calendar for scheduling, holiday awareness, and health check relaxation.

The market calendar module (`src/imdr/market_calendar/`) provides holiday-aware date logic for 50+ markets. Every live script should use it. See `docs/admin/calendar_module.md` for the full module reference.

#### EOD Scheduling — Target Date

Use `last_business_day()` to determine the correct data date:

```python
from imdr.market_calendar.calendar import last_business_day

# For US-centric products (rates, most FX)
target = last_business_day("US")

# For region-specific products
target = last_business_day("JP")   # Tokyo trading days
target = last_business_day("GB")   # London trading days
```

This walks backward from today skipping weekends and holidays for the given market. Returns a UTC datetime at midnight.

#### Holiday Detection — Report in Email

Every live script should report which currencies are affected by holidays:

```python
from imdr.market_calendar.holidays import holiday_hits_for_timestamp

# Get all currencies your pipeline covers
my_ccys = universe.target_currencies()  # e.g. ["USD", "EUR", "JPY", ...]

# Check which have holidays on the target date
holiday_hits = holiday_hits_for_timestamp(my_ccys, target)
# Returns: [HolidayHit(currency="JPY", market_code="JP", date=..., name="Vernal Equinox Day"), ...]
```

Holiday hits explain missing data: if JPY has a holiday, zero rows for JPY curves is expected, not an error.

#### Market Hours — Hourly Pipelines

For intraday/hourly pipelines, check if the market is open before fetching:

```python
from imdr.market_calendar.calendar import is_market_open

if not is_market_open("US", utc_now):
    log.info("market_closed", market="US")
    return 0  # skip — no data to fetch
```

For 24h OTC markets (FX), use the universe's own open/closed logic instead:

```python
if not universe.is_fx_open(utc_now):
    return 0
```

#### Settlement Holidays — Rates/Swaps

For products with settlement dates (swaps, bonds, forwards), check ISDA financial center holidays:

```python
from imdr.market_calendar.holidays import is_settlement_holiday, isda_holidays

# Check if a date is a settlement holiday
if is_settlement_holiday("US", target_date):
    # Settlement rolls to next good business day

# Get all ISDA holidays for a center
nyse_holidays = isda_holidays("NYSE", 2026)
```

#### IMM Dates — Swap Rolls

For products tied to IMM dates (quarterly swaps, futures):

```python
from imdr.market_calendar.imm import next_imm_date, imm_dates_quarterly

next_q = next_imm_date(quarterly_only=True)  # Next quarterly IMM
all_q = imm_dates_quarterly(2026)             # All 4 quarterly dates
```

#### Market Configuration — `markets.yml`

If your domain covers currencies not already in `markets.yml`, add entries:

```yaml
# src/imdr/market_calendar/markets.yml
MY_MARKET:
  timezone: "Region/City"            # IANA timezone
  currencies: [XXX]                  # ISO currency codes mapped to this market
  exchanges: [XCHANGE]               # Exchange codes (optional)
  calendar_type: country_type        # Holiday calendar source
  country_code: XX                   # ISO-3166 alpha-2
  weekend_days: [5, 6]               # Python weekday ints (5=Sat, 6=Sun)
  isda_centers: [CENTER]             # ISDA settlement centers (optional)
  trading_hours:                     # Omit for 24h/OTC markets
    open: "09:30"
    close: "16:00"
    lunch_start: "12:00"             # Optional (Asian markets)
    lunch_end: "13:00"
```

Key variants:
- **Non-standard weekends**: Israel/Saudi/Egypt/Bangladesh use `weekend_days: [4, 5]` (Fri/Sat)
- **Lunch breaks**: JP, CN, HK, TH, ID, MY, VN have midday breaks
- **TARGET2**: EU markets use `calendar_type: target2` for ECB settlement calendar

Most G10 + major EM currencies are already covered. Check existing entries before adding.

#### Health Check Relaxation

Health checks should relax thresholds on non-trading days (lower row counts expected):

```python
from imdr.healthchecks.quality import should_relax_checks

if should_relax_checks(run_date, market_code="US"):
    # Use relaxed row-count and freshness thresholds
```

#### Reference

| Doc | Scope |
|-----|-------|
| `docs/admin/calendar_module.md` | Full module architecture, CB events, custom holidays |
| `docs/fx/calendar_integration.md` | FX-specific patterns (24h OTC, settlement) |
| `docs/rates/calendar_integration.md` | Rates-specific patterns (ISDA, IMM, CB events) |
| `docs/admin/cb_events_refresh.md` | Bloomberg CB event import pipeline |

---

## Step 6: Frequency (Scheduler Registration)

**Goal**: Register the pipeline in the appropriate scheduler.

Add to `scripts/imdr_{frequency}.py`:

```python
# imdr_daily.py uses a dict format with estimated tag counts for quota pre-flight:
PIPELINES: list[dict] = [
    # existing...
    {"cmd": ["python", "-m", "scripts.{domain}.{provider}.{product}_live"], "estimated_tags": 5_000},
]
```

The `estimated_tags` value is used by the orchestrator to skip pipelines when insufficient quota remains. Be conservative — overestimate by ~20% to account for universe changes.

| Frequency | File | Current Registrations |
|-----------|------|-----------------------|
| Hourly | `scripts/imdr_hourly.py` | FX OHLC (BidFX) |
| Daily | `scripts/imdr_daily.py` | Rates (Citi), Rates Vol (Citi), FX Vol (Citi) |
| Weekly | `scripts/imdr_weekly.py` | Health dashboard |
| Monthly | `scripts/imdr_monthly.py` | (empty) |
| Quarterly | `scripts/imdr_quarterly.py` | (empty) |

**How schedulers work**: Each pipeline runs via subprocess in isolation. Failures are logged but don't block other pipelines. Exit code 1 if any pipeline failed.

**Retry cron** (`scripts/imdr_retry.py`): Runs at 12pm and 6pm SGT. Scans today's JSONL run logs for `tag_quota` errors, checks if the 24h quota window has freed up, then re-runs failed pipelines automatically. No changes needed when adding a new pipeline — the retry script discovers failures from run logs. See `docs/admin/citi_tag_quota.md` for details.

---

## Step 7: Health Checks

**Goal**: Post-append checks that verify data integrity after every ingest.

### 7a. In-Pipeline Health Checks

Override `get_health_checks()` in the pipeline class:

```python
def get_health_checks(self) -> list:
    cfg = self._config.health_checks
    return [
        RowCountCheck(MyModel, self._config.date_column, cfg.row_count_min),
        NullCheck(MyModel, self._config.required_columns, self._config.date_column),
        DuplicateCheck(MyModel, self._config.unique_columns, self._config.date_column),
        FreshnessCheck(MyModel, "created_at", max_staleness_hours=cfg.max_staleness_hours),
        ValueRangeCheck(MyModel, "value", min_val, max_val, self._config.date_column),
    ]
```

**Available checks** (`src/imdr/healthchecks/checks.py`):

| Check | What it verifies |
|-------|-----------------|
| `RowCountCheck` | Minimum rows exist for the time window |
| `NullCheck` | No NULLs in required columns |
| `DuplicateCheck` | No duplicates on natural key |
| `FreshnessCheck` | Data was written within max_staleness_hours |
| `ValueRangeCheck` | Values within absolute min/max bounds |

### 7b. Derive Range Bounds from Universe

Don't hardcode min/max. Derive from universe config:

```python
# FX Vol: union of per-(strike, vol_type) ranges
vq = universe.vol_quality_config()
vol_min = min(r[0] for r in vq.ranges.values())
vol_max = max(r[1] for r in vq.ranges.values())

# FX OHLC: union of per-symbol expected ranges
all_ranges = [universe.expected_range_for(sym) for sym in universe.api_symbols()]
price_min = min(r.min for r in all_ranges)
price_max = max(r.max for r in all_ranges)
```

---

## Step 8: Cleaning Rules

**Goal**: Post-hoc data cleaning that NULLs bad values (flag, don't delete).

### 8a. Cleaning Rule Classes

Create `src/imdr/domains/{domain}/clean_{table}.py`:

```python
class HardBoundViolationRule(CleaningRule):
    @property
    def name(self) -> str: return "hard_bound"

    @property
    def action_label(self) -> str: return "null_value"

    def detect(self, reader, table, where, params) -> pd.DataFrame:
        # SQL: SELECT id, ... WHERE value NOT BETWEEN min AND max
        return reader.query(sql, params)

    def build_update_sql(self, ids: list[int]) -> str:
        return f"UPDATE {table} SET value = NULL, updated_at = ... WHERE id IN (...)"

    def build_action(self, row: pd.Series) -> CleaningAction:
        return CleaningAction(id=row["id"], detail=f"value={row['value']}")
```

**Standard rule set** (per domain):

| Rule | What it NULLs | Config source |
|------|---------------|---------------|
| `HardBoundViolationRule` | Values outside absolute range | Universe YAML `expected_ranges` |
| `RobustOutlierRule` | Values beyond N MADs from rolling median | `pipelines.yml` `cleaning.n_mad`, `trailing_months` |
| `PctChangeRule` | Extreme day-over-day moves | `pipelines.yml` `cleaning.pct_threshold` |

FX OHLC adds: `NonPositivePriceRule`, `BidAskCrossRule`

### 8b. Cleaning CLI Script

Create `scripts/{domain}/clean/clean_{table}.py`:

```python
def build_cleaning_rules(n_mad=None, trailing_months=None, pct_threshold=None, rule=None):
    cfg = get_pipeline_config(PIPELINE_NAME).cleaning
    n_mad = n_mad if n_mad is not None else cfg.n_mad
    # ... build and return rule list

def main():
    rules = build_cleaning_rules(...)
    runner = CleaningRunner(connector, reader, rules, TABLE, dry_run=not args.execute)
    results = runner.run(where=where)
```

### 8c. Register in Multi-Clean

Add to `scripts/imdr_clean.py`:

```python
CLEANING_SCRIPTS = [
    # existing...
    ("My Domain", "scripts.{domain}.clean.clean_{table}"),
]
```

---

## Step 9: Quality Checks

**Goal**: Diagnostic quality analysis (deeper than health checks). No separate report script is needed -- quality checks, health checks, and coverage are all built into the cleaning CLI from Step 8.

### 9a. Quality Check Builders

Add `build_health_checks()` and `build_quality_checks()` to the cleaning CLI (`scripts/{domain}/clean/clean_{table}.py`):

```python
PIPELINE_NAME = "{domain}.{product}"
TABLE = "[{schema}].[{table}]"

def build_health_checks(freshness_hours=None) -> list:
    # Same as step 7, but standalone for the cleaning CLI's --section health

def build_quality_checks() -> list:
    cfg = get_pipeline_config(PIPELINE_NAME).cleaning
    return [
        SymbolRangeCheck(ranges=..., value_column="value"),
        RobustStatisticalOutlierCheck(value_column="value", group_columns=[...],
                                       n_mad=cfg.n_mad, trailing_months=cfg.trailing_months),
        DistributionCheck(value_column="value", group_column="symbol"),
    ]

def build_cleaning_rules(...) -> list:
    # From step 8
```

Each cleaning CLI **MUST export exactly these three functions** — the dashboard and multi-clean scripts import them by name:

```python
# The dashboard imports like this — function names must match exactly:
from scripts.{domain}.clean.clean_{table} import (
    build_health_checks as my_health_checks,
    build_quality_checks as my_quality_checks,
    build_cleaning_rules as my_cleaning_rules,
)
```

The cleaning CLI supports `--section clean|health|coverage|quality|all` to run any combination:

```bash
python -m scripts.{domain}.clean.clean_{table} --section all        # everything
python -m scripts.{domain}.clean.clean_{table} --section health     # health checks only
python -m scripts.{domain}.clean.clean_{table} --section coverage   # coverage only
python -m scripts.{domain}.clean.clean_{table} --section quality    # quality checks only
python -m scripts.{domain}.clean.clean_{table} --section clean      # cleaning dry-run only
python -m scripts.{domain}.clean.clean_{table} --execute            # cleaning with writes
```

**Available quality checks** (`src/imdr/healthchecks/quality.py`):

| Check | Category | What it flags |
|-------|----------|---------------|
| `PositiveValueCheck` | invariant | Non-positive prices |
| `ColumnOrderCheck` | invariant | bid > ask, low > high, etc. |
| `SymbolRangeCheck` | range | Per-symbol hard bound violations |
| `CompositeRangeCheck` | range | Multi-key ranges (e.g., strike+vol_type) |
| `DistributionCheck` | statistical | Distribution shape per group |
| `ReturnDistributionCheck` | statistical | Return distribution per group |
| `StatisticalOutlierCheck` | statistical | Z-score outliers |
| `RobustStatisticalOutlierCheck` | statistical | MAD-based outliers (rolling window) |
| `PercentageChangeCheck` | statistical | Extreme day-over-day moves |
| `SeriesBasisCheck` | basis | Forward/spot basis divergence |

### 9b. Coverage Analysis

Create `src/imdr/domains/{domain}/coverage.py`:

```python
from imdr.connectors.reader import AnalyticalReader
from imdr.healthchecks.dashboard import CoverageData

def get_my_coverage(reader: AnalyticalReader, table: str, years: list[int]) -> CoverageData:
    """Per-{symbol/pair/curve} coverage analysis.

    The dashboard imports this function — it MUST match this signature.
    """
    # 1. Per-symbol date coverage (actual dates vs expected trading days)
    df_cov = reader.query(f"SELECT symbol, MIN(ts) as first, MAX(ts) as last, COUNT(*) as n FROM {table} ...")

    # 2. Grid completeness (strikes×tenors, or tenors per quote type)
    df_grid = reader.query(f"SELECT symbol, COUNT(DISTINCT tenor) as tenors FROM {table} ...")

    # 3. Row counts
    df_counts = reader.query(f"SELECT YEAR(ts) as yr, COUNT(*) as n FROM {table} GROUP BY YEAR(ts)")

    return CoverageData(
        tables={"per_symbol": df_cov, "grid": df_grid, "row_counts": df_counts},
        summary={"grand_total_rows": int(df_counts["n"].sum()), "symbols": len(df_cov)},
    )
```

The `CoverageData` has two fields:
- `tables: dict[str, pd.DataFrame]` — named DataFrames rendered as HTML tables in the dashboard
- `summary: dict[str, Any]` — scalar metrics shown in the dashboard header

**Examples**:
| Domain | Cleaning CLI (single diagnostic tool) |
|--------|---------------------------------------|
| FX OHLC | `scripts/fx/clean/clean_fx_fact_ohlc.py` |
| FX Vol | `scripts/fx/clean/clean_fx_fact_vol.py` |
| Rates | `scripts/rates/clean/clean_rates_fact_observation.py` |

---

## Step 10: Emailers (ESSENTIAL)

**Goal**: Automated notifications for ingest results and weekly dashboard. This step is **not optional** — every pipeline must send post-ingest email reports. Without email notifications, silent failures go undetected until downstream consumers notice stale data.

### 10a. Ingest Formatter

Create `src/imdr/notifications/formatters/{domain}_{product}_ingest.py`:

```python
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"

class MyIngestFormatter:
    def __init__(self):
        self._env = Environment(
            loader=FileSystemLoader(str(_TEMPLATE_DIR)),
            autoescape=True,  # REQUIRED for HTML safety
        )
        self._template = self._env.get_template("{domain}_{product}_ingest.html")

    def format_subject(self, pipeline_name, date, rows, has_errors) -> str:
        status = "OK" if not has_errors else "WARN"
        return f"[IMDR] {pipeline_name} {status} | {date} | {rows} rows"

    def format_body(self, **context) -> str:
        return self._template.render(context)
```

### 10b. Jinja2 HTML Template

Create `src/imdr/notifications/templates/{domain}_{product}_ingest.html`:
- Use inline CSS (Outlook compatibility)
- Include: summary header, data table, health check results, quality flags
- Reference existing templates for structure

### 10c. Wire into Live Script

In the live script (`scripts/{domain}/{provider}/{product}_live.py`):

```python
formatter = MyIngestFormatter()
subject = formatter.format_subject(...)
body = formatter.format_body(...)
send_outlook_email(to=settings.email_to, subject=subject, html_body=body)
```

### 10d. Dashboard Integration

Add to `scripts/imdr_health_dashboard.py`:

```python
# 1. Import all 3 builders from the cleaning CLI
from scripts.{domain}.clean.clean_{table} import (
    build_health_checks as my_health_checks,
    build_quality_checks as my_quality_checks,
    build_cleaning_rules as my_cleaning_rules,
)
# 2. Import the coverage function
from imdr.domains.{domain}.coverage import get_my_coverage

# 3. Create the domain collector function
def _collect_my_domain(
    connector: MSSQLConnector,
    reader: AnalyticalReader,
    years: list[int] | None = None,
) -> DomainReport:
    log.info("dashboard_collect", domain="My Domain")
    reporter = HealthReporter(connector, "{domain}.{product}")
    years = years or reporter.discover_years()

    health_report = reporter.run_health_window(
        my_health_checks(), lookback_days=30, quiet=True,
    )
    coverage = get_my_coverage(reader, "[{schema}].[{table}]", years)
    quality = reporter.run_quality_section(
        my_quality_checks(), years, quiet=True,
    )
    runner = CleaningRunner(
        connector=connector, reader=reader,
        rules=my_cleaning_rules(), table="[{schema}].[{table}]",
        dry_run=True,
    )
    cleaning = runner.run()

    return DomainReport(
        domain_name="My Domain",
        table_name="[{schema}].[{table}]",
        years=years,
        health_reports=[health_report],
        coverage=coverage,
        quality_results=quality,
        cleaning_results=cleaning,
    )
```

Then in `main()`, call `_collect_my_domain()` and add the result to the collection dict. Also add a section to the dashboard HTML template.

---

## File Checklist

Complete list of files to create/modify when adding a new product:

### New Files

| # | File | Purpose |
|---|------|---------|
| 1 | `src/imdr/universe/{domain}.yml` | Universe config (instruments, ranges, providers) |
| 2 | `src/imdr/universe/{domain}.py` | Universe class + cached loader |
| 3 | `src/imdr/models/{domain}.py` | ORM models (dim + fact) |
| 4 | `src/imdr/schemas/{domain}.py` | Pydantic schemas (Create + Response) |
| 5 | `migrations/NNN_create_{schema}_{table}.sql` | SQL DDL (schema, tables, indexes) |
| 6 | `src/imdr/domains/{domain}/extractors.py` | Extractor class (with `_errors`, `quota_tracker`) |
| 7 | `src/imdr/domains/{domain}/translate.py` | Tag parsing: API response → DataFrame (Citi domains) |
| 8 | `src/imdr/domains/{domain}/repository.py` | Repositories (dim + fact, MergeSpec) |
| 9 | `src/imdr/domains/{domain}/pipeline.py` | Pipeline class (ETL + health checks) |
| 10 | `src/imdr/domains/{domain}/store.py` | Parquet archival (Hive-partitioned, atomic writes) |
| 11 | `src/imdr/domains/{domain}/coverage.py` | Coverage analysis SQL (returns `CoverageData`) |
| 12 | `src/imdr/domains/{domain}/clean_{table}.py` | Cleaning rule classes |
| 13 | `scripts/{domain}/{provider}/{product}_live.py` | Live ingest CLI (RunReport + email + JSONL) |
| 14 | `scripts/{domain}/{provider}/{product}_historical.py` | Historical backfill CLI |
| 15 | `scripts/{domain}/clean/clean_{table}.py` | Cleaning CLI (**MUST export**: `build_cleaning_rules()`, `build_health_checks()`, `build_quality_checks()`) |
| 16 | `src/imdr/notifications/formatters/{product}_ingest.py` | Email formatter (ESSENTIAL) |
| 17 | `src/imdr/notifications/templates/{product}_ingest.html` | Email template — inline CSS only (ESSENTIAL) |
| 18 | `tests/unit/test_{domain}_*.py` | Unit tests |

### Modified Files

| # | File | Change |
|---|------|--------|
| 1 | `src/imdr/config/pipelines.yml` | Add pipeline config section |
| 2 | `scripts/run_pipeline.py` | Add to `PIPELINE_REGISTRY` |
| 3 | `scripts/imdr_{frequency}.py` | Register in scheduler (include `estimated_tags` for daily) |
| 4 | `scripts/imdr_retry.py` | Add to `PIPELINE_REGISTRY` dict (cmd, estimated_tags, log_dir, log_prefix) |
| 5 | `scripts/imdr_clean.py` | Add to `CLEANING_SCRIPTS` |
| 6 | `scripts/imdr_health_dashboard.py` | Add domain collector + imports |

### Worked Example: FX Rate (Spot + Forward Curve + Points, 2026-04-22)

Citi Velocity daily EOD spot + 10-tenor forward curve + forward points across 31 FX pairs (G10 + Asia + EM).

| Checklist # | FX Rate file |
|---|---|
| 1 | `src/imdr/universe/fx.yml` (`fx_rate:` block — 31 pairs, 11 tenors, 3 tag templates, 31 expected_ranges) |
| 2 | `src/imdr/universe/fx.py` (`FXRateConfig`, `fx_rate_pairs()`, `build_fx_rate_spot_tag/outright/point_tags()`, `fx_rate_pair_create_entries()`) |
| 3 | `src/imdr/models/fx_rate.py` (`FXFactFXRate` — 3 FKs to pair, vendor, frequency) + `src/imdr/models/frequency.py` (new cross-domain dim) |
| 4 | `src/imdr/schemas/fx_rate.py` (`FXRateCreate` with tenor enum validation + spot/fwd_points constraint) |
| 5 | `migrations/023_create_dim_frequency.sql` + `migrations/024_create_fx_fact_fx_rate.sql` (PAGE-compressed, NONCLUSTERED PK, clustered on `(obs_date, pair_id, tenor)`) |
| 6 | `src/imdr/domains/fx/extractors_rate.py` (`CitiVelocityFXRateExtractor`) |
| 7 | `src/imdr/domains/fx/rate_translate.py` (3-family tag parser + long→wide pivot) |
| 8 | `src/imdr/domains/fx/repository_rate.py` (`_FX_RATE_SPEC` MergeSpec; reuses `FXCurrencyPairRepository`) |
| 9 | `src/imdr/domains/fx/pipeline_rate.py` (`FXRatePipeline` — resolves pair_id + vendor_id + frequency_id in transform) |
| 10 | `src/imdr/domains/fx/store_rate.py` (month-partitioned parquet) |
| 11 | `src/imdr/domains/fx/coverage.py::get_fx_rate_coverage()` |
| 12 | `src/imdr/domains/fx/clean_fx_fact_fx_rate.py` (HardBound = DELETE per CHECK constraint, Outlier + PctChange = flag only) |
| 13 | `scripts/fx/citi/fx_rate_citi_live.py` |
| 14 | `scripts/fx/citi/fx_rate_citi_historical.py` (range / catchup / gaps modes) |
| 15 | `scripts/fx/clean/clean_fx_fact_fx_rate.py` |
| 16 | `src/imdr/notifications/formatters/fx_rate_ingest.py` |
| 17 | `src/imdr/notifications/templates/fx_rate_ingest.html` |
| 18 | `tests/unit/test_fx_rate_{translate,universe,schema}.py` (43 tests) |

**Cross-domain dim pattern**: This product introduced `dbo.dim_frequency` — the cadence enum reusable across all future fact tables. See [dim_frequency.md](dim_frequency.md) and [schema_conventions.md §3.7](schema_conventions.md).

**Docs**: [fx_rate_schema.md](../fx/fx_rate_schema.md), [fx_rate_pipeline.md](../fx/fx_rate_pipeline.md), [fx_rate_operations.md](../fx/fx_rate_operations.md).

### Worked Example: Bench Rates (Flat Leaf Tags)

Bench rates is a simple flat-tag product (10 tags, no tenor/curve structure). Useful as a reference for products that don't need multi-tenor combos, complex partitioning, or separate extractor modules.

| Checklist # | Bench Rates File |
|---|---|
| 1 | `src/imdr/universe/rates.yml` (`bench_rates:` section) |
| 2 | `src/imdr/universe/rates.py` (`BenchRateEntry`, `bench_rates_tags()`) |
| 3 | `src/imdr/models/rates_bench.py` (`RatesDimCentralBank`, `RatesFactBenchRates`) |
| 4 | `src/imdr/schemas/rates_bench.py` (`CentralBankCreate`, `BenchRateCreate`) |
| 5 | `migrations/020_create_rates_bench_rates.sql` |
| 6-8 | Inline in `src/imdr/domains/rates/pipeline_bench.py` (tag parser, repos, pipeline — consolidated for simple products) |
| 10 | Inline in `pipeline_bench.py` (`parquet_write()` — month-partitioned) |
| 13 | `scripts/rates/citi/rates_bench_citi_live.py` |
| 14 | `scripts/rates/citi/rates_bench_citi_historical.py` |
| 16 | `src/imdr/notifications/formatters/rates_bench_ingest.py` |
| 17 | `src/imdr/notifications/templates/rates_bench_ingest.html` |
| 18 | `tests/unit/test_rates_bench.py` (33 tests) |

**Vendor linking:** `fact_bench_rates.vendor_id` FK → `dbo.dim_vendor.id`, resolved at transform time via `DimVendor.vendor_code == "citi_velocity"`.

**Market code:** `dim_central_bank.market_code` is a VARCHAR referencing market calendar config (`src/imdr/market_calendar/markets.yml`) — not a FK to `dim_market`. Used for holiday detection in the live script.

---

## Config Source of Truth

All statistical parameters live in **one place** and flow to both quality checks and cleaning rules:

```
pipelines.yml
  └── {domain}.{product}:
        └── cleaning:
              ├── n_mad            ──► RobustOutlierRule + RobustStatisticalOutlierCheck
              ├── trailing_months  ──► rolling window for both
              └── pct_threshold    ──► PctChangeRule + PercentageChangeCheck

{domain}.yml
  └── expected_ranges / quality.ranges
        └── hard bounds           ──► HardBoundViolationRule + SymbolRangeCheck/CompositeRangeCheck
                                      + ValueRangeCheck (union for health check)
```

CLI `--n-mad` / `--pct-threshold` override config for ad-hoc analysis only.

### Tag Quota Settings

```
settings.py / .env
  ├── IMDR_CITI_TAG_QUOTA_LIMIT = 95000    ──► TagQuotaTracker.check_budget()
  └── IMDR_CITI_TAG_QUOTA_FILE  = ""       ──► data/cache/citi_tag_quota.json
```

See `docs/admin/citi_tag_quota.md` for the full quota management architecture.

---

## Naming Conventions

| Item | Pattern | Example |
|------|---------|---------|
| Pipeline name | `{domain}.{product}` | `fx.vol`, `rates.historical` |
| SQL schema | `[{domain}]` | `[fx]`, `[rates]` |
| Fact table | `fact_{product}` | `fact_vol`, `fact_observation` |
| Dim table | `dim_{entity}` | `dim_currency_pair`, `dim_curve` |
| Unique constraint | `uq_{schema}_{table}` | `uq_fx_fact_vol` |
| Index | `ix_{schema}_{table}_{cols}` | `ix_fx_fact_vol_obs_date` |
| Migration | `NNN_{description}.sql` | `005_create_fx_fact_vol.sql` |
| Script module | `scripts.{domain}.{provider}.{script}` | `scripts.fx.citi.fx_vol_citi_live` |
| `__init__.py` | Required in each `scripts/{domain}/` and `scripts/{domain}/{provider}/` | |
