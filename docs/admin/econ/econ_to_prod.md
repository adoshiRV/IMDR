# Econ → Production — prod-promotion playbook

Last updated: 2026-06-10

Sister doc to [`onboarding_new_country.md`](onboarding_new_country.md). That doc covers **discovery + playground build**; this doc covers **promoting playground work to production**.

> ## ⛔ HARD GATE — do not enter without user approval
>
> Promotion is a separate, gated workflow from discovery. Before touching anything in this doc, the prerequisites are:
>
> 1. Discovery work is **complete** per [`onboarding_new_country.md`](onboarding_new_country.md) — populated inventory docs, playground fetchers running end-to-end, sample parquet (Track A) and/or manifest snapshots (Track B) on disk.
> 2. Findings have been **summarised to the user** — what's covered, what's blocked, item/indicator counts.
> 3. The user has **explicitly approved** the promotion in this session, scoped to this country. A prior approval for a different country does NOT carry over. "Looks good" on a discovery summary is NOT promotion approval.
>
> If any of the three is missing, stop and ask. Promotion = creating files outside `playground/`, applying migrations, registering pipelines into schedulers. Each of these is hard-to-reverse and visible to the whole repo.

Reinforces [[feedback-no-prod-wiring-without-permission]] + [[feedback-playground-only-for-exploration]].

---

## What's promoted, by track

| Track | Discovery deliverable | Prod target |
|---|---|---|
| **A — Data series** | `playground/econ/{vendor}/{fetch_*.py, _{vendor}_*.py}` + `sample_output/*.parquet` | `src/imdr/domains/econ/{vendor}_*.py` (library) + `scripts/econ/{vendor}/{vendor}_{topic}.py` (fetchers) + `scripts/econ/{cc}/{cc}_monthly.py` (orchestrator) + `scripts/imdr_monthly.py:PIPELINES` (scheduler) → `econ.fact_indicator` |
| **B — Govt/CB documents** | `playground/econ/{cc}/govt/{fetch_*.py, daily_pull.py}` + `data/snapshots/*.json` manifests | `migrations/086_add_dim_vendor_category.sql` + per-country vendor-seed migration applied + `src/imdr/research/filings.py:ingest_filing()` complete + `scripts/econ/{cc}/{cc}_govt_daily.py` + `scripts/imdr_daily.py:PIPELINES` → `research.dim_report` + Qdrant + SharePoint |

---

## Track A — Phase G (Data series → prod)

> Lessons from Korea (2026-06-05) and Indonesia (2026-06-09) promotions. Both countries followed this sequence; it is the stable playbook.

### G.1 Hard rule — zero playground imports in prod

`scripts/econ/{vendor}/` and `src/imdr/domains/econ/` must have **zero `playground.*` imports**. Playground stays as the development surface; production is its own tree. Verify with a grep before any docs step:

```
grep -r "playground" scripts/econ/{vendor}/ src/imdr/domains/econ/
```

No matches = safe to proceed.

### G.2 Promotion sequence

**Step 1 — Promote helpers to `src/`.**
Copy `playground/econ/{vendor}/_{vendor}_*.py` to `src/imdr/domains/econ/{vendor}_*.py` (drop the leading underscore — they become first-class library modules). Update `_REPO_ROOT = Path(__file__).resolve().parents[N]` to match the new depth (typically `parents[4]` for `src/imdr/domains/econ/`).

**Step 2 — Re-implement fetchers as prod scripts.**
For each `playground/econ/{vendor}/fetch_*.py`, create `scripts/econ/{vendor}/{vendor}_{topic}.py`. Reference pattern: `scripts/econ/kosis/kosis_cpi.py`.

Required structure:
- Short docstring (1-2 paragraphs; trim playground exploration commentary)
- Imports from `imdr.domains.econ.{helper}` + `imdr.domains.econ.schema` + `scripts.econ._runner`
- `run_fetch(since, until) -> (indicators, observations)` — body lifted from playground, import paths swapped
- `main()` delegates to `scripts.econ._runner.run_main(vendor, topic, fetch_fn, description)`
- Strip: `sys.stdout = io.TextIOWrapper(...)`, `sys.path.insert(0, str(_REPO_ROOT))`, leftover `cli_main(...)` stubs

**Step 3 — Build the country orchestrator.**
`scripts/econ/{cc}/{cc}_monthly.py` calls `scripts.econ._country_runner.run(...)`. Do NOT fork a per-country `_runner.py` — `_country_runner.py` is parametrised by `country_code`, `country_label`, `country_name`, `orchestrator_path`, `pipelines`, `frequency_scope`. Reuse it.

**Step 4 — Register into the scheduler (GATED — explicit user sign-off required).**
Add the orchestrator to `scripts/imdr_monthly.py:PIPELINES`. **Build the code first; let the user flip the switch.** This is the single hardest-to-reverse step in the whole playbook — once it's in the scheduler the country starts writing to `econ.fact_indicator` on the next cron tick.

### G.3 One orchestrator, many cadences

`frequency_scope` accepts `["MONTHLY","QUARTERLY","SEMIANNUAL","ANNUAL","DAILY"]` in one bundle. Idempotent MERGE makes over-running cheap. Default: a single `{cc}_monthly.py`. Only add `{cc}_weekly.py` if the country actually has weekly-cadence data (Korea has REB; Indonesia doesn't).

For policy-rate-style series that change rarely (e.g. BIS `WS_CBPOL`), wire the fetcher into `scripts/imdr_daily.py:PIPELINES` *in addition to* the monthly bundle when 24h-latency matters. The same fetcher in both schedulers is fine — MERGE-on-PK makes daily re-runs free; monthly stays as backstop. Indonesia BIS uses this pattern.

### G.4 Schema additions land in two places

If the country needs a new `frequency_code` (e.g. `SEMIANNUAL` for BPS Sakernas), add to both:
- `src/imdr/domains/econ/schema.py:VALID_FREQUENCIES`
- `src/imdr/notifications/econ_snapshot.py:_STALE_DAYS`

A migration to seed `dbo.dim_frequency` is also required. **Migrations are drafted in this PR but applied separately by the privileged DB account** — never auto-apply.

### G.5 Category placeholder pattern

If a vendor emits a topic that doesn't fit an existing `dim_indicator_category` code, bucket it under `"other"` with a named constant + comment pointing at the follow-on work:

```python
# Bucketed under "other" until a dedicated "fiscal" code is added to
# econ.dim_indicator_category + VALID_CATEGORIES in
# src/imdr/domains/econ/schema.py. Tracked in
# docs/admin/econ/{country}/{cc}_coverage_plan.md (Phase E follow-on).
_FISCAL_CATEGORY_PLACEHOLDER = "other"
```

Also: avoid `if/elif` on a prefix string when building `imdr_code` — encode variable dimensions (suffix, category) as columns in your `_TABLES` row tuples instead.

### G.6 Code-review gate (HARD GATE)

Run `imdr-code-reviewer` on the new prod tree before touching docs. Hard checklist (8 items max):

1. Zero `playground.*` imports in `scripts/econ/{vendor}/` and `src/imdr/domains/econ/`
2. No back-compat shims for files deleted during generalisation
3. Existing countries (Korea) still pass their smoke tests
4. Fetcher structure matches `scripts/econ/kosis/kosis_cpi.py`
5. `imdr_code` built via dimension columns in `_TABLES`, not `if/elif` on a prefix string
6. Placeholder constants carry their rationale comment
7. `_REPO_ROOT` depth correct for new file location
8. No `sys.path` manipulation in prod scripts

Address all IMPORTANT findings before the docs step.

### G.7 Docs to update on prod-promotion

| Doc | What to do |
|---|---|
| NEW `docs/admin/econ/{country}/{country}_prod_pipeline.md` | Create mirroring `korea_prod_pipeline.md` section-by-section (architecture → library code table → cadence → invocation → CLI flags → archive layout → idempotency → failure modes → smoke tests → playground footer) |
| `docs/admin/econ/{country}/index.md` | Flip Phase G row to ✅; add Quick Links row to new prod-pipeline doc |
| `docs/admin/econ/{country}/{cc}_coverage_plan.md` | Strike "Phase G pending"; add prod-live timestamp |
| `docs/admin/econ/{country}/{country}_indicator_inventory.md` | Add a "Production fetchers" section listing the N prod fetcher modules |
| `docs/admin/econ/macro_economy_wiring_map.md` §{country} | Extend with prod-wiring sentence |
| `docs/admin/econ/economics_data_ingest.md` | Add country roster row referencing the orchestrator(s) |

Canonical prod-live wording for any of these docs:
> "Wired into `scripts/imdr_monthly.py:PIPELINES` YYYY-MM-DD"

Extend with `+ scripts/imdr_daily.py` if the country has a daily-bound fetcher.

### G.8 Email formatter

The country orchestrator's email report is produced by `imdr.notifications.formatters.country_econ_ingest.CountryEconIngestFormatter` (template at `templates/country_econ_ingest.html`). No per-country formatter needed — it's parametrised.

### G.9 Worked examples

- **Korea** — `docs/admin/econ/korea/korea_prod_pipeline.md`, `scripts/econ/kr/kr_monthly.py`, `scripts/econ/kosis/`
- **Indonesia** — `docs/admin/econ/indonesia/indonesia_prod_pipeline.md`, `scripts/econ/id/id_monthly.py`, `scripts/econ/{bps,bi,bis}/`

---

## Track B — Phase J (Govt/CB documents → prod)

> Track B promotion is younger than Track A — Korea is mid-flight (migrations drafted, awaiting apply) and Australia is one-off (RBA/Treasury/APRA fetchers landed 2026-06-10, no prod wiring yet). The shape below mirrors Phase G but discriminates by the storage layer: Track B writes to `research.dim_report` + Qdrant + SharePoint, **not** `econ.fact_indicator`.

### J.1 Hard rule — zero playground imports in prod

Same gate as G.1, applied to Track B paths:

```
grep -r "playground" scripts/econ/{cc}/govt/ src/imdr/research/filings.py
```

No matches = safe to proceed.

### J.2 Apply the one-time schema migrations (GATED — privileged DB account only)

If this is the **first country** lifting Track B to prod:

1. **`migrations/086_add_dim_vendor_category.sql`** — adds `vendor_category` column to `dbo.dim_vendor` with CHECK constraint covering the 10-value enum, backfills all existing rows (drafted from the Korea inventory; check that other Track-B-pending countries don't need new enum values), asserts zero NULLs post-backfill.
2. **`migrations/{NNN}_seed_{cc}_official_vendors.sql`** — seeds the new per-country agency rows (e.g. `bok` / `moef` / `motir` / `fsc` / `fss` / `kdi` for Korea, `rba` / `treasury_au` / `apra` for Australia) with `vendor_category='official_*'`.

Migrations are drafted in the PR; **applied by the privileged DB account in a separate step** — never auto-apply.

If a later country lifts Track B, only the per-country vendor-seed migration applies (086 is already done).

### J.3 Complete the ingest helper

`src/imdr/research/filings.py:ingest_filing(FilingInput) -> FilingResult` is currently a skeleton (`NotImplementedError`). Fill it in:

```
fetcher (per-agency) → FilingItem
                            │
                            ▼
                 src/imdr/research/filings.py::ingest_filing
                            │
                            ▼
        [skip: classifier, relevance filter — official sources are always-keep]
                            │
                            ▼
            parse_pdf  OR  synthesize_document_from_text
                            │
                            ▼
            chunk_doc → embed → write to research.dim_report + Qdrant + SharePoint
```

Two things that make Track B ingest **distinct from sell-side ingest**:

- **No classifier / relevance filter** — sell-side has aggressive single-name + sector-equity drop logic ([[project_research_relevance_filter]]); official sources are always macro/policy-relevant and always retained.
- **`body_text` path is first-class** — sell-side ingest assumes PDF in every case; Track B has agencies that publish HTML-only releases (MOEF, MOTIR body). `FilingInput` accepts EITHER `pdf_bytes` OR `body_text`; HTML-only sources go through `synthesize_document_from_text` → single-page Document → chunk → embed → write.

Delegate internals to existing primitives in `playground/research/ingest/` (parse, chunk, embed, upload, write) — do not fork. Reuse via re-export from the prod tree.

### J.4 Promote fetchers + orchestrator

**Step 1 — Promote helpers to `src/`.**
If `playground/econ/{cc}/govt/_models.py` / `_http.py` are vendor-agnostic enough to be cross-country reusable (the Korea + AU patterns are similar), promote to `src/imdr/research/filings_transport.py` (or per-purpose modules). Otherwise leave inline in `scripts/econ/{cc}/govt/`.

**Step 2 — Promote fetchers.**
For each `playground/econ/{cc}/govt/fetch_{agency}.py`, create `scripts/econ/{cc}/govt/fetch_{agency}.py` with the same structural cleanup as G.2 Step 2 (strip exploration commentary, swap imports, remove `sys.path` hacks).

**Step 3 — Build the daily orchestrator.**
`scripts/econ/{cc}/{cc}_govt_daily.py` runs all per-agency fetchers, dedupes via the rolling `seen.json` (path moves from `playground/.../data/` to the prod archive location), pipes each new item through `filings.ingest_filing()`, prints a per-agency summary table.

**Step 4 — Register into the scheduler (GATED — explicit user sign-off required).**
Add to `scripts/imdr_daily.py:PIPELINES`. Same gate as G.2 Step 4 — build first, user flips the switch. Once registered, the country starts writing govt filings to `research.dim_report` + Qdrant + SharePoint on the next daily cron.

### J.5 Code-review gate (HARD GATE)

Run `imdr-code-reviewer` on the new prod tree. Track-B-specific checklist:

1. Zero `playground.*` imports in `scripts/econ/{cc}/govt/` and `src/imdr/research/filings.py`
2. `filings.ingest_filing()` honours BOTH `pdf_bytes` and `body_text` paths
3. No relevance-filter / classifier code copied over from sell-side ingest
4. Per-agency fetchers all return uniform `FetchResult` of `FilingItem`
5. `seen.json` path is configurable (playground vs prod archive locations)
6. Migrations 086/{NNN} drafted with backfill assertions
7. No `dim_vendor` insert that omits `vendor_category`

### J.6 Docs to update on Track B prod-promotion

| Doc | What to do |
|---|---|
| NEW `docs/admin/econ/{country}/{country}_govt_prod_pipeline.md` | Mirror `{country}_prod_pipeline.md` but for the daily govt-doc orchestrator (architecture → fetcher table → cadence → invocation → archive layout → idempotency → failure modes → smoke tests) |
| `docs/admin/econ/{country}/index.md` | Flip Phase J row to ✅; add Quick Links row to the new prod-pipeline doc |
| `docs/admin/econ/{country}/{country}_govt_doc_sources.md` | Add "Production fetchers" section listing the N prod fetcher modules; flip per-agency status to LIVE |
| `docs/admin/development/{cc}_govt_filings.md` | Update execution tracker — flip "pending wiring work" items to done; record migration apply timestamps |
| `docs/admin/econ/economics_data_ingest.md` | Note country has a Track B daily-pull alongside the Track A monthly orchestrator |

Canonical prod-live wording:
> "Wired into `scripts/imdr_daily.py:PIPELINES` YYYY-MM-DD. Migrations 086 + {NNN} applied YYYY-MM-DD."

### J.7 Worked examples

- **Korea** — `docs/admin/development/kr_govt_filings.md` (execution tracker) + `docs/admin/econ/korea/govt_doc_sources.md` (inventory). 7 fetchers built in `playground/econ/kr/govt/`; migrations 086/087 drafted but **not yet applied**. Phase J **not yet entered.**
- **Australia** — 6 fetchers built in `playground/econ/au/govt/` (RBA × 4 via Playwright + Treasury + APRA via plain httpx). No execution tracker yet; no migrations drafted yet. Phase J **not yet entered.**

---

## Cross-refs

- [`onboarding_new_country.md`](onboarding_new_country.md) — sister doc (discovery + playground build)
- [country_econ_blueprint.md](country_econ_blueprint.md) — the indicator catalogue
- [macro_economy_wiring_map.md](macro_economy_wiring_map.md) — the 16-cell coverage tracker
- [economics_data_ingest.md](economics_data_ingest.md) — per-vendor build log
- [korea/](korea/) — Track A prod (LIVE): `korea/korea_prod_pipeline.md`. Track B prod: pending (migrations 086/087 drafted, awaiting apply)
- [indonesia/](indonesia/) — Track A prod (LIVE): `indonesia/indonesia_prod_pipeline.md`. No Track B yet
- [australia/](australia/) — Track A: pending Phase G. Track B: pending Phase J (6 playground fetchers live)
- [`../development/kr_govt_filings.md`](../development/kr_govt_filings.md) — Korea Track B execution tracker (template for other countries)
