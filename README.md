# IMDR

IMDR (Internal Market Data Repository) is the firm's scheduled ingestion and storage layer for financial market data across FX, rates, equity, and commodities. Data is sourced from Citi Velocity, the Bloomberg share (via an external R pipeline), BidFX, and a small number of research and email-linked vendor feeds. Each successful pipeline run writes to SQL Server (the `IMDR` database) and archives a parquet copy under `data/parquet/`.

## Documentation

- `docs/admin/` — operations, infrastructure, schema conventions, scheduling, and vendor notes
- `docs/admin/vendors/` — per-vendor admin docs (BBG, Barclays, Citi, BidFX) and the vendor framework
- `docs/fx/`, `docs/rates/`, `docs/equity/`, `docs/commodities/` — per-domain schemas, pipelines, and operations guides
- `docs/admin/development/` — open development tasks and the lean-pass repo review (`full_repo_review.md`)

## Setup

Activate the `imdr` conda environment. The database uses MSSQL with Windows Authentication (no password required on a domain-joined machine). All configuration is read from `.env` using the `IMDR_` prefix — copy `.env.example` and fill in the required values before running anything.

## Running a pipeline

```
python -m scripts.fx.citi.fx_rate_citi_live
python -m scripts.run_pipeline <name>
```
