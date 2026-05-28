# BBG Feed — IMDR Integration Plan

> **Status (2026-04-25)**: FX phases A + B + D **complete**. 520K rows across 25 pairs back to 2007 in `fx.fact_fx_rate`. See [docs/admin/fx/fx_rate_bbg.md](../../fx/fx_rate_bbg.md) for the live operational picture and [docs/admin/ops/bbg_intraday_schedule.md](../../ops/bbg_intraday_schedule.md) for the 6×/day Task Scheduler install. Sections below describe the original design choices made during planning.

## Goal

Ingest Bloomberg-sourced market data into IMDR without disrupting the existing R-based multi-PC pipeline on Z:\. The R pipeline stays authoritative for the existing dashboards; IMDR becomes a parallel consumer that stores the same data in normalized DB form plus parquet archives, with the usual run-logging, email reports, and health checks.

## Strategic choices

### Choice 1 — Source: CSV or `.rda`?

| Option | Pros | Cons |
|---|---|---|
| **CSVs** (`FX/{CCY}/FX_{CCY}.csv` etc.) | Matches downstream consumers; format already documented | Includes R-side transforms (FxSwap→FxFwd); 3-row header quirks; NA-backfilled data; one file per pair |
| **`.rda` blobs** (`FX/_Raw/fx.rda` etc.) | Raw ticker-level; ground truth before transforms; one read = all FX tickers | Overwritten each run (no history); needs `pyreadr` or R subprocess; have to re-implement ticker→series mapping in Python |

**Recommendation**: Start with **CSVs** for FX + Rates. Reasons:
- Zero new dependency on `pyreadr`.
- Format is stable (3-header-row) and well-documented now.
- Preserves compat with how the rest of the research team thinks about these files.
- We can add `.rda` ingest later for raw audit / replay.

### Choice 2 — Acquirer type

BBG doesn't fit any existing `imdr.vendors` acquirer cleanly:
- **Not email-linked** (no download link).
- **Not SFTP/HTTP** (files are on the local fileshare).
- **Not web-scrape** (no browser session).

Closest analog: **filesystem-poll acquirer** — a new acquirer type that treats files on Z: as the "vendor" and polls for freshness.

**Decision**: Add a new acquirer `FilesystemPollAcquirer` under `src/imdr/vendors/acquirers/filesystem.py`:
- Input: a list of file globs + a `min_mtime` spec ("files must be mtime >= today 19:00 SGT").
- Output: a `FetchResult` listing the matched files.
- Failure modes: `ListingNotFound` (no files), `FilesStale` (mtime too old).

This reuses the vendors framework (error handling, run-logging, email) without needing to invent a parallel abstraction.

### Choice 3 — Pipeline builder(s)

One pipeline per domain, each consuming a filtered `FetchResult`:

- `bbg_fx` — reads all `FX/{CCY}/FX_{CCY}.csv` → `fx.fact_fx_rate` (extend the existing table, add `vendor_id` for `dbo.dim_vendor` entry `BBG`)
- `bbg_rates` — reads `{IRS,OIS,BASIS,CCS}/{Ccy}/PAR/*.csv` → new `rates.fact_swap_rate` (or extend existing)
- `bbg_fixings` — reads `FIXINGS/_Out/*.csv` → new `rates.fact_ir_fixing`
- ...

### Choice 4 — Schedule

- Target the **19:00 SGT** batch from BBG (daily EOD). All files should have `mtime >= 19:00` by then.
- Run IMDR's BBG ingest at **20:00 SGT** daily — 1h buffer gives wiggle room for slow batches.
- This is **before** our `imdr_daily.py` at 08:00 SGT (next morning), so fresh BBG data is in IMDR ahead of downstream consumers.

## Proposed phases

### Phase 0 — Foundations (1 sprint)

1. Add `BBG` vendor entry to `dbo.dim_vendor`.
2. Add migration to create `rates.fact_swap_rate` (if not reusing existing).
3. Write `FilesystemPollAcquirer` in `src/imdr/vendors/acquirers/filesystem.py`.
4. Write `BBGCsvReader` helper in `src/imdr/connectors/bbg_csv.py` — handles the 3-row header, `dd/mm/yyyy` dates, tenor-column mapping.
5. Write `BBGUniverse` in `src/imdr/universe/bbg.py` — parses the two Excel configs + generates dim-table seeds.

### Phase 1 — FX outright levels (P0)

1. `bbg_fx` vendor feed + pipeline.
2. Ingest 28 FX pairs × tenors → `fx.fact_fx_rate` with `vendor_id = BBG`.
3. Reconcile against existing Citi FX rates — compare SPOT + 1M, expect ~same within bid-ask spread.
4. Quality checks: range check per ccy, percentage-change check vs prior day, null check.
5. Email notification with per-pair row counts and reconciliation summary.

### Phase 2 — Rates curves (P0)

1. `bbg_rates` vendor feed + pipeline.
2. Ingest IRS (19 series) + OIS (14 series) → `rates.fact_swap_rate` (new table with `curve_id` FK to `rates.dim_curve`).
3. Extend `rates.dim_curve` with BBG-specific series not currently in Citi: SHIBOR, KLIBOR, TAIBOR, KRW-91D_CD, MIBOR, etc.
4. QC: range, pct-change, null.

### Phase 3 — BASIS / CCS (P1)

1. Same as Phase 2 but for `BASIS` (12 series) + `CCS` (5–7 series).
2. New table `rates.fact_basis_quote` (basis expressed in bps).

### Phase 4 — Fixings (P1)

1. Ingest IR fixings from `FIXINGS/_Out/*.csv` → `rates.fact_ir_fixing`.
2. Handle retired series (EONIA, WIBOR) with `effective_to` dates.

### Phase 5 — Health monitoring

1. New module `src/imdr/connectors/bbg_health.py` reads:
   - Latest `log/bbgCheck/*.csv` → Bloomberg terminal status.
   - `log/BBGLog.log{today}` → per-file `Issue in-` reports.
2. Surface findings as `RunReport` warnings.
3. Email escalation if BBG terminal down for >4 hours.

### Phase 6 — Deferred items

- **Credit** (P2): CDS ingestion into new schema.
- **Bonds** (P3): single-bond-level ingestion — needs design.
- **Futures** (P3): separate design (our existing Citi catalog has some futures).
- **FX Vol** (P3): 94 pairs — dedupe against our existing Citi FX vol pipeline.
- **Listed** (P4): position-level — not market data.
- **FX_30mins / FX_BFIX** (P4): intraday — separate ingest.

## Design notes

### Vendor framework integration

BBG fits as an "acquirer + pipeline" in the existing `imdr.vendors` framework (see [../../../admin/vendors/index.md](../index.md)):

```python
# src/imdr/vendors/specs/bbg_fx.py
BBG_FX_SPEC = FilesystemPollSpec(
    name="bbg_fx",
    root=Path(r"Z:\Business\Research\Dashboard\DataSources\BBG\FX"),
    patterns=["{CCY}/FX_{CCY}.csv" for CCY in BBG_FX_UNIVERSE],
    min_mtime_sgt=time(19, 0),    # files must be post-19:00 SGT
    universe=BBG_FX_UNIVERSE,
)

BBG_FX_FEED = VendorFeed(
    spec=BBG_FX_SPEC,
    acquirer=FilesystemPollAcquirer(),
    pipeline_builder=lambda files, conn, cfg: BBGFxPipeline(files, conn, cfg),
    success_formatter=BBGFxSuccessFormatter(),
)
```

And registered in `src/imdr/vendors/registry.py`:

```python
from .specs.bbg_fx import BBG_FX_FEED
from .specs.bbg_rates import BBG_RATES_FEED

VENDOR_FEEDS: dict[str, VendorFeed] = {
    "barclays_skew": BARCLAYS_SKEW_FEED,
    "bbg_fx": BBG_FX_FEED,
    "bbg_rates": BBG_RATES_FEED,
}
```

### Invocation

```bash
python -m scripts.run_vendor_feed bbg_fx
python -m scripts.run_vendor_feed bbg_rates
```

Both registered in `scripts/imdr_daily.py` at 20:00 SGT with `estimated_tags: 0` (not Citi).

### DB normalization

Use `dbo.dim_vendor` (existing) to distinguish BBG from Citi/BidFX rows in `fx.fact_fx_rate`. For series not currently covered by Citi:
- Extend `rates.dim_curve` with BBG-only curves.
- Add `vendor_id` FK on all new fact tables.

### Testing plan

1. **Universe test**: parse both Excel configs, assert row counts match expected (30 FX, 52 rates).
2. **Parser test**: round-trip a known CSV (fixture) through `BBGCsvReader` and assert expected rows.
3. **Conversion test**: for each ccy, verify `outright = spot + points / divisor` on a frozen fixture.
4. **Reconciliation test** (post-ingest): select N random dates + pairs, compare BBG vs Citi vs original CSV — assert within tolerance.
5. **Health-check test**: mock `log/BBGLog.log{date}` with an `Issue in-` line, assert RunReport surfaces the warning.

### Rollout

- Week 1–2: Phase 0 foundations + FX universe seeding, dry-run ingest (no DB writes) to validate parser.
- Week 3: Phase 1 FX ingestion → DB + reconciliation report. Daily runs in parallel with Citi; no downstream consumers yet.
- Week 4: Phase 2 rates.
- Week 5: Phase 3 BASIS/CCS, Phase 4 fixings.
- Week 6: Phase 5 health monitoring + dashboards.

## Open questions

1. **Who authorizes adding a second source?** Citi has been primary for FX and rates; adding BBG means dual data for cross-check but also: which is authoritative for consumers?
2. **Are there licensing concerns?** Bloomberg data terms typically restrict redistribution; ingesting into IMDR for internal use is almost certainly fine but worth a formal check with the terminal admin.
3. **Do we snapshot `.rda` for replay?** If yes, we need a separate cron to `cp fx.rda fx.{date}.rda` — one more moving piece.
4. **Do we back-write cleaned data to CSV?** If IMDR applies quality checks and rejects some rows, do we:
   - Leave the Z:\ CSVs alone? (Easier. Research team consumes raw.)
   - Push a "cleaned" mirror back? (More useful but increases coupling.)
   Recommend: leave Z:\ alone; expose cleaned data via IMDR only.
5. **Do we care about historical backfill?** The `.rda` has 90–1000 days depending on domain; the CSVs have up to ~5 years. If we want more history, that's a one-off pull via `bdh(start=Sys.Date()-3650)` — requires a Bloomberg terminal session.

## What to do first

The first PR should be small and just unblock exploration:

1. Write `src/imdr/universe/bbg.py` that reads the two Excel configs and emits structured dicts.
2. Write `src/imdr/connectors/bbg_csv.py` with `BBGCsvReader` that parses the 3-header-row format into `(metadata, DataFrame)` tuples.
3. Write a `scripts/explore/bbg/` folder (mirroring `scripts/explore/citi/`) with scripts that:
   - List the full universe from both configs.
   - Read latest CSV for each series and report `last_date` + null counts.
   - Compare BBG FX spot vs Citi FX spot for the same pairs.

Once those three pieces land, design decisions become concrete.
