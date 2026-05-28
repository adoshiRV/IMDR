# Database Visualization & Monitoring

## Overview

IMDR is a SQL Server database with 34 tables across 8 schemas (fx, rates,
calendar, commodities, equities, dbo, audit, admin, research) and growing.
As of 2026-04-24 it holds ~1.2 GB, dominated by a handful of fact tables:

| Table                       | Rows      | Size    |
|-----------------------------|-----------|---------|
| rates.fact_observation      | 5,844,540 | 762 MB  |
| fx.fact_ohlc                | 1,100,604 | 205 MB  |
| rates.fact_swaption_vol     | 1,893,416 | 121 MB  |
| rates.fact_swaption_skew    |   767,129 |  48 MB  |
| fx.fact_vol                 |   304,150 |  22 MB  |
| calendar.dim_trading_day    |   420,050 |   8 MB  |

At this size, `SELECT TOP 100 *` in SSMS stops being enough. This doc lays
out the recommended stack for **schema browsing** (what tables exist, how
they relate) and **data monitoring** (is the data fresh, are pipelines
healthy, what's in it).

## Recommended Stack

Three tools, each solving a different problem:

| Tool               | Role                              | Cost | Setup |
|--------------------|-----------------------------------|------|-------|
| Azure Data Studio  | Daily schema + ad-hoc SQL         | Free | 5 min |
| Grafana (OSS)      | Monitoring dashboards + alerting  | Free | 1-2 h |
| SchemaSpy          | One-shot HTML schema docs         | Free | 30 min |

Install in that order. Azure Data Studio replaces SSMS for daily use.
Grafana is the ops/monitoring surface. SchemaSpy produces a committable
HTML wiki of the schema.

---

## Azure Data Studio — schema browsing

Free Microsoft tool, cross-platform, supports Windows Authentication.
Replaces SSMS for day-to-day work.

### What it shows per table
- Columns (name, type, nullable, default, identity)
- Indexes (PK, FK, clustered/non-clustered) with column lists
- Foreign keys — e.g. `fx.fact_fx_rate.pair_id → fx.dim_currency_pair.id`
- Check constraints — e.g. the `fwd_points NULL for SPOT` rule
- Row count, size, partition info
- MS_Description extended properties inline (see "Table descriptions" below)
- Right-click → "Select Top 1000" to preview data
- Query editor with IntelliSense + result grid

### Install
Download: https://aka.ms/azuredatastudio
Connection: server = local machine name, auth = Windows Authentication,
database = `IMDR`.

### Recommended extensions
- **Schema Visualization** — interactive ERD with FK lines
- **SQL Server Dacpac** — compare/export schemas
- **SQL Server Profiler** — trace queries (useful when debugging pipelines)

---

## Grafana — monitoring & dashboards

Grafana is the right fit because **IMDR is almost entirely time-series**.
Every fact table has an `obs_date` or `obs_ts`, and Grafana's native
MSSQL connector + time-series primitives make this cheap to visualize.

### Dashboards to build (in priority order)

**1. Pipeline Health** (from `audit.pipeline_runs`)
- Success/failure rate per pipeline, rolling 7 / 30 days
- Run duration trend — spot slowdowns before they become timeouts
- Last successful run per pipeline — red panel if >24h (daily) or >2h (hourly)
- Rows inserted per run, grouped by domain

**2. Data Freshness** (per fact table)
- Latest `obs_date` / `obs_ts` per table — red if stale vs expected cadence
- Daily row-count growth — flatline = broken feed
- Coverage heatmap: did all 19 FX pairs land today? All 11 swaption currencies?
- Complements `imdr_staleness_check.py` with visual + interactive exploration

**3. Domain dashboards**
- **FX rates**: per-pair line chart, spot vs forward spread by tenor
- **Swaption vol cube**: heatmap of option_expiry × swap_tenor for a chosen
  currency, with time slider
- **Yield curves**: curve shape evolution over time (3D or animated 2D)
- **Commodity vols**: Brent/WTI/XAU surfaces
- **Equity indices**: index levels + VIX family

### Alerting
OSS Grafana includes free alerting. Candidate rules:
- Pipeline failure in last run
- Data stale beyond threshold (replaces / supplements staleness email)
- Row count anomaly (>3σ deviation from 30-day mean)

Route to email (Outlook SMTP) or Slack.

### Install (Docker, recommended)
```bash
docker run -d --name grafana -p 3000:3000 grafana/grafana-oss
```
Then: http://localhost:3000 → add data source → Microsoft SQL Server →
host = `host.docker.internal`, database = `IMDR`, auth = SQL login
(create a read-only login for Grafana — Windows Auth from Docker is painful).

**Note on auth**: Grafana in Docker cannot use Windows Authentication
against the host's SQL Server directly. Either:
- Create a dedicated read-only SQL login (`grafana_ro`) with
  `db_datareader` on IMDR, or
- Run Grafana natively on Windows (no Docker) to use Windows Auth.

Starter dashboard JSONs should live in `docs/admin/visualization/dashboards/`
once built, so they can be version-controlled and re-imported.

---

## SchemaSpy — browsable HTML docs

One-shot tool that generates a static HTML site documenting the entire
schema. Output can be committed to the repo as a wiki.

### What it shows
- Landing page: all tables grouped by schema
- Per-table page with:
  - Column table (name, type, size, null, default, comments, parents, children)
  - Indexes list
  - Inbound/outbound FK diagram — mini ERD per table
  - Sample rows
- Relationship pages: full ERD per schema + cross-schema
- Orphan tables (no FKs) highlighted
- Anomaly report (tables without PKs, implied relationships, etc.)

### Install & run
Requires Java + Graphviz + SchemaSpy JAR + MSSQL JDBC driver.

```bash
java -jar schemaspy.jar \
  -t mssql17 \
  -host localhost \
  -db IMDR \
  -s dbo \
  -u <sql_user> -p <password> \
  -o docs/schema \
  -dp mssql-jdbc.jar
```

Re-run after migrations. Commit `docs/schema/` (or add to `.gitignore`
and regenerate via CI).

---

## Table Descriptions (critical prerequisite)

None of the tables currently have MS_Description extended properties.
Without them, Azure Data Studio and SchemaSpy show column names + types
but no **semantic** context ("what is this table for, what's one row").

Adding descriptions is a one-time migration. Example:

```sql
EXEC sys.sp_addextendedproperty
  @name = N'MS_Description',
  @value = N'Daily FX spot + forward rates from Citi Velocity. One row per (obs_date, pair, tenor).',
  @level0type = N'SCHEMA', @level0name = N'fx',
  @level1type = N'TABLE',  @level1name = N'fact_fx_rate'
```

Planned migration: `migrations/NNN_add_table_descriptions.sql` —
descriptions sourced from the existing pipeline docs
(`docs/admin/fx/fx_rate_pipeline.md`, `docs/admin/rates/swaption_vol_schema.md`,
`docs/admin/calendar_module.md`, etc.) so they match reality.

Once populated, every tool surfaces them inline.

---

## Rollout Checklist

- [ ] Install Azure Data Studio, connect to IMDR via Windows Auth
- [ ] Install Schema Visualization extension
- [ ] Write & apply `NNN_add_table_descriptions.sql` migration
- [ ] Stand up Grafana (Docker or native) with read-only SQL login
- [ ] Build Pipeline Health dashboard (first — highest value)
- [ ] Build Data Freshness dashboard
- [ ] Build per-domain dashboards incrementally
- [ ] Configure alert rules (pipeline failure, staleness)
- [ ] Run SchemaSpy, commit `docs/schema/` HTML output
- [ ] Add re-run step to migration playbook so SchemaSpy stays current

## Related Docs

- [staleness_monitor.md](../staleness_monitor.md) — existing per-key freshness check
- [schema_conventions.md](../reference/schema_conventions.md) — naming + FK conventions
- [weekly_ops.md](../weekly_ops.md) — ops cadence
