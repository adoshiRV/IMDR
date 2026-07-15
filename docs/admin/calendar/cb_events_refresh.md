# CB Events Monthly Refresh

Last updated: 2026-07-16

## Overview

The CB events refresh pipeline combines Bloomberg Excel imports with automated web scraping of official central bank websites. It validates both sources against each other and upserts to `calendar.cb_events` with provenance tracking.

## Monthly Workflow

1. **Download Bloomberg CB events** Excel file (multi-sheet format)
2. **Run the refresh script**:
   ```bash
   # Full pipeline: Bloomberg + scrape + validate
   python -m scripts.calendar.refresh_cb_events --bloomberg-file "path/to/file.xlsx" --dry-run
   python -m scripts.calendar.refresh_cb_events --bloomberg-file "path/to/file.xlsx"

   # Scrape only (no Bloomberg file)
   python -m scripts.calendar.refresh_cb_events --scrape-only --year 2026 --dry-run
   python -m scripts.calendar.refresh_cb_events --scrape-only --year 2026
   ```
3. **Review the validation report** — check for DATE_MISMATCH and SCRAPED_ONLY items
4. **Verify in DB**:
   ```sql
   SELECT source, is_estimated, COUNT(*)
   FROM calendar.cb_events
   WHERE event_date >= '2026-01-01'
   GROUP BY source, is_estimated
   ```

## Provenance Columns

Added by migration 012:

| Column | Type | Purpose |
|--------|------|---------|
| `is_estimated` | BIT (default 0) | 1 = date is not officially confirmed |
| `source` | VARCHAR(200) | Origin: "bloomberg", "pboc.gov.cn", "rbi.org.in", "cbc.gov.tw", "bsp.gov.ph", "estimated" |

Use `confirmed_only=True` in query helpers to exclude estimated events:
```python
from imdr.market_calendar.cb_events import upcoming_cb_events
events = upcoming_cb_events(session, country_code="SG", confirmed_only=True)
# Phase D Step 4 (2026-05-13): the parameter is now `country_code=` and
# filters cb_events.country_code directly. The string itself is the country
# business key ("US", "EU", "SG", etc.).
```

### Soft dates — do not state as hard (2026-07-16)

Rows with `source='estimated'` (or `source IS NULL`) **and** no `event_datetime`
**and** no `survey`/`forecast`/`actual` are seeded **placeholders carrying a
guessed date**, not a feed-backed event. They exist so downstream code has
*something* to join against before a real scrape/BQL row lands, not because
the date is known.

Any consumer of `cb_events` — Spider digests, query helpers, ad-hoc SQL —
**must not print or state one of these dates as a confirmed scheduled event**.
Either:
- filter with `confirmed_only=True` (excludes `is_estimated`/`source='estimated'`), or
- cross-check the row against the real feed (TE/BQL, see
  [`tradingeconomics_calendar.md`](tradingeconomics_calendar.md)) or the bank's
  actual announced cadence before quoting a date.

**Incident:** a Spider daily digest (2026-07-14/15 editions) stated the MAS
Monetary Policy Statement as a 14-Jul event, grounded on a `cb_events` row.
Root cause: the MAS mid-month (14th) estimated fallback below — a batch of 4
MAS MPS placeholder rows (Jan/Apr/Jul/Oct 14, 2026), seeded 2026-03-24 with
`source='estimated'`/`NULL`, carried a **wrong** 14th date. The real MAS MPS
window lands later in the month; for July 2026 the TE feed carries the
correct **31-Jul** date. The digest took the estimated 14-Jul placeholder at
face value instead of cross-checking the TE-sourced row.

## Scrapers

Module: `src/imdr/market_calendar/cb_scrapers.py`

| Central Bank | Method | Source | Reliability | Notes |
|-------------|--------|--------|-------------|-------|
| **PBOC** (CN) | Algorithmic | N/A | High | 20th each month, shifted to Mon if weekend |
| **RBI** (IN) | Web scrape | hellobanker.in | High | Scrapes FY schedule; fallback to bimonthly estimates |
| **CBC** (TW) | Web scrape | cbc.gov.tw | High | Scrapes official provisional schedule page |
| **BSP** (PH) | Web scrape | bsp.gov.ph | High | Scrapes "MB Meeting No." patterns from schedule page |
| **MAS** (SG) | Estimated | N/A | Low | No pre-announced dates; uses mid-month estimates (14th) — **deprecation candidate, see below** |

All scrapers have fallback logic — if the web scrape fails, they generate estimated dates and mark `is_estimated=1`.

**MAS mid-month (14th) fallback — flag for deprecation (2026-07-16).** Now
that the TE feed reliably carries the real MAS Monetary Policy Statement date
(see [`tradingeconomics_calendar.md`](tradingeconomics_calendar.md)), the
14th-of-the-month estimate is no longer filling a gap — it actively
**conflicts** with real data (see incident above). Recommendation: deprecate
this fallback in favour of the TE-sourced date. Deleting the existing
placeholder rows is **not durable on its own** — a future failed web scrape
will re-trigger the same fallback logic and re-seed new 14th-dated rows. The
soft-dates rule above (never state an estimated row as hard) is the real,
durable protection until the fallback is actually removed from
`cb_scrapers.py`.

## Validation Report

When both Bloomberg and scraped events are provided, the script prints a comparison:

| Status | Meaning |
|--------|---------|
| `MATCH` | Both sources agree on the date |
| `DATE_MISMATCH` | Same event but different dates (within 3-day window) |
| `SCRAPED_ONLY` | Event found by scraper but not in Bloomberg |
| `BLOOMBERG_ONLY` | Event in Bloomberg but not scraped (for covered countries) |

## Universe Linkage

After the country-anchor restructure (migrations 037–049), CB events link to FX pairs and rates curves via `dbo.dim_country`:

```
cb_events.country_id  ─FK──> dim_country.id
    │
    ├──> dim_currency.country_id  (one country → N currencies)
    │       │
    │       └──> fx.dim_currency_pair.base_currency_id / quote_currency_id
    │
    └──> rates.dim_curve.country_id, rates.dim_vol_surface.country_id,
         rates.dim_skew_surface.country_id, rates.dim_central_bank.country_id,
         equities.dim_index.country_id
```

`cb_events.country_code` is retained as the natural-key business column (one-release deprecation buffer); `country_id` is the canonical FK.

Use `events_for_currency()` to find CB events + affected instruments:
```python
from imdr.market_calendar.cb_events import events_for_currency
results = events_for_currency(session, "JPY", days_ahead=90)
for r in results:
    print(r["event"].event_name, r["affected_fx_pairs"], r["affected_curves"])
```

## Adding a New CB Scraper

1. Add a function to `src/imdr/market_calendar/cb_scrapers.py`:
   - Name: `scrape_{cb_name}_schedule(year)` or `generate_{cb_name}(year)`
   - Return `list[dict]` using `_make_event()` helper
   - Include a `_{cb_name}_fallback(year)` for graceful degradation
2. Add the function call to `scrape_all()`
3. Test with `--scrape-only --dry-run`

## Cleanup: removing placeholder rows

`playground/econ/cleanup_estimated_cb_events.py` is a guarded, backup-first,
dry-run-by-default one-off that deletes seeded placeholder rows matching:

```sql
((source = 'estimated' AND is_estimated = 1) OR source IS NULL)
AND event_datetime IS NULL AND actual IS NULL
AND survey IS NULL AND forecast IS NULL
```

Usage:
```bash
python playground/econ/cleanup_estimated_cb_events.py            # dry-run (default) — lists matches, writes backup, deletes nothing
python playground/econ/cleanup_estimated_cb_events.py --apply     # deletes inside a transaction, verifies count is zero
```

Every run backs up the matched rows to
`playground/econ/cleanup_estimated_cb_events.backup*.json` before any delete,
so the operation is reversible. The 2026-07-16 run removed the 4 MAS MPS
placeholders described in the incident above and left all real TE/BQL feed
rows untouched (the WHERE clause never matches a row that has a real
`event_datetime`, `survey`, `forecast`, or `actual`).

Because the underlying MAS mid-month fallback is still live (not yet
deprecated — see above), a future failed scrape can re-seed matching rows.
This script may need to be re-run periodically until the fallback is removed
from `cb_scrapers.py`; the soft-dates consumer rule is what keeps a stray
re-seeded row from being misread as a hard date in the meantime.

## Files

| File | Role |
|------|------|
| `migrations/012_add_cb_event_provenance.sql` | Schema migration |
| `src/imdr/models/calendar.py` | ORM model (CBEvent) |
| `src/imdr/market_calendar/cb_scrapers.py` | Scraper functions |
| `src/imdr/market_calendar/cb_events.py` | Query helpers |
| `scripts/calendar/refresh_cb_events.py` | Monthly refresh orchestrator |
| `scripts/calendar/import_cb_events.py` | Bloomberg-only import (standalone) |
| `playground/econ/cleanup_estimated_cb_events.py` | One-off: delete seeded `estimated`/`NULL`-source placeholder rows (dry-run default, `--apply` to delete, JSON backup each run) |
