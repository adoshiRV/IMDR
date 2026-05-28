# A3 — Live Schema vs Migrations Drift Report

- **Filed**: 2026-05-14
- **Migrations scanned**: 51
- **Live tables (MCP `list_tables`)**: 41
- **Intended after replay**: 38

## Method

Regex-extract `CREATE TABLE` / `DROP TABLE` / `sp_rename` statements from each
migration in file order. Comments stripped. Replay the additions/removals to
compute the *intended* end state, then diff against the live table list.

**Caveats**: regex parser — misses dynamic SQL, schema-bound views, ALTERs that
create columns rather than tables. Use this as a first-pass drift report, not a
schema source of truth.

## Match — table in both migrations and DB (38)

Healthy state.

<details><summary>Show 38 tables</summary>

| Table | Last action |
|---|---|
| `admin.mcp_query_log` | 006_create_admin_mcp_query_log.sql CREATE |
| `audit.pipeline_runs` | 001_create_pipeline_runs.sql CREATE |
| `calendar.cb_events` | 008_create_calendar_schema.sql CREATE |
| `calendar.dim_calendar` | 031_create_calendar_market_holidays.sql CREATE |
| `calendar.dim_market_calendar_old` | 050_rename_legacy_calendar_tables.sql RENAME from dim_market_calendar |
| `calendar.dim_market_currency_old` | 050_rename_legacy_calendar_tables.sql RENAME from dim_market_currency |
| `calendar.dim_market_old` | 050_rename_legacy_calendar_tables.sql RENAME from dim_market |
| `calendar.dim_trading_day_old` | 050_rename_legacy_calendar_tables.sql RENAME from dim_trading_day |
| `calendar.market_holidays` | 031_create_calendar_market_holidays.sql CREATE |
| `commodities.dim_commodity` | 013_create_commodities_schema.sql CREATE |
| `commodities.dim_eia_series` | 013_create_commodities_schema.sql CREATE |
| `commodities.fact_eia` | 014_create_cmdty_fact_tables.sql CREATE |
| `commodities.fact_implied_vol` | 014_create_cmdty_fact_tables.sql CREATE |
| `commodities.fact_spot` | 014_create_cmdty_fact_tables.sql CREATE |
| `dbo.dim_country` | 037_create_dim_country.sql CREATE |
| `dbo.dim_currency` | 021_create_dim_currency.sql CREATE |
| `dbo.dim_frequency` | 023_create_dim_frequency.sql CREATE |
| `dbo.dim_vendor` | 018_create_dim_vendor.sql CREATE |
| `equities.dim_index` | 015_create_equities_schema.sql CREATE |
| `equities.fact_index_level` | 015_create_equities_schema.sql CREATE |
| `equities.fact_vix` | 015_create_equities_schema.sql CREATE |
| `fx.dim_currency_pair` | 004_create_fx_dim_currency_pair.sql CREATE |
| `fx.fact_fx_rate` | 024_create_fx_fact_fx_rate.sql CREATE |
| `fx.fact_vol` | 005_create_fx_fact_vol.sql CREATE |
| `rates.cache_empty_combo` | 003_create_cache_empty_combo.sql CREATE |
| `rates.dim_central_bank` | 020_create_rates_bench_rates.sql CREATE |
| `rates.dim_skew_surface` | 017_create_rates_swaption_skew.sql CREATE |
| `rates.dim_vol_surface` | 007_create_rates_swaption_vol.sql CREATE |
| `rates.fact_bench_rates` | 020_create_rates_bench_rates.sql CREATE |
| `rates.fact_swaption_skew` | 017_create_rates_swaption_skew.sql CREATE |
| `rates.fact_swaption_vol` | 007_create_rates_swaption_vol.sql CREATE |
| `research.dim_embedding_model` | 033_create_research_chunks_and_embeddings.sql CREATE |
| `research.dim_report` | 019_create_research_schema.sql CREATE |
| `research.dim_tag` | 019_create_research_schema.sql CREATE |
| `research.fact_chunk` | 033_create_research_chunks_and_embeddings.sql CREATE |
| `research.fact_chunk_embedding` | 033_create_research_chunks_and_embeddings.sql CREATE |
| `research.map_report_market` | 019_create_research_schema.sql CREATE |
| `research.map_report_tag` | 019_create_research_schema.sql CREATE |

</details>

## In migrations only — never applied or already rolled back (0)

If non-empty, these are migrations whose CREATE survived our replay but the
table isn't in DB. Either the migration was never applied, or our parser
missed a downstream DROP/rename.

| Table | History |
|---|---|

## In DB only — no creating migration found (3)

Either the table predates `migrations/` (e.g., `dbo.*` dims may have been
seeded by hand), or our regex missed the CREATE.

| Table |
|---|
| `fx.fact_ohlc` |
| `rates.dim_curve` |
| `rates.fact_observation` |

## Suspicious patterns flagged for D5 (Calendar) review

- `calendar.dim_market_calendar_old`, `dim_market_currency_old`, `dim_market_old`,
  `dim_trading_day_old` — `_old` suffix tables from migration 050 rename. Confirm
  no live code reads from them; schedule a future migration to DROP.
- `calendar.dim_calendar` (live) — successor to several `_old` tables; verify
  population is complete before dropping the old ones.
