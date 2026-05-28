# Database Audits

Dated third-party-style reviews of IMDR schema design, indexing, storage,
and referential integrity. Each audit is a point-in-time snapshot with an
actionable migration playbook.

## Audits

- [2026-04-24 — Design Audit](2026-04-24_design_audit.md) —
  initial baseline. 22 findings across P0/P1/P2 severity. Targets
  ~1.0 GB of ~1.2 GB storage reclamation, 5-20× query-latency win on
  time-range scans, schema uniformity across all fact tables.
- [Naming Convention Standardization Proposal](naming_conventions.md) —
  12 concrete rules (S-1 to S-12) covering schema case, column
  vocabulary, FK naming, VARCHAR sizing, booleans, bridge tables, and
  vendor-specific columns. Includes violation census and rename plan
  (migrations 048-056).

## Cadence

Run a fresh audit **quarterly**, or after any of:
- New domain added (new schema)
- > 2× growth in any fact table
- Migration adds new FK patterns
- Noticeable query-latency degradation

## How to Run

See the re-audit queries block at the top of any dated audit file. All
queries are read-only and use `sys.*` catalog views — safe to run against
production.

## What Belongs Here

- Dated audit files: `YYYY-MM-DD_<scope>_audit.md`
- ADRs for material schema decisions: `ADR-NNNN_<short_name>.md`

Migration SQL always lives in [migrations/](../../../migrations/) with a
sequential numbering pattern; audits here link to the relevant migration
numbers but do not duplicate them.
