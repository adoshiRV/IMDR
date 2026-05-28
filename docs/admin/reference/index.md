# Admin — Reference

Last updated: 2026-05-20

Cross-domain reference docs: naming conventions, dimension table specs, and quota tracking.

- **[schema_conventions.md](schema_conventions.md)** — Canonical naming and design rules for all IMDR tables: `fact_`/`dim_` prefixes, FK patterns, timestamp conventions, compression, clustering.
- **[dim_vendor.md](dim_vendor.md)** — `dbo.dim_vendor` dimension: vendor codes, IDs, and how to add a new vendor.
- **[dim_frequency.md](dim_frequency.md)** — `dbo.dim_frequency` dimension: 10-value ingest-cadence enum (TICK → EVENT) used by all fact tables.
- **[citi_tag_quota.md](citi_tag_quota.md)** — Citi Velocity tag quota management: 100K/24h rolling window, `TagQuotaTracker`, daily batch timing rationale.
- **[scenarios.md](scenarios.md)** — `dbo.dim_scenario` + `scenario_window` + `dim_stress_tag` (+ bridge): PM-curated registry of historical market-stress windows for scenario P&L queries.
