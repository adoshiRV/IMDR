# URGENT: Unit-test backlog triage

**Status:** 75 failing unit tests across 11 files. Discovered 2026-06-09
during the research-auth commit ([9dce13b](https://github.com/adoshiRV/IMDR/commit/9dce13b)).
None of these failures are caused by the auth work — they're
accumulated drift from prior sessions that landed implementation
without keeping tests in sync.

The auth commit was deliberately narrowed (36 files) to keep the
ledger clean. The remaining ~180 working-tree files (BBG specs,
Indonesia BPS, Korea econ, calendar reshuffle, vendor framework,
Qdrant, etc.) still need triage + commits — but **this doc is about
the failing tests, not the file backlog**. Get the tests green first;
the file backlog can land in coherent slices afterwards.

## Failing test files

```
tests/unit/test_bbg_fx_rate_pipeline.py
tests/unit/test_cmdty_universe.py
tests/unit/test_config.py
tests/unit/test_econ/test_abs_fetch.py
tests/unit/test_econ/test_fred_connector.py
tests/unit/test_econ/test_hkma_fetch.py
tests/unit/test_econ/test_rba_fetch.py
tests/unit/test_econ/test_schema_prototype.py
tests/unit/test_econ/test_statsnz_fetch.py
tests/unit/test_fx_rate_universe.py
tests/unit/test_rates_universe.py
```

Total: 75 failures, 1434 passing, 2 skipped (pytest -q output).

## Failure categories (sampled)

### 1. Contract drift — implementation widened, tests didn't follow

The biggest bucket. The code under test gained capabilities, the test
expectations weren't bumped.

**Example:** [`tests/unit/test_fx_rate_universe.py:76`](../../../tests/unit/test_fx_rate_universe.py#L76)

```
E   AssertionError: assert 946 == 462
     +  where 946 = len(['FX.SPOT.EUR.USD.CITI', ...])
```

The FX universe doubled in size (462 → 946 tags) — likely a real
universe expansion that should be reflected in the asserted count.

### 2. Settings shape drift

[`tests/unit/test_config.py`](../../../tests/unit/test_config.py) is
already noted as env-specific in [CLAUDE.md](../../../CLAUDE.md)
("test_config.py skipped in unit tests for env-specific ODBC mismatch").
Confirm it's still on the skip list or move it to an integration
folder.

### 3. Econ connector signature drift

`test_econ/` has the most failures (~50 spread across abs/fred/hkma/
rba/schema/statsnz). These are connector tests whose API endpoints,
response shapes, or row schemas have moved. Likely cohort:

- `test_fred_connector.py` — `TestFetchReleaseCalendar`,
  `TestFetchRecentUpdates`, `TestSearchSeries`,
  `TestRunCalendar`, `TestRunUpdatesSince`,
  `TestFredSeedLoad`, `TestFredClientApiKey`
- `test_hkma_fetch.py` — `TestBuildIndicator` (all `BBG ticker`
  assertions)
- `test_abs_fetch.py`, `test_rba_fetch.py`, `test_statsnz_fetch.py` —
  similar indicator-row shape mismatch
- `test_schema_prototype.py` — likely the underlying schema model
  changed shape

## Triage approach

Recommended order — one PR per file, smallest first:

1. **`test_config.py`** — confirm it's intentionally env-skipped per
   CLAUDE.md and `tools/pytest` markers. May just need a marker fix.
2. **`test_cmdty_universe.py`, `test_fx_rate_universe.py`,
   `test_rates_universe.py`** — universe expansion. Bump asserted
   counts to the new ground truth; spot-check the new entries make
   sense. ~5 tests each.
3. **`test_bbg_fx_rate_pipeline.py`** — transform shape change.
   Likely a single fixture update.
4. **`test_econ/test_schema_prototype.py`** — schema model. Fix
   first because hkma/abs/rba/statsnz tests probably depend on the
   same model.
5. **`test_econ/test_fred_connector.py`** — biggest cluster (~20
   tests). May reveal that the FRED client signature has fundamentally
   changed (e.g. `TestFredClientApiKey::test_accepts_fred_api_key_fallback`
   suggests a config-source change).
6. **`test_econ/test_hkma_fetch.py`, `test_abs_fetch.py`,
   `test_rba_fetch.py`, `test_statsnz_fetch.py`** — apply the same
   fixture pattern; these likely move together.

For each file:

1. Run failing tests in isolation (`pytest tests/unit/test_X.py -v`).
2. Read the failure messages — most are `AssertionError` with the
   expected vs actual value, which is enough to pick the fix.
3. Where the test is correct and the implementation has bugged out —
   fix the implementation. Where the implementation is the new ground
   truth — update the test.
4. Commit per file with a clear "test: refresh against current X
   shape" or "fix: restore X invariant" message.

## What's **not** in scope here

- The ~180 untracked / modified working-tree files (BBG specs,
  Indonesia BPS, Korea econ runner, calendar, etc.) — that's a
  separate audit. Some of those files probably introduced the test
  drift in this doc; landing them as coherent slices will surface
  more failures, so do this triage **first**.
- Integration tests (none of the failing tests live under
  `tests/integration/`).

## Linear

Tracked at [IMD-41](https://linear.app/imdr/issue/IMD-41/urgent-75-unit-tests-failing-across-11-files-triage-backlog) — Urgent priority, labels `tech-debt` + `Bug`, owner Arjun.

## Verification when done

```
C:/Users/adoshi/.conda/envs/imdr/python.exe -m pytest tests/unit/ -q --tb=no
```

Acceptance: 0 failed, ~1509 passed (1434 currently + 75 to fix), 2
skipped.
