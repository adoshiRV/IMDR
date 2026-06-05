# Admin — Calendar

Last updated: 2026-06-05

Global trading calendar module documentation.

> **Canonical holiday calendar.** `calendar.market_holidays` populated from the
> weekly BBG snapshot at `Z:\...\IMDR_MANUAL_UPLOADS\Calendar\YYYY\MM\calendar_YYYYMMDD.xlsx`
> is the single source of truth for IMDR's holiday calendar. The producer
> (`refresh_calendar.py`, Fri 11:00) writes the snapshot; the consumer
> (`scripts.calendar.import_latest_holiday_calendar_snapshot`, wired into
> `imdr_weekly.py`) merges it into the DB idempotently and emails a
> confirmation. Treat this loop as the canonical refresh path — do not load
> holidays into `calendar.market_holidays` via any other route without
> updating this doc.

- **[calendar_module.md](calendar_module.md)** — Full reference for `src/imdr/market_calendar/`: API surface (`is_holiday`, `last_business_day`, `is_trading_day`), 30 calendar codes, countries reference, CB events schema, IMM dates, ISDA centers. Phase D Step 11 complete — modern `(country_code, calendar_code)` API only.
- **[cb_events_refresh.md](cb_events_refresh.md)** — Monthly CB events refresh pipeline: Bloomberg Excel import + Asia EM web scrapers, provenance tracking (`is_estimated`, `source` columns).
- **[country_anchor_design.md](country_anchor_design.md)** — Design rationale for `dbo.dim_country` as the cross-domain geographic anchor, replacing `calendar.dim_market`. Covers migrations 037–049 and the deprecation path.
