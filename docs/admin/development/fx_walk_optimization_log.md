# FX Domain Walk — Optimization Log

- **Date opened**: 2026-05-15
- **Scope**: `src/imdr/domains/fx/` lean-pass file walk (file 1 → 19)
- **Purpose**: per-file inventory of every optimization considered, with status
  and rationale. Single index so future passes don't re-evaluate the same
  trade-off from scratch.

| Status | Meaning |
|---|---|
| ✅ applied | Edited in the file 7s slice's commit |
| 📄 deferred | Filed in a dev doc, intentional follow-up |
| ❌ skipped | Considered and rejected; reason recorded so it stays rejected |
| 🚧 open | Surfaced but undecided — needs a decision |

## File 1 — `__init__.py`

| Optimization | Status | Notes |
|---|---|---|
| Drop dead `FXOHLCRepository` re-export | ✅ applied | Zero callers; submodule path used everywhere. Commit `641d630`. |

## File 2 — `_parquet_store.py`

| Optimization | Status | Notes |
|---|---|---|
| `timezone.utc` → `datetime.UTC` (UP017) | 📄 deferred | Part of 273-site ruff sweep — see [ruff_sweep_scope.md](ruff_sweep_scope.md). |

## File 3 — `clean_fx_fact_fx_rate.py`

| Optimization | Status | Notes |
|---|---|---|
| Collapse 5-way `HardBound/RobustOutlier/PercentageChange` duplication | 📄 deferred | Cross-domain rewrite — see [cleaning_rules_consolidation.md](cleaning_rules_consolidation.md). |
| Fix docstring lie (NULL vs DELETE) | 📄 deferred | Land with consolidation. |
| Route f-string bounds through `params` | 📄 deferred | Land with consolidation. |

## File 4 — `clean_fx_fact_ohlc.py`

| Optimization | Status | Notes |
|---|---|---|
| Adopt OHLC's `_assert_safe()` regex guard as the baseline | 📄 deferred | Consolidation baseline — see [cleaning_rules_consolidation.md](cleaning_rules_consolidation.md). |
| Trim over-fetched `LAG()` in `HardBoundViolationRule.detect` | 📄 deferred | Land with consolidation. |

## File 5 — `clean_fx_fact_vol.py`

| Optimization | Status | Notes |
|---|---|---|
| Unify `_assert_safe()` vs `_assert_safe_config_key()` helpers | 📄 deferred | Single helper at consolidation layer. |
| Per-domain `PercentageChangeRule` extension hook (4-tier logic) | 📄 deferred | Canonical use case for the extension hook — see [cleaning_rules_consolidation.md](cleaning_rules_consolidation.md). |
| Route f-string thresholds through `params` | 📄 deferred | Land with consolidation. |

## File 6 — `coverage.py`

| Optimization | Status | Notes |
|---|---|---|
| Add missing return annotations on `_per_pair_row_counts` / `_row_counts_summary` | ❌ skipped | Two 30-second fixes that don't change behavior; not worth churning the diff. |
| Cross-domain extraction of `_year_filter` / `_per_pair_row_counts` | 🚧 open | Pattern recurs across domains' coverage modules; revisit when walking rates/commodities coverage. |

## File 7 — `extractors_ohlc.py`

| Optimization | Status | Notes |
|---|---|---|
| Delete dead `FXSpotExtractor` + `CitiVelocityExtractor` stubs | ✅ applied | Zero callers; CitiVelocity stub superseded by `extractors_rate.py`. Commit `641d630`. |
| Hoist `requests` / `HTTPAdapter` / `timedelta` to module top | ✅ applied | Lazy imports inside method bodies — moved to top. Commit `641d630`. |
| Fix stale module docstring (no longer a stub) | ✅ applied | Commit `641d630`. |
| Add 27 tests with exact `BarDiagnostic.reason` strings pinned | ✅ applied | Per [feedback_always_write_tests](../../../../../C:/Users/adoshi/.claude/projects/z--Business-Personnel-Arjun-GitHub-IMDR/memory/feedback_always_write_tests.md). |
| Expose `universe._order_pair()` as public | 🚧 open | `BidFXExtractor._process_currency` reaches into a private. Defer to Stage D1 (FX domain trim) — universe rewrite needed, not just an extractor edit. |
| Add `BidFXExtractor` integration tests with HTTP mocking | 🚧 open | Networked — would need a mocking harness; defer to integration suite. |

## File 8 — `extractors_rate.py`

| Optimization | Status | Notes |
|---|---|---|
| Publish `_errors` / `_tag_errors` as public (Opt A) | ✅ applied | Pipeline already reached in via comment-documented alias. Commit `ef2be5c`. |
| `e` → `exc` on except handler (E741) | ✅ applied | Folded into the same edit. Commit `ef2be5c`. |
| Add 11 tests pinning every error branch + budget math | ✅ applied | Commit `ef2be5c`. |
| Cross-pair batching (one mega-fetch instead of N per-pair) | 📄 deferred | Real perf win (19 → 3 HTTP calls for live FX rate, 18 → 2 rate-limit sleeps), but contract-changing across multiple Citi extractors + notification formatters. See [citi_fetch_batch_across_pairs.md](citi_fetch_batch_across_pairs.md). |

## File 9 — `extractors_rate_bbg.py`

| Optimization | Status | Notes |
|---|---|---|
| Same Opt A + E741 fix (consistency with file 8) | ✅ applied | Commit `edc6835`. |
| Collapse `_TENOR_NORMALIZATION` to the one real rename | ✅ applied | 6 identity passthroughs were redundant given the dict-get fallback. Commit `edc6835`. |
| Promote duplicated empty-result column list to `_OUTPUT_COLUMNS` constant | ✅ applied | Commit `edc6835`. |
| Single boolean mask for spot / non-spot split | ✅ applied | Replaces 3 repeated `tenor == "SPOT"` scans. Commit `edc6835`. |
| Move `BBG_POINTS_DIVISOR` to `bbg_points_divisor.yml` | ✅ applied | Adding a new BBG ccy now only requires a yml edit, not a code change. Commit `edc6835`. |
| Add `bbg_no_spot_row` warning when CSV has forwards but no SPOT | ✅ applied | Previously silent failure — merge dropped every forward and returned empty. Commit `edc6835`. |
| Add test pinning the new warning event payload | ✅ applied | Uses `structlog.testing.capture_logs()`. Commit `edc6835`. |

## File 10 — `extractors_vol.py`

| Optimization | Status | Notes |
|---|---|---|
| Same Opt A + E741 fix (consistency with files 8 + 9) | ✅ applied | Commit `70eba89`. |
| Add `tag_errors` parity with file 8 | ✅ applied | Diagnostic gap fix — per-tag ERROR/EMPTY responses were silently dropped on vol. Commit `70eba89`. |
| Add 11 tests including `tag_errors` plumbing contract | ✅ applied | Commit `70eba89`. |
| Cache `build_vol_tags(c1, c2)` between pre-flight and loop | ❌ skipped | Pure string concat × 17 pairs × 2 calls — trivial perf-wise, not worth the code complexity. |
| Move type-only imports under `TYPE_CHECKING` | ❌ skipped | `from __future__ import annotations` already makes them lazy; the `TYPE_CHECKING` dance adds noise without measurable benefit. |
| Unify `COLUMNS` vs `WIDE_COLUMNS` naming across translate modules | ❌ skipped | Cosmetic, would force a rename ripple across imports for zero behavior change. Revisit if other inconsistencies surface. |
| Cross-pair batching for vol specifically | ❌ skipped | Per [citi_fetch_batch_across_pairs.md](citi_fetch_batch_across_pairs.md): only ~10% call-count reduction at 90 tags/pair (already nearly saturates the 50-tag batch). Not worth the contract change for vol alone. |
| Cross-domain `_errors` → `errors` rename (7 callsites) | 📄 deferred | See [extractor_errors_rename.md](extractor_errors_rename.md). |
| `BatchedCitiExtractor` base class | 📄 deferred | Pairs with the cross-domain rename — see [extractor_errors_rename.md](extractor_errors_rename.md). |

## File 11 — `pipeline_ohlc.py`

| Optimization | Status | Notes |
|---|---|---|
| N+1 in `_anomaly_prescreen` — batch into one query | ✅ applied | New `FXOHLCRepository.get_last_closes_batch()` (single query with 7-day lookback bound). 19+ DB RTTs/hour → 1. Test pinned: `repo.get_last_close.assert_not_called()`. |
| Wire quality thresholds from `pipelines.yml`'s `fx.ohlc.cleaning` | ✅ applied | Re-added `get_pipeline_config()` import; thresholds (`n_mad`, `trailing_months`, `pct_threshold`) flow into `_build_quality_checks`. Aligns post-ingest checks with batch cleaning. |
| Capture `_write_parquet` failures in `result.diagnostics` | ✅ applied | Helper now returns `None` on success or a structured dict on failure; orchestrator appends to `result.diagnostics` + emits `report.warning`. Previously: silent log line. |
| Add 18 tests covering orchestrator + helpers + pipeline class | ✅ applied | Includes assertion that the N+1 stays gone (`repo.get_last_close.assert_not_called()`). |
| `BasePipeline` ABC abuse (extract/transform → None) | 📄 deferred | See [`single_step_pipeline_abc.md`](single_step_pipeline_abc.md). Pinned in `test_extract_and_transform_are_noops` so the deferred refactor is visible. |
| F-string SQL in `_post_ingest_quality` (`where = f"AND [ts] = '...'"`) | ❌ skipped | Datetime comes from internal `HourWindow`, not user input; consistent with the project's existing pattern for healthcheck queries. Revisit if a wider parameterisation push happens. |

## File 12 — `pipeline_rate.py`

| Optimization | Status | Notes |
|---|---|---|
| `iterrows()` → `to_dict("records")` in `transform()` | ✅ applied | 10-50× speedup for historical-backfill case (years of daily data → hundreds of thousands of rows). Regression test pins the call form `.iterrows(` so future refactors can't silently reintroduce it. |
| Add 12 tests covering transform happy / skip / failure paths | ✅ applied | Includes exact-message assertions on `RuntimeError` for missing vendor + missing frequency (`023_create_dim_frequency.sql` hint pinned). |
| Pipeline-side `_extraction_errors` / `_quota_usage` / `_tag_errors` / `_quality_results` private-attr smell | 📄 deferred | Extended [`extractor_errors_rename.md`](extractor_errors_rename.md) with the pipeline-layer rename — 8+ script callsites read these as `pipeline._extraction_errors`. Bundle with the extractor-layer rename. |
| F-string SQL in `_run_quality_checks` (`where = f"..."`) | ❌ skipped | Internal-only datetime values (`self._start`/`self._end`); same decision as file 11. |
| Function-local imports at lines 286-291 | ❌ skipped | `from imdr.healthchecks.base import CheckStatus` etc. are inside `_run_quality_checks` — preserves laziness for the post-load hook that may not always fire. Not worth the churn. |
| 11-param `__init__` (settings, universe, dates, pairs, chunk, frequency, creds, quota path…) | ❌ skipped | Could group into a config dataclass but every parameter is used and the call sites pass keyword args. Premature consolidation. |

## File 13 — `pipeline_rate_bbg.py`

| Optimization | Status | Notes |
|---|---|---|
| Hoist function-local imports from `extract()` to module top | ✅ applied | `BBGFXSourceFile`, `resolve_pair_orientation`, `datetime`, `timezone` were imported lazily inside the method body. No circular-import risk (parent module already imports `extractors_rate_bbg`). |
| `iterrows()` → `to_dict("records")` in `transform()` | ✅ applied | Same 10-50× speedup as file 12. Regression guard pinned in new `TestTransformRowIteration`. |
| Add tests: NaN mid_rate skip, frequency-missing error message, invalid-Pydantic-row skip, `get_run_context` | ✅ applied | 4 new tests covering the previously-missing transform branches. |
| Transform duplication with `FXRatePipeline.transform` | 🚧 open | ~90% identical: dim seeding + pair_id cache + vendor/frequency FK lookup + validation loop. Differences are real (Decimal precision rounding, obs_date column source, try/except shape) — a shared `_resolve_fx_rate_fks()` helper would extract the genuinely shared bit. Bundle with the cleaning consolidation when that lands. |
| `_extraction_errors` / `_raw_df` private-attr smell | 📄 deferred | Bundled with [`extractor_errors_rename.md`](extractor_errors_rename.md) at the pipeline layer. |
| `timezone.utc` → `datetime.UTC` (UP017) | 📄 deferred | Part of the ruff sweep — see [ruff_sweep_scope.md](ruff_sweep_scope.md). |

## File 14 — `pipeline_rate_bbg_daily.py`

| Optimization | Status | Notes |
|---|---|---|
| Add `obs_ts` midnight-UTC override test | ✅ applied | The daily class's only novel behavior was untested — `TestDailyExtractMidnightUTC.test_obs_ts_is_midnight_utc_of_obs_date`. |
| Add wiring tests (`pipeline_name`, `FREQUENCY_CODE` override) | ✅ applied | Tiny but locks the subclass contract; 5 tests total in new `test_bbg_fx_rate_daily_pipeline.py`. |
| Drop `df["ts"] = df["obs_ts"]` alias | ❌ skipped | "Kept for any downstream expecting `ts`" — no current consumer reads it, but the alias is one line and removing it would require a wider audit. Defensive add, low cost. |
| Function-local `pd.to_datetime` call vs module-level helper | ❌ skipped | One-liner, called once per extract; not worth a helper. |

## File 15 — `pipeline_vol.py`

| Optimization | Status | Notes |
|---|---|---|
| `iterrows()` → `to_dict("records")` in `transform()` | ✅ applied | Closes the punch-list item flagged at the end of file 12. Regression guard pinned. |
| Add transform / load / get_run_context tests (no tests existed) | ✅ applied | 9 new tests in `test_fx_vol_pipeline.py`. Per `feedback_always_write_tests` — missing tests for a `src/` module is a finding to fix now. |
| `_extraction_errors` / `_quota_usage` / `_quality_results` private-attr smell | 📄 deferred | Same pattern as file 12 — bundled with [`extractor_errors_rename.md`](extractor_errors_rename.md). |
| Lazy imports inside `_run_quality_checks` | ❌ skipped | Same decision as file 11 — preserves laziness for an optional post-load hook. |

## File 16 — `rate_translate.py`

| Optimization | Status | Notes |
|---|---|---|
| Keep — 98 lines, well-tested (16 existing tests), no smells | ✅ applied | Pure helpers (`citi_fx_rate_tag_to_internal`, `pivot_long_to_wide`); early-return on empty; no iterrows; no private-attr leaks. Nothing to do. |

## File 17 — `repository_ohlc.py`

| Optimization | Status | Notes |
|---|---|---|
| Delete dead `bulk_create()` | ✅ applied | Zero callers in src/ or tests/. The pipeline uses `bulk_upsert` (temp-table MERGE). |
| Delete dead `count_by_hour()` | ✅ applied | Zero callers anywhere. |
| Delete dead `get_last_close()` (single-row) | ✅ applied | Replaced by `get_last_closes_batch()` in slice 11. The pinned regression guard in `test_fx_ohlc_pipeline.py:213` was relying on a MagicMock attribute that no longer exists in the real class — rewrote it as a source-code assertion (`def get_last_close(` must not reappear). |
| `delete_range`: load-then-loop-delete → single bulk DELETE | ✅ applied | Old impl loaded every row into memory then called `session.delete()` per row. New impl: `session.execute(delete(FXFactOHLC).where(...))`. `FXFactOHLC` has no ORM cascades or relationships, so the bulk path is equivalent. Returns `rowcount`. |
| Update `docs/admin/fx/fx_overview.md` module map + anomaly-prescreen description | ✅ applied | Stale references to `repository.py` / `get_last_close()` updated to `repository_ohlc.py` / `get_last_closes_batch()`. |
| Cross-domain `count_by_date` / `count_by_hour` dead-method audit | 🚧 open | Surfaced 5 other repositories with identical dead `count_by_date()` methods (rates, equity, commodities, rates_skew, rates_vol). Skip until those domains are walked — bundle into the per-domain trim. |

## File 18 — `repository_rate.py`

| Optimization | Status | Notes |
|---|---|---|
| Delete dead `count_by_date()` | ✅ applied | Zero callers; same pattern as repository_ohlc's `count_by_hour`. |
| Drop now-unused imports (`date`, `func`, `select`, `FXFactFXRate`) | ✅ applied | Falls out of the deletion. |

## File 19 — `repository_vol.py` + `vol_translate.py`

`repository_vol.py`:

| Optimization | Status | Notes |
|---|---|---|
| Delete dead `FXCurrencyPairRepository.get_or_create()` | ✅ applied | Zero external callers; pipelines use `bulk_seed_from_universe` instead. |
| Delete dead `FXVolRepository.count_by_date()` | ✅ applied | Zero callers. |
| Drop now-unused imports (`date`, `func`, `FXFactVol`) | ✅ applied | Falls out of the deletions. |
| Make `get_by_key()` private | ❌ skipped | Used only internally by `bulk_seed_from_universe`, but the [`fx_dim_currency_pair_string_cleanup.md`](fx_dim_currency_pair_string_cleanup.md) deferred work explicitly targets `get_by_key()` as the JOIN integration point. Leaving it public so the rename ripple stays small. |

`vol_translate.py`:

| Optimization | Status | Notes |
|---|---|---|
| Add tests for `citi_vol_tag_to_internal` + `citi_vol_response_to_df` | ✅ applied | 9 new tests in `test_fx_vol_translate.py` — segment count, wrong prefix, empty, sort order, unparseable tag drop, per-tag ERROR skip. Per `feedback_always_write_tests`. |
| File kept as-is (40 lines, clean, pure helpers) | ✅ applied | Nothing else to do. |

## Agentic-review pass (post-walk, 2026-05-19)

Ran `imdr-code-reviewer` over the post-walk state. Verified findings, applied
in-scope correctness fixes and filed the cross-domain items as follow-ups.

### Applied this pass

| File:line | Fix | Reason |
|---|---|---|
| [`pipeline_rate_bbg.py`](../../../src/imdr/domains/fx/pipeline_rate_bbg.py) `extract()` | Guard `path.stat()` with `FileNotFoundError`/`OSError` try/except → per-file error entry, continue. Aliased `extractor.errors` to `self._extraction_errors` before the loop so the guard's appends survive. | The R pipeline overwrites in place — a source CSV can disappear between `LocalFilesystemAcquirer.fetch()` and `extract()`. Previously this would crash the whole fire. Test: `TestExtractMissingFileRace`. |
| [`pipeline_rate_bbg.py`](../../../src/imdr/domains/fx/pipeline_rate_bbg.py) `transform()` | Hoist `if raw.empty: return []` to the top of the method — short-circuit before the session is opened. | Common "no new BBG files" case previously did two DB round-trips (vendor + frequency lookups) for nothing. Test: `TestTransformEmptyShortCircuit`. |
| [`pipeline_vol.py`](../../../src/imdr/domains/fx/pipeline_vol.py) `extract()` | Alias `extractor.errors` inside the `with CitiVelocityClient` block + `try/finally` for `_quota_usage`. Mirrors the existing `pipeline_rate.py` pattern. | Mid-fetch `TagQuotaExceeded` previously lost the partial-state diagnostic lists because the alias was assigned *after* the context exited. Test: `TestExtractPartialStateSurvivesQuotaExceeded`. |
| [`pipeline_ohlc.py`](../../../src/imdr/domains/fx/pipeline_ohlc.py) | Hoist `import pandas as pd` to module top; drop the function-local import in `_write_parquet`. | Module already imports heavyweight deps; the lazy `pandas` import bought nothing. |

### Filed as new follow-up docs

- [`quality_dispatch_helper.md`](quality_dispatch_helper.md) — 60-line `_run_quality_checks` dispatch loop duplicated across 4 pipelines (FX rate/vol, rates vol, commodities vol). Also catches a real bug: `qr.meta.get("total_violations") or qr.meta.get("outlier_count") or qr.meta.get("flagged_count")` returns `None` when all three are `0` (falsy). Audit logs currently record `flagged_count: None` for clean runs. Bundle with `healthchecks/` redesign.
- [`bbg_pipeline_config_split.md`](bbg_pipeline_config_split.md) — `BloombergFXRatePipeline` reads `get_pipeline_config("fx.citi_rate")` for its config. Different cadence + vendor warrants its own entry in `pipelines.yml` so health-check thresholds (`row_count_min`, `max_staleness_hours`) can diverge cleanly. Loop in `imdr-dbm`.

### Verified good (no action)

- `get_last_closes_batch()` cartesian-IN + Python trim — correct; time bound keeps candidates small.
- `_parquet_store.write_partitioned_parquet` atomic tmp+replace — correct, shared properly.
- `FXCurrencyPairRepository.bulk_seed_from_universe()` — idempotent via `get_by_key` guard.
- `BloombergFXRateDailyPipeline.FREQUENCY_CODE` class-attr override — correct mechanism.
- `_TENOR_NORMALIZATION` post-slice-9 trim — correct.

## Pointers to deferred work docs

- [ruff_sweep_scope.md](ruff_sweep_scope.md) — 645 ruff findings (273 `UP017`, 65 `F401`, etc.)
- [cleaning_rules_consolidation.md](cleaning_rules_consolidation.md) — 5-way `HardBound/RobustOutlier/PercentageChange` collapse
- [citi_fetch_batch_across_pairs.md](citi_fetch_batch_across_pairs.md) — cross-pair Citi batching
- [extractor_errors_rename.md](extractor_errors_rename.md) — `_errors` → `errors` rename + optional `BatchedCitiExtractor` base
- [single_step_pipeline_abc.md](single_step_pipeline_abc.md) — `BasePipeline` ABC abuse for single-step pipelines
- [quality_dispatch_helper.md](quality_dispatch_helper.md) — shared `_run_quality_checks` helper + `flagged_count` 0-falsy bug
- [bbg_pipeline_config_split.md](bbg_pipeline_config_split.md) — BBG pipelines need their own `pipelines.yml` entries
