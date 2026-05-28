# IMDR DB Migration Guides

Guides for **external consumers** when an IMDR release changes the database schema in a way that breaks existing queries.

The audience here is anyone whose code reads IMDR tables directly — your own app, a BI tool (Power BI, Excel, Tableau), a scheduled SQL job, a notebook, an ad-hoc analyst. **These consumers only see the DB**; they don't import the IMDR Python library and don't see internal IMDR refactoring. Each guide is written from that perspective: SQL-only, table-and-column focused, with before/after recipes.

## When to file a new guide

File a guide here when **any** of the following ships in a release:

- A table, view, column, or index that an external query could reference is **dropped, renamed, or has its type changed**.
- A new table replaces an old one and the old one will be removed in a future release.
- The **semantics** of an existing column change (e.g. a date column's timezone shifts, a "default" value changes meaning) — even if the schema technically didn't.
- A **vendor / source filter convention** changes in a multi-vendor table such that "the same query" now returns different rows.

If the change is purely **additive** — new columns with defaults, new optional tables, new indexes — a guide here is not required. Mention it in the relevant feature doc.

## File naming

```
YYYY-MM-DD_short-slug.md
```

The date is the **release date** of the breaking change, not the date the guide was written. Use Q1/Q2/etc. when the exact date is still pending.

Examples:

```
2026-05-13_country-anchor-calendar-restructure.md   ← this directory's first entry
2026-11-02_drop-cb-events-country-code-string.md    ← future
2027-Q1_legacy-calendar-tables-physical-drop.md     ← future
```

## What each guide must include

1. **TL;DR** — one paragraph that a busy SQL consumer can read in 30 seconds to know "do I need to change my queries?"
2. **Affected tables / columns** — every table, column, index an external consumer might touch. Each row marked as: *removed*, *renamed*, *column type changed*, *new replacement*, etc.
3. **Old → new SQL recipes** — exhaustive. For every common query shape against the old table, show the equivalent against the new table. Real, copy-paste-runnable SQL — not pseudocode.
4. **Calendar / lookup tables** — if the change retires a lookup table (like `dim_market_calendar`), embed the lookup as a literal table in the guide so consumers can rebuild it in their own schema.
5. **Vendor / data-source guidance** — when the new structure is multi-vendor (like `market_holidays`), specify which vendor a typical query should filter on, and how to layer overrides.
6. **Timeline** — three boxes: *already happened in earlier releases*, *happens with this release*, *deferred to a later release*. Be specific about which migration number does what.
7. **Verification SQL** — copy-paste smoke queries the consumer can run pre-deploy (to scan their query log) and post-deploy (to confirm the new tables work).
8. **Parity check** — a query that returns the same rows from the old and new schema, so the consumer can verify their rewrite is correct before the old table is renamed.
9. **Reversibility** — for each DB change, document the rollback statement (or "not reversible" with reason). Be explicit about destructive steps.

## Conventions

- **Reference live row counts.** "9,957 rows in `calendar.market_holidays`" beats "many rows" — readers can re-query and verify.
- **No Python content.** External consumers don't import `imdr.*`. If the IMDR Python library also changed, document that in `docs/admin/development/` instead — those docs are for IMDR maintainers, not external consumers.
- **No internal refactor narrative.** Don't explain "Phase D Step 7"; explain "your query needs to change from X to Y because column Z was dropped."
- **Link the migration number.** Every renamed/dropped object should cite the migration that did it (`migrations/050_…sql`), so the consumer can map their backup-timing to the change.

## Index

| Date | Guide | Status |
|---|---|---|
| 2026-05-13 | [Country-anchor calendar restructure](2026-05-13_country-anchor-calendar-restructure.md) | Active — first wave of column drops already shipped; legacy-table rename imminent |
