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

## Files 12–19 — to be walked

| File | Notes |
|---|---|
| `pipeline_rate.py` | Has `iterrows()` perf rewrite flagged in repo-review doc. |
| `pipeline_rate.py` | Has `iterrows()` perf rewrite flagged in repo-review doc. |
| `pipeline_rate_bbg.py` | Already touched in file 9 (Opt A caller update). |
| `pipeline_rate_bbg_daily.py` | Untracked. |
| `pipeline_vol.py` | Already touched in file 10 (Opt A caller update). Has `iterrows()` perf flag. |
| `rate_translate.py` | Already touched in files 7-8 testing. |
| `repository_ohlc.py` | — |
| `repository_rate.py` | — |
| `repository_vol.py` | — |
| `vol_translate.py` | Already touched in file 10 testing. |

## Pointers to deferred work docs

- [ruff_sweep_scope.md](ruff_sweep_scope.md) — 645 ruff findings (273 `UP017`, 65 `F401`, etc.)
- [cleaning_rules_consolidation.md](cleaning_rules_consolidation.md) — 5-way `HardBound/RobustOutlier/PercentageChange` collapse
- [citi_fetch_batch_across_pairs.md](citi_fetch_batch_across_pairs.md) — cross-pair Citi batching
- [extractor_errors_rename.md](extractor_errors_rename.md) — `_errors` → `errors` rename + optional `BatchedCitiExtractor` base
- [single_step_pipeline_abc.md](single_step_pipeline_abc.md) — `BasePipeline` ABC abuse for single-step pipelines
