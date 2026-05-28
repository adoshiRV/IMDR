# Tech Debt — Ruff F-class Findings

- **Filed**: 2026-05-13
- **Scanner**: `ruff check src/ --select F`
- **Total**: 33 findings across `src/` (27 unused imports + 4 unused variables + 2 false-positive undefined names)
- **Status**: open — none block Phase D, but worth chipping at when touching the relevant files
- **How to refresh**: `python -m ruff check src/ --select F` from repo root

These are surfaced by the standard ruff "F" category (pyflakes-equivalent). They're not Phase D regressions — most predate the country-anchor work. Filing here so they're not invisible.

---

## F841 — Unused variables (4 findings)

These are the highest-signal items: real code that was computed and then discarded. Most look like half-finished refactors where a variable's intended consumer got removed without removing the assignment.

### 1. `src/imdr/market_calendar/cb_scrapers.py:336`

```python
end_idx = len(text)
prev_year_marker = f"MPR I - {year - 1}"   # ← never used
if start_idx > 0:
    next_section = text.find(f"MPR I - {year + 1}", start_idx)
    if next_section == -1:
        next_section = text.find(f"({year - 1}", start_idx)
    if next_section > 0:
        end_idx = next_section
```

The comment two lines above says *"End at the next year's section or `(DD Month YYYY MB` pattern from prior year"*. The variable looks like it was meant for the *"from prior year"* search but the actual code only searches the next year and a `({year - 1}` pattern. Either the variable is dead and should be deleted, or there's a missing search branch using it (e.g. `text.find(prev_year_marker, start_idx)`).

**Risk**: low — scraper still works, just no fallback for an edge case it might have been meant to handle.
**Suggested fix**: delete the line if the missing branch isn't needed; otherwise wire it in.

### 2 + 3. `src/imdr/healthchecks/anomaly.py:78–79`

```python
ts_col = getattr(model, ts_column)
sym_col = getattr(model, symbol_column)   # ← never used
ser_col = getattr(model, series_column)   # ← never used
```

`getattr` calls with no side effect, results thrown away. Indicates the function used to project these columns somewhere and the projection was removed. Currently the column-name arguments `symbol_column` and `series_column` are not exercised by this code path at all.

**Risk**: medium — if `symbol_column`/`series_column` are documented parameters but ignored at runtime, callers passing them get silent no-ops. Worth verifying by tracing the function's callers.
**Suggested fix**: either remove the now-pointless `getattr` calls AND remove the dead parameters from the signature, or restore the projection logic the calls were feeding.

### 4. `src/imdr/healthchecks/quality.py:278`

```python
violating_syms = df[self._symbol_col].tolist()
if violating_syms:
    sym_list = ", ".join(f"'{s}'" for s in violating_syms[:5])   # ← never used
    detail_whens = []
    for sym, (lo, hi) in self._ranges.items():
        ...
```

`sym_list` is a comma-joined string of the first 5 violating symbols — looks like it was meant for an error message or log line that's not there anymore.

**Risk**: low — quality-check output may be missing a "violating: 'AAPL', 'MSFT', ..." string in some log/email.
**Suggested fix**: grep recent commits to see if a log line was deleted; either restore the log or delete the variable.

---

## F401 — Unused imports (27 findings)

Bulk-fixable: `python -m ruff check src/ --select F401 --fix`.

A few representative entries (see scanner output for full list):

| File | Import | Notes |
|---|---|---|
| `src/imdr/connectors/citi_quota.py:16` | `import time` | Probably orphan from an old timing branch |
| `src/imdr/domains/commodities/coverage.py:9` | `import pandas as pd` | Removed during a coverage rewrite |
| `src/imdr/domains/commodities/repository.py:16-18` | `CmdtyFactEIA`, `CmdtyFactImpliedVol`, `CmdtyFactSpot` | Re-exports that no caller uses |

**Risk**: zero functional impact; cosmetic + slightly slower import in some cases.

**Suggested fix**: run `ruff check src/ --select F401 --fix` once. Review the diff, ensure no re-exports get dropped that downstream code reaches via `from imdr.X import Y` (where Y is conceptually part of the public surface of X even if X itself doesn't use it).

---

## F821 — False-positive undefined names (2 findings, no action)

```
src/imdr/domains/equity/clean_index.py:25
    def detect(self, reader, table, where, params) -> "pd.DataFrame":
src/imdr/domains/equity/clean_index.py:46
    def build_action(self, row: "pd.Series") -> CleaningAction:
```

These are string-quoted forward references. `pd` is imported inside the function body (line 26), and the type hint is evaluated lazily because the file has `from __future__ import annotations`. Ruff's heuristic flags them but they work at runtime and pass mypy.

**Risk**: none.
**Suggested fix**: either move `import pandas as pd` to module top, or add `# noqa: F821` on the two lines. Style-only.

---

## Why this is a separate doc

These findings aren't related to the country-anchor restructure (none are Phase D regressions). Bundling them into the restructure docs would muddy the timeline. This file is a small, scoped tech-debt tracker that lives independently and can be ticked off opportunistically by anyone touching the relevant modules.

When fixing items, remove their entry from this doc (or note the commit that fixed them). Re-run `ruff check src/ --select F --statistics` after batch-fixes to keep this list current.
