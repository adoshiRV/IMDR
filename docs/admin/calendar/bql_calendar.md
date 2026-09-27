# Bloomberg BQL Calendar — daily refresh

**Last updated:** 2026-07-27

Loader for the Bloomberg **BQL** economic-calendar feed — the sibling of
[`tradingeconomics_calendar.md`](tradingeconomics_calendar.md) (TradingEconomics). Together
BQL and TE are the two canonical sources behind `calendar.cb_events`.

---

## Quick reference

| Topic | Detail |
|-------|--------|
| Source | `BQL.EconData.DB` — SQLite, produced by an upstream Bloomberg BQL Excel pull, refreshed ~daily (STIRT dashboard share) |
| Source path | `Z:\Business\Research\Dashboard\STIRT\db\BQL.EconData.DB` (`bql_econdata.DEFAULT_DB`) |
| Target table | `calendar.cb_events`, **BBG vendor lane** (`vendor_id = 4`, `vendor_code = 'BBG'`) — supersedes legacy Bloomberg-Excel rows in the same lane on the shared `(vendor_id, event_date, country_id, event_name)` unique index |
| Window | Rolling **T−7 → T+21** daily; `--all` for a full-history reload |
| Schedule | `scripts/imdr_daily.py` PIPELINES list (isolated subprocess, `estimated_tags: 0`) — see [Scheduling](#scheduling) below |
| Dedup | One row per `(event_date, country_code, event_name)`; multiple daily-pull snapshots of the same event collapse to the freshest (non-empty `actual` wins, ties broken by latest `ingested_at`) |
| `event_name` | Normalized via `imdr.market_calendar.event_name.normalize_event_name()` — shared with `te_scraper.py`, see [tradingeconomics_calendar.md](tradingeconomics_calendar.md#accentcase-collation-collision-fixed-2026-07-16) |
| Resilience | Per-row `SAVEPOINT`; one bad row logs (`bql.upsert_row_failed`) and is skipped (`UpsertResult.errored`) instead of aborting the run |

---

## Timezone fix (2026-07-27)

**Bug:** `_parse_datetime()` in `src/imdr/market_calendar/bql_econdata.py` previously stamped
Bloomberg-rendered `(date, time)` values as if they were already UTC. They are not.

**Root cause, confirmed empirically:** cross-referencing released BQL events against the TE
lane's true-UTC `event_datetime` for the *same release* across KR/US/UK/AU/EU/JP showed a
uniform **+8h** offset. BQL's `time` column is rendered in a fixed **Asia/Singapore (UTC+8)**
desk timezone — not each country's local time, and not UTC. Singapore has no DST, so this is a
constant offset, not a rule that needs revisiting twice a year.

**Fix:**

```python
_BQL_TZ = ZoneInfo("Asia/Singapore")
```

The naive `(date, time)` pair is localized as SGT, then converted to the true UTC instant:

```python
local = datetime(d.year, d.month, d.day, t.hour, t.minute, t.second, tzinfo=_BQL_TZ)
return local.astimezone(timezone.utc)
```

**What changed vs. what didn't:**

| Field | Before | After |
|---|---|---|
| `event_datetime` | Naive local time mislabeled as UTC | True UTC instant |
| `event_date` | Source SGT calendar day | **Unchanged** — deliberately left as the source-provided SGT local date (the correct local-day bucket for the release) |

**Consequence:** the forward-event guard (`event_datetime > now` ⟹ NULL the `actual`/`revised`
for an event that hasn't released yet, see `upsert_events()`) now evaluates correctly. Before
the fix, an already-released Asian-morning print could land on the wrong side of "now" (the
naive SGT time compared directly against a true-UTC `now`) and have its real `actual` wrongly
stripped on upsert.

**Tests:** `tests/unit/test_bql_econdata.py` — 20 pass.

> ⚠ This fix is scoped to the **BQL SQLite lane**. See
> [calendar_module.md § `event_datetime` Convention](calendar_module.md#event_datetime-convention-important)
> for how this interacts with the older, still-valid convention for legacy Bloomberg-Excel-import
> rows that share the same `vendor_id = 4` lane.

---

## Scheduling

**Before 2026-07-27:** the BQL lane had no scheduled runner. It had been frozen since
2026-07-17. The Windows task literally named `IMDR_econ_calendar` does **not** run the joint
`scripts.calendar.imdr_econ_calendar` orchestrator (TE+BQL) — despite the name, it runs
`scripts.calendar.te_release_alert`, a **TE-only** 15-minute refresh + release-alert emailer
(vendor 73). That task never touched the BQL lane.

**Now:** `scripts.calendar.bql_calendar_refresh` is a registered step in
`scripts/imdr_daily.py`'s `PIPELINES` list — an isolated subprocess, `estimated_tags: 0`, bound
via `sys.executable` (needs the `imdr` conda env + the STIRT `Z:` share). `imdr_daily` runs
08:00 SGT daily per its module docstring (`scripts/imdr_daily.py`), giving the BQL lane a
reliable scheduled home for the first time.

**Net state of the two feeds:**

| Feed | Vendor lane | Scheduled by | Cadence |
|---|---|---|---|
| TradingEconomics | 73 | `te_release_alert` (Windows task `IMDR_econ_calendar`) | every 15 min |
| Bloomberg BQL | 4 (BBG) | `scripts/imdr_daily.py` | ~2×/day (imdr_daily slots) |
| Joint orchestrator (`imdr_econ_calendar.py`) | both | **not itself scheduled** | manual — ad-hoc dual-feed dry-run / backfill helper only |

`scripts.calendar.imdr_econ_calendar` still exists and works (`--te-only` / `--bql-only` /
`--bql-all` / `--dry-run`) — it is just not the thing either Windows task actually runs. Treat
it as a manual convenience wrapper, not a production entry point.

---

## Known limitation — cross-feed date/name divergence (not fixed)

The same underlying release can be bucketed under **different `event_date`s** and carry
**different `event_name`s** across the two vendor lanes, and the two lanes do not currently
reconcile:

- **Date:** BQL buckets on the **SGT local day** (see `event_date` above); TE buckets on the
  **true-UTC day** — for an Asian-morning release, TE's UTC day is often the **prior calendar
  day** relative to BQL's SGT day.
- **Name:** BQL and TE independently generate event names — e.g. BQL's `"Natl CPI YoY"` vs
  TE's generic `"inflation rate yoy"` for the same country/release.

Net effect: querying `cb_events` for "did country X's CPI print land in this window" by a
single `(event_date, event_name)` shape can miss the other lane's row entirely. This is a real
gap — it caused a Japan CPI print to be overlooked in a Spider daily digest. See
[`tradingeconomics_calendar.md` § Out of scope](tradingeconomics_calendar.md#out-of-scope-deliberately)
for the existing "cross-vendor de-duplication is not done" framing; this note makes the
concrete failure mode explicit.

This is documented as a **known limitation / future reconciliation work**, not a fix. No code
change has been made for it. Until it lands, downstream consumers (Spider, ad-hoc SQL) should
check **both** vendor lanes for a given country/date-range rather than assuming one lane's
absence means "nothing happened" — see
[`spider_daily_spec.md`](../research/spider_daily_spec.md) for the consumer-side caution.

---

## Files

| File | Role |
|------|------|
| `src/imdr/market_calendar/bql_econdata.py` | Library — read SQLite, dedup, `_parse_datetime` (SGT→UTC), upsert |
| `src/imdr/market_calendar/event_name.py` | Shared `normalize_event_name()` — used by both `bql_econdata.py` and `te_scraper.py` |
| `scripts/calendar/bql_calendar_refresh.py` | Daily refresh CLI — registered in `scripts/imdr_daily.py` |
| `scripts/calendar/imdr_econ_calendar.py` | Manual joint TE+BQL orchestrator (not itself scheduled) |
| `tests/unit/test_bql_econdata.py` | Unit tests, incl. the SGT→UTC timezone fix (20 pass) |

---

## Out of scope (deliberately)

- Cross-vendor de-duplication / reconciliation (see [Known limitation](#known-limitation--cross-feed-datename-divergence-not-fixed) above) — shared with `tradingeconomics_calendar.md`.
- Renaming or removing the Windows task `IMDR_econ_calendar` — its actual behavior (TE-only via `te_release_alert`) is documented here as a fact, not changed.
