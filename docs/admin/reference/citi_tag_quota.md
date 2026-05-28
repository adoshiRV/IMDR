# Citi Velocity API — Tag Quota Management

## Overview

The Citi Velocity API enforces a **100,000 cumulative tag limit** on a **rolling 24-hour window**.

Key characteristics:
- The window is **not aligned to midnight** — it rolls from whenever tags were first consumed
- The quota is **invisible**: no header or endpoint exposes current usage. It is only revealed when exceeded, via an error response: `"Exceeded max tag count. Current usage: N, Available usage: M"`
- Separate from the per-minute rate limit (1 req/sec, `x-ratelimit-remaining` header) — that's request-level, not tag-level
- Each `fetch_historical` call sends up to 100 tags per request; the cumulative count across all requests within 24h is what matters

---

## Daily Tag Budget

All daily Citi pipelines run together in the 08:00 SGT batch orchestrated by [imdr_daily.py](../../scripts/imdr_daily.py). See [Daily Batch Timing](#daily-batch-timing) below for the rationale behind 08:00 SGT.

| Pipeline | Tags/Run | Schedule | Notes |
|----------|----------|----------|-------|
| `rates.citi_live` | ~15–20K | Daily 08:00 SGT | 33 curves x 6 quotes x ~15 tenors |
| `rates_vol.citi_live` | ~38K | Daily 08:00 SGT | 11 ccys x 6 data types x 17 expiries x 10 tenors |
| `fx_vol.citi_live` | ~1.5K | Daily 08:00 SGT | 17 pairs x 90 tags |
| `fx.citi_rate_live` | ~400 | Daily 08:00 SGT | 19 pairs x (1 spot + 20 fwd tags) |
| `commodities.spot_citi_live` | ~5 | Daily 08:00 SGT | Brent/WTI/XAU/XAG/XPT |
| `commodities.vol_citi_live` | ~1.2K | Daily 08:00 SGT | 5 products x vol surface |
| `equity.index_citi_live` | ~24 | Daily 08:00 SGT | 24 index tickers |
| `equity.vix_citi_live` | ~5 | Daily 08:00 SGT | VIX + variants |
| `rates.bench_citi_live` | ~10 | Daily 08:00 SGT | 10 CB policy rates |
| **Daily total (primary OAuth client)** | **~56–61K** | | Leaves ~40K headroom for manual/backfill runs |

### Hourly tag budget — dedicated OAuth client

The hourly intraday pipelines (`rates.citi_live_hourly`, `fx.citi_rate_live_hourly`) run under a **separate OAuth client** (`IMDR_CITI_HOURLY_CLIENT_ID`/`_SECRET`) with its own Citi-side 100K/24h rolling bucket. Tracker file: [data/cache/citi_tag_quota_hourly.json](../../data/cache/citi_tag_quota_hourly.json).

| Pipeline | Tags/Run | Runs/Day (trading) | Tags/Day | Notes |
|---|---|---|---|---|
| `rates.citi_live_hourly` | 864 | 24 | ~20,736 | 12 RFR curves × (44 par + 28 fwd) |
| `fx.citi_rate_live_hourly` | 399 | 24 | ~9,576 | 19 pairs × (1 spot + 2 × 10 fwd tenors) |
| **Hourly total** | | | **~30.3K/day (~32% of 95K)** | Leaves ~65K headroom on the hourly client |

Weekend/holiday gates (`all_anchor_markets_closed_skip` for rates, `is_fx_open` for FX) set the usage to **0 tags/day** on Sat + most of Sun + universal holidays (New Year's, etc.).

## Daily Batch Timing

**Run time: 08:00 SGT** via Windows Task Scheduler (moved from 07:00 SGT on 2026-04-23).

- **Summer (EDT, ~Mar–Nov)**: 08:00 SGT = 20:00 previous-day NY — 4h after NY close (16:00), 2h after Citi EOD publish (~18:00 NY). Comfortable margin.
- **Winter (EST, ~Nov–Mar)**: 08:00 SGT = 19:00 previous-day NY — 3h after close, ~1h after Citi publish. Chosen over 07:00 SGT to eliminate the edge case where Citi occasionally hadn't finished publishing at 18:00 NY, causing partial-row runs.
- **SG desk impact**: zero — traders are at their desks 08:30–09:00; data still lands before market-open consumption.
- **Retry cron** ([imdr_retry.py](../../scripts/imdr_retry.py)) runs 12:00 + 18:00 SGT to catch any residual tag-quota or transient failures.

Other consumers of the same quota pool:
- **Historical backfill scripts** (`*_historical.py`) — can easily consume 50K+ tags for multi-month ranges
- **Exploration scripts** (`scripts/explore/`) — tag browsing/listing counts against quota; avoid running on same day as daily ingest
- **`--no-cache` flag** on rates scripts bypasses the empty-combo cache, increasing tag consumption
- **Any script** using `CitiVelocityClient.fetch_historical()` directly

---

## How Tracking Works

### Tracker File

**Path**: `data/cache/citi_tag_quota.json`

Every API batch request records an entry with timestamp, pipeline name, and tag count:

```json
{
  "entries": [
    {"ts": "2026-03-26T23:01:00+00:00", "pipeline": "rates.citi_live", "tags": 15200},
    {"ts": "2026-03-26T23:05:00+00:00", "pipeline": "rates_vol.citi_live", "tags": 38056},
    {"ts": "2026-03-26T23:08:00+00:00", "pipeline": "fx_vol.citi_live", "tags": 1530}
  ]
}
```

- Entries older than 24 hours are **automatically pruned** on every read
- **File locking** (`filelock`) ensures correctness across concurrent subprocesses
- The tracker is created per-pipeline in each pipeline's `extract()` method and passed through to the shared `fetch_and_parse_batched()` function

### Pre-Flight Budget Check

Before starting extraction, each extractor:
1. Computes total tags needed (from universe config — curves x quotes x tenors)
2. Reads the tracker file to get current 24h usage
3. If `needed > remaining`, raises `TagQuotaBudgetExceeded` **immediately** — no partial API calls are wasted

The daily orchestrator (`imdr_daily.py`) also checks budget before launching each subprocess, skipping pipelines that can't fit.

### Architecture

```
imdr_daily.py (orchestrator)
  |
  |-- reads quota tracker → logs budget, skips if insufficient
  |
  |-- subprocess: rates_citi_live
  |     |-- RatesHistoricalPipeline.extract()
  |     |     |-- creates TagQuotaTracker
  |     |     |-- CitiVelocityRatesExtractor(quota_tracker=tracker)
  |     |     |     |-- check_budget() → pre-flight
  |     |     |     |-- for each curve/quote:
  |     |     |     |     |-- fetch_and_parse_batched(quota_tracker=tracker)
  |     |     |     |           |-- client.fetch_historical(batch)
  |     |     |     |           |-- tracker.record_usage(pipeline, len(batch))
  |     |     |     |-- on TagQuotaExceeded → re-raise (not swallowed)
  |     |-- except TagQuotaExceeded → report.error("tag_quota", ...) + flush JSONL
  |
  |-- subprocess: rates_vol_citi_live  (same pattern)
  |-- subprocess: fx_vol_citi_live     (same pattern)
```

---

## Error Behavior

| Scenario | What Happens | Email Report |
|----------|-------------|--------------|
| Pre-flight budget check fails | `TagQuotaBudgetExceeded` raised before any API call | ERROR badge, shows needed vs remaining |
| Quota exceeded mid-extraction | `TagQuotaExceeded` raised by API response parser | ERROR badge, shows current_usage and available from API |
| Single curve/pair API failure (non-quota) | Logged, accumulated in `extractor._errors`, loop continues | WARNING with count of failed curves |
| All curves succeed | Normal flow | OK badge with quota usage summary |

### Exception Hierarchy

```
RuntimeError
  └── TagQuotaExceeded           ← raised when API returns "Exceeded max tag count"
        └── TagQuotaBudgetExceeded  ← raised by pre-flight check before API call
```

Both are caught by the same `except TagQuotaExceeded` handler in live scripts.

---

## Automatic Retry (`scripts/imdr_retry.py`)

A separate cron job runs after the daily ingest to automatically retry pipelines that failed due to tag quota exhaustion.

### How It Works

1. Scans today's JSONL run logs (`data/run_logs/`) for `tag_quota` error events
2. Reads `data/cache/citi_tag_quota.json` — checks if enough quota has freed up (24h window rolled)
3. Checks DB first — if rows already exist for that date (manual re-run happened), skips
4. Re-runs the failed pipeline with `--date` set to the original target date
5. Sends email report on successful retry

### Schedule (Windows Task Scheduler)

| Task | Time | Notes |
|------|------|-------|
| `imdr_retry` | 12:00 SGT | First retry (~4h after daily run) |
| `imdr_retry` | 18:00 SGT | Second retry (~10h after daily run) |

### Usage

```bash
python -m scripts.imdr_retry                    # retry today's failures
python -m scripts.imdr_retry --date 2026-03-25  # retry specific date
```

No manual intervention needed in the common case: quota rolls over within a few hours, retry picks it up automatically.

---

## Inspecting Quota State

```bash
# View current quota file
cat data/cache/citi_tag_quota.json | python -m json.tool

# Check remaining budget programmatically
python -c "
from imdr.connectors.citi_quota import TagQuotaTracker
t = TagQuotaTracker()
print(f'Used: {t.current_usage():,} / Remaining: {t.remaining():,}')
for e in t.entries():
    print(f'  {e[\"ts\"]}  {e[\"pipeline\"]:30s}  {e[\"tags\"]:>6,} tags')
"
```

---

## Configuration

| Setting | Default | Env Var | Description |
|---------|---------|---------|-------------|
| `citi_tag_quota_limit` | `95,000` | `IMDR_CITI_TAG_QUOTA_LIMIT` | Conservative limit (5K below actual 100K) |
| `citi_tag_quota_file` | `""` (→ `data/cache/citi_tag_quota.json`) | `IMDR_CITI_TAG_QUOTA_FILE` | Override tracker file path |

The 95K default provides a safety margin for:
- Manual ad-hoc runs that bypass tracking
- Rounding errors in tag estimation
- Exploration scripts that use `CitiVelocityClient` directly without a tracker

---

## Troubleshooting

### "TagQuotaBudgetExceeded" in email

The pre-flight check determined there isn't enough quota remaining.

1. Check `data/cache/citi_tag_quota.json` to see which pipelines consumed the budget
2. Wait for the 24h window to roll — older entries will be pruned automatically
3. The `imdr_retry.py` cron job will auto-retry at 12pm and 6pm SGT

### "TagQuotaExceeded" in email

The Citi API itself rejected the request mid-extraction.

1. The `current_usage` and `available` fields in the error show the API's view
2. Same remediation as above — wait for window rollover + retry

### Quota file missing or corrupted

The tracker auto-creates the file on first write. If corrupted:
1. Delete `data/cache/citi_tag_quota.json`
2. It resets to empty (assumes 0 usage)
3. This is conservative only if you haven't run anything in the last 24h

### Manual/exploration runs bypass tracking

Scripts that use `CitiVelocityClient` directly (without passing through `fetch_and_parse_batched` with a tracker) will consume quota without recording it. Be aware of this when running exploration scripts on the same day as scheduled ingest.

### "0 rows written" but status OK

This was the original bug. If you see this pattern:
1. Check if extraction errors were logged (the `_errors` list in the email)
2. Check if a `TagQuotaExceeded` was raised but not captured
3. With the new error handling, this should no longer happen silently — `TagQuotaExceeded` is always re-raised and surfaces as an ERROR in the email
