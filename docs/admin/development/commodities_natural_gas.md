# Natural gas in IMDR — build tracker

**Status:** ✅ **Phase 1 DATA-LIVE 2026-09-22** (loaded, **not wired** — user holding on scheduler) ·
🔨 **Phase 3 BUILT 2026-09-23, load blocked on DBA** (`CREATE TABLE` denied — account is CRUD-only) ·
Phases 2 & 4 scoped, not started · BBG track **parked at user's request**
**Owner:** adoshi · **Linear:** _pending_

Sister docs: [`../vendors/citi/exploration/commodities.md`](../vendors/citi/exploration/commodities.md)
(Citi commodity tag tree) · [`../econ/united_states/united_states_prod_pipeline.md`](../econ/united_states/united_states_prod_pipeline.md)
(US econ ops runbook).

---

## 1. Why

IMDR has **one** natural-gas price series and **no** gas fundamentals:

| What | Where | State |
|---|---|---|
| Henry Hub spot (USD/MMBtu, daily) | `econ.fact_indicator` → `EIA.ENERGY.HH_GAS_SPOT.US` | ✅ live, 2015-01-02→, T-5 lag, loaded in weekly ~5-obs batches |
| Henry Hub spot (FRED dupe) | `FRED.ENERGY.NATGAS.US` | ⛔ `is_active=0` — deliberate dupe kill, do not revive |
| US gas storage (the market-moving print) | `econ.fact_indicator` → `EIA.NATGAS.STORAGE_*.US` | ✅ **added 2026-09-22** — 8 series × 872 weeks, 2010→; not yet wired |
| Gas futures curve / strip | — | ❌ absent — EIA's `RNGC1`–`RNGC4` died 2024-04-05; CME/ICE are ToS-blocked |
| TTF, JKM | `commodities.fact_price_forecast` (Citi house forecast) | 🔨 **built 2026-09-23** — 112 rows ready; **no market price exists without BBG**, this is a VIEW |
| Anything gas in `commodities.*` | `dim_commodity` + **NG_HH / NG_TTF / NG_JKM** (ids 6–8) | ✅ seeded 2026-09-23 |

Desk questions currently unanswerable: what the Thursday EIA storage print was vs the
5-year band, where the HH curve sits, what European/Asian gas is doing.

## 2. Source survey (probed 2026-09-22, not assumed)

| Source | Probe result | Verdict |
|---|---|---|
| **EIA `natural-gas/stor/wkly`** | 200 OK · **8 series** (Lower-48, East, Midwest, Mountain, Pacific, South-Central + salt/nonsalt splits) · 2010-01-01 → 2026-09-11 · Bcf | ✅ **Phase 1** |
| **EIA `natural-gas/pri/fut`** — `RNGC1`–`RNGC4` (HH futures 1–4) | Series exist, **last obs 2024-04-05** | ❌ discontinued — no curve from EIA |
| **EIA `natural-gas/pri/fut`** — `RNGWHHD` | Live, T-5 lag | ⚠️ already ingested; history source, not a live tick |
| **CME settlements JSON** (`/CmeWS/mvc/Settlements/...`) | HTTP **403** — *"scripts, software, spiders, robots … strictly prohibited"* | ❌ **ToS-blocked. Do not attempt.** |
| **ICE delayed-markets JSON** | HTTP 403 (Akamai) | ❌ |
| **stooq CSV** (`ng.f`, `cl.f`, `cb.f`) | SHA-256 proof-of-work JS challenge on every request | ❌ (retail EOD anyway) |
| **Citi Velocity** | Gas appears **only** as `COMMODITIES.FORECAST.ENERGY.{HH_NGAS,TTF_NGAS,JKM_LNG}.{POINT_PRICES.0_3M, POINT_PRICES.6_12M, QTR, ANNUAL}.PRICE_FCST.CITI`. Full commodities tree = 3 spot tags · 67 EIA petroleum · 1,011 implied-vol · 115 forecast · 6 index | ⚠️ a **house view**, not a price → **Phase 3** |
| **GIE AGSI+** (EU storage) | 200 keyless but `total: 0` — needs free registered key (`x-key` header); `gas_day` current | ✅ **Phase 4** |
| **ENTSOG transparency** (EU flows) | 200 **keyless**, returns rows | ✅ **Phase 4** |
| **Bloomberg Terminal** | [`bloomberg/refresh.py`](../../../bloomberg/refresh.py) producer framework is live and generic (`tickers/{rates,bonds,fx}.csv`, per-user, 3 cadences). No commodities sheet; `bbg_mirror_inventory.csv` has **zero** commodity rows; `blpapi` not in the `imdr` env (by design) | ⏸️ **PARKED** — see §7 |

**Conclusion:** there is **no free, licensed, programmatic source for TTF or JKM**. JKM is
Platts-proprietary; TTF settlement is ICE's. Every scrapable route is ToS-blocked or
bot-walled. The gas *price* surface beyond Henry Hub spot requires Bloomberg.
What is reachable without BBG is **US fundamentals + history + the Citi house view** —
that is Phases 1–4.

---

## 3. Phase 1 — EIA weekly gas storage → `econ.fact_indicator` ✅

**Goal:** the Thursday 10:30 ET Weekly Natural Gas Storage Report, 8 series, 2010→.

| Item | Detail |
|---|---|
| Route | `natural-gas/stor/wkly`, `frequency=weekly`, facet `series` |
| Transport | **reuse** [`src/imdr/domains/econ/eia_http.py`](../../../src/imdr/domains/econ/eia_http.py) — `EiaClient`, key `IMDR_ECON_EIA_KEY` already set |
| New fetcher | `scripts/econ/us/eia/eia_natgas_storage.py` — config-driven `_SERIES` map, same shape as `eia_energy.py`, but **one** `fetch_series` call with all 8 ids as a list facet (2 HTTP requests, not 8 paginations) |
| Codes | `EIA.NATGAS.STORAGE_{L48,EAST,MIDWEST,MOUNTAIN,PACIFIC,SOUTH_CENTRAL,SOUTH_CENTRAL_SALT,SOUTH_CENTRAL_NONSALT}.US` |
| Unit | `bcf` — **does not exist in `dbo.dim_unit`** → migration 131 |
| Frequency | `WEEKLY` (dim_frequency id 6) · Category `energy` · `country_code="US"` · SA = false |

**Series map (verified against the live facet list):**

| EIA series | imdr_code |
|---|---|
| `NW2_EPG0_SWO_R48_BCF` | `EIA.NATGAS.STORAGE_L48.US` |
| `NW2_EPG0_SWO_R31_BCF` | `EIA.NATGAS.STORAGE_EAST.US` |
| `NW2_EPG0_SWO_R32_BCF` | `EIA.NATGAS.STORAGE_MIDWEST.US` |
| `NW2_EPG0_SWO_R33_BCF` | `EIA.NATGAS.STORAGE_SOUTH_CENTRAL.US` |
| `NW2_EPG0_SSO_R33_BCF` | `EIA.NATGAS.STORAGE_SOUTH_CENTRAL_SALT.US` |
| `NW2_EPG0_SNO_R33_BCF` | `EIA.NATGAS.STORAGE_SOUTH_CENTRAL_NONSALT.US` |
| `NW2_EPG0_SWO_R34_BCF` | `EIA.NATGAS.STORAGE_MOUNTAIN.US` |
| `NW2_EPG0_SWO_R35_BCF` | `EIA.NATGAS.STORAGE_PACIFIC.US` |

**⚠️ Ordering gotcha:** FK resolution on `unit` happens in
`scripts/migrations/load_econ_indicator_from_playground.py`. An unrecognised `unit_code`
collects into `seen_missing` and the loader then **aborts the whole parquet pair** —
`!! FK resolution failures`, `return 2` — so *nothing* loads, not even the rows whose FKs
were fine. **Migration 131 MUST be applied before the first load.**

> **Correction (code review, 2026-09-22):** migration 123's header describes this as a
> silent per-row skip that still exits 0. That is **wrong** — verified against the loader;
> the abort has been there since `69508fe` (2026-06-05). The first drafts of 131, the
> fetcher docstring and the test comments all inherited 123's wording and have been fixed.
> **Do not copy 123's wording into new migrations.**

**Partial-response guard:** all eight series share one publication and one history, so a
response missing 1–7 of them means EIA renamed or retired a series id. The fetcher
**raises** in that case rather than loading the survivors — `run_main`'s only emptiness
gate is *no observations at all*, which a surviving `L48` would satisfy on its own,
leaving the other seven silently stale once scheduled (the `rbi_bulletin` failure class,
`feedback_silent_fetcher_failure_detection`). An entirely empty response still falls
through to `run_main`'s rc=1.

**Not in scope:** the weekly *change* (the "+82 Bcf build" headline) and the 5-year band
are **derived** from the levels. Compute downstream; do not store a derived series next to
its inputs.

### Checklist
- [x] `migrations/131_seed_dim_unit_bcf.sql` — `bcf`, category 6 (physical), scale 1.0, idempotent
- [x] Apply 131 via `python -m scripts.migrations.apply_migration`
- [x] `scripts/econ/us/eia/eia_natgas_storage.py`
- [x] Unit test — `tests/unit/test_econ/test_eia_natgas_storage.py`, 18 passing
- [x] Smoke `--no-load`, report row counts, **ask before loading**
- [x] **Loaded 2026-09-22** — `staged=6,976 new=6,976 revision=0 skipped=0`; DB-verified:
      8 indicators × 872 obs, 2010-01-01→2026-09-11, unit `bcf` / WEEKLY / energy / US,
      0 duplicate (indicator, obs_date, vintage) keys. Identity re-checked in SQL:
      L48 vs sum-of-5-regions max |diff| **2 Bcf**, 10 weeks of 872 over 1 Bcf (EIA's own
      rounding of the published regionals); South Central = salt+nonsalt within 1 Bcf.
- [x] Docs: [US indicator inventory](../econ/united_states/united_states_indicator_inventory.md) §4 + §8 ·
      [US prod pipeline](../econ/united_states/united_states_prod_pipeline.md) EIA section
- [ ] **Wiring into `us_daily.py` — requires explicit OK** (weekly series, daily poll is
      idempotent via MERGE-on-PK; alternative is `imdr_weekly.py`)

## 4. Phase 2 — history backfill for `commodities.fact_spot`

`commodities.fact_spot` is **2026-only**: WTI (`CR_NYM_CL`) 174 obs from 2026-01-02,
gold 193, silver 180 — because the Citi live pipeline started then. Brent
(`CR_IPE_BRENT`) holds 61 stray obs 2021→2026 and **has no Citi spot tag at all**
(confirmed: only 3 SPOT tags exist in the entire Citi commodities tree).

> **Answers "can WTI be made daily?" — it already is.** `commodities.spot` runs **4×/day**
> (00:12, 06:04, 12:15, 18:13 UTC) via [`imdr_daily.py`](../../../scripts/imdr_daily.py),
> last obs 2026-09-21. The gap is history, not cadence.

- [ ] Add Henry Hub to `dim_commodity` (`NG_HH`, class `energy`, `spot_tag` NULL)
- [ ] Decide: does `fact_spot` tolerate a second vendor (EIA alongside Citi)? It has no
      `vendor_id` column — the same shape as the `fx.fact_ohlc` landmine. **Resolve before ingest.**
- [ ] Backfill WTI/Brent/HH from EIA (2015→, or 1986→ for `RWTC`/`RBRTE`)
- [ ] Alternative/parallel: `cmdty_citi_historical.py` for WTI (quota-aware — 100k tags/24h)

## 5. Phase 3 — Citi gas forecasts (the house view) — **BUILT 2026-09-23, load blocked on DBA**

12 tags, negligible quota. The only TTF/JKM numbers obtainable without a Terminal.
Probe: `playground/commodities/probe_citi_gas_forecasts.py`. **All 12 tags return data.**

### 5.1 Payload gotchas (each cost a wrong first answer — do not re-learn)

1. **The value key is `c` (close), not `y`.** Shape is
   `{"frequency", "status", "body": {"<tag>": {"x": [yyyymmdd], "c": [float], "type": "SERIES"}}}`.
   Reading `y` returns an **empty list silently** — every tag looks like 0 values.
2. **`fetch_historical`'s `end` clips on the TARGET date for FORECAST tags.** For
   `QTR`/`ANNUAL` the x-axis is the *forecast target period*, not the as-of date, so
   `end=today` **silently drops the entire forward curve** and the tags look stale/
   backward-looking. Query with `end = today + ~4y`. With a forward window: **6 forward
   quarters + 2 forward years** per product.
3. **`fetch_metadata` returns `{"message": "Invalid Input", "status": "ERROR"}`** for the
   whole FORECAST branch — no units, no display names. Units must be hard-coded
   (HH = USD/MMBtu, TTF = EUR/MWh, JKM = USD/MMBtu — **confirm before storing**).

### 5.2 Two different shapes behind one tag family

| Tag family | x-axis | Points | Behaviour |
|---|---|---|---|
| `POINT_PRICES.{0_3M,6_12M}` | **as-of date**, daily | 579 over 2.2y | A **step function** — republished daily but only **6–9 changes in 2.2 years**. ~99% of rows are repeats of the prior day |
| `QTR` / `ANNUAL` | **target period end** | 16 / 5 | A forward **curve**, current vintage only. Re-fetching overwrites; an as-of history exists only if we snapshot |

This is the design crux: the two families are not the same object. `POINT_PRICES` gives
as-of history for free; `QTR`/`ANNUAL` give a curve with no vintage dimension unless we
snapshot daily.

### 5.3 Live values (2026-09-22)

| Product | 0–3M | 6–12M | Q4-26 | Q1-27 | 2027 |
|---|---:|---:|---:|---:|---:|
| Henry Hub (USD/MMBtu) | 2.8 | 2.5 | 3.3 | 3.2 | 2.81 |
| TTF | 18.7 | 13.6 | 19.1 | 17.4 | 14.0 |
| JKM | 19.2 | 14.1 | 19.6 | 18.0 | — |

### 5.4 Built 2026-09-23 — BLOCKED ON DBA

Everything is written and green except the table itself: **the IMDR account is
`db_datareader` + `db_datawriter` only — CRUD, zero DDL**. `CREATE TABLE` returns
*"CREATE TABLE permission denied in database 'imdr'"*. (Migration 131 landed only because
it was an INSERT.) Same gate as migrations 120–122.

| Piece | State |
|---|---|
| `migrations/132_create_commodities_fact_price_forecast.sql` | ⏳ **needs DBA** for the `CREATE TABLE`; the `dim_commodity` MERGE half was applied by hand (CRUD) and is idempotent, so the DBA can just run the whole file |
| `commodities.dim_commodity` + NG_HH / NG_TTF / NG_JKM (ids 6–8) | ✅ seeded |
| `src/imdr/universe/commodities.yml` — `forecast:` block | ✅ 12 tags; adding any of the other 26 products is a one-line entry |
| `CommoditiesUniverse.forecast_*` | ✅ |
| `imdr.domains.commodities.translate_forecast` | ✅ pure + fully tested |
| `CmdtyFactPriceForecast` model · `_FORECAST_SPEC` · `CmdtyPriceForecastRepository` | ✅ |
| `scripts/commodities/citi/cmdty_forecast_citi_live.py` | ✅ runs; `--no-load` verified end-to-end |
| `tests/unit/test_cmdty_translate_forecast.py` | ✅ 26 tests |
| Load | ⏳ blocked on the table |

**Verified `--no-load` run:** 12/12 tags, **3,543 vendor points → 112 rows** after step
compression (97% smaller), forward curve out to 2027-12-31.

#### Two defects found and fixed while building

1. **`bulk_merge` could not express this table's natural key.** `target_date` is NULL on
   every RELATIVE row, and the generated `ON` clause used plain `tgt.col = src.col`.
   `NULL = NULL` is never true, so MERGE would take the NOT MATCHED branch on *every*
   run — re-inserting existing rows and colliding with `UX_fact_price_forecast_natural`,
   which (unlike `=`) *does* treat NULLs as equal. Added an opt-in `null_safe_key` to
   `MergeSpec`; omitted, every existing caller behaves exactly as before. The pre-existing
   `nullable_columns` only shapes the staging DDL and does not help here.
2. **`record_usage(pipeline, tags)` takes its arguments in the opposite order to
   `check_budget(needed, pipeline)`.** A reversed call wrote
   `{"pipeline": 12, "tags": "commodities.price_forecast"}` into the **shared**
   `data/cache/citi_tag_quota.json`, after which `current_usage()` raised
   `TypeError: unsupported operand type(s) for +: 'int' and 'str'` — for *every* Citi
   pipeline on the box, not just the offender. File repaired (817 → 816 entries,
   cumulative 56,210 tags) and `record_usage` now type-checks both arguments and names the
   reversal in the error.

#### Known trade-off

ABSOLUTE rows are snapshotted every run, so an unchanged curve stores a fresh `as_of_date`
each day (~24 rows/day for the 3 gas products). Detecting "unchanged since yesterday" needs
a DB read, which would make the transform impure; revisit if row growth ever matters.

## 6. Phase 4 — EU gas fundamentals (optional)

- [ ] **GIE AGSI+** — register free key → `IMDR_GIE_KEY`; EU + per-country storage fill %
- [ ] **ENTSOG** transparency — keyless; physical flows by point (Russian/Norwegian/LNG entry)

## 7. Parked — Bloomberg track (TTF · JKM · curves · Brent)

Parked by the user 2026-09-22 ("keep BBG out of it for now"). Recorded so the reasoning is
not re-derived later:

- The **only** licensed route to TTF, JKM, a real NG futures strip, and a daily Brent.
- Mechanically small: a new `bloomberg/tickers/commodities.csv` (same columns as
  `fx.csv`: `ticker,user,fields,schedule,enabled,owner,…`), plus a consumer-side watcher.
- Blocked on a **person**, not on code: needs a Terminal-logged user assigned to own the
  scheduled pull.

## 8. Open questions

1. ~~Why `econ.fact_indicator` and not `commodities.*` for storage?~~ **RESOLVED 2026-09-22.**
   Spider's own grounding rule ([`spider_daily_spec.md`](../research/spider_daily_spec.md))
   splits the layers: *actuals + component depth ⟵ `econ.fact_indicator`; market moves ⟵
   market layers (`FX.fact_fx_rate` · `equities.fact_index_level` · `rates.fact_observation`
   · `commodities.fact_spot`)*. Storage is a scheduled statistical **release**, not a price.
   The concrete blockers on the alternative, `commodities.fact_eia`:
   **(a)** its PK is `(eia_series_id, obs_date, stat_value)` with **no vintage column** —
   EIA revises storage, so a revision would silently overwrite history;
   **(b)** it is fed by Citi tags `COMMODITIES.EIA.*`, and **Citi carries no gas tags at
   all** (all 67 are petroleum), so EIA-direct gas would mix two vendors in a table with
   **no vendor column**; **(c)** `stat_value` is `NOT NULL`, so a withheld EIA value cannot
   be stored; **(d)** no agent reads it (18 `econ.fact_indicator` references across Atlas /
   Smith / Spider, zero for `fact_eia`); **(e)** HH spot already lives in econ under the
   same vendor. The one real point *for* `commodities.*` — `dim_eia_series` has a proper
   `region` column, vs region-in-the-`imdr_code` — is a modelling nicety that does not
   outweigh (a)–(d). Revisiting would mean first adding `vendor_id` + a vintage column to
   `fact_eia`, which is arguably the right long-term fix for that table regardless.
2. `commodities.fact_spot` has no `vendor_id` — does oil/gas **price** history from EIA go
   in there, or do prices stay split (Citi → `commodities.*`, EIA → `econ.*`)?
   **Decide in Phase 2.**
3. Should the EIA storage print get a release row so Spider can preview it?
   (`calendar.cb_events` is central-bank-scoped — this probably needs a different home.)
4. Phase 3 target table shape — new fact table vs. widening an existing one.
