# Follow-up: Drop string ccy columns from `FX.dim_currency_pair`

- **Date filed**: 2026-05-13
- **Status**: deferred (not in country-anchor restructure)
- **Triggered by**: design discussion during Phase E migration 043

## Current state (post migration 043)

`FX.dim_currency_pair` carries **both** string ccy refs and FK ids:

```
id, base_ccy (str), quote_ccy (str),
base_currency_id (FK -> dim_currency.id), quote_currency_id (FK -> dim_currency.id),
ccy_class
```

Migration 043 added the FKs alongside the strings for safety — every existing
consumer reads `base_ccy` / `quote_ccy` as strings, and rewriting all of them
was out of scope for the country-anchor restructure. The strings are now
redundant with the FKs but still authoritative for ~20 code points.

## Why drop the strings later

- **Two sources of truth**: `pair.base_ccy = 'AUD'` AND
  `pair.base_currency_id = dim_currency where code='AUD'`. Diverging from
  reality is silently possible (rename a currency, only one side updates).
- **FK enforces correctness**; the string column does not.
- **Schema clutter**: 4 columns to express what 2 FK ids already capture.

## Why we deferred it

20+ direct `pair.base_ccy` / `p.base_ccy + p.quote_ccy` accesses in code:

| File | Lines | Pattern |
|---|---|---|
| `src/imdr/data_access.py` | 124, 128 | raw SQL: `p.base_ccy + p.quote_ccy AS pair` |
| `src/imdr/domains/fx/coverage.py` | 91, 99, 112, 119, 126, 134, 164, 176, 189, 197, 204, 212 | raw SQL GROUP BY / SELECT |
| `src/imdr/domains/fx/pipeline_rate.py` | 142 | `pair_id_cache[(pair.base_ccy, pair.quote_ccy)] = pair.id` |
| `src/imdr/domains/fx/pipeline_rate_bbg.py` | 161 | same cache builder |
| `src/imdr/domains/fx/pipeline_vol.py` | 111 | same cache builder |
| `src/imdr/domains/fx/repository_vol.py` | 42–43, 49, 64 | `FXCurrencyPair.base_ccy == base_ccy.upper()` |
| `src/imdr/domains/fx/extractors_rate_bbg.py` | 269–270 | `out["base_ccy"] = src.base_ccy` |
| `src/imdr/models/fx_vol.py` | 35 | `__repr__` uses `self.base_ccy/self.quote_ccy` |

Refactoring these to JOIN through `dim_currency.code` is a focused but
substantial change. Doing it inside the country-anchor restructure would have
ballooned the change set without buying anything new — the country-anchor
goal was already met by `dim_currency.country_id`.

## Citi API impact (when we do this)

**None.** The Citi extractor returns `[base_ccy, quote_ccy]` STRING DataFrames
(extractor lives upstream of any DB lookup). The string→id resolution is
already isolated inside `FXCurrencyPairRepository.get_by_key()`, so the
public signature of that helper can stay the same — just its internal query
adds a JOIN to `dim_currency`.

## What needs to happen

### Phase 1 — refactor consumers (one PR per cluster)
1. `repository_vol.py:get_by_key()` — change internal query to JOIN
   `dim_currency` twice and filter by `code = :base / :quote`. Public
   signature unchanged.
2. `pipeline_rate.py`, `pipeline_rate_bbg.py`, `pipeline_vol.py` cache
   builders — replace `pair.base_ccy` access with eager-loaded
   `pair.base_currency.code` (add `relationship()` on the ORM model).
3. `coverage.py` — rewrite the 12 raw SQL queries to JOIN
   `dim_currency` for the projected `base_ccy + quote_ccy` strings.
4. `data_access.py` — same treatment.
5. `__repr__` on `FXCurrencyPair` — switch to using the relationship.

### Phase 2 — migration to drop the columns
- Migration `0NN_drop_fx_dim_currency_pair_strings.sql`:
  ```sql
  ALTER TABLE [FX].[dim_currency_pair] DROP CONSTRAINT uq_fx_dim_currency_pair;  -- on (base_ccy, quote_ccy)
  ALTER TABLE [FX].[dim_currency_pair] DROP COLUMN base_ccy;
  ALTER TABLE [FX].[dim_currency_pair] DROP COLUMN quote_ccy;
  CREATE UNIQUE INDEX uq_fx_dim_currency_pair_ids
      ON [FX].[dim_currency_pair] (base_currency_id, quote_currency_id);
  ```
- Update the ORM model `FXCurrencyPair` in `src/imdr/models/fx_vol.py` to
  remove the string columns and rely on the FK relationships.
- Update `FXCurrencyPairCreate` Pydantic schema to drop string fields.

### Phase 3 — run tests + smoke test pipelines
- `tests/unit/test_fx_*` — update any fixtures referencing `.base_ccy`/.quote_ccy
- Smoke test: run a daily Citi pull dry-run, verify pair lookup still works,
  verify fact rows write with correct `pair_id`.

## Watch-outs

- Pydantic schema `FXCurrencyPairCreate` is used by external seeders and the
  `bulk_seed_from_universe()` path. Changing its shape is a public-API change
  that needs every seed-script caller updated.
- `extractors_rate_bbg.py:269-270` writes `base_ccy/quote_ccy` keys into a
  result dict that downstream code reads — verify it's the in-memory shape
  that flows through translate/clean and not a DB column reference.

## Estimated effort

~1-2 days of focused work. Should be done as a single PR with all consumer
refactors and the migration in one shippable change, because the schema-only
migration breaks consumers and consumer-only refactors leave the schema
inconsistent.

## Related

- `migrations/043_fx_dim_currency_pair_add_country.sql` — the migration that
  added the FK columns alongside strings (this is the precursor)
- local Claude Code plan `okay-lets-do-that-validated-puzzle.md` — main
  restructure plan; this task is explicitly NOT in scope
- `docs/admin/development/visualization_monitoring.md`,
  `apac_macro_data_gaps.md` — other deferred work tracked here
