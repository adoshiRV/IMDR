# Region / country enrichment — dim_report

Last updated: 2026-06-14

Documents the forward-looking pipeline change and one-time backfill that
populated `research.dim_report.region` and `country_id` for existing
sell-side reports (previously blank on ~95% and ~50% of rows respectively).

## Problem

Per-vendor classifiers emit region as a multi-valued `Tag('region', ...)`.
The single-valued `dim_report.region` column was never populated from those
tags — the orchestrator hardcoded `region=""`. This made well-covered topics
(BoJ ~329 docs, RBA ~160 docs, FOMC) invisible to any region/country filter.

**Scope of the blank-region problem:** only sell-side reports were affected.
Government/econ-vendor rows (fsc, bok, fss, moef, motir, etc.) use a separate
legacy vocab (`ASIA-EM` / `ASIA-DM`) populated by a different path and are
**untouched** by this work.

## Forward-looking fix (durable)

### `region_from_tags()` in canonical.py

Added to `playground/research/ingest/classifiers/canonical.py`:

- `_REGION_TAG_TO_COLUMN` — mapping from every region tag value that any
  vendor classifier emits (both pre-normalised constants like `apac`/`emea`
  and raw vendor labels like `AsiaPacific`/`Japan`/`NorthAmerica`) to the
  canonical column bucket.
- `region_from_tags(tags)` — collapses a report's multi-valued region tags
  into the single `dim_report.region` value. Collapse rules:
  - A lone `global` tag stays `"global"`.
  - An explicit regional bucket wins over a co-occurring `"global"` tag.
  - Two or more distinct regional buckets collapse to `"global"`.
  - No region tag at all → `""` (column stays blank — never guesses).

Column vocab: `americas` / `emea` / `apac` / `latam` / `global` / `""`.

### Wiring into the orchestrator

`playground/research/ingest_today.py` (~line 385) now calls:

```python
region=region_from_tags(tags),
```

replacing the previous `region=""` hardcode. All new ingests populate the
column automatically on the first write.

## One-time backfills (already applied to DB)

### Tag-based backfill — `backfill_region_country.py`

`playground/research/backfill_region_country.py` — propagated existing region
and country tags into `dim_report.region` / `country_id`:

- Scoped to rows with blank `region` column (econ ASIA-EM/ASIA-DM rows are
  already non-blank — the WHERE clause never selects them).
- For country: only assigned `country_id` when exactly one resolvable country
  tag was present; multi-country reports were left NULL.
- Imports `region_from_tags` from `canonical.py` so the backfill cannot drift
  from the live ingest path.
- DRY-RUN by default; `--commit` to write.

Result (committed 2026-06-14):

| bucket   | reports |
|----------|--------:|
| apac     |     955 |
| americas |     673 |
| global   |     647 |
| emea     |     299 |
| latam    |      64 |
| **total region backfilled** | **2,638** |

Country tag-based: 1 row set (reports with a country tag almost always
already had `country_id` from the original ingest).

### Title-heuristic backfill — `backfill_country_from_title.py`

`playground/research/backfill_country_from_title.py` — conservative
title-pattern `country_id` backfill for the sell-side NULLs that carry no
country tag (e.g. macro strategy reports referencing a central bank by name).

Patterns anchored by canonical central-bank / currency identifiers:

| Country | Triggers |
|---------|----------|
| JP | `BoJ`, `JGB`, `JPY`, `Bank of Japan`, `USD/JPY`, `Tokyo CPI`, `Ueda` |
| AU | `RBA`, `AUD`, `Reserve Bank of Australia`, `Australia`, `Aussie` |
| US | `FOMC`, `Federal Reserve`, `Fed`, `UST`, `Jackson Hole`, `Powell`, `Warsh` |
| NZ | `RBNZ`, `NZD`, `Reserve Bank of New Zealand`, `New Zealand` |
| CN | `PBoC`, `CNY`, `RMB`, `People's Bank of China`, `onshore China` |
| IN | `RBI`, `Reserve Bank of India` |

Veto regex prevents single-country assignment on titles that also contain
regional scope words (`ex-Japan`, `Asia`, `APAC`, `global`, `EM`, `G10`,
`emerging`, `cross-asset`, `LATAM`, `EMEA`, `Europe`). Only rows where
**exactly one** country pattern fires and no veto matches receive an
assignment.

Result (committed 2026-06-14): 132 rows set.

## Verification

`playground/research/smoke_region_from_tags.py` — read-only, two checks:

1. Doctests on `canonical.region_from_tags` (10/10 pass).
2. Reconciliation: recomputes `region_from_tags()` for every report with
   a region tag and compares against the column value now in the DB.
   Result: 2,638/2,638 match, 0 mismatch — the pipeline helper reproduces
   the backfilled values exactly.

## DB state after backfill (2026-06-14)

| column | before | after |
|--------|-------:|------:|
| `dim_report.region` populated (non-blank) | 2,194 | 4,832 |
| `dim_report.country_id` populated (non-NULL) | 3,926 | 4,059 |
| Japan (`JP`) | 329 | 366 |
| Australia (`AU`) | 160 | 184 |
| United States (`US`) | 202 | 232 |

## Known remaining gaps

These are genuine data limitations, not bugs:

- **Multi-country sell-side reports stay NULL on `country_id`.** Reports like
  "Asia ex-Japan Equity Strategy" or "EM Rates Weekly" correctly carry no
  single country assignment. This is the correct representation.
- **FOMC FX-desk coverage is thin.** Only 1 FX-desk FOMC doc at time of
  backfill — not a data quality issue with the enrichment, but a coverage gap
  in what gets ingested from FX desks.
- **FOMC June 2026 SEP commentary absent.** The June 2026 FOMC meeting
  occurred after the data cutoff for this backfill. Will populate naturally
  once those reports are discovered and ingested.

## Files

| Path | Role |
|------|------|
| `playground/research/ingest/classifiers/canonical.py` | `region_from_tags()` + `_REGION_TAG_TO_COLUMN` — single source of truth |
| `playground/research/ingest_today.py` | Live wiring: `region=region_from_tags(tags)` on every new ingest |
| `playground/research/backfill_region_country.py` | Tag-based one-time backfill (DRY-RUN by default; `--commit` to write) |
| `playground/research/backfill_country_from_title.py` | Title-heuristic `country_id` backfill (same DRY-RUN / `--commit` pattern) |
| `playground/research/smoke_region_from_tags.py` | Read-only smoke — doctests + pipeline-vs-column reconciliation |
