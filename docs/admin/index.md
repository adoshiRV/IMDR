# IMDR Admin Documentation

Last updated: 2026-05-20

Administrative, operational, and reference documentation for the IMDR project. Domain-specific schema and pipeline docs live in `docs/{domain}/`.

## Sections

- **[setup/](setup/)** — Developer environment setup: VS Code, MCP server, Claude Desktop configuration.
- **[ops/](ops/)** — Operational runbooks: weekly ops checklist, staleness monitor, bulk ingestion, cleaning framework, data cleanup, new-product playbook, BBG intraday schedule, prediction tools.
- **[reference/](reference/)** — Cross-domain reference: schema conventions, dimension table specs (`dim_vendor`, `dim_frequency`, `citi_tag_quota`).
- **[calendar/](calendar/)** — Trading calendar module: calendar_module, CB events refresh, country-anchor design.
- **[db_audit/](db_audit/)** — Database design audits and naming convention proposals.
- **[development/](development/)** — PM-owned task threads, in-progress design notes, tech-debt tracking. Do not edit without PM approval.
- **[incidents/](incidents/)** — Post-incident writeups.
- **[updates/](updates/)** — Consumer-impact migration guides (one file per breaking change).
- **[qdrant/](qdrant/)** — Qdrant vector-DB server: install, lifecycle, config, schema. Peer of MSSQL.
- **[research/](research/)** — Research-vendor scraper docs and retrieval concepts.
- **[vendors/](vendors/)** — Vendor framework docs (BBG, Barclays, Citi) and feed-specific notes.
