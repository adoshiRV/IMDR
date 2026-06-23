# CB Events Monthly Refresh

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

## BQL SQLite Source (`bloomberg_bql`)

A third source feeds `calendar.cb_events` — the **daily Bloomberg BQL refresh**,
the sibling of the TradingEconomics refresh (`te_calendar_refresh`). Together
BQL + TE are the two canonical event sources behind the calendar.

An upstream process lands a Bloomberg **BQL** Excel pull as a SQLite database at
`Z:\Business\Research\Dashboard\STIRT\db\BQL.EconData.DB` (table `bql_events`,
refreshed ~daily), carrying two datasets — `economic_calendar` (upcoming:
survey + prior, mostly no actual) and `historical_econ_data` (past: actual
filled), ~12.5k rows across the prior ~6 months out to ~7 months forward, for
15 markets (US/JP/UK/EU/AU/CA/KR/NZ/SG/IN/PH/TW/TH/ID/MY).

The pull *appends* daily, so the same logical event recurs as its value is
revised. The loader collapses to ONE row per `(event_date, country, event_name)`
— freshest snapshot wins (non-empty `actual` beats pending; ties broken by
latest `ingested_at`) — giving ~6.5k distinct events.

By default the refresh reads a **rolling T-7 → T+21 window** (mirrors
`te_scraper`): the full history is backfilled once with `--all`, and day-to-day
the only rows that change are actuals/revisions around recent releases, so the
window keeps each run fast (~360 events / ~5s vs ~6.5k / ~100s for a full read).

```bash
# Read-only read + dedup + classify what would change; writes nothing
python -m scripts.calendar.bql_calendar_refresh --dry-run
# Live: rolling T-7 → T+21 window (the daily default)
python -m scripts.calendar.bql_calendar_refresh
# Full reload of the whole file (initial backfill / periodic catch-up for
# newly-scheduled far-future events)
python -m scripts.calendar.bql_calendar_refresh --all
# Point at a different copy of the SQLite DB
python -m scripts.calendar.bql_calendar_refresh --db "path/to/BQL.EconData.DB"
```

Library: `src/imdr/market_calendar/bql_econdata.py` (`refresh()` / `read_bql_events()`
/ `upsert_events()`); thin runner: `scripts/calendar/bql_calendar_refresh.py`.

Mapping / behaviour:

| BQL field | cb_events column | Notes |
|-----------|------------------|-------|
| `date` (+ `time`) | `event_date` / `event_datetime` | datetime stamped UTC (matches `te_scraper`); drives the forward-event guard |
| `name` (→ `display_name` fallback) | `event_name` | full Bloomberg event name; part of the dedup/merge key |
| `country_code` | `country_id` | `GB→UK`, `EZ→EU`; rest resolve directly against `dim_country` |
| `category_label` | `category` | e.g. "Macro economic data", "Central banks / speakers" |
| `survey` / `actual` / `prior` / `revision` | `survey` / `actual` / `prior_value` / `revised` | cleaned (`""`/`--`/`nan`→NULL) + truncated to `varchar(20)` |
| `relevancy` (+ `tier`) | `relevance` | Very High=100 … Very Low=20; `tier_rank` fallback (1→90/2→60/3→30), policy→100 |
| `release_freq` | `frequency` | |
| — | `source` / `vendor_id` | stamped `bloomberg_bql` / `4` (BBG) |

**Lane:** BQL writes the **BBG vendor lane** (`vendor_id=4`) and is its
daily-refresh authority. The MERGE is idempotent on
`(vendor_id, event_date, country_id, event_name)` with `ticker` always NULL (BQL
has no instrument tickers). Within its window BQL supersedes older Excel/legacy
Bloomberg rows in place (one canonical row per event); older BBG history
(pre-window) and the manual Excel path (`import_cb_events`) are untouched. TE
keeps its own vendor lane (`vendor_id=73`).

**Forward-event guard:** an upcoming event should never carry an outcome, so
`actual`/`revised` are NULLed when the event is still in the future (by
`event_datetime` when present, else `event_date >= today`). `period` is a label
("1Q", "May P") not a date, so `period_value` stays NULL.

> **Scheduling:** wired into `scripts/imdr_daily.py` (`PIPELINES`, non-Citi feed,
> `estimated_tags=0`) — runs every daily orchestrator pass. The upstream SQLite
> refreshes daily and the MERGE is idempotent, so re-runs just fill in
> actuals/revisions. Can also be run manually via the CLI above.

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

## Scrapers

Module: `src/imdr/market_calendar/cb_scrapers.py`

| Central Bank | Method | Source | Reliability | Notes |
|-------------|--------|--------|-------------|-------|
| **PBOC** (CN) | Algorithmic | N/A | High | 20th each month, shifted to Mon if weekend |
| **RBI** (IN) | Web scrape | hellobanker.in | High | Scrapes FY schedule; fallback to bimonthly estimates |
| **CBC** (TW) | Web scrape | cbc.gov.tw | High | Scrapes official provisional schedule page |
| **BSP** (PH) | Web scrape | bsp.gov.ph | High | Scrapes "MB Meeting No." patterns from schedule page |
| **MAS** (SG) | Estimated | N/A | Low | No pre-announced dates; uses mid-month estimates (14th) |

All scrapers have fallback logic — if the web scrape fails, they generate estimated dates and mark `is_estimated=1`.

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

## Files

| File | Role |
|------|------|
| `migrations/012_add_cb_event_provenance.sql` | Schema migration |
| `src/imdr/models/calendar.py` | ORM model (CBEvent) |
| `src/imdr/market_calendar/cb_scrapers.py` | Scraper functions |
| `src/imdr/market_calendar/cb_events.py` | Query helpers |
| `scripts/calendar/refresh_cb_events.py` | Monthly refresh orchestrator |
| `scripts/calendar/import_cb_events.py` | Bloomberg-only import (standalone) |
