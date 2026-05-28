# Rates Hourly Pipeline

Last updated: 2026-05-13

Intraday rates ingest from Citi Velocity, writing to [`rates.fact_observation`](rates_schema.md) at `frequency_id=4` (HOURLY). Operational runbook: [rates_operations.md](rates_operations.md). Daily EOD pipeline: [rates_schema.md](rates_schema.md).

---

## At a glance

| Property | Value |
|---|---|
| Script | `scripts/rates/citi/rates_citi_live_hourly.py` |
| Orchestrator | [`scripts/imdr_hourly.py`](../../scripts/imdr_hourly.py) |
| Cadence | Hourly fires (up to 24/day on trading days) |
| Frequency tag | `HOURLY` (Citi API) → `frequency_id=4` (IMDR DB) |
| OAuth client | Dedicated `IMDR_CITI_HOURLY_CLIENT_ID` / `IMDR_CITI_HOURLY_CLIENT_SECRET` |
| Quota file | `data/cache/citi_tag_quota_hourly.json` (separate from daily `citi_tag_quota.json`) |
| Target table | `[rates].[fact_observation]` (same as daily; differentiated by `frequency_id`) |

---

## Universe

18 curves across two groups:

**RFR G10 + APAC** (12 curves): USD SOFR, EUR EUROSTR, GBP SONIA, JPY TONAR, CHF SARON, AUD AONIA, CAD CORRA, NZD NZIONA, NOK NOWA, SEK STINA, SGD SORA, THB THOR.

**APAC IBOR / NDIRS** (6 curves): HKD HIBOR, CNH CNH_HIBOR, CNY SHIBOR, CNY NDIRS, MYR KLIBOR, TWD TAIBOR. These are once-daily fixings (e.g. HIBOR at 11:15 HKT); hourly fires catch the mark on the same UTC day Citi publishes it rather than waiting for the daily pipeline.

Two quote types per curve:
- `par` — full tenor grid (44 tenors per curve)
- `fwd` — forward-starting rates (28 combos per curve)

**Budget**: 18 curves × (44+28) = 1,296 tags/call × 24 runs/day ≈ **31,104 tags/day** (~33% of the hourly client's 95K/24h rolling budget).

---

## Pull window strategy

Each run pulls `yesterday 00:00 UTC → now UTC` (a ~48h window). This ensures:
- The prior day's 22:00 and 23:00 UTC bars — missed by the last fire of day N — are captured on day N+1's first fire.
- With `--date` override: that single calendar day's `00:00 → 23:59 UTC` — used for explicit backfills.

The MERGE upsert on `(curve_id, ts, quote, tenor, frequency_id)` makes refetching earlier hours a no-op. Citi returns empty bodies for narrow sub-hour windows, so the wide pull window is required.

---

## Skip-on-closed-market gate

Commit `79de67e`. Before any API call, the script checks whether all four anchor markets are non-trading on today's UTC date:

```python
_ANCHOR_MARKETS = ["US", "EU", "UK", "JP"]
closed = [m for m in _ANCHOR_MARKETS if not is_trading_day(m, default_calendar(m), day)]
if len(closed) == len(_ANCHOR_MARKETS):
    log.info("all_anchor_markets_closed_skip", ...)
    return 0  # no-op
```

The gate uses today's UTC date (not the left edge of the pull window) to avoid falsely skipping a live trading day because the prior day was a weekend.

**Effect**: on Saturday UTC and Sunday UTC (before Asia open), the script exits cleanly with code 0 and no email. On Good Friday (US/UK/EU closed, JP open) the run still fires.

---

## Disabled empty-combo cache

Commit `d625e8d`. The hourly runner calls the pipeline with `use_cache=False` by default (and `--use-cache` flag exists but is intentionally not set in the scheduler).

**Why**: the daily pipeline's empty-combo cache has a 2-day stale window. At 24 fires/day, a cache populated by fire #1 would suppress real data for hours 2–48 before auto-retry. The hourly client also has a separate Citi-side quota bucket, so there is no budget pressure requiring the cache — every run can afford to fetch all 1,296 tags.

To force cache-enabled for debugging: `--use-cache` flag.

---

## Separate OAuth client

Environment variables:
```
IMDR_CITI_HOURLY_CLIENT_ID=...
IMDR_CITI_HOURLY_CLIENT_SECRET=...
```

Citi allocates a separate 100K/24h rolling quota per OAuth client. Using a dedicated key for hourly keeps the daily pipelines' shared 95K budget (tracked in `data/cache/citi_tag_quota.json`) unaffected.

If either key is missing, the script exits with code 2 and logs `hourly_creds_missing`.

---

## Expected output volume

| Scenario | Rows |
|---|---|
| Single fire (all curves, both quotes) | ~1,296 rows (18 × 72 avg tenors) |
| Full UTC day — steady state | ~31,104 rows (24 fires × ~1,296) |
| Full UTC day — partial (early Asia open) | Lower; grows as markets open |

APAC IBOR fixings may return 0 rows for pre-fix hours — expected. The ingest email classifies these as `pre_open` / `non_trading` / `otc` per market status at run time.

---

## Failure modes

### `TagQuotaExceeded`

Exits with code 1. Sends an email with `[QUOTA]` prefix in the subject. The quota failure path (commit `40dd597`) surfaces per-tag error context captured before the exception was raised, so ops can diagnose which curves exhausted the per-tag 10/24h rolling bucket.

### Coverage error escalation (lookback window)

Commit `5cf05ad`. When a curve returns 0 rows and the market is classified as `open` or `post_close`, the run emits a `coverage_gap` warning in the RunReport. This appears in the email as a warning-level banner, distinct from an info-level gap (which is `pre_open` / `non_trading`).

The lookback window strategy (pulling 48h of data) provides a second chance to pick up bars missed by the previous fire, reducing false-positive coverage gaps.

### Hourly IBOR silence

APAC IBOR fixings are published once daily. Citi returns `type=ERROR` or an empty series for all pre-fix hours. These appear in `_tag_errors` but are not escalated — the extractor drops them silently and the ingest email explains them under the "Citi API messages" section.

---

## Running manually

```bash
# Default: yesterday 00:00 UTC → now
python -m scripts.rates.citi.rates_citi_live_hourly

# Specific date override (backfill)
python -m scripts.rates.citi.rates_citi_live_hourly --date 2026-04-23

# Region subset (asia / europe / americas / all)
python -m scripts.rates.citi.rates_citi_live_hourly --region asia

# Force cache (not recommended)
python -m scripts.rates.citi.rates_citi_live_hourly --use-cache
```

---

## SQL spot-checks

```sql
-- Hourly row counts for today
SELECT CAST(ts AS DATE) AS obs_date, DATEPART(HOUR, ts) AS obs_hour,
       COUNT(*) AS rows
FROM [rates].[fact_observation]
WHERE CAST(ts AS DATE) >= CAST(GETUTCDATE() AS DATE)
  AND frequency_id = 4
GROUP BY CAST(ts AS DATE), DATEPART(HOUR, ts)
ORDER BY obs_date DESC, obs_hour DESC;

-- Coverage check: which curves have data today
SELECT c.ccy, c.curve, COUNT(*) AS rows
FROM [rates].[fact_observation] o
JOIN [rates].[dim_curve] c ON c.id = o.curve_id
WHERE CAST(o.ts AS DATE) = CAST(GETUTCDATE() AS DATE)
  AND o.frequency_id = 4
GROUP BY c.ccy, c.curve
ORDER BY c.ccy;
```
