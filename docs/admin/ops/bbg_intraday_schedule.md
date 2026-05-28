# BBG FX intraday — schedule

> ## ⚠️ HARD RULE — IMDR NEVER MOVES OR MODIFIES BBG FILES ⚠️
>
> The poll is **read-only**: `glob` + `stat` + `pd.read_csv`. The R
> pipeline owns the live CSVs and overwrites them in place; if IMDR
> moves a file the next 30-min fire has nothing to read. Enforced by
> `archive_after_load=False` on the `bbg_fx_snapshot` feed and by
> `tests/unit/test_vendors/test_bbg_fx_snapshot_no_move.py`. See
> [`vendors/bbg/index.md`](vendors/bbg/index.md) for the full rule.

The BBG R-pipeline runs 6 batches per day on the multi-PC fetcher (see
[`vendors/bbg/scheduling_and_health.md`](vendors/bbg/scheduling_and_health.md)).
IMDR ingests them by polling the live CSVs every 30 minutes during the
active window.

For domain context (vendor framework, frequency mapping, source CSV
semantics) see [`docs/admin/fx/fx_rate_bbg.md`](../fx/fx_rate_bbg.md).

---

## Schedule

All times **SGT** (Asia/Singapore). Half-hourly fires from **09:45 to
20:45 SGT** plus one end-of-day health check at 20:00.

| # | Time SGT | On disk now | BBG batch caught | Attempt # |
|---|---|---|---|---|
| 1 | 09:45 | 09:30 batch | **09:30** | 1 |
| 2 | 10:15 | 09:30 | 09:30 (no-op) | 2 |
| 3 | 10:45 | 09:30 | 09:30 (no-op) | 3 |
| 4 | 11:15 | 11:00 batch | **11:00** | 1 |
| 5 | 11:45 | 11:00 | 11:00 (no-op) | 2 |
| 6 | 12:15 | 11:00 | 11:00 (no-op) | 3 |
| 7 | 12:45 | 11:00 | 11:00 (no-op) | 4 |
| 8 | 13:15 | 13:00 batch | **13:00** | 1 |
| 9 | 13:45 | 13:00 | 13:00 (no-op) | 2 |
| 10 | 14:15 | 13:00 | 13:00 (no-op) | 3 |
| 11 | 14:45 | 13:00 | 13:00 (no-op) | 4 |
| 12 | 15:15 | 13:00 | 13:00 (no-op) | 5 |
| 13 | 15:45 | 13:00 | 13:00 (no-op) | 6 |
| 14 | 16:15 | 16:00 batch | **16:00** | 1 |
| 15 | 16:45 | 16:00 | 16:00 (no-op) | 2 |
| 16 | 17:15 | 16:00 | 16:00 (no-op) | 3 |
| 17 | 17:45 | 16:00 | 16:00 (no-op) | 4 |
| 18 | 18:15 | 18:00 batch | **18:00** | 1 |
| 19 | 18:45 | 18:00 | 18:00 (no-op) | 2 |
| 20 | 19:15 | 19:00 batch | **19:00** | 1 |
| 21 | 19:45 | 19:00 | 19:00 (no-op) | 2 |
| 22 | 20:15 | 19:00 | 19:00 (no-op) | 3 |
| 23 | 20:45 | 19:00 | 19:00 (no-op) | 4 |
| EOD | 20:00 | — | full health report | — |

**Per-batch coverage** (no batch weaker than 2 capture attempts):

| BBG batch | Fires | Tolerates |
|---|---|---|
| 09:30 | 3 | 2 consecutive failures |
| 11:00 | 4 | 3 consecutive failures |
| 13:00 | 6 | 5 consecutive failures |
| 16:00 | 4 | 3 consecutive failures |
| 18:00 | 2 | 1 failure |
| 19:00 | 4 | 3 consecutive failures |

The 19:00 batch CSV stays on disk until ~23:14 SGT (external archive
job moves it to `FX/AUD/old/`), so 19:45 / 20:15 / 20:45 fires keep
finding it.

**Total**: 23 ingest fires + 1 EOD health check = 24 entries.

**Email volume**: 23 ingest fires/day. Roughly 6 land new data; 17 are
idempotent re-runs that emit "0 rows" success emails. Wire email
suppression in `imdr_snapshots_bbg.py` (skip email when
`rows_loaded == 0`) to bring this back to ~6/day.

---

## Time-window guard (built into the orchestrator)

`scripts/imdr_snapshots_bbg.py` enforces the active window itself —
**outside 09:45–20:45 SGT it exits silently** (no fire, no email,
no error). This means a Task Scheduler entry registered for an
out-of-window time is harmless: the script simply no-ops.

Two consequences:

1. You can register Task Scheduler entries on a coarser cadence (every
   30 min round-the-clock) without flooding the inbox at night.
2. Manual runs outside the window also no-op silently — useful for
   accidentally re-firing a debug shell.

To override (e.g. ad-hoc backfill of yesterday's missed snap), pass
`--force` so the window check is bypassed.

---

## Why `imdr_snapshots_bbg.py` and not `run_vendor_feed bbg_fx_snapshot` directly?

The orchestrator wraps the vendor feed call so we can later add
`bbg_rates_snapshot` / `bbg_vol_snapshot` without touching any Task
Scheduler entries. Each fire today still ultimately calls one vendor
feed; tomorrow it could call several in sequence.

---

## What the health check tells you

The 20:00 SGT email lists, **per pair**, exactly which of the 6
batches landed and which didn't (e.g. `Missing: 11:00 SGT, 16:00 SGT`).
Bucketing by UTC hour of `obs_ts` gives an unambiguous batch-id mapping
(each batch has a unique UTC hour). Pairs in `KNOWN_BROKEN_PAIRS`
(currently `USD/CNO` — upstream R label issue) are flagged separately
so they don't false-positive.

Subject line at a glance:

* `[OK] BBG FX Health | 2026-04-25 | 22/22 full`
* `[!] BBG FX Health | 2026-04-25 | 18/22 full, 4 partial, 2 BBG offline`

---

## Idempotency + recovery

Each row is keyed on `(pair_id, vendor_id, frequency_id, obs_ts,
tenor)` with `obs_ts = CSV mtime`. A re-fire of the same batch is a
MERGE no-op — safe to re-trigger any task entry manually.

If an entire batch is lost (all attempts failed AND the next BBG batch
overwrote the CSV), partial recovery is possible from
`Z:\...\BBG_ASIA\{date}\` (one ~16:30 SGT snap per day) — but a single
recovered snap is not the same batch, just an alternative time-point
for that day.

---

## Verification

After one full day of operation:

```sql
SELECT
    p.base_ccy + '/' + p.quote_ccy AS pair,
    f.obs_date,
    COUNT(DISTINCT f.obs_ts) AS snaps_today
FROM fx.fact_fx_rate f
JOIN fx.dim_currency_pair p ON p.id = f.pair_id
JOIN dbo.dim_vendor v ON v.id = f.vendor_id
JOIN dbo.dim_frequency fq ON fq.id = f.frequency_id
WHERE v.vendor_code = 'bloomberg'
  AND fq.frequency_code = 'SNAPSHOT'
  AND f.obs_date = CAST(GETDATE() AS DATE)
GROUP BY p.base_ccy, p.quote_ccy, f.obs_date
ORDER BY pair;
```

Target: `snaps_today = 6` for every active pair (USD/CNO excluded).
