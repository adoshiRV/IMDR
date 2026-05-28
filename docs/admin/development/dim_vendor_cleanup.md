# Follow-up: Clean up `dbo.dim_vendor` duplicates and unused rows

- **Date filed**: 2026-05-13
- **Status**: in progress (Option A — code + migration prepared 2026-05-26; awaiting DB apply)
- **Triggered by**: country-anchor calendar restructure (id 5 `BBG` added for
  the calendar module while id 4 `bloomberg` was already in use by FX/rates
  ingest)

## Apply checklist (Option A, 2026-05-26)

- [x] `VENDOR_CODE` constants flipped to `"BBG"` (3 files)
- [x] BBG health-check SQL flipped to `vendor_code='BBG'` (2 files)
- [x] Pinned test renamed/asserted to `"BBG"` (`tests/unit/test_vendors/test_bbg_no_move.py`)
- [x] Migration 056 applied — **partial** (calendar FKs moved; rename + delete aborted on unique-constraint + FK violation)
- [x] Migration 057 written as recovery — **aborted** (UPDATE id=5→4 on FX/rates fact tables hit unique-index duplicates: stray id=5 rows share business keys with id=4 rows)
- [ ] Apply migration 058 (delete dup id=5 rows where id=4 row exists, promote rest, then finish dim_vendor cleanup)
- [ ] Smoke-test one BBG ingest run per domain (FX rate + rates curves)
- [ ] Run unit tests (`pytest tests/unit`)

### Lessons (so we don't redo this dance)

- `dbo.dim_vendor.vendor_code` has `uq_dbo_dim_vendor_name`. Renaming a row to a value held by another row must happen **after** the other row is deleted, not before. Operation order matters.
- BBG ingest runs hourly and resolves `vendor_code='BBG'` at runtime. Flipping the code constants before the DB rows are consolidated routes new writes to the unwanted id, which then collide on the fact tables' unique indices when you try to merge. Either consolidate the DB row first (rename + delete) **before** flipping code constants, or accept that the merge will need a DELETE-then-UPDATE recovery step.

## Current state

`dbo.dim_vendor` rows relevant to the calendar restructure:

| id | vendor_code         | display_name              | Status |
|----|---------------------|---------------------------|---|
| 4  | `bloomberg`         | Bloomberg                 | **Active** — legacy code, BBG data-ingest pipelines write here |
| 5  | `BBG`               | Bloomberg                 | **Active** — calendar module writes here |
| 6  | `MANUAL`            | Manual override           | Active |
| 7  | `HOLIDAYS_LIB`      | Python holidays package   | **Unused** — zero fact rows |
| 8  | `EXCHANGE_CALENDARS`| Python exchange_calendars | **Unused** — zero fact rows |

## Problem 1 — two `Bloomberg` rows (id 4 and id 5)

Same vendor, two ids. Split happened because the calendar module standardized
on `'BBG'` while the FX/rates ingest pipelines already wrote `'bloomberg'`.

Usage today (FK references to `dbo.dim_vendor`):

| Table                          | vendor_id=4 rows | vendor_id=5 rows |
|--------------------------------|------------------|------------------|
| `FX.fact_fx_rate`              | 725,745          | 0                |
| `rates.fact_observation`       | 513,090          | 0                |
| `calendar.market_holidays`     | 0                | 9,957            |
| `calendar.dim_market_calendar` | 0                | 26               |

Latest writes to id 4: 2026-05-13 (live BBG ingest is still using the legacy
code). The `'bloomberg'` constant is hard-coded in three pipeline modules:

- [src/imdr/domains/fx/pipeline_rate_bbg.py:43](src/imdr/domains/fx/pipeline_rate_bbg.py#L43) — `VENDOR_CODE = "bloomberg"`
- [src/imdr/domains/rates/pipeline_bbg.py:59](src/imdr/domains/rates/pipeline_bbg.py#L59) — `VENDOR_CODE = "bloomberg"`
- [src/imdr/vendors/specs/_bbg_factory.py:34](src/imdr/vendors/specs/_bbg_factory.py#L34) — `VENDOR_CODE = "bloomberg"`

## Problem 2 — `HOLIDAYS_LIB` (id 7) and `EXCHANGE_CALENDARS` (id 8) unused

Declared in code only as fallbacks in `GLOBAL_VENDOR_PRIORITY`
([holidays_db.py:38-43](src/imdr/market_calendar/holidays_db.py#L38-L43))
and referenced in test fixtures
([tests/unit/test_market_holidays.py:52](tests/unit/test_market_holidays.py#L52)).
No ingest path ever populates `calendar.market_holidays` with these
`vendor_id`s, so the priority chain is currently a no-op past `BBG`.

## What needs to happen

### Option A — consolidate Bloomberg and prune unused (recommended)

1. **Merge id 4 into id 5** (or vice versa — pick the keeper):
   - Pick `'BBG'` as canonical (matches calendar convention, all-caps like
     other vendor codes).
   - Update the three `VENDOR_CODE = "bloomberg"` constants to `"BBG"`.
   - Migration: `UPDATE dim_vendor SET vendor_code='BBG', display_name='Bloomberg' WHERE id=4; DELETE FROM dim_vendor WHERE id=5;` — but the calendar tables FK to id 5, so the safer ordering is:
     - Repoint calendar rows: `UPDATE calendar.market_holidays SET vendor_id=4 WHERE vendor_id=5; UPDATE calendar.dim_market_calendar SET trusted_vendor_id=4 WHERE trusted_vendor_id=5;`
     - Rename id 4: `UPDATE dbo.dim_vendor SET vendor_code='BBG' WHERE id=4;`
     - Delete id 5: `DELETE FROM dbo.dim_vendor WHERE id=5;`
   - Bump `VENDOR_CODE` constants and re-run pipelines to confirm lookups
     resolve to id 4.

2. **Decide on `HOLIDAYS_LIB` / `EXCHANGE_CALENDARS`**:
   - **Drop**: remove from `GLOBAL_VENDOR_PRIORITY`, delete the two rows, drop
     test fixtures. Simpler, matches actual data shape.
   - **OR wire them up**: write an ingest path that populates
     `calendar.market_holidays` from the `holidays` and `exchange_calendars`
     PyPI packages — gives a cross-vendor sanity check on BBG holidays.

### Option B — leave id 4/id 5 split, prune 7/8 only

Cheaper if we want to avoid touching the BBG ingest pipelines. Just delete
rows 7 and 8 and remove them from `GLOBAL_VENDOR_PRIORITY`. Leaves the
duplicate Bloomberg rows in place — accept the cosmetic wart in exchange for
not migrating ~1.2M fact rows.

## Watch-outs

- Both calendar tables FK to id 5; any merge into id 4 must repoint those FKs
  before deleting id 5, or the delete will fail.
- `calendar.dim_market_calendar.trusted_vendor_id` is a single-column FK with
  26 rows — small, but it's the source of truth for which vendor's holidays
  to trust per market. Verify the repoint doesn't change resolution behavior.
- Any cached vendor-id lookups in long-running services (none today, but
  worth checking) would need a restart after the merge.
- Update [docs/admin/schema_conventions.md](../reference/schema_conventions.md) §3.8
  vendor-FK rules if we standardize the casing convention (`'BBG'` not
  `'bloomberg'`).

## Estimated effort

- Option A: half a day (one migration + three constant changes + smoke-test
  one BBG run per domain).
- Option B: 30 minutes (delete two dim rows + remove from priority tuple).

## Related

- `MEMORY.md` — `dim_vendor` overview
- [docs/admin/schema_conventions.md](../reference/schema_conventions.md) §3.8 — vendor FK rules
- [docs/admin/updates/2026-05-13_country-anchor-calendar-restructure.md](../updates/2026-05-13_country-anchor-calendar-restructure.md) — the restructure that surfaced this