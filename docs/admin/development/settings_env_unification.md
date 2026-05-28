# Unify `IMDR_*` env-var consumers behind `Settings`

- **Filed**: 2026-05-14
- **Status**: partially mitigated 2026-05-21; full unification still deferred
- **Triggered by**: lean-pass review of `src/imdr/config/settings.py` (2026-05-14)

## 2026-05-21 update — partial mitigation

`Settings` now calls `dotenv.load_dotenv()` at import time, so `.env`
values are pushed into `os.environ`. Raw `os.environ.get(...)` callers
in `playground/research/ingest_today_*.py` therefore see `.env` values
without needing each script to load it. Two research keys
(`IMDR_RESEARCH_EMBED`, `IMDR_RESEARCH_EMBED_MODEL`) are also now
first-class `Settings` fields. The `extra="forbid"` blocker described
below is unchanged — there are still 13+ `IMDR_RESEARCH_*` keys not
declared on `Settings`.

## Current state

Two uncoordinated consumers read `IMDR_*` env vars from the same `.env`:

1. **`Settings`** in [src/imdr/config/settings.py](../../../src/imdr/config/settings.py) — pydantic-settings class with `env_prefix="IMDR_"`. 55 declared fields (`mssql_*`, `citi_*`, `bidfx_*`, `barclays_*`, `email_*`, `parquet_*`, `cache_*`, etc.). Used by 101 production callers across `src/` and `scripts/`.

2. **Direct `os.environ` reads** for `IMDR_RESEARCH_*` (15 keys: `_GS_*`, `_ANZ_*`, `_HSBC_*`, `_MS_*`, `_NOMURA_*`, `_QDRANT_*`, plus loop-control `_EMBED`, `_EMBED_MODEL`, `_SINCE`, `_UNTIL`, `_LIMIT`, `_PARALLEL`). Consumers:
   - [playground/research/](../../../playground/research/) — 12 ingest scripts (`ingest_today_*.py`, `ingest_one.py`, `explore_*.py`)
   - [mcp/research_server.py](../../../mcp/research_server.py) — separate research MCP server

## Problem

Because both consumers share the same prefix, we can't safely apply
`model_config = {"extra": "forbid"}` to `Settings`. With `forbid`,
pydantic-settings sees `IMDR_RESEARCH_*` in env, fails to find matching
fields on `Settings`, and raises at every `get_settings()` call.

So we lose the safety win we just added to `PipelineConfig` (typo
detection at startup) for the single most-imported module in the codebase.

## Options

1. **Add the research keys to `Settings`** — declare 15 more fields. Clutters
   the file but unifies the surface. Risk: research framework wants to evolve
   independently; declaring each new vendor cred on `Settings` is friction.

2. **Subclass with a longer prefix** — add `ResearchSettings(BaseSettings)`
   with `env_prefix="IMDR_RESEARCH_"`. Production `Settings` stays as-is.
   *Does not solve forbid* because main `Settings` would still match
   `IMDR_RESEARCH_*` via the shorter prefix and reject them as extras.

3. **Decouple the research prefix** — rename `IMDR_RESEARCH_*` → e.g.
   `RV_RESEARCH_*` in `.env`, `playground/research/*.py`, and
   `mcp/research_server.py`. Then `Settings(env_prefix="IMDR_") + forbid`
   only sees its own keys. This is the cleanest fix.

4. **Keep both, skip forbid** — accept the typo-detection gap. Document it.

## Recommendation

Pursue **option 3** when there's appetite for a small cross-cutting rename:

- Find/replace `IMDR_RESEARCH_` → `RV_RESEARCH_` (or another distinct prefix)
  across `.env`, `.env.example`, `playground/research/`, `mcp/research_server.py`,
  and `docs/admin/research/` references.
- Apply `model_config = {"extra": "forbid"}` to `Settings`.
- Verify `get_settings()` still loads in a clean shell.

Until then we are on **option 4** — `Settings` keeps `extra="ignore"` and we
accept that a typo in an `IMDR_*` env var silently falls back to the default.

## Out of scope

- Adding research vendor credentials to a proper `vendors/credentials.py`-style
  lookup. That's a research-framework refactor, not an env-prefix one.
- Splitting `Settings` itself into sub-models (`DatabaseSettings`,
  `CitiSettings`, etc.). Worth doing eventually but unrelated to the
  forbid question.
