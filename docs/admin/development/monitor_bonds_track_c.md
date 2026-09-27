# Track C — econ-monitor BBG store → `rates.fact_bond_yield`

**Status:** data LOADED + verified (2026-09-03) · one migration BLOCKED on DBA ·
extends [`govt_bond_population.md`](govt_bond_population.md) ·
schema in [`../rates/sov_bond_design.md`](../rates/sov_bond_design.md)

The third source for the CMT bond grain, alongside Track A (BBG_mirror CSVs, still unbuilt) and
Track B (Govy Monitor ISINs, built + loaded 2026-07-20). Source is the econ monitor's own
Bloomberg store, `z:\Business\Research\Dashboard\imdr_econ_monitor\data\bbg.sqlite3`.

**What landed:** 278,921 rows across 45 sovereign 10Y legs (nominal / breakeven /
inflation-linked real) in 17 markets, daily 1990-01-01 → 2026-08-31. `rates.fact_bond_yield`
went 0 → 278,921; it had been empty DDL since migration 067 (2026-06-02).

---

## 1. Why this source, and what it is not

The monitor store was surveyed end-to-end for what IMDR could take from it. Most of it is not
extractable, and saying why is the point of this section — the survey should not be repeated.

| Source layer | Rows | Verdict |
|---|---|---|
| `fact_market_daily`, `kind='INDEX'` legs | 391,468 | **EXTRACTED** — this doc |
| `fact_market_daily`, OIS/IRS legs | ~730/leg | **not available** — see §1.1 |
| `fact_observation` (econ) | 206,650 | **rejected** — see §1.2 |
| `bql_calendar` + `_revision` | 32,509 + ~32k | deferred — `cb_events` already holds 27k BBG rows; no `event_id` column to key reschedules on |
| `series_coverage` | 862 | not ingested; see the ledger-drift note in §1.1 |
| `fact_market_intraday` | 628 | ~1 day, pruned hard — nothing to take |
| `dashboard.sqlite3` | 4 charts / 1 placement | UI state, belongs with the app |
| `snapshots.sqlite3` (D23) | — | **does not exist**; never built |

### 1.1 Why the swap curves are not here

An earlier scan (2026-09-01) measured `fact_market_daily` at 4,053,247 rows and scoped a
3.65M-row OIS/IRS history backfill into `rates.fact_observation`. That was mis-scoped. The
monitor prunes its market layer to a rolling window and exempts only the deep sovereign legs
— stated in the original brief as *"fact_market_daily/_intraday (~1wk, except the deep
sovereign bond legs)"*. The 4.05M figure was a transient post-capture state; the steady state
is ~730 days per OIS/IRS leg with the INDEX legs at full depth. Retention working as designed,
not data loss.

Two consequences worth carrying forward:

- **The deep swap history is not obtainable from this source.** IMDR already runs its own BBG
  rates feed into `rates.fact_observation` (797k rows, 30 curves, live) — that remains the
  path for swaps.
- **`series_coverage` outlives the data it describes.** It still asserts `obs_rows = 13,392`,
  `first_obs = 1990-01-01`, verdict `complete` for legs now holding 730 rows. Because
  `complete` is a "don't ask" verdict in `coverage.asks_for`, the monitor will not re-request
  that history. Anything sizing work off that ledger will be ~5x wrong — this is exactly how
  the backfill above got mis-scoped.

### 1.2 Why the econ layer was rejected

`fact_observation` is a carry-forward sampled level series on a **pull-dependent grid**, not a
print store:

- `obs_date` is a BDH grid date anchored to the pull date (`ALL_CALENDAR_DAYS` +
  `PREVIOUS_VALUE`, `periodicityAdjustment=ACTUAL`), so a quarterly print repeats across every
  monthly grid point. 55 series ride a grid finer than their own frequency; 79 of 178 carry
  off-month-end dates from differing pull days, and two interleaved grids make one series
  alternate between values fortnightly under `ORDER BY obs_date`.
- `release_date` is a **per-run scalar** (`LAST_UPDATE` from the reference request, stamped
  identically on every row a run writes): 43 distinct values over 206,650 rows, 16 of which are
  times of day rather than dates. It is not a per-row print identifier and cannot recover the
  reference period.
- `vintage` records pull-to-pull churn, not statistical revision (1,083 non-zero rows).

There is therefore **no reference-period axis in the table and none recoverable from it**, so no
`INSERT…SELECT` into `econ.fact_indicator` is correct at any vintage. Independently, 168 of the
178 tickers already exist in `econ.dim_indicator` under vendor 4 with identical `imdr_code`; the
10 that do not are all `BBG.RATES.POLICY_RATE.*` on the finest (`D`) grid. Confirmed with the
module owner; the store's schema header claiming a straight `INSERT…SELECT` is being corrected
at source.

---

## 2. Decisions locked (2026-09-03)

1. **Resolution is by `source_ticker` through `rates.dim_bond_source`**, never by a
   `(ccy, yield_type, country_id)` tuple. Migration 125 deliberately authors curves that share
   an identity tuple and differ only by ticker family, so the tuple is ambiguous by
   construction; `uq_dim_bond_source_ticker` guarantees the ticker is not.
2. **One ticker family per curve identity** — the rule migration 064 already set with its three
   parallel GT placeholders. Where the monitor's ticker belongs to a different family than an
   existing active curve, a parallel curve is authored rather than mixing conventions:

   | leg | existing curve | resolution |
   |---|---|---|
   | JPY nominal `GJGB10` | `JPY_JGB_NOMINAL_GENERIC` (note: *"not on-the-run GJGB\*"*) | new `JPY_JGB_OTR_NOMINAL_OTR` |
   | AUD real `GTAUDII10Y` | `AUD_ACGBI_REAL_GENERIC` (CTAUDII\*) | new `AUD_ACGBI_REAL_GT_GENERIC` |
   | JPY real `GTJPYII10Y` | `JPY_JGBI_REAL_GENERIC` (`GTJPYII10YR  govt`) | new `JPY_JGBI_REAL_GT_GENERIC` — see §4 |
   | KRW nominal `GTKRW10Y` | `KRW_KTB_NOMINAL_OTR` (GVSK\*) | reuse `KRW_KTB_NOMINAL_GENERIC`, parked for GTKRW\* |

3. **France carries four legs, not two.** Bloomberg publishes a domestic-CPI breakeven/linker
   (`FRGGBE10` / `GFRGIN10`, OATi) and a euro-HICP pair (`FRGG10EB` / `GFRGEN10`, OAT-euro-i).
   Different reference indices → different curve identities.
4. **Weekends dropped, holidays kept.** The source is `ALL_CALENDAR_DAYS`-padded — verified flat
   across all seven weekday buckets on `BBG.RATES.GOVT_10Y.AU` (Sun 1913 … Sat 1913 of 13,398).
   Weekends go on calendar arithmetic, which works across the whole 1990- span.
   `calendar.market_holidays` covers only 9 of the 17 markets and only from 2007, so a holiday
   filter would be silently uneven across the panel; holidays are flagged, not dropped (§5).
5. **`quote_type = 'YIELD'` for nominal AND real legs** (a linker quotes a real yield — the same
   choice migration 066 made for the JPY/AUD linkers); `'BREAKEVEN'` for the `XXGGBE*` indices.
6. **`units = 'PCT'`** from the monitor's `dim_rate_instrument.unit`, never its `quote_units` —
   that column is Bloomberg-captured provenance and is wrong on ~30 rows of that table.
7. **Highest vintage per `(series_id, obs_date)` only**; `close IS NULL` rows skipped, not zeroed.
8. **Read from a scratch COPY, never the live file.** The monitor writes to it from its own
   scheduled refresh runs; the copy also yields a stable sha256 to record with the counts.

---

## 3. What landed

| Table | Before | After |
|---|---|---|
| `dbo.dim_bond_curve` | 26 (8 active) | **58 (52 active)** — 32 new, 12 reactivated |
| `rates.dim_bond_source` | 54 | **98** — 44 new |
| `rates.fact_bond_yield` | **0** | **278,921** |

The 12 reactivated curves are placeholders migration 064 parked `is_active=0` with notes naming
the exact securities the mirror lacked — *"No USGGBE\* in mirror"*, *"No UK folder in mirror"*,
*"No US TIPS (GTII\*/USGGT\*) in mirror"*. The monitor store carries precisely those.

Coverage: 17 markets x up to 3 legs. AU BR CA DE ES FR IL IT JP KR MX NZ PL SE TR UK US.
Deepest legs (9,566 rows, 1990-01-01→) — AU, CA, DE, FR, JP, NZ, UK, US nominal. Shallowest —
`FRGG10EB` euro-HICP breakeven, 1,118 rows from 2022-05-19.

Excluded by design: `BBG.RATES.bbg-manual-kofr-index` (`KRFRINDX Index`, 521 weekday rows) — the
KOFR compounded index is a rate, not a bond, and has no `dim_bond_source` row.

### Migrations

| # | File | Type | Status |
|---|---|---|---|
| 125 | `125_seed_dim_bond_curve_econ_monitor.sql` | DML (MERGE + guarded UPDATE) | APPLIED 2026-09-03 |
| 126 | `126_seed_dim_bond_source_econ_monitor.sql` | DML (MERGE) | APPLIED 2026-09-03 |
| 127 | `127_add_fact_bond_yield_is_carried.sql` | **DDL (ALTER TABLE)** | **BLOCKED — needs DBA** (§5) |

### Code

| Path | Purpose |
|---|---|
| `src/imdr/domains/rates/repository_bond.py` | `+ BondYieldRepository` (`resolve_sources`, `bulk_upsert`) + `_FACT_BOND_YIELD_SPEC` |
| `scripts/rates/bonds_monitor.py` | runner — `--no-load` / `--tickers`, copy-then-read, batched merge |
| `tests/unit/test_rates/test_bonds_monitor.py` | 7 tests on the transform contract (31 pass across the rates suite) |
| `playground/bonds/monitor_bonds_reader.py` | the shape-proof reader + `--resolve` curve classifier |

Idempotent: the MERGE keys on the deployed `uq_fact_bond_yield` (curve, vendor, obs_date, tenor,
+ the 4 axes). Re-running the UK leg merged 9,566 rows in place; the total held at 278,921.

---

## 4. Review

### Verified, not asserted

Counts were recomputed **from the monitor source** and compared to IMDR rather than read back
from the load's own report (a re-derivation, per the standing rule):

- All 45 tickers match source on **both** row count and span. The only delta is `KRFRINDX`
  (521 rows), excluded by design.
- 278,921 rows · 45 curves · 45 distinct tickers · 1990-01-01 → 2026-08-31 · **0 weekend rows**.
- Value range -3.757 … 33.33, nothing out of band. Negative reals on JGBi/Bund-linkers and 30%+
  on Turkey are both correct for what they are.
- Migration 126 was **pre-flighted** against the live axes constraint before applying (predicted
  44 inserts, 1 ticker skipped; both exact).

### Corrections made in flight — worth recording, all three were wrong first

1. **`uq_dim_bond_source_axes` caught a modelling error.** `GTJPYII10Y Govt` was first modelled
   as a second source on `JPY_JGBI_REAL_GENERIC`, reasoning it was the same GTJPYII family as the
   seeded `GTJPYII10YR  govt`. The constraint rejected it: a curve holds exactly one source per
   curve point. It got a parallel curve, the same treatment as AUD. Migration 126 had rolled back
   whole, so nothing partial was left behind. **The schema was right and the modelling was not.**
2. **The Israeli-Friday hypothesis was wrong.** The Mon–Fri filter was flagged as dropping genuine
   Israeli trading days (ILS trades Sun–Thu). The source refutes it: Israeli **Sundays carry 0%
   value change**, so nothing is lost. Bloomberg publishes these legs on a Mon–Fri grid regardless
   of local convention; it is Israeli *Fridays* that are ~87% carry-forward of Thursday.
3. **A 3.2M-row "deletion" was retention working as designed** — see §1.1. Reported as an
   anomaly before connecting it to the retention rule stated in the original brief.

### Risk register

| Risk | Assessment |
|---|---|
| Carried-forward values misread as prints | **Live.** 12.74% of rows. Mitigated by mig 127 once applied; see §5. |
| `series_coverage` drift mis-sizing future work | **Live.** Ledger asserts 4.05M verified rows against a table holding 831k. Do not size off it. |
| Curve identity proliferation (58 curves, many single-tenor) | Accepted. These are 10Y-only legs; `dim_bond_curve` rows are curve-shaped and only partially filled. A later multi-tenor source (Track A) extends them rather than duplicating. |
| Single-tenor curves read as full curves | Flagged in each curve's `notes` ("10Y point only"). |
| Source is pruned + actively written during reads | Mitigated: copy-then-read + sha256 recorded. A `pull:extract` lease is the stronger handshake if this is ever scheduled. |
| `close` on a *trading* day may itself be fill | **Open.** The dow histogram proves fill on weekends but cannot distinguish a genuine holiday print from a filled one. A `refresh_market.py` question (§6). |

### Blast radius

Additive only. No existing table altered by 125/126 (both seed rows); no existing pipeline
touched; the new modules are imported nowhere but their own runner and tests. `fact_bond_yield`
was empty, so nothing was overwritten. Migration 127 is an additive column with a default.

---

## 5. Staleness — measured, and the fix

35,538 of 278,921 weekday rows (**12.74%**) repeat the prior observation at that curve point:

| Cause | Rows | Rule-fixable? |
|---|---|---|
| Israeli Fridays (Sun–Thu week on a Mon–Fri vendor grid) | 2,100 | yes, deterministic |
| Falls on a known market holiday | 3,557 | partly — 9/17 markets, 2007+ |
| **Security genuinely did not print** | **29,881** | **no** |

Per-leg it ranges from 2–8% (USD legs — genuinely daily) to 42–49% (ILS legs, BRL NTN-B, JPY
JGBi, TRY — illiquid or convention-mismatched). The 8 markets with no holiday calendar at all
(BR ES FR IL IT MX PL TR) are 111,558 rows, 40% of the panel.

**84% is therefore not a filtering problem.** The carried value is the *correct mark* for that
day; it simply carries no new information. Deleting those rows would destroy the as-of property
— a Friday query on the Israeli 10Y would return nothing instead of Thursday's mark — to serve
one consumer at another's expense.

**Decision: flag, don't delete.** Migration 127 adds `is_carried BIT NOT NULL DEFAULT 0` and
backfills it. Mark-to-market reads ignore the flag; change/return computations filter on it and
stop seeing false zeros. Consistent with the project's quality convention.

> **`is_carried` semantics.** It means *"value equals the previous observation at this curve
> point"* — a **proxy** for "no new print", not proof of one. A genuinely unchanged yield is
> flagged too. The property it certifies is *no new information*, which is the one that matters
> for returns. It is not a claim that Bloomberg returned nothing; the vendor does not expose that
> distinction down this path.

### Migration 127 is BLOCKED

```
login            : RVCAPITALFUNDS\adoshi
role memberships : db_datareader, db_datawriter
ALTER  on rates.fact_bond_yield : 0        <- no db_ddladmin
INSERT on rates.fact_bond_yield : 1
is_carried column               : does not exist
```

`ALTER TABLE` fails with **error 1088** — *"Cannot find the object … because it does not exist or
you do not have permissions"* — which reads like a missing object and is not one. Same wall as
the Citi FX index migrations 120–122. **Needs a DBA.** Nothing partial was applied.

Three SQL forms were needed to get the backfill right; the file documents all three so nobody
re-derives them:

1. `UPDATE f … FROM tbl f JOIN <cte>` — fails, the CTE projects a window function
2. `UPDATE <cte>` — fails, a CTE containing `LAG` is not updatable in SQL Server
3. **works** — materialise to `#carried` with a clustered index on `id`, then `UPDATE … FROM`

The backfill *logic* is already proven: it is the identical window function used to produce the
35,538 / 12.74% decomposition above, run read-only. Only the `ALTER` + `UPDATE` plumbing is
unexecuted.

`is_carried` is deliberately **not** yet wired into the model, schema, `MergeSpec` or loader — if
it were, the next `bonds_monitor` run would reference a non-existent column and break the load.
Once 127 lands: add the model field, the schema field, the spec column, one comparison in
`extract()`, and tests; then one re-run stamps the flag.

---

## 6. Open items

| # | Item | Gate |
|---|---|---|
| 1 | Apply migration 127 | **DBA** — no `db_ddladmin` on this account |
| 2 | Wire `is_carried` through model/schema/spec/loader + tests, re-run | after (1) |
| 3 | `refresh_market.py` questions — is a trading-day `close` a genuine print or `PREVIOUS_VALUE` fill? Does `_write_daily` bump `vintage` on carried values? Is `mark` (4,281 of 830,957 rows) abandoned or mid-backfill? Is `series_coverage`'s `short_at_source` judged on the calendar grid? | module owner |
| 4 | Quality checks — `RangeCheck` on yields, `StaleCheck` keyed on `is_carried` | after (2) |
| 5 | Scheduler wiring | **explicit OK** — deferred, per the standing rule |
| 6 | Calendar layer (`bql_calendar` → `cb_events`) | needs the `event_id` decision first |

## Hard rules in play

- **Monitor store is READ-ONLY** — copy-then-read, never open the live file for write.
- No DDL / no data load / no prod wiring without explicit OK — (1), (5) gated.
- Tests + this doc kept current (split code vs data promotion).
