# Follow-up: Collapse the 5 copies of `HardBoundViolationRule` / `RobustOutlierRule` / `PercentageChangeRule`

- **Date filed**: 2026-05-14
- **Status**: deferred — depends on the larger `healthchecks/` redesign
- **Triggered by**: file-by-file walk of `src/imdr/domains/fx/`, file 3 ([clean_fx_fact_fx_rate.py](../../../src/imdr/domains/fx/clean_fx_fact_fx_rate.py))
- **Related**: [project_healthchecks_needs_rework.md](../../../../../C:/Users/adoshi/.claude/projects/z--Business-Personnel-Arjun-GitHub-IMDR/memory/project_healthchecks_needs_rework.md) (memory), [cleaning_framework.md](../ops/cleaning_framework.md)

## What we found

The same three cleaning-rule classes — `HardBoundViolationRule`, `RobustOutlierRule`, `PercentageChangeRule` — are independently re-implemented in **five** domain modules.

| # | File | Lines | Target table | Group keys |
|---|---|---:|---|---|
| 1 | [src/imdr/domains/fx/clean_fx_fact_fx_rate.py](../../../src/imdr/domains/fx/clean_fx_fact_fx_rate.py) | 279 | `fx.fact_fx_rate` | `pair_id, tenor` |
| 2 | [src/imdr/domains/fx/clean_fx_fact_ohlc.py](../../../src/imdr/domains/fx/clean_fx_fact_ohlc.py) | ~430 | `fx.fact_ohlc` | `symbol, series` |
| 3 | [src/imdr/domains/fx/clean_fx_fact_vol.py](../../../src/imdr/domains/fx/clean_fx_fact_vol.py) | ~370 | `fx.fact_vol` | `pair_id, strike, tenor, vol_type` |
| 4 | [src/imdr/domains/rates/clean_rates_fact_observation.py](../../../src/imdr/domains/rates/clean_rates_fact_observation.py) | ~340 | `rates.fact_observation` | `curve_id, quote, tenor` |
| 5 | [src/imdr/domains/commodities/clean_implied_vol.py](../../../src/imdr/domains/commodities/clean_implied_vol.py) | ~270 | `cmdty.fact_implied_vol` | varies |

Each copy implements the same three rule shapes (hard-bound check, rolling-window MAD outlier, day-over-day pct change) over the same `CleaningRule` ABC, differing only in:

- **Table / column names** — purely configuration.
- **Group-by keys** — natural-key tuple per fact table.
- **Action on violation** — DELETE (where the target column is `NOT NULL` with a `CHECK` constraint, e.g. `fx.fact_fx_rate.mid_rate`) vs UPDATE-to-NULL (where NULL is allowed).
- **Threshold defaults** — but every script callsite passes them in from `pipelines.yml` anyway.

Each script entry in `scripts/{domain}/clean/clean_*.py` instantiates the same three rules with thresholds pulled from config:

```python
[
    HardBoundViolationRule(ranges=ranges),
    RobustOutlierRule(n_mad=..., trailing_months=..., min_obs=...),
    PercentageChangeRule(threshold_pct=...),
]
```

## Why it's duplicated today

Historical accretion. Each fact table got its own `clean_*.py` written copy-paste style as it was added. The `CleaningRule` ABC in [healthchecks/cleaning.py](../../../src/imdr/healthchecks/cleaning.py) exists but doesn't host concrete implementations — every domain re-writes them.

Some real differences are baked in:

- The SQL in `RobustOutlierRule.detect` joins different dim tables per domain (`dim_currency_pair` vs `dim_curve` vs `dim_implied_vol_surface`).
- The `PercentageChangeRule` for `clean_fx_fact_vol.py` has a 3-tier filtering scheme (strike-aware absolute thresholds → class×tenor matrix → fallback) — see [cleaning_framework.md:279-293](../ops/cleaning_framework.md#L279-L293) — that doesn't apply to the others.
- The `HardBoundViolationRule.build_update_sql` switches between DELETE and UPDATE depending on whether the target column has a NOT-NULL CHECK constraint.

So the collapse isn't pure copy-paste removal — it needs a parameterised base that takes a table spec (table name, dim joins, group keys, action mode, optional per-rule extension hooks).

## Proposed shape

Three concrete rule classes in `src/imdr/healthchecks/cleaning_rules.py` (or wherever the redesign lands):

```python
class HardBoundViolationRule(CleaningRule):
    def __init__(self, spec: TableSpec, ranges: dict[Key, tuple[float, float]]) -> None: ...

class RobustOutlierRule(CleaningRule):
    def __init__(self, spec: TableSpec, n_mad: float, trailing_months: int, min_obs: int) -> None: ...

class PercentageChangeRule(CleaningRule):
    def __init__(self, spec: TableSpec, threshold_pct: float, **per_domain_extensions) -> None: ...
```

Where `TableSpec` carries:

- `table_name`, `value_column`, `dim_joins` (list of `(table, alias, on_clause)` tuples)
- `group_columns` (the natural key minus the time axis)
- `action_mode`: `"delete" | "null"` (which decides what `build_update_sql` emits)
- `extra_select_columns` (anything the `describe()` helper needs)

Each domain shrinks from a ~300-line file to a ~30-line file that builds its `TableSpec` and exports the three configured rules.

## Why it's deferred

This is one branch of the larger `healthchecks/` rework already flagged in memory. The healthchecks redesign decides:

- Where rule registration lives (domain folder, central registry, or `pipelines.yml`).
- Whether `healthchecks/reporter.py` and `reporting/reporter.py` collapse first.
- How the 4-line `RowCountCheck/NullCheck/DuplicateCheck/ValueRangeCheck` boilerplate from each pipeline's `get_health_checks()` is replaced.

Doing the cleaning-rule collapse first means rewriting it again when the healthchecks shape is decided. Hold until then.

## Baseline patterns to adopt from the existing copies

The 5 copies have diverged on safety / cleanliness — the consolidation should adopt the strongest version of each:

- **Identifier safety** — [clean_fx_fact_ohlc.py:29-34](../../../src/imdr/domains/fx/clean_fx_fact_ohlc.py#L29-L34) defines `_assert_safe()` and [clean_fx_fact_vol.py:26-31](../../../src/imdr/domains/fx/clean_fx_fact_vol.py#L26-L31) defines an almost-identical `_assert_safe_config_key()` — same regex `^[A-Za-z0-9_./-]+$`, two helper names. `clean_fx_fact_fx_rate.py` and the rates / commodities copies f-string identifiers in raw with no guard. **Adopt the single `_assert_safe()` helper at the consolidated layer** and delete both duplicates.
- **Parameterised bounds** — only `clean_fx_fact_ohlc.py`'s `HardBoundViolationRule.detect` uses real `:hb_sym_0 / :hb_lo_0 / :hb_hi_0` binding through the `params` dict. The other copies f-string the floats in. Reuse the OHLC pattern.

## Per-fact extension hooks

Each fact has 0–3 rules that don't fit the shared trio — they stay in a thin per-fact module that imports the shared rules and adds its own:

| Fact | Extra rules | Why domain-local |
|---|---|---|
| `fx.fact_ohlc` | `NonPositivePriceRule`, `OHLCOrderRule`, `BidAskInversionRule` | OHLC structure invariants — only applicable to OHLC candle shape. |
| `fx.fact_vol` | 4-tier `PercentageChangeRule` override (abs-vol_types → abs-strikes → ccy_class×tenor matrix → fallback). `HardBound` keyed on `(strike, vol_type)` tuple. `RobustOutlier` group keys include `vol_type` to keep IMPLIED/REALISED/SPREAD distributions separate (see [cleaning_framework.md:279-293](../ops/cleaning_framework.md#L279-L293)). | The pct logic is the canonical "per-domain hook" use case — surface scale varies wildly by strike (ATM vs 10-delta RR) and vol_type (REALISED vs SPREAD), no single threshold works. |
| `rates.fact_observation` | (TBD when walked) | Curve-specific. |
| `cmdty.fact_implied_vol` | (TBD when walked) | Vol-surface-specific. |
| `fx.fact_fx_rate` | None | Just the trio. |

So the consolidated layout is:

```
src/imdr/healthchecks/cleaning_rules.py   # the 3 shared rules + TableSpec
src/imdr/domains/fx/cleaning_fx_ohlc.py   # ~50 lines: TableSpec + 3 OHLC-only rules
src/imdr/domains/fx/cleaning_fx_rate.py   # ~10 lines: just the TableSpec
src/imdr/domains/fx/cleaning_fx_vol.py    # ~30 lines: TableSpec + vol-specific rules
...
```

## When this lands, also fix

- [clean_fx_fact_fx_rate.py:1-13](../../../src/imdr/domains/fx/clean_fx_fact_fx_rate.py#L1-L13) — module docstring says rules *"NULL bad values in mid_rate"* but `HardBoundViolationRule.build_update_sql` actually `DELETE`s (the column is `NOT NULL` with a positive CHECK constraint). The inline comment at [line 82-85](../../../src/imdr/domains/fx/clean_fx_fact_fx_rate.py#L82-L85) explains why, but the top docstring is misleading.
- F-string SQL interpolation of numeric bounds in `clean_fx_fact_fx_rate.py`'s `HardBoundViolationRule.detect` — pass via `params` for consistency with the rest of the reader path. Not a security risk (floats from config) but stylistically inconsistent.
- [clean_fx_fact_ohlc.py:152-170](../../../src/imdr/domains/fx/clean_fx_fact_ohlc.py#L152-L170) — `HardBoundViolationRule.detect` over-fetches: pulls a `LAG()` + `pct_change` column just for the `describe()` log message. A hard-bound check doesn't need history. Trim to just the violation row when consolidating.
- [clean_fx_fact_vol.py:297-338](../../../src/imdr/domains/fx/clean_fx_fact_vol.py#L297-L338) — `PercentageChangeRule.detect` f-strings numeric thresholds (`{thresh}`, `{self._min_abs_prev}`, `{self._threshold}`) directly into SQL. Keys are guarded by `_assert_safe_config_key` but numerics are not — they're floats from `fx.yml` so safe by type, but the consolidated version should route them through `params` for consistency.

## Blast radius when consolidation lands

- 5 domain modules collapsed (~1,690 lines → ~150 lines net).
- 5 corresponding `scripts/*/clean/clean_*.py` callsites — import path changes.
- Tests: [test_cleaning.py](../../../tests/unit/test_cleaning.py) — 4 tests that import the FX-rate variant by name; would import from the new shared module.
- Docs: [cleaning_framework.md](../ops/cleaning_framework.md), [fx_overview.md](../fx/fx_overview.md), [weekly_ops.md](../ops/weekly_ops.md), [new_product_playbook.md](../ops/new_product_playbook.md), [fx_rate_pipeline.md](../fx/fx_rate_pipeline.md), [rates_operations.md](../rates/rates_operations.md) — all reference the per-domain class paths and would update to the shared path.
- [scripts/imdr_health_dashboard.py:49](../../../scripts/imdr_health_dashboard.py#L49), [scripts/imdr_clean.py:22](../../../scripts/imdr_clean.py#L22) — entry points.
