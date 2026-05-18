# Follow-up: Shared `_run_quality_checks` dispatch helper

- **Date filed**: 2026-05-19
- **Status**: deferred — cross-cutting; do as a single slice
- **Triggered by**: imdr-code-reviewer agent review of the FX walk (commit `a8e98c4`)

## The pattern

Four pipelines repeat the same 15-line dispatch loop verbatim:

| Pipeline | Lines |
|---|---|
| [`src/imdr/domains/fx/pipeline_rate.py`](../../../src/imdr/domains/fx/pipeline_rate.py) | `~326-345` |
| [`src/imdr/domains/fx/pipeline_vol.py`](../../../src/imdr/domains/fx/pipeline_vol.py) | `~247-266` |
| [`src/imdr/domains/rates/pipeline_vol.py`](../../../src/imdr/domains/rates/pipeline_vol.py) | (verify line range when slice runs) |
| [`src/imdr/domains/commodities/pipeline_vol.py`](../../../src/imdr/domains/commodities/pipeline_vol.py) | (same) |

The block is byte-for-byte identical:

```python
for check, src_where in checks:
    try:
        qr = check.run(reader, table, where=src_where)
        self._quality_results.append({
            "check": qr.check_name,
            "status": qr.status.value,
            "message": qr.message,
            "flagged_count": qr.meta.get("total_violations")
            or qr.meta.get("outlier_count")
            or qr.meta.get("flagged_count"),
        })
        if qr.status != CheckStatus.PASSED:
            _log.warning("quality_flag", ...)
    except Exception:
        _log.exception("quality_check_failed", check=type(check).__name__)
```

The only variation per pipeline is **what goes into `checks`** and the `where` argument.

## The fix

Add a single shared helper in `src/imdr/healthchecks/quality.py` (the module
every caller already imports) or in a new `src/imdr/healthchecks/dispatch.py`:

```python
def run_quality_checks(
    checks: list[tuple[Any, str]],  # (check, src_where) pairs
    reader: AnalyticalReader,
    table: str,
    results_log: list[dict[str, Any]],
    log: structlog.BoundLogger,
) -> None:
    ...
```

Each pipeline then collapses 20 lines to:

```python
from imdr.healthchecks.dispatch import run_quality_checks
run_quality_checks(checks, reader, table, self._quality_results, _log)
```

## Coupled bug: `flagged_count` `or`-chain

The shared helper should also fix the silent bug where the count is `None`
when all three keys' values are `0` (because `0 or 0 or None = None`):

```python
# wrong: 0 is falsy, so a check that found 0 violations loses the 0
qr.meta.get("total_violations") or qr.meta.get("outlier_count") or qr.meta.get("flagged_count")

# right
next(
    (v for v in (
        qr.meta.get("total_violations"),
        qr.meta.get("outlier_count"),
        qr.meta.get("flagged_count"),
    ) if v is not None),
    None,
)
```

Better still: add `QualityResult.flagged_count` as a property on the base
class in `src/imdr/healthchecks/base.py` so the call-site is just
`qr.flagged_count`.

## Why now

- Removes a 60-line cross-domain duplication.
- Fixes the `0`-is-falsy bug at all 4 call sites at once (audit logs
  currently record `flagged_count: None` for any check that passed cleanly).
- Single import path for future pipelines.

## Why deferred

Cross-domain rewrite — needs to land all at once with a regression-guard
test that uses `inspect.getsource` to confirm none of the 4 pipelines
still contains the duplicated loop. Plan with the cleaning consolidation
([`cleaning_rules_consolidation.md`](cleaning_rules_consolidation.md)) and
the broader `healthchecks/` redesign (see
[`project_healthchecks_needs_rework.md`](../../../../../C:/Users/adoshi/.claude/projects/z--Business-Personnel-Arjun-GitHub-IMDR/memory/project_healthchecks_needs_rework.md)).

## Effort

S — one helper, four 20→3-line substitutions, one property on
`QualityResult`. Cross-domain test sweep to confirm no regressions.
