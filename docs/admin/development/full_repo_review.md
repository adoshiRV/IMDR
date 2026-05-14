# Full Repo Review — Domain-by-Domain Lean Pass

- **Filed**: 2026-05-13
- **Status**: in progress — 4 of 21 subdirs walked + FX overhaul Phases 1-4 of 6 shipped + FX file-walk 10 of 19 files done
- **Owner**: <OWNER>
- **Goal**: **make IMDR lean and meaningful.** Every file justifies itself or it goes. Stale exploration, half-finished refactors, dead `__init__` exports, duplicated patterns, and orphan tests get cut.
- **Scope**: every file in the repo — **tracked, untracked, and gitignored alike** — reviewed through the lens of *the domain it serves*, not the directory it lives in. Tracked count was 432 as of 2026-05-13; an additional 47 untracked production files surfaced on 2026-05-14 (BBG core ingest, Phase D country/calendar work, polymarket prediction, research MCP). Gitignored runtime dirs (`data/`, `.venv/`, build artifacts) get a quick glance to confirm nothing important is hiding, then we move on.

## Progress log (last updated 2026-05-15)

Tests: **1028 passing, 6 baseline failures, 2 skipped** (+50 net since walk start). Baseline failures unchanged — same `test_fx_rate_universe` + `test_cmdty_universe` known-fails.

### Subdirs walked (4 of 21)

| # | Subdir | Files | Outcome |
|---|---|---|---|
| 1 | **Repo root** | 8 | README rewritten, `arjun_notes.txt` deleted, `setup.txt` relocated → `docs/admin/setup/dev_environment.md`, `.gitignore` collapsed, `.vscode/settings.json` expanded with sensible defaults, `pyproject.toml` cleaned (description fix, ruff src expanded, stale apscheduler comment removed). `.mcp.json` + `.env.example` kept as-is. |
| 2 | **`src/imdr/config/`** | 4 | `extra="forbid"` added to all 4 pydantic config models (catches yml typos at startup). `mssql_driver` default fixed to `SQL+Server`. `fx.spot_rates` dead chain deleted (17 files touched, 5 deleted). Dead `sources:` block removed from every pipeline + `SourceConfig` deleted. Followup filed at [`settings_env_unification.md`](settings_env_unification.md). |
| 3 | **`src/imdr/connectors/`** | 8 | New `_sql_safety.py` (shared validators, dedup'd from bulk + reader). `bulk.py` docstring fix + SQL caching + 8 new tests. `citi_helpers.py` typed `client: CitiVelocityClient`, hoisted `import re`, extracted `_make_error_entry` + `_process_batch` helpers + 27 new tests. `citi_velocity.py` 2× `raise ... from e`. `reader.py` 12 new tests. 4 admin docs updated via doc agent. |
| 4 | **`data_access.py` + `queries/`** | 3 | All dead — deleted (280 lines). Zero callers anywhere; v1 facade got bypassed by `AnalyticalReader` + per-domain repositories. |

### FX overhaul phases (subdir 5 prelude — 4 of 6 done)

Six-phase overhaul of `src/imdr/domains/fx/`. User-approved scope: rename for consistency, dedupe duplicated patterns, merge OHLC into the class-based pipeline shape that rate/vol use.

| Phase | Status | Commit |
|---|---|---|
| 1 — Renames + spec public | ✅ shipped | `62220c0` |
| 2 — Parquet store consolidation | ✅ shipped (same commit) | `62220c0` |
| 3 — Coverage helper dedup | ✅ shipped | `8e0c597` |
| 4 — OHLC merge (fold `ingest.py` into `pipeline_ohlc.py`) | ✅ shipped | `47be7ba` |
| 5 — Pipeline tests (~7 transform tests) | ⏳ pending | — |
| 6 — Git-add FX-BBG chain (~14 untracked files) | ⏳ partial — files 9 + 10 brought 4 of them under VC | — |

Concrete artifacts of phases 1-3 (preserved here for reference):
- `repository.py` → `repository_ohlc.py`, `extractors.py` → `extractors_ohlc.py`, `time_utils.py` → `src/imdr/utils/time_windows.py`
- `_FX_RATE_SPEC` / `_FX_VOL_SPEC` → public `FX_RATE_SPEC` / `FX_VOL_SPEC`
- New `domains/fx/_parquet_store.py` with shared `write_partitioned_parquet()`; `store_rate.py` + `store_vol.py` deleted (95% identical, ~100 lines net saved)
- `coverage.py` extracted `_per_pair_row_counts` + `_row_counts_summary` (only the truly-identical bits — per_pair queries left inline to avoid string-template parameterisation)
- 4 dead imports removed in passing (`pandas` in coverage, `parse_x_to_ts_utc` in vol_translate, `discover_bbg_fx_files` in pipeline_rate_bbg, `holiday_hits_for_timestamp` in fx_bidfx_historical)

Phase 4 artifacts:
- `ingest.py` (267 lines) deleted; `process_hour()` + `HourResult` + quality/anomaly/parquet helpers folded into `pipeline_ohlc.py`. Two bidfx script imports retargeted.
- Fixed Phase 1 straggler: `extractors_ohlc.py` was still importing `HourWindow` from the deleted `imdr.domains.fx.time_utils` — caught by the post-merge smoke test.
- Dropped unused `get_pipeline_config` import per the doc's note.

PM agent reviewed phases 1-2 before push (green-lit phase-by-phase commits over a single mega-PR, flagged the `pipeline.py` deletion lineage + the BBG-chain staging exclusion, confirmed `fx_dim_currency_pair_string_cleanup.md` conflict avoidance).

### FX file-by-file walk (subdir 5 proper — 10 of 19 files done)

Started after the FX overhaul as the formal "per-file verdict" walk over `src/imdr/domains/fx/`. Per-file decisions tracked in [`fx_walk_optimization_log.md`](fx_walk_optimization_log.md) (applied / deferred / skipped with reasons).

| # | File | Action | Commit |
|---|---|---|---|
| 1 | `__init__.py` | Emptied dead `FXOHLCRepository` re-export | `641d630` |
| 2 | `_parquet_store.py` | Keep (recently introduced, clean) | — |
| 3 | `clean_fx_fact_fx_rate.py` | Keep + filed [`cleaning_rules_consolidation.md`](cleaning_rules_consolidation.md) (5-way collapse) | — |
| 4 | `clean_fx_fact_ohlc.py` | Keep + extended consolidation doc with OHLC patterns + extension hooks | — |
| 5 | `clean_fx_fact_vol.py` | Keep + extended consolidation doc with vol 4-tier pct rule | — |
| 6 | `coverage.py` | Keep (Phase 3 already trimmed it) | — |
| 7 | `extractors_ohlc.py` | Rewrite: delete 2 dead stub classes, hoist 3 imports, fix docstring + **27 new tests** | `641d630` |
| 8 | `extractors_rate.py` | Opt A (`_errors` → public), E741, **11 new tests** + filed [`citi_fetch_batch_across_pairs.md`](citi_fetch_batch_across_pairs.md) | `ef2be5c` |
| 9 | `extractors_rate_bbg.py` | Opt A, E741, dict→yml config, collapse tenor normalization, single boolean mask, no-spot warning + 1 test | `edc6835` |
| 10 | `extractors_vol.py` | Opt A, E741, `tag_errors` diagnostic parity, **11 new tests** + filed [`extractor_errors_rename.md`](extractor_errors_rename.md) (cross-domain) | `70eba89`, `0dbbb3d` |

Pending files 11-19: pipelines (ohlc / rate / rate_bbg / rate_bbg_daily / vol), translate (rate / vol), repositories (ohlc / rate / vol). Several already touched in slices 7-10 via caller updates.

### Memory notes added during the walk

- `feedback_file_walk_keep_moving.md` — defer doc relocations; just walk files
- `feedback_walk_includes_all_files.md` — 47 untracked production files in scope
- `project_healthchecks_needs_rework.md` — `healthchecks/` subdir gets a redesign proposal, not per-file edits
- `feedback_breakdown_design_upfront.md` (pre-existing) — by-X reports design upfront
- **`feedback_always_write_tests.md`** (new 2026-05-15) — every `src/` module needs tests; pin exact error-message strings; missing tests is a finding to fix now, not defer to Stage E3
- Memory line for `FXSpotExtractor` was stale — corrected to point at the post-rename `extractors_ohlc.py` / `extractors_rate.py` / `extractors_vol.py` split

### Dev docs filed during the walk

| Doc | Scope |
|---|---|
| [`fx_walk_optimization_log.md`](fx_walk_optimization_log.md) | Single index across files 1-19; per-file ✅/📄/❌/🚧 status + reasons |
| [`ruff_sweep_scope.md`](ruff_sweep_scope.md) | 645 ruff findings broken into 4 tiers; 5-step execution plan |
| [`cleaning_rules_consolidation.md`](cleaning_rules_consolidation.md) | 5-way `HardBoundViolationRule` / `RobustOutlierRule` / `PercentageChangeRule` collapse with `TableSpec` shape |
| [`citi_fetch_batch_across_pairs.md`](citi_fetch_batch_across_pairs.md) | Cross-pair Citi batching — 19 HTTP calls → 3 for live FX rate, 18 rate-limit sleeps → 2 |
| [`extractor_errors_rename.md`](extractor_errors_rename.md) | `_errors` → `errors` across 5 Citi extractors + optional `BatchedCitiExtractor` base |

### Deferred / blocked

- **`healthchecks/` rework** — affects every domain's `clean_*.py` + `_run_quality_checks` + `get_health_checks` boilerplate. Wait for the redesign before further per-file cleanup there.
- **`Settings` `extra="forbid"`** — blocked by `IMDR_RESEARCH_*` env vars consumed by separate loaders (`playground/research/`, `mcp/research_server.py`). Plan in [`settings_env_unification.md`](settings_env_unification.md).
- **`fx_dim_currency_pair_string_cleanup`** — the 12 `base_ccy + quote_ccy` string-concat sites in `coverage.py` stay as-is until that task runs.
- **Cross-domain `extractor._errors` rename** — 7 callsites across commodities/rates/equity. Bundle with `BatchedCitiExtractor` base extraction as one slice before Stage D per-domain trims. See [`extractor_errors_rename.md`](extractor_errors_rename.md).
- **5-way cleaning rules collapse** — gated on the `healthchecks/` redesign decision. See [`cleaning_rules_consolidation.md`](cleaning_rules_consolidation.md).
- **Cross-pair Citi batching** — contract-changing, bundle with healthchecks redesign + per-domain trims. See [`citi_fetch_batch_across_pairs.md`](citi_fetch_batch_across_pairs.md).
- **Ruff 645-finding sweep** — Tier 1 (~360 true-no-op fixes) safe to run in one session; Tier 2 needs per-file eyeball. See [`ruff_sweep_scope.md`](ruff_sweep_scope.md).

### Open follow-ups still on the punch list

- `for _, row in raw.iterrows():` in `pipeline_rate.py:172` + `pipeline_vol.py:119` — pending `to_dict("records")` rewrite (10-50× speedup for historical backfills). Will land when files 12 + 15 are walked.
- `BidFXExtractor` integration tests with HTTP mocking — pure-helper tests landed in slice 7; networked surface needs a mocking harness.
- `BidFXExtractor._process_currency` reaches into `universe._order_pair` private — defer to Stage D1 (universe rewrite, not extractor edit).

## Why this structure

The repo is laid out by *kind of code* (`models/`, `schemas/`, `domains/`, `scripts/`, `migrations/`, `tests/`, `docs/`, `notifications/`, etc.) but it *functions* as a small number of **vertical pipelines**, one per market data domain. To judge whether a file is pulling its weight, you have to see it next to the other 8–15 files that share its pipeline — not next to other files of the same kind.

So we review by domain. Within each domain we walk the **vertical slice** end-to-end: schema → universe → vendor extract → translate → store → read → quality-check → orchestrate → schedule → notify → test → document. At each stop we ask:

> *Is this file still earning its keep? Is there a simpler shape that does the same job? Has the world moved on under it?*

## The lean-code rules (apply to every file)

A file is **stale** and gets discarded if any of these are true:

1. **No callers** — nothing imports it, no script invokes it, no scheduler references it. Verify with `rg <symbol>`.
2. **Cached one-shot** — exploration / probe script whose results are pickled in `data/cache/` and written up in a doc. Move insights to docs, delete the script (or migrate to `playground/` per the project rule).
3. **Superseded** — newer file in the same pipeline does the same job. Common signal: `foo.py` next to `foo_v2.py`, `extractors.py` next to `extractors_rate.py`, `pipeline.py` next to `pipeline_ohlc.py`.
4. **Half-finished** — code path that branches but the branch goes nowhere (unused vars, TODO with no consumer). Already 33 ruff F-findings on file.
5. **Dead config** — entry in `pipelines.yml` / `universe/*.yml` / `events.yml` that no live pipeline reads.
6. **Orphan template / formatter** — Jinja template with no formatter, formatter referenced by no scheduler.
7. **Placeholder docs** — `.gitkeep` files in folders that now have real content; empty/stub markdown that's never been written.
8. **Schema rot** — migration's effect was rolled back by a later migration; table/column it created no longer exists.

A file is **bloated** and gets refactored / merged if:

- It duplicates a sibling-domain pattern that could move to a shared base (`pipelines/base.py`, `domains/_base/`, or a generic Jinja template).
- It mixes concerns the rest of the codebase keeps separate (translate inside store, extract inside pipeline).
- It hard-codes data that belongs in YAML.

A file is **kept as-is** only if it has a clear caller, a clean concern, and no obvious twin.

## Per-file output

Each file gets one row in the relevant domain doc:

| Field | What goes here |
|---|---|
| **File** | `[path](path)` |
| **Role in the pipeline** | One phrase — *"vendor extractor"*, *"DB upsert"*, *"sched entry"*, etc. |
| **Callers** | Where it's used (file:line if non-obvious) |
| **Stale signal** | Which rule above (if any) it hits |
| **Verdict** | `keep` / `merge:X` / `move:Y` / `delete` / `rewrite` |
| **Action** | One sentence of follow-up, or `—` |

Domain docs land under `docs/admin/development/repo_review/{domain}.md`.

---

# Domain areas

Each domain section below: **(a) how it functions today**, **(b) the file inventory grouped by role in the pipeline**, **(c) the specific stale-code suspects to interrogate first.**

## 1. FX — spot, OHLC, rate (with forwards), vol

### How it functions

Three fact tables, three vendor sources:
- `fx.fact_ohlc` — daily/hourly OHLC. BidFX live + Citi historical. Older pipeline; pre-normalization.
- `fx.fact_fx_rate` — spot + tenor forwards (mid + fwd_points). Citi live + hourly + historical. **Newest** — already on the FK'd dim_currency_pair + dim_vendor + dim_frequency model.
- `fx.fact_vol` — implied vol surface (strike × tenor × type). Citi only.

Plus BBG mirror reads (`BBG_mirror\FX\`) for the new BBG-linked pipeline (`pipeline_rate_bbg.py`).

The three sub-pipelines share extractors / translators / stores but each has its own file. Naming is inconsistent (`rate_translate.py` vs `vol_translate.py` vs `clean_fx_fact_vol.py`).

### File inventory by role

**Schema (DB + pydantic):**
- [src/imdr/models/fx.py](src/imdr/models/fx.py), [fx_ohlc.py](src/imdr/models/fx_ohlc.py), [fx_rate.py](src/imdr/models/fx_rate.py), [fx_vol.py](src/imdr/models/fx_rate.py)
- [src/imdr/schemas/fx.py](src/imdr/schemas/fx.py), [fx_ohlc.py](src/imdr/schemas/fx_ohlc.py), [fx_rate.py](src/imdr/schemas/fx_rate.py), [fx_vol.py](src/imdr/schemas/fx_vol.py)

**Universe:**
- [src/imdr/universe/fx.py](src/imdr/universe/fx.py) / [fx.yml](src/imdr/universe/fx.yml)

**Vendor extract:**
- [domains/fx/extractors.py](src/imdr/domains/fx/extractors.py) — base + OHLC
- [domains/fx/extractors_rate.py](src/imdr/domains/fx/extractors_rate.py) — rate (spot+fwd)
- [domains/fx/extractors_vol.py](src/imdr/domains/fx/extractors_vol.py) — vol

**Translate (vendor → IMDR):**
- [domains/fx/rate_translate.py](src/imdr/domains/fx/rate_translate.py)
- [domains/fx/vol_translate.py](src/imdr/domains/fx/vol_translate.py)
- *(OHLC translate inside `extractors.py`? — verify.)*

**Store (IMDR → DB):**
- [domains/fx/store_rate.py](src/imdr/domains/fx/store_rate.py)
- [domains/fx/store_vol.py](src/imdr/domains/fx/store_vol.py)
- *(no `store_ohlc.py` — verify where OHLC upserts happen.)*

**Read / repository:**
- [domains/fx/repository.py](src/imdr/domains/fx/repository.py)
- [domains/fx/repository_rate.py](src/imdr/domains/fx/repository_rate.py)
- [domains/fx/repository_vol.py](src/imdr/domains/fx/repository_vol.py)

**Quality / cleaning:**
- [domains/fx/clean_fx_fact_fx_rate.py](src/imdr/domains/fx/clean_fx_fact_fx_rate.py)
- [domains/fx/clean_fx_fact_ohlc.py](src/imdr/domains/fx/clean_fx_fact_ohlc.py)
- [domains/fx/clean_fx_fact_vol.py](src/imdr/domains/fx/clean_fx_fact_vol.py)
- [domains/fx/coverage.py](src/imdr/domains/fx/coverage.py)

**Pipeline orchestration:**
- [domains/fx/pipeline.py](src/imdr/domains/fx/pipeline.py)
- [domains/fx/pipeline_ohlc.py](src/imdr/domains/fx/pipeline_ohlc.py)
- [domains/fx/pipeline_rate.py](src/imdr/domains/fx/pipeline_rate.py)
- [domains/fx/pipeline_vol.py](src/imdr/domains/fx/pipeline_vol.py)
- [domains/fx/ingest.py](src/imdr/domains/fx/ingest.py)
- [domains/fx/time_utils.py](src/imdr/domains/fx/time_utils.py)

**CLI entry / scripts:** all of `scripts/fx/{bidfx,citi,clean}/` — 14 files

**Notifications:**
- [formatters/fx_ingest.py](src/imdr/notifications/formatters/fx_ingest.py) + [template](src/imdr/notifications/templates/fx_ingest.html)
- [formatters/fx_rate_ingest.py](src/imdr/notifications/formatters/fx_rate_ingest.py) + [template](src/imdr/notifications/templates/fx_rate_ingest.html)
- [formatters/fx_vol_ingest.py](src/imdr/notifications/formatters/fx_vol_ingest.py) + [template](src/imdr/notifications/templates/fx_vol_ingest.html)

**Tests:** `test_fx_ohlc_model.py`, `test_fx_pipeline.py`, `test_fx_rate_schema.py`, `test_fx_rate_translate.py`, `test_fx_rate_universe.py`, `test_fx_universe.py`

**Docs:** [docs/fx/fx_data_reference.md](../../fx/fx_data_reference.md) + [docs/admin/fx/](../fx/) — 9 admin files

**Migrations:** 004 (dim_currency_pair), 005 (fact_vol), 024 (fact_fx_rate), 027 (obs_ts), 028 (onshore EM), 043 (country), 022 (skew currency)

### Stale-code suspects

- `ingest.py` + `pipeline.py` — leftover from before the per-fact pipeline split? Verify callers.
- `repository.py` (no suffix) — same.
- `time_utils.py` — should this be at `src/imdr/utils/` or `src/imdr/market_calendar/`?
- Three near-identical `clean_fx_fact_*.py` and three `clean_*.py` script entries — collapse into one parameterized cleaner.
- Naming: `rate_translate.py` vs `vol_translate.py` — pick one form, apply across domains.

## 2. Rates — curves, benchmarks, swaption vol, swaption skew

### How it functions

Largest domain. Four sub-pipelines on three fact tables:
- `rates.fact_observation` — curve observations (SOV_CMT, swaps, basis, xccy, TSY, etc.); the big one. Citi + BBG.
- `rates.fact_bench_rate` — central-bank policy / benchmark rates (BENCH_RATES). Citi.
- `rates.fact_swaption_vol` — 38K tags/day, 3D cube (option_expiry × swap_tenor × qualifier). Citi.
- `rates.fact_swaption_skew` — Barclays SKEW Excel via email-linked vendor.

Plus dim tables `dim_curve`, `dim_vol_surface`, `dim_skew_surface`, `dim_central_bank` (all country-FK'd after Phase D).

There's a discovery layer (`discovery.py`) and a cache layer (`cache.py`) that had a silent-drop incident on 2026-04-14.

### File inventory by role

**Schema:**
- Models: [rates.py](src/imdr/models/rates.py), [rates_bench.py](src/imdr/models/rates_bench.py), [rates_skew.py](src/imdr/models/rates_skew.py), [rates_vol.py](src/imdr/models/rates_vol.py)
- Schemas (pydantic): [rates.py](src/imdr/schemas/rates.py), [rates_bench.py](src/imdr/schemas/rates_bench.py), [rates_skew.py](src/imdr/schemas/rates_skew.py), [rates_vol.py](src/imdr/schemas/rates_vol.py)
- **Plus** [domains/rates/schema.py](src/imdr/domains/rates/schema.py) — interrogate: duplicate of `schemas/rates*.py`?

**Universe:** [rates.py](src/imdr/universe/rates.py) / [rates.yml](src/imdr/universe/rates.yml)

**Vendor extract:**
- [extractors.py](src/imdr/domains/rates/extractors.py)
- [extractors_vol.py](src/imdr/domains/rates/extractors_vol.py)
- [discovery.py](src/imdr/domains/rates/discovery.py)
- [cache.py](src/imdr/domains/rates/cache.py) — 2026-04-14 incident; flag for special review

**Translate:**
- [translate.py](src/imdr/domains/rates/translate.py) (main curve)
- [vol_translate.py](src/imdr/domains/rates/vol_translate.py)
- [skew_translate.py](src/imdr/domains/rates/skew_translate.py)
- [utils.py](src/imdr/domains/rates/utils.py) — `curve_entry_to_create`

**Store:**
- [store.py](src/imdr/domains/rates/store.py)
- [store_vol.py](src/imdr/domains/rates/store_vol.py)
- [store_skew.py](src/imdr/domains/rates/store_skew.py)

**Read / repository:**
- [repository.py](src/imdr/domains/rates/repository.py)
- [repository_vol.py](src/imdr/domains/rates/repository_vol.py)
- [repository_skew.py](src/imdr/domains/rates/repository_skew.py)

**Quality / cleaning:**
- [clean_rates_fact_observation.py](src/imdr/domains/rates/clean_rates_fact_observation.py)
- [coverage.py](src/imdr/domains/rates/coverage.py)

**Pipeline:**
- [pipeline.py](src/imdr/domains/rates/pipeline.py)
- [pipeline_bench.py](src/imdr/domains/rates/pipeline_bench.py)
- [pipeline_vol.py](src/imdr/domains/rates/pipeline_vol.py)
- [pipeline_skew.py](src/imdr/domains/rates/pipeline_skew.py)

**Scripts:** all of `scripts/rates/{barclays,citi,clean}/` — 11 files

**Notifications:** 4 formatter+template pairs (`rates_ingest`, `rates_bench_ingest`, `rates_vol_ingest`, `rates_skew_ingest`)

**Tests:** 9 files (`test_rates_*`) — one per concern (bench, cache, discovery, models, schema, store, translate, universe, utils)

**Docs:** [docs/rates/rates_data_reference.md](../../rates/rates_data_reference.md) + [docs/admin/rates/](../rates/) — 10 admin files

**Migrations:** 007 (vol), 017 (skew), 020 (bench), 022 (skew currency), 025 (frequency_id), 029 (vendor_id), 030 (basis CK), 044/045/046/047 (country)

### Stale-code suspects

- [domains/rates/schema.py](src/imdr/domains/rates/schema.py) — almost certainly redundant with `src/imdr/schemas/rates*.py`. Pick one location.
- [cache.py](src/imdr/domains/rates/cache.py) hourly empty-combo cache is disabled per commit `d625e8d`; revisit whether the code path should be deleted or kept dormant.
- Rates exploration docs (4+ files) — fold into one `citi_velocity_rates_full.md` and delete the per-subcat writeups once content is merged.
- Cached `data/cache/rates/*_tree.json` — confirm they're git-ignored, not tracked.

## 3. Equity — index level, VIX family

### How it functions

Two narrow sub-pipelines:
- `equity.fact_index_level` — 24 global index tickers, daily.
- `equity.fact_vix` — VIX / VIX3M / VIX9D / VVIX / VXN.

Citi-only. Smallest domain by tag count.

### File inventory by role

- Models/schemas: [models/equity.py](src/imdr/models/equity.py), [schemas/equity.py](src/imdr/schemas/equity.py)
- Universe: [equity.py](src/imdr/universe/equity.py) / [equity.yml](src/imdr/universe/equity.yml)
- Extract: [extractors.py](src/imdr/domains/equity/extractors.py)
- Translate: [translate_index.py](src/imdr/domains/equity/translate_index.py) *(no vix translate — verify)*
- Store: [store_index.py](src/imdr/domains/equity/store_index.py), [store_vix.py](src/imdr/domains/equity/store_vix.py)
- Read: [repository.py](src/imdr/domains/equity/repository.py)
- Clean: [clean_index.py](src/imdr/domains/equity/clean_index.py), [coverage.py](src/imdr/domains/equity/coverage.py)
- Pipeline: [pipeline_index.py](src/imdr/domains/equity/pipeline_index.py), [pipeline_vix.py](src/imdr/domains/equity/pipeline_vix.py)
- Scripts: `scripts/equity/{citi,clean}/` — 5 files
- Notifications: [formatters/equity_ingest.py](src/imdr/notifications/formatters/equity_ingest.py) + [template](src/imdr/notifications/templates/equity_ingest.html)
- Tests: `test_equity_schema.py`, `test_equity_translate.py`, `test_equity_universe.py`
- Docs: [equity.md](docs/admin/vendors/citi/exploration/equity.md) + `.gitkeep`
- Migrations: 015 (schema), 016 (market_code), 035 (US equity bridge), 048 (country)

### Stale-code suspects

- No VIX-specific translate / coverage / clean — either inherited from index or genuinely missing (gap, not stale).
- `docs/equity/.gitkeep` — remove now that real docs exist.
- `explore_equity_indices.py` + `explore_equity_indices2.py` in `scripts/explore/` — clear duplication.

## 4. Commodities — spot, EIA, implied vol, forecast

### How it functions

Smallest tag count (1,202) but most product types:
- `cmdty.fact_spot` — 3 products (front-month proxies).
- `cmdty.fact_eia_weekly` — 67 EIA petroleum series × PADD regions.
- `cmdty.fact_implied_vol` — 5 products (Brent, WTI, XAU, XAG, XPT) with full vol surfaces.
- *Forecast* discovered in catalog but **not** ingested.

Citi-only.

### File inventory by role

- Models/schemas: [models/commodities.py](src/imdr/models/commodities.py), [schemas/commodities.py](src/imdr/schemas/commodities.py)
- Universe: [commodities.py](src/imdr/universe/commodities.py) / [commodities.yml](src/imdr/universe/commodities.yml)
- Extract: [extractors.py](src/imdr/domains/commodities/extractors.py)
- Translate (one per fact): [translate_eia.py](src/imdr/domains/commodities/translate_eia.py), [translate_spot.py](src/imdr/domains/commodities/translate_spot.py), [translate_vol.py](src/imdr/domains/commodities/translate_vol.py)
- Store: [store_eia.py](src/imdr/domains/commodities/store_eia.py), [store_spot.py](src/imdr/domains/commodities/store_spot.py), [store_vol.py](src/imdr/domains/commodities/store_vol.py)
- Read: [repository.py](src/imdr/domains/commodities/repository.py)
- Clean: [clean_implied_vol.py](src/imdr/domains/commodities/clean_implied_vol.py), [coverage.py](src/imdr/domains/commodities/coverage.py)
- Pipeline: [pipeline_eia.py](src/imdr/domains/commodities/pipeline_eia.py), [pipeline_spot.py](src/imdr/domains/commodities/pipeline_spot.py), [pipeline_vol.py](src/imdr/domains/commodities/pipeline_vol.py)
- Scripts: `scripts/commodities/{citi,clean}/` — 5 files
- Notifications: [formatters/cmdty_ingest.py](src/imdr/notifications/formatters/cmdty_ingest.py) + [template](src/imdr/notifications/templates/cmdty_ingest.html)
- Tests: `test_cmdty_translate.py`, `test_cmdty_universe.py`
- Docs: [commodities.md](docs/admin/vendors/citi/exploration/commodities.md) + `.gitkeep`
- Migrations: 013 (schema), 014 (fact tables)

### Stale-code suspects

- No EIA / spot cleaning — confirm intentional or a gap.
- Cached `data/cache/commodities/commodities_deep.json` + `scripts/explore/explore_commodities.py` — per memory, **don't re-run**. Move script to `playground/`, delete from `scripts/explore/`.

## 5. Calendar — markets, holidays, CB events, trading days

### How it functions

Cross-domain dimension. Drives `last_business_day`, settlement offsets, NDF / CNH handling, hourly skip logic.

- `calendar.dim_market` — 50 markets, YAML-seeded.
- `calendar.dim_trading_day` — pre-computed per market.
- `calendar.cb_events` — central-bank meeting dates, Bloomberg Excel + scraper fallback.
- `calendar.market_holidays` — holiday calendar per market (migration 031).

Module: `src/imdr/market_calendar/`. Heavy refactor just landed (country-anchor restructure, migrations 034–049).

### File inventory by role

- Module: `__init__.py`, [calendar.py](src/imdr/market_calendar/calendar.py), [holidays.py](src/imdr/market_calendar/holidays.py), [imm.py](src/imdr/market_calendar/imm.py), [markets.py](src/imdr/market_calendar/markets.py), [events.py](src/imdr/market_calendar/events.py)
- CB events: [cb_events.py](src/imdr/market_calendar/cb_events.py), [cb_scrapers.py](src/imdr/market_calendar/cb_scrapers.py)
- YAML config: [markets.yml](src/imdr/market_calendar/markets.yml), [events.yml](src/imdr/market_calendar/events.yml)
- Model: [models/calendar.py](src/imdr/models/calendar.py)
- Scripts: [import_cb_events.py](scripts/calendar/import_cb_events.py), [refresh_cb_events.py](scripts/calendar/refresh_cb_events.py), [populate_asia_em_2026.py](scripts/calendar/populate_asia_em_2026.py)
- Already-deleted scripts (working tree): `backfill_market_codes.py`, `seed_dim_market.py`, `seed_trading_days.py` — confirm commit
- Tests: [test_calendar.py](tests/unit/test_calendar.py), [test_market_calendar.py](tests/unit/test_market_calendar.py)
- Docs: [docs/admin/calendar/calendar_module.md](../calendar/calendar_module.md), [cb_events_refresh.md](../calendar/cb_events_refresh.md), [docs/admin/fx/calendar_integration.md](../fx/calendar_integration.md), [docs/admin/rates/calendar_integration.md](../rates/calendar_integration.md)
- Migrations: 008, 009, 010, 011, 012, 026, 031, 034–049 (country-anchor)

### Stale-code suspects

- Two test files (`test_calendar.py` + `test_market_calendar.py`) — verify they don't overlap.
- [docs/admin/development/last_business_day_call_sites.md](docs/admin/development/last_business_day_call_sites.md) — still open? close out.
- Phase D country-anchor restructure had 16 migrations; check if any of the early ones (034, 035, 036, 038) were superseded.

## 6. Vendors framework — generic acquisition

### How it functions

A small framework for non-Citi feeds (email-linked downloads, SFTP, web scraping, HTTP polling). Only one feed is implemented: **Barclays SKEW** via Outlook + Playwright. Three of the four acquirer modules are scaffold-only.

### File inventory by role

- Framework: [base.py](src/imdr/vendors/base.py), [registry.py](src/imdr/vendors/registry.py), [runner.py](src/imdr/vendors/runner.py), [credentials.py](src/imdr/vendors/credentials.py), [exceptions.py](src/imdr/vendors/exceptions.py), [helpers.py](src/imdr/vendors/helpers.py)
- Acquirers: [email_linked.py](src/imdr/vendors/acquirers/email_linked.py) ✅, [http_poll.py](src/imdr/vendors/acquirers/http_poll.py) 💤, [sftp.py](src/imdr/vendors/acquirers/sftp.py) 💤, [web_scrape.py](src/imdr/vendors/acquirers/web_scrape.py) 💤
- Sessions: [browser.py](src/imdr/vendors/sessions/browser.py), [outlook.py](src/imdr/vendors/sessions/outlook.py)
- Specs: [barclays_skew.py](src/imdr/vendors/specs/barclays_skew.py) (+ untracked `_bbg_factory.py` per memory — verify)
- CLI: [scripts/run_vendor_feed.py](scripts/run_vendor_feed.py)
- Tests: `tests/unit/test_vendors/` — 5 files (base, credentials, email_linked, registry, runner)
- Docs: [docs/admin/vendors/](docs/admin/vendors/) — 12 files (incl. stubs for `web_scraping.md`, `sftp.md`, `http_poll.md` matching the empty acquirers)

### Stale-code suspects

- Three scaffold acquirers (`http_poll.py`, `sftp.py`, `web_scrape.py`) and their docs — **delete now** and re-add when there's a real feed needing them. Speculative scaffolding is the textbook stale-code rule.
- BBG-share integration is documented under `docs/admin/vendors/bbg/` but lives in `src/imdr/domains/fx/pipeline_rate_bbg.py` (per memory) — verify where the actual BBG vendor spec lives, and whether the `bbg/` docs match the code.

## 7. Cross-cutting infrastructure

### 7a. Connectors / data access

- [connectors/mssql.py](src/imdr/connectors/mssql.py) — engine, session factory
- [connectors/reader.py](src/imdr/connectors/reader.py) — read-side with `_validate_identifier`
- [connectors/bulk.py](src/imdr/connectors/bulk.py) — MERGE / upsert helpers
- [connectors/citi_velocity.py](src/imdr/connectors/citi_velocity.py) — Citi API client
- [connectors/citi_helpers.py](src/imdr/connectors/citi_helpers.py) — tag building, etc.
- [connectors/citi_quota.py](src/imdr/connectors/citi_quota.py) — quota tracking
- [connectors/http.py](src/imdr/connectors/http.py) — generic HTTP. **Suspect** — is anything still using this once `citi_velocity.py` exists?
- [data_access.py](src/imdr/data_access.py) — top-level read API. Possible merge with `reader.py`.
- [queries/fx.py](src/imdr/queries/fx.py) — why only fx? Likely candidate to fold into `data_access.py`.

### 7b. Pipeline base classes

- [pipelines/base.py](src/imdr/pipelines/base.py) — `BasePipeline` ABC, audit/email plumbing
- [pipelines/extractors.py](src/imdr/pipelines/extractors.py) — generic extractor base
- [models/audit.py](src/imdr/models/audit.py) — `pipeline_runs` table + `RunStatus`
- [config/pipeline_config.py](src/imdr/config/pipeline_config.py) — `fq_name`, registry helpers
- [config/pipelines.yml](src/imdr/config/pipelines.yml) — every pipeline configured here; audit for dead entries
- [config/settings.py](src/imdr/config/settings.py) — pydantic-settings; audit unused env keys

### 7c. Healthchecks

- [healthchecks/__init__.py](src/imdr/healthchecks/__init__.py), [base.py](src/imdr/healthchecks/base.py), [checks.py](src/imdr/healthchecks/checks.py) — framework
- [healthchecks/quality.py](src/imdr/healthchecks/quality.py) — `CompositeRangeCheck`, `RobustStatisticalOutlierCheck`, etc.
- [healthchecks/anomaly.py](src/imdr/healthchecks/anomaly.py) — has F841 dead vars (filed)
- [healthchecks/cleaning.py](src/imdr/healthchecks/cleaning.py), [clean_cli.py](src/imdr/healthchecks/clean_cli.py) — cleaning framework
- [healthchecks/staleness.py](src/imdr/healthchecks/staleness.py)
- [healthchecks/dashboard.py](src/imdr/healthchecks/dashboard.py)
- [healthchecks/reporter.py](src/imdr/healthchecks/reporter.py) — vs [reporting/reporter.py](src/imdr/reporting/reporter.py)? **Strong dup suspect.**
- Tests: `test_healthchecks.py`, `test_cleaning.py`, `test_quality_robust.py`, `test_staleness.py`

### 7d. Reporting

- [reporting/reporter.py](src/imdr/reporting/reporter.py)
- [reporting/run_report.py](src/imdr/reporting/run_report.py)
- Tests: `test_reporter.py`, `test_run_report.py`
- Possible merge target with `healthchecks/reporter.py`.

### 7e. Notifications

Biggest consolidation opportunity in the repo.

- Email plumbing: [email.py](src/imdr/notifications/email.py)
- Base formatter: [formatters/base.py](src/imdr/notifications/formatters/base.py)
- **11 near-identical `*_ingest` pairs** (formatter + template):
  - fx, fx_rate, fx_vol, rates, rates_bench, rates_vol, rates_skew, equity, cmdty
- **5 alert formatters/templates**: `anomaly_alert`, `staleness_alert`, `vendor_fetch_failure`, `weekly_dashboard`

**Hypothesis**: 9 `*_ingest` pairs collapse to 1 Jinja template + 1 formatter parameterized by domain context. Saves 16 files.

### 7f. Scheduling

- [scripts/imdr_daily.py](scripts/imdr_daily.py) — 95% of pipelines
- [scripts/imdr_hourly.py](scripts/imdr_hourly.py) — FX rate + rates hourly
- [scripts/imdr_weekly.py](scripts/imdr_weekly.py), [imdr_monthly.py](scripts/imdr_monthly.py), [imdr_quarterly.py](scripts/imdr_quarterly.py) — confirm each has live work
- [scripts/imdr_retry.py](scripts/imdr_retry.py)
- [scripts/imdr_clean.py](scripts/imdr_clean.py)
- [scripts/imdr_staleness_check.py](scripts/imdr_staleness_check.py)
- [scripts/imdr_health_dashboard.py](scripts/imdr_health_dashboard.py)
- [scripts/cleanup_old_data.py](scripts/cleanup_old_data.py)
- [scripts/run_pipeline.py](scripts/run_pipeline.py) — generic runner with `PIPELINE_REGISTRY`

### 7g. MCP server

- [mcp/server.py](mcp/server.py) — read-only DB MCP. Working-tree changes pending review.
- [.mcp.json](.mcp.json)
- [docs/admin/mcp.md](docs/admin/mcp.md)
- [docs/claude_desktop/](docs/claude_desktop/) — MCPB bundle scaffolding

### 7h. Models / schemas overlap

14 SQLAlchemy models in `src/imdr/models/`, 13 pydantic schemas in `src/imdr/schemas/`. Almost 1:1. Decide:
- Keep both (current) — full type independence, double the maintenance.
- Generate one from the other (e.g., `sqlmodel`, or pydantic `from_attributes`) — single source of truth.

Done as a single phase covering all 27 files.

### 7i. Universe loaders

[universe/base.py](src/imdr/universe/base.py) + 4 domain pairs (`.py` + `.yml`). Lean check: is `base.py` actually used by all 4, or does each domain re-implement loading?

### 7j. Utilities

- [utils/logging.py](src/imdr/utils/logging.py) — only file in `utils/`. Possibly migrate other "utils-ish" code (e.g., `domains/fx/time_utils.py`) here.

## 8. Exploration code (stale by default)

Per project rule **"PLAYGROUND-ONLY FOR EXPLORATION"**, `scripts/explore/` should not exist. 20 files live there today. For each:

1. Extract any insight not already in docs.
2. Move to `playground/` if there's a future re-run case.
3. **Delete otherwise.**

Candidates to delete immediately (insights cached + documented per memory):
- `explore_commodities.py` — results in `data/cache/commodities/commodities_deep.json`, doc in [commodities_exploration.md](docs/admin/development/...) (memory pointer)
- `explore_equity.py`, `explore_equity_indices.py`, `explore_equity_indices2.py` — equity deep dive cached
- `explore_fx_forward.py`, `explore_fx_vol.py`, `probe_fx_spot.py`, `probe_fwd_tags.py` — FX deep dives cached
- `explore_rates_categories.py`, `explore_rates_vol.py`, `explore_other_categories.py` — rates deep dives cached
- `probe_bbg_fx.py` — already removed on working tree
- `probe_bidfx_*.py` (3 files) — BidFX exploration, results in docs
- `probe_citi_quota.py` — superseded by `connectors/citi_quota.py`
- `probe_forward_rates.py`, `probe_rates_citi_hourly.py`, `probe_usd_stale_tags.py` — discovery work, done

That's ~20 deletions if the audit confirms the cached docs are sufficient.

## 9. Migrations — 49 files

Append-only, but a per-file pass should record: *did this migration's effect survive, or did a later migration undo it?* Specific add → drop → re-add suspects from the sequence:

- 036 `drop_exchange_calendars_data.sql` — supersedes earlier exchange-calendars work? trace.
- 037–048 Phase D country-anchor — 12 migrations in tight sequence; verify none was rolled back mid-flight.
- 041 `drop_calendar_segment_remnant.sql` — leftover from an earlier migration.

Goal isn't to rewrite history; it's to record "current schema state per table" so future devs don't have to walk all 49 files.

## 10. Tests — 46 files

Per-file check: (a) does the module under test still exist, (b) does the test still pass, (c) is the test covering today's behavior or yesterday's?

Particular suspects:
- `test_config.py` — already skipped due to ODBC driver mismatch. Either fix or delete.
- `tests/integration/` — only `__init__.py`. Decide: build out or delete.

## 11. Docs — 80 files

Per-file check: does the doc still describe current state? Phase D restructure invalidated several.

Specific cleanup targets:
- 4 `.gitkeep` files in domain-doc folders that now have real docs → delete the `.gitkeep`s.
- 4+ rates exploration docs (`rates_sov_cmt.md`, `rates_xccy_ois.md`, `rates_ois_meeting.md`, `rates_inflation.md`) under [`docs/admin/vendors/citi/exploration/`](docs/admin/vendors/citi/exploration/) — fold into [`rates_full.md`](docs/admin/vendors/citi/exploration/rates_full.md), delete the per-subcat files.
- `docs/admin/vendors/{web_scraping,sftp,http_poll}.md` — stubs matching scaffold-only acquirers; delete with the code.
- `docs/admin/development/` — 11 dev-task docs. Each gets a status pass (`active` / `done` / `dropped`). Done ones move to a `completed/` subfolder or delete.
- [README.md](README.md) — 6 bytes. Write a real one or delete.
- [arjun_notes.txt](arjun_notes.txt), [setup.txt](setup.txt) — scratch files in repo root. Move or delete.

---

# Execution plan — five stages, twenty-one phases

The work is organized into **five stages**. Each stage has a single character — discovery, deletion, consolidation, per-domain trim, final sweep — and the phases inside it share preconditions, risk profile, and the kind of review they need. The stages run sequentially; phases inside a stage can mostly run in parallel.

Every phase below carries the same six fields so the plan is operable: **Goal · Depends on · Files in scope · Actions · Deliverable · Done when · Risk · Effort.**

Effort uses t-shirt sizes: **S** ≤ ½ day, **M** ≤ 1 day, **L** ≤ 2 days, **XL** > 2 days.

Risk uses **low / med / high** based on blast radius if the change is wrong.

---

## Stage A — Discovery & baseline *(no production code changes)*

The lean pass is destructive by design; before touching anything we capture today's state so we can prove later that we didn't break it.

### Phase A1 — Symbol callgraph & dead-symbol report
- **Goal**: produce a machine-readable map of every public symbol in `src/imdr/` and `scripts/` and every place it's referenced. Anything with zero references becomes a Stage B candidate.
- **Depends on**: nothing.
- **Files in scope**: read-only walk of 432 files.
- **Actions**:
  - Run a Python AST pass that lists each module's top-level defs/classes.
  - `rg` each symbol across the repo; record callers.
  - Output `data/repo_review/callgraph.json` + a markdown view of unreferenced symbols.
- **Deliverable**: `docs/admin/development/repo_review/A1_callgraph.md`
- **Done when**: every `src/imdr/**/*.py` and `scripts/**/*.py` symbol has a callers count.
- **Risk**: low (read-only).
- **Effort**: M.

### Phase A2 — Test & lint baseline
- **Goal**: pin today's green state so we can detect regressions in Stages B–E.
- **Depends on**: nothing.
- **Files in scope**: `tests/`, `pyproject.toml`.
- **Actions**:
  - Run full `pytest tests/unit/` (excluding `test_config.py`); record passing count + duration.
  - Run `ruff check src/ scripts/ --select F` and record the 33 findings + their locations.
  - Run `ruff check src/ scripts/` (all rules) and snapshot.
- **Deliverable**: `docs/admin/development/repo_review/A2_baseline.md` (counts, durations, ruff hash).
- **Done when**: numbers committed; CI / local repro documented.
- **Risk**: low.
- **Effort**: S.

### Phase A3 — Live-schema snapshot vs migrations
- **Goal**: prove that the 49 migrations on disk match what's actually in the IMDR database. Anything in migrations but not in DB → schema rot. Anything in DB but not in migrations → undocumented drift.
- **Depends on**: nothing.
- **Files in scope**: `migrations/*.sql` (49 files) + DB via `mcp__imdr-db__list_tables` / `describe_table`.
- **Actions**:
  - List all tables/columns via MCP read-only.
  - Replay migrations in dry-run mode (parser-only, no DB writes) to compute the *intended* schema.
  - Diff the two; flag every mismatch.
- **Deliverable**: `docs/admin/development/repo_review/A3_schema_drift.md`
- **Done when**: every table is `match` / `drift:added` / `drift:dropped` / `rot:never-applied`.
- **Risk**: low (read-only MCP).
- **Effort**: M.

### Phase A4 — `pipelines.yml` liveness map
- **Goal**: prove every entry in `pipelines.yml` is reached by a scheduler / runner; flag the dead ones.
- **Depends on**: A1.
- **Files in scope**: [`config/pipelines.yml`](src/imdr/config/pipelines.yml), all `scripts/imdr_*.py` + `run_pipeline.py`.
- **Actions**: trace each yaml key → consumer; mark `live` / `dead`.
- **Deliverable**: `docs/admin/development/repo_review/A4_pipeline_liveness.md`
- **Risk**: low.
- **Effort**: S.

---

## Stage B — Safe deletions *(high confidence, no inter-dependencies)*

Everything here is a file we expect to delete outright. Each phase ships an open-and-shut PR: review the punch list, run the test baseline from A2, confirm green, merge.

### Phase B1 — Exploration purge (`scripts/explore/` → `playground/` or delete)
- **Goal**: enforce the **PLAYGROUND-ONLY FOR EXPLORATION** rule. ~20 files.
- **Depends on**: A1 (to know nothing imports them).
- **Files in scope**: all of `scripts/explore/`.
- **Actions**: for each file — confirm cached results exist in `data/cache/` and writeup exists in `docs/`; if yes → delete; if maybe-needed → move to `playground/`.
- **Deliverable**: `docs/admin/development/repo_review/B1_explore_purge.md`
- **Done when**: `scripts/explore/` directory removed; A2 baseline still green.
- **Risk**: low — these are one-shots not invoked by any scheduler.
- **Effort**: S.

### Phase B2 — Vendor framework scaffold purge
- **Goal**: remove three unused acquirers (`http_poll.py`, `sftp.py`, `web_scrape.py`) + matching docs. Re-add when a real feed needs them.
- **Depends on**: A1 (confirm zero callers).
- **Files in scope**: 3 `src/imdr/vendors/acquirers/*.py` + 3 `docs/admin/vendors/{web_scraping,sftp,http_poll}.md` + any `__init__` re-exports.
- **Actions**: delete files; clean `vendors/acquirers/__init__.py`; update [vendors/index.md](docs/admin/vendors/index.md).
- **Deliverable**: `docs/admin/development/repo_review/B2_vendor_scaffolds.md`
- **Done when**: tests still green; `run_vendor_feed barclays_skew` still works end-to-end.
- **Risk**: low.
- **Effort**: S.

### Phase B3 — Placeholder & scratch purge
- **Goal**: kill `.gitkeep`s in folders that now have content, empty/stub markdowns, repo-root scratch.
- **Depends on**: A1.
- **Files in scope**: `docs/{commodities,credit,equity,macro,rates,shared}/.gitkeep`, [README.md](README.md) (6 bytes), [arjun_notes.txt](arjun_notes.txt), [setup.txt](setup.txt), any zero-content `__init__.py` outside packages that need them.
- **Actions**: delete each, or replace `README.md` with a real one-pager if we want one.
- **Deliverable**: `docs/admin/development/repo_review/B3_placeholders.md`
- **Risk**: low.
- **Effort**: S.

### Phase B4 — Dead `pipelines.yml` / `settings.py` entries
- **Goal**: trim dead config that confuses readers.
- **Depends on**: A4.
- **Files in scope**: [`pipelines.yml`](src/imdr/config/pipelines.yml), [`settings.py`](src/imdr/config/settings.py), [`.env.example`](.env.example).
- **Actions**: drop yaml keys flagged dead in A4; remove env vars referenced nowhere in code.
- **Deliverable**: `docs/admin/development/repo_review/B4_dead_config.md`
- **Risk**: med (a removed setting that's actually live in `.env` would silently change behavior — diff `.env.example` vs grep of `settings.X` carefully).
- **Effort**: S.

### Phase B5 — Stale dev-task docs status pass
- **Goal**: every doc in `docs/admin/development/` gets `Status: active | done | dropped`; done ones move to `completed/`.
- **Depends on**: nothing.
- **Files in scope**: 11 dev-task docs (this file included).
- **Deliverable**: each file edited in place; index of `done/` in `repo_review/B5_devtask_status.md`.
- **Risk**: low.
- **Effort**: S.

---

## Stage C — Cross-cutting consolidation *(repo-wide refactors)*

These touch many domains at once, so they precede Stage D. Each delivers a behavior-preserving merge or refactor — green tests are the only acceptance criterion.

### Phase C1 — `reporting/` vs `healthchecks/reporter.py` merge
- **Goal**: one reporter module. Strong dup suspect.
- **Depends on**: A1 (call sites), A2 (baseline).
- **Files in scope**: [reporting/reporter.py](src/imdr/reporting/reporter.py), [healthchecks/reporter.py](src/imdr/healthchecks/reporter.py), [reporting/run_report.py](src/imdr/reporting/run_report.py), `tests/unit/test_reporter.py`, `test_run_report.py`.
- **Actions**: diff the two; pick canonical location; redirect imports; delete the duplicate.
- **Deliverable**: `docs/admin/development/repo_review/C1_reporter_merge.md`
- **Done when**: A2 baseline green; only one `reporter.py` survives.
- **Risk**: med (reporter is invoked by every pipeline's post-run hook).
- **Effort**: M.

### Phase C2 — Connector / data-access consolidation
- **Goal**: collapse [http.py](src/imdr/connectors/http.py), [data_access.py](src/imdr/data_access.py), [queries/fx.py](src/imdr/queries/fx.py) into the right canonical seams. Pure read seam vs pure transport seam.
- **Depends on**: A1.
- **Files in scope**: above + [reader.py](src/imdr/connectors/reader.py).
- **Actions**: classify each helper as `read` (→ `data_access.py`), `transport` (→ `connectors/`), or `domain query` (→ domain repository); redirect imports.
- **Deliverable**: `docs/admin/development/repo_review/C2_connectors.md`
- **Risk**: med — touched by ~every pipeline.
- **Effort**: M.

### Phase C3 — Notifications consolidation
- **Goal**: 11 `*_ingest` formatter+template pairs → 1 generic Jinja template + 1 parametric formatter. Net delete ≈ 16 files.
- **Depends on**: A1, A2 baseline including snapshot tests on rendered HTML.
- **Files in scope**: 11 formatters + 11 templates + [formatters/base.py](src/imdr/notifications/formatters/base.py).
- **Actions**:
  - Capture rendered HTML for each pipeline as golden files (one-time).
  - Build a generic `ingest_email` formatter that takes a `domain_context` dict.
  - Replace each `*_ingest.py` with a thin call to the generic formatter.
  - Verify rendered HTML matches the golden files byte-for-byte (or with documented diff).
- **Deliverable**: `docs/admin/development/repo_review/C3_notifications.md`
- **Done when**: scheduler emails for one day's run look identical to pre-merge baseline.
- **Risk**: med — emails are user-visible.
- **Effort**: L.

### Phase C4 — `models/` ↔ `schemas/` single-source-of-truth decision
- **Goal**: stop maintaining 14 SQLAlchemy + 13 pydantic side-by-side. Pick one path (sqlmodel, pydantic `from_attributes`, codegen) and execute on one domain as a proof.
- **Depends on**: A1.
- **Files in scope**: all 27 model/schema files; one domain (recommend FX rate — newest, simplest) as the proof.
- **Actions**:
  - Write an ADR-style decision doc with pros/cons.
  - Apply to FX rate as pilot.
  - If pilot is clean, schedule per-domain rollout in Stage D.
- **Deliverable**: `docs/admin/development/repo_review/C4_models_schemas_decision.md` + pilot PR.
- **Risk**: high if forced repo-wide in one go — keep this phase as *decision + 1 pilot*; full rollout is per-domain in D.
- **Effort**: L (pilot only).

### Phase C5 — Domain base-class extraction
- **Goal**: lift the repeating `extract / translate / store / repository / clean / coverage / pipeline` skeleton into a shared base under `src/imdr/pipelines/base.py` or a new `src/imdr/domains/_base/`. Each domain ends up with ~30–40% less file count.
- **Depends on**: C1, C2 (so the base can use the canonical reporter + connectors).
- **Files in scope**: writes to `src/imdr/pipelines/` and a new `_base/` package. Domain files become subclasses in Stage D.
- **Actions**:
  - Identify the genuinely-shared shape (one pass across FX rate / rates curve / equity index — three pipelines that already work).
  - Define an `ABC` (or protocols) and minimal mixins; don't over-abstract.
  - Add tests for the base behavior.
- **Deliverable**: `docs/admin/development/repo_review/C5_base_extraction.md` + new base modules.
- **Risk**: high — easy to over-abstract. Cap scope by **only lifting what 3+ existing domains already share verbatim**.
- **Effort**: L.

---

## Stage D — Per-domain vertical trims *(one slice at a time)*

Each phase is a single domain's verticals slice: the file inventory section above tells you exactly which files. Stages C must land first because each domain phase will adopt the new base / canonical reporter / canonical notification path.

Every Stage D phase follows the same playbook:

1. Open the domain's section in this doc.
2. For each file, fill the verdict table (`keep / merge / move / delete / rewrite`).
3. Apply verdicts; keep tests green at each step.
4. Migrate the domain onto the new base (C5).
5. Migrate the domain onto the canonical notification path (C3).
6. If C4 went well, migrate one model/schema pair as a continuation of the pilot.
7. Update domain docs to reflect post-trim state.

### Phase D1 — FX
- **Files in scope**: ~20 in `src/imdr/domains/fx/` + 14 scripts + 3 notification pairs + 6 tests + 8 docs.
- **Specific suspects**: `ingest.py`, `pipeline.py` (no suffix), `repository.py` (no suffix), `time_utils.py` location, naming consistency (`rate_translate.py` vs `vol_translate.py`), three near-identical `clean_fx_fact_*.py`.
- **Deliverable**: `docs/admin/development/repo_review/D1_fx.md`
- **Risk**: med — FX rate is on the hot path (hourly + daily).
- **Effort**: L.

### Phase D2 — Rates
- **Files in scope**: ~20 in `src/imdr/domains/rates/` + 11 scripts + 4 notification pairs + 9 tests + 14 docs.
- **Specific suspects**: [domains/rates/schema.py](src/imdr/domains/rates/schema.py) (dup of `schemas/rates*`), `cache.py` post-disable, 4+ rates exploration docs → fold into one.
- **Deliverable**: `docs/admin/development/repo_review/D2_rates.md`
- **Risk**: high — largest domain; cache layer had a silent-drop incident; hot path daily + hourly.
- **Effort**: XL.

### Phase D3 — Equity
- **Files in scope**: ~10 in `src/imdr/domains/equity/` + 5 scripts + 1 notification pair + 3 tests + 1 doc.
- **Specific suspects**: missing VIX translate/clean/coverage (gap vs stale?), `explore_equity_indices2.py` duplicate.
- **Deliverable**: `docs/admin/development/repo_review/D3_equity.md`
- **Risk**: low.
- **Effort**: M.

### Phase D4 — Commodities
- **Files in scope**: ~13 in `src/imdr/domains/commodities/` + 5 scripts + 1 notification pair + 2 tests + 1 doc.
- **Specific suspects**: no EIA / spot cleaning (intentional?), forecast catalog discovered but not ingested.
- **Deliverable**: `docs/admin/development/repo_review/D4_commodities.md`
- **Risk**: low.
- **Effort**: M.

### Phase D5 — Calendar + market_calendar
- **Files in scope**: 10 in `src/imdr/market_calendar/` + 3 calendar scripts + 1 model + 2 tests + 4 docs + 16 migrations (037–049).
- **Specific suspects**: two test files possibly overlapping; Phase D country-anchor tail (any early migration superseded?); newly-opened [051_cb_events_drop_country_code.sql](migrations/051_cb_events_drop_country_code.sql) hints at further churn — fold into this phase's review.
- **Deliverable**: `docs/admin/development/repo_review/D5_calendar.md`
- **Risk**: med — calendar drives `last_business_day` across every pipeline.
- **Effort**: L.

### Phase D6 — Vendors framework cleanup *(post-B2)*
- **Files in scope**: remaining `src/imdr/vendors/` after B2 deletions + barclays_skew spec + sessions.
- **Specific suspects**: `_bbg_factory.py` (untracked per memory — investigate), `bbg/` docs vs actual BBG integration location.
- **Deliverable**: `docs/admin/development/repo_review/D6_vendors.md`
- **Risk**: low (B2 already did the deletions; this is cleanup).
- **Effort**: M.

---

## Stage E — Infrastructure & final sweep

### Phase E1 — Schedulers & `run_pipeline`
- **Goal**: every scheduler runs only live pipelines; every entry in `PIPELINE_REGISTRY` resolves.
- **Depends on**: A4, B4, all of Stage D.
- **Files in scope**: 12 top-level `scripts/imdr_*.py` + `run_pipeline.py` + `run_vendor_feed.py`.
- **Actions**: prune dead entries; verify each scheduler script's pipeline list against post-D state.
- **Deliverable**: `docs/admin/development/repo_review/E1_schedulers.md`
- **Risk**: med — a wrongly-removed scheduler entry = silent data outage.
- **Effort**: M.

### Phase E2 — Migrations annotation pass
- **Goal**: emit `docs/admin/schema_state.md` — per-table current column list with a pointer to the migrations that built it. Future devs read one file, not 49.
- **Depends on**: A3.
- **Files in scope**: 49 migrations + DB.
- **Actions**: per table, walk forward through migrations; record final state.
- **Deliverable**: `docs/admin/schema_state.md` + `repo_review/E2_migrations.md`
- **Risk**: low (doc-only).
- **Effort**: L.

### Phase E3 — Tests audit
- **Goal**: every kept `src/` file has a test or an explicit waiver.
- **Depends on**: all of Stage D.
- **Files in scope**: 46 tests + every `src/imdr/**/*.py` that survived D.
- **Actions**: map test → module; fill gaps with stubs or document the waiver in the relevant phase doc; resolve `test_config.py` (fix or delete); decide `tests/integration/`.
- **Deliverable**: `docs/admin/development/repo_review/E3_tests.md`
- **Risk**: low.
- **Effort**: L.

### Phase E4 — Docs audit
- **Goal**: every doc describes current state; exploration writeups folded; index files accurate.
- **Depends on**: all of Stage D + E2.
- **Files in scope**: 80 docs.
- **Actions**: fold 4+ rates exploration docs into one; verify cross-references; refresh `docs/admin/vendors/index.md`, `docs/admin/vendors/bbg/index.md`.
- **Deliverable**: `docs/admin/development/repo_review/E4_docs.md`
- **Risk**: low.
- **Effort**: M.

### Phase E5 — Ruff F-class zero
- **Goal**: 33 → 0 findings. Resolve as part of each touched phase; this is the sweep for whatever's left.
- **Depends on**: D1–D6.
- **Files in scope**: whatever ruff still flags.
- **Actions**: fix or annotate (`# noqa: F401  reason`).
- **Deliverable**: `docs/admin/development/repo_review/E5_ruff_zero.md`; updated [tech_debt_ruff_findings.md](tech_debt_ruff_findings.md) closed.
- **Risk**: low.
- **Effort**: S.

### Phase E6 — Synthesis & metrics
- **Goal**: prove we hit the lean target.
- **Depends on**: everything above.
- **Files in scope**: synthesis only.
- **Actions**: aggregate file counts before/after, ruff before/after, test count before/after, lines deleted, top-5 follow-ups.
- **Deliverable**: `docs/admin/development/repo_review/E6_synthesis.md`
- **Done when**: net file count ≤ 340 (≥ 20% reduction), zero F-class findings, A2 baseline test count ≥ original.
- **Risk**: low.
- **Effort**: S.

---

## Sequencing summary

```
A1 ─┬─ A2 ─┐
    │      │
A3 ─┤      ├──> B1 B2 B3 ── B4(<-A4)  B5
    │      │       (parallel deletions)
A4 ─┘      │                                  ┌── D1 ─┐
           │                                  ├── D2 ─┤
           └──> C1 ──> C5 ──┐                 ├── D3 ─┤
                C2 ─────────┤                 ├── D4 ─┼──> E1 ──> E2 ── E3 ── E4 ── E5 ── E6
                C3 ─────────┼──> (Stage D) ──>┤── D5 ─┤
                C4 (pilot) ─┘                 └── D6 ─┘
```

Stage A is read-only and can run in one sitting. Stage B is safe parallel PRs. Stage C is the riskiest *structural* work and must precede Stage D. Stage D phases can run in any order (or in parallel by different sessions) once C is done. Stage E is the wrap.

## Cross-cutting hypotheses to validate as we go

1. **Domain-symmetry collapse** — `extract / translate / store / repository / clean / coverage / pipeline` repeats 5×. Move common shape into `src/imdr/pipelines/base.py` or `src/imdr/domains/_base/`.
2. **Notifications collapse** — 11 ingest pairs → 1 generic.
3. **Models vs schemas** — single source of truth.
4. **Explore → playground migration** — enforce the project rule.
5. **`dim_vendor` 'bloomberg' vs 'BBG'** — tracked in [dim_vendor_cleanup.md](dim_vendor_cleanup.md).
6. **Country-anchor tail** — anything still using old market codes (per [country_anchor_restructure_progress.md](country_anchor_restructure_progress.md)).
7. **`pyproject.toml` deps** — cross-reference imports, flag unused.
8. **F-class ruff findings** — already on file in [tech_debt_ruff_findings.md](tech_debt_ruff_findings.md); fold into phase docs as we touch each file.
9. **Stale `__init__.py` re-exports** — surfaces drift as files are added/removed.
10. **Stale `pipelines.yml` entries** — every entry needs a live caller.

## Done criteria

- 16 phase docs exist; each closes with a count of files deleted / merged / kept.
- Net file count drops by **≥ 20%** (back-of-envelope target: 432 → ~340).
- Zero ruff F-class findings (the 33 in flight all resolved).
- Every kept `src/` file has at least one test or an explicit "no test needed because X" note in its phase doc.
- This file flips `Status: complete` only when phase 16 lands.
