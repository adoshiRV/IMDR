# Follow-up: `BasePipeline` ABC fits a 3-step shape; some pipelines are single-step

- **Date filed**: 2026-05-15
- **Status**: deferred — depends on the `healthchecks/` redesign that
  also re-decides the `pipelines/base.py` contract
- **Triggered by**: file 11 walk of [`src/imdr/domains/fx/pipeline_ohlc.py`](../../../src/imdr/domains/fx/pipeline_ohlc.py)

## What we see today

`BasePipeline[E, T, L]` expects three callables — `extract → transform → load`
— each returning a typed payload. `FXOHLCPipeline` fits awkwardly:

```python
class FXOHLCPipeline(BasePipeline[None, None, HourResult]):
    def extract(self) -> None:
        # All work delegated to process_hour() in load()
        return None

    def transform(self, raw: None) -> None:
        return None

    def load(self, data: None) -> HourResult:
        return process_hour(...)
```

Two of the three abstract methods are stubs. `process_hour` is a 7-step
orchestrator that internally does its own extract/transform/load — the
class is essentially "wrap `process_hour()` with the audit trail and
post-run hooks". The ABC contract is being abused as a sealed-shape
wrapper.

This was pinned in a test (`TestFXOHLCPipeline.test_extract_and_transform_are_noops`)
so the deferred refactor can find it.

## Why it's deferred

The `healthchecks/` redesign already on file
([`project_healthchecks_needs_rework.md`](../../../../../C:/Users/adoshi/.claude/projects/z--Business-Personnel-Arjun-GitHub-IMDR/memory/project_healthchecks_needs_rework.md))
will decide how every pipeline's `get_health_checks()` boilerplate flows.
That redesign touches the same `pipelines/base.py` surface — splitting the
"how do I shape my pipeline" decision across two refactors would create churn.

## Options when the redesign happens

1. **Single-step subclass** — add `SingleStepPipeline(BasePipeline)` that
   collapses `extract/transform/load` into one abstract method:
   ```python
   class SingleStepPipeline(BasePipeline[None, None, R]):
       @abstractmethod
       def run_step(self) -> R: ...
       # default implementations of extract/transform/load that funnel into run_step
   ```
   Cleanest if there are 3+ single-step pipelines today (verify by grepping
   `class .*Pipeline(BasePipeline\[None, None,`).

2. **Make the three steps optional** — let pipelines override only the
   methods they need. Type system support is awkward; semantic load shifts
   to the developer.

3. **Drop the ABC for single-step pipelines** — they get a thin `RunPipeline`
   protocol instead. The audit / hooks plumbing moves to a decorator or
   mixin.

## Other pipelines to check at the same time

Grep candidate single-step or two-step pipelines that hit the same shape:

```bash
rg "class .*Pipeline\(BasePipeline\[None, None," src/imdr/
rg "return None" src/imdr/domains/*/pipeline*.py -B 2 | grep "def extract\|def transform"
```

Likely fits: any pipeline whose real work is a single function call
(historical backfills, vendor-feed runners). Audit when the redesign starts.

## When to do this

Bundle with the `healthchecks/` redesign in Stage C5 (Domain base-class
extraction). Defer means: don't restructure `BasePipeline` mid-walk; just
note the smell and keep moving.
