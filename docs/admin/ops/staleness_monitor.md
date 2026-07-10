# Data Staleness Monitor

## Overview

The staleness monitor is a cross-domain health check that runs after the
nightly pipeline batch completes. It queries every fact table in IMDR at the
**per-key** level (per-curve, per-pair, per-commodity, per-index) and flags
any series whose latest observation is older than its configured threshold.

This catches **silent upstream feed drops** — situations where the pipeline
reports `success` because it wrote rows, but a subset of series quietly
stopped arriving from the upstream provider. The USD SOFR / CAD CORRA
drop-off after 2026-03-31 is the motivating example.

When a fact table carries vendor or frequency FKs, the monitor also produces
**per-breakdown rollups** so a partial outage (e.g. Bloomberg drops while
Citi keeps publishing, or HOURLY stops while DAILY continues) shows up as a
distinct row instead of being averaged into the surviving feed.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│              scripts/imdr_staleness_check.py                │
│  (standalone runner — also called at end of imdr_daily.py)  │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│        src/imdr/healthchecks/staleness.py                   │
│  StalenessMonitor — iterates DEFAULT_SPECS, queries each    │
│  fact table via AnalyticalReader, returns StalenessReport   │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│  src/imdr/notifications/formatters/staleness_alert.py       │
│  StalenessAlertFormatter — Jinja2 HTML email                │
│  Template: notifications/templates/staleness_alert.html     │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│        src/imdr/notifications/email.py                      │
│  send_outlook_email() — Outlook COM                         │
└─────────────────────────────────────────────────────────────┘
```

## How It Works

For each `StalenessSpec` in `DEFAULT_SPECS`, the monitor builds a SQL query
of the form:

```sql
SELECT
    f.[key_column]                       AS key_id,
    <label expr from dim cols>           AS label,
    -- one extra (code, name) pair per breakdown:
    b0.[vendor_code]   AS vendor_code,    b0.[display_name]   AS vendor_name,
    b1.[frequency_code] AS frequency_code, b1.[display_name] AS frequency_name,
    CAST(MAX(f.[date_column]) AS DATE)   AS latest_date
FROM [schema].[fact_table] f
JOIN [schema].[dim_table]  d  ON d.id = f.[key_column]
JOIN [dbo].[dim_vendor]    b0 ON b0.id = f.[vendor_id]
JOIN [dbo].[dim_frequency] b1 ON b1.id = f.[frequency_id]
WHERE d.<dim_filter>
GROUP BY f.[key_column], <dim cols>, b0.<cols>, b1.<cols>
ORDER BY latest_date ASC
```

- One row per `(key)` when no breakdowns are configured.
- One row per `(key, vendor)`, `(key, frequency)`, or `(key, vendor, frequency)` when breakdowns are configured.
- A row is flagged stale when its age exceeds `max_stale_days`. Age is
  counted in **calendar days** by default, or **business days** (Mon–Fri)
  when the spec sets `business_days=True` — so a Friday observation read on
  Monday is 1 day behind, not 3. See `_days_behind()` in `staleness.py`.

Results are aggregated into a `StalenessReport` with per-domain summaries.
For each enabled breakdown, the monitor also produces a `BreakdownRollup`
list (one entry per distinct value, e.g. one per vendor) collapsed across
the other dims — so a single result set yields **N independent views**
without re-querying.

If any staleness is found, a consolidated HTML email is sent via Outlook.

## Domain Specs

| Domain               | Pipeline                  | Key Column      | Dim Table                    | Breakdowns           | Threshold |
|----------------------|---------------------------|-----------------|------------------------------|----------------------|-----------|
| Rates Curves         | rates.historical          | curve_id        | rates.dim_curve              | vendor + frequency   | 2 business days |
| Rates Swaption Vol   | rates.vol                 | surface_id      | rates.dim_vol_surface        | —                    | 3 days    |
| Rates Swaption Skew  | rates.skew_barclays_daily | surface_id      | rates.dim_skew_surface       | vendor               | 3 days    |
| Rates Benchmark      | rates.bench_rates         | cb_id           | rates.dim_central_bank       | vendor               | 3 days    |
| FX Rate              | fx.citi_rate              | pair_id         | fx.dim_currency_pair         | vendor + frequency   | 3 days    |
| FX Vol               | fx.vol                    | pair_id         | FX.dim_currency_pair         | —                    | 3 days    |
| Commodities Spot     | commodities.spot          | commodity_id    | commodities.dim_commodity    | —                    | 3 days    |
| Commodities Impl Vol | commodities.vol           | commodity_id    | commodities.dim_commodity    | —                    | 3 days    |
| Commodities EIA      | commodities.eia           | eia_series_id   | commodities.dim_eia_series   | —                    | 10 days   |
| Equity Indices       | equity.index              | index_id        | equities.dim_index           | —                    | 2 business days |
| Equity VIX           | equity.vix                | ticker          | (none, string key)           | —                    | 2 business days |

A spec opts into a breakdown by listing it in `breakdowns=(VENDOR_BREAKDOWN, FREQUENCY_BREAKDOWN)`.
The two predefined constants live in `staleness.py` and reference
`dbo.dim_vendor` / `dbo.dim_frequency` respectively. Adding a third
breakdown later is a single `BreakdownDim(...)` declaration plus the
`fk_column` on each fact table that supports it — no SQL builder or
formatter changes needed.

## Usage

### Standalone
```bash
python -m scripts.imdr_staleness_check
python -m scripts.imdr_staleness_check --date 2026-04-13
python -m scripts.imdr_staleness_check --always-email   # send even when all fresh
```

### As part of daily batch
The staleness check runs automatically at the end of `scripts/imdr_daily.py`
after all pipelines complete. It does not block the pipeline exit code —
pipeline failures are reported separately.

### Exit codes
- `0` — all domains fresh
- `1` — at least one key is stale

## Email

- **Subject (stale, with breakdowns)**:
  `[IMDR] STALENESS ALERT | 72 stale key(s) across 2 domain(s) | vendor: bloomberg=6 | frequency: DAILY=3,SNAPSHOT=3 | 2026-04-13`
- **Subject (stale, no breakdowns)**:
  `[IMDR] STALENESS ALERT | N stale key(s) across M domain(s) | 2026-04-13`
- **Subject (fresh)**: `[IMDR] Staleness Check OK | All domains fresh | 2026-04-13`
- **Importance**: High (2) when stale, Normal (1) when fresh
- **Recipients**: `IMDR_EMAIL_TO` from `.env`
- **Sent only when**: `email_enabled=True` and `email_to` is set

The email body includes:
- **Summary table** — domains checked, healthy, stale, total stale keys, plus
  one "Stale by *Dim*" row per breakdown showing aggregate counts across all
  domains (e.g. `bloomberg=6`, `HOURLY=3`).
- **Per-stale-domain section**, with:
  - One **By *Dim*** rollup table per breakdown (counts of stale/fresh per vendor, per frequency).
  - **Per-key detail table** with extra Vendor / Frequency columns (only when that domain has breakdowns).
- **Healthy domains table** with a "Breakdowns" column listing which dims each domain ships.
- Color-coded severity (red >7d, orange >3d).

## Adding a New Domain

When a new fact table is added to IMDR:

1. Add a `StalenessSpec` to `DEFAULT_SPECS` in `src/imdr/healthchecks/staleness.py`.
2. Specify the key column, dimension table (if any), and threshold.
3. If the fact carries `vendor_id`, add `breakdowns=(VENDOR_BREAKDOWN,)` —
   add `FREQUENCY_BREAKDOWN` if `frequency_id` is also present.
4. The monitor will automatically include it on the next run.

## Adding a New Breakdown Dimension

To add a third breakdown (e.g. region, country):

1. Define a `BreakdownDim` constant in `staleness.py`:
   ```python
   COUNTRY_BREAKDOWN = BreakdownDim(
       name="country",
       fk_column="country_id",
       dim_table="[dbo].[dim_country]",
       code_column="country_code",
       name_column="display_name",
   )
   ```
2. Reference it from any spec whose fact table has the FK (currently most
   dim tables in rates/equity/fx carry `country_id` after migrations 044–048):
   ```python
   StalenessSpec(..., breakdowns=(VENDOR_BREAKDOWN, COUNTRY_BREAKDOWN))
   ```
3. Optionally add the dim's name to `_BREAKDOWN_ORDER` in
   `staleness_alert.py` for stable email display order.

The SQL builder, monitor aggregation, formatter, and HTML template all
iterate the breakdown list — no changes required there.

## Tests

```bash
python -m pytest tests/unit/test_staleness.py -v
```

Covering:
- Data model classes (`StalenessSpec`, `BreakdownDim`, `DomainSummary`,
  `BreakdownRollup`, `StalenessReport`)
- SQL builder (`_build_query`) — no-dim, with-dim, with-filter, single
  breakdown, multiple breakdowns
- Monitor logic (all fresh, some stale, all stale, empty tables, boundary conditions)
- **Business-day age** (`_days_behind`, `business_days=True` specs) — weekend
  observations aren't flagged, genuine multi-day stalls are
- **Breakdown aggregation** — vendor splits stale per vendor, two
  breakdowns yield independent rollups, no breakdowns means empty rollups
- Error handling (DB failures are caught, don't crash the monitor)
- Formatter (subject lines, breakdown totals in subject, HTML rendering,
  color coding, edge cases, breakdown rollup section, per-key vendor/frequency columns)
- Default specs validation (all domains covered, dual-vendor specs have
  vendor breakdown, hourly-capable specs have frequency breakdown)

## Design Decisions

1. **Per-key, not per-table**: Table-level freshness (already done by `FreshnessCheck`)
   misses the case where most keys are fresh but a few silently dropped.

2. **Calendar days by default, business days opt-in**: Calendar-day ages
   with a buffer are the right gauge for calendar-cadence feeds (weekly EIA
   at 10 days, monthly econ). Daily *market-data* feeds only publish on
   weekdays, so a calendar buffer either over-alerts across a weekend or
   has to be loosened to a point where it misses a genuine 2-day stall. The
   `business_days=True` flag (added 2026-07-09) counts Mon–Fri only — used
   by the **Rates Curves**, **Equity Indices**, and **Equity VIX** specs at a
   2-business-day threshold so a per-key stall (e.g. AUD 3s6s lagging its
   siblings, or the daily Citi equity batch being starved/skipped) is caught
   without firing on same-day publish lag. Holidays are not modelled:
   weekend-awareness removes the dominant false-positive source and a real
   stall still clears the threshold within a trading day or two. The
   remaining market-data specs (rates vol/skew/bench, FX) stay calendar-day
   for now — flip them per feed if weekend noise appears.

3. **AnalyticalReader, not ORM**: Raw SQL via `AnalyticalReader` is faster for
   aggregate queries and avoids importing all domain ORM models.

4. **Generic `BreakdownDim` list, not hard-coded vendor/frequency fields**:
   The first breakdown was vendor; the second was frequency, requested
   immediately after. Building a generic `breakdowns: tuple[BreakdownDim, ...]`
   abstraction up-front means the third dim (region, country) is a one-line
   change. The SQL builder iterates the list with aliases `b0`, `b1`, …
   so the join logic does not grow with new dims.

5. **One result set, N rollup views**: With breakdowns enabled, the monitor
   queries `(key × vendor × frequency)` once and aggregates the resulting
   DataFrame N+1 times in pandas — once for stale-item detail, once per
   breakdown for rollups. Cheaper than N+1 round-trips and keeps the SQL
   simple.

6. **Separate from FreshnessCheck**: The existing `FreshnessCheck` in
   `src/imdr/healthchecks/checks.py` checks table-level freshness within
   a single pipeline's post-append flow. The staleness monitor is a
   cross-domain, per-key check that runs independently after all pipelines.

## Motivating Incident

This monitor was built in response to the **Easter 2026 rates cache incident**
(see `docs/admin/incidents/2026-04-14_rates_cache_silent_drop.md`). The
`CurveQuoteCache` silently blocked 20/39 rate curves for 2 weeks after a
transient Easter holiday blip. The pipeline reported `success` every night.
Only a per-key staleness check would have caught this.

The vendor + frequency breakdown was added on 2026-04-29 to surface partial
outages — e.g. Bloomberg drops while Citi keeps publishing, or HOURLY stops
while DAILY continues — that would otherwise still trip the per-key check
but be hard to triage from "72 stale keys" alone.

## Known Failure Modes

| Mode | Detection | Example |
|------|-----------|---------|
| **Silent cache lockout** | Per-key staleness >3 days for active curves | Easter 2026: `par` quotes cached as empty for 30 days |
| **Single-vendor outage** | Per-vendor breakdown shows non-zero stale_keys for only one vendor | Bloomberg terminal feed drops, Citi keeps publishing |
| **Single-frequency outage** | Per-frequency breakdown isolates HOURLY vs DAILY | Hourly snapshot job dies overnight, daily run still completes |
| **Upstream feed drop** | Per-key staleness, confirmed by API probe returning 0 | Citi retiring IBOR tags |
| **Pipeline crash** | `audit.pipeline_runs` shows `failed` status | Code bug, network error |
| **Quota exhaustion** | Pipeline skipped in `imdr_daily.py`, `TagQuotaExceeded` in logs | >95K tags in 24h window |
| **EIA weekly lag** | All 66 EIA keys stale >10 days | EIA publication delay or tag format change |
