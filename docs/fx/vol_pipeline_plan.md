# FX Vol Surface — Database & Pipeline Plan

## Context

We currently ingest FX data from **BidFX** only (hourly OHLC + daily spot). Citi Velocity provides daily FX implied/realized vol surfaces covering 39 base currencies, 11 strike types, 14 tenors — ~180 tags per pair. This plan adds a normalized schema and pipeline for daily vol surface ingestion from Citi Velocity, following the same patterns established by the rates domain (dimension table + FK-linked fact table + MERGE upsert + auto-seeding).

**Goal**: Daily FX vol levels (implied + realized + spread) stored in a normalized, query-friendly schema under `[fx]`.

---

## Architecture Overview

```
fx.yml (vol config)          pipelines.yml (fx.vol entry)
     │                              │
     ▼                              ▼
FXUniverse                   PipelineConfig
  .vol_pairs()                 health_checks, unique_cols
  .build_vol_tags()
     │
     ▼
CitiVelocityFXVolExtractor
  uses shared fetch_and_parse_batched()     ─┐
  uses shared citi_response_to_rows()        ├─ connectors/citi_helpers.py
  uses shared parse_x_to_ts_utc()           ─┘
     │
     ▼
pd.DataFrame [ts, base_ccy, quote_ccy, strike, tenor, vol_type, value]
     │
     ▼
FXVolPipeline.transform()
  1. Auto-seed fx.dim_currency_pair (idempotent)
  2. Build pair_id cache
  3. Validate → list[FXVolCreate]
     │
     ▼
FXVolPipeline.load()
  FXVolRepository.bulk_upsert() — MERGE on natural key
     │
     ▼
post_load: parquet archive + quality checks
     │
     ▼
[fx].[dim_currency_pair]  ←FK→  [fx].[fact_vol]
```

---

## 0. Shared Utilities Refactor (prerequisite — eliminates cross-domain coupling)

### Problem

Three pieces of Citi-generic logic currently live in `domains/rates/`:

| Current Location | Function | Problem |
|---|---|---|
| `domains/rates/utils.py` | `parse_x_to_ts_utc()` | Citi timestamp parser, not rates-specific |
| `domains/rates/translate.py` | response→rows loop in `citi_response_to_df()` | Generic API response parsing pattern |
| `domains/rates/extractors.py` | `_fetch_batched()` batch+sleep+concat loop | Generic batching pattern |

FX vol (and future Citi datasets: FX FORWARD, DEPOSIT, SOV_CMT, etc.) needs all three. Importing from `domains/rates/` into `domains/fx/` creates a cross-domain dependency — wrong.

### Solution: `src/imdr/connectors/citi_helpers.py` (NEW)

```python
"""Shared Citi Velocity helpers — domain-agnostic.

Used by: rates extractor, rates translate, fx vol extractor, fx vol translate,
and any future Citi-sourced pipeline.
"""

# ── 1. Timestamp parser (moved from domains/rates/utils.py) ──
def parse_x_to_ts_utc(x: int) -> datetime:
    """Infer Citi x-axis format by digit count → UTC datetime."""
    # Exact same code, just relocated

# ── 2. Generic response → rows parser ──
def citi_response_to_rows(
    resp: dict,
    tag_parser: Callable[[str], dict | None],
    parse_x: Callable[[int], datetime] = parse_x_to_ts_utc,
) -> list[dict]:
    """Parse Citi Historical API response into flat row dicts.

    tag_parser is the ONLY domain-specific piece:
      rates: tag → {ccy, curve, quote, tenor}
      fx vol: tag → {base_ccy, quote_ccy, strike, tenor, vol_type}

    Returns list of dicts, each: {ts, **tag_fields, value}
    """
    if resp.get("status") != "OK":
        raise RuntimeError(f"API status not OK: {resp}")
    rows = []
    for tag, series in resp.get("body", {}).items():
        if not isinstance(series, dict) or series.get("type") == "ERROR":
            continue
        parsed = tag_parser(tag)
        if parsed is None:
            continue
        for x, c in zip(series.get("x", []), series.get("c", [])):
            if c is None:
                continue
            rows.append({"ts": parse_x(x), **parsed, "value": float(c)})
    return rows

# ── 3. Batched fetch with rate limiting ──
def fetch_and_parse_batched(
    client: "CitiVelocityClient",
    tags: list[str],
    start: datetime, end: datetime,
    frequency: str, batch_size: int, rate_limit: float,
    response_parser: Callable[[dict], pd.DataFrame],
) -> pd.DataFrame:
    """Fetch tags in batches, respecting rate limits, concat results.

    response_parser converts a single API response dict → DataFrame.
    Each domain provides its own parser.
    """
    frames = []
    for i in range(0, len(tags), batch_size):
        batch = tags[i : i + batch_size]
        resp = client.fetch_historical(batch, start, end, frequency)
        df = response_parser(resp)
        if not df.empty:
            frames.append(df)
        if i + batch_size < len(tags):
            time.sleep(rate_limit)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
```

### Update existing rates code (zero behavior change)

**`domains/rates/utils.py`** — Remove `parse_x_to_ts_utc` body, re-export for backward compat:
```python
# Keep existing imports working — just re-export from new location
from imdr.connectors.citi_helpers import parse_x_to_ts_utc  # noqa: F401
```

**`domains/rates/translate.py`** — `citi_response_to_df()` delegates to shared parser:
```python
from imdr.connectors.citi_helpers import citi_response_to_rows

def citi_response_to_df(resp, parse_x, universe=None):
    if universe is None:
        universe = get_rates_universe()
    rows = citi_response_to_rows(
        resp,
        tag_parser=lambda t: citi_tag_to_internal(t, universe),
        parse_x=parse_x,
    )
    df = pd.DataFrame(rows, columns=COLUMNS) if rows else pd.DataFrame(columns=COLUMNS)
    if not df.empty:
        df = df.sort_values(["ccy", "curve", "quote", "tenor", "ts"]).reset_index(drop=True)
    return df
```

**`domains/rates/extractors.py`** — `_fetch_batched()` delegates to shared utility:
```python
from imdr.connectors.citi_helpers import fetch_and_parse_batched

def _fetch_batched(self, tags, start, end, frequency):
    return fetch_and_parse_batched(
        self._client, tags, start, end, frequency,
        self._batch_size, self._rate_limit,
        response_parser=lambda resp: citi_response_to_df(resp, parse_x_to_ts_utc, self._universe),
    )
```

**Verification**: All 268 existing tests pass. Same behavior, just cleaner imports.

---

## 1. SQL Migrations

### `migrations/004_create_fx_dim_currency_pair.sql`

```sql
CREATE TABLE [fx].[dim_currency_pair] (
    id            INT IDENTITY(1,1) PRIMARY KEY,
    base_ccy      VARCHAR(3)   NOT NULL,
    quote_ccy     VARCHAR(3)   NOT NULL,
    ccy_class     VARCHAR(20)  NOT NULL,  -- g10, em_ndf, em_deliverable
    created_at    DATETIMEOFFSET NOT NULL DEFAULT SYSDATETIMEOFFSET(),
    updated_at    DATETIMEOFFSET NOT NULL DEFAULT SYSDATETIMEOFFSET(),
    CONSTRAINT uq_fx_dim_currency_pair UNIQUE (base_ccy, quote_ccy)
);
```

- Seeded from `fx.yml` universe — initially 17 rows (existing USD crosses)
- Expandable for vol-specific crosses (EUR/GBP, AUD/NZD) — just add rows, no DDL
- **Future**: spot_rates and fact_ohlc can FK to this same dim (not in this PR)

### `migrations/005_create_fx_fact_vol.sql`

```sql
CREATE TABLE [fx].[fact_vol] (
    id            INT IDENTITY(1,1) PRIMARY KEY,
    pair_id       INT            NOT NULL REFERENCES [fx].[dim_currency_pair](id),
    obs_date      DATE           NOT NULL,
    strike        VARCHAR(15)    NOT NULL,  -- ATM, 25RR, 10RR, 25STR, 10STR, STRIKE_C10, ...
    tenor         VARCHAR(5)     NOT NULL,  -- 1M, 3M, 1Y, ...
    vol_type      VARCHAR(10)    NOT NULL,  -- IMPLIED, REALISED, SPREAD
    value         FLOAT          NOT NULL,
    created_at    DATETIMEOFFSET NOT NULL DEFAULT SYSDATETIMEOFFSET(),
    updated_at    DATETIMEOFFSET NOT NULL DEFAULT SYSDATETIMEOFFSET(),
    CONSTRAINT uq_fx_fact_vol UNIQUE (pair_id, obs_date, strike, tenor, vol_type)
);

CREATE INDEX ix_fx_fact_vol_obs_date ON [fx].[fact_vol] (obs_date);
CREATE INDEX ix_fx_fact_vol_pair_date ON [fx].[fact_vol] (pair_id, obs_date);
```

**Design rationale**:
- `obs_date` is DATE not DATETIMEOFFSET — daily granularity, no time component needed
- `strike` + `tenor` + `vol_type` as VARCHAR columns (not separate dims) — 11 × 14 × 3 = small fixed enums, dimension tables would add join complexity for no benefit
- `pair_id` FK enforces referential integrity to dim
- UNIQUE constraint doubles as the MERGE key for upsert
- Two indexes: one for date-range scans, one for pair+date lookups

---

## 2. ORM Models

### `src/imdr/models/fx_vol.py` (NEW)

```python
class FXCurrencyPair(Base):
    """Currency pair dimension — shared across FX domain."""
    __tablename__ = "dim_currency_pair"
    __table_args__ = (
        UniqueConstraint("base_ccy", "quote_ccy", name="uq_fx_dim_currency_pair"),
        {"schema": "fx"},
    )
    base_ccy: Mapped[str]    = mapped_column(String(3), nullable=False)
    quote_ccy: Mapped[str]   = mapped_column(String(3), nullable=False)
    ccy_class: Mapped[str]   = mapped_column(String(20), nullable=False)

    vol_observations: Mapped[list["FXFactVol"]] = relationship(back_populates="pair")


class FXFactVol(Base):
    """Daily FX vol surface observations."""
    __tablename__ = "fact_vol"
    __table_args__ = (
        UniqueConstraint("pair_id", "obs_date", "strike", "tenor", "vol_type",
                         name="uq_fx_fact_vol"),
        {"schema": "fx"},
    )
    pair_id: Mapped[int]     = mapped_column(Integer, ForeignKey("fx.dim_currency_pair.id"), nullable=False)
    obs_date: Mapped[date]   = mapped_column(Date, nullable=False, index=True)
    strike: Mapped[str]      = mapped_column(String(15), nullable=False)
    tenor: Mapped[str]       = mapped_column(String(5), nullable=False)
    vol_type: Mapped[str]    = mapped_column(String(10), nullable=False)
    value: Mapped[float]     = mapped_column(Float, nullable=False)

    pair: Mapped[FXCurrencyPair] = relationship(back_populates="vol_observations")
```

Pattern follows `RatesCurve` → `RatesObservation` exactly.

---

## 3. Pydantic Schemas

### `src/imdr/schemas/fx_vol.py` (NEW)

```python
ALLOWED_STRIKES = {"ATM", "25RR", "10RR", "25STR", "10STR",
                   "STRIKE_C10", "STRIKE_C25", "STRIKE_C35",
                   "STRIKE_P10", "STRIKE_P25", "STRIKE_P35"}
ALLOWED_VOL_TYPES = {"IMPLIED", "REALISED", "SPREAD"}

class FXCurrencyPairCreate(BaseModel):
    base_ccy: str   # Field(min_length=3, max_length=3), validator: uppercase
    quote_ccy: str  # Field(min_length=3, max_length=3), validator: uppercase
    ccy_class: str  # validated against {g10, em_ndf, em_deliverable}

class FXVolCreate(BaseModel):
    pair_id: int    # FK
    obs_date: date
    strike: str     # validated against ALLOWED_STRIKES
    tenor: str      # e.g. "1M", "3M", "1Y"
    vol_type: str   # validated against ALLOWED_VOL_TYPES
    value: float

class FXCurrencyPairResponse(FXCurrencyPairCreate):  # + id, created_at, updated_at
class FXVolResponse(FXVolCreate):                      # + id, created_at, updated_at
```

---

## 4. Universe Extension

### `src/imdr/universe/fx.yml` — add `vol` section

```yaml
vol:
  # Pairs to track — uses Citi's ccy ordering (not market convention)
  # Start with G10 majors; expand later
  pairs:
    - [EUR, USD]
    - [GBP, USD]
    - [USD, JPY]
    - [AUD, USD]
    - [NZD, USD]
    - [USD, CAD]
    - [USD, CHF]
    - [USD, NOK]
    - [USD, SEK]
    - [USD, CNH]

  strikes:
    - ATM
    - 25RR
    - 10RR
    - 25STR
    - 10STR
    - STRIKE_C25
    - STRIKE_P25

  tenors:
    - 1W
    - 1M
    - 2M
    - 3M
    - 6M
    - 9M
    - 1Y
    - 2Y
    - 5Y
    - 10Y

  # ATM has 3 leaf types; all others have only IMPLIED
  vol_types:
    ATM: [IMPLIED, REALISED, SPREAD]
    _default: [IMPLIED]

  tag_template: "FX.VOL.{ccy1}.{ccy2}.{strike}.{tenor}.{vol_type}.CITI"
```

**Tag count**: 10 pairs × [(7 strikes × 10 tenors × 1) + (10 tenors × 2 ATM extras)] = 10 × 90 = **900 tags** → 9 API batches → ~10s per run.

### `src/imdr/universe/fx.py` — extend FXUniverse

Add new config models:
```python
class VolConfig(BaseModel):
    pairs: list[list[str]]
    strikes: list[str]
    tenors: list[str]
    vol_types: dict[str, list[str]]  # strike→types mapping, _default key
    tag_template: str
```

Add to `FXUniverseConfig`:
```python
vol: VolConfig | None = None
```

Add methods to `FXUniverse`:
```python
def vol_pairs(self) -> list[tuple[str, str]]
def vol_strikes(self) -> list[str]
def vol_tenors(self) -> list[str]
def vol_types_for_strike(self, strike: str) -> list[str]
def build_vol_tags(self, ccy1: str, ccy2: str) -> list[str]
def build_all_vol_tags(self) -> list[str]
def vol_pair_entries(self) -> list[FXCurrencyPairCreate]  # for dim seeding
```

---

## 5. Domain Code

All new FX vol files in `src/imdr/domains/fx/` alongside existing code.

### `src/imdr/domains/fx/vol_translate.py` (NEW)

Tag parser + response converter. **Only domain-specific code is `citi_vol_tag_to_internal()`** — everything else delegates to shared helpers.

```python
from imdr.connectors.citi_helpers import citi_response_to_rows, parse_x_to_ts_utc

COLUMNS = ["ts", "base_ccy", "quote_ccy", "strike", "tenor", "vol_type", "value"]

def citi_vol_tag_to_internal(tag: str) -> dict | None:
    """Parse FX.VOL.EUR.USD.ATM.1M.IMPLIED.CITI → dict of column values.
    This is the ONLY domain-specific function needed."""
    parts = tag.split(".")
    if len(parts) != 8 or parts[0] != "FX" or parts[1] != "VOL":
        return None
    return {
        "base_ccy": parts[2], "quote_ccy": parts[3],
        "strike": parts[4], "tenor": parts[5], "vol_type": parts[6],
    }

def citi_vol_response_to_df(resp: dict) -> pd.DataFrame:
    """Convert Citi Historical response → DataFrame. Delegates to shared parser."""
    rows = citi_response_to_rows(resp, tag_parser=citi_vol_tag_to_internal)
    df = pd.DataFrame(rows, columns=COLUMNS) if rows else pd.DataFrame(columns=COLUMNS)
    if not df.empty:
        df = df.sort_values(["base_ccy", "quote_ccy", "strike", "tenor", "ts"]).reset_index(drop=True)
    return df
```

Compare with `rates/translate.py` — **zero duplicated parsing logic**. Both call `citi_response_to_rows()` with their own tag parser.

### `src/imdr/domains/fx/extractors_vol.py` (NEW)

Uses `fetch_and_parse_batched()` — **zero duplicated batch loop**.

```python
from imdr.connectors.citi_helpers import fetch_and_parse_batched
from imdr.domains.fx.vol_translate import COLUMNS, citi_vol_response_to_df

class CitiVelocityFXVolExtractor:
    """Extract FX vol surfaces from Citi Velocity Historical API."""

    def __init__(self, client, settings, universe):
        self._client = client
        self._batch_size = settings.citi_batch_size
        self._rate_limit = settings.citi_rate_limit_sec
        self._universe = universe

    def extract(self, start, end, pairs=None, frequency="DAILY") -> pd.DataFrame:
        vol_pairs = pairs or self._universe.vol_pairs()
        frames = []
        for ccy1, ccy2 in vol_pairs:
            tags = self._universe.build_vol_tags(ccy1, ccy2)
            df = fetch_and_parse_batched(
                self._client, tags, start, end, frequency,
                self._batch_size, self._rate_limit,
                response_parser=citi_vol_response_to_df,  # domain-specific parser
            )
            if not df.empty:
                frames.append(df)
        if not frames:
            return pd.DataFrame(columns=COLUMNS)
        return pd.concat(frames, ignore_index=True)
```

Compare with `CitiVelocityRatesExtractor._fetch_batched()` — **same shared utility, different parser**.

### `src/imdr/domains/fx/repository_vol.py` (NEW)

```python
class FXCurrencyPairRepository:
    """Data access for [fx].[dim_currency_pair].
    Same pattern as RatesCurveRepository — session-injected, idempotent seed."""
    def __init__(self, session): ...
    def get_by_key(self, base_ccy, quote_ccy) -> FXCurrencyPair | None: ...
    def get_or_create(self, data: FXCurrencyPairCreate) -> FXCurrencyPair: ...
    def all(self) -> Sequence[FXCurrencyPair]: ...
    def bulk_seed_from_universe(self, pairs: list[FXCurrencyPairCreate]) -> int:
        """Idempotent: skip existing, flush new. ~10 lines."""

class FXVolRepository:
    """Data access for [fx].[fact_vol]."""
    def __init__(self, session): ...
    def bulk_upsert(self, items: list[FXVolCreate]) -> int:
        """SQL MERGE via #fx_vol_staging temp table.
        Natural key: (pair_id, obs_date, strike, tenor, vol_type)
        Same temp→MERGE pattern as RatesObservationRepository but with
        different columns/table — kept per-repo (30 lines) because
        parameterizing MERGE SQL requires dynamic column lists with
        injection risk. If a 3rd table needs this, extract generic helper then."""
    def count_by_date(self, obs_date) -> int: ...
```

### `src/imdr/domains/fx/pipeline_vol.py` (NEW)

```python
class FXVolPipeline(BasePipeline[pd.DataFrame, list[FXVolCreate], int]):
    pipeline_name = "fx.vol"
    domain = "fx"

    def __init__(self, connector, settings, universe, start, end, pairs=None):
        super().__init__(connector)
        self._settings = settings
        self._universe = universe
        self._config = get_pipeline_config(self.pipeline_name)
        self._start = start
        self._end = end
        self._pairs = pairs
        self._raw_df = None

    def extract(self) -> pd.DataFrame:
        with CitiVelocityClient(self._settings) as client:
            extractor = CitiVelocityFXVolExtractor(client, self._settings, self._universe)
            df = extractor.extract(self._start, self._end, self._pairs)
        self._raw_df = df
        return df

    def transform(self, raw) -> list[FXVolCreate]:
        # 1. Auto-seed dim_currency_pair (same pattern as rates dim_curve seeding)
        pairs_to_seed = self._universe.vol_pair_create_entries()
        with self._connector.session() as session:
            pair_repo = FXCurrencyPairRepository(session)
            pair_repo.bulk_seed_from_universe(pairs_to_seed)
            pair_id_cache = {(p.base_ccy, p.quote_ccy): p.id for p in pair_repo.all()}

        # 2. Resolve pair_ids, validate via Pydantic
        observations = []
        for _, row in raw.iterrows():
            pair_id = pair_id_cache.get((row["base_ccy"], row["quote_ccy"]))
            if pair_id is None:
                continue
            observations.append(FXVolCreate(
                pair_id=pair_id, obs_date=row["ts"].date(),
                strike=row["strike"], tenor=row["tenor"],
                vol_type=row["vol_type"], value=row["value"],
            ))
        return observations

    def load(self, data) -> int:
        with self._connector.session() as session:
            return FXVolRepository(session).bulk_upsert(data)

    def post_load(self, result, data):
        # Parquet archive: data/parquet/fx/fact_vol/{base}_{quote}/{YYYY-MM}.parquet
        # Quality: SymbolRangeCheck on vol values (0.1–200.0%)

    def get_health_checks(self) -> list[HealthCheck]:
        cfg = self._config.health_checks
        return [
            RowCountCheck(FXFactVol, self._config.date_column, cfg.row_count_min),
            NullCheck(FXFactVol, self._config.required_columns, self._config.date_column),
            DuplicateCheck(FXFactVol, self._config.unique_columns, self._config.date_column),
            FreshnessCheck(FXFactVol, "created_at", cfg.max_staleness_hours),
        ]

    def get_run_context(self):
        return {"run_date": self._start.date()}
```

---

## 6. Pipeline Config

### `src/imdr/config/pipelines.yml` — add `fx.vol`

```yaml
fx.vol:
  domain: fx
  target_schema: fx
  target_table: fact_vol
  date_column: obs_date
  unique_columns:
    - pair_id
    - obs_date
    - strike
    - tenor
    - vol_type
  required_columns:
    - pair_id
    - obs_date
    - strike
    - tenor
    - vol_type
    - value
  health_checks:
    row_count_min: 50
    max_staleness_hours: 48
    value_ranges:
      value: { min: 0.1, max: 200.0 }
  sources:
    citivelocity:
      type: rest
      auth_type: bearer
```

### `scripts/run_pipeline.py` — add `fx.vol` to registry

```python
def _build_fx_vol_pipeline(connector, args):
    """Build FX Vol pipeline."""
    # Parse --start, --end, optional --pairs
    # Return FXVolPipeline(connector, settings, universe, start, end, pairs)

PIPELINE_REGISTRY["fx.vol"] = _build_fx_vol_pipeline
```

CLI usage:
```
python -m scripts.run_pipeline fx.vol --start 2024-01-01 --end 2024-12-31
python -m scripts.run_pipeline fx.vol --start 2026-03-10 --end 2026-03-10  # single day
```

---

## 7. Reusability Map

### Shared utilities (extracted in step 0 — used by rates AND fx vol)

| Utility | Location | Consumers |
|---|---|---|
| `parse_x_to_ts_utc()` | `connectors/citi_helpers.py` | rates translate, **fx vol translate**, any future Citi pipeline |
| `citi_response_to_rows()` | `connectors/citi_helpers.py` | rates translate, **fx vol translate** |
| `fetch_and_parse_batched()` | `connectors/citi_helpers.py` | rates extractor, **fx vol extractor** |

### Existing shared (no changes needed)

| Component | File | Consumers |
|---|---|---|
| `CitiVelocityClient` | `connectors/citi_velocity.py` | rates pipeline, **fx vol pipeline** |
| `BasePipeline` | `pipelines/base.py` | all pipelines |
| Health checks | `healthchecks/checks.py` | all pipelines |
| `MSSQLConnector` | `connectors/mssql.py` | all pipelines |
| `get_settings()` | `config/settings.py` | all pipelines |

### Domain-specific (FX vol only — cannot be shared)

| Component | Why it's unique |
|---|---|
| `citi_vol_tag_to_internal()` | 8-part FX.VOL tag format (vs 5-part RATES tags) |
| `FXVolCreate` schema | strike/tenor/vol_type enum validation |
| `FXFactVol` ORM | DATE obs_date, 5-column natural key |
| `FXVolRepository.bulk_upsert()` | MERGE SQL with vol-specific columns (30 lines, kept per-repo) |

### Reusable for future FX Citi datasets (FORWARD, DEPOSIT, CARRY, etc.)

| Component | How future datasets benefit |
|---|---|
| `fx.dim_currency_pair` table | Any pair-based fact table FKs here — no new dim needed |
| `FXCurrencyPairRepository` | Same seed/lookup for any FX pair-keyed dataset |
| `citi_helpers.py` utilities | Same batching, response parsing, timestamp parsing |
| `FXUniverse` pattern | Add `forward_pairs()`, `deposit_ccys()` following same YAML+methods pattern |
| `pipelines.yml` + registry | Add `fx.forward`, `fx.deposit` entries — same wiring |

---

## 8. File Summary — All Changes

### New files (9)

| File | Description |
|---|---|
| `src/imdr/connectors/citi_helpers.py` | **Shared**: parse_x, response→rows, batched fetch |
| `migrations/004_create_fx_dim_currency_pair.sql` | Dimension table DDL |
| `migrations/005_create_fx_fact_vol.sql` | Fact table DDL |
| `src/imdr/models/fx_vol.py` | ORM: FXCurrencyPair + FXFactVol |
| `src/imdr/schemas/fx_vol.py` | Pydantic: FXCurrencyPairCreate + FXVolCreate + Responses |
| `src/imdr/domains/fx/vol_translate.py` | Tag parser + response→DataFrame (uses shared helpers) |
| `src/imdr/domains/fx/extractors_vol.py` | Extractor (uses shared batched fetch) |
| `src/imdr/domains/fx/repository_vol.py` | FXCurrencyPairRepo + FXVolRepo |
| `src/imdr/domains/fx/pipeline_vol.py` | FXVolPipeline ETL orchestration |

### Modified files (7)

| File | Change |
|---|---|
| `src/imdr/domains/rates/utils.py` | Remove `parse_x_to_ts_utc` body → re-export from `citi_helpers` |
| `src/imdr/domains/rates/translate.py` | Use `citi_response_to_rows()` instead of inline loop |
| `src/imdr/domains/rates/extractors.py` | Use `fetch_and_parse_batched()` instead of inline loop |
| `src/imdr/universe/fx.yml` | Add `vol:` section |
| `src/imdr/universe/fx.py` | Add VolConfig, vol_* methods to FXUniverse |
| `src/imdr/config/pipelines.yml` | Add `fx.vol` pipeline config |
| `scripts/run_pipeline.py` | Add `fx.vol` factory + registry entry |

---

## 9. Connection Map

```
                    fx.yml
                   ┌──────┐
                   │ vol:  │
                   │ pairs │──────────────────────┐
                   │strikes│                      │
                   │tenors │                      │
                   └───┬───┘                      │
                       │                          │
                  FXUniverse                      │
              vol_pairs(), build_vol_tags()        │
                       │                          │
            ┌──────────┴──────────┐               │
            │                     │               │
    CitiVelocityClient    FXCurrencyPairCreate    │
    .fetch_historical()   (for dim seeding)       │
            │                     │               │
            ▼                     ▼               │
    ┌──────────────────────────┐  │               │
    │ connectors/citi_helpers  │  │               │
    │ fetch_and_parse_batched()│ ◄── shared with  │
    │ citi_response_to_rows()  │    rates domain  │
    │ parse_x_to_ts_utc()     │                   │
    └───────────┬──────────────┘                  │
                │                                 │
    ┌───────────┴──────┐                          │
    │ vol_translate.py │                          │
    │ citi_vol_tag_to  │ ◄── ONLY domain-specific │
    │ _internal()      │     logic needed         │
    └───────┬──────────┘                          │
            │                                     │
            ▼                                     │
     pd.DataFrame                                 │
     [ts, base_ccy, quote_ccy,                    │
      strike, tenor, vol_type,                    │
      value]                                      │
            │                                     │
            ▼                                     │
     ┌─────────────────────────────┐              │
     │   FXVolPipeline.transform() │              │
     │  1. seed dim_currency_pair  │◄─────────────┘
     │  2. build pair_id cache     │
     │  3. validate → FXVolCreate  │
     └────────────┬────────────────┘
                  │
                  ▼
     ┌─────────────────────────┐
     │   FXVolPipeline.load()  │
     │  FXVolRepository        │
     │  .bulk_upsert()         │
     │  (MERGE on natural key) │
     └────────────┬────────────┘
                  │
         ┌────────┴────────┐
         │                 │
         ▼                 ▼
  [fx].[dim_currency_pair] [fx].[fact_vol]
  ┌──────────────────┐  ┌────────────────────────────┐
  │ id (PK)          │  │ id (PK)                    │
  │ base_ccy         │  │ pair_id (FK→dim)           │
  │ quote_ccy        │  │ obs_date (DATE)            │
  │ ccy_class        │  │ strike                     │
  │ created_at       │  │ tenor                      │
  │ updated_at       │  │ vol_type                   │
  └──────────────────┘  │ value                      │
       ▲                │ created_at                 │
       │ shared dim     │ updated_at                 │
       │ for future:    │ UNIQUE(pair_id, obs_date,  │
       │ FORWARD,       │   strike, tenor, vol_type) │
       │ DEPOSIT, etc.  └────────────────────────────┘
```

---

## 10. Verification Plan

### Unit Tests (new)
- `test_citi_helpers.py`: parse_x_to_ts_utc (existing test coverage moves here), citi_response_to_rows (mock responses), fetch_and_parse_batched (mock client)
- `test_fx_vol_translate.py`: citi_vol_tag_to_internal (valid 8-part tags, malformed, wrong prefix, edge cases)
- `test_fx_vol_schemas.py`: Pydantic validation (ALLOWED_STRIKES, ALLOWED_VOL_TYPES, uppercase, bounds)
- `test_fx_universe_vol.py`: vol_pairs(), build_vol_tags(), vol_types_for_strike(), tag count = 900
- `test_fx_vol_repository.py`: bulk_seed idempotency, bulk_upsert (mock session)

### Existing Tests (must still pass after refactor)
- All 268 existing tests — verify after moving parse_x_to_ts_utc and refactoring rates imports
- Re-export in `rates/utils.py` ensures backward compatibility

### Integration Test (manual)
1. Run migrations 004 + 005 against IMDR database
2. Single-day pipeline run:
   ```
   python -m scripts.run_pipeline fx.vol --start 2026-03-10 --end 2026-03-10
   ```
3. Verify:
   - `dim_currency_pair`: 10 rows (vol pairs)
   - `fact_vol`: ~900 rows (10 pairs × 90 tags/pair)
   - Health checks pass (row count, nulls, duplicates, freshness)
   - FK integrity (no orphan pair_ids)
4. Idempotency: re-run same date → row count unchanged (MERGE updates, not duplicates)

### Query Validation
```sql
-- EUR/USD ATM term structure
SELECT p.base_ccy, p.quote_ccy, v.tenor, v.vol_type, v.value
FROM [fx].[fact_vol] v
JOIN [fx].[dim_currency_pair] p ON p.id = v.pair_id
WHERE p.base_ccy = 'EUR' AND p.quote_ccy = 'USD'
  AND v.strike = 'ATM' AND v.obs_date = '2026-03-10'
ORDER BY v.vol_type, v.tenor;

-- Vol smile: EUR/USD 1M implied
SELECT v.strike, v.value
FROM [fx].[fact_vol] v
JOIN [fx].[dim_currency_pair] p ON p.id = v.pair_id
WHERE p.base_ccy = 'EUR' AND p.quote_ccy = 'USD'
  AND v.tenor = '1M' AND v.vol_type = 'IMPLIED' AND v.obs_date = '2026-03-10'
ORDER BY v.strike;
```

---

## 11. Build Order

1. **Shared utilities** (`citi_helpers.py` + rates refactor) — extract, update imports, run all 268 tests
2. **Migrations** (004, 005) — create tables
3. **Models** (`fx_vol.py`) — ORM definitions
4. **Schemas** (`fx_vol.py`) — Pydantic validation
5. **Universe** (modify `fx.yml` + `fx.py`) — vol config + methods
6. **Translate** (`vol_translate.py`) — tag parsing using shared helpers
7. **Repository** (`repository_vol.py`) — data access + MERGE
8. **Extractor** (`extractors_vol.py`) — Citi API fetching using shared batched fetch
9. **Pipeline** (`pipeline_vol.py`) — ETL orchestration
10. **Config** (modify `pipelines.yml` + `run_pipeline.py`) — registration
11. **Tests** — new unit tests + verify existing all pass
12. **Verify** — end-to-end run against live API
