# Admin — Calendar

Last updated: 2026-07-27

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
- **[cb_events_refresh.md](cb_events_refresh.md)** — Monthly CB events refresh pipeline: Bloomberg Excel import + Asia EM web scrapers, provenance tracking (`is_estimated`, `source` columns). Documents the "soft dates" consumer rule (estimated/sourceless placeholder rows must never be stated as hard scheduled dates — 2026-07-14/15 MAS mis-date incident), the MAS mid-month (14th) fallback flagged for deprecation, and the `playground/econ/cleanup_estimated_cb_events.py` placeholder-row cleanup script.
- **[tradingeconomics_calendar.md](tradingeconomics_calendar.md)** — Daily TE web scrape + 15-min `[Macro]` release alerter. Feeds `cb_events` under `vendor_id=73` alongside BBG; rolling 4-week window via `cal-custom-range` cookie; forward-actual guard; SGT-rendered email digest with RV palette. MERGE ON clause now mirrors the active filtered unique index (ticker vs event_name); `_is_placeholder_symbol()` unconditionally NULLs `*CALENDAR` data-symbols; migration 101 cleaned existing duplicate rows. **2026-07-16:** accent/case collation-collision fix — `event_name.py::normalize_event_name()` now canonicalizes the MERGE match key + stored value in both `te_scraper.py` and `bql_econdata.py`, plus per-row `SAVEPOINT` isolation (`UpsertResult.errored`) so one bad row no longer aborts the batch. **2026-07-27:** scheduling correction — the Windows task `IMDR_econ_calendar` only ever ran this alerter (TE lane), not the joint orchestrator; see `bql_calendar.md` for where the BQL lane is actually scheduled now.
- **[bql_calendar.md](bql_calendar.md)** — Daily Bloomberg BQL calendar refresh, sibling of the TE doc above. Feeds `cb_events` under `vendor_id=4` (BBG). **2026-07-27:** timezone fix — BQL `time` is rendered in a fixed Asia/Singapore (UTC+8) desk timezone, not per-country local time; `event_datetime` now converts to true UTC (`event_date` unchanged); fixes the forward-event guard for Asian-morning releases. Also: wired `bql_calendar_refresh` into `scripts/imdr_daily.py` (the lane had no scheduled runner since 2026-07-17). Documents the known cross-feed date/name divergence between the BQL and TE lanes (not fixed).
- **[country_anchor_design.md](country_anchor_design.md)** — Design rationale for `dbo.dim_country` as the cross-domain geographic anchor, replacing `calendar.dim_market`. Covers migrations 037–049 and the deprecation path.
