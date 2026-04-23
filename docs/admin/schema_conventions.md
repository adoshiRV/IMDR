# IMDR Schema Conventions

Rules that apply to every new table, column, and constraint in the IMDR database. Update this doc whenever a convention changes — do not bury conventions in individual migrations.

---

## 1. Never use SQL-reserved or ambiguous column names

Column names must not collide with:

- **SQL standard / T-SQL reserved words** — e.g. `USER`, `ORDER`, `GROUP`, `TYPE`, `KEY`, `VALUE`, `COUNT`, `DATE`, `TIME`, `YEAR`, `MONTH`, `DAY`, `CURRENT`, `PUBLIC`, `SYSTEM`.
- **ODBC reserved words** — including `NAME` (conflicts with `USER_NAME()`, `COL_NAME()`, `DB_NAME()`, `SCHEMA_NAME()`, `OBJECT_NAME()` etc. and is listed as ODBC-reserved).
- **Ambiguous system words** — `STATUS`, `STATE`, `OWNER`, `SOURCE`, `TARGET` (legal but routinely require bracketing and read as system-level).

Official reference: [Microsoft — Reserved Keywords (Transact-SQL)](https://learn.microsoft.com/en-us/sql/t-sql/language-elements/reserved-keywords-transact-sql).

### Preferred alternatives

| Avoid | Use instead |
|-------|-------------|
| `name` | `display_name` |
| `type` | `{entity}_type` (e.g. `vendor_type`) |
| `status` | `run_status`, `state_code` |
| `date` | `obs_date`, `created_at`, `event_date` |
| `value` | `observed_value`, `{metric}_value`, or the domain metric name (`vol`, `rate`, `price`) |
| `key` | `natural_key`, `{entity}_code` |
| `count` | `row_count`, `{noun}_count` |
| `order` | `sort_order`, `rank` |

### Rationale

Using reserved or ambiguous identifiers forces every query to bracket the column (`[name]`) and breaks tooling that autogenerates SQL — ORM reflection, pandas `read_sql`, MERGE staging, ad-hoc reports. One careless unbracketed reference in a future migration or script silently fails or returns the wrong thing.

---

## 2. Naming patterns

- **Schema prefix**: `dbo.` for cross-domain dimensions; domain schema (`rates.`, `fx.`, `equities.`, `commodities.`, `calendar.`, `audit.`) for domain-specific tables.
- **Tables**: `dim_{noun}` for dimensions, `fact_{noun}` for facts.
- **Foreign keys**: column name matches the referenced dimension — `vendor_id` → `dbo.dim_vendor(id)`, `currency_id` → `dbo.dim_currency(id)`, `market_id` → `dbo.dim_market(id)`.
- **Natural-key columns**: short, domain-standard codes — `code VARCHAR(3)` for ISO currencies, `vendor_code VARCHAR(30)` for vendors.
- **Timestamps**: `created_at` / `updated_at`, both `DATETIMEOFFSET NOT NULL DEFAULT SYSDATETIMEOFFSET()`.
- **Constraint names**: `uq_{schema}_{table}_{cols}`, `FK_{schema}_{table}_{ref}`, `ix_{schema}_{table}_{cols}`.

---

## 3. New-table checklist

Every new table must satisfy the following before the migration is merged. If an item does not apply, state why in the migration header comment.

1. **Primary key `id`** — surrogate integer PK named `id`. Size by expected cardinality: `TINYINT` (≤255 rows, e.g. small enums/dimensions), `SMALLINT` (≤32K), `INT` (default for facts), `BIGINT` only when `INT` is genuinely insufficient. Always `IDENTITY(1,1) NOT NULL PRIMARY KEY`.
2. **No reserved/ambiguous column names** — verify every column against the list in §1 and the [T-SQL reserved keywords reference](https://learn.microsoft.com/en-us/sql/t-sql/language-elements/reserved-keywords-transact-sql). If in doubt, rename.
3. **`created_at`** — `DATETIMEOFFSET NOT NULL DEFAULT SYSDATETIMEOFFSET()`. Required on every table (dim and fact).
4. **`updated_at`** — `DATETIMEOFFSET NOT NULL DEFAULT SYSDATETIMEOFFSET()`. Required on every table; update via trigger or application layer on `UPDATE`.
5. **Geographical market FK** — if the row is scoped to a trading venue, country, or market session, add `market_id TINYINT` → `calendar.dim_market(id)` (surrogate id added in [migration 026](../../migrations/026_add_market_id_fk_to_dims.sql); `market_code` remains as the PK + natural key for legacy compatibility). Do not embed country/market strings inline on facts. If the table is truly market-agnostic (e.g. global FX EOD, global commodities spot), document why in the migration header.
6. **Currency FK** — if the row references a currency (single-ccy) or pair (cross-ccy), add `currency_id` → `dbo.dim_currency(id)` or `currency_pair_id` → `fx.dim_currency_pair(id)`. Do not store `VARCHAR(3)` currency codes on fact tables.
7. **Frequency FK** — if the row has an ingest cadence (tick / snapshot / minute / hourly / daily / weekly / monthly / quarterly / annual / event), add `frequency_id` → `dbo.dim_frequency(id)`. Do not store cadence as a string. Include `frequency_id` in the natural-key tuple so rows at different frequencies can coexist per entity + date. See [dim_frequency.md](dim_frequency.md) for enum values and adoption pattern.
8. **Vendor FK** — if the row came from an external data source, add `vendor_id` → `dbo.dim_vendor(id)` and include it in the natural-key tuple. See [dim_vendor.md](dim_vendor.md).

---

## 4. Migration hygiene

- Sequentially numbered: `{NNN}_{description}.sql` under `migrations/`.
- **Additive only** — add columns, dimensions, indexes, and constraints. Never `DROP TABLE`/`DROP DATABASE`. Dropping a legacy column requires an explicit, separately numbered migration after all consumers have cut over.
- Use `GO` to separate batches when subsequent statements depend on schema changes committed by the prior batch (e.g. `ALTER ADD COLUMN` → `UPDATE` → `ALTER NOT NULL`).
- Always verify backfill completeness before tightening nullability — use `THROW 51000, '...', 1;` inside an `IF EXISTS (...)` guard so a broken migration fails loudly.

---

## 5. DBMS optimization patterns

IMDR is an append-heavy, range-scan-heavy time-series workload on SQL Server. The guidance below applies to **new tables** unless noted. Retrofitting existing fact tables (which are currently heaps with no compression or partitioning) is a separate, additive-migration decision per table.

Research references: [Columnstore design guidance](https://learn.microsoft.com/en-us/sql/relational-databases/indexes/columnstore-indexes-design-guidance), [Partitioned tables and indexes](https://learn.microsoft.com/en-us/sql/relational-databases/partitions/partitioned-tables-and-indexes), [Data compression](https://learn.microsoft.com/en-us/sql/relational-databases/data-compression/data-compression).

### 5.1 Clustered index — match the read pattern, not the PK

The surrogate `id` is the **primary key**, but not necessarily the **clustered index**. For fact tables, cluster on the natural access path:

- **Time-series facts** → cluster on `(obs_date, {entity}_id)`. Range scans by date dominate (see `date_range_scan()` in [reader.py](../../src/imdr/connectors/reader.py)); surrogate-keyed clustering scatters same-day rows across the B-tree.
- **Dimensions** → cluster on `id`. Lookups are point reads by FK.
- Declare the PK as `NONCLUSTERED` when the clustered index is something else: `CONSTRAINT pk_... PRIMARY KEY NONCLUSTERED (id)`.

### 5.2 Data compression

Enable `PAGE` compression on every new fact table. Market data is highly repetitive (same symbols, tenors, dates) and typically compresses 3–5×, cutting both storage and buffer-pool pressure.

```sql
CREATE TABLE rates.fact_swaption_vol (...)
WITH (DATA_COMPRESSION = PAGE);
```

Fall back to `ROW` only if PAGE proves CPU-bound (unlikely for batch ingest). Once a partition is closed (no further writes), consider converting it to `CLUSTERED COLUMNSTORE` — roughly 10× compression and orders-of-magnitude faster aggregate scans, valid only when <10% of rows are ever updated.

### 5.3 Partitioning for large facts

Any fact table projected to exceed **~50M rows** or **~3 years of daily snapshots** should be **partitioned by month** on `obs_date` from day one using `RANGE RIGHT`. Retrofitting partitioning requires a full table rebuild.

- Register the partition function + scheme in the migration that creates the table.
- Align all nonclustered indexes on the same partition scheme.
- Use **partition switching** for archival/retention (sliding window pattern — metadata-only, very fast).
- Known near-term candidates: `rates.fact_swaption_vol` (~38K rows/day → ~14M/yr → partition before year 3), any future intraday FX OHLC table.

### 5.4 Index discipline

- **Every FK column gets an index.** SQL Server does not auto-index FKs; missing indexes cause table scans on parent-side updates and slow lookup joins.
- **Covering indexes** with `INCLUDE (...)` for the 2–3 highest-volume query shapes per fact table — avoids key lookups.
- **Filtered indexes** for sparse predicates (e.g. `WHERE is_estimated = 1`, `WHERE vol IS NOT NULL`) — much smaller, much faster.
- **Avoid over-indexing.** Each index adds write cost. Review `sys.dm_db_index_usage_stats` quarterly; drop indexes with zero seeks/scans.

### 5.5 Narrow, correct types

Storage and cache efficiency compound with row count. Use the narrowest correct type:

- **Integer sizing**: `TINYINT` (≤255), `SMALLINT` (≤32K), `INT` (default), `BIGINT` only when justified. Reinforces §3 item 1.
- **Decimals**: `DECIMAL(p, s)` with domain-appropriate precision — `DECIMAL(18,8)` for prices/rates, `DECIMAL(9,6)` for vols. Never `FLOAT`/`REAL` for monetary or reference data (non-deterministic comparisons).
- **Dates**: `DATE` for calendar days, `DATETIMEOFFSET` for timestamps. Never legacy `DATETIME` (3 ms rounding).
- **Strings**: `VARCHAR(n)` sized to the domain maximum. Avoid `NVARCHAR` unless Unicode is truly required (doubles storage). Avoid `VARCHAR(MAX)` unless storing genuine blobs.

### 5.6 Constraints as optimizer hints

- **`NOT NULL` by default** — require a reason to allow NULL. NULLs defeat index seeks and complicate aggregates.
- **`CHECK` constraints** on domain ranges — `CHECK (vol >= 0 AND vol <= 5)`, `CHECK (tenor_days > 0)`. Catches corrupt ingest and gives the optimizer constants.
- **`UNIQUE` constraint on the natural-key tuple** of every fact table (e.g. `(obs_date, symbol_id, tenor_id)`).
- **Keep FKs `TRUSTED`** — avoid `WITH NOCHECK`. Trusted FKs enable join elimination in the optimizer.

### 5.7 Write path

- **Bulk load → `#staging` temp table → `MERGE` inside one transaction.** Already the [bulk.py](../../src/imdr/connectors/bulk.py) pattern — document it in any new pipeline.
- **`TABLOCK` hint** on bulk inserts into empty or partition-aligned targets enables minimal logging under simple/bulk-logged recovery.
- **Batch size**: 10K–50K rows per transaction for live ingest; larger for historical backfill.

### 5.8 Statistics and Query Store

- **Auto-update statistics** stays on, but for tables with >10M rows add a scheduled `UPDATE STATISTICS ... WITH FULLSCAN` weekly — sampled auto-update underestimates cardinality on skewed time-series.
- **Query Store** is already enabled (see [migration 002](../../migrations/002_enable_query_store.sql)). Review top regressed queries monthly via `sys.query_store_*` DMVs and use findings to guide index additions.

### 5.9 What to avoid

- `SELECT *` in application code — breaks when columns are added, defeats covering indexes.
- Scalar UDFs in `WHERE` clauses — force row-by-row execution (SQL 2019+ inlines many, but still brittle).
- `NVARCHAR` for ASCII-only data.
- Storing JSON/XML blobs for data that has a fixed schema — normalize it.
- Implicit conversions in joins (`VARCHAR` vs `NVARCHAR`, `INT` vs `BIGINT`) — visible as `CONVERT_IMPLICIT` in plans; kills index seeks.
