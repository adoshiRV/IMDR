# Scenario Registry (dbo.dim_scenario)

**Last updated**: 2026-05-20
**Status**: Seeded — migrations 053 + 054 applied, all 25 scenarios live in `dbo`.

---

## Goal

A cross-domain, PM-curated table of historical market-stress windows (SVB crisis, COVID crash, Brexit, etc.) living in `dbo` so any fact table can slice against named scenarios without per-domain duplication.

## Why

25 scenarios were curated by the PM and need to be queryable across FX, rates, equity, and future domains. A `yml` universe file was rejected in favour of a proper DB dimension so foreign keys and indexed date-range lookups work natively.

## What Landed (2026-05-20)

- [x] `migrations/053_create_dim_scenario.sql` — 4 tables in `dbo`: `dim_scenario`, `scenario_window`, `dim_stress_tag`, `scenario_stress_tag`. PKs sized to cardinality (SMALLINT/TINYINT). Covering index `(start_date) INCLUDE (end_date, scenario_id)`. CASCADE on bridge only.
- [x] `scripts/migrations/seed_dim_scenario.py` — idempotent seed with all 25 PM scenarios; parses comma-list `stress_focus` into the tag bridge. All-or-nothing transaction.
- [x] `docs/admin/reference/scenarios.md` — schema doc + query patterns.
- [x] `tests/unit/test_seed_dim_scenario.py` — 18 passing unit tests covering pure-logic helpers and curated inventory.

## Three-Agent Review (pre-commit)

- **imdr-code-reviewer**: flagged missing tests (fixed), constraint-name nit (fixed), spurious `updated_at` writes (fixed).
- **imdr-security**: clean — parameterized SQL, no secrets, `dbo`-only scope, all-or-nothing transaction.
- **imdr-dbm**: flagged `name` as ODBC-reserved (renamed to `display_name`), missing `updated_at` columns (added), oversized PKs (narrowed to SMALLINT/TINYINT), index shape reworked to covering index.

## Seed execution notes (2026-05-20)

Seed ran on the third attempt — the legacy `SQL Server` ODBC driver tripped on `datetime.date` and Python `None` bindings to `DATE` columns. Documented here so the next seed-script author doesn't burn the same hour.

### The gotcha

Driver: `IMDR_MSSQL_DRIVER=SQL+Server` (legacy, not `ODBC Driver 17/18 for SQL Server`). When you bind a `datetime.date` parameter to a `DATE` column via `sqlalchemy.text()`, the driver raises:

```
pyodbc.Error: ('HYC00', '[HYC00] [Microsoft][ODBC SQL Server Driver]
                          Optional feature not implemented (0) (SQLBindParameter)')
```

Same error fires for a `None` parameter targeting `DATE`. `sqlalchemy.bindparam(... type_=Date())` does **not** rescue the type information through to pyodbc.

### What works

1. **Bind dates as ISO strings** (`start.isoformat()` → `'2020-04-20'`). SQL Server converts `VARCHAR` → `DATE` implicitly. This is the same trick used in [src/imdr/connectors/bulk.py](../../../src/imdr/connectors/bulk.py) for fact-table upserts.
2. **Inline `NULL`** in the SQL string for nullable date columns when the Python value is `None`. Don't bind `None`. Concretely: use two prepared statements — one with `:end`, one with the literal `NULL` — and pick at call time.

See `_INSERT_WINDOW_DATED` / `_INSERT_WINDOW_OPEN` in [scripts/migrations/seed_dim_scenario.py](../../../scripts/migrations/seed_dim_scenario.py) for the canonical small-batch pattern.

### When to use what

- **One-shot seed / migration script (≤ a few hundred rows)** — inline pattern in the seed file is fine.
- **Repeated fact-table writes (any volume)** — route through `bulk_merge()` in [src/imdr/connectors/bulk.py](../../../src/imdr/connectors/bulk.py), which stages DATE columns as `VARCHAR(10)` and lets SQL Server convert on MERGE. Do not re-invent.

### Related quirks already documented

- `use_setinputsizes=False` on the engine — needed for legacy-driver DATETIMEOFFSET compatibility (MEMORY.md).
- `dbo.dim_scenario.display_name`, not `name` — ODBC-reserved word (schema_conventions.md §1).

## Outstanding / Deferred

- [ ] No ORM model under `src/imdr/models/` — deferred until a consumer needs it.
- [ ] No `ScenarioRepository` abstraction — seed uses raw `sqlalchemy.text()`. Code reviewer flagged as "should fix, not must fix". Re-evaluate when first analytics caller arrives.

## Next Steps

When the first analytics consumer (e.g. scenario P&L query) is built:

1. Add `DimScenario` / `ScenarioWindow` ORM models under `src/imdr/models/`.
2. Promote raw `text()` upserts into a `ScenarioRepository` per the project repository pattern.
3. At that point the inline ODBC-string trick in the seed can move into the repository layer (or the repository can delegate to `bulk_merge`).

## Key Files

| File | Purpose |
|------|---------|
| `migrations/053_create_dim_scenario.sql` | DDL for all 4 tables + covering index |
| `scripts/migrations/seed_dim_scenario.py` | Idempotent seed — 25 PM scenarios |
| `docs/admin/reference/scenarios.md` | Schema doc + query patterns |
| `tests/unit/test_seed_dim_scenario.py` | 18 unit tests |
