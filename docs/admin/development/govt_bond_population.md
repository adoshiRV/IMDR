# Govt-bond population plan (Quick Monitor · India + Korea first)

**Status:** design/plan · **Date:** 2026-07-17 · Feeds [`quick_monitor/`](quick_monitor/) ·
extends the schema in [`../rates/sov_bond_design.md`](../rates/sov_bond_design.md).

## Decisions (user, 2026-07-17)
1. **Both sources** — BBG_mirror (deep CMT history) **and** Govy Monitor (India + ASW + auctions + ISIN).
2. **Ingest into IMDR** — IMDR owns the data; the Quick Monitor reads IMDR, not the live app. Survives the desktop app being down.
3. **ISIN-level sibling fact** — Govy's per-bond grain lands in a new `rates.fact_bond_instrument_obs` (sketched in `sov_bond_design.md` §"What this schema does NOT try to handle"); CMT tiles derived on read.

## Track C (added 2026-09-03) - econ-monitor BBG store -> `rates.fact_bond_yield`

A third source landed ahead of Track A: **278,921 rows, 45 sovereign 10Y legs (nominal /
breakeven / real) across 17 markets, daily back to 1990**, from the econ monitor's own Bloomberg
store. It fills the 12 `is_active=0` placeholder curves migration 064 parked for the securities
the mirror lacks (USGGBE*, UKGGBE*, DEGGBE*, GTII*, ...), plus 32 new curve identities.
`fact_bond_yield` is no longer empty. Full design, verification and review:
**[`monitor_bonds_track_c.md`](monitor_bonds_track_c.md)**.

Track C does **not** supersede Track A: it carries the **10Y point only**, so the curves it
activates are single-tenor. Track A's mirror CSVs extend them to full CMT curves rather than
duplicating them.

## Two tracks

### Track A — BBG_mirror → `rates.fact_bond_yield` (CMT grain, existing schema)
- Schema already built + seeded (migs 063–067; 8 active curves, 54 source rows). Fact table empty.
- **Build** a mirror bonds reader following the existing pattern (`src/imdr/domains/rates/pipeline_bbg*.py` + `src/imdr/bbg/csv_parser.py`) — **not** the stale `vendors/feeds/` path the design doc named (no such dir).
- Reads `Z:\...\BBG_mirror\BONDS\{CCY}\{GOVT|LINKER}\*.csv` (READ-ONLY), maps to `dim_bond_source`, upserts `fact_bond_yield`. Runs backfill `068` (~210K rows, 2007+).
- **Covers:** US, JP, CN(CDB), ID, **KR (GVSK CMT, deep history)**, MY, AU-linker. **No India.**

### Track B — Govy Monitor SQLite → `rates.fact_bond_instrument_obs` (ISIN grain, NEW)
- Source: `Z:\Business\Research\Dashboard\Govy Monitor\BBG.Yield.DB` (SQLite, **READ-ONLY — NO EDITS**).
- **Covers:** all 12 curves incl **India (IGB) + Korea (KTB)**; daily since 2025-12-19; ISIN-level yields + 1d/1w/1m/3m Δ + ASW + auctions.
- Ingest reads a **copy** of the DB (never opens the live file for write; copy to scratch, checkpoint WAL, read). Loads three shapes:
  - `yield_snapshots` → `rates.fact_bond_instrument_obs` (per-bond yields + changes)
  - `asw_snapshots` → same fact with `quote_type='ASW'` (or a lane) — the India bond-swap-spread panel
  - `auction_calendar` → `rates.fact_bond_auction` (issuance/supply → D6 fiscal)

## Proposed new schema (Track B) — for review, DDL not yet applied

```sql
-- ISIN identity (cross-domain, dbo — credit will reuse)
CREATE TABLE dbo.dim_bond_instrument (
    id            INT IDENTITY PRIMARY KEY,
    isin          VARCHAR(20)  NOT NULL UNIQUE,
    bbg_ticker    VARCHAR(30)  NULL,
    country_id    TINYINT      NOT NULL,   -- FK dim_country
    ccy           VARCHAR(3)   NOT NULL,
    issuer_code   VARCHAR(30)  NOT NULL,   -- IGB | KTB | ...
    description   VARCHAR(200) NULL,
    coupon        FLOAT        NULL,
    maturity_date DATE         NULL,
    is_active     BIT NOT NULL DEFAULT 1,
    created_at, updated_at ...
);

-- Per-bond daily observations (ISIN grain)
CREATE TABLE rates.fact_bond_instrument_obs (
    id            BIGINT IDENTITY PRIMARY KEY NONCLUSTERED,
    instrument_id INT           NOT NULL,   -- FK dbo.dim_bond_instrument
    vendor_id     INT           NOT NULL,   -- BBG (id=4); pricing_source in its own col
    frequency_id  TINYINT       NOT NULL,
    obs_date      DATE          NOT NULL,
    obs_ts        DATETIMEOFFSET NOT NULL,
    quote_type    VARCHAR(20)   NOT NULL,   -- YIELD | ASW | PRICE
    tenor_years   FLOAT         NOT NULL,   -- residual maturity at obs (for bucketing)
    value         FLOAT         NOT NULL,
    chg_1d        FLOAT NULL, chg_1w FLOAT NULL, chg_1m FLOAT NULL, chg_3m FLOAT NULL,
    pricing_source VARCHAR(12)  NOT NULL,   -- BVAL | NDSI | DAB | ...
    units         VARCHAR(10)   NOT NULL,   -- PCT | BP
    source_app    VARCHAR(20)   NOT NULL DEFAULT 'GOVY_MONITOR',
    created_at, updated_at ...,
    CONSTRAINT uq_fbio UNIQUE (instrument_id, vendor_id, obs_date, quote_type)
);
CREATE CLUSTERED INDEX ci_fbio ON rates.fact_bond_instrument_obs (obs_date, instrument_id) WITH (DATA_COMPRESSION=PAGE);

-- Auctions / issuance (fiscal supply → D6)
CREATE TABLE rates.fact_bond_auction (
    id INT IDENTITY PRIMARY KEY,
    country_id TINYINT NOT NULL, auction_date DATE NOT NULL,
    security_type VARCHAR(30) NULL, term VARCHAR(10) NULL, isin VARCHAR(20) NULL,
    coupon FLOAT NULL, maturity_date DATE NULL, reopening BIT NULL,
    offered_amount FLOAT NULL, currency VARCHAR(3) NULL, source VARCHAR(30) NULL,
    fetched_at DATETIMEOFFSET NOT NULL, created_at, updated_at,
    CONSTRAINT uq_fba UNIQUE (country_id, auction_date, security_type, term, isin)
);
```

## Deriving the monitor's CMT tiles from ISIN data
The Quick Monitor needs a per-tenor curve (2/5/7/10Y…) + Δ. From `fact_bond_instrument_obs`:
select, per (country, obs_date, target tenor), the bond whose `tenor_years` is nearest the bucket
(the Govy app uses `comparison_tenors [2,5,7,10]`). Store the mapping as a read-time view, not a
new fact — the ISIN fact stays the source of truth.

## Migrations (NEW — pending explicit OK to apply)

> **Numbering corrected 2026-07-17.** The `sov_bond_design.md` plan named slots `068`–`072` for
> bond work; those were **reused** (`068_create_econ_schema.sql` … the econ build took 068–069).
> Latest applied migration is **111**. New bond migrations therefore anchor at **112+**.
> Track A needs **no new DDL** — `fact_bond_yield` already exists (empty); the backfill loads
> through the ingest pipeline, not raw SQL.

| # | Migration | Track | Purpose |
|---|---|---|---|
| 112 | `112_create_dim_bond_instrument.sql` | B | ISIN identity dim (`dbo`). |
| 113 | `113_create_fact_bond_instrument_obs.sql` | B | Per-bond obs fact (`rates`). |
| 114 | `114_create_fact_bond_auction.sql` | B | Issuance calendar (`rates`). |

Seeding of instruments/curves happens **at ingest** (auto-seed pattern, like `BloombergRatesPipeline`
seeds `dim_curve`), so no separate seed migration is required. Track A reuses the already-seeded
`dim_bond_curve`/`dim_bond_source` (migs 064/066).

## Build sequence
1. **(now) Playground Govy reader** — `playground/bonds/govy_reader.py`: copy DB read-only, parse the 3 tables for IGB+KTB, emit the target row shapes, **report counts only (`--no-load`)**. Proves the shape end-to-end, zero DB writes. *No approval needed.*
2. Review the schema above → apply migs 073–076 (**needs OK — new DDL**).
3. Build the Govy ingest (lib in `src/imdr/`, runner) + tests; smoke `--no-load`, then load India+Korea (**needs OK — data load**).
4. Track A mirror reader + run 068 (Korea deep history) + tests.
5. Quality checks (RangeCheck yields, StaleCheck, ASW sanity) + docs update.
6. Wiring into a scheduler — **deferred, explicit OK required**.

## Linkage / FK review (best-practice check vs `schema_conventions.md`, 2026-07-17)

Full FK map after review (existing tables verified live; new tables authored):

| Table | Links to (dbo dims) | Status |
|---|---|---|
| `dbo.dim_bond_curve` *(exists)* | `dim_country`, `dim_vendor` (primary) | ✓ |
| `rates.dim_bond_source` *(exists)* | `dim_bond_curve`, `dim_vendor` | ✓ |
| `rates.fact_bond_yield` *(exists)* | `dim_bond_curve`, `dim_vendor`, `dim_frequency` | ✓ |
| `dbo.dim_bond_instrument` *(new)* | `dim_country`, **`dim_bond_curve`** | ✓ (curve link **added** this review) |
| `rates.fact_bond_instrument_obs` *(new)* | `dim_bond_instrument`, `dim_vendor`, `dim_frequency` | ✓ |
| `rates.fact_bond_auction` *(new)* | `dim_country`, **`dim_currency`** | ✓ (**was** `VARCHAR(3) currency` → now `currency_id` per §6) |

**Two fixes made this review:**
1. **ISIN→curve linkage** — added `dim_bond_instrument.bond_curve_id` FK → `dbo.dim_bond_curve`
   (nullable). This is the whole reason `dim_bond_curve` lives in `dbo`: it normalizes the ISIN grain
   (Track B) and the CMT grain (Track A) onto one curve identity. Without it the two grains float apart.
2. **§6 compliance** — `fact_bond_auction` used a `VARCHAR(3) currency` column on a fact; the convention
   is "no VARCHAR currency codes on facts" → replaced with `currency_id` FK → `dbo.dim_currency` (TINYINT).

**Conventions honoured:** FK column names match the dim (`country_id`/`currency_id`/`vendor_id`/`frequency_id`);
every FK column is indexed (§5.4); `vendor_id`+`frequency_id` in the obs natural key; `NOT NULL` by default;
`''` sentinels on the auction unique-key text cols (SQL Server NULL-in-UNIQUE quirk). Constraint prefixes
follow the **existing bond migrations' lowercase** `fk_/pk_/uq_/ck_/df_` (the doc shows `FK_`; code precedent wins).

**One open choice (not forced):** `fact_bond_auction` is calendar/reference data carrying a free-text
`source` column rather than a `vendor_id` FK. §8 would add `vendor_id` for externally-sourced rows;
auctions come from mixed sources (Govy config + live official). Left as `source` string — flag if you
want it normalized to `dim_vendor`.

## Scope of change & impact (verified against live DB + code, 2026-07-17)

### Current state (audited, not assumed)
| Fact | Verified |
|---|---|
| `dbo.dim_bond_curve` | *(superseded 2026-09-03: 58 rows / 52 active via Track C.)* 26 rows — 8 active (BBG_mirror), incl **KRW_KTB_NOMINAL_OTR active**, **INR_IGB_NOMINAL_CMT is_active=0**. |
| `rates.dim_bond_source` | *(superseded 2026-09-03: 98 rows via Track C.)* 54 rows (BBG tickers). |
| `rates.fact_bond_yield` | *(superseded 2026-09-03: 278,921 rows via Track C.)* **0 rows** — never backfilled. |
| Bond code | **None.** `grep dim_bond|fact_bond` across `src/scripts/tests` → 0 hits. Schema is orphaned DDL. |
| Bond ORM model | **None** in `src/imdr/models/`. Must be added. |
| Vendor | `BBG` = id 4 (reuse; no new vendor row). `citi_velocity`=1, `citi`=46 (pre-existing dup, not ours). |
| Frequencies | DAILY=5, SNAPSHOT=2 (bonds use DAILY). |
| Country ids | IN=24, KR=27, + the other 10 all present. |
| Migrations | latest = **111**; bond slots 063–067 applied; 068–072 reused by econ. New = 112+. |
| BBG_mirror `KRW_GOVT.csv` | **fresh to 17/07/2026** (daily), 3-header `Identifier/Ticker/Maturity` layout, GVSK 3M–20Y. |
| Govy `BBG.Yield.DB` | IGB 21 bonds / KTB 13 bonds, daily since 2025-12-19, last pull 2026-07-13. |

### Impact classification: **additive-only, low blast radius**
- **No existing table altered.** Three new tables (`dbo.dim_bond_instrument`, `rates.fact_bond_instrument_obs`, `rates.fact_bond_auction`); `fact_bond_yield` is populated, not changed.
- **No existing pipeline touched.** New ingest modules only. No edits to `fact_observation`, FX, econ, or any live feed.
- **No scheduler change** until an explicit wiring step (gated).
- **Data volume:** Track A backfill ≈ 210K rows (mirror, 2007+); Track B ≈ 37K yield rows (all 12) + ASW + ~260 auctions. Trivial vs `fact_observation` (21.5M).

### File-by-file change list
**New:**
| Path | Purpose |
|---|---|
| `src/imdr/models/rates_bond.py` | ORM: `DimBondCurve`(dbo), `DimBondSource`, `FactBondYield`, + new `DimBondInstrument`(dbo), `FactBondInstrumentObs`, `FactBondAuction`. |
| `src/imdr/schemas/rates_bond.py` | Pydantic `*Create` models. |
| `src/imdr/domains/rates/repository_bond.py` | Repos + `MergeSpec`s (mirror `RatesObservationRepository`). |
| `src/imdr/domains/rates/pipeline_bbg_bonds.py` | **Track A** — mirror CMT → `fact_bond_yield` (BasePipeline; reuse `csv_parser`, but key off **row 0 Identifier**, not row 1). |
| `src/imdr/domains/rates/govy_bonds.py` | **Track B** — Govy SQLite (read-only copy) → instrument fact + auctions. |
| `scripts/rates/bonds_backfill.py` + `scripts/rates/bonds_daily.py` | Runners (backfill + daily), `--no-load` smoke support. |
| `migrations/112–114_*.sql` | New DDL (above). |
| `tests/unit/test_rates/test_bbg_bonds.py`, `test_govy_bonds.py` | Parser + transform + no-move lock-in tests. |

**Modified (small):**
| Path | Change |
|---|---|
| `docs/admin/rates/sov_bond_design.md` | Correct stale migration numbering; add ISIN-fact + Govy source. |
| `docs/admin/development/quick_monitor/*.md` | Flip govt-bond rows to ✓ once loaded. |
| `docs/admin/rates/index.md` | Link the new bond ingest doc. |
| (later, gated) `scripts/imdr_daily.py` | Register the daily bond pipelines. |

### Parser nuance (Track A) — flag
The shared `parse_3hdr_csv` returns **row-1 aliases** (`BOND_KTB_3M`), but `dim_bond_source` is keyed
on the **row-0 Identifier** (`GVSK3MON Index`). The bond extractor must map on row 0. Also preserve
byte-exact `source_ticker` (double-space `GTJPYII5YR  govt`, mixed-case `GIDN30YR Index`).

### Risk register
| Risk | Mitigation |
|---|---|
| Govy `chg_1d` unreliable (India all-0 on 07-13) | compute Δ from stored history; treat vendor Δ as display-only. |
| Govy ASW sparse (3 bonds) + stale (~1mo) | ingest as-is, flag staleness; not a daily promise. |
| Govy DB freshness depends on desktop app uptime | StaleCheck + it's a *copy* ingest, so IMDR retains last-good. |
| ISIN vs CMT two-grain confusion | ISIN fact = source of truth; CMT tiles = read-time view, documented. |
| Govy SQLite locked/WAL while app runs | copy file (+wal/shm) then open the copy — never touch live. |
| Grain overlap KR (mirror CMT *and* Govy ISIN) | intentional (deep history + ISIN); dedup by vendor/source_app, not merged. |

### Effort / sequencing (all DB-touching steps gated on OK)
1. ✅ Playground reader (done — read-only shape proof).
2. ✅ **APPLIED 2026-07-20 (by user): migrations 112–114** + `src/imdr/models/rates_bond.py`
   (6 models), `src/imdr/schemas/rates_bond.py` (4 Create schemas). Verified live: 3 tables exist
   (cols 14/18/16), all 7 FKs resolve (incl the `fact_bond_auction.currency_id`→`dim_currency` FK
   added to 114 this session).
3. ✅ **Track B ingest BUILT + REVIEWED 2026-07-20 (not loaded):** `repository_bond.py` (3 repos + MergeSpecs),
   `domains/rates/govy_bonds.py` (read-only copy → extract → dedup → validate), `scripts/rates/bonds_govy.py`
   (CLI, `--no-load`/`--countries`/`--db`), `tests/unit/test_rates/test_govy_bonds.py` (**24 tests**, all pass).
   `configure_mappers()` clean. `--no-load` smoke: **4,552 obs** (4,540 one-per-day yields + 12 ASW),
   32 instruments, 30 auctions, 0 skipped. **Full software review (code-reviewer agent + manual): no
   load-blocking bugs; atomic single-transaction load; zero blast radius (no existing table/pipeline touched;
   the new modules are imported nowhere but their own runner/tests).** Fixes applied post-review:
   (a) `bond_curve_id` made insert-only in the dim MERGE (was clobbered to NULL on re-run);
   (b) auction rows now dedup last-write-wins (`_dedupe_auctions_latest`) to prevent a future dup-key MERGE crash;
   (c) `tenor_years IS NULL` guard in the extractors (would else abort the whole load on ValidationError).
   **Deferred to the scheduler-wiring gate:** refactor `GovyBondsPipeline` onto `BasePipeline` so a scheduled
   run writes an `audit.PipelineRun` row (every other domain's pipeline does; not needed for a manual load).
4. ⏳ Track B load India+Korea **(NEEDS OK — data load; next gate)**.
5. Track A mirror ingest + tests → backfill Korea (+6) **(needs OK to load)**.
6. Quality checks + doc flips.
7. Scheduler wiring **(separate explicit OK)**.

### Decisions locked (2026-07-20, ingest build)
- **Yield grain = ONE authoritative row per (isin, obs_date, quote_type)** — latest `snapshot_ts` wins,
  regardless of `source`. The source is heavily over-sampled (one IGB bond had 24 intraday snapshots/day;
  7,114 raw yield rows → 4,540 distinct bond-days). `pricing_source` is descriptive (which feed won), NOT
  part of the dedup grain. Idempotency note: the deployed fact unique key is a *superset*
  `(instrument_id,vendor_id,obs_date,quote_type,pricing_source)`, so a single load never self-collides; the
  winning source per bond-day is stable across re-runs in practice (historical dates aren't re-pulled; live
  pulls are consistently BQL). No key migration taken.
- **`pricing_source` normalization**: 4 raw source strings observed, all mapped to ≤12-char canonical codes
  (`blpapi-bql`/`Excel BQL`→`BQL`, `Excel BQL history`→`BQL_HIST`, `Excel history import…`→`EXCEL_IMPORT`,
  `workbook_seed`→`SEED`). VARCHAR(12) is sufficient — no real value truncates.
- **`fact_bond_auction.source` VARCHAR(30)**: accept clipping. NB — empirically **all 30/30** IGB+KTB
  auction rows exceed 30 chars (not "~2" as first estimated), e.g. `"RBI Issuance Calendar H1 FY2026-27 (PIB)"`
  (40) → `"RBI Issuance Calendar H1 FY202"`. The `H1`/FY differentiator generally survives the clip, so it
  stays provenance-only (no data-integrity impact) — but if full provenance fidelity is ever wanted, widen
  the column then (empty-table ALTER). No width migration taken now.
- **Timezone**: Govy stores naive `snapshot_ts`/`fetched_at`; ingest attaches UTC. `obs_date` derives from
  the calendar day (`as_of_date`), unaffected. Revisit only if intraday `obs_ts` is ever used.
- **KTB `chg_1d` all-zero** confirmed live — vendor Δ stored as-is (display-only); Quick Monitor recomputes Δ
  from stored history.

**Authored artifacts (review before apply):**
`migrations/112_create_dim_bond_instrument.sql` · `113_create_fact_bond_instrument_obs.sql` ·
`114_create_fact_bond_auction.sql` · `src/imdr/models/rates_bond.py` · `src/imdr/schemas/rates_bond.py`.

## Hard rules in play
- **NO EDITS to Govy Monitor** — read a copy only.
- BBG_mirror READ-ONLY.
- **No DDL / no data load / no prod wiring without explicit OK** — steps 2/3/4/6 gated.
- Tests + this doc kept current (split code vs data promotion).
