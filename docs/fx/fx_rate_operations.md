# FX Rate Operations Runbook

Operational guide for the `fx.citi_rate` pipeline. Target table: [fx.fact_fx_rate](fx_rate_schema.md). Architecture: [fx_rate_pipeline.md](fx_rate_pipeline.md).

---

## Schedule

- **Daily 08:00 SGT** — via Windows Task Scheduler, orchestrated by [scripts/imdr_daily.py](../../scripts/imdr_daily.py) alongside all other Citi daily pipelines. Registered with `estimated_tags=800`. Rationale for 08:00 vs 07:00 SGT: see [citi_tag_quota.md — Daily Batch Timing](../admin/citi_tag_quota.md#daily-batch-timing).
- **Retry cron** — `fx.citi_rate_live` is also registered in [scripts/imdr_retry.py](../../scripts/imdr_retry.py); runs at 12:00 and 18:00 SGT if the earlier run hit the tag quota or returned a partial row count.

---

## Running

### Live (daily EOD)

```bash
# Default: last business day (US), all 19 pairs
C:/Users/adoshi/.conda/envs/imdr/python.exe -m scripts.fx.citi.fx_rate_citi_live

# Override date
C:/Users/adoshi/.conda/envs/imdr/python.exe -m scripts.fx.citi.fx_rate_citi_live --date 2026-04-21

# Filter to specific pairs
C:/Users/adoshi/.conda/envs/imdr/python.exe -m scripts.fx.citi.fx_rate_citi_live --pairs EUR/USD,USD/HKD
```

Expected output: 209 rows upserted (19 pairs × 11 tenors).

### Historical backfill

Edit `MODE`, `START`, `END`, and `LOOKBACK_DAYS` in [scripts/fx/citi/fx_rate_citi_historical.py](../../scripts/fx/citi/fx_rate_citi_historical.py), then:

```bash
C:/Users/adoshi/.conda/envs/imdr/python.exe -m scripts.fx.citi.fx_rate_citi_historical
```

**Modes**:
- `range` — explicit `START` / `END` (YYYY-MM-DD)
- `catchup` — last `LOOKBACK_DAYS` business days
- `gaps` — read dates from `data/gaps/fx_rate_gaps.txt` (one YYYY-MM-DD per line)

Re-running is idempotent — MERGE upserts on `(pair_id, vendor_id, frequency_id, obs_date, tenor)`.

### Ad-hoc via generic runner

```bash
C:/Users/adoshi/.conda/envs/imdr/python.exe -m scripts.run_pipeline fx.citi_rate \
    --start 2026-04-21 --end 2026-04-21
```

### Cleaning

```bash
# Dry-run all rules + health + coverage + quality
C:/Users/adoshi/.conda/envs/imdr/python.exe -m scripts.fx.clean.clean_fx_fact_fx_rate --section all

# Apply hard-bound violations (drops rows where mid_rate is out of range)
C:/Users/adoshi/.conda/envs/imdr/python.exe -m scripts.fx.clean.clean_fx_fact_fx_rate --execute
```

---

## Failure modes

### `TagQuotaExceeded`

Logged with category `tag_quota` and exit code 1. The retry cron (12pm/6pm SGT) picks up automatically once the rolling 24h quota frees. No manual action needed unless it recurs — then check [citi_api_limits.md](../admin/citi_api_limits.md) and consider splitting the estimated_tags budget.

### `Vendor 'citi_velocity' missing from dbo.dim_vendor`

The pipeline fails loudly in `transform()` if the vendor row is absent. Apply [migration 018_create_dim_vendor.sql](../../migrations/018_create_dim_vendor.sql) (it seeds all four initial vendors) or INSERT the row manually.

### `Frequency 'DAILY' missing from dbo.dim_frequency`

Apply [migration 023_create_dim_frequency.sql](../../migrations/023_create_dim_frequency.sql) — seeds 10 enum values.

### `Pair not in universe — skipped`

If Citi returns a tag for a pair not listed in [fx.yml fx_rate.pairs](../../src/imdr/universe/fx.yml), the transform logs `transform_skipped_unmapped_pairs` and drops that row. Expected only when the universe is being actively edited. To add a new pair:

1. Add `[BASE, QUOTE]` to `fx_rate.pairs` in fx.yml (use Citi ordering).
2. Add `expected_ranges.{BASE}{QUOTE}: {min, max}` in the same block.
3. Ensure the currency is in `classifications` (existing 29 ccys + USD are already covered).
4. Next pipeline run auto-seeds `fx.dim_currency_pair` via `bulk_seed_from_universe()`.

### Holiday skip (expected)

For pairs whose home market is closed, Citi returns `type=ERROR` for that day — the extractor drops the row. The live script logs `holidays` via `holiday_hits_for_timestamp()` so the email explains missing rows.

### `fwd_points NULL for a non-SPOT tenor`

Citi's `FWD_POINT` tag occasionally returns `ERROR` even when `FWD_OUTRIGHT` succeeds (e.g., for thinly-quoted EM tenors). The pipeline accepts this — `fwd_points` is nullable. Downstream code must tolerate NULL.

### Mid rate drop + CHECK violation

If Citi returns a non-positive value (rare — indicates data corruption), Pydantic `FXRateCreate` validation rejects it before insert (`mid_rate > 0` constraint). The row is logged in `transform_skipped_nan_mid_rate` counters.

---

## Monitoring

- **Email** — every live run sends an HTML report via [FXRateIngestFormatter](../../src/imdr/notifications/formatters/fx_rate_ingest.py) (template: [fx_rate_ingest.html](../../src/imdr/notifications/templates/fx_rate_ingest.html)). Subject includes `OK`/`ERROR` status, row count, pair count.
- **Weekly dashboard** — section "FX Rate" in [imdr_health_dashboard.py](../../scripts/imdr_health_dashboard.py).
- **JSONL run logs** — `{run_log_dir}/fx/fact_fx_rate/fx_rate_citi_live_{YYYYMMDD}.jsonl` (retry cron reads this).

---

## SQL spot-checks

```sql
-- Latest load per pair
SELECT p.base_ccy + p.quote_ccy AS pair, MAX(r.obs_date) AS last_date, COUNT(*) AS rows
FROM fx.fact_fx_rate r
JOIN fx.dim_currency_pair p ON p.id = r.pair_id
GROUP BY p.base_ccy, p.quote_ccy
ORDER BY last_date DESC, pair;

-- One day's spot/forward curve for USDHKD
SELECT r.tenor, r.mid_rate, r.fwd_points
FROM fx.fact_fx_rate r
JOIN fx.dim_currency_pair p ON p.id = r.pair_id
WHERE p.base_ccy = 'USD' AND p.quote_ccy = 'HKD'
  AND r.obs_date = '2026-04-21'
ORDER BY CASE r.tenor
    WHEN 'SPOT' THEN 0 WHEN 'ON' THEN 1 WHEN '1W' THEN 2 WHEN '1M' THEN 3
    WHEN '3M' THEN 4 WHEN '6M' THEN 5 WHEN '9M' THEN 6 WHEN '1Y' THEN 7
    WHEN '2Y' THEN 8 WHEN '5Y' THEN 9 WHEN '10Y' THEN 10
END;

-- Check freshness
SELECT MAX(r.created_at) AS last_write,
       DATEDIFF(HOUR, MAX(r.created_at), SYSDATETIMEOFFSET()) AS hours_ago
FROM fx.fact_fx_rate r;
```

---

## Parquet archive

Location: `data/parquet/fx/fact_fx_rate/{BASE}_{QUOTE}/{YYYY-MM}.parquet`. Columns: `[obs_date, tenor, mid_rate, fwd_points]`. Natural key for dedup: `(obs_date, tenor)`. Written by [store_rate.py](../../src/imdr/domains/fx/store_rate.py) in `post_load()`.
