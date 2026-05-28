# Development tracking

**Linear is the system of record** for development status, prioritization, and ownership.
The markdown files in this directory remain the **detailed design and context** for each
initiative; Linear holds the **live status, priority, and ownership**. Keep the two consistent.

## Where things live

- **Workspace**: [linear.app/imdr](https://linear.app/imdr) — two teams: **IMDR** and **IMDR Lens**
  (two separate products). All work for this repo lives in the **IMDR** team (issue prefix `IMD-`).
- **This directory** (`docs/admin/development/`): one markdown per initiative — the goal, scope,
  open questions, and checklist. The durable design notes.

## How the dev docs map to Linear

| Concept | Linear primitive |
|---|---|
| A specific **end-to-end deliverable** (can be finished and closed) | **Project** |
| The **topic / domain** (fx, rates, schema, calendar, research, refactor, …) | **Label** |
| A small one-line fix, too minor to be a project | **Standalone issue** (no project) |

**Project rule:** a Linear Project must be a specific end-to-end requirement that can actually
*end* — e.g. "Build `rates.fact_govtbond` pipeline", not "Calendar quality". A topic that never
finishes is a label, not a project.

## Ownership

- The **`imdr-pm` agent** keeps Linear in sync with these docs — reconciling statuses, filing new
  issues for newly-surfaced work, and updating project state after work lands. When auditing
  "what's left", read Linear first, then cross-check git + these docs.
- **Security reviews** run periodically, tracked as a **recurring Linear issue** (first instance
  `IMD-38`, monthly) and run by the **`imdr-security` agent** — plus ad-hoc before any commit
  touching credentials, `.env`, a new vendor connector, OAuth/SSO, or file-share paths.

## Initial population (2026-05-27)

Built from the PM inventory of this directory: **16 projects + 33 issues** (`IMD-6`…`IMD-38`) and
12 domain labels. The projects, grouped by theme:

- **Schema/infra**: Country-anchor migration close-out · dim_vendor consolidation ·
  Product & vendor-ticker registry (dim_product) · FX dim_currency_pair FK-only cutover
- **Calendar/quality**: Modern calendar API migration (last_business_day) · Rates hourly cohort-drift hardening
- **Pipelines/data**: SOFR & LIBOR published-fixing ingestion · APAC macro Sprint 1 ·
  Citi quant-signal library — first pipelines
- **Repo health**: Healthchecks subsystem redesign · Full repo lean-pass · Ruff sweep ·
  Extractor errors rename + BatchedCitiExtractor base
- **Observability**: Visualization & monitoring stack
- **Research**: Research RAG quality improvement · Fix GS/MS/Barclays scraper auth + backfill gap
