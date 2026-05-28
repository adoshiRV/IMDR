# KRW KOFR curve — ingest (overnight fixing + OIS swap curve)

- **Date filed**: 2026-05-28 (investigated 2026-05-29)
- **Priority**: 1 (Urgent)
- **Status**: not started
- **Triggered by**: Manual Excel drop at
  `Z:\Business\Personnel\Arjun\IMDR_MANUAL_UPLOADS\May 2026\kofr curve.xlsx`
  (401 daily rows, 2024-10-07 → 2026-05-28; two sheets `BBG` and
  `value pasted`, content-identical — load from `value pasted`). KRW KOFR
  is currently missing from `rates.dim_curve` entirely; we have CD/91D_CD_3M
  for KRW but no RFR.

## Problem

1. **No KRW KOFR in IMDR.** `rates.dim_curve` has 22 `rfr` rows
   (USD SOFR, EUR EUROSTR, GBP SONIA, JPY TONAR, …, THB THOR, ILS SHIR,
   INR MIBOR, NZD NZOCRS) but no entry for KRW. The desk needs a KOFR
   overnight series plus the KOFR OIS swap curve (1W → 5Y).

2. **The Bloomberg-published "KOFR Rate" column in the source file is
   wrong on multi-day spans.** The Excel computes
   `(idx_t / idx_{t-1} - 1) * 365 * 100` with **no day-count adjustment**,
   so any row where `t-1` is not the immediately preceding calendar day
   (Mon-after-weekend, post-holiday) prints a fake 7-10% rate. The KOFR
   Index itself (`KRFRINDX Index`, col 1) is the live-updating cumulative
   index and IS trustworthy — we recompute the daily O/N from the index
   ratio with proper ACT/365 calendar-day spacing.

   Verification on file:
   | Date | Index | Days since prev | Sheet "KOFR Rate" | Correct (idx ratio × 365/days) |
   |---|---:|---:|---:|---:|
   | 2026-05-28 | 1188.91614 | 1 | 2.5526 | 2.5526 ✓ |
   | 2026-05-27 | 1188.833   | 1 | 2.5485 | 2.5485 ✓ |
   | 2026-05-26 | 1188.75    | 4 | **10.10** | **2.529** (bridge across Fri/Sat/Sun) |
   | 2026-05-18 | 1188.094   | 3 | **7.56**  | **2.52**  (Mon after weekend) |
   | 2026-05-04 | 1186.940   | 4 | **10.18** | **2.55**  (long-weekend bridge) |

## Source file structure

`kofr curve.xlsx` Sheet1 has 30 columns laid out as (date, value) pairs:

| Col | Bloomberg ticker | Label | Tenor |
|---|---|---|---|
| 0-2 | `KRFRINDX Index` | KOFR Index + naive "KOFR Rate" | O/N (recompute) |
| 3-4 | `KWKON1Z Curncy` | KRW KOFR OIS | 1W |
| 5-6 | `KWKON2Z Curncy` | KRW KOFR OIS | 2W |
| 7-8 | `KWKON3Z Curncy` | KRW KOFR OIS | 3W |
| 9-10 | `KWKONA Curncy` | KRW KOFR OIS | 1M |
| 11-12 | `KWKONB Curncy` | KRW KOFR OIS | 2M |
| 13-14 | `KWKONC Curncy` | KRW KOFR OIS | 3M |
| 15-16 | `KWKONF Curncy` | KRW KOFR OIS | 6M |
| 17-18 | `KWKONI Curncy` | KRW KOFR OIS | 9M |
| 19-20 | `KWKON1 Curncy` | KRW KOFR OIS | 1Y |
| 21-22 | `KWKON1F Curncy` | KRW KOFR OIS | 18M |
| 23-24 | `KWKON2 Curncy` | KRW KOFR OIS | 2Y |
| 25-26 | `KWKON3 Curncy` | KRW KOFR OIS | 3Y |
| 27-28 | `KWKON4 Curncy` | KRW KOFR OIS | 4Y |
| 29-30 | `KWKON5 Curncy` | KRW KOFR OIS | 5Y |

Each tenor pair has its own date column — but **do not** filter on it.
The per-tenor date is Bloomberg's "last-actual-print date"; the value
column is the mid-market quote and updates regularly even on days where
the print date is days old. KRW KOFR swaps are illiquid enough that
filtering on `bbg_date == obs_date` would drop 75–100% of the data
(1M tenor: 0/401 rows match exactly; 5Y has 252 unique values across
399 days with mean BBG-date lag of 2 days — the *values* are fresh).

Right rule: **insert one fact row per `(obs_date, tenor)` where the
value is non-null**, treating `obs_date` as the observation. This matches
how the existing daily snapshots for INR MIBOR / THB THOR work in
`fact_observation` — Bloomberg-sourced, no quote-freshness filter,
`frequency_id=DAILY`, `ts` at UTC midnight of the observation date.

Coverage per tenor (non-null rows / 401 obs dates), confirmed against the
file:

| Tenor | Rows | Notes |
|---|---:|---|
| 1D  | 400 | recomputed from KOFR index (one less than obs because the earliest row has no predecessor) |
| 1W  | 340 | |
| 2W  | 141 | sparse — ~35% coverage, illiquid |
| 3W  | 139 | sparse |
| 1M  | 330 | |
| 2M  | 336 | |
| 3M  | 334 | |
| 6M  | 392 | |
| 9M  | 398 | |
| 1Y  | 398 | |
| 18M | 293 | ~73% coverage |
| 2Y  | 400 | |
| 3Y  | 400 | |
| 4Y  | 399 | |
| 5Y  | 399 | |

Total: **~5,300 inserts** (sum of column above).

## Schema target — mirror THOR/SHIR/MIBOR

The clean analog already in the DB is **THOR / SHIR / MIBOR / NZOCRS**
(rows 53-57 in `rates.dim_curve`): `curve_type='rfr'`, `instrument='ois'`,
`vendor_id=4` (BBG), `citi_prefix='BBG:{CCY}-{NAME}-ON'`. Data lives in
`rates.fact_observation` with tenor `1D` for the O/N and `1W` … `5Y` for
the swap curve, `quote='par'`, `frequency_id=DAILY`.

### `rates.dim_curve` insert

| ccy | curve | curve_type | curve_status | instrument | citi_prefix       | country_id |
|-----|-------|------------|--------------|------------|--------------------|-----------:|
| KRW | KOFR  | rfr        | active       | ois        | BBG:KRW-KOFR-ON    | 27 (KR) |

`notes`: "Korean overnight unsecured RFR + OIS swap curve. O/N recomputed
from KRFRINDX Index using ACT/365 calendar-day day count; sheet 'KOFR
Rate' col is bridge-day broken and not used."

### `rates.fact_observation` inserts

Per (date, tenor):
- `curve_id` → new KOFR row
- `ts` → `obs_date` at UTC midnight
- `quote` → `par`
- `tenor` → `1D` for O/N, `1W` / `2W` / `3W` / `1M` / `2M` / `3M` / `6M` /
  `9M` / `1Y` / `18M` / `2Y` / `3Y` / `4Y` / `5Y` for swaps
- `value` → recomputed for `1D`, raw quote for swap tenors
- `vendor_id` → 4 (BBG)
- `frequency_id` → DAILY (id from `dbo.dim_frequency`)

Estimated row count: 400 O/N + 4,899 swap (sum of non-null per-tenor
counts) = **~5,300 inserts**. Idempotent upsert on
`(curve_id, ts, quote, tenor, vendor_id, frequency_id)`.

`frequency_id=5` (DAILY) from `dbo.dim_frequency`. `vendor_id=4` (BBG)
from `dbo.dim_vendor`.

## O/N recompute formula

For each consecutive pair of index observations `(t-1, t)` in the file
(sorted ascending):

```
days_elapsed   = (date_t - date_{t-1}).days        # calendar days
ratio          = idx_t / idx_{t-1}
overnight_rate = (ratio - 1) * 365 / days_elapsed * 100   # percent
```

The earliest row (2024-10-07, no predecessor) gets no O/N value. All
subsequent rows produce one O/N print. Weekend/holiday bridges become
**single** average O/N rates spanning those days — that's the correct
interpretation of a compounded index over a multi-day bridge.

**File quantification of the col-2 bug (confirmed 2026-05-29 against
the file)**:

- 307 / 401 rows have `days_gap == 1` — col 2 matches recompute to
  floating point.
- 93 / 401 rows have `days_gap > 1` — col 2 diverges, **all 93 are
  wrong**.
- Worst case: 2025-01-31, 7-day gap (Lunar New Year), col 2 prints
  **22.26%** vs correct **3.18%**.
- Distribution of days_gap: 1: 307, 2: 8, 3: 75, 4: 6, 5: 1, 6: 1, 7: 1,
  8: 1.

## Script location

One-off backfill — follows the `scripts/migrations/{action}_{schema}_{table}` pattern:

- `scripts/migrations/load_rates_kofr_curve.py` — reads the Excel,
  recomputes the O/N series, inserts `dim_curve` row (if missing) and
  upserts `fact_observation` rows.

No new SQL migration needed (only new dim row + fact rows; no DDL).

## Why Priority 1

Manual desk-requested upload, file is already on disk and dated today.
Blocks any KRW OIS / KOFR-anchored analytics until landed. Not blocked on
external review or DB DDL — pure CRUD with an additive `dim_curve` row.

## Open questions

- ~~**Country `id` for Korea**~~ — resolved: `dbo.dim_country.id = 27`,
  iso_alpha3 KOR.
- **Should we set up an automated KOFR feed** going forward, or treat
  this as recurring manual drops (drop a fresh `kofr curve.xlsx` each
  month and re-run the loader, which is idempotent)? Open follow-up.
- **`fact_bench_rates` vs `fact_observation` for the O/N**: KOFR is an
  RFR (market-determined), not a central-bank policy rate, so it belongs
  in `fact_observation` next to THOR/MIBOR. Confirmed by the existing
  precedent.
- **2W / 3W / 18M sparsity**: these tenors are quoted only ~35-73% of
  observation dates. Probably fine — load only the days that have
  values — but flag in the loader output so we can see the coverage gap
  per tenor at load time.

## Done when

- [ ] `rates.dim_curve` row for KRW / KOFR exists with correct `country_id`
- [ ] `scripts/migrations/load_rates_kofr_curve.py` exists, reads the
      Excel, idempotent on re-run
- [ ] `rates.fact_observation` has ~400 O/N rows (tenor `1D`) recomputed
      from `KRFRINDX Index`
- [ ] `rates.fact_observation` has the 14 KOFR OIS swap tenors backfilled
      for every `(obs_date, tenor)` where the value is non-null
      (~4,900 rows; do **not** filter on Bloomberg's last-print date)
- [ ] Spot-check on three bridge dates (e.g. 2026-05-26, 2026-05-18,
      2026-05-04): DB `1D` value ≠ the sheet's broken col-2 number, and
      matches the recompute table above
- [ ] Doc on the recompute convention added under
      `docs/admin/rates/` or `docs/rates/`
