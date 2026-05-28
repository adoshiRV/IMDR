# Admin — FX

Last updated: 2026-05-14

FX domain internal documentation: schemas, pipeline architecture, operations runbooks, and vendor integrations.

- **[fx_overview.md](fx_overview.md)** — Operational reference overview for the FX domain: architecture, pipeline scripts, quality checks, and configuration. Entry point for ops.
- **[fx_ohlc_schema.md](fx_ohlc_schema.md)** — Database schema reference for `fx.*` tables (OHLC fact and dimension tables, columns, constraints, indexes).
- **[fx_rate_schema.md](fx_rate_schema.md)** — Schema reference for `fx.fact_fx_rate`: spot + forward outright + forward points, 19 pairs × 11 tenors. Covers migrations 024 and 027 (`obs_ts` retrofit).
- **[fx_rate_pipeline.md](fx_rate_pipeline.md)** — End-to-end architecture of the `fx.citi_rate` pipeline (Citi Velocity → `fx.fact_fx_rate`). Daily and hourly cadences, extractor design, parquet layout.
- **[fx_rate_operations.md](fx_rate_operations.md)** — Operations runbook for `fx.citi_rate`: how to run, monitor, backfill, and troubleshoot.
- **[fx_rate_bbg.md](fx_rate_bbg.md)** — Bloomberg FX rate pipeline operations. Read-only rules for `Z:\BBG_mirror\FX\`, BBG CSV format, and integration with IMDR.
- **[fx_vol_schema.md](fx_vol_schema.md)** — Historical design plan for `fx.fact_fx_vol` (retained as reference; pipeline is live as of 2026-04). 17 pairs × 90 tags.
- **[fx_vol_operations.md](fx_vol_operations.md)** — Operations guide for the FX vol pipeline: running, monitoring, and maintaining `FXVolPipeline`.
- **[calendar_integration.md](calendar_integration.md)** — FX market hours, calendar codes per currency, and how the FX domain integrates with `src/imdr/market_calendar/`.
