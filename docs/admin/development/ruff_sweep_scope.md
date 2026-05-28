# Ruff Sweep — Full Scope

- **Filed**: 2026-05-14
- **Scanner**: `python -m ruff check src/ scripts/ tests/ --statistics`
- **Config**: [pyproject.toml](../../../pyproject.toml) `[tool.ruff]` — `target-version = "py311"`, `line-length = 120`, `select = ["E", "F", "I", "N", "UP", "B", "SIM", "RUF"]`
- **Total findings**: **645** (486 auto-fixable, 72 more behind `--unsafe-fixes`, 87 manual)
- **Companion doc**: [tech_debt_ruff_findings.md](tech_debt_ruff_findings.md) — narrow F-class subset with case writeups for the 4 F841 unused-variable hits worth manual investigation. Keep both.

## Why this doc exists

The repo-review plan (`docs/admin/development/full_repo_review.md` Stage E5) commits to a final "ruff F-class zero" sweep, but the actual scanner state is much broader than F-class. This doc scopes **everything ruff flags today**, bucketed by fix risk so we can decide what to batch into the lean pass vs what to leave for Stage E5 vs what stays open.

The 11-fix `timezone.utc → datetime.UTC` estimate in the in-flight FX overhaul section turned out to be a 273-site issue across the whole repo — that mismatch is what prompted this scoping.

## Headline numbers

| Tree | Total | Auto-fixable | Manual |
|---|---:|---:|---:|
| `src/` | 208 | 145 | 63 |
| `scripts/` | 309 | 227 | 82 |
| `tests/` | 128 | 114 | 14 |
| **All** | **645** | **486** | **159** |

`scripts/` is the heaviest because of `run_pipeline.py` (21 UP017) + every scheduler reaching the `timezone.utc` idiom.

---

## Tier 1 — True no-op cosmetic (360 fixes, zero risk)

`ruff check --fix --select UP017,F541,UP037,UP015,UP045,UP035,RUF100,RUF010,RUF046,SIM300,SIM114,SIM117` is safe to run, review the diff once, ship it. No behavior change, no deleted code, just syntax modernization.

| Rule | Count | What it does | Notes |
|---|---:|---|---|
| `UP017` | **273** | `timezone.utc` → `UTC` | The big one. Python 3.11+ aliases `datetime.UTC` to `datetime.timezone.utc`. Pure rename. |
| `F541` | 49 | `f"text"` (no placeholders) → `"text"` | Almost all in scripts. Cosmetic. |
| `RUF100` | 18 | Strip unused `# noqa: X` | Removes a comment, no code change. |
| `UP037` | 12 | `def f(x: "int")` → `def f(x: int)` | Unquotes annotations when the type is in scope. |
| `UP035` | 6 | `from typing import List` → `from collections.abc import ...` / built-ins | Deprecated typing imports. |
| `RUF010` | 2 | `f"{str(x)}"` → `f"{x!s}"` | Explicit conversion flag. |
| `RUF046` | 2 | `int(round(x))` → `round(x)` | `round()` already returns int when called with no ndigits. |
| `SIM117` | 2 | `with A: with B:` → `with A, B:` | Combine context managers. Tests only. |
| `SIM114` | 1 | `if A or B: x else if C: x` → `if A or B or C: x` | One branch consolidation. |
| `SIM300` | 1 | `5 == x` → `x == 5` | Yoda condition. |
| `UP015` | 1 | `open(f, 'r')` → `open(f)` | Default mode. |
| `UP045` | 1 | `Optional[X]` → `X \| None` | PEP 604. |
| **Total** | **368** | | |

### Top files for UP017 (timezone.utc rewrite)

| File | Hits |
|---|---:|
| [scripts/run_pipeline.py](../../../scripts/run_pipeline.py) | 21 |
| [tests/unit/test_citi_helpers.py](../../../tests/unit/test_citi_helpers.py) | 13 |
| [tests/unit/test_staleness.py](../../../tests/unit/test_staleness.py) | 9 |
| [scripts/prediction/polymarket/streaming.py](../../../scripts/prediction/polymarket/streaming.py) | 9 |
| [scripts/fx/bidfx/fx_bidfx_historical.py](../../../scripts/fx/bidfx/fx_bidfx_historical.py) | 8 |
| [tests/unit/test_citi_quota.py](../../../tests/unit/test_citi_quota.py) | 7 |
| [tests/unit/test_citi_velocity_client.py](../../../tests/unit/test_citi_velocity_client.py) | 6 |
| [src/imdr/connectors/citi_helpers.py](../../../src/imdr/connectors/citi_helpers.py) | 6 |

A single sweep removes 273 spurious diff lines that will otherwise show up forever in `git blame` whenever someone touches those modules.

---

## Tier 2 — Auto-fixable but deletes / reorders code (116 fixes, low risk)

`--fix` works, but the change is structural enough that a per-file diff review is worth doing.

| Rule | Count | What it does | Why it merits a glance |
|---|---:|---|---|
| `F401` | **65** | Delete unused imports | If a module re-exports for consumers (no `__all__`), the auto-fix drops the re-export. Spot-check `__init__.py`s and any `from imdr.X import Y` that's *meant* to be public. |
| `I001` | 51 | Re-sort imports per isort grouping | Safe in 99% of cases, but rare modules with import-order side effects (matplotlib backend, monkeypatching) can break. |

### Top files for F401

| File | Hits | Suspicion |
|---|---:|---|
| [scripts/migrations/load_fx_fact_ohlc.py](../../../scripts/migrations/load_fx_fact_ohlc.py) | 7 | Migration script — likely safe to delete |
| [tests/unit/test_rates_bench.py](../../../tests/unit/test_rates_bench.py) | 5 | Probably orphaned test fixtures |
| [src/imdr/domains/rates/extractors.py](../../../src/imdr/domains/rates/extractors.py) | 4 | Touched recently in cache disable — review |
| [src/imdr/domains/rates/pipeline_skew.py](../../../src/imdr/domains/rates/pipeline_skew.py) | 3 | Recently added module |
| [src/imdr/domains/commodities/repository.py](../../../src/imdr/domains/commodities/repository.py) | 3 | Per tech_debt_ruff_findings.md, these are deliberate re-exports — **do NOT auto-fix** |

The commodities re-exports are the canonical example of why F401 needs human review — the auto-fix is wrong there.

---

## Tier 3 — Auto-fixable style nits (a few unsafe-fixes, ~14 total)

`RUF022` (2) — sort `__all__`. Auto-fix changes export ordering — fine for runtime, but unstable diffs if `__all__` ordering carries semantic meaning (it usually doesn't).

`SIM118` (2) — `x in d.keys()` → `x in d`. Behavior-identical, micro-perf win.

Various other one-off rule hits, all listed in `--statistics`.

---

## Tier 4 — Manual, defer or address per file (159 findings)

Not auto-fixable. Each needs a decision, ideally as part of touching the file for other reasons.

| Rule | Count | What it flags | Why it's manual |
|---|---:|---|---|
| `E501` | 19 | Lines > 120 chars | Each is a judgment call: wrap, refactor, or `# noqa: E501` (rare). |
| `B905` | 16 | `zip()` without `strict=` | Pick `strict=True` (mismatched length is an error) or `strict=False` (drop without warning). The default is footgunny — Python 3.10+ recommends explicit. |
| `RUF002`/`RUF003`/`RUF001` | 30 | Ambiguous unicode (smart quotes, em-dashes in docstrings/comments/strings) | Mostly cosmetic copy-paste artifacts. Auto-fix would rewrite the text, risky if the unicode is intentional (rare in this repo). |
| `SIM108` | 13 | `if/else` block → `... if ... else ...` ternary | Style judgment; ternaries hurt readability when the branches are non-trivial. |
| `F841` | **10** | Unused variables (the high-signal one) | 4 of these are written up in [tech_debt_ruff_findings.md](tech_debt_ruff_findings.md). Each is a possible half-finished refactor. **Investigate, don't suppress.** |
| `RUF005` | 10 | `[*x, y]` style for concat | Style choice; ruff thinks splat is clearer than `x + [y]`. |
| `N806` | 9 | Non-lowercase var in function (`Universe`, `DF`, etc.) | Often deliberate when matching domain conventions (currency codes, dataframe `DF`). Case-by-case. |
| `SIM105` | 9 | `try: ... except: pass` → `contextlib.suppress(...)` | Style; contextlib is cleaner but pulls an import. |
| `N818` | 7 | Exception class name doesn't end in `Error` | Names like `TagQuotaExceeded` are intentional. Worth surveying once. |
| `RUF059` | 7 | Unused unpacked variable in tuple-unpacking | `a, b = func()` where `b` is unused. Usually `_` it. |
| `E402` | 5 | Module-level import after non-import code | Often legit when there's a `sys.path` mod or `os.environ` set first. |
| `RUF012` | 5 | Mutable class attribute without `ClassVar` | Pydantic / dataclass interplay — usually safe but worth pinning. |
| `B017` | 3 | `pytest.raises(Exception)` too broad | Should match the specific exception. Test-quality nit. |
| `E741` | 3 | Single-char variable name like `l` / `I` / `O` | Easy rename. |
| `UP042` | 3 | `StrEnum` (3.11+) over `str, Enum` | Constraint: ensure nothing inherits/checks the dual-base form. |
| `B007` | 2 | Unused loop variable | Rename to `_`. |
| `F821` | 2 | Undefined name | Both are false-positive forward refs documented in [tech_debt_ruff_findings.md](tech_debt_ruff_findings.md). |
| Various | ~6 | One-offs: `SIM102` collapsible if, `SIM103` needless bool, etc. | Single-site fixes. |

---

## Suggested execution

| Step | Scope | Risk | Effort | Why |
|---|---|---|---|---|
| 1 | Tier 1 — `ruff check --fix --select UP017,F541,UP037,UP015,UP045,UP035,RUF100,RUF010,RUF046,SIM300,SIM114,SIM117` | Zero | S | Removes 360 spurious diff lines forever; clean PR; no test risk. |
| 2 | Tier 2 — F401, with the commodities re-exports pre-excluded | Low | S | Eyeball the diff; mostly migration scripts and test fixtures. |
| 3 | Tier 2 — I001 alone | Low | S | Re-sorts imports; review for any module with `sys.path` games. |
| 4 | Tier 4 manual — opportunistic during Stage D (per-domain trim) | Per file | — | Each file's flags get resolved as the lean pass touches it. |
| 5 | Tier 4 residue — Stage E5 final sweep | Low | M | Whatever's left after Stage D. |

Steps 1-3 can land as three small commits in a single sitting. Steps 4-5 are already on the Stage E5 plan.

## Notes for the sweep

- Run `pytest tests/unit/ --ignore=tests/unit/test_config.py` after each step. The baseline is **978 passed, 6 known fails, 2 skipped** as of 2026-05-14.
- The 4 F841 cases in [tech_debt_ruff_findings.md](tech_debt_ruff_findings.md) are *not* auto-fixable and represent the only items worth specific investigation. Don't lose them.
- After the sweep, refresh both `tech_debt_ruff_findings.md` and this doc — close items as fixed, leave manual hits open.
- `--unsafe-fixes` is **not** recommended yet; the 72 additional fixes there include things ruff itself flags as risky.
