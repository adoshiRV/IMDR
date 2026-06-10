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
