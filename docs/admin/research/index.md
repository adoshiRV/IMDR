# Research RAG — overview

IMDR's research-RAG system ingests sell-side research PDFs from
multiple vendor portals, parses them, splits into token-sized chunks,
embeds those chunks into a vector store, and writes everything to
``research.*`` tables for retrieval.

## Pipeline

The daily run for each vendor (`ingest_today_{vendor}.py`) has two
distinct halves: a **discovery + filter stack** that decides which
listings deserve to be ingested, then the **per-PDF pipeline** that
actually fetches, parses, embeds, and stores the chosen ones.

```
                        DAILY RUN PER VENDOR
                  ingest_today_{vendor}.py launches
                                │
                                ▼
            ┌───────────────────────────────────────┐
            │ 1. DISCOVERY                          │
            │    crawler_{vendor}.discover_reports  │
            │    Playwright + persistent profile;   │
            │    hits the vendor's listing API.     │
            └───────────────────┬───────────────────┘
                                │  list[ReportRef]
                                ▼
            ┌───────────────────────────────────────┐
            │ 2. DISCOVERY FILTER                   │
            │    filters/{vendor}.should_exclude    │
            │    Logs:  [SKIP] title-prefix:'invite:│
            │    Drops admin/logistics posts —      │
            │    invites, webcasts, conference      │
            │    calls, ANZ "5 in 5" podcast.       │
            └───────────────────┬───────────────────┘
                                │
                                ▼
            ┌───────────────────────────────────────┐
            │ 3. CLASSIFIER                         │
            │    classifiers/{vendor}.classify      │
            │    Returns ClassifyResult:            │
            │      asset_class, country_code,       │
            │      tags (ticker, region, country,   │
            │      discipline, vendor_pubtype),     │
            │      context (text blob for RAG).     │
            └───────────────────┬───────────────────┘
                                │
                                ▼
            ┌───────────────────────────────────────┐
            │ 4. RELEVANCE FILTER                   │
            │    ingest/relevance.                  │
            │     apply_relevance_filter            │
            │    Logs:  [DROP] single-name-equity:  │
            │    Drops single-name equity research; │
            │    see relevance_filter.md.           │
            │    Off-switch: settings.research_     │
            │     drop_single_name_equity = false   │
            └───────────────────┬───────────────────┘
                                │  refs that survived everything
                                ▼
            ┌───────────────────────────────────────┐
            │ 5. LIMIT CAP (optional)               │
            │    IMDR_RESEARCH_LIMIT=N truncates    │
            │    the post-filter list to N reports. │
            └───────────────────┬───────────────────┘
                                │
                                ▼

                    PER-PDF PIPELINE — for each surviving ref
                       (orchestrated by ingest_one in pipeline.py)

   ┌──────┐   ┌──────┐   ┌─────────────┐   ┌──────┐   ┌────────┐
   │ fetch│──▶│ parse│──▶│ idempotency │──▶│ chunk│──▶│ upload │
   └──────┘   └──────┘   │ (hash check)│   └──────┘   │OneDrive│
   Playwright PyMuPDF    │ skip if hit │  tiktoken    │SharePt │
                         └──────┬──────┘  cl100k      └────┬───┘
                                │ miss                     │
                                ▼                          ▼
                         ┌──────────┐  ┌─────────────────────────┐
                         │  embed   │─▶│ MSSQL transaction       │
                         │ Voyage/  │  │ research.dim_report     │
                         │ Gemini   │  │ + fact_chunk + map_tag  │
                         └──────────┘  │ (classifier output      │
                                       │  lands here)            │
                                       └──────────┬──────────────┘
                                                  │ commits first
                                                  ▼
                                       ┌──────────────────────────┐
                                       │ Qdrant upsert            │
                                       │ research_{model}_{dim}d  │
                                       │ point.id = fact_chunk.id │
                                       └──────────────────────────┘
```

Stages 2 and 4 are **pre-fetch gatekeepers**: anything they reject
never causes a PDF download, parse, embedding spend, or DB write. The
classifier (stage 3) runs twice — once before the filter for the
relevance check, again inside the MSSQL transaction at write time.
Both calls produce identical output, so payload tags stay consistent.

At write time the orchestrator also collapses the multi-valued
`Tag('region', ...)` output into the single `dim_report.region` column
via `region_from_tags()` from `classifiers/canonical.py`. See
[`region_country_enrichment.md`](region_country_enrichment.md).

**Observed daily volume** (24h samples; BNP from 2026-05-26 sample,
others from 2026-05-21):

| Vendor   | Discovered (post-filter) | Dropped (relevance) | Kept |
|----------|-------------------------:|--------------------:|-----:|
| anz      |                       18 |                   0 |   18 |
| barclays |                      236 |                 143 |   93 |
| bnp      |                       12 |                   0 |   12 |
| goldman  |                      271 |                 135 |  136 |
| hsbc     |                       11 |                   0 |   11 |
| ms       |                      280 |                 265 |   15 |
| nomura   |                       95 |                  29 |   66 |
| **total**|                  **923** |             **572** |  **351** |

Roughly 62% of post-filter discovery gets dropped at the relevance
stage; the remainder is what gets fetched, embedded, and indexed. See
[`relevance_filter.md`](relevance_filter.md) for the heuristic per
vendor and the trade-offs.

**BNP-specific filter note**: BNP's main drop happens at the
*discovery filter* (chart-pack boilerplate), not at the relevance
stage. ~21/day are discovered raw, ~9/day are chart-pack updates
matched by ``summary == "Update of the latest values"``, leaving ~12
into the relevance stage where none drop (BNP never tags
``tickers``/``issuers``). See [scrapers/bnp.md](scrapers/bnp.md#filter-scope--recommendation).

All code currently lives under [`playground/research/`](../../../playground/research/).
Promote to ``src/imdr/research/`` once the design is settled and the
crawlers stabilise across more vendors.

## Schema

Migrations applied (see [`migrations/`](../../../migrations/)):

* **032** — `research.dim_report` retrofit: adds `content_hash` (BINARY 32),
  `pdf_text` (NVARCHAR MAX), `page_count`, `parser_version`, `parsed_at`.
  Unique key flips from `(vendor_id, title, publish_date)` to `content_hash`
  (the hash is over watermark-stripped text — see "Watermark stripping"
  below).
* **033** — creates `research.fact_chunk`, `research.fact_chunk_embedding`,
  `research.dim_embedding_model`. Vectors were originally stored in
  `fact_chunk_embedding.vector` as `VARBINARY(MAX)`.
* **052** — adds report context (`asset_class`, `region`, etc.) to
  `research.dim_report`.

**`dim_report.region` enrichment (2026-06-14):** the `region` column was
blank on ~95% of sell-side reports even though region tags existed. Root
cause: the orchestrator hardcoded `region=""` instead of collapsing the
multi-valued `Tag('region', ...)` output. Fixed in `ingest_today.py` via
`region_from_tags()` from `classifiers/canonical.py`. A one-time backfill
populated 2,638 sell-side rows (apac 955, americas 673, global 647, emea
299, latam 64); a title-heuristic backfill set `country_id` on 132
additional rows (BoJ, RBA, FOMC, RBNZ, PBoC, RBI anchors). Econ/govt rows
with `ASIA-EM` / `ASIA-DM` region values were untouched. See
[`region_country_enrichment.md`](region_country_enrichment.md) for the full
spec, backfill scripts, verification results, and known remaining gaps.

Live state of the embedding tables:

* Vectors now live **only in Qdrant** (`127.0.0.1:6333`); the pipeline
  no longer writes `research.fact_chunk_embedding`. Migration 055
  drops the `vector` column from that table; the (chunk_id, model_id)
  link rows remain as a thin audit trail.
* `research.fact_chunk` is the system of record for chunk text + page
  spans. Its `id` is also the Qdrant point id (cross-system FK).
* `research.dim_embedding_model` is a small lookup table (one row per
  `(provider, model_name, dimensions)` triple) and remains populated.

All tables join via `report_id`/`chunk_id`/`model_id`. PAGE compression on
fact tables; clustered on natural access path.

## SharePoint layout

Files live under the IMDR-scoped subfolder of the
``TradeKnowledgeCore/ResearchData1`` SharePoint library, locally synced
to the user's OneDrive:

```
<ONEDRIVE_SYNC_ROOT>\
   2026/05/07/goldman/Strategy_Espresso_Europe_at_the_Margin_Inflection_a1647be2.pdf
   2026/05/07/anz/The_Philippines_Q1_2026_GDP_remains_sub_par_bb49e24d.pdf
   ...
```

Path format: ``{YYYY}/{MM}/{DD}/{vendor_code}/{slug}_{uuid_short}.pdf``,
where the slug is the title sanitised to alphanumeric + underscores
(max 80 chars) and `uuid_short` is the first 8 chars of the vendor's
docRef. See [`paths.py`](../../../playground/research/ingest/paths.py)
for the canonical builder.

**Hard rule**: IMDR writes ONLY under ``ResearchData1/IMDR/`` (locally
``Trade Knowledge Core - IMDR\``). See feedback memory
``feedback_sharepoint_research_scope.md``.

## Embedding models (switchable)

| Name | Provider | Dims | Status |
|---|---|---|---|
| `gemini-embedding-2` | Google | 3072 | **Active default** — has a live Qdrant collection (`research_gemini_embedding_2_3072d`). |
| `voyage-3-large` | Voyage / Anthropic | 1024 | Supported in code; no active Qdrant collection. Add a `CollectionSpec` to `qdrant_schema.SCHEMA` to activate. |
| `voyage-finance-2` | Voyage / Anthropic | 1024 | Supported in code; no Qdrant collection. Finance-tuned A/B candidate. |
| `gemini-embedding-001` | Google | 3072 | Supported in code; no Qdrant collection. Legacy v1, parity testing only. |

Switch per-run via env:

```
IMDR_RESEARCH_EMBED=true
IMDR_RESEARCH_EMBED_MODEL=gemini-embedding-2     # or voyage-3-large, etc.
```

`research.dim_embedding_model` auto-seeds new models on first use.
Vectors from different models can coexist (UNIQUE on `chunk_id, model_id`).

See [`playground/research/EMBEDDING_MODELS.md`](../../../playground/research/EMBEDDING_MODELS.md)
for selection guidance.

## Watermark stripping (idempotency)

Bank PDFs typically embed a per-download watermark — a 32-char hex
unique-id, the licensee's email, etc. Two downloads of the same logical
report therefore have different byte-level SHA-256 hashes, so byte-hash
isn't a stable dedup key.

**Solution**: hash the *normalised extracted text* with watermark patterns
stripped. See `_normalise_for_hash()` in
[`parse.py`](../../../playground/research/ingest/parse.py). Patterns:

* 32-char hex on its own line (Goldman download UID)
* "For the exclusive use of <email>" (most vendors)

Add new patterns when we discover new watermark formats.

## Vector store — Qdrant

Vectors moved out of MSSQL ``VARBINARY(MAX)`` into Qdrant for ANN
search at production scale. See [qdrant.md](qdrant.md) for the
storage location, collection layout, FK convention, and how to inspect.
For background on *why* HNSW + filtered ANN + (eventually) rerank, see
[retrieval_concepts.md](retrieval_concepts.md).

Quick commands:

```
# Show what's in the local store
python playground/research/inspect_qdrant.py

# Query the corpus
python playground/research/retrieve.py "your question"
```

Storage: the Qdrant Windows Service on ``127.0.0.1:6333``. See
[`docs/admin/qdrant/`](../qdrant/index.md) for setup, lifecycle, and
backup. The legacy embedded file store under
``playground/research/qdrant_local/`` was deleted on 2026-05-21; the
embedded mode hook in `QdrantWriter` still exists for offline unit
tests but is no longer the implicit default.

## MCP server (research retrieval from Claude Desktop)

> **Owner-only.** Unlike `imdr-db` (which is distributed to the team
> via the MCPB bundle under `docs/admin/setup/claude_desktop/`), the
> research MCP server is **single-user**. Qdrant is bound to
> `127.0.0.1:6333` on the owner's laptop only — nobody else on the
> network can reach it. The wiring lives in the owner's local Claude
> Desktop config; nothing in this repo's team-shared setup pipeline
> references it.

[`mcp/research_server.py`](../../../mcp/research_server.py) is a
self-contained MCP server (sibling to `mcp/server.py` for read-only
DB access) that exposes the research corpus to Claude Desktop via:

- `research_search` — semantic search over chunks → grouped citations.
- `research_get_report` — full metadata + chunk listing for one report.
- `research_list_vendors` — inventory of vendors with publication counts.

Wiring:

- Reads `IMDR_QDRANT_URL`, `IMDR_MSSQL_*`, `IMDR_VOYAGE_KEY`,
  `IMDR_GEMINI_KEY`, and `IMDR_RESEARCH_EMBED_MODEL` from `.env` via a
  small inline loader (the file deliberately does NOT import the
  `imdr` package to keep Claude Desktop's ~5-second startup budget).
- Default embedding model: `gemini-embedding-2` (matches `Settings.research_embed_model`
  and the only live Qdrant collection).
- Fails loudly if no Qdrant target is set — no silent fallback to an
  embedded file store.

### Owner-only recovery notes

If the owner's `imdr-mcp` conda env is ever rebuilt from
[`docs/admin/setup/claude_desktop/environment.yml`](../setup/claude_desktop/environment.yml)
— which intentionally carries only the SQL-MCP deps — re-add the
research-MCP extras locally:

```powershell
C:\Users\adoshi\.conda\envs\imdr-mcp\python.exe -m pip install qdrant-client voyageai google-genai
```

The Claude Desktop config on this machine is at the packaged-app
location (NOT `%APPDATA%\Claude\...`):

```
C:\Users\adoshi\AppData\Local\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude\claude_desktop_config.json
```

The `imdr-research` block sits alongside `imdr-db` with
`IMDR_QDRANT_URL=http://127.0.0.1:6333` and
`IMDR_RESEARCH_MSSQL_DRIVER=ODBC+Driver+18+for+SQL+Server` (research
needs Driver 18 for `VARBINARY` / `NVARCHAR(MAX)`; the SQL MCP works
on the legacy driver).

## Content quality

[`content_quality.md`](content_quality.md) — cross-cutting mechanisms
shipped 2026-06-15: prose-density gate (skips chart-pack/data-dump PDFs
at parse time), per-vendor series title drop-lists, deduplication fix
(pre-fetch `(vendor_code, pdf_path)` gate + `(vendor_id, date, title)`
fallback), and the repeatable coverage harness. Two reports removed from
the corpus: 471 surplus dim_report rows and ~11.7k surplus fact_chunk
rows across 13 vendors.

## Per-vendor scrapers

Each vendor has its own quirks (URL patterns, DOM structure, viewer
gates). See [`scrapers/`](scrapers/) for one doc per vendor. When
**adding a new vendor**, follow the end-to-end playbook in
[`onboarding_new_vendor.md`](onboarding_new_vendor.md).

| Vendor | Status | Doc |
|---|---|---|
| Goldman Sachs (Marquee) | live | [scrapers/goldman.md](scrapers/goldman.md) |
| ANZ (SingleTrack CMS) | live | [scrapers/anz.md](scrapers/anz.md) |
| Nomura Now | live | [scrapers/nomura.md](scrapers/nomura.md) |
| Morgan Stanley Matrix | live | [scrapers/ms.md](scrapers/ms.md) |
| HSBC Reach | live | [scrapers/hsbc.md](scrapers/hsbc.md) |
| Barclays Live | live | [scrapers/barclays.md](scrapers/barclays.md) |
| BNP Paribas Markets360 | live | [scrapers/bnp.md](scrapers/bnp.md) |
| J.P. Morgan Markets | TBD | [scrapers/jpm.md](scrapers/jpm.md) |

## Vendor authentication

See [`auth.md`](auth.md) — the central operator runbook for
[`src/imdr/research/auth/`](../../../src/imdr/research/auth/):
per-vendor auth mode table, CLI reference (`check` / `refresh` /
`login` / `status` / `validate`), typed error catalogue, email
triggers + recipient routing, heartbeat operator notes, and
troubleshooting.

## Running the daily ingest

**Canonical command** — always use the multi-vendor orchestrator with
embedding on:

```
IMDR_RESEARCH_EMBED=true python playground/research/ingest_today.py --vendors bnp
```

Omit `--vendors` to run all seven (anz, barclays, bnp, goldman, hsbc,
ms, nomura). Default window is `today-3d .. today` (SGT-anchored);
embedding model is `gemini-embedding-2`.

> **Use the orchestrator, not the per-vendor scripts.** The
> `ingest_today.py` orchestrator runs the per-vendor classifier and
> writes `asset_class` / `country` / `context` / tag links. The
> per-vendor `ingest_today_{vendor}.py` scripts **skip the classifier**
> — rows land "thin" (no context, no tags, `asset_class` = raw
> publication-type). This applies to all seven per-vendor scripts.
> Reserve them for discovery/fetch debugging only. Thin rows from a
> per-vendor run are skipped as content-hash duplicates on the next
> orchestrator run, so they must be deleted first to be re-ingested
> properly.

## Operational notes

* **DB driver**: research ingest uses a separate engine pinned to
  ODBC Driver 18 for SQL Server (the project default is the legacy
  "SQL Server" driver, which can't bind BINARY/NVARCHAR(MAX) parameters
  cleanly). The driver override lives in each runner's
  ``_research_engine()`` factory — leaves all other IMDR pipelines on
  the legacy driver.
* **Voyage free tier**: 3 RPM / 10K TPM. Embeddings sub-batched to stay
  under TPM and retry on RateLimitError. Production scale needs paid tier.
* **Concurrency**: pipeline is sequential per-vendor (Chrome locks the
  persistent profile dir to one process). Cross-vendor parallelism is
  fine. Batch ingest of N PDFs from one vendor is ~3-15s/PDF serially
  with embeddings off; embed-on adds ~70s/PDF on Voyage free tier.
* **Migration helper**: [`migrate_paths.py`](../../../playground/research/migrate_paths.py)
  rewrites paths in DB + moves OneDrive files. Default is dry-run;
  pass ``--apply`` to execute.

## Downstream — research consumption

Research rows land in `research.dim_report` + `research.fact_chunk`.
What consumes them downstream:

* **[Macro brief author spec](weekly_brief_spec.md)** — the canonical
  instruction set for producing RV-Capital-styled weekly + daily HTML
  briefs from ingested research + cross-asset IMDR data. Includes the
  design system pointer, per-section content rubric, data-source
  recipes, hard rules, and a pre-ship checklist. **[Lois sub-agent](../../../.claude/agents/lois.md)**
  reads this and ships briefs end-to-end. Assets (CSS + logo + reference
  HTML example) under [`brief_assets/`](brief_assets/).
* **Research MCP** — owner-only Qdrant MCP for ad-hoc semantic search
  (see project memory `project_research_mcp_owner_only`).

## Adjacent corpus: government policy filings

Starting 2026-06-10, the same `research.dim_report` + Qdrant + SharePoint
stack will also hold **official-source policy filings** (central bank,
ministries, regulators, statistical agencies). These do NOT touch the
sell-side scraper scaffold described above — no per-vendor crawlers,
no classifiers, no relevance filter. They're discovered by per-country
prod scripts (Korea first: [`playground/econ/kr/govt/`](../../../playground/econ/kr/govt/))
and pass through the same parse → chunk → embed → write pipeline via
a thin helper at [`src/imdr/research/filings.py`](../../../src/imdr/research/filings.py)
(full impl; migrations 086/087 applied 2026-06-10).

Discrimination is by `dbo.dim_vendor.vendor_category`:

* `sell_side` — JPM, MS, Goldman, BNP, Barclays, ANZ, Westpac, Nomura,
  HSBC, DB, SocGen, Standard Chartered, BofA, UBS, Citi (this doc's
  domain).
* `official_cb` / `official_ministry` / `official_regulator` /
  `official_thinktank` / `official_statistics` / `official_market_infra` /
  `official_supranational` — see [`migrations/086_add_dim_vendor_category.sql`](../../../migrations/086_add_dim_vendor_category.sql).

Mycroft and Lois blend both corpora by default; users can filter
via the payload field. See per-country docs for the official-source
inventory + URL recipes:

* [Korea — govt_doc_sources.md](../econ/korea/govt_doc_sources.md) —
  70+ Korean streams, 5 URL-shape clusters (RSS-fan, egov GET, egov POST,
  dt-list, JS-handler), per-agency PDF/body resolution recipes proven
  2026-06-10. Daily pull at [`playground/econ/kr/govt/daily_pull.py`](../../../playground/econ/kr/govt/daily_pull.py).
* Other countries (AU/ID/JP/IN/TH/PH): pending the Korea ingest going
  live then replication.

