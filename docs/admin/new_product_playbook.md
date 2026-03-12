# New Product Playbook

Step-by-step guide for adding a new domain or product to IMDR.
Each step references existing patterns from FX OHLC, FX Vol, and Rates.

---

## Overview

```
 1. Data Source         Identify provider, API, auth, rate limits
 2. API Modules         Connector client + extractor class
 3. Connectors          Bulk merge spec, repository, dimension seeding
 4. Domain Documents    Universe YAML + Python, schemas, ORM models, SQL migrations
 5. Live & Historical   Pipeline class + live/historical CLI scripts
 6. Frequency           Register in scheduler (hourly/daily/weekly/etc.)
 7. Health              Post-append checks (row count, nulls, dupes, freshness, range)
 8. Clean               Cleaning rules (hard bounds, outliers, pct change) + CLI script
 9. Quality             Quality checks (distribution, statistical, range) — in cleaning CLI
10. Emailers            Formatter + Jinja2 template + dashboard integration
```

---

## Step 1: Data Source

**Goal**: Identify and document the external data source.

**Deliverables**:
- Provider name, API type (REST, WebSocket, CSV), auth method
- Tag/symbol naming convention and how to enumerate instruments
- Rate limits, batch sizes, historical availability
- Expected data shape (columns, types, granularity)

**Reference**: `docs/shared/citi_velocity_catalog.md` for Citi Velocity discovery notes.

**Exploration scripts** (optional): `scripts/explore/explore_{domain}.py` to probe the API and cache results to `data/cache/`.

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
class MyExtractor:
    def __init__(self, client, settings, universe): ...
    def extract(self, start, end, **filters) -> pd.DataFrame: ...
```

**Rules**:
- Extractor does NOT own client lifecycle (injected)
- Always returns `pd.DataFrame` with standardized columns
- Handles batching internally (e.g., rates batches 100 tags per request)
- Logs via `structlog.get_logger()`

**Examples**:
| Domain | File | Class |
|--------|------|-------|
| FX OHLC | `src/imdr/domains/fx/extractors.py` | `BidFXExtractor` |
| FX Vol | `src/imdr/domains/fx/extractors_vol.py` | `CitiVelocityFXVolExtractor` |
| Rates | `src/imdr/domains/rates/extractors.py` | `CitiVelocityRatesExtractor` |

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
class MyPipeline(BasePipeline[pd.DataFrame, list[MyFactCreate], int]):
    pipeline_name = "{domain}.{product}"
    domain = "{domain}"

    def extract(self) -> pd.DataFrame:
        with Client(self._settings) as client:
            return Extractor(client, ...).extract(self._start, self._end)

    def transform(self, raw: pd.DataFrame) -> list[MyFactCreate]:
        # 1. Auto-seed dimensions (idempotent)
        # 2. Build FK cache in same session
        # 3. Resolve FKs, validate via Pydantic
        return observations

    def load(self, data: list[MyFactCreate]) -> int:
        with self._connector.session() as session:
            return MyFactRepository(session).bulk_upsert(data)

    def post_load(self, result, data):
        # Parquet archive + quality checks (flag, don't block)

    def get_health_checks(self) -> list:
        # Return health checks (from step 7)
```

### 5b. Live Script

Create `scripts/{domain}/{provider}/{domain}_{product}_live.py`:

```python
def main():
    # 1. Parse args (--date override)
    # 2. Get universe, settings, connector, RunReport
    # 3. Check market hours / weekends (skip if closed)
    # 4. Instantiate pipeline, call .run()
    # 5. Format email notification, send
    # 6. Flush RunReport to JSONL
```

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

Add factory to `scripts/run_pipeline.py`:

```python
PIPELINE_REGISTRY["domain.product"] = _build_my_pipeline
```

**Examples**:
| Domain | Live | Historical |
|--------|------|------------|
| FX OHLC | `scripts/fx/bidfx/fx_bidfx_live.py` | `scripts/fx/bidfx/fx_bidfx_historical.py` |
| FX Vol | `scripts/fx/citi/fx_vol_citi_live.py` | `scripts/fx/citi/fx_vol_citi_historical.py` |
| Rates | `scripts/rates/citi/rates_citi_live.py` | `scripts/rates/citi/rates_citi_historical.py` |

---

## Step 6: Frequency (Scheduler Registration)

**Goal**: Register the pipeline in the appropriate scheduler.

Add to `scripts/imdr_{frequency}.py`:

```python
PIPELINES: list[list[str]] = [
    # existing...
    ["python", "-m", "scripts.{domain}.{provider}.{domain}_{product}_live"],
]
```

| Frequency | File | Current Registrations |
|-----------|------|-----------------------|
| Hourly | `scripts/imdr_hourly.py` | FX OHLC (BidFX) |
| Daily | `scripts/imdr_daily.py` | Rates (Citi), FX Vol (Citi) |
| Weekly | `scripts/imdr_weekly.py` | Health dashboard |
| Monthly | `scripts/imdr_monthly.py` | (empty) |
| Quarterly | `scripts/imdr_quarterly.py` | (empty) |

**How schedulers work**: Each pipeline runs via subprocess in isolation. Failures are logged but don't block other pipelines. Exit code 1 if any pipeline failed.

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

Each cleaning CLI exports three builders: `build_health_checks()`, `build_quality_checks()`, `build_cleaning_rules()`. The dashboard imports all three from the cleaning CLI.

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
def get_my_coverage(reader, table, years) -> CoverageData:
    # Domain-specific SQL queries
    return CoverageData(
        tables={"per_symbol": df_cov, "row_counts": df_counts, ...},
        summary={"grand_total_rows": N, ...},
    )
```

**Examples**:
| Domain | Cleaning CLI (single diagnostic tool) |
|--------|---------------------------------------|
| FX OHLC | `scripts/fx/clean/clean_fx_fact_ohlc.py` |
| FX Vol | `scripts/fx/clean/clean_fx_fact_vol.py` |
| Rates | `scripts/rates/clean/clean_rates_fact_observation.py` |

---

## Step 10: Emailers

**Goal**: Automated notifications for ingest results and weekly dashboard.

### 10a. Ingest Formatter

Create `src/imdr/notifications/formatters/{domain}_{product}_ingest.py`:

```python
class MyIngestFormatter:
    def __init__(self):
        self._env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
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
# Import all 3 builders from the cleaning CLI (single source of truth)
from scripts.{domain}.clean.clean_{table} import (
    build_health_checks as my_health_checks,
    build_quality_checks as my_quality_checks,
    build_cleaning_rules as my_cleaning_rules,
)

def _collect_my_domain(connector, reader) -> DomainReport:
    reporter = HealthReporter(connector, "{domain}.{product}")
    years = reporter.discover_years()
    # Run health, coverage, quality, cleaning (dry-run)
    return DomainReport(...)
```

Add to main collection loop and dashboard template.

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
| 6 | `src/imdr/domains/{domain}/extractors.py` | Extractor class |
| 7 | `src/imdr/domains/{domain}/repository.py` | Repositories (dim + fact, MergeSpec) |
| 8 | `src/imdr/domains/{domain}/pipeline.py` | Pipeline class (ETL + health checks) |
| 9 | `src/imdr/domains/{domain}/store.py` | Parquet archival (optional) |
| 10 | `src/imdr/domains/{domain}/coverage.py` | Coverage analysis SQL |
| 11 | `src/imdr/domains/{domain}/clean_{table}.py` | Cleaning rule classes |
| 12 | `scripts/{domain}/{provider}/{product}_live.py` | Live ingest CLI |
| 13 | `scripts/{domain}/{provider}/{product}_historical.py` | Historical backfill CLI |
| 14 | `scripts/{domain}/clean/clean_{table}.py` | Cleaning CLI (exports `build_cleaning_rules()`, `build_health_checks()`, `build_quality_checks()`) |
| 15 | `src/imdr/notifications/formatters/{product}_ingest.py` | Email formatter |
| 16 | `src/imdr/notifications/templates/{product}_ingest.html` | Email template |
| 17 | `tests/unit/test_{domain}_*.py` | Unit tests |

### Modified Files

| # | File | Change |
|---|------|--------|
| 1 | `src/imdr/config/pipelines.yml` | Add pipeline config section |
| 2 | `scripts/run_pipeline.py` | Add to `PIPELINE_REGISTRY` |
| 3 | `scripts/imdr_{frequency}.py` | Register in scheduler |
| 4 | `scripts/imdr_clean.py` | Add to `CLEANING_SCRIPTS` |
| 5 | `scripts/imdr_health_dashboard.py` | Add domain collector + imports |

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
