# Bloomberg FX Rate Pipeline — operations

> ## ⚠️ READ-ONLY ACCESS TO Z:\BBG_mirror\FX ⚠️
>
> IMDR must NEVER move, rename, delete, or modify any file under
> `Z:\Business\Research\Dashboard\DataSources\BBG_mirror\` (live ingest)
> or `BBG\` / `BBG_ASIA\` (archive). The upstream R pipeline owns these
> files and overwrites them in place every batch. Moving a file breaks
> both the next IMDR poll and the R overwrite loop. Enforced by
> `archive_after_load=False` on the `bbg_fx_snapshot` feed + the lock-in
> test `tests/unit/test_vendors/test_bbg_fx_snapshot_no_move.py`.

Bloomberg sits alongside Citi Velocity as a second vendor on
[`fx.fact_fx_rate`](fx_rate_schema.md). This doc covers BBG-specific
operational details. Schema-level information lives in
[fx_rate_schema.md](fx_rate_schema.md); the universe + tenor grid is
covered in [fx_rate_pipeline.md](fx_rate_pipeline.md).

For upstream R-pipeline architecture (multi-PC fetcher writing to Z:\),
see [`docs/admin/vendors/bbg/`](../admin/vendors/bbg/).

---

## At a glance

| Property | Value |
|---|---|
| Vendor code | `bloomberg` (vendor_id=4) |
| Live cadence | Half-hourly fires 09:45–20:45 SGT (23 fires/day) — captures 6 BBG batches with ≥2 retry attempts each |
| Historical | DAILY back to **2007** for 10 majors, 2013–2024 for the rest; **190K SNAPSHOT rows** from BBG_ASIA archive (Dec 2021 → today) |
| Total rows in DB | **710K rows** across 25 pairs (RUB skipped — not in universe) |
| Universe | 26 pairs (22 G10/EM + 4 onshore variants — CNY/CNO/MYO/IDO) |
| Source files | live CSV at `Z:\...\BBG_mirror\FX\{CCY}\FX_{CCY}.csv` (overwritten each batch; cutover to BBG_mirror 2026-04-28) |
| Archive | `BBG_ASIA\{date}\` (1 ~16:30 SGT snap per day, 1,137 dates, fully ingested) + `FX\AUD\old\FX_{CCY}_{date}.csv` |
| Pipeline | `BloombergFXRatePipeline` ([src](../../src/imdr/domains/fx/pipeline_rate_bbg.py)) |
| Vendor feed | `bbg_fx_snapshot` ([spec](../../src/imdr/vendors/specs/bbg_fx_snapshot.py)) |
| Orchestrator | [`scripts/imdr_snapshots_bbg.py`](../../scripts/imdr_snapshots_bbg.py) (window-guarded 09:45–20:45 SGT, `--force` to bypass) |

---

## Data sources & semantics

The BBG R-pipeline writes one CSV per ccy with a 3-row header:

```
Row 0: Ticker,JPY curncy,JPY1W curncy,...
Row 1: Tenor,FX_JPY_SPOT,FX_JPY_1W,...
Row 2: Maturity,0,0.020833,...
Row 3+: dd/mm/yyyy,<spot>,<col2>,<col3>,...
```

The R script applies `outright = spot + points / divisor` per ccy
before writing, so the live CSV always contains **outright levels**.
IMDR's [`BloombergCSVFXRateExtractor`](../../src/imdr/domains/fx/extractors_rate_bbg.py)
applies the inverse to recover `fwd_points`:

| ccy class | divisor | inverse formula |
|---|---|---|
| JPY, THB | 100 | `points = (outright - spot) × 100` |
| G10 + MXN/PLN/ILS/IDO + metals | 10000 | `points = (outright - spot) × 10000` |
| NDFs (KRW/INR/IDR/PHP/TWD/MYR), HKD, CNY family | n/a | tickers already outright; `fwd_points = NULL` |

Frequency-vs-cadence mapping in the DB:

* **Citi rows** → `frequency_code='DAILY'`, `obs_ts = obs_date 00:00 UTC`
* **BBG live ingest** → `frequency_code='SNAPSHOT'`, `obs_ts = CSV mtime UTC`
* **BBG historical (xlsx + AUD/old/ archive)** → `frequency_code='DAILY'`, `obs_ts = obs_date 00:00 UTC`

---

## Universe — 26 pairs

19 pairs shared with Citi + 3 BBG-deliverable (MXN/PLN/ILS) + 4
BBG-only onshore (CNY/CNO/MYO/IDO). The 4 onshore variants are listed
in `fx_rate.bbg_only_pairs` in
[`src/imdr/universe/fx.yml`](../../src/imdr/universe/fx.yml) — the Citi
extractor filters them out so only BBG ingests them.

### Known upstream label issue
* **CNO** (offshore CNY variant) — the R pipeline writes `FX_CNY_*`
  tenor labels into the CNO file. Strict prefix matching is preserved
  (no alias overrides), so CNO sits at 0 rows in DB. To enable CNO
  loading, the R-side script must be updated to emit `FX_CNO_*`
  tenor labels.

---

## Phase A historical backfill (one-off, completed 2026-04-25)

The historical backfill is **complete** — 710K rows across 25 pairs
back to 2007 sit in `fx.fact_fx_rate`. The one-off converter +
loader scripts (`convert_bbg_fx_csvs.py`, `convert_bbg_fx_xlsx.py`,
`load_bbg_fx_historical.py`, `topup_bbg_fx_daily.py`) have been
deleted as part of the post-load cleanup. The data they produced
remains.

Sources that contributed:
- Live BBG_mirror CSVs (DAILY tail, ~171K rows)
- Pre-2019 xlsx exports (DAILY back to 2007, ~365K rows)
- BBG_ASIA snaps (SNAPSHOT 2021-12 → today, ~190K rows)
- AUD/old/ archive (SNAPSHOT, ~175 rows; archive no longer used)
- Onshore EM variants (CNY/CNO/MYO/IDO, ~15K rows)

**RUB** rows (~28K) were skipped — RUB is not in the 26-ccy universe.

---

## Phase B live ingest (planned)

21 fires per day via Windows Task Scheduler, each running:

```
python -m scripts.imdr_snapshots_bbg
```

Half-hourly on the :00 and :30 marks from **10:00 to 20:00 SGT**.
Every BBG batch (09:30, 11:00, 13:00, 16:00, 18:00, 19:00) gets at
least 2 capture attempts before the next batch overwrites the live CSV.

Idempotency: each row keyed on `(pair_id, vendor_id, frequency_id,
obs_ts, tenor)` with `obs_ts = CSV mtime`. A re-fire of the same batch
is a no-op MERGE — the redundant fires cost only an extra MERGE-with-no-
INSERT cycle, no data corruption risk.

End-of-day verification at **20:00 SGT**:
```
python -m scripts.bbg_fx_health_check
```
Reports `COUNT(DISTINCT obs_ts) per (pair, today's obs_date)`. Target
= 6. Cross-references `Z:\...\BBG\log\bbgCheck\` so genuine upstream
BBG outages are distinguished from IMDR-side ingest failures.

See [bbg_intraday_schedule.md](../admin/ops/bbg_intraday_schedule.md) for
Task Scheduler installation steps.

---

## Source-data caveats observed during backfill

Historical anomalies surfaced and verified as **real market events**,
not data corruption:

* **AUD** Oct 2008: 7 spot jumps >5% (GFC)
* **JPY** Oct 28 2008: -5.7% (carry trade unwind)
* **RUB** Dec 2014: 9 jumps including -18.5% Dec 16, +15.9% Dec 17
  (ruble crisis); 1W fwd_points up to 11,841
* **MXN** 2008-08: spot bottomed 9.86 on Aug 4 (peso pre-GFC peak)
* **MXN** 2016-11-09 +8.3% (Trump election)
* **INR** (TWD-folder data) 2007-2008: 128 days with spot 39-40 (real
  pre-crisis INR strength; universe range floor [40, 120] is too narrow
  for full historical)

Source-data corruption (already isolated):

* **HKD** 2025-03 / **ILS** 2025-03: 13 rows total with negative
  `mid_rate` (~-294). These are upstream BBG export errors. The
  loader's Pydantic `gt=0` check skips them with a per-row error log.
  No corruption propagates.

---

## Common operations

| Need | Command |
|---|---|
| Fire one snapshot manually (in-window) | `python -m scripts.run_vendor_feed bbg_fx_snapshot` |
| Fire all BBG snapshots for current 30-min window | `python -m scripts.imdr_snapshots_bbg` |
| End-of-day health report | `python -m scripts.bbg_fx_health_check` |
