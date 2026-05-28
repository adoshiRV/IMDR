# IMDR Database Design Audit — 2026-04-24

> ⚠ **STATUS — partially superseded (2026-05-13).** The audit's executive summary called out a stalled `market_code → market_id` migration and proposed P1-10 / P1-14 to finish it. That work was instead resolved by the **country-anchor restructure** (migrations 037–049), which goes further: it replaces `market_id`/`market_code` with a `country_id` FK to a new `dbo.dim_country` anchor, drops the legacy `calendar.dim_market` chain entirely from domain schemas, and folds the per-table renaming questions raised in P1-14 into a coherent design. See [country_anchor_design.md](../calendar/country_anchor_design.md) and [country_anchor_restructure_progress.md](../development/country_anchor_restructure_progress.md). The other audit findings (compression, clustering, partitioning, FLOAT→DECIMAL) remain valid open items.

**Auditor perspective**: external senior DBMS engineer review
**DB**: IMDR (SQL Server, Windows Auth)
**Scope**: schema design, indexing, compression, normalization, statistics,
constraints, referential integrity, storage efficiency

---

## Executive Summary

IMDR shows classic **schema-evolution debt**. Newest tables
(`fx.fact_fx_rate`, `rates.dim_vol_surface`) follow solid dimensional-modeling
practice; oldest and largest (`rates.fact_observation`, `fx.fact_ohlc`) carry
un-normalized string dimensions, wrong clustering keys, stale statistics, no
compression, and no business-key uniqueness. A partially completed
`market_code → market_id` migration leaves 10+ tables carrying duplicate FK
columns.

**Quantified opportunity** from the P0/P1 fixes in this document:

| Dimension | Current | After fixes | Saving |
|---|---|---|---|
| `rates.fact_observation` size | 762 MB | ~180-250 MB | ~67% |
| `fx.fact_ohlc` size + index bloat | ~600 MB (table + 2 covering idx) | ~100 MB | ~83% |
| `rates.fact_swaption_vol` | 121 MB | ~35-45 MB | ~65% |
| Time-range query latency (big facts) | scan or key-lookup per row | clustered seek | 5-20× |
| Schema uniformity (value types, FKs) | mixed float/decimal, string dims | consistent | — |

Total reclaimed storage target: **~1.0 GB of ~1.2 GB current DB size**.

---

## How This Audit Was Run

All findings are backed by live metadata queries run via the IMDR MCP server
on 2026-04-24. Re-run any of these to verify or track progress over time.

### Re-audit queries (run as a batch)

```sql
-- Table inventory + size
SELECT s.name AS schema_name, t.name AS table_name, p.rows AS row_count,
       SUM(a.total_pages) * 8 / 1024 AS size_mb,
       MAX(p.data_compression_desc) AS compression
FROM sys.tables t
JOIN sys.schemas s ON t.schema_id = s.schema_id
JOIN sys.partitions p ON t.object_id = p.object_id AND p.index_id IN (0,1)
JOIN sys.allocation_units a ON p.partition_id = a.container_id
GROUP BY s.name, t.name, p.rows
ORDER BY size_mb DESC

-- Check-constraint inventory
SELECT OBJECT_SCHEMA_NAME(parent_object_id) s, OBJECT_NAME(parent_object_id) t,
       name, is_disabled, is_not_trusted
FROM sys.check_constraints

-- Foreign-key inventory
SELECT OBJECT_SCHEMA_NAME(fk.parent_object_id) ps, OBJECT_NAME(fk.parent_object_id) pt,
       COL_NAME(fkc.parent_object_id, fkc.parent_column_id) pc,
       OBJECT_SCHEMA_NAME(fk.referenced_object_id) rs, OBJECT_NAME(fk.referenced_object_id) rt
FROM sys.foreign_keys fk
JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
ORDER BY ps, pt, pc

-- Statistics freshness
SELECT OBJECT_SCHEMA_NAME(st.object_id) s, OBJECT_NAME(st.object_id) t,
       st.name AS stat_name, STATS_DATE(st.object_id, st.stats_id) AS last_updated,
       sp.rows, sp.modification_counter
FROM sys.stats st
CROSS APPLY sys.dm_db_stats_properties(st.object_id, st.stats_id) sp
WHERE st.object_id IN (SELECT object_id FROM sys.tables)
ORDER BY sp.modification_counter DESC
```

---

## Findings by Severity

### P0 — Critical (high impact, low risk, fix first)
1. Only 1 of 34 tables compressed
2. Big facts clustered on `IDENTITY` instead of time-key
3. `fact_ohlc` has no business-key uniqueness (duplicate insertion possible)
4. `fact_ohlc` statistics are 45+ days stale on an actively written table
5. Redundant low-cardinality indexes on `fact_fx_rate`
6. Massive covering indexes on `fact_ohlc` (14 INCLUDE columns each)

### P1 — High (correctness, uniformity, dev velocity)
7. `fact_observation` still uses string dimensions (`quote`, `tenor`)
8. `fact_ohlc` entirely un-normalized (5 varchar dims per row)
9. `fact_vix` uses `ticker` string; `fact_index_level` uses `index_id`
10. `market_code → market_id` migration stalled (10+ tables carry both)
11. Currency strings not FK'd to `dim_currency`
12. `dim_vol_surface.freq` duplicates `dim_frequency`
13. Value type inconsistency: `FLOAT` vs `DECIMAL`
14. `cb_events.country_code` semantically misnamed (it's a market_code)
15. Missing domain check constraints (only 3 exist DB-wide)

### P2 — Hygiene & Future-Proofing
16. `updated_at` is dead weight on append-only facts
17. Varchar size inconsistency (`tenor` ranges VARCHAR(4) to VARCHAR(30))
18. No partitioning on big facts
19. No columnstore indexes for analytical workloads
20. Dead schema objects (`rates.cache_empty_combo`, empty `research.*`)
21. No retention policy on `admin.mcp_query_log`
22. No `dim_pipeline` / `dim_series` cross-domain catalog

---

# P0 — Critical Fixes

---

## P0-1 — Enable PAGE compression on the three big facts

### Problem
Only `FX.fact_fx_rate` has `DATA_COMPRESSION = PAGE`. The three monsters
(`fact_observation` 762 MB, `fact_ohlc` 205 MB, `fact_swaption_vol` 121 MB)
are uncompressed. Time-series data with repeating string/int dimensions is
the textbook PAGE-compression target.

### Pre-flight (estimate savings)
```sql
-- Per-table estimate (SQL Server built-in; safe, read-only)
EXEC sys.sp_estimate_data_compression_savings
  @schema_name = 'rates', @object_name = 'fact_observation',
  @index_id = NULL, @partition_number = NULL, @data_compression = 'PAGE'
```
Run for `FX.fact_ohlc` and `rates.fact_swaption_vol` too. Expect 60-75%
savings on each.

### Migration — `migrations/028_enable_page_compression.sql`
```sql
-- Requires sufficient transaction log space: rebuild is fully logged.
-- Run outside business hours. Each ALTER takes minutes (not seconds).

ALTER TABLE rates.fact_observation
  REBUILD WITH (DATA_COMPRESSION = PAGE, ONLINE = OFF)

ALTER TABLE FX.fact_ohlc
  REBUILD WITH (DATA_COMPRESSION = PAGE, ONLINE = OFF)

ALTER TABLE rates.fact_swaption_vol
  REBUILD WITH (DATA_COMPRESSION = PAGE, ONLINE = OFF)

ALTER TABLE rates.fact_swaption_skew
  REBUILD WITH (DATA_COMPRESSION = PAGE, ONLINE = OFF)

ALTER TABLE FX.fact_vol
  REBUILD WITH (DATA_COMPRESSION = PAGE, ONLINE = OFF)

-- Also rebuild every nonclustered index on these tables with compression:
ALTER INDEX ALL ON rates.fact_observation REBUILD WITH (DATA_COMPRESSION = PAGE)
ALTER INDEX ALL ON FX.fact_ohlc           REBUILD WITH (DATA_COMPRESSION = PAGE)
ALTER INDEX ALL ON rates.fact_swaption_vol REBUILD WITH (DATA_COMPRESSION = PAGE)
ALTER INDEX ALL ON rates.fact_swaption_skew REBUILD WITH (DATA_COMPRESSION = PAGE)
ALTER INDEX ALL ON FX.fact_vol            REBUILD WITH (DATA_COMPRESSION = PAGE)
```

### Verification
```sql
SELECT OBJECT_SCHEMA_NAME(object_id) s, OBJECT_NAME(object_id) t,
       data_compression_desc
FROM sys.partitions
WHERE object_id IN (SELECT object_id FROM sys.tables) AND index_id IN (0,1)
  AND data_compression_desc = 'NONE'
-- Expect: only dims + small facts should remain NONE after this migration
```

### Rollback
```sql
ALTER TABLE rates.fact_observation REBUILD WITH (DATA_COMPRESSION = NONE)
-- etc.
```

### Expected impact
~500 MB reclaimed. Zero query rewrites required. CPU overhead per scan
~10% higher but I/O drops dramatically, net query latency improves.

---

## P0-2 — Recluster big facts on time-key tuples

### Problem
Five big facts are clustered on `id INT IDENTITY`. Your dominant query
pattern is `WHERE obs_date BETWEEN X AND Y AND {dim}_id = Z` (per pipeline
readers, staleness checks, Grafana dashboards). Identity clustering forces
either a full scan or seek + **bookmark lookup per row**. `fact_fx_rate`
already did this correctly — replicate.

| Table | Current cluster key | Proposed cluster key |
|---|---|---|
| rates.fact_observation | `id` | `(curve_id, ts, quote, tenor, frequency_id)` |
| fx.fact_ohlc | `id` | `(ts, symbol, tenor, deal_type)` |
| rates.fact_swaption_vol | `id` | `(obs_date, surface_id, option_expiry, swap_tenor)` |
| rates.fact_swaption_skew | `id` | `(obs_date, surface_id, swap_tenor, strike_offset)` |
| fx.fact_vol | `id` | `(obs_date, pair_id, strike, tenor, vol_type)` |

In each case the new clustered key is **also the business unique key**
(currently implemented as a nonclustered `uq_*` index) — so we collapse
two structures into one, saving storage on top of the speedup.

### Pre-flight
Confirm current query patterns:
```sql
SELECT TOP 10 *
FROM rates.fact_observation
WHERE curve_id = 1 AND ts >= '2026-01-01'
ORDER BY ts
-- Note: SQL Server's actual execution plan will show "Key Lookup" today.
```

Confirm that the business key is actually unique (if this returns rows,
stop and investigate):
```sql
SELECT curve_id, ts, quote, tenor, frequency_id, COUNT(*)
FROM rates.fact_observation
GROUP BY curve_id, ts, quote, tenor, frequency_id
HAVING COUNT(*) > 1
```

### Migration — `migrations/029_recluster_rates_fact_observation.sql`
```sql
-- One migration per table. Template shown for fact_observation.
-- ONLINE=ON requires Enterprise edition; use OFF for Standard (takes a
-- brief X lock at swap time).

-- 1. Drop old clustered PK (currently on id)
ALTER TABLE rates.fact_observation
  DROP CONSTRAINT PK__fact_obs__3213E83FBB2240FD  -- verify exact name

-- 2. Drop old unique nonclustered (business key) — we'll rebuild as clustered
DROP INDEX uq_rates_fact_obs ON rates.fact_observation

-- 3. Create new clustered index on business key
CREATE UNIQUE CLUSTERED INDEX ix_rates_fact_observation_cluster
  ON rates.fact_observation (curve_id, ts, quote, tenor, frequency_id)
  WITH (DATA_COMPRESSION = PAGE)

-- 4. Recreate PK as nonclustered on id
ALTER TABLE rates.fact_observation
  ADD CONSTRAINT pk_rates_fact_observation
  PRIMARY KEY NONCLUSTERED (id)
  WITH (DATA_COMPRESSION = PAGE)

-- 5. Evaluate remaining NC indexes — most become redundant:
DROP INDEX ix_rates_obs_ts ON rates.fact_observation
  -- subsumed by clustered leading with curve_id, not optimal; keep a standalone
  -- ts index only if staleness queries are "latest ts ACROSS ALL curves"
DROP INDEX Ix_curve_id_quote ON rates.fact_observation
  -- fully subsumed by new cluster
DROP INDEX ix_rates_fact_observation_frequency ON rates.fact_observation
  -- cardinality 10, never used as seek predicate (see P0-5)

-- 6. Keep: ix_rates_obs_quote_tenor (cross-curve lookups by quote-type)
--    But reconsider after workload review.
```

### Verification
```sql
-- Confirm new cluster + old PK are in place
SELECT i.name, i.type_desc, i.is_primary_key, i.is_unique,
       STUFF((SELECT ', ' + c.name FROM sys.index_columns ic
              JOIN sys.columns c ON ic.object_id=c.object_id AND ic.column_id=c.column_id
              WHERE ic.object_id=i.object_id AND ic.index_id=i.index_id AND ic.is_included_column=0
              ORDER BY ic.key_ordinal FOR XML PATH('')),1,2,'') AS key_cols
FROM sys.indexes i
WHERE i.object_id = OBJECT_ID('rates.fact_observation')

-- Measure: run a typical date-range query, look for "Clustered Index Seek"
SET STATISTICS IO, TIME ON
SELECT ts, value FROM rates.fact_observation
WHERE curve_id = 1 AND ts BETWEEN '2026-01-01' AND '2026-04-01'
```

### Rollback
The migration is two transactions (drop old cluster, create new) — wrap in
`BEGIN TRAN` and test in a staging copy first. If rollback needed, reverse
the 4 steps.

### Expected impact
Queries like "all SOFR 3M observations over last year" drop from ~5.8M-row
scan or 1K-5K key lookups to a single clustered-range seek. 5-20× latency
improvement on Grafana/staleness workloads.

---

## P0-3 — `fact_ohlc` has no business-key uniqueness

### Problem
1,100,642 rows, 1,100,642 distinct `(ts, symbol, tenor, deal_type)` tuples
— no duplicates today, but **nothing enforces that**. A re-run of a
historical load would silently double-insert.

### Migration — `migrations/030_fact_ohlc_business_key.sql`
```sql
-- If P0-2 has landed first, this unique is the new clustered index.
-- Otherwise add a nonclustered unique constraint:

CREATE UNIQUE NONCLUSTERED INDEX uq_fx_fact_ohlc_business_key
  ON FX.fact_ohlc (ts, symbol, tenor, deal_type)
  WITH (DATA_COMPRESSION = PAGE)
```

### Verification
```sql
-- Must return 0 before the index will be created; if > 0, clean duplicates first
SELECT COUNT(*) - COUNT(DISTINCT CONCAT(ts,'|',symbol,'|',tenor,'|',deal_type))
FROM FX.fact_ohlc
```

---

## P0-4 — Update stale statistics on `fact_ohlc`

### Problem
`FX.fact_ohlc` statistics last updated **2026-03-10** on an actively written
table now at 1.1M rows and still growing. The optimizer is making plan
decisions against ~45-day-old data distribution.

### Fix (run now; one-off)
```sql
UPDATE STATISTICS FX.fact_ohlc WITH FULLSCAN
UPDATE STATISTICS rates.fact_observation WITH FULLSCAN
UPDATE STATISTICS rates.fact_swaption_vol WITH FULLSCAN
UPDATE STATISTICS rates.fact_swaption_skew WITH FULLSCAN
UPDATE STATISTICS FX.fact_vol WITH FULLSCAN
UPDATE STATISTICS FX.fact_fx_rate WITH FULLSCAN
```

### Ongoing — weekly SQL Agent job
```sql
-- Scheduled job step: rebuild fragmented indexes + update stats
EXEC sp_MSforeachtable @command1 = 'UPDATE STATISTICS ? WITH FULLSCAN'
-- For IMDR-scale (tens of GB), FULLSCAN is fine weekly. If the DB grows
-- to hundreds of GB, switch to WITH SAMPLE 30 PERCENT.
```

### Verification
```sql
SELECT OBJECT_SCHEMA_NAME(st.object_id) s, OBJECT_NAME(st.object_id) t,
       st.name, STATS_DATE(st.object_id, st.stats_id) last_updated,
       sp.modification_counter AS rows_changed_since_last_update
FROM sys.stats st CROSS APPLY sys.dm_db_stats_properties(st.object_id, st.stats_id) sp
WHERE st.object_id IN (SELECT object_id FROM sys.tables) AND sp.rows > 10000
ORDER BY last_updated ASC
-- Expect: oldest update < 7 days after weekly job is in place.
```

---

## P0-5 — Drop useless low-cardinality indexes

### Problem
`FX.fact_fx_rate` has standalone indexes on columns of cardinality 4 and
10. Optimizer will never choose them over the clustered index; they cost
storage + insert overhead for zero read benefit.

| Index | Leading column | Distinct values | Verdict |
|---|---|---|---|
| `ix_fx_fact_fx_rate_vendor` | `vendor_id` | 4 | drop |
| `ix_fx_fact_fx_rate_frequency` | `frequency_id` | 10 | drop |
| `ix_rates_fact_observation_frequency` | `frequency_id` | 10 | drop |

### Migration — `migrations/031_drop_low_cardinality_indexes.sql`
```sql
DROP INDEX ix_fx_fact_fx_rate_vendor         ON FX.fact_fx_rate
DROP INDEX ix_fx_fact_fx_rate_frequency      ON FX.fact_fx_rate
DROP INDEX ix_rates_fact_observation_frequency ON rates.fact_observation
```

### Verification
```sql
-- Confirm optimizer has never used these (validates the drop decision).
-- Requires sys.dm_db_index_usage_stats; may need VIEW SERVER STATE.
SELECT OBJECT_NAME(s.object_id) AS tbl, i.name, s.user_seeks, s.user_scans
FROM sys.dm_db_index_usage_stats s
JOIN sys.indexes i ON s.object_id=i.object_id AND s.index_id=i.index_id
WHERE i.name IN (
  'ix_fx_fact_fx_rate_vendor','ix_fx_fact_fx_rate_frequency',
  'ix_rates_fact_observation_frequency')
```

---

## P0-6 — Reduce `fact_ohlc` covering-index bloat

### Problem
`FX.fact_ohlc` has two nonclustered indexes each with ~14 INCLUDE columns:

| Index | Key | INCLUDE |
|---|---|---|
| Ix_ts | ts | symbol, series, tenor, deal_type, pair_used, open_px, high_px, low_px, close_px, mid_px, mid_mean_px, mid_median_px, bid, ask |
| Ix_tenor | tenor | ts, symbol, open_px, close_px, mid_px, mid_mean_px, mid_median_px, bid, ask |

Each is effectively a **duplicate of the whole table**. After P0-2
(clustering on `(ts, symbol, tenor, deal_type)`), these become redundant.

### Migration — `migrations/032_drop_fact_ohlc_covering_indexes.sql`
Apply **after** P0-2 for `fact_ohlc`:
```sql
DROP INDEX Ix_ts    ON FX.fact_ohlc
DROP INDEX Ix_tenor ON FX.fact_ohlc
```

### Expected impact
Index pages likely ~300-400MB between them. This ships most of the
fact_ohlc storage win.

---

# P1 — High-Priority Fixes

---

## P1-7 — Normalize `fact_observation` dimensions

### Problem
5.8M rows carrying `quote VARCHAR(10)` (only 5 distinct values!) and
`tenor VARCHAR(30)` (90 distinct values). Heavy row width, no FK,
no enforcement of valid values.

| Column | Type | Distinct values | Storage per row |
|---|---|---|---|
| quote | VARCHAR(10) | 5 (par/fwd/ssw/spread/bfly) | ~2 + avg 4 = 6 bytes |
| tenor | VARCHAR(30) | 90 (1D, 1M, 3M, 10Y, ...) | ~2 + avg 3 = 5 bytes |

**Distribution** (verify with live query):
```sql
SELECT quote, COUNT(*) FROM rates.fact_observation GROUP BY quote ORDER BY 2 DESC
-- par 3,765,520 | fwd 1,619,819 | ssw 451,065 | spread 5,085 | bfly 3,051
```

### Design
Create two small lookup dims, backfill FK columns on the fact.

### Migration — `migrations/033_normalize_fact_observation_dims.sql`
```sql
-- 1. Create dim_quote_type (5 rows)
CREATE TABLE rates.dim_quote_type (
  id TINYINT IDENTITY(1,1) PRIMARY KEY,
  quote_code VARCHAR(10) NOT NULL UNIQUE,
  display_name VARCHAR(40) NOT NULL,
  description VARCHAR(200) NULL,
  created_at DATETIMEOFFSET(3) NOT NULL CONSTRAINT df_dim_quote_type_created DEFAULT SYSDATETIMEOFFSET()
)

INSERT INTO rates.dim_quote_type (quote_code, display_name, description) VALUES
  ('par',    'Par Rate',      'Par swap rate'),
  ('fwd',    'Forward Rate',  'Forward-starting swap rate'),
  ('ssw',    'Single Swap',   'Single-swap mid'),
  ('spread', 'Spread',        'Basis spread to benchmark'),
  ('bfly',   'Butterfly',     'Curve butterfly');

-- 2. Create dim_tenor (~90 rows) — shared across rates + fx + commodities
CREATE TABLE dbo.dim_tenor (
  id SMALLINT IDENTITY(1,1) PRIMARY KEY,
  tenor_code VARCHAR(10) NOT NULL UNIQUE,
  tenor_days SMALLINT NULL,        -- for ordering/math; NULL for non-standard
  tenor_months SMALLINT NULL,
  display_name VARCHAR(20) NOT NULL,
  sort_order INT NOT NULL,         -- for axis ordering in dashboards
  created_at DATETIMEOFFSET(3) NOT NULL CONSTRAINT df_dim_tenor_created DEFAULT SYSDATETIMEOFFSET()
)

-- Backfill from existing distinct values:
INSERT INTO dbo.dim_tenor (tenor_code, display_name, sort_order)
SELECT DISTINCT tenor, tenor, ROW_NUMBER() OVER (ORDER BY tenor)
FROM rates.fact_observation
-- Follow up: manually set tenor_days / tenor_months / sort_order correctly.

-- 3. Add FK columns to fact (nullable during backfill)
ALTER TABLE rates.fact_observation ADD quote_id TINYINT NULL, tenor_id SMALLINT NULL

-- 4. Backfill
UPDATE f SET quote_id = q.id
FROM rates.fact_observation f JOIN rates.dim_quote_type q ON f.quote = q.quote_code
UPDATE f SET tenor_id = t.id
FROM rates.fact_observation f JOIN dbo.dim_tenor t ON f.tenor = t.tenor_code

-- 5. Enforce NOT NULL + FK
ALTER TABLE rates.fact_observation ALTER COLUMN quote_id TINYINT NOT NULL
ALTER TABLE rates.fact_observation ALTER COLUMN tenor_id SMALLINT NOT NULL
ALTER TABLE rates.fact_observation ADD CONSTRAINT fk_rates_fact_obs_quote
  FOREIGN KEY (quote_id) REFERENCES rates.dim_quote_type(id)
ALTER TABLE rates.fact_observation ADD CONSTRAINT fk_rates_fact_obs_tenor
  FOREIGN KEY (tenor_id) REFERENCES dbo.dim_tenor(id)

-- 6. Update writer code (src/imdr/domains/rates/pipeline.py + utils.py)
--    to populate quote_id / tenor_id instead of quote / tenor strings.

-- 7. After production writers are updated and a burn-in period passes:
ALTER TABLE rates.fact_observation DROP CONSTRAINT ck_rates_quote
ALTER TABLE rates.fact_observation DROP COLUMN quote
ALTER TABLE rates.fact_observation DROP COLUMN tenor

-- 8. Recreate the business-key cluster/unique with new columns (see P0-2):
-- (curve_id, ts, quote_id, tenor_id, frequency_id)
```

### Verification
```sql
-- All backfilled
SELECT COUNT(*) FROM rates.fact_observation WHERE quote_id IS NULL OR tenor_id IS NULL
-- Expect 0

-- FK integrity
SELECT COUNT(*) FROM rates.fact_observation f
LEFT JOIN rates.dim_quote_type q ON f.quote_id = q.id
LEFT JOIN dbo.dim_tenor t ON f.tenor_id = t.id
WHERE q.id IS NULL OR t.id IS NULL
-- Expect 0
```

### Expected impact
- Row width drops ~11 bytes × 5.8M = ~64 MB of raw table (multiplied by
  compression ratio = actual disk savings ~20-30 MB).
- Larger win: **join integrity** + optimizer statistics on small dims are
  far more reliable than on varchar.
- Writer code becomes cleaner (`series = (curve, quote, tenor)` → one ID).

---

## P1-8 — Normalize `fact_ohlc`

### Problem
1.1M rows carry `symbol VARCHAR(12)`, `series VARCHAR(20)`, `tenor VARCHAR(10)`,
`deal_type VARCHAR(10)`, `pair_used VARCHAR(10)` — five un-normalized string
columns, no FK to `fx.dim_currency_pair` despite being FX data.

### Design
Create a `fx.dim_ohlc_series` that encodes the five dimensions as a single
`series_id`, referencing `dim_currency_pair`.

### Migration — `migrations/034_normalize_fact_ohlc.sql`
```sql
-- 1. Create dim_ohlc_series
CREATE TABLE FX.dim_ohlc_series (
  id INT IDENTITY(1,1) PRIMARY KEY,
  pair_id INT NOT NULL,
  symbol VARCHAR(12) NOT NULL,          -- cached denorm for debugging
  series VARCHAR(20) NOT NULL,           -- SPOT, FORWARD_1M, etc.
  tenor VARCHAR(10) NOT NULL,            -- SPOT, 1M, 3M, ...
  deal_type VARCHAR(10) NOT NULL,        -- SPOT, FORWARD
  pair_used VARCHAR(10) NOT NULL,        -- may differ from symbol (e.g. USDNDF routing)
  created_at DATETIMEOFFSET(3) NOT NULL CONSTRAINT df_dim_ohlc_series_created DEFAULT SYSDATETIMEOFFSET(),
  CONSTRAINT uq_fx_dim_ohlc_series UNIQUE (pair_id, series, tenor, deal_type, pair_used),
  CONSTRAINT fk_fx_dim_ohlc_series_pair FOREIGN KEY (pair_id) REFERENCES FX.dim_currency_pair(id)
)

-- 2. Backfill dim (one row per distinct tuple)
INSERT INTO FX.dim_ohlc_series (pair_id, symbol, series, tenor, deal_type, pair_used)
SELECT DISTINCT
  (SELECT p.id FROM FX.dim_currency_pair p
   WHERE p.base_ccy = LEFT(o.symbol,3) AND p.quote_ccy = SUBSTRING(o.symbol,4,3)),
  o.symbol, o.series, o.tenor, o.deal_type, o.pair_used
FROM FX.fact_ohlc o
-- If pair_id is NULL for any row, seed missing dim_currency_pair rows first.

-- 3. Add FK column to fact
ALTER TABLE FX.fact_ohlc ADD series_id INT NULL

UPDATE f SET series_id = d.id
FROM FX.fact_ohlc f
JOIN FX.dim_ohlc_series d
  ON d.symbol = f.symbol AND d.series = f.series AND d.tenor = f.tenor
 AND d.deal_type = f.deal_type AND d.pair_used = f.pair_used

ALTER TABLE FX.fact_ohlc ALTER COLUMN series_id INT NOT NULL
ALTER TABLE FX.fact_ohlc ADD CONSTRAINT fk_fx_fact_ohlc_series
  FOREIGN KEY (series_id) REFERENCES FX.dim_ohlc_series(id)

-- 4. Update writer (src/imdr/domains/fx/*). After burn-in:
ALTER TABLE FX.fact_ohlc DROP COLUMN symbol, series, tenor, deal_type, pair_used
```

### Expected impact
~55 bytes of string columns per row × 1.1M = ~60 MB table reduction plus
proportional index reduction. Plus the row becomes joinable to
`dim_currency_pair` for uniform cross-domain analytics.

---

## P1-9 — Unify `fact_vix` with `fact_index_level`

### Problem
Two FX/equity-style tables, one using FK (`index_id`), the other using a
raw `ticker VARCHAR(10)`. VIX/VIX3M/VIX9D/VVIX/VXN are indices too.

### Migration — `migrations/035_unify_fact_vix.sql`
```sql
-- 1. Seed VIX-family into dim_index if not present
INSERT INTO equities.dim_index (ticker, display_name, currency, region, citi_tag)
SELECT DISTINCT f.ticker, f.ticker, 'USD', 'Global', NULL
FROM equities.fact_vix f
LEFT JOIN equities.dim_index d ON d.ticker = f.ticker
WHERE d.id IS NULL

-- 2. Copy fact_vix into fact_index_level (add discriminator column first)
ALTER TABLE equities.fact_index_level ADD is_vol_index BIT NOT NULL
  CONSTRAINT df_fact_index_level_is_vol_index DEFAULT 0

INSERT INTO equities.fact_index_level (index_id, obs_date, close_level, is_vol_index)
SELECT d.id, v.obs_date, v.close_level, 1
FROM equities.fact_vix v
JOIN equities.dim_index d ON d.ticker = v.ticker

-- 3. After writers updated + burn-in:
DROP TABLE equities.fact_vix
```

---

## P1-10 — Complete the `market_code → market_id` migration

### Problem
Migration 026 added `market_id TINYINT FK` to 5 domain dims. But the legacy
`market_code VARCHAR(5)` columns remain (some also FK'd) on:
`calendar.cb_events`, `calendar.dim_market_currency`, `calendar.dim_trading_day`,
`equities.dim_index`, `FX.dim_currency_pair`, `rates.dim_curve`,
`rates.dim_skew_surface`, `rates.dim_vol_surface`, `research.dim_report`.

Joins are ambiguous; inserts pay 2× FK overhead; audits show drift risk.

### Migration plan (one per table) — `migrations/036_drop_market_code_*.sql`
For each table:
```sql
-- 1. Pre-flight: ensure market_id is backfilled
SELECT COUNT(*) FROM <table> WHERE market_code IS NOT NULL AND market_id IS NULL
-- Expect 0

-- 2. Add market_id where missing on calendar.dim_market_currency + cb_events + dim_trading_day
-- (these currently use only market_code)
ALTER TABLE calendar.dim_trading_day ADD market_id TINYINT NULL
UPDATE t SET market_id = m.id
FROM calendar.dim_trading_day t JOIN calendar.dim_market m ON t.market_code = m.market_code
ALTER TABLE calendar.dim_trading_day ALTER COLUMN market_id TINYINT NOT NULL
ALTER TABLE calendar.dim_trading_day ADD CONSTRAINT fk_trading_day_market
  FOREIGN KEY (market_id) REFERENCES calendar.dim_market(id)

-- 3. Rebuild cluster on dim_trading_day to use market_id
ALTER TABLE calendar.dim_trading_day DROP CONSTRAINT PK_dim_trading_day
ALTER TABLE calendar.dim_trading_day ADD CONSTRAINT PK_dim_trading_day
  PRIMARY KEY CLUSTERED (market_id, calendar_date)

-- 4. Drop market_code FKs + columns on every migrated dim
ALTER TABLE FX.dim_currency_pair DROP CONSTRAINT <fk_name>
ALTER TABLE FX.dim_currency_pair DROP COLUMN market_code
-- ... repeat for every dim
```

### Verification
```sql
-- Zero remaining market_code columns outside calendar.dim_market itself
SELECT OBJECT_SCHEMA_NAME(c.object_id) s, OBJECT_NAME(c.object_id) t, c.name
FROM sys.columns c WHERE c.name = 'market_code'
-- Expect only calendar.dim_market (canonical)
```

---

## P1-11 — FK currency strings to `dim_currency`

### Migration — `migrations/037_currency_fks.sql`
```sql
-- Example: rates.dim_central_bank.currency (VARCHAR(3))
ALTER TABLE rates.dim_central_bank ADD currency_id TINYINT NULL
UPDATE cb SET currency_id = c.id
FROM rates.dim_central_bank cb JOIN dbo.dim_currency c ON cb.currency = c.code
ALTER TABLE rates.dim_central_bank ALTER COLUMN currency_id TINYINT NOT NULL
ALTER TABLE rates.dim_central_bank ADD CONSTRAINT fk_rates_dim_central_bank_ccy
  FOREIGN KEY (currency_id) REFERENCES dbo.dim_currency(id)
ALTER TABLE rates.dim_central_bank DROP COLUMN currency

-- Repeat for:
--   equities.dim_index.currency
--   FX.dim_currency_pair.base_ccy, quote_ccy  -- two FKs: base_ccy_id, quote_ccy_id
--   rates.dim_curve.ccy
--   rates.dim_vol_surface.ccy
--   rates.cache_empty_combo.ccy (if we keep this table — see P2-20)
```

### Expected impact
Currency strings cannot drift (`'usd'` vs `'USD'`). Joins become 1-byte
TINYINT instead of VARCHAR(3). Minor but consistent win.

---

## P1-12 — `dim_vol_surface.freq` → FK to `dim_frequency`

### Migration — `migrations/038_vol_surface_frequency_fk.sql`
```sql
ALTER TABLE rates.dim_vol_surface ADD frequency_id TINYINT NULL
UPDATE s SET frequency_id = f.id
FROM rates.dim_vol_surface s JOIN dbo.dim_frequency f ON s.freq = f.frequency_code
ALTER TABLE rates.dim_vol_surface ALTER COLUMN frequency_id TINYINT NOT NULL
ALTER TABLE rates.dim_vol_surface ADD CONSTRAINT fk_rates_vol_surface_freq
  FOREIGN KEY (frequency_id) REFERENCES dbo.dim_frequency(id)

-- Update unique constraint
DROP INDEX uq_rates_dim_vol_surface ON rates.dim_vol_surface
CREATE UNIQUE NONCLUSTERED INDEX uq_rates_dim_vol_surface
  ON rates.dim_vol_surface (ccy, data_type, quote_type, vol_window, frequency_id)

ALTER TABLE rates.dim_vol_surface DROP COLUMN freq
```

---

## P1-13 — Standardize on `DECIMAL(18,8)` for value columns

### Problem
| Fact | Value column | Type |
|---|---|---|
| fact_fx_rate | mid_rate | DECIMAL(18,8) ✓ |
| fact_ohlc | open_px, high_px, ... | DECIMAL(22,8) |
| fact_observation | value | **FLOAT(53)** |
| fact_swaption_vol | value | **FLOAT(53)** |
| fact_swaption_skew | vol | **FLOAT(53)** |
| fact_bench_rates | rate | **FLOAT(53)** |
| fact_vol | value | **FLOAT(53)** |
| fact_implied_vol | vol | **FLOAT(53)** |
| fact_index_level | close_level | FLOAT(53) |
| fact_vix | close_level | FLOAT(53) |

Financial data demands exact representation. Pick one of:
- **(a) DECIMAL(18,8) everywhere** — exact, 9 bytes, recommended
- **(b) FLOAT everywhere** — 8 bytes, inexact, cheap math

### Migration — `migrations/039_standardize_value_types.sql`
```sql
-- DECIMAL(18,8) supports values up to 10 billion with 8-digit precision.
-- Sufficient for all IMDR value ranges (rates, vols, prices, index levels).

-- Template (test on each table; ONLINE=OFF, requires brief schema lock):
ALTER TABLE rates.fact_observation ALTER COLUMN value DECIMAL(18,8) NOT NULL
ALTER TABLE rates.fact_swaption_vol ALTER COLUMN value DECIMAL(18,8) NOT NULL
-- ... etc

-- Post-check: confirm no precision lost
SELECT MAX(ABS(value)), MIN(ABS(value)) FROM rates.fact_observation
-- Values should fit 1e-8 to 1e10 range; if not, use DECIMAL(22,10).
```

---

## P1-14 — Rename `cb_events.country_code` to `market_code` (then to `market_id`)

### Migration — `migrations/040_cb_events_rename_country_code.sql`
```sql
-- 1. Drop old FK, rename, recreate FK
ALTER TABLE calendar.cb_events DROP CONSTRAINT <fk_name>
EXEC sp_rename 'calendar.cb_events.country_code', 'market_code', 'COLUMN'
ALTER TABLE calendar.cb_events ADD CONSTRAINT fk_cb_events_market
  FOREIGN KEY (market_code) REFERENCES calendar.dim_market(market_code)

-- 2. Update Python code references: any SELECT/WHERE country_code
```

Combined with P1-10, eventually becomes `market_id TINYINT`.

---

## P1-15 — Add domain check constraints

### Problem
Only 3 check constraints exist DB-wide. Cheap sanity that fails fast on bad
writes is missing.

### Migration — `migrations/041_add_domain_checks.sql`
```sql
-- Vol must be positive and bounded
ALTER TABLE rates.fact_swaption_vol ADD CONSTRAINT ck_rates_swaption_vol_range
  CHECK (value > 0 AND value < 500)

ALTER TABLE commodities.fact_implied_vol ADD CONSTRAINT ck_cmdty_implied_vol_range
  CHECK (vol > 0 AND vol < 500)

ALTER TABLE FX.fact_vol ADD CONSTRAINT ck_fx_vol_range
  CHECK (value > 0 AND value < 200)

-- Prices must be positive
ALTER TABLE commodities.fact_spot ADD CONSTRAINT ck_cmdty_spot_price_pos
  CHECK (price > 0)

ALTER TABLE equities.fact_index_level ADD CONSTRAINT ck_equities_index_level_pos
  CHECK (close_level > 0)

-- Benchmark rates can be negative (ECB, BOJ) but bounded
ALTER TABLE rates.fact_bench_rates ADD CONSTRAINT ck_rates_bench_rate_range
  CHECK (rate > -10 AND rate < 100)

-- Pipeline run_status enum
ALTER TABLE audit.pipeline_runs ADD CONSTRAINT ck_audit_pipeline_run_status
  CHECK (run_status IN ('pending','running','success','failed','partial','skipped'))
```

---

# P2 — Hygiene & Future-Proofing

---

## P2-16 — Drop `updated_at` on append-only facts

### Rationale
Facts are append-only. `updated_at` is initialized to `created_at` and
never changes. `DATETIMEOFFSET(7)` = 10 bytes × 5.8M rows = ~58 MB on
`fact_observation` alone.

### Migration — `migrations/042_drop_fact_updated_at.sql`
```sql
ALTER TABLE rates.fact_observation  DROP COLUMN updated_at
ALTER TABLE rates.fact_swaption_vol DROP COLUMN updated_at
ALTER TABLE rates.fact_swaption_skew DROP COLUMN updated_at
ALTER TABLE rates.fact_bench_rates  DROP COLUMN updated_at
ALTER TABLE FX.fact_fx_rate         DROP COLUMN updated_at
ALTER TABLE FX.fact_vol             DROP COLUMN updated_at
ALTER TABLE commodities.fact_spot   DROP COLUMN updated_at
ALTER TABLE commodities.fact_eia    DROP COLUMN updated_at
ALTER TABLE commodities.fact_implied_vol DROP COLUMN updated_at
ALTER TABLE equities.fact_index_level DROP COLUMN updated_at
ALTER TABLE equities.fact_vix       DROP COLUMN updated_at

-- Also reduce created_at precision to DATETIMEOFFSET(3) = 8 bytes
-- (millisecond precision is plenty for load timestamps):
ALTER TABLE rates.fact_observation  ALTER COLUMN created_at DATETIMEOFFSET(3) NOT NULL
-- ... etc
```

---

## P2-17 — Standardize varchar sizing

### Migration — `migrations/043_standardize_varchar_sizes.sql`
```sql
-- tenor: VARCHAR(10) everywhere (longest current value fits, e.g. "30Y")
-- ccy: VARCHAR(3) everywhere
-- After P1-7, most of these go away via FK. This migration covers residuals.

ALTER TABLE rates.cache_empty_combo ALTER COLUMN ccy VARCHAR(3) NOT NULL
ALTER TABLE rates.cache_empty_combo ALTER COLUMN quote VARCHAR(10) NOT NULL
-- etc.
```

---

## P2-18 — Partition big facts by `obs_date`

### Rationale
`fact_observation` spans 2015-06 to 2026-04 (11 years, 5.8M rows). Monthly
partitioning gives:
- Partition elimination on date-range queries
- Fast archival via `SWITCH PARTITION OUT TO <archive_table>`
- Better parallelism and lock granularity

### Migration — `migrations/044_partition_fact_observation.sql`
```sql
-- 1. Create partition function + scheme (monthly boundaries)
CREATE PARTITION FUNCTION pf_monthly (DATETIMEOFFSET(3))
  AS RANGE RIGHT FOR VALUES (
    '2015-01-01 +00:00', '2015-02-01 +00:00', /* ... */
    '2026-05-01 +00:00', '2026-06-01 +00:00'
  )
CREATE PARTITION SCHEME ps_monthly AS PARTITION pf_monthly ALL TO ([PRIMARY])

-- 2. Rebuild clustered index on the partition scheme
CREATE UNIQUE CLUSTERED INDEX ix_rates_fact_observation_cluster
  ON rates.fact_observation (curve_id, ts, quote_id, tenor_id, frequency_id)
  WITH (DATA_COMPRESSION = PAGE, DROP_EXISTING = ON)
  ON ps_monthly(ts)

-- 3. Schedule monthly partition-sliding job to add future boundaries
```

### Verification
```sql
-- Partition elimination should kick in for ranged queries
SET STATISTICS IO ON
SELECT * FROM rates.fact_observation WHERE ts BETWEEN '2026-01-01' AND '2026-01-31'
-- Plan should show "Actual Partition Count = 1"
```

---

## P2-19 — Add columnstore indexes for analytical scans

### Rationale
Grafana dashboards and analytical aggregates scan millions of rows. A
nonclustered columnstore index (NCCI) on each big fact gives 10-100×
compression + batch-mode execution.

### Migration — `migrations/045_add_columnstore_indexes.sql`
```sql
CREATE NONCLUSTERED COLUMNSTORE INDEX ncci_rates_fact_observation
  ON rates.fact_observation (curve_id, ts, value, quote_id, tenor_id, frequency_id)

CREATE NONCLUSTERED COLUMNSTORE INDEX ncci_fx_fact_ohlc
  ON FX.fact_ohlc (series_id, ts, close_px, mid_px, bid, ask)

CREATE NONCLUSTERED COLUMNSTORE INDEX ncci_rates_fact_swaption_vol
  ON rates.fact_swaption_vol (surface_id, obs_date, option_expiry, swap_tenor, value)
```

### Expected impact
Aggregate queries (`SELECT AVG, STDEV, PERCENTILE`) over date ranges drop
from seconds to milliseconds. Coexists with B-tree clusters — optimizer
picks row-store for lookups, column-store for scans.

---

## P2-20 — Remove dead schema objects

### Queries to confirm dead
```sql
SELECT COUNT(*) FROM rates.cache_empty_combo      -- 0 (confirmed, deprecated by memory)
SELECT COUNT(*) FROM research.dim_report          -- 0
SELECT COUNT(*) FROM research.dim_tag             -- 0
SELECT COUNT(*) FROM research.map_report_market   -- 0
SELECT COUNT(*) FROM research.map_report_tag      -- 0
```

### Migration — `migrations/046_drop_dead_objects.sql`
```sql
-- cache_empty_combo replaced by hourly cadence (memory: a61eb48 + d625e8d)
DROP TABLE rates.cache_empty_combo

-- research.* — either commit to building or drop.
-- Recommend: keep, as the research tagging module is actively planned.
-- But: mark as "work-in-progress" in extended properties so tools flag it.
```

---

## P2-21 — Retention policy for `admin.mcp_query_log`

### Migration — `migrations/047_mcp_query_log_retention.sql`
```sql
-- Option A: simple scheduled delete
-- SQL Agent job (daily @ 03:00):
DELETE FROM admin.mcp_query_log
WHERE created_at < DATEADD(day, -30, SYSDATETIMEOFFSET())

-- Option B: partitioned by month, SWITCH OUT on age (cleaner at scale)
```

---

## P2-22 — Universal `dim_series` catalog (architectural)

### Rationale
Every fact table has an implicit "series" concept. Staleness monitor,
research tagging, Grafana dashboards, and coverage dashboards all benefit
from a single catalog.

### Design sketch (no migration yet — for planning)
```sql
CREATE TABLE dbo.dim_series (
  id INT IDENTITY PRIMARY KEY,
  domain VARCHAR(20) NOT NULL,         -- rates, fx, commodities, equities
  series_type VARCHAR(30) NOT NULL,    -- curve_point, vol_point, fx_rate, ...
  fact_schema VARCHAR(20) NOT NULL,
  fact_table VARCHAR(60) NOT NULL,
  natural_key VARCHAR(200) NOT NULL,   -- e.g. "USD|SOFR|3M|par"
  display_name VARCHAR(200) NOT NULL,
  first_obs_at DATETIMEOFFSET(3),
  last_obs_at DATETIMEOFFSET(3),
  expected_cadence_id TINYINT FK -> dim_frequency,
  staleness_threshold_hours SMALLINT,
  is_active BIT NOT NULL DEFAULT 1
)
```
Then staleness monitor reads one table. Research tags point to `series_id`.
Grafana dashboards generate panels from one query. Defer until 2+ more
domains land (Bloomberg feeds, Barclays skew).

---

# Sequenced Rollout Plan

## Week 1 — Non-destructive wins (P0-1, P0-4, P0-5)
- Apply `028_enable_page_compression.sql` (one afternoon, ~500 MB reclaimed)
- Apply `031_drop_low_cardinality_indexes.sql`
- Run `UPDATE STATISTICS ... WITH FULLSCAN` on all big facts
- Create weekly SQL Agent job for stats maintenance

**Rollback**: single `ALTER ... REBUILD WITH (DATA_COMPRESSION = NONE)` per table.

## Week 2 — Clustered-index migrations (P0-2, P0-3, P0-6)
Apply in staging first. Per table: drop old cluster, create new, drop
obsolete NC indexes. Run verification query per table.

**Rollback**: reverse the 4-step per-table migration.

## Week 3-4 — Normalization (P1-7, P1-8, P1-9)
Apply dim creation + backfill + nullable FK column. **Update writer code**.
Run for 2 pipeline cycles to verify. Then drop legacy string columns.

**Rollback**: keep legacy columns until burn-in complete; rollback = revert
writer code and drop new FK.

## Week 5 — Migration completion (P1-10, P1-11, P1-12, P1-14)
Finish `market_code → market_id`. FK currency + frequency strings. Rename
`country_code` → `market_code` on `cb_events`.

## Week 6 — Type uniformity + constraints (P1-13, P1-15, P2-16, P2-17)
Converge on `DECIMAL(18,8)`. Add domain check constraints. Drop
`updated_at` on facts. Standardize varchar sizes.

## Week 7+ — Performance upgrades (P2-18, P2-19)
Partitioning + columnstore. Prerequisite: normalization migrations complete.

## Ongoing — Hygiene (P2-20, P2-21, P2-22)
Dead-object cleanup. Retention policies. `dim_series` design doc.

---

# Operational Practices to Adopt

## 1. Weekly DB maintenance job (SQL Agent)
```sql
-- Step 1: Rebuild/reorganize by fragmentation level
DECLARE @sql NVARCHAR(MAX)
SELECT @sql = STRING_AGG(
  CASE
    WHEN avg_fragmentation_in_percent > 30 THEN
      'ALTER INDEX ' + QUOTENAME(i.name) + ' ON ' +
      QUOTENAME(OBJECT_SCHEMA_NAME(ps.object_id)) + '.' +
      QUOTENAME(OBJECT_NAME(ps.object_id)) + ' REBUILD;'
    WHEN avg_fragmentation_in_percent > 10 THEN
      'ALTER INDEX ' + QUOTENAME(i.name) + ' ON ' +
      QUOTENAME(OBJECT_SCHEMA_NAME(ps.object_id)) + '.' +
      QUOTENAME(OBJECT_NAME(ps.object_id)) + ' REORGANIZE;'
  END, CHAR(10))
FROM sys.dm_db_index_physical_stats(DB_ID(), NULL, NULL, NULL, 'LIMITED') ps
JOIN sys.indexes i ON ps.object_id = i.object_id AND ps.index_id = i.index_id
WHERE ps.page_count > 1000 AND ps.avg_fragmentation_in_percent > 10
EXEC sp_executesql @sql

-- Step 2: Update statistics
EXEC sp_MSforeachtable @command1 = 'UPDATE STATISTICS ? WITH FULLSCAN'

-- Step 3: Prune audit log
DELETE FROM admin.mcp_query_log WHERE created_at < DATEADD(day, -30, SYSDATETIMEOFFSET())
```

## 2. Pre-migration checklist template
For every schema migration, attach:
- [ ] Pre-flight query showing current state
- [ ] Migration SQL (in `migrations/NNN_*.sql`)
- [ ] Verification query confirming desired state
- [ ] Rollback SQL (or explicit "irreversible" flag)
- [ ] Expected duration + log-space estimate
- [ ] Impact on running pipelines (lock scope)

## 3. Schema evolution ADR log
Add `docs/admin/db_audit/ADR-NNNN.md` per material change. Captures
rationale, alternatives considered, rollback plan, and measured impact
post-deployment.

## 4. Grafana "DB Health" dashboard panels
- Table row growth trend (per big fact)
- Index fragmentation over time
- Statistics age per table (red if > 7 days on high-change table)
- Compression ratio per table
- Top 10 largest tables by size

## 5. Quarterly re-audit
Re-run the queries at the top of this doc every quarter. Compare against
this baseline. Update this document or add a new dated audit.

---

# References

- [Naming Convention Standardization Proposal](naming_conventions.md) — companion doc with 12 concrete naming rules + rename plan (migrations 048-056)
- [Existing normalization plan](../../normalization.md)
- [Schema conventions](../reference/schema_conventions.md)
- [Staleness monitor](../ops/staleness_monitor.md)
- [Visualization stack](../visualization/README.md)
- [Migration index](../../../migrations/)

---

# Changelog

| Date | Author | Change |
|---|---|---|
| 2026-04-24 | external-audit | Initial audit |
