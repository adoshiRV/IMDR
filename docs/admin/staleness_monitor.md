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

1. For each `StalenessSpec` in `DEFAULT_SPECS`, the monitor runs:
   ```sql
   SELECT f.[key_column], d.[label_cols], MAX(f.[date_column]) AS latest_date
   FROM [schema].[fact_table] f
   JOIN [schema].[dim_table] d ON d.id = f.[key_column]
   GROUP BY ...
   ```

2. Any key whose `latest_date < reference_date - max_stale_days` is flagged.

3. Results are aggregated into a `StalenessReport` with per-domain summaries.

4. If any staleness is found, a consolidated HTML email is sent via Outlook.

## Domain Specs

| Domain               | Pipeline            | Key Column      | Dim Table             | Threshold |
|----------------------|--------------------|-----------------|-----------------------|-----------|
| Rates Curves         | rates.historical   | curve_id        | rates.dim_curve       | 3 days    |
| Rates Swaption Vol   | rates.vol          | surface_id      | rates.dim_vol_surface | 3 days    |
| Rates Swaption Skew  | rates.skew_barclays_daily | surface_id | rates.dim_skew_surface | 3 days  |
| FX Vol               | fx.vol             | pair_id         | FX.dim_currency_pair  | 3 days    |
| Commodities Spot     | commodities.spot   | commodity_id    | commodities.dim_commodity | 3 days |
| Commodities Impl Vol | commodities.vol    | commodity_id    | commodities.dim_commodity | 3 days |
| Commodities EIA      | commodities.eia    | eia_series_id   | commodities.dim_eia_series | 10 days |
| Equity Indices       | equity.index       | index_id        | equities.dim_index    | 3 days    |
| Equity VIX           | equity.vix         | ticker          | (none, string key)    | 3 days    |

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

- **Subject (stale)**: `[IMDR] STALENESS ALERT | N stale key(s) across M domain(s) | 2026-04-13`
- **Subject (fresh)**: `[IMDR] Staleness Check OK | All domains fresh | 2026-04-13`
- **Importance**: High (2) when stale, Normal (1) when fresh
- **Recipients**: `IMDR_EMAIL_TO` from `.env`
- **Sent only when**: `email_enabled=True` and `email_to` is set

The email includes:
- Summary table (domains checked, healthy, stale, total stale keys)
- Per-domain stale key detail (series name, latest date, days behind, threshold)
- Healthy domains table (domain, pipeline, key count, latest date)
- Color-coded severity (red >7d, orange >3d)

## Adding a New Domain

When a new fact table is added to IMDR:

1. Add a `StalenessSpec` to `DEFAULT_SPECS` in `src/imdr/healthchecks/staleness.py`
2. Specify the key column, dimension table (if any), and threshold
3. The monitor will automatically include it on the next run

## Tests

```bash
python -m pytest tests/unit/test_staleness.py -v
```

29 tests covering:
- Data model classes (StalenessSpec, DomainSummary, StalenessReport)
- Monitor logic (all fresh, some stale, all stale, empty tables, boundary conditions)
- Error handling (DB failures are caught, don't crash the monitor)
- Formatter (subject lines, HTML rendering, color coding, edge cases)
- Default specs validation (all domains covered, correct thresholds)

## Design Decisions

1. **Per-key, not per-table**: Table-level freshness (already done by `FreshnessCheck`)
   misses the case where most keys are fresh but a few silently dropped.

2. **Calendar days, not business days**: Business-day awareness would require
   per-market calendar lookups for each key. Calendar days with a 3-day buffer
   naturally accommodate weekends. The EIA spec uses 10 days for its weekly cadence.

3. **AnalyticalReader, not ORM**: Raw SQL via `AnalyticalReader` is faster for
   aggregate queries and avoids importing all domain ORM models.

4. **Separate from FreshnessCheck**: The existing `FreshnessCheck` in
   `src/imdr/healthchecks/checks.py` checks table-level freshness within
   a single pipeline's post-append flow. The staleness monitor is a
   cross-domain, per-key check that runs independently after all pipelines.

## Motivating Incident

This monitor was built in response to the **Easter 2026 rates cache incident**
(see `docs/admin/incidents/2026-04-14_rates_cache_silent_drop.md`).  The
`CurveQuoteCache` silently blocked 20/39 rate curves for 2 weeks after a
transient Easter holiday blip.  The pipeline reported `success` every night.
Only a per-key staleness check would have caught this.

## Known Failure Modes

| Mode | Detection | Example |
|------|-----------|---------|
| **Silent cache lockout** | Per-key staleness >3 days for active curves | Easter 2026: `par` quotes cached as empty for 30 days |
| **Upstream feed drop** | Per-key staleness, confirmed by API probe returning 0 | Citi retiring IBOR tags |
| **Pipeline crash** | `audit.pipeline_runs` shows `failed` status | Code bug, network error |
| **Quota exhaustion** | Pipeline skipped in `imdr_daily.py`, `TagQuotaExceeded` in logs | >95K tags in 24h window |
| **EIA weekly lag** | All 66 EIA keys stale >10 days | EIA publication delay or tag format change |
