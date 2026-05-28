# Naming Convention Standardization Proposal

**Companion to**: [2026-04-24_design_audit.md](2026-04-24_design_audit.md)
**Supersedes partially**: [schema_conventions.md §2](../reference/schema_conventions.md) — this doc extends §2 with concrete column-level rules, current violations, and a rename plan.
**Status**: proposal, pending review.

---

## Why This Matters

Rules in [schema_conventions.md](../reference/schema_conventions.md) cover tables and
FKs well but leave column-level vocabulary to per-table judgement. The
result is avoidable cognitive load:

- **Tenor** is `VARCHAR(5)`, `(10)`, `(15)`, or `(30)` depending on table
- **Currency** is `ccy` in some tables, `currency` in others (both `VARCHAR(3)`)
- **Observation time** is spelled 8 different ways: `ts`, `obs_date`,
  `obs_ts`, `event_date`, `event_datetime`, `calendar_date`, `publish_date`,
  `last_checked`
- **Primary value column** is named `value`, `rate`, `price`, `vol`,
  `close_level`, or `mid_rate` depending on the fact
- **Identifier** is `symbol`, `ticker`, `code`, or `tag` for the same concept
- Schema name `FX` is uppercase while every other schema is lowercase

Every inconsistency costs one more line in every join, one more typo in
every ad-hoc query, one more branch in every Grafana dashboard.

This doc proposes **one rule per concept**, lists every current violation,
and sketches the migration path.

---

## Confirmed Current-State Violations

Run this query to reproduce the violation census:

```sql
SELECT c.name AS column_name,
       COUNT(DISTINCT OBJECT_NAME(c.object_id)) AS n_tables,
       ty.name AS data_type, c.max_length
FROM sys.columns c
JOIN sys.types ty ON c.user_type_id = ty.user_type_id
WHERE c.object_id IN (SELECT object_id FROM sys.tables)
  AND c.name IN ('ts','obs_date','obs_ts','event_date','event_datetime',
                 'calendar_date','publish_date','last_checked','value',
                 'rate','price','vol','close_level','mid_rate','tenor',
                 'strike','ccy','currency','symbol','ticker','code','display_name')
GROUP BY c.name, ty.name, c.max_length
ORDER BY c.name
```

Results as of 2026-04-24:

| Column | Appears in | Current types |
|---|---|---|
| `tenor` | 5 tables | VARCHAR(5), (10), (15), (30) |
| `ccy` / `currency` | 2 / 2 tables | both VARCHAR(3) |
| `display_name` | 6 tables | VARCHAR(40), (50), (60), (100) |
| `ts` | 2 tables | DATETIMEOFFSET(8)*, (10) |
| `symbol` / `ticker` | 2 / 3 tables | VARCHAR(12,20) / (10,20,50) |
| `value` / `rate` / `price` / `vol` / `close_level` / `mid_rate` | 11 tables total | mix of FLOAT(53), DECIMAL(18,8), DECIMAL(22,8) |

*FX.fact_ohlc.ts is DATETIMEOFFSET(0); rates.fact_observation.ts is DATETIMEOFFSET(7). Silent precision mismatch.

---

# Proposed Standards

## S-1 — Schema names are lowercase snake_case

### Rule
Every schema name is lowercase. No mixed case, no underscores inside
single-word schemas.

### Current state
| Schema | Status |
|---|---|
| `dbo` | ✓ |
| `audit`, `admin`, `calendar`, `commodities`, `equities`, `rates`, `research` | ✓ |
| `FX` | **✗ uppercase** — rename to `fx` |

### Rationale
SQL Server is case-insensitive by default but case-preserving. Tools
(generated DDL, ORM reflection, docs-as-code) emit whatever case the
catalog shows. Mixed case creates friction for no benefit.

### Migration
```sql
-- SQL Server doesn't support schema rename directly; transfer objects.
CREATE SCHEMA fx
GO
-- For each object in FX:
ALTER SCHEMA fx TRANSFER FX.dim_currency_pair
ALTER SCHEMA fx TRANSFER FX.fact_fx_rate
ALTER SCHEMA fx TRANSFER FX.fact_ohlc
ALTER SCHEMA fx TRANSFER FX.fact_vol
GO
DROP SCHEMA FX
```
Then update every Python reference from `FX.` to `fx.` (grep + sed).

---

## S-2 — One name per concept (canonical column vocabulary)

### Rule
Every concept has exactly one canonical column name. Pick one, forbid
aliases.

### Canonical column dictionary
| Concept | Canonical name | Type | Current aliases to retire |
|---|---|---|---|
| Observation calendar day | `obs_date` | `DATE` | `event_date` (keep for events), `calendar_date` (keep on dim_trading_day as PK), `publish_date` (keep on research.dim_report) |
| Observation timestamp | `obs_ts` | `DATETIMEOFFSET(3)` | `ts` — rename to `obs_ts` everywhere |
| Value column on a fact | `{metric}_value` or canonical metric name | see S-3 below | `value` (too generic) |
| Currency (single) | `currency_id` FK to `dbo.dim_currency` | `TINYINT` | `ccy`, `currency` (VARCHAR) |
| Base currency | `base_ccy_id` FK | `TINYINT` | `base_ccy` VARCHAR |
| Quote currency | `quote_ccy_id` FK | `TINYINT` | `quote_ccy` VARCHAR |
| Natural code (short) | `{entity}_code` | `VARCHAR(n)` domain-sized | `symbol`, `ticker`, `tag` (when used as natural key) |
| Human-readable name | `display_name` | `VARCHAR(60)` (default) | `market_name`, `series_name`, `event_name`, `title` (keep the last 3 — they're genuinely different concepts) |
| Boolean flag | `is_{predicate}` | `BIT NOT NULL` | (already consistent) |
| Tenor | `tenor_id` FK to `dbo.dim_tenor` | `SMALLINT` | `tenor VARCHAR(*)` |
| Option strike (numeric) | `strike` | `DECIMAL(18,8)` | `strike VARCHAR(15)` (!) |
| Pipeline run state | `run_status` | `VARCHAR(20)` + CHECK | (already consistent) |

### Rationale
Cognitive savings compound. `obs_ts` means the same thing in every fact,
the same filter clause works in every Grafana panel, the same ORM base
class works for every time-series fact.

### Migration
Per column, per table, in small additive migrations (add new column →
backfill → update writers → drop old). Sequence in P1 of the main audit.

---

## S-3 — Value columns: name them after the metric

### Rule
Facts that store a single numeric measurement name the column after the
metric, not `value`. Facts that store a price tuple (OHLC, bid/ask) keep
the domain-standard names.

### Mapping
| Fact | Current column | Proposed column | Type |
|---|---|---|---|
| rates.fact_observation | `value` | `observed_value` | DECIMAL(18,8) |
| rates.fact_swaption_vol | `value` | `vol` | DECIMAL(9,6) |
| rates.fact_swaption_skew | `vol` | `vol` ✓ | DECIMAL(9,6) |
| rates.fact_bench_rates | `rate` | `rate` ✓ | DECIMAL(9,6) |
| fx.fact_fx_rate | `mid_rate`, `fwd_points` | `mid_rate`, `fwd_points` ✓ | DECIMAL(18,8) |
| fx.fact_vol | `value` | `vol` | DECIMAL(9,6) |
| fx.fact_ohlc | `open_px`, `close_px`, ... | (unchanged) | DECIMAL(18,8) |
| commodities.fact_spot | `price` | `price` ✓ | DECIMAL(18,8) |
| commodities.fact_implied_vol | `vol` | `vol` ✓ | DECIMAL(9,6) |
| commodities.fact_eia | `stat_value` | `stat_value` ✓ | DECIMAL(18,6) |
| equities.fact_index_level | `close_level` | `close_level` ✓ | DECIMAL(18,6) |
| equities.fact_vix | `close_level` | `close_level` ✓ | DECIMAL(18,6) |

### Rationale
`SELECT AVG(value) FROM rates.fact_observation` reads worse than
`SELECT AVG(observed_value)`. Across a union of facts for a dashboard,
`value` is ambiguous; metric-named columns aren't.

---

## S-4 — FK column naming: `{dim_noun}_id`

### Rule
FK column name = the referenced dimension's noun (without the `dim_`
prefix) + `_id`.

### Mapping
| FK column | Refers to | Verdict |
|---|---|---|
| `vendor_id` | `dbo.dim_vendor` | ✓ canonical |
| `currency_id` | `dbo.dim_currency` | ✓ canonical |
| `frequency_id` | `dbo.dim_frequency` | ✓ canonical |
| `country_id` | `dbo.dim_country` | ✓ canonical (replaced `market_id` in the country-anchor restructure, 2026-05) |
| `curve_id` | `rates.dim_curve` | ✓ canonical |
| `commodity_id` | `commodities.dim_commodity` | ✓ canonical |
| `index_id` | `equities.dim_index` | ✓ canonical |
| `pair_id` | `fx.dim_currency_pair` | **✗ rename** to `currency_pair_id` (avoid abbreviation) |
| `cb_id` | `rates.dim_central_bank` | **✗ rename** to `central_bank_id` |
| `surface_id` | `rates.dim_vol_surface` or `rates.dim_skew_surface` | **✗ ambiguous** — rename to `vol_surface_id` / `skew_surface_id` |
| `eia_series_id` | `commodities.dim_eia_series` | ✓ (follows rule) |
| `report_id`, `tag_id` | `research.dim_report`, `research.dim_tag` | ✓ |

### Rationale
Abbreviations like `cb_id` are readable in their native context but
fail in cross-domain queries. `surface_id` is actively ambiguous — two
surface dims exist. Pay the 10 extra characters once, save disambiguation
work forever.

---

## S-5 — Temporal columns: three names, one purpose each

### Rule
Use exactly these three names for time columns:

| Purpose | Column | Type |
|---|---|---|
| The business date the observation represents | `obs_date` | `DATE` |
| The business timestamp the observation represents | `obs_ts` | `DATETIMEOFFSET(3)` |
| The load-time / row-insert timestamp | `created_at` | `DATETIMEOFFSET(3)` |

Non-observation events use domain-natural names that match the concept:
- `event_date` / `event_datetime` for `calendar.cb_events` — OK, it's an event, not an observation
- `publish_date` for `research.dim_report` — OK, publication is not an observation
- `calendar_date` on `calendar.dim_trading_day` — OK, it's the dimension key, not an observation

### Current violations
| Table | Column | Fix |
|---|---|---|
| rates.fact_observation | `ts` | rename → `obs_ts` |
| fx.fact_ohlc | `ts` | rename → `obs_ts` |
| rates.cache_empty_combo | `last_checked` | keep (not an observation) or drop table (see audit P2-20) |

### Migration
```sql
EXEC sp_rename 'rates.fact_observation.ts', 'obs_ts', 'COLUMN'
EXEC sp_rename 'FX.fact_ohlc.ts',           'obs_ts', 'COLUMN'
```
Update all Python references.

---

## S-6 — Standardized VARCHAR sizing for shared vocabularies

### Rule
Every concept has one canonical size. If the domain max exceeds it, use
the larger size *and update this table* (one canonical size per concept).

### Canonical sizes
| Concept | Column names | Canonical size |
|---|---|---|
| ISO 4217 currency code | `code`, `ccy` | `VARCHAR(3)` |
| Tenor code | `tenor`, `tenor_code` | `VARCHAR(10)` |
| Country code (canonical) | `country_code` | `VARCHAR(3)` |
| ~~Market/MIC code~~ | ~~`market_code`~~ | ~~`VARCHAR(5)`~~ — deprecated; replaced by `country_code`/`country_id` in the country-anchor restructure (2026-05) |
| Vendor code | `vendor_code` | `VARCHAR(30)` |
| Frequency code | `frequency_code` | `VARCHAR(10)` |
| Ticker/symbol | `ticker`, `symbol` | `VARCHAR(20)` |
| Generic tag | `tag` | `VARCHAR(50)` |
| Display name (short) | `display_name` | `VARCHAR(60)` |
| Description | `description`, `notes` | `VARCHAR(500)` |
| Free text / long prose | `summary`, `error_message` | `VARCHAR(2000)` or `VARCHAR(MAX)` |

### Current violations
| Table | Column | Current | Fix |
|---|---|---|---|
| rates.fact_observation | tenor | VARCHAR(30) | VARCHAR(10) (also → `tenor_id` via S-2) |
| rates.cache_empty_combo | ccy | VARCHAR(10) | VARCHAR(3) |
| rates.dim_curve | ccy | VARCHAR(10) | VARCHAR(3) |
| rates.fact_observation | quote | VARCHAR(10) | → `quote_id` FK (see audit P1-7) |
| commodities.fact_implied_vol | tenor | VARCHAR(15) | VARCHAR(10) |
| commodities.fact_implied_vol | strike | VARCHAR(15) | DECIMAL(18,8) (see S-7) |
| fx.fact_vol | strike | VARCHAR(15) | DECIMAL(18,8) |
| fx.fact_vol | vol_type | VARCHAR(10) | → FK to dim_vol_type (5-10 enum values) |
| equities.fact_vix | ticker | VARCHAR(10) | merge into fact_index_level (see audit P1-9) |
| dbo.dim_vendor | display_name | VARCHAR(50) | VARCHAR(60) |
| dbo.dim_frequency | display_name | VARCHAR(40) | VARCHAR(60) |
| dbo.dim_currency | display_name | VARCHAR(100) | VARCHAR(60) |
| dbo.dim_country | display_name | VARCHAR(100) | already `display_name` (canonical after country-anchor restructure) |

---

## S-7 — Numeric data must be numeric

### Rule
Fields that represent numbers are stored as numeric types, not strings.
No exceptions for "looks like a code but is really a number."

### Current violations
| Table | Column | Current | Fix |
|---|---|---|---|
| fx.fact_vol | strike | VARCHAR(15) | DECIMAL(18,8) — values are ATM, 25D, 10D, etc. |
| commodities.fact_implied_vol | strike | VARCHAR(15) | DECIMAL(18,8) |

**Caveat for `strike`**: If strike carries mixed representations (delta
codes like "25DC" *and* absolute strikes like "50.00"), the cleanest
design is a `dim_strike(id, strike_type, delta_value, absolute_value)`
and an `strike_id` FK. Either pure-numeric or an enumerated dim — but
never varchar.

### Rationale
String strikes defeat range queries (`WHERE strike BETWEEN 25 AND 50`),
mis-sort on axes (`"10D"` sorts before `"25D"` lexically, correct
numerically is coincidence), and block schema validation.

---

## S-8 — Boolean columns: `is_` prefix, always `BIT NOT NULL`

### Rule
Boolean columns start with `is_`, are `BIT`, and are always `NOT NULL`
with an explicit default. No tri-state booleans (`NULL = unknown`).

### Current state
All booleans already follow this (`is_active`, `is_estimated`, `is_rfr`,
`is_weekend`, `is_holiday`, `is_trading_day`, `is_custom`, `is_primary`,
`is_disabled`, `is_not_trusted`, `health_check_passed`). ✓

### One edge case
`audit.pipeline_runs.health_check_passed` is **nullable**. Reason: NULL =
"health check not run." Prefer `health_check_status VARCHAR(10)` (values:
`'pending'`, `'passed'`, `'failed'`) so NULL has no semantic role. Or
require explicit `0` default and record "not run" as `NULL` in a separate
`health_check_ran_at` column.

---

## S-9 — Bridge/junction tables: `map_{a}_{b}` or `bridge_{a}_{b}`

### Rule
Many-to-many junction tables use `map_` or `bridge_` prefix, not `dim_`.
`dim_` is reserved for entities, not relationships.

### Current state
- `calendar.dim_market_currency` is scheduled for `_old` rename (Phase H of country-anchor restructure). The 1:N relationship it expressed is now captured directly on `dim_currency.country_id`. No bridge table needed.
- `calendar.dim_trading_day` is also scheduled for `_old` rename — no read consumers; Phase D refactor will replace `is_trading_day()` callsites with direct calendar queries.
- `research.map_report_market` and `map_report_tag` ✓ already follow the rule.

---

## S-10 — Reserve vendor-specific columns under a consistent prefix

### Rule
Columns that hold a vendor-specific identifier are prefixed with the vendor
name: `citi_tag`, `bbg_ticker`, `ice_symbol`.

### Current state
| Table | Column | Status |
|---|---|---|
| rates.dim_curve | `citi_prefix` | ✓ vendor-prefixed |
| rates.dim_central_bank | `citi_tag` | ✓ |
| equities.dim_index | `citi_tag` | ✓ |
| commodities.dim_commodity | `spot_tag` | **✗** should be `citi_spot_tag` (it's Citi-specific) |

### Rationale
Once a second vendor is added (BBG, ICE), having `citi_*` makes it trivial
to add `bbg_*` alongside. Unprefixed `spot_tag` implies vendor-agnostic
and will collide.

### Alternative (scales better at N vendors)
Stop putting vendor tags in dim tables. Create:
```sql
CREATE TABLE dbo.dim_vendor_mapping (
  id INT IDENTITY PRIMARY KEY,
  vendor_id INT NOT NULL FK,
  entity_schema VARCHAR(20) NOT NULL,
  entity_table VARCHAR(60) NOT NULL,
  entity_id INT NOT NULL,
  vendor_identifier VARCHAR(200) NOT NULL,
  UNIQUE (vendor_id, entity_schema, entity_table, entity_id)
)
```
One row per (entity, vendor) pairing. Polymorphic but explicit. Defer
until 2+ vendors per entity.

---

## S-11 — Use `dbo` schema for truly cross-domain dimensions

### Rule
A dim that is referenced by facts in **two or more domain schemas** lives
in `dbo`. A dim referenced by only one domain lives in that domain's schema.

### Current state
| Dim | Schema | Referenced by domains | Verdict |
|---|---|---|---|
| `dim_currency` | `dbo` | fx, rates, equities, commodities | ✓ |
| `dim_country` | `dbo` | fx, rates, equities, research, calendar | ✓ (added 2026-05, country-anchor restructure) |
| `dim_frequency` | `dbo` | fx, rates (future: all) | ✓ |
| `dim_vendor` | `dbo` | fx, rates, research (future: all) | ✓ |
| ~~`dim_market`~~ | ~~`calendar`~~ | (deprecated) | replaced by `dbo.dim_country`; awaiting Phase H rename to `_old` |
| `dim_tenor` (proposed in audit P1-7) | `dbo` | rates, fx, commodities | ✓ |

### Resolution
The "where does `dim_market` belong" question is moot — it's being retired. The country-anchor restructure (migrations 037–049) introduced `dbo.dim_country` in the right place from the start (cross-domain `dbo` schema, surrogate `id` preserved from `calendar.dim_market.id` via `IDENTITY_INSERT`). See [country_anchor_design.md](../calendar/country_anchor_design.md).

---

## S-12 — Append-only fact tables do not carry `updated_at`

### Rule
Fact tables are append-only. They have `created_at` but not `updated_at`.
Dimension tables have both (entities can change).

### Rationale
Facts by definition record an observation at a point in time — they
should never be updated. If a fact must change (correction), prefer:
1. Insert a new row with the corrected value + a `revision` column, OR
2. Soft-delete via `is_superseded BIT` + `superseded_by_id INT`

### Current violations
All facts currently carry both `created_at` and `updated_at`. See audit
P2-16 for the drop migration.

---

# Migration Summary (naming-focused)

All migrations below are additive / additive-then-drop. Sequence after
the P0 migrations from the main audit.

| Migration # | Scope | Risk |
|---|---|---|
| 048 | Rename schema `FX` → `fx` | Medium (all Python refs) |
| 049 | Rename `ts` → `obs_ts` on `fact_observation`, `fact_ohlc` | Low |
| 050 | Rename FKs: `pair_id` → `currency_pair_id`, `cb_id` → `central_bank_id`, `surface_id` → `vol_surface_id` / `skew_surface_id` | Medium (all Python refs) |
| 051 | Rename `value` → `observed_value` on `fact_observation`; `value` → `vol` on `fact_swaption_vol`, `fact_vol` | Low |
| 052 | Standardize VARCHAR sizing per S-6 table | Low |
| 053 | Convert `strike` VARCHAR → DECIMAL on `fact_vol`, `fact_implied_vol` | Medium (writer updates) |
| ~~054~~ | ~~Rename `dim_market_currency` → `map_market_currency`~~ — moot; table retiring in Phase H of country-anchor restructure | — |
| 055 | Rename `spot_tag` → `citi_spot_tag` on `dim_commodity` | Low |
| ~~056~~ | ~~Rename `market_name` → `display_name` on `dim_market`~~ — moot; `dim_market` deprecated, `dbo.dim_country.display_name` is the replacement | — |

### Standard rename template
```sql
-- 1. Rename column
EXEC sp_rename '{schema}.{table}.{old_col}', '{new_col}', 'COLUMN'

-- 2. Update ALL Python references (grep then edit)
--    src/imdr/**/*.py, scripts/**/*.py, tests/**/*.py

-- 3. Verify with query harness
SELECT TOP 1 {new_col} FROM {schema}.{table}
```

### Standard retype template (varchar → numeric)
```sql
-- 1. Add new column
ALTER TABLE {schema}.{table} ADD {col}_num DECIMAL(18,8) NULL

-- 2. Backfill with safe parse (errors surface here)
UPDATE {schema}.{table}
SET {col}_num = TRY_CAST({col} AS DECIMAL(18,8))
WHERE {col} IS NOT NULL

-- 3. Verify no parse failures
SELECT COUNT(*) FROM {schema}.{table}
WHERE {col} IS NOT NULL AND {col}_num IS NULL
-- Expect 0. If > 0, inspect and clean source data first.

-- 4. Swap columns
ALTER TABLE {schema}.{table} DROP COLUMN {col}
EXEC sp_rename '{schema}.{table}.{col}_num', '{col}', 'COLUMN'
```

---

# Enforcement

### Pre-commit hook (proposed)
A Python script that parses new migration files and flags:
- Column names matching any `{Avoid → Use}` pair from S-2
- Column types mismatching the S-6 canonical sizes
- Missing `created_at` on new tables
- `updated_at` on new fact tables (violates S-12)
- Uppercase schema names (violates S-1)

### CI schema check
Daily job that runs the "violation census" query from the top of this doc
and fails the build if any new violations appear. Baseline the current
set; track only new regressions until backlog is burned down.

### Update schema_conventions.md
Once this proposal is accepted, fold sections S-1 through S-12 into
[schema_conventions.md](../reference/schema_conventions.md) as the canonical source.
Keep this doc as the historical audit + migration plan.

---

# References

- [Main design audit](2026-04-24_design_audit.md)
- [Existing schema conventions](../reference/schema_conventions.md)
- [Migration index](../../../migrations/)
- [Dim frequency operations](../reference/dim_frequency.md)
- [Dim vendor operations](../reference/dim_vendor.md)
