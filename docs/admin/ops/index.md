# Admin — Operations

Last updated: 2026-06-05

Operational runbooks and playbooks for the IMDR data platform.

- **[weekly_ops.md](weekly_ops.md)** — Weekly and monthly operations checklist: full `scripts/imdr_weekly.py` pipeline registry (EIA → canonical holiday-calendar merge → Korea econ weekly → health dashboard → cleanup) and `scripts/imdr_monthly.py` registry (Korea econ monthly — 19 KOSIS fetchers), data freshness checks, gap fills, vendor credential rotation.
- **[staleness_monitor.md](staleness_monitor.md)** — Staleness monitoring setup and alert thresholds.
- **[bulk_ingestion.md](bulk_ingestion.md)** — Bulk historical ingestion procedures and rate-limit guidance.
- **[cleaning_framework.md](cleaning_framework.md)** — Data cleaning pipeline architecture and rule catalog.
- **[data_cleanup.md](data_cleanup.md)** — Ad-hoc data cleanup procedures (bad rows, outliers, source corrections).
- **[new_product_playbook.md](new_product_playbook.md)** — Step-by-step checklist for onboarding a new data product (domain + table + pipeline + docs).
- **[bbg_intraday_schedule.md](bbg_intraday_schedule.md)** — Windows Task Scheduler setup for the 6×/day BBG FX snapshot ingest.
- **[prediction/](prediction/)** — Prediction market tooling: Polymarket buildout, Polywatch operations, watchlist format, macro snapshot, observations backfill.
