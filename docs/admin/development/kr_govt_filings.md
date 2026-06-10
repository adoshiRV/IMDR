# Korea government policy filings — corpus extension

**Status**: **PROD-WIRED 2026-06-10.** Registered in `scripts/imdr_daily.py:PIPELINES`; runs daily under the existing IMDR cron.
**Started**: 2026-06-09 (inventory) → 2026-06-10 (probes + filings.py impl + first ingests + reviews + promotion + prod wire-up).

Extends the existing sell-side research corpus (`research.dim_report` +
Qdrant + SharePoint) to hold government policy filings from Korea — BoK
MPC text, MOEF press, MOTIR trade releases, FSC/FSS releases, KDI
publications. Same storage stack, no new tables.

## Why

Mycroft / Lois briefs currently only see sell-side commentary (JPM/MS/
Goldman/etc.) when answering "what does the market think about KRW?".
They have no access to **official voices** — BoK's own decision text,
MOEF's KTB issuance plans, FSC macroprudential rules. Adding govt
filings to the same RAG corpus closes that gap with one filter flag.

## Architecture decision

Reuse the existing pipeline, don't fork:

```
fetcher (per-agency) → FilingItem
                            │
                            ▼
                 src/imdr/research/filings.py::ingest_filing
                            │
                            ▼
        [skip: classifier, relevance filter]
                            │
                            ▼
            parse_pdf  OR  synthesize_document_from_text
                            │
                            ▼
            chunk_doc → embed → write to dim_report + Qdrant + SharePoint
```

Discrimination via new column `dbo.dim_vendor.vendor_category`:
- `sell_side` — existing 15 banks
- `official_cb` / `official_ministry` / `official_regulator` /
  `official_thinktank` / `official_statistics` / `official_market_infra` /
  `official_supranational` — new for filings
- `data_vendor` / `utility` — bloomberg, bidfx, MANUAL, HOLIDAYS_LIB, etc.

## Scope

| Vendor | Code | Category | Cadence | Body type |
|---|---|---|---|---|
| Bank of Korea | `bok` (new) | official_cb | ~1/day | PDF |
| Korea MoEF | `moef` (new) | official_ministry | ~5/day across 10 boards | HTML body |
| MOTIR (Trade/Industry/Resources) | `motir` (new) | official_ministry | ~2/day | HTML body (PDF TLS-blocked) |
| FSC | `fsc` (new) | official_regulator | ~0.4/day | PDF + HTML body |
| FSS | `fss` (new) | official_regulator | ~0.3/day | PDF |
| Korea Customs Service | `kcs` (new) | official_statistics | ~0 (stale boards) | JPG only — deferred |
| KDI | `kdi` (new) | official_thinktank | ~0.1/day | PDF via base64 atch_no |
| KOSTAT / MoDS | `mods` (existing id=24) | official_statistics | TBD | TBD |

Daily expected volume: **~9 items, ~275/month, ~32k Qdrant chunks/year**.
About 10% of current sell-side chunk volume.

## Built (2026-06-10)

| Artifact | Location | State |
|---|---|---|
| Inventory + URL recipes | [`docs/admin/econ/korea/govt_doc_sources.md`](../econ/korea/govt_doc_sources.md) (~870 lines) | done |
| Migration 086 — `vendor_category` column + CHECK + 47-row backfill | [`migrations/086_add_dim_vendor_category.sql`](../../../migrations/086_add_dim_vendor_category.sql) | **APPLIED 2026-06-10** |
| Migration 087 — 7 Korea vendor seeds | [`migrations/087_seed_kr_official_vendors.sql`](../../../migrations/087_seed_kr_official_vendors.sql) | **APPLIED 2026-06-10** |
| Filings helper | [`src/imdr/research/filings.py`](../../../src/imdr/research/filings.py) | **LIVE — full impl** (synthesize_document_from_text, ingest_filing, vendor/idempotency/qdrant helpers; vendor_code alnum guard; body content_hash vendor namespace) |
| Per-agency fetchers (7) | [`scripts/econ/kr/govt/fetch_*.py`](../../../scripts/econ/kr/govt/) | **PROMOTED to scripts/** — bok, moef, motir, fsc, fss, kcs, kdi |
| Per-agency resolvers | [`scripts/econ/kr/govt/resolvers.py`](../../../scripts/econ/kr/govt/resolvers.py) | **PROMOTED** — 7 resolvers (PDF or body) |
| Shared TLS-1.2 + URL allowlist | [`scripts/econ/kr/govt/_http.py`](../../../scripts/econ/kr/govt/_http.py) | **PROMOTED** — patient_get/post with `.go.kr`/`.or.kr`/`.re.kr` allowlist |
| Govt-filings daily ingest | [`scripts/econ/kr/govt/ingest_filings.py`](../../../scripts/econ/kr/govt/ingest_filings.py) | **PROMOTED + RENAMED** (was `daily_pull.py`) — `--ingest` / `--no-embed` / `--limit` / `--reset` / `--dry-run` |
| KR daily orchestrator | [`scripts/econ/kr/kr_daily.py`](../../../scripts/econ/kr/kr_daily.py) | **NEW (2026-06-10)** — inline filings-aware HTML email, parallel pattern to kr_weekly/kr_monthly |
| Registered in scheduler | [`scripts/imdr_daily.py:PIPELINES`](../../../scripts/imdr_daily.py) | **WIRED 2026-06-10** — `python -m scripts.econ.kr.kr_daily` runs under the daily cron |
| Mods backfill (one-off) | [`scripts/econ/kr/govt/backfill_mods.py`](../../../scripts/econ/kr/govt/backfill_mods.py) | done — 10 KOSTAT CPI releases re-ingested via filings.py |
| Cadence analysis + late-day probes | [`playground/econ/kr/govt/_explore/`](../../../playground/econ/kr/govt/_explore/) | kept in playground (exploration tools) |
| Runtime state (per-vendor) | `data/econ/kr/govt/{vendor}/{seen.json, snapshots/YYYY-MM-DD.json}` | per-vendor partition mirrors the SharePoint `econ/kr/{vendor}/` layout. Orchestrator log at parent `data/econ/kr/govt/_last_run.log`. Per-machine, gitignored under top-level `data/*` rule. |

Baseline daily-pull run captured **317 items across 7 agencies** in ~50s.
Smoke-ingest (with embeddings on) verified end-to-end: 21 + 10 = 41 reports
in `research.dim_report` (ids 5448-5478), 55+ chunks in Qdrant, 22 PDFs on
SharePoint at `{YYYY}/{MM}/{DD}/econ/kr/{vendor}/...`.

## Done (2026-06-10)

1. ~~Apply migrations 086 + 087~~ — **DONE**
2. ~~Implement `filings.py`~~ — **DONE**
3. ~~Per-agency `resolve_pdf` / `resolve_body` helpers~~ — **DONE**
4. ~~Add `--ingest` flag to ingest_filings.py~~ — **DONE**
5. ~~Multi-agent code/DB/docs/security review~~ — **DONE** (8 fixes applied: vendor_code alnum guard, URL allowlist, deferred-import hoisting, sys.path dedup, body content_hash namespace, obsolete probe deletion, doc accuracy)
6. ~~Promote `playground/econ/kr/govt/` → `scripts/econ/kr/govt/`~~ — **DONE** (rename `daily_pull.py` → `ingest_filings.py`)
7. ~~Build `scripts/econ/kr/kr_daily.py` with clean email~~ — **DONE** (inline HTML; subject `[IMDR Daily KR] ✓ all ok — N new filings, M chunks (T min)`)
8. ~~Wire into `scripts/imdr_daily.py:PIPELINES`~~ — **DONE 2026-06-10**

## Done (2026-06-11)

11. **BoK fetcher `menuNo=400007` bug fixed** — commit `9c9d1ae`. Server-side
    filter on `400007` capped the BoK firehose at ~250 items / 7 months.
    Switched to `menuNo=400423` (Press Releases) which returns the full
    5,000+ item firehose back to 2011-09-08. See [BoK gotcha](../econ/korea/govt_doc_sources.md#cluster-b)
    in `govt_doc_sources.md` for the probe data per menuNo. Smoke OK
    (30 items / 3 pages, content includes National Accounts, MSB notices,
    BoK working papers).
12. **One-off historical backfill helper** — [`scripts/econ/kr/govt/backfill_kr_govt.py`](../../../scripts/econ/kr/govt/backfill_kr_govt.py).
    CLI: `--vendor X --pages N --dry-run --no-embed --limit M`. Modelled
    on `backfill_mods.py`. Uses the same `discover()` + `_r.resolve()` +
    `ingest_filing()` pipeline as the daily so backfilled filings are
    indistinguishable from daily-ingested ones (same content_hash dedup,
    same seen.json update, same SharePoint path).
13. **Backfill — tight scope (complete 2026-06-11)** — embed=yes, 2h 17m total:
    - MOTIR `pages=20` → **152 ingested** (2026-01-26 → 2026-06-05), 0 dedup, 0 fail
    - FSS   `pages=25` → **230 ingested** (2024-04-29 → 2026-03-31), 0 dedup, 0 fail
    - FSC   `pages=50` → **978 ingested** (2020-04-13 → 2026-04-06), 2 dedup, 0 fail
    - BoK   `pages=50` → **468 ingested** (2025-04-11 → 2026-06-10), 32 dedup, **1 fail** (transient WinError 10053 on "Financial Statement Analysis for 2024" — auto-retried on next daily run)

    Total: **+1,828 filings → corpus 307 → 2,135**. Logs under [`playground/econ/kr_govt_docs/backfill_logs/`](../../../playground/econ/kr_govt_docs/backfill_logs/) (gitignored).

15. **BoK MSB-noise denylist** — commit `8b068a7`. Audit of the BoK 487-item slice found 131 (27%) were one-line MSB operational notices with zero macro commentary. Added `_DROP_TITLE_RE` in [`fetch_bok.py`](../../../scripts/econ/kr/govt/fetch_bok.py) to drop at discovery — items matching never enter the FilingItem stream, so no future re-ingest. Forward-only; the 131 noise rows already in DB are left in place (down-ranked by Mycroft relevance scoring).

## Storage layers per filing

Each filing writes to **3 or 4 layers** depending on source type. The SharePoint mirror is PDF-source only — body-text sources (HTML release prose, RSS feeds) are searchable via SQL + Qdrant only, no PDF artefact on the file share.

| Layer | What | Always written? |
|---|---|---|
| `research.dim_report` (SQL) | One row per filing — title, publish_date, vendor_id, content_hash, pdf_path | ✅ always |
| `research.fact_chunk` (SQL) | One row per ~800-token slice of body | ✅ always (both PDF and body-text sources) |
| Qdrant `research_gemini_embedding_2_3072d` | One vector per chunk; payload includes `vendor_category`, `country_code`, `doc_type`, `stream` | ✅ always (when `--ingest` runs with `embed=yes`) |
| **SharePoint PDF** at `{YYYY}/{MM}/{DD}/econ/kr/{vendor}/{slug}_{hash8}.pdf` | The original PDF (or fetched PDF for sources that publish PDFs only) | **❌ PDF sources only.** Body-text sources (MOEF RSS, MOTIR HTML, KCS HTML) skip SharePoint — there's no PDF to upload. |

Mechanism: SharePoint writes go via **local OneDrive sync** (`C:\Users\adoshi\OneDrive - RV Capital...\Trade Knowledge Core - IMDR\`) which OneDrive then uploads to the SharePoint library. See [[project-sharepoint-via-onedrive-sync]] in MEMORY for why this beats the Graph API path on this machine.

Per-vendor SharePoint mirror rate (post-backfill 2026-06-11):

| Vendor | Items | SP-mirrored | % |
|---|---|---|---|
| FSC | 998 | 838 | 84% (16% body-text fallback when PDF fails) |
| BoK | 487 | 467 | 96% |
| FSS | 250 | 247 | 99% |
| MOEF | 216 | 0 | 0% (RSS body) |
| MOTIR | 160 | 0 | 0% (HTML body, MOTIR PDF TLS-blocked from rvsg-fs01) |
| KCS | 10 | 0 | 0% (HTML body) |
| MODS | 10 | 10 | 100% |
| KDI | 4 | 4 | 100% |
| **TOTAL** | **2,135** | **1,749** | **82%** |

The 386 non-SP-mirrored items are still fully searchable (SQL + Qdrant) — Mycroft/Lois can ground macro reasoning on them; they just can't link to a PDF download.

## Current corpus state (2026-06-11)

**2,135 KR govt filings** across 8 agencies, all SQL + Qdrant indexed; 1,749 (82%) also mirrored to SharePoint:

| Agency | n | Coverage | Density |
|---|---|---|---|
| FSC  | 998 | 2020-04-13 → 2026-06-10 (6 yr) | Densest source — regulatory policy |
| BoK  | 487 | 2025-04-11 → 2026-06-10 (14 mo) | Shallow vs reachable; see backlog below |
| FSS  | 250 | 2024-04-29 → 2026-06-10 (2 yr) | Bank/insurer supervision |
| MOEF | 216 | 2009-03-31 → 2026-06-10 (17 yr) | RSS feeds — already deep |
| MOTIR | 160 | 2026-01-26 → 2026-06-10 (4.5 mo) | Capped on portal pagination |
| KCS | 10 | 2021-01-21 → 2024-11-21 | Stale board, deferred to Phase 2 |
| MODS | 10 | 2025-10-02 → 2026-06-02 (8 mo) | One-off backfill |
| KDI | 4 | 2026-04-13 → 2026-05-13 (2 mo) | Capped on landing pages |

## Backfill backlog

What's left to pull from upstream that we haven't yet:

### High-value, deferred pending decision

#### BoK 2011-2025 deep backfill

**Command**: `python -m scripts.econ.kr.govt.backfill_kr_govt --vendor bok --pages 500`

**What gets pulled** (upstream limits, confirmed by [`playground/econ/kr_govt_docs/probe_backfill_depth.py`](../../../playground/econ/kr_govt_docs/probe_backfill_depth.py) 2026-06-11):
- ~5,000 items reachable on `menuNo=400423`, dates 2011-09-08 → 2026-06-10
- ~487 already in DB (the post-fix recent slice)
- ~131 dropped at discovery by the MSB-noise denylist
- ≈ **~3,150 new keepers** after dedup + denylist

**Content composition** (sampled from the 2025-04 → 2026-06 slice already in DB, projected back):
- Monetary Policy Report (quarterly, ~60 across 15 years)
- Financial Stability Report (semiannual, ~30 across 15 years)
- MPB Minutes (~8/yr, ~120 across 15 years)
- BoK Working Papers + Issue Notes (~30/yr, ~450 across 15 years)
- Economic Outlooks (quarterly, ~60 across 15 years)
- Press releases for BoP, IIP, GDP advance, household credit, FX reserves, industrial loans (multi-hundred per year)
- Speeches by the Governor (~10/yr, ~150 across 15 years)
- Trade settlement / international investment position / official statistics releases

**Storage cost**:
- `dim_report`: ~3,150 rows
- `fact_chunk`: avg 15 pages × ~5 chunks/page ≈ **~47k chunks** (BoK PDFs are richer than FSC/FSS — Q3 2025 GDP release was 6 chunks alone)
- Qdrant: 47k × 3,072-dim vectors ≈ **~580 MB** added (compressed Voyage embeddings smaller than 16-bit dense; budget ~300-600 MB)
- SharePoint: ~3,000 PDFs × ~500 KB avg ≈ **~1.5 GB** added to the IMDR library

**Embed cost** (Voyage `voyage-3` + Gemini `gemini-embedding-2`, latest pricing seen on 2026-06-11 daily run):
- Voyage chunks: ~47k @ ~$0.12/1M tokens × ~600 tokens/chunk ≈ **~$3.40**
- Gemini summary calls: ~3,150 @ ~$0.001/call ≈ **~$3.15**
- **Total LLM spend: ~$7 one-off**

**Wall time**: tight-scope backfill ran 1,828 items in 2h 17m = ~4.5s/item. BoK deep adds ~3,150 items at higher per-item cost (richer PDFs, more chunks per item), call it **~4-5 hours background**. Same `backfill_kr_govt.py` script, idempotent via content_hash dedup, retryable per-item on failures.

**Why valuable**: 15 years of BoK policy text would push the KR macro-narrative corpus from 14 months → 15 years, covering 4 BoK governor terms (Kim Choongsoo · Lee Juyeol · Rhee Changyong · current), every easing + tightening cycle since 2011, and every FSR's view of household-debt buildup through the cycle. The single biggest macro-narrative coverage unlock available for KR.

**Why deferred**: ~4-5 hr unattended ingest + ~$7 spend is small but the user's call. Hold for now per 2026-06-11 decision.

### Bounded upstream (cannot extend further without other vendors)

| Item | Why bounded |
|---|---|
| FSS `pages=25` already exhausts the listing (no further pagination) | Going further would need stream-specific board IDs or POST search; not currently mapped. |
| MOTIR `pages=20` already exhausts | English portal caps at ~200 items / 6 months; Korean-side portal might have deeper but isn't mapped. |
| FSC `pages=50` likely has more (probe didn't go further) | Could try `pages=100` to test; deferred until BoK deep is decided. |
| KDI | Landing pages only — 4 items is the full visible catalogue. |
| KCS | Stale board (2024-11 latest). Live trade data lives on Korean-side URL not yet mapped (Phase 2). |
| MOEF | RSS already returns full history (216 items back to 2009). |

### Cleanup / housekeeping (not data-bearing)

| Item | Notes |
|---|---|
| Sweep-delete the 131 BoK MSB noise rows from `dim_report` + Qdrant + SharePoint | Only worth it if down-ranking proves insufficient. Pattern: `MSB Issuance Notice(...)` / `Notice for Competitive Bidding...` / `Regular MSB Fixed Rate Tender...`. |
| Retry the 1 transient BoK ingest fail | "Financial Statement Analysis for 2024" — picked up by next daily run automatically (not in seen.json). |

## Pending

9. Mycroft / Lois prompt updates — filter `vendor_category IN
   ('sell_side', 'official_*')` by default; document override flag for
   "sell-side only" mode. Specs (mycroft_brief_spec.md / weekly_brief_spec.md)
   updated; agent prompts (`.claude/agents/lois.md`, `.claude/agents/mycroft.md`)
   still need the explicit Qdrant-filter language.
10. Optional: build proper `fetch_mods.py` for daily MoDS discovery (the 10
    backfilled PDFs cover history; ongoing daily MoDS won't auto-ingest
    until a fetcher is added that uses Playwright like the playground
    `econ/mods/fetch.py`).
14. **BoK deep backfill (2011-2025)** — optional. After the tight scope
    above completes, BoK `--pages 500` would pull the remaining ~4,500
    items back to 2011-09-08 (15 years of MPR, FSR, minutes, working
    papers, economic outlooks). Highest macro-narrative coverage unlock
    available for KR. Cost: ~4 hr ingest + Voyage/Gemini embed for ~15k
    extra chunks. Deferred pending decision.

## Open items (do not block initial ingest)

1. **MOTIR PDF download** — body_text path covers the release prose
   (~5-10 KB/item); annexed tables/charts in the PDF are lost. Revisit
   with Playwright-rendered ingest if Mycroft outputs show gaps.
2. **KCS live boards** — the English News board is stale to 2024-11; the
   high-value 10-day trade quick estimates live on a different
   (Korean-side) URL not yet mapped. Defer to phase 2.
3. **OCR fallback** — no scanned PDFs encountered in any of the 7 live
   feeds. If a back-fill of pre-2015 BoK minutes is requested, add
   Gemini Vision (~$0.001/page) or Tesseract at that point.
4. **Tier-2 / Tier-3 Korea agencies** — FSC sub-streams, KIEP/KIF/KCIF/
   KIET/KLI/KIPF/KRIHS/STEPI/KEEI, NABO/NARS, KDIC/KDB/KEXIM/KAMCO/HF,
   KRX/KSD, NPS/KIC, etc. Adding each is one `INSERT INTO dim_vendor`
   + one fetcher module (~80 LoC).

## Replication to other countries

Pattern proves out at Korea → replicate to Australia, Indonesia, Japan,
India, Thailand, Philippines. Each country needs:
- Inventory (1-2 days research) — same shape as Korea's
  [`govt_doc_sources.md`](../econ/korea/govt_doc_sources.md).
- Migration NNN_seed_{country}_official_vendors.sql (~5-15 new rows).
- Fetcher modules per agency (most agencies already in dim_vendor — see
  the comprehensive 086 backfill).
- Per-country daily-pull orchestrator in `playground/econ/{country}/govt/`.

Estimated effort: **~8-10 hrs per country** after the Korea infra is
shipped.

## Related

- [`docs/admin/econ/korea/govt_doc_sources.md`](../econ/korea/govt_doc_sources.md) — Korea inventory + recipes (the working doc).
- [`docs/admin/research/index.md` §Adjacent corpus](../research/index.md#adjacent-corpus-government-policy-filings) — research-pipeline-side overview.
- Memory: [[project_bok_listcont_post_recipe]], [[project_motie_renamed_to_motir]], [[feedback_kr_govt_flaky_tls_patient_retry]].
