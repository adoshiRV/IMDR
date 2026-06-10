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

> ## ⛔ HARD RULE — directory layout for prod (data strict country-first, scripts country-first, playground free-form)
>
> Codified 2026-06-10 after the country-first refactor (Phases 1-3) reshuffled every existing vendor. This is the contract every prod promotion must satisfy. Same wording lives at the top of [`onboarding_new_country.md`](onboarding_new_country.md) — repeated here because promotion is where it's tested.
>
> | Tree | Layout | Enforcement |
> |---|---|---|
> | `data/econ/` | **STRICTLY country-first.** `data/econ/{cc}/{vendor}/{topic}/{Y}/{M}/{D}/...` for series, `data/econ/{cc}/govt/{vendor}/...` for filings. **No vendor-at-root, ever.** Multi-country vendors slice per-country (`data/econ/id/bis/`, `data/econ/in/bis/`). | Enforced at runtime by `scripts/econ/_runner.py:_normalise_country_code` — mandatory keyword-only `country_code` on `run_main(...)`; raises `TypeError`/`ValueError`. |
> | `scripts/econ/` | **Country-first.** `scripts/econ/{cc}/{vendor}/{vendor}_{topic}.py` for series; `scripts/econ/{cc}/govt/...` for filings; orchestrators at `scripts/econ/{cc}/{cc}_{cadence}.py`. | Enforced by code review on every PR. No exceptions. |
> | `playground/econ/` | **Free-form** — vendor-first / multi-country / profile-dir shapes all OK during discovery. Soft preference: when discovery is single-country, prefer `playground/econ/{cc}/{vendor}/` to make promotion mechanical. | Not enforced — discovery is exploratory. The strict layout kicks in **at promotion**. |
> | `src/imdr/domains/econ/` | Vendor-keyed library code is country-agnostic. Library-side caches (e.g. `bi_seki.py:_RAW_DIR`) that bypass `_runner.py` must still encode the country in the path manually: `_REPO_ROOT / "data" / "econ" / "{cc}" / "{vendor}" / ...`. | Audited at code review — anywhere a raw `_RAW_DIR` or `_CACHE_DIR` constant is built, country must be in the path string. |
>
> **At promotion, the path swap is mechanical:**
> 1. Move `playground/econ/{vendor}/...` to `scripts/econ/{cc}/{vendor}/` (preserve git history with `git mv`).
> 2. Wire `country_code="{CC}"` into every `run_main(...)` call.
> 3. Adjust any `_REPO_ROOT = Path(__file__).resolve().parents[N]` — file moves one level deeper, `N` increases by 1.
> 4. `data/econ/{vendor}/...` from playground sample-output stays in playground; the prod tree always starts fresh under `data/econ/{cc}/{vendor}/` once the runner fires.
>
> Reinforces [[feedback-data-strict-country-first]]. See [project-econ-country-first-refactor-complete] for the 2026-06-10 retrofit (3 PRs across KR / ID / IN).

> ## ⭐ Korea is the complete reference — use it as the template
>
> As of **2026-06-10**, Korea has both tracks fully live in prod. Every file path, migration, doc, and orchestrator pattern below has a worked example sitting in the repo. When promoting a new country, the fastest correct path is to **`diff` against Korea's tree**:
>
> | Layer | Korea reference path |
> |---|---|
> | Discovery inventory (B) | [`korea/govt_doc_sources.md`](korea/govt_doc_sources.md) |
> | Domain library (A) | [`src/imdr/domains/econ/`](../../../src/imdr/domains/econ/) (kosis_http.py + schema.py) |
> | Per-vendor fetchers (A) | [`scripts/econ/kr/kosis/`](../../../scripts/econ/kr/kosis/) (19 fetchers) · [`scripts/econ/kr/reb/`](../../../scripts/econ/kr/reb/) |
> | Per-agency fetchers (B) | [`scripts/econ/kr/govt/fetch_*.py`](../../../scripts/econ/kr/govt/) (7 agencies) |
> | Per-agency resolvers (B) | [`scripts/econ/kr/govt/resolvers.py`](../../../scripts/econ/kr/govt/resolvers.py) |
> | Shared TLS/HTTP (B) | [`scripts/econ/kr/govt/_http.py`](../../../scripts/econ/kr/govt/_http.py) |
> | Govt-filings daily entry (B) | [`scripts/econ/kr/govt/ingest_filings.py`](../../../scripts/econ/kr/govt/ingest_filings.py) |
> | Country DAILY orchestrator (B) | [`scripts/econ/kr/kr_daily.py`](../../../scripts/econ/kr/kr_daily.py) (inline filings-aware email) |
> | Country WEEKLY orchestrator (A) | [`scripts/econ/kr/kr_weekly.py`](../../../scripts/econ/kr/kr_weekly.py) (uses `_country_runner.run`) |
> | Country MONTHLY orchestrator (A) | [`scripts/econ/kr/kr_monthly.py`](../../../scripts/econ/kr/kr_monthly.py) (uses `_country_runner.run`) |
> | Scheduler wiring | [`scripts/imdr_daily.py`](../../../scripts/imdr_daily.py) + [`scripts/imdr_weekly.py`](../../../scripts/imdr_weekly.py) + [`scripts/imdr_monthly.py`](../../../scripts/imdr_monthly.py) |
> | Track A prod-pipeline doc | [`korea/korea_prod_pipeline.md`](korea/korea_prod_pipeline.md) (covers all three cadences) |
> | Track B execution tracker | [`../development/kr_govt_filings.md`](../development/kr_govt_filings.md) |
> | Track A migrations | various per vendor (kosis, reb seeds) |
> | Track B migrations | [`migrations/086_add_dim_vendor_category.sql`](../../../migrations/086_add_dim_vendor_category.sql) (cross-country) + [`migrations/087_seed_kr_official_vendors.sql`](../../../migrations/087_seed_kr_official_vendors.sql) (per-country) |
> | Track B runtime state | `data/econ/kr/govt/{vendor}/` — `seen.json` (per-vendor rolling dedup) + `snapshots/{YYYY-MM-DD}.json` (per-vendor daily new-items manifest). `_last_run.log` at the parent (cross-vendor orchestrator output). Per-machine, gitignored via top-level `data/*` rule. Mirrors the country-first convention (`data/econ/{cc}/{vendor}/`) used everywhere post-2026-06-10 refactor AND the SharePoint vendor layout (`econ/kr/{vendor}/`). |
>
> Live state on Korea: **172 indicators × ~265k obs in `econ.fact_indicator`** (Track A) + **307+ filings, ~600 Qdrant chunks** in `research.dim_report` (Track B), self-sustaining daily.

---

## What's promoted, by track

| Track | Discovery deliverable | Prod target |
|---|---|---|
| **A — Data series** | `playground/econ/{vendor}/{fetch_*.py, _{vendor}_*.py}` + `sample_output/*.parquet` | `src/imdr/domains/econ/{vendor}_*.py` (library) + `scripts/econ/{cc}/{vendor}/{vendor}_{topic}.py` (fetchers — country-first per the HARD RULE) + `scripts/econ/{cc}/{cc}_monthly.py` (orchestrator) + `scripts/imdr_monthly.py:PIPELINES` (scheduler) → `econ.fact_indicator` |
| **B — Govt/CB documents** | `playground/econ/{cc}/govt/{fetch_*.py, daily_pull.py}` + `data/snapshots/*.json` manifests | `migrations/086_add_dim_vendor_category.sql` (cross-country, **applied 2026-06-10** for Korea) + per-country vendor-seed migration applied + `src/imdr/research/filings.py:ingest_filing()` complete + `scripts/econ/{cc}/govt/ingest_filings.py` (renamed from playground `daily_pull.py`) + `scripts/econ/{cc}/{cc}_daily.py` + `scripts/imdr_daily.py:PIPELINES` → `research.dim_report` + Qdrant + SharePoint |

---

## Track A — Phase G (Data series → prod)

> Lessons from Korea (2026-06-05) and Indonesia (2026-06-09) promotions. Both countries followed this sequence; it is the stable playbook.

### G.1 Hard rule — zero playground imports in prod

`scripts/econ/{cc}/{vendor}/` and `src/imdr/domains/econ/` must have **zero `playground.*` imports**. Playground stays as the development surface; production is its own tree. Verify with a grep before any docs step:

```
grep -r "playground" scripts/econ/{cc}/{vendor}/ src/imdr/domains/econ/
```

No matches = safe to proceed.

### G.2 Promotion sequence

**Step 1 — Promote helpers to `src/`.**
Copy `playground/econ/{vendor}/_{vendor}_*.py` to `src/imdr/domains/econ/{vendor}_*.py` (drop the leading underscore — they become first-class library modules). Update `_REPO_ROOT = Path(__file__).resolve().parents[N]` to match the new depth (typically `parents[4]` for `src/imdr/domains/econ/`). If the library module needs a raw-data cache (e.g. `bi_seki.py:_RAW_DIR`), bake the country into the path: `_REPO_ROOT / "data" / "econ" / "{cc}" / "{vendor}" / ...` — library-side paths bypass `_runner.py`, so the country-first contract has to be enforced manually.

**Step 2 — Re-implement fetchers as prod scripts.**
For each `playground/econ/{vendor}/fetch_*.py`, create `scripts/econ/{cc}/{vendor}/{vendor}_{topic}.py`. Reference pattern: `scripts/econ/kr/kosis/kosis_cpi.py`.

Required structure:
- Short docstring (1-2 paragraphs; trim playground exploration commentary)
- Imports from `imdr.domains.econ.{helper}` + `imdr.domains.econ.schema` + `scripts.econ._runner`
- `run_fetch(since, until) -> (indicators, observations)` — body lifted from playground, import paths swapped
- `main()` delegates to `scripts.econ._runner.run_main(vendor, topic, fetch_fn, description, country_code="{CC}")` — **`country_code` is mandatory keyword-only** (2-letter ISO, uppercase by convention; lowercased on disk). Omitting it raises `TypeError`; bad shape raises `ValueError`. Pinned in [feedback-data-strict-country-first].
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
4. Fetcher structure matches `scripts/econ/kr/kosis/kosis_cpi.py`
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

### G.8 Email + error logging (shared runtime — Track A)

The `scripts.econ._country_runner.run(...)` helper that every country orchestrator calls handles email + error logging the same way for all countries. **Do not fork**; configure via `Settings`.

#### Email — what fires and when

| Aspect | Detail |
|---|---|
| Sender | `imdr.notifications.email.send_outlook_email` — local Outlook COM via `win32com.client` (no SMTP, no Graph). Fails silently with a `win32com_not_available` warning if pywin32 isn't installed (e.g. in CI). |
| Recipient | `Settings.email_to` (semicolon-separated). Anomaly-style alerts use `Settings.email_anomaly_to` — not used by `_country_runner` itself but available for fetcher-level alerts. |
| Gate | `Settings.email_enabled=True` AND `Settings.email_to` non-empty. Otherwise logs `email_disabled_skipping_country_econ_summary` and returns 0/1 silently. |
| Formatter | `imdr.notifications.formatters.country_econ_ingest.CountryEconIngestFormatter` (template at `imdr/notifications/templates/country_econ_ingest.html`). Parametrised by `country_label` / `country_name` / `orchestrator_path` — no per-country formatter needed for Track A. |
| Subject | Built by `formatter.format_subject(run_name, new_rows, indicators_updated, stale_count, failed_pipelines)`. Convention: `[{country_label}] {run_name} econ ingest — {new_rows} new / {stale_count} stale[ / FAILED]`. |
| Body | `formatter.format_body(...)` — per-pipeline rc + elapsed, per-indicator new-rows-this-run, staleness flags, run duration, frequency scope. |
| Importance | `1` (normal) on full success, `2` (high) when any pipeline rc≠0. Outlook surfaces the red-bang badge for `2`. |
| Failure mode | Whole email-render-and-send wrapped in `try/except` — a broken template or COM failure logs `country_econ_email_failed` and prints the traceback but does NOT change the orchestrator exit code. |

One email per orchestrator run. If a country has both `{cc}_monthly.py` and `{cc}_daily.py`, expect two emails on the days both fire.

#### Error logging — structlog + run_log_dir

| Aspect | Detail |
|---|---|
| Library | `structlog` (configured in `imdr.utils.logging.configure_logging`). All log events are key-value structured. |
| Format | `Settings.log_format` = `"json"` (machine-parseable, prod default) or `"console"` (dev). |
| Level | `Settings.log_level` (default `"INFO"`). `log.exception(...)` always emits with traceback regardless of level. |
| Context | Use `structlog.contextvars.bind_contextvars(country=..., vendor=..., topic=...)` at the top of `run_fetch` — `merge_contextvars` will fold these into every event downstream. |
| Canonical events emitted by `_country_runner` | `country_econ_snapshot` (DB snapshot of post-run state — indicators / new rows / stale count) · `country_econ_snapshot_failed` (snapshot raised; email still attempts) · `country_econ_email_failed` (email render or send raised) · `email_disabled_skipping_country_econ_summary` (config gate not met) · `email_sent` (success, from `send_outlook_email`) |
| Fetcher-level | Each prod fetcher (`scripts/econ/{vendor}/{vendor}_{topic}.py`) is run as a **subprocess** — its stdout/stderr go straight to the parent's stdout/stderr. The orchestrator captures the rc and elapsed; it does NOT parse fetcher output. So per-fetcher structlog events land in console/cron logs, not in the email body. |
| Run-log archive | `Settings.run_log_dir` — used by the **vendors framework** (`src/imdr/vendors/runner.py`) for per-feed jsonl `RunReport` flush (`{run_log_dir}/vendors/{feed}/{feed}_{ts}.jsonl`). `_country_runner` does NOT write run-logs itself; if you need archived per-run state for an econ pipeline, route through the vendors framework or write jsonl explicitly from the fetcher. |

#### Failure-isolation semantics

`_country_runner` runs fetchers via `subprocess.call(cmd)` in a sequential loop, capturing rc + elapsed per pipeline. One fetcher's non-zero exit **does NOT abort** the loop — the orchestrator still:

1. Runs the remaining fetchers
2. Snapshots the DB for indicators in the country + frequency scope (this is the "what's actually in the database now" view — independent of fetcher rc)
3. Sends the consolidated email with `failed_pipelines=[...]` listed
4. Returns exit code `1` (so cron / `imdr_monthly.py` sees the run as failed)

Snapshot itself is `try/except` — DB outage logs `country_econ_snapshot_failed` but the email still goes out (with empty snapshots and an unhappy subject). Same for the email-send step. The principle: **partial visibility beats no visibility**.

#### `Settings` keys you'll touch

```
email_enabled         bool   default False
email_to              str    default ""   (semicolon-separated)
email_anomaly_to      str    default ""   (anomaly-style alerts; not used by _country_runner)
log_level             str    default "INFO"
log_format            str    default "console"   ("json" in prod)
run_log_dir           str    default ""          (vendors-framework artifact archive)
```

Set in `.env` (loaded by `pydantic-settings` via `imdr.config.settings.get_settings`). Never hard-code in scripts.

#### Smoke-test checklist before scheduler wiring

| Check | How |
|---|---|
| Email actually arrives | Set `email_enabled=True` + `email_to=<yourself>`, run the orchestrator manually with a fast subset, confirm the message lands in Outlook with the expected subject + body. |
| Subject reflects failure | Force one fetcher to fail (e.g. wrong env var), re-run, confirm `Importance=High` + `FAILED` in subject. |
| Snapshot survives DB outage | Disconnect / block the DB temporarily, run, confirm email still arrives with `country_econ_snapshot_failed` in console logs and empty snapshot section in body. |
| structlog JSON parses | `log_format=json`, pipe stdout to `jq` — should be one JSON object per line. |
| No secrets in body | The CountryEconIngestFormatter body is HTML; confirm no env-var values or connection strings appear. |

### G.9 Worked examples

- **Korea** — `docs/admin/econ/korea/korea_prod_pipeline.md`, `scripts/econ/kr/kr_monthly.py`, `scripts/econ/kr/kosis/`
- **Indonesia** — `docs/admin/econ/indonesia/indonesia_prod_pipeline.md`, `scripts/econ/id/id_monthly.py`, `scripts/econ/{bps,bi,bis}/`

---

## Track B — Phase J (Govt/CB documents → prod)

> Track B promotion is one-country live as of 2026-06-10 — **Korea is the reference implementation**: migrations 086 + 087 applied; `src/imdr/research/filings.py` is impl complete; `scripts/econ/kr/govt/ingest_filings.py` + `scripts/econ/kr/kr_daily.py` are wired into `scripts/imdr_daily.py:PIPELINES`; 41 filings landed in `research.dim_report` (ids 5448-5478), 55+ chunks in Qdrant, 22 PDFs on SharePoint at `{YYYY}/{MM}/{DD}/econ/kr/{vendor}/`. Australia is one-off (RBA/Treasury/APRA fetchers landed 2026-06-10, no prod wiring yet). The shape below mirrors Phase G but discriminates by the storage layer: Track B writes to `research.dim_report` + Qdrant + SharePoint, **not** `econ.fact_indicator`.

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

**Step 1 — Promote helpers + fetchers into `scripts/econ/{cc}/govt/`.**
Move `playground/econ/{cc}/govt/{_http.py, _models.py, resolvers.py, fetch_*.py}` to `scripts/econ/{cc}/govt/`. The fetchers use `sys.path.insert(0, Path(__file__).parent)` for the in-folder `_http`/`_models` imports — relative-to-file, survives the move. The `_http.py` could be promoted to `src/imdr/connectors/kr_govt_http.py` if cross-country re-use materialises, but for v1 leaving it inline at `scripts/econ/{cc}/govt/_http.py` is fine (each country's edges have different TLS quirks).

**Step 2 — Rename `daily_pull.py` → `ingest_filings.py`.**
The playground name was descriptive of the discovery action; in prod the canonical role is "daily filings ingest". Place at `scripts/econ/{cc}/govt/ingest_filings.py`. Module path becomes `scripts.econ.{cc}.govt.ingest_filings` — invokable from the country orchestrator.

**Step 3 — Build the country daily orchestrator.**
`scripts/econ/{cc}/{cc}_daily.py` is a thin orchestrator with `PIPELINES = [[sys.executable, "-m", "scripts.econ.{cc}.govt.ingest_filings", "--ingest"]]`. Sequence: run each pipeline subprocess → query `research.dim_report` for filings ingested at/after `run_started_at` → render + send a filings-aware email (see J.6). Future per-country daily entries (high-frequency rates, KRW spot, etc.) extend the same `PIPELINES` list.

> **Naming**: country-level daily orchestrator is `{cc}_daily.py` — not `{cc}_govt_daily.py`. Matches the existing `{cc}_monthly.py` / `{cc}_weekly.py` family. The govt-specific entry lives one level down at `scripts/econ/{cc}/govt/ingest_filings.py`.

**Step 4 — Register into the scheduler (GATED — explicit user sign-off required).**
Add `{"cmd": ["python", "-m", "scripts.econ.{cc}.{cc}_daily"], "estimated_tags": 0}` to `scripts/imdr_daily.py:PIPELINES`. Same gate as G.2 Step 4 — build first, user flips the switch. Once registered, the country starts writing govt filings on the next daily cron.

> **Reference impl (Korea, 2026-06-10):** `scripts/econ/kr/kr_daily.py` (~250 LoC, custom inline email runner — no separate `_country_govt_runner.py` needed; see J.6).

### J.5 Code-review gate (HARD GATE)

Run `imdr-code-reviewer` on the new prod tree. Track-B-specific checklist:

1. Zero `playground.*` imports in `scripts/econ/{cc}/govt/` and `src/imdr/research/filings.py`
2. `filings.ingest_filing()` honours BOTH `pdf_bytes` and `body_text` paths
3. No relevance-filter / classifier code copied over from sell-side ingest
4. Per-agency fetchers all return uniform `FetchResult` of `FilingItem`
5. Runtime state lives at `data/econ/{cc}/govt/{vendor}/` (NOT `scripts/econ/{cc}/govt/data/`, NOT a single shared `data/econ/{cc}/govt/seen.json`). Each agency gets its own `seen.json` + `snapshots/` subtree; the orchestrator log stays at the parent `data/econ/{cc}/govt/_last_run.log`. Centralise the path in `_models.py:DATA_DIR` + `vendor_dir(code)` + `vendor_seen_file(code)` + `vendor_snapshots_dir(code)` so `ingest_filings.py` + `resolvers.py` + `{cc}_daily.py` all import from one constant. `load_seen()` / `save_seen()` keep a flat-set API; partitioning happens at IO time via the `"{vendor}|{url}"` dedup-key convention.
6. Migrations 086/{NNN} drafted with backfill assertions
7. No `dim_vendor` insert that omits `vendor_category`

### J.6 Email + error logging (shared runtime — Track B)

Same `Settings`-driven stack as G.8: structlog with `log_format=json` + `log_level` for everything, `send_outlook_email` for the consolidated daily report, `run_log_dir` for any per-feed jsonl archive. Track-B-specific deltas:

| Aspect | Track A (G.8) | Track B (J.6) |
|---|---|---|
| Orchestrator runtime | `scripts.econ._country_runner.run(...)` — DB snapshot of `econ.fact_indicator` rows + `CountryEconIngestFormatter` | **Inline in `{cc}_daily.py`** — `_country_runner` is indicator-focused (queries `econ.fact_indicator`) and doesn't fit. The Korea reference impl puts the orchestration directly in `kr_daily.py` (~250 LoC): run subprocesses → query `research.dim_report` for filings created at/after `run_started_at` → render HTML email. No separate `_country_govt_runner` module — the orchestrator is small enough to read inline; new country_daily.py files copy the same pattern. |
| Formatter | `CountryEconIngestFormatter` (parametrised — one for all countries) | **Inline HTML in `{cc}_daily.py:_render_email()`** — small enough not to warrant a Jinja template. Body: pipeline-results table, per-vendor filings table (vendor_code · display_name · category · n_reports · n_chunks), top-5 recent titles. Mirror the structure when adding au_daily/id_daily/etc. — promote to a shared formatter once 3+ countries are live. |
| Subject line | `[{cc}] {run_name} econ ingest — {new_rows} new / {stale} stale` | `[IMDR Daily {CC}] ✓ all ok — {N} new filings, {M} chunks ({duration} min)` (or `⚠ X failed` instead of `✓ all ok`). Korea pattern is `[IMDR Daily KR]`. |
| Failure-isolation | Per-fetcher subprocess; one fetcher's rc≠0 doesn't abort others; partial DB snapshot still emails | Per-fetcher subprocess (same shape). **Additionally**: per-`FilingItem` failures inside `ingest_filing()` (PDF parse error, Qdrant timeout, SharePoint auth refresh) are caught at the item level inside `ingest_filings.py:_one()` — one bad filing logs `[ingest-fail]` and skips, doesn't poison the run. The orchestrator's pipeline_results entry stays `rc=0`. Failed items aren't added to seen.json so they retry next run. |
| Importance | `1` normal, `2` on any pipeline rc≠0 | Same: `1` normal, `2` on any pipeline rc≠0. |
| Anomaly channel | Optional, via `email_anomaly_to` | Not yet used in the Korea reference. Add if degenerate-content detection (zero-page PDF, body_text < 200 chars) becomes a recurring concern — keep separate from the per-run summary so it doesn't drown in noise. |
| Smoke checks (see G.8 list) | All apply | All apply, plus: `python -m scripts.econ.kr.kr_daily --no-email` end-to-end ingest works without sending mail (useful for first prod-run sanity). Confirm Qdrant rollback is clean when an item fails partway. |

`Settings` keys are the same as G.8 — no new env vars unless the filings runtime needs a separate recipient list (don't add one unless asked).

**Korea reference (2026-06-10):** [`scripts/econ/kr/kr_daily.py`](../../../scripts/econ/kr/kr_daily.py) — `PIPELINES` list (1 entry: `scripts.econ.kr.govt.ingest_filings --ingest`), `_filings_snapshot()` query, `_render_email()` HTML builder, `send_outlook_email()` call. Replicate the shape; do not refactor into a shared runner until 3+ countries are live and the abstraction is forced.

### J.7 Docs to update on Track B prod-promotion

| Doc | What to do |
|---|---|
| NEW `docs/admin/econ/{country}/{country}_govt_prod_pipeline.md` | Mirror `{country}_prod_pipeline.md` but for the daily govt-doc orchestrator (architecture → fetcher table → cadence → invocation → archive layout → idempotency → failure modes → smoke tests) |
| `docs/admin/econ/{country}/index.md` | Flip Phase J row to ✅; add Quick Links row to the new prod-pipeline doc |
| `docs/admin/econ/{country}/{country}_govt_doc_sources.md` | Add "Production fetchers" section listing the N prod fetcher modules; flip per-agency status to LIVE |
| `docs/admin/development/{cc}_govt_filings.md` | Update execution tracker — flip "pending wiring work" items to done; record migration apply timestamps |
| `docs/admin/econ/economics_data_ingest.md` | Note country has a Track B daily-pull alongside the Track A monthly orchestrator |

Canonical prod-live wording:
> "Wired into `scripts/imdr_daily.py:PIPELINES` YYYY-MM-DD. Migrations 086 + {NNN} applied YYYY-MM-DD."

### J.8 Worked examples

- **Korea — LIVE 2026-06-10.** Phase J complete. Reference impl for all future Track B promotions.
  - 7 fetchers + resolvers + `_http` + `_models` + `ingest_filings.py` at [`scripts/econ/kr/govt/`](../../../scripts/econ/kr/govt/)
  - Country daily orchestrator: [`scripts/econ/kr/kr_daily.py`](../../../scripts/econ/kr/kr_daily.py) (inline filings-aware email)
  - Migrations 086 (vendor_category column + 47-row backfill) + 087 (7 KR agency seeds) applied
  - Registered in [`scripts/imdr_daily.py:PIPELINES`](../../../scripts/imdr_daily.py)
  - 41 reports / 55+ Qdrant chunks / 22 PDFs at canonical SP layout
  - Execution tracker: [`docs/admin/development/kr_govt_filings.md`](../development/kr_govt_filings.md)
  - Inventory + URL recipes: [`korea/govt_doc_sources.md`](korea/govt_doc_sources.md)
- **Australia** — 6 fetchers built in `playground/econ/au/govt/` (RBA × 4 via Playwright + Treasury + APRA via plain httpx). No execution tracker yet; no migrations drafted yet. Phase J **not yet entered.** Replicate the Korea pattern when promoting.

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
