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

## Provenance Columns

Added by migration 012:

| Column | Type | Purpose |
|--------|------|---------|
| `is_estimated` | BIT (default 0) | 1 = date is not officially confirmed |
| `source` | VARCHAR(200) | Origin: "bloomberg", "pboc.gov.cn", "rbi.org.in", "cbc.gov.tw", "bsp.gov.ph", "estimated" |

Use `confirmed_only=True` in query helpers to exclude estimated events:
```python
from imdr.market_calendar.cb_events import upcoming_cb_events
events = upcoming_cb_events(session, market_code="SG", confirmed_only=True)
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

CB events link to FX pairs and rates curves via `dim_market`:

```
cb_events.country_code
    → dim_market.market_code (FK)
    → dim_market_currency.ccy
    → fx.dim_currency_pair.market_code
    → rates.dim_curve.market_code
    → rates.dim_vol_surface.market_code
```

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
