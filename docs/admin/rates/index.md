# Admin — Rates

Last updated: 2026-05-25

Rates domain internal documentation: schemas, pipeline architecture, operations runbooks, curve catalog, and vendor integrations.

- **[rates_overview.md](rates_overview.md)** — Operational reference overview for the Rates domain: architecture, pipeline scripts, data quality, and configuration. Entry point for ops.
- **[rates_schema.md](rates_schema.md)** — Database schema reference for `rates.*` tables (`dim_curve`, `fact_observation`, and related dims), columns, constraints, and indexes.
- **[rates_operations.md](rates_operations.md)** — Operations guide for setting up, running, and troubleshooting the rates pipeline (daily EOD cadence).
- **[rates_hourly_pipeline.md](rates_hourly_pipeline.md)** — Intraday rates pipeline: Citi Velocity → `rates.fact_observation` at `frequency_id=4` (HOURLY). Anchor-market gate logic, skip-on-close behaviour.
- **[curve_catalog.md](curve_catalog.md)** — Complete inventory of all interest rate curves in IMDR: lifecycle status, data availability, quote type coverage. Source of truth: `src/imdr/universe/rates.yml`.
- **[swaption_vol_schema.md](swaption_vol_schema.md)** — Schema reference for `rates.dim_vol_surface` + `rates.fact_swaption_vol`: 38,056 tags, 11 currencies, 3D vol cube (option_expiry × swap_tenor × type).
- **[swaption_vol_operations.md](swaption_vol_operations.md)** — Operations guide for the rates swaption vol pipeline: running, monitoring, and backfilling.
- **[swaption_skew_schema.md](swaption_skew_schema.md)** — Swaption skew data: normalised implied vol at strike offsets from ATM across option expiry × swap tenor. Sourced from Barclays via email-linked download.
- **[rates_bbg.md](rates_bbg.md)** — Bloomberg rates pipeline operations. Read-only rules for `Z:\BBG\IRS` and `Z:\BBG\OIS`, CSV format, and IMDR integration.
- **[sov_bond_design.md](sov_bond_design.md)** — PROPOSED: bond yield integration. **Cross-domain `dbo.dim_bond_curve`** + `rates.dim_bond_source` (ticker map) + `rates.fact_bond_yield`. Five-axis fact (tenor / quote_type / spread_anchor / fwd_start / horizon) with sentinel values. Sibling facts for bond-future basis + yield forecasts. BBG_mirror seed: 8 curves, 54 source rows + 15 pending placeholders for mirror gaps. Vendor model: BBG_mirror primary, Citi for DM (Citi has zero APAC EM sov coverage).
- **[calendar_integration.md](calendar_integration.md)** — Rates domain calendar integration: EOD scheduling, anchor markets, holiday handling, and `(country_code, calendar_code)` API usage.
