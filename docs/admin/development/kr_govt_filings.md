# Korea government policy filings — corpus extension

**Status**: pre-flight complete, awaiting migrations 086/087 apply.
**Started**: 2026-06-09 (inventory) → 2026-06-10 (probes + daily pull + recipes).

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
| Migration 086 — `vendor_category` column + CHECK + 47-row backfill | [`migrations/086_add_dim_vendor_category.sql`](../../../migrations/086_add_dim_vendor_category.sql) | drafted, awaiting apply |
| Migration 087 — 7 Korea vendor seeds | [`migrations/087_seed_kr_official_vendors.sql`](../../../migrations/087_seed_kr_official_vendors.sql) | drafted, awaiting apply |
| Filings helper skeleton | [`src/imdr/research/filings.py`](../../../src/imdr/research/filings.py) | skeleton (NotImplementedError) |
| Per-agency fetchers (7) | [`playground/econ/kr/govt/fetch_*.py`](../../../playground/econ/kr/govt/) | live, all 7 tested |
| Daily-pull orchestrator | [`playground/econ/kr/govt/daily_pull.py`](../../../playground/econ/kr/govt/daily_pull.py) | live (manifest only) |
| Cadence analysis tool | [`playground/econ/kr/govt/analyze_cadence.py`](../../../playground/econ/kr/govt/analyze_cadence.py) | live |
| PDF/body resolution probes | [`playground/econ/kr/govt/probe_resolve.py`](../../../playground/econ/kr/govt/probe_resolve.py) + [`probe_resolve_v2.py`](../../../playground/econ/kr/govt/probe_resolve_v2.py) | done; recipes documented |

Baseline daily-pull run captured **317 items across 7 agencies** in ~50s.
Re-run on the same day reports 0 new items (dedup verified via seen.json).

## Pending — day-of-wiring work (~250 LoC)

1. Apply migrations 086 + 087 (privileged DB account).
2. Implement [`filings.py`](../../../src/imdr/research/filings.py):
   - `ingest_filing(FilingInput, embed=True, store_pdf_text=False) -> FilingResult`
   - `synthesize_document_from_text(body_text) -> Document` (~10 LoC)
   - `_resolve_vendor`, `_short_circuit_if_exists`, `_qdrant_payload_extra`
3. Per-agency `resolve_pdf(item)` / `resolve_body(item)` helpers
   (~20 LoC each × 6 agencies = ~120 LoC). Recipes already proven —
   see [`govt_doc_sources.md` §Per-agency resolution recipes](../econ/korea/govt_doc_sources.md#per-agency-body--pdf-resolution-recipes-probed-2026-06-10).
4. Add `--ingest` flag to `daily_pull.py` that pipes each new item
   through `ingest_filing()`.
5. Mycroft / Lois prompt updates — filter `vendor_category IN
   ('sell_side', 'official_*')` by default; document override flag for
   "sell-side only" mode.
6. Promote `playground/econ/kr/govt/` → `scripts/econ/kr/kr_govt_daily.py`
   for prod (only after a few days of clean daily-pull runs in playground).
7. Wire into `scripts/imdr_daily.py:PIPELINES` (user OK only).

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
- Memory: [[project-bok-listcont-post-recipe]], [[project-motie-renamed-to-motir]], [[feedback-kr-govt-flaky-tls-patient-retry]].
