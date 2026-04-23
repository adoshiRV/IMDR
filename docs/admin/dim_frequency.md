# `dbo.dim_frequency` — cross-domain ingest-cadence dimension

Small enum of ingest cadences used by every IMDR fact table going forward. Sibling of [dbo.dim_vendor](dim_vendor.md). Created 2026-04-22 via [migration 023_create_dim_frequency.sql](../../migrations/023_create_dim_frequency.sql).

---

## Rows (10)

| id | frequency_code | display_name | typical_seconds |
|---|---|---|---|
| 1 | `TICK` | Tick-level | 0 |
| 2 | `SNAPSHOT` | Intraday snapshot (ad-hoc cadence) | NULL |
| 3 | `MINUTE` | Minute bar | 60 |
| 4 | `HOURLY` | Hourly bar | 3600 |
| 5 | `DAILY` | Daily EOD | 86400 |
| 6 | `WEEKLY` | Weekly | 604800 |
| 7 | `MONTHLY` | Monthly | 2592000 |
| 8 | `QUARTERLY` | Quarterly | 7776000 |
| 9 | `ANNUAL` | Annual | 31536000 |
| 10 | `EVENT` | Event-driven | NULL |

`typical_seconds` is a nominal approximation for informational purposes only — it is **not** used to infer whether a record is late.

---

## Columns

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | TINYINT IDENTITY | NO | PK — capacity 255, plenty for an enum |
| `frequency_code` | VARCHAR(10) | NO | Natural key; uppercase |
| `display_name` | VARCHAR(40) | NO | Human-readable label |
| `typical_seconds` | INT | YES | Nominal cadence in seconds; NULL for event/snapshot |
| `created_at` | DATETIMEOFFSET | NO | DEFAULT `SYSDATETIMEOFFSET()` |
| `updated_at` | DATETIMEOFFSET | NO | DEFAULT `SYSDATETIMEOFFSET()` |

**Unique**: `uq_dbo_dim_frequency_code` on `frequency_code`.

---

## Adoption pattern

Every new fact table should include a `frequency_id` FK column:

```sql
frequency_id  TINYINT  NOT NULL,
CONSTRAINT FK_{schema}_{table}_frequency
    FOREIGN KEY (frequency_id) REFERENCES [dbo].[dim_frequency](id),
```

And an index:

```sql
CREATE INDEX ix_{schema}_{table}_frequency ON [{schema}].[{table}] (frequency_id);
```

Include `frequency_id` in the table's UNIQUE natural key so DAILY + (future) HOURLY rows can coexist without conflict:

```sql
CONSTRAINT uq_{schema}_{table}
    UNIQUE (entity_id, vendor_id, frequency_id, obs_date, ...)
```

See [schema_conventions.md §3.7](schema_conventions.md) for the full convention.

---

## Retrofitting existing tables

Existing fact tables (e.g., `fx.fact_ohlc`, `fx.fact_vol`, `rates.fact_observation`, `rates.fact_bench_rates`) don't have `frequency_id` yet. Adding it is an additive migration:

1. `ALTER TABLE ... ADD frequency_id TINYINT NULL;`
2. `UPDATE` to backfill based on each table's cadence (most are `DAILY`, `fact_ohlc` is `HOURLY`).
3. `ALTER TABLE ... ALTER COLUMN frequency_id TINYINT NOT NULL;`
4. Add FK + index.
5. Extend unique constraint to include `frequency_id`.

**Out of scope** for the current FX rate pipeline migration — document as a future retrofit per table.

---

## Example queries

```sql
-- All DAILY-cadence facts for a date
SELECT SCHEMA_NAME(o.schema_id) + '.' + o.name AS table_name
FROM sys.objects o
INNER JOIN sys.foreign_keys fk ON fk.parent_object_id = o.object_id
INNER JOIN sys.objects ref ON ref.object_id = fk.referenced_object_id
WHERE ref.name = 'dim_frequency';

-- Code → id lookup
SELECT id, frequency_code FROM dbo.dim_frequency ORDER BY id;
```

---

## Sources

| Module | Purpose |
|---|---|
| [migrations/023_create_dim_frequency.sql](../../migrations/023_create_dim_frequency.sql) | CREATE + seed |
| [src/imdr/models/frequency.py](../../src/imdr/models/frequency.py) | SQLAlchemy ORM |
| [src/imdr/schemas/frequency.py](../../src/imdr/schemas/frequency.py) | Pydantic read schema |

First consumer: [fx.fact_fx_rate](../fx/fx_rate_schema.md).
