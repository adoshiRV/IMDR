# Follow-up: Rename `extractor._errors` → `extractor.errors` across all Citi extractors

- **Date filed**: 2026-05-15
- **Status**: deferred — cross-cutting rename, do as a single slice
- **Triggered by**: file 10 walk of [`src/imdr/domains/fx/extractors_vol.py`](../../../src/imdr/domains/fx/extractors_vol.py); same private-attr smell already cleaned up locally in [`extractors_rate.py`](../../../src/imdr/domains/fx/extractors_rate.py) (commit `ef2be5c`), [`extractors_rate_bbg.py`](../../../src/imdr/domains/fx/extractors_rate_bbg.py) (commit `edc6835`), and [`extractors_vol.py`](../../../src/imdr/domains/fx/extractors_vol.py) (this slice).

## The pattern

Every Citi extractor follows the same shape:

```python
class CitiVelocityXxxExtractor:
    def __init__(self, ...):
        ...
        self._errors: list[dict] = []   # leading underscore lie

    def extract(self, ...):
        ...
        except Exception as e:
            self._errors.append({...})

# Pipeline consumer:
extractor = CitiVelocityXxxExtractor(...)
self._extraction_errors = extractor._errors   # reach into "private"
df = extractor.extract(...)
```

The leading underscore is a lie — the list is part of the public contract.
The pipeline aliases it by reference *before* calling `extract()` so partial
state survives a mid-extract `TagQuotaExceeded` re-raise. Renaming to `errors`
removes the smell without changing behavior.

## Where the rename needs to land

The three FX extractors are already done. **Seven more callsites remain**, all
following the identical pattern:

| Extractor module | Pipeline consumer (`extractor._errors` callsite) |
|---|---|
| [`src/imdr/domains/commodities/extractors.py`](../../../src/imdr/domains/commodities/extractors.py) | [`pipeline_spot.py:73`](../../../src/imdr/domains/commodities/pipeline_spot.py#L73) |
| (same — single extractor for cmdty) | [`pipeline_eia.py:75`](../../../src/imdr/domains/commodities/pipeline_eia.py#L75) |
| (same) | [`pipeline_vol.py:83`](../../../src/imdr/domains/commodities/pipeline_vol.py#L83) |
| [`src/imdr/domains/rates/extractors.py`](../../../src/imdr/domains/rates/extractors.py) | [`rates/pipeline.py:161`](../../../src/imdr/domains/rates/pipeline.py#L161) |
| [`src/imdr/domains/rates/extractors_vol.py`](../../../src/imdr/domains/rates/extractors_vol.py) | [`rates/pipeline_vol.py:99`](../../../src/imdr/domains/rates/pipeline_vol.py#L99) |
| [`src/imdr/domains/equity/extractors.py`](../../../src/imdr/domains/equity/extractors.py) | [`equity/pipeline_index.py:73`](../../../src/imdr/domains/equity/pipeline_index.py#L73) |
| (same — single equity extractor for both pipelines) | [`equity/pipeline_vix.py:73`](../../../src/imdr/domains/equity/pipeline_vix.py#L73) |

Plus two docs that show the smell as example code:

- [`docs/admin/reference/citi_tag_quota.md:123`](../reference/citi_tag_quota.md#L123) — quoted snippet uses `extractor._errors`
- [`docs/admin/ops/new_product_playbook.md:384`](../ops/new_product_playbook.md#L384) — playbook example, will mislead future copy-paste

## Why one slice, not piecemeal

- The mechanical rename is identical across all 5 extractors. Bundling avoids
  five separate touches of `imdr_health_dashboard.py` (it imports several
  extractors via their pipeline wrappers).
- Test files for each domain assert against the private name in the same way
  the FX walk did — easier to do all the test-file edits in one PR.
- The two doc-snippet updates are trivial but easy to forget unless bundled
  with the code rename.

## Also bundle: the `tag_errors` parity fix

While we're here, audit whether each extractor passes `tag_errors=` to
`fetch_and_parse_batched`. The vol extractor was missing it before file 10's
fix (silent diagnostic gap on per-tag ERROR/EMPTY responses). The others may
have the same gap — worth a 5-minute grep when this slice lands:

```bash
rg "fetch_and_parse_batched" src/imdr/domains/ -A 8 | grep -B 1 "tag_errors"
```

Any extractor calling `fetch_and_parse_batched` without `tag_errors=…` is
silently dropping per-tag failures. Add `self.tag_errors: list[dict] = []`
in `__init__` + pass it through.

## Bigger opportunity worth pairing: base class for all Citi extractors

While doing the rename across 5 extractors, we'll be staring at how
**~80% identical** they all are. Side-by-side of just the two FX extractors
([extractors_rate.py](../../../src/imdr/domains/fx/extractors_rate.py),
[extractors_vol.py](../../../src/imdr/domains/fx/extractors_vol.py)):

| Component | Shared? | Per-extractor difference |
|---|---|---|
| `__init__(client, settings, universe, quota_tracker)` | ✅ identical | — |
| `self.errors` + `self.tag_errors` init | ✅ identical (after rename) | — |
| Pre-flight `tracker.check_budget(N, pipeline_name)` | ✅ identical | `pipeline_name` string |
| Per-pair loop with `fetch_and_parse_batched` | ✅ identical | tag list + response parser |
| `except TagQuotaExceeded: re-raise + log` | ✅ identical | — |
| `except Exception: capture in errors, continue` | ✅ identical | — |
| Empty-result `pd.DataFrame(columns=...)` | ✅ identical | output shape constant |

So a `BatchedCitiExtractor` base could be:

```python
class BatchedCitiExtractor(ABC):
    pipeline_name: ClassVar[str]
    empty_columns: ClassVar[list[str]]

    @abstractmethod
    def _build_tags_for_pair(self, c1: str, c2: str) -> list[str]: ...

    @abstractmethod
    def _response_parser(self, resp: dict) -> pd.DataFrame: ...

    @abstractmethod
    def _default_pair_list(self) -> list[tuple[str, str]]: ...

    def extract(self, start, end, pairs=None, frequency="DAILY") -> pd.DataFrame:
        # The shared loop — preflight budget, per-pair fetch, error capture,
        # tag_errors plumbing, concat.
```

Each concrete extractor shrinks to ~30 lines: declare the class-level constants
and implement three thin overrides.

### Why I'm not lifting it now

The project rule (`CLAUDE.md` "Don't add abstractions beyond what the task
requires") explicitly warns against premature abstraction — three similar
lines beats a base class. With only the two FX extractors visible mid-walk,
the abstraction wouldn't pay. It only pays when bundled with the
cross-domain rename above — touching all 5 extractors in one slice means
the base class lifts 5 × ~50 lines = ~250 lines of duplicate machinery in
one motion, with a single test surface for the shared loop.

### Sequencing inside that slice

When the cross-domain rename PR is opened:

1. First commit — **mechanical rename only** (`_errors` → `errors`,
   add `tag_errors` parity). Easy to review, easy to revert.
2. Second commit — **add `BatchedCitiExtractor` base** + add tests for it.
3. Third commit — **port each extractor to the base** one at a time, so
   per-domain breakages stay isolated.

That ordering means the rename PR is reviewable even if the base-class
extraction gets pushed to a follow-up.

## When to do this

Bundle as a **single slice across all 5 domains** before the Stage D per-domain
trim phases (commodities D4, rates D2, equity D3). The rename clears noise out
of those domains' files so the per-domain walks don't have to re-litigate the
same smell five times.

Effort: S for the rename alone; M when bundled with the base-class
extraction. All changes test-covered after the rename.
