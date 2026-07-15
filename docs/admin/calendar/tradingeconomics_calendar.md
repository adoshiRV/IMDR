# TradingEconomics Calendar — daily refresh + 15-min macro alerter

**Last updated:** 2026-07-16

Single web scraper feeding `calendar.cb_events` from
[tradingeconomics.com/calendar](https://tradingeconomics.com/calendar), with
two consumers:

1. **Daily refresh** — one polite GET, full rolling 4-week window, idempotent UPSERT.
2. **15-minute macro alerter** — same scraper, plus a digest email (`[Macro] …`) when actuals flip from NULL → value or get revised.

> **Distinct from `refresh_cb_events.py`.** That pipeline is monthly,
> Bloomberg-Excel-led, central-bank only. This one is daily, TE-led,
> all-country / all-event, and feeds the same table under a different
> `vendor_id`. The two coexist — they use `vendor_id` to keep namespaces
> separate (see migration 096).

---

## Quick reference

| Topic | Detail |
|-------|--------|
| Source | `https://tradingeconomics.com/calendar` (one polite HTML GET) |
| Target table | `calendar.cb_events` (`vendor_id = 73`, `vendor_code = 'tradingeconomics'`) |
| Window | Rolling **today − 7 days → today + 21 days** (28-day month) |
| Daily cadence | once / day, default `imdr_daily` slot (not auto-wired) |
| Alert cadence | every 15 minutes (Windows Task Scheduler, manual setup) |
| Alert recipients | `IMDR_EMAIL_MACRO_TO` → falls back to `IMDR_EMAIL_TO` |
| Alert threshold | `relevance >= 66` (TE imp 2+3) by default |
| Subject prefix | `[Macro]` — **never `[IMDR]`** (filter-avoidance) |
| Time zone | All times in alert email render in **SGT** |
| Politeness | 5–8s pre-flight jitter, gzip only, robots.txt honoured |

---

## Why TE alongside BBG

The existing `calendar.cb_events` table was populated from a Bloomberg
snapshot (`vendor_id = 4`, ~16,515 rows, 2008-01 onwards) limited to
central-bank rate decisions. TE complements that with:

| | BBG | TradingEconomics |
|---|-----|------------------|
| Coverage | CB rate decisions only | All macro releases (~24 countries, 1,000 events / 4-week window) |
| Provenance | Terminal-licensed | Public website |
| Frequency | Monthly Excel refresh | Daily + intra-day |
| Forward field | Often blank | Consensus + TE-model forecast |
| Released `actual` | Hand-stamped on refresh | Live within 15 min of release |
| Revisions | Not tracked | `revised` column on `previous` |

---

## Architecture

```
                            ┌──────────────────────────────┐
   tradingeconomics.com  ───┤  te_scraper.fetch_calendar   │── polite GET, cookie
   (one GET per run)        │  + parse_calendar_html       │   cal-custom-range
                            └──────────────┬───────────────┘
                                           │ list[TECalendarEvent]
                                           ▼
                            ┌──────────────────────────────┐
                            │  te_scraper.upsert_events    │── MERGE into cb_events,
                            │  (vendor_id=73 namespace)    │   forward-actual guard,
                            └──────────────┬───────────────┘   collision dedupe
                                           │ UpsertResult.actual_changes
                                           ▼
              ┌────────────────────────────┴────────────────────────────┐
              │                                                         │
   ┌──────────▼───────────┐                              ┌──────────────▼─────────────┐
   │ te_calendar_refresh  │                              │  te_release_alert          │
   │ (daily; counts only) │                              │  (15-min; emits emails)    │
   └──────────────────────┘                              └────────────────────────────┘
```

---

## How the scraper works

### URL shape — cookie-based date window

TE's `/calendar` route ignores `?d1=&d2=` query params. The UI sets a
`cal-custom-range` cookie of the form `"YYYY-MM-DD|YYYY-MM-DD"`, then
reloads the page. We follow the same pattern — one polite GET with that
cookie set, no JavaScript needed:

```
Cookie: cal-custom-range=2026-06-04|2026-07-02
```

The default window from `default_window()` is `today − 7d` → `today + 21d`
(rolling 28 days), so even if a daily run is missed for several days, the
next one catches the lookback.

### Politeness posture

- robots.txt re-checked every run (TE allows `/calendar` for our UA)
- 5–8s pre-flight jitter (`random.uniform(5.0, 8.0)`)
- Single request, no retries, no headless browser
- Cloudflare-challenge fingerprint detected; abort with clear error if it fires
- `Accept-Encoding: gzip, deflate` only — `requests` cannot decode brotli without the optional `brotli` package, and TE will send it if you advertise it. This was a footgun on first build.

### Parser

`parse_calendar_html()` reads the `<table id="calendar">` block. Each event
row carries TE's rich data attributes directly — no fragile text parsing:

```html
<tr data-id="393889"
    data-country="euro area"
    data-event="ecb interest rate decision"
    data-symbol="EURR002W"
    data-category="interest rate"
    data-url="/euro-area/interest-rate">
```

Importance comes from a `calendar-date-{1,2,3}` class on the time-cell
span. The country flag/ISO is in a nested table within the row.

### Forward-actual guard (critical)

TE's calendar page shows the **last released level** in the Actual column
for events that haven't released yet — a placeholder, not a real outcome.
Example: BoJ Jun 16 row shows `0.75%` (the currently-held rate) until the
new decision lands on Jun 16.

To prevent contamination we NULL `actual` and `revised` when the release
has not yet happened:

```python
if e.event_datetime is not None:
    event_is_forward = e.event_datetime > now_utc
else:
    event_is_forward = e.event_date >= today_utc   # no-time fallback
```

Time-aware for the ~95 % of TE events that ship a UTC time stamp;
date-based fallback for speeches / no-time events. An event scheduled
today at 12:15 UTC and scraped at 16:00 UTC keeps its actual. A 23:00 UTC
event scraped at 16:00 has actual nulled.

Backfill of pre-existing contamination is in migration 097.

### Country mapping

Most TE ISO-ish codes map directly to `dim_country.country_code`. Two
overrides plus a supranational bucket:

| TE code | Mapped → | Notes |
|---------|---------|-------|
| `EA` | `EU` | TE's "Euro Area" → our Eurozone (TARGET2) row, id=17 |
| `GB` | `UK` | direct alias |
| `WL` | `WW` | TE worldwide signals (FAO Food Index, NY Fed Supply Chain) → "Worldwide", id=49 |
| `OP` | `WW` | OPEC monthly + ministerial → "Worldwide" (provenance kept in `source`) |

Codes with no `dim_country` row are skipped with a warning. Today the
set is empty after the WL/OP overrides.

### Idempotent MERGE

The table has **two** filtered unique indexes (migration 096): one keyed on
`ticker` (`WHERE ticker IS NOT NULL`) and one on `event_name` (`WHERE ticker
IS NULL`). The MERGE ON clause mirrors whichever index is active for the
incoming row:

- `ticker IS NOT NULL` → match by ticker (uses the ticker index)
- `ticker IS NULL` → match by event_name with `tgt.ticker IS NULL` (uses the event_name index)

Matching on event_name alone (pre-2026-06-15) broke when TE renamed an
event instance between runs while keeping its `data-symbol` (e.g. te_id
419028 renamed from `'bonos y obligaciones auction'` → `'14-year obligacion
auction'`): the new name missed the existing row and the INSERT collided on
the ticker index. The fix also adds `event_name` to the `UPDATE SET` so a
ticker-matched row whose TE display-name changed gets refreshed.

The MERGE OUTPUTs `$action`, `inserted.id`, `deleted.actual`,
`inserted.actual` so callers detect per-row changes without a re-query.

`event_name` is normalized (see
[Accent/case collation collision](#accentcase-collation-collision-fixed-2026-07-16)
below) before it ever reaches the MATCH/ON clause or the `UPDATE`/`INSERT`
value list.

#### Placeholder-symbol handling (primary path)

TE attaches `*CALENDAR` data-symbols — `CALENDAR`, `ESP CALENDAR`,
`USD CALENDAR`, `OPECALENDAR`, etc. — to events that have no real
instrument ticker. A single placeholder is shared across many distinct
events (e.g. several Spanish sovereign auctions on one day) and across
multiple runs on different dates, so it cannot serve as a uniqueness key.

`_is_placeholder_symbol()` tests `"CALENDAR" in symbol.upper()` and
**always NULLs the ticker** for matching rows, forcing them through the
event_name uniqueness path. This closes both the within-batch and the
cross-date / cross-run gap — the `ESP CALENDAR` incident on 2026-06-15
that triggered the duplicate-key crash would have been caught here.

#### Within-batch collision backstop

`_build_collision_set()` pre-scans the batch and NULLs the ticker for any
`(event_date, country_id, symbol)` triple that appears more than once —
a backstop for non-placeholder real symbols that TE might happen to re-use
across distinct same-day same-country events.

#### Accent/case collation collision (fixed 2026-07-16)

The `event_name`-keyed unique index (below) is accent- and
case-**insensitive** at the SQL Server collation level, but the feed's
MERGE match key was accent-**sensitive** Python string comparison. An
incoming event name differing from an already-stored row only by
diacritics/case — e.g. TE event 420801, incoming `"ecb vujčić speech"` vs the
stored `"ecb vujcic speech"` — failed to MATCH the existing row, fell through
to the `NOT MATCHED` (INSERT) branch, and the index rejected the insert as a
duplicate (`pyodbc.IntegrityError` 2601). That aborted the whole run —
recurred 3 straight days before being caught.

Fix: `src/imdr/market_calendar/event_name.py::normalize_event_name()`
(NFKD-decompose → strip combining marks → casefold) is now applied in
**both** `te_scraper.py` and `bql_econdata.py` — the two feeds are parallel
mirrored writers to `cb_events`, there is no single shared upsert — as
**both the MERGE match key and the stored value**. Any accent/case variant
of the same event collapses to one canonical byte-identical string before it
reaches the MERGE, so it always matches the existing row and UPDATEs instead
of colliding on INSERT.

Side effect: stored `event_name` is now lowercased. TE's `data-event` slug
was already lowercase, so no visible change there; BQL's title-case names
(e.g. `"MAS Monetary Policy Statement"`) now store lowercase too — the
calendar is casing-consistent across vendors as a result. A display layer
can title-case on render if desired.

**Resilience.** Each row's MERGE now runs inside its own `SAVEPOINT`
(`session.begin_nested()`). A single failing row is logged
(`te.upsert_row_failed` / `bql.upsert_row_failed`) and counted in a new
`errored` field on `UpsertResult`, instead of the exception propagating and
aborting the batch. Both refresh CLIs print `errored` alongside
inserted/updated/unchanged.

**Tests:** `tests/unit/test_event_name.py` (new) plus accent-collision and
per-row-isolation additions to `tests/unit/test_te_scraper.py` and
`tests/unit/test_bql_econdata.py` — 37 pass. Verified live:
`imdr_econ_calendar` (TE+BQL) now runs clean end-to-end (`errored=0`), no
manual row-delete required.

### Vendor-scoped unique indexes (migration 096)

Before this scraper, the unique indexes on `calendar.cb_events` had no
`vendor_id` in the key — BBG's "BOJ Target Rate" and TE's "boj interest
rate decision" would collide. Migration 096 rebuilt them as:

```
UX_cb_events_vendor_date_country_event   (vendor_id, event_date, country_id, event_name) WHERE ticker IS NULL
UX_cb_events_vendor_date_country_ticker  (vendor_id, event_date, country_id, ticker)     WHERE ticker IS NOT NULL
```

Each vendor now has its own dedupe namespace.

`UX_cb_events_vendor_date_country_event` is accent- and case-**insensitive**
(the default SQL Server collation) — see
[Accent/case collation collision](#accentcase-collation-collision-fixed-2026-07-16)
above for the feed-side mismatch this caused and its fix.

---

## How the 15-minute alerter works

### State capture

The scraper emits a `list[ActualChange]` on every refresh. An
`ActualChange` is built when the MERGE output shows
`old_actual != new_actual AND new_actual IS NOT NULL`. Each record
contains the DB `event_id`, country name (joined from `dim_country`),
event slug, old/new actual, previous/consensus/forecast, importance, and
TE URL — enough to render the email row without a re-query.

### Natural idempotency — no audit table required

Once the scraper commits the new actual, the next tick's MERGE sees
`old_actual == new_actual` and emits **zero** changes. A successful
alert is naturally non-repeated. If email send fails, the next tick
will not re-fire — the release is "lost" from email but present in the
DB. Acceptable trade-off; DB is the canonical record.

### Filter

```
qualified = [c for c in result.actual_changes
             if c.relevance >= settings.te_alert_importance_threshold]
```

`relevance` is the TE 1/2/3 importance scale normalised to the BBG
0-100 `relevance` column (1 → 33.33, 2 → 66.67, 3 → 100).

| Threshold env var setting | Practical meaning |
|---|---|
| `IMDR_TE_ALERT_IMPORTANCE_THRESHOLD=66` (default) | TE imp 2 + 3 only — every Fed/ECB/BoJ decision, CPI/NFP/PPI prints, key Asia EM rates |
| `=90` | Only TE imp 3 — heaviest events only |
| `=0` | Everything that changes (speeches, auctions, all confidence indices) |

### Email layout

Brand-aligned to the Picasso design system
([`docs/admin/research/brief_assets/rv_tokens.css`](../research/brief_assets/rv_tokens.css)).
No images, no Google Fonts (Outlook blocks them) — `Public Sans` listed
as a hint with `Segoe UI / Arial` fallbacks; tabular numerals in
`SF Mono / Consolas`.

Visual cues mirror TE's `/calendar` row order:

```
Imp   Time (SGT)   Country         Event                       Actual    Previous  Cons    Forecast
●●●   20:15        Eurozone        ECB Interest Rate Decision  2.15%     2.4%      2.4%    —
●●●   20:30        United States   PPI MoM                     1.1%      0.7%      0.7%    0.3%
●●    22:00        South Korea     Unemployment Rate           2.9%      2.8%      2.8%    2.8%
●     17:30        South Africa    Sacci Business Confidence   131.3     123.6     131     —    revised
```

| Element | Colour (RV token) |
|---------|-------------------|
| Brand bar | `#001830` (rv-dark-blue) with `3px` `#004527` (rv-green) under-rule |
| Count badge | `#B2D0B9` (rv-light-green) on dark blue |
| ●●● high | `#B23A2B` (`--neg`) |
| ●● medium | `#B8862F` (`--warn`) |
| ● low | `#A7A8A8` (`--text-faint`) |
| Actual > consensus | `#004527` (`--pos` / rv-green) |
| Actual < consensus | `#B23A2B` (`--neg`) |
| Numbers | `SF Mono`, tabular-nums |

### Subject lines (verified examples)

Single release:
```
[Macro] Eurozone (TARGET2) ECB Interest Rate Decision 2.15% (vs 2.4% cons) | 20:15 SGT
```

Multi-release digest:
```
[Macro] 4 releases @ 20:30 SGT | top: Eurozone (TARGET2) ECB Interest Rate Decision 2.15%
```

Quiet tick (no email sent, but if forced):
```
[Macro] No releases | 14:00 SGT
```

The subject prefix is `[Macro]` and **must remain non-IMDR** — desk-side
filters keyed on `[IMDR]` would otherwise catch macro alerts.

---

## Run

### Daily refresh (currently manual; not in `imdr_daily.py`)

```powershell
# Default rolling 4-week window
python -m scripts.calendar.te_calendar_refresh

# Custom catchup window
python -m scripts.calendar.te_calendar_refresh --d1 2026-05-01 --d2 2026-05-31

# Dry-run from a saved HTML snapshot (no network, no commit)
python -m scripts.calendar.te_calendar_refresh --dry-run --html-file playground/econ/calendars/_out/te_ok_<stamp>.html
```

### 15-minute alerter

```powershell
# Live tick — fetch, upsert, send email if qualifying changes
python -m scripts.calendar.te_release_alert

# Dry-run — fetch + upsert + classify, print the would-send subject,
# write the body to data\_tmp\te_alert_preview.html, no email
python -m scripts.calendar.te_release_alert --dry-run

# Threshold override (e.g. only high-importance)
python -m scripts.calendar.te_release_alert --threshold 90

# Replay a saved snapshot
python -m scripts.calendar.te_release_alert --dry-run --html-file playground/econ/calendars/_out/te_ok_<stamp>.html
```

### Scheduling (NOT auto-wired)

Per the project's "no prod wiring without permission" rule the alerter
is **not** registered in any orchestrator. To run every 15 minutes via
Windows Task Scheduler:

```powershell
schtasks /Create /SC MINUTE /MO 15 /TN "IMDR Macro Alert" `
  /TR "powershell -Command 'cd Z:\Business\Personnel\Arjun\GitHub\IMDR; python -m scripts.calendar.te_release_alert'" `
  /RL HIGHEST /F
```

The daily refresh can stay manual, or be added to `scripts/imdr_daily.py`
when ready.

---

## Configuration

Add to `.env`:

```
IMDR_EMAIL_ENABLED=true
IMDR_TE_ALERT_ENABLED=true
IMDR_EMAIL_MACRO_TO=adoshi@rvcapital.com   # falls back to IMDR_EMAIL_TO
IMDR_TE_ALERT_IMPORTANCE_THRESHOLD=66      # 66 = TE imp 2+3, default
```

Master switch: `IMDR_TE_ALERT_ENABLED` lets you flip the alerter
independently of the global `IMDR_EMAIL_ENABLED`.

---

## Database

### Schema additions

| Migration | What |
|-----------|------|
| **093** | `cb_events.forecast varchar(20)`, `cb_events.vendor_id INT NULL`, FK to `dim_vendor`, supporting index |
| **094** | Seed `dim_vendor` row: `tradingeconomics` (id=73, vendor_type=`web`, vendor_category=`data_vendor`) |
| **095** | Backfill `vendor_id = 4` (BBG) on all legacy `cb_events` rows where `source='bloomberg'` or NULL |
| **096** | Rebuild filtered unique indexes with `vendor_id` as the lead key |
| **097** | Backfill — NULL `actual`/`revised` on TE rows where `event_date >= today` (one-shot clean-up of pre-guard contamination) |
| **101** | Delete 21 duplicate pairs caused by `*CALENDAR` placeholder leakage (same `te_id` stored twice — once ticker-NULL, once with placeholder ticker); NULL remaining `*CALENDAR` tickers on surviving rows. Post-state: 0 placeholder tickers, 0 collisions. |

### Column mapping (TE → `cb_events`)

| TE column | DB column | Notes |
|-----------|-----------|-------|
| Actual | `actual` | NULLed if `event_datetime > now` |
| Previous | `prior_value` | Trailing `*` parsed into `revised` |
| Consensus | `survey` | Shares column with BBG's analyst-survey median |
| Forecast | `forecast` | TE's ARIMA-derived forecast (new in 093) |
| Importance (1-3) | `relevance` | Normalised → 33.33 / 66.67 / 100 |
| `data-symbol` | `ticker` | NULLed if it is a `*CALENDAR` placeholder (always) or collides within the batch (see MERGE section) |
| `data-id` (instance) | `source` | Stored as `tradingeconomics:<te_id>` for trace |
| `data-url` | not stored | Used by alerter to build click-throughs |
| `data-country` ISO | `country_id` | Via `dim_country` lookup with overrides |

### Useful queries

Top of TE coverage today:
```sql
SELECT TOP 10 c.country_code, e.event_date, e.event_name, e.actual, e.relevance
FROM calendar.cb_events e
JOIN dbo.dim_country c ON c.id = e.country_id
WHERE e.vendor_id = 73
  AND e.event_date = CAST(SYSDATETIMEOFFSET() AS date)
ORDER BY e.relevance DESC, e.event_datetime;
```

Forward releases over the next 3 days, imp ≥ 2:
```sql
SELECT c.country_code, e.event_date, e.event_datetime, e.event_name,
       e.survey AS cons, e.forecast, e.relevance
FROM calendar.cb_events e
JOIN dbo.dim_country c ON c.id = e.country_id
WHERE e.vendor_id = 73
  AND e.event_date BETWEEN CAST(SYSDATETIMEOFFSET() AS date)
                       AND DATEADD(day, 3, CAST(SYSDATETIMEOFFSET() AS date))
  AND e.relevance >= 66
ORDER BY e.event_datetime;
```

Vendor split:
```sql
SELECT v.vendor_code, COUNT(*) AS n, MIN(event_date), MAX(event_date)
FROM calendar.cb_events e
LEFT JOIN dbo.dim_vendor v ON v.id = e.vendor_id
GROUP BY v.vendor_code;
```

---

## Files

| File | Role |
|------|------|
| `src/imdr/market_calendar/te_scraper.py` | Library — fetch, parse, upsert, `ActualChange` dataclass |
| `src/imdr/market_calendar/event_name.py` | Shared `normalize_event_name()` — accent/case-canonical MERGE key + stored value, used by both `te_scraper.py` and `bql_econdata.py` |
| `scripts/calendar/te_calendar_refresh.py` | Daily refresh CLI |
| `scripts/calendar/te_release_alert.py` | 15-min alerter CLI |
| `src/imdr/notifications/formatters/te_release_alert.py` | Subject + HTML formatter (RV palette) |
| `src/imdr/notifications/templates/te_release_alert.html` | Outlook-safe HTML template |
| `migrations/093_add_calendar_cb_events_forecast.sql` | Add `forecast` + `vendor_id` columns |
| `migrations/094_seed_tradingeconomics_dim_vendor.sql` | Seed TE vendor row |
| `migrations/095_backfill_cb_events_bbg_vendor_id.sql` | Tag legacy BBG rows |
| `migrations/096_cb_events_unique_indexes_per_vendor.sql` | Vendor-scoped unique indexes |
| `migrations/097_cb_events_null_te_forward_actuals.sql` | One-shot contamination clean-up |
| `migrations/101_cb_events_null_te_calendar_placeholder_tickers.sql` | Delete dup pairs + NULL `*CALENDAR` tickers (post-fix data clean-up) |
| `playground/econ/calendars/te_quiet_probe.py` | Original scout script (reference) |
| `playground/econ/calendars/te_probe_cookie_range.py` | Cookie-range URL discovery |

---

## Known limitations

- **24-hour lag for `event_date < today` releases** if the alerter is offline during the release window. The 4-week lookback in the daily refresh fills it on the next run.
- **No SMS / Teams / Slack channel** — Outlook email only, per current infra.
- **No quiet-hours / dedupe across same-event multi-revision in one tick** beyond the formatter-level `event_id` collapse.
- **No `cb_event_alerts` audit table** — easy to add if delivery proof is needed.
- **Web-scrape, not paid API** — TE's ToS prohibits scraping at scale. Posture is "one polite GET per tick"; if TE pushes back, the fallback is investing.com's JSON calendar (looser ToS) or TE's $200/mo API tier.
- **Stale name for renamed placeholder events** — if TE renames a `*CALENDAR` event between runs (e.g. an auction series retitled), the old `event_name` can linger as one stale row. No crash, no data loss; the new name is inserted as a second row and both survive. Fully eliminating this would require keying placeholder rows on TE's `te_id` (schema change, deferred).

---

## Out of scope (deliberately)

- Cross-vendor de-duplication (treating BBG and TE observations of the "same" CB event as one row). Today they live as two rows under different `vendor_id`s.
- A separate `te_events` schema. We share `calendar.cb_events` — `vendor_id` discriminates.
- Per-row alert provenance (which user got which alert when). The DB row holds the actual; the email is best-effort.
