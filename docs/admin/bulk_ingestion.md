# Bulk Ingestion Optimization

## Overview

IMDR uses a **temp-table MERGE** pattern for all high-volume database writes. Data flows through:

```
Pydantic models → staging temp table (#xxx) → MERGE into target fact table
```

This is implemented in `src/imdr/connectors/bulk.py` via `MergeSpec` (defines the schema) and `bulk_merge()` / `chunked_bulk_merge()` (executes the pattern).

## Key Optimizations

### 1. `fast_executemany` (Engine-Level)

The SQLAlchemy engine is configured with `fast_executemany=True` on the `mssql+pyodbc` dialect. This tells pyodbc to batch all parameters in a single ODBC array call instead of one round-trip per row. **This is the single biggest performance lever** — typically 10-50x faster for parameterized inserts.

- **File**: `src/imdr/connectors/mssql.py`
- **Applies to**: All pipelines (live + historical)
- **Compatible with**: `use_setinputsizes=False` (required for legacy ODBC driver DATETIMEOFFSET handling)

### 2. Chunked MERGE (`chunked_bulk_merge`)

For large loads, `chunked_bulk_merge()` breaks the dataset into configurable chunks. Each chunk gets its own session with an independent commit:

```
Chunk 1: create #staging → INSERT 5K rows → MERGE → commit
Chunk 2: create #staging → INSERT 5K rows → MERGE → commit
...
```

**Benefits**:
- Bounded lock duration on the target table (one chunk at a time)
- Reduced tempdb pressure (staging table only holds one chunk)
- Crash-safe — completed chunks are committed; MERGE is idempotent so re-running is safe

**File**: `src/imdr/connectors/bulk.py` → `chunked_bulk_merge()`

### 3. Temp-Table MERGE Pattern (`bulk_merge`)

The core write pattern used by all high-volume repositories:

1. **Create** session-scoped temp table (`#staging`)
2. **Batch INSERT** rows into staging (1000 rows per batch)
3. **MERGE** staging → target (atomic upsert on natural key)
4. **DROP** staging table

**File**: `src/imdr/connectors/bulk.py` → `bulk_merge()`

## Configuration

### `IMDR_BULK_BATCH_SIZE`

Controls the chunk size for `chunked_bulk_merge`. Set in `.env`:

```
IMDR_BULK_BATCH_SIZE=5000
```

**Default**: 5000 rows per chunk.

**Tuning guidance**:

| Batch Size | Tradeoff | Best For |
|-----------|----------|----------|
| 1,000-2,000 | Less tempdb pressure, shorter locks | Shared SQL Server instances |
| 5,000 (default) | Good balance of throughput and resource usage | Most workloads |
| 10,000-20,000 | Fewer round-trips, faster throughput | Dedicated instances with large tempdb |

**Monitor**: If you increase the batch size, watch tempdb version store growth (`sys.dm_tran_version_store_space_usage`) during backfills.

### Staging Batch Size

Within each chunk, rows are inserted into the staging table in batches of 1000 (hardcoded default in `MergeSpec.batch_size`). This can be overridden per-spec if needed but the default works well with `fast_executemany`.

## Pipeline Integration

The `chunk_size` parameter flows from settings through scripts to pipelines:

```
.env (IMDR_BULK_BATCH_SIZE=5000)
  → Settings.bulk_batch_size
    → Script passes chunk_size=settings.bulk_batch_size
      → Pipeline.__init__(chunk_size=...)
        → Pipeline.load() calls chunked_bulk_merge() if chunk_size is set
          → chunked_bulk_merge() loops bulk_merge() per chunk
```

**Pipelines with chunking support**:
- `RatesHistoricalPipeline` (rates.fact_observation)
- `RatesVolPipeline` (rates.fact_swaption_vol)
- `FXVolPipeline` (fx.fact_vol)

**Pipelines without chunking** (low volume, not needed):
- `FXSpotRatePipeline` (fx.spot_rate — uses ORM `bulk_create`)
- `FXOHLCPipeline` (fx.fact_ohlc — hourly ~30-50 rows, uses `bulk_merge` directly)

## MergeSpec Configuration

Each fact table has a `MergeSpec` defining its staging schema:

| Spec | Location | Natural Key | Audit Columns |
|------|----------|-------------|---------------|
| `_RATES_OBS_SPEC` | `domains/rates/repository.py` | curve_id, ts, quote, tenor | created_at, updated_at |
| `_SWAPTION_VOL_SPEC` | `domains/rates/repository_vol.py` | surface_id, obs_date, option_expiry, swap_tenor | created_at, updated_at |
| `_FX_VOL_SPEC` | `domains/fx/repository_vol.py` | pair_id, obs_date, strike, tenor, vol_type | created_at, updated_at |
| `_FX_OHLC_SPEC` | `domains/fx/repository.py` | ts, symbol, series, tenor | created_at only (no updated_at) |

### `audit_columns` Parameter

Tables that don't have an `updated_at` column (like `fx.fact_ohlc`) use a custom `audit_columns` dict:

```python
MergeSpec(
    ...,
    audit_columns={"created_at": "SYSDATETIMEOFFSET()"},  # No updated_at
)
```

Default (`audit_columns=None`) includes both `created_at` and `updated_at`.

### Decimal Handling

Specs with `FLOAT` staging columns automatically convert Python `Decimal` values to `float` during serialization. This is needed for schemas like `FXFactOHLCCreate` that use `Decimal` fields for prices.

## Troubleshooting

### ODBC Driver Compatibility

The project uses the legacy `SQL Server` ODBC driver (not ODBC Driver 17/18). Key constraints:

- `use_setinputsizes=False` — required; the legacy driver can't handle SQLAlchemy's `setinputsizes` for DATETIMEOFFSET
- `fast_executemany=True` — compatible with the legacy driver (proven in migration scripts)
- DATE/SMALLDATETIME columns are staged as VARCHAR(10) with ISO strings, then implicitly converted by SQL Server on MERGE

### Lock Timeouts

If you see lock timeout errors during historical backfills:
1. Reduce `IMDR_BULK_BATCH_SIZE` (e.g., from 5000 to 2000)
2. Ensure no concurrent writes to the same target table
3. Check if there are long-running analytical queries holding shared locks

### Tempdb Growth

Each chunk creates and drops a session-scoped temp table. Monitor tempdb during large backfills:
```sql
SELECT * FROM sys.dm_db_file_space_usage WHERE database_id = 2;
```

If tempdb grows excessively, reduce `IMDR_BULK_BATCH_SIZE`.

### Partial Completion

If a historical backfill crashes mid-way through chunked processing:
- Completed chunks are already committed (safe)
- Re-running the same date range is safe — MERGE is idempotent (updates existing rows, inserts new ones)
- No manual cleanup needed
