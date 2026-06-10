# Australia government policy filings — prod pipeline

**Status:** **PROD-BUILT 2026-06-11.** Migration 092 applied; `scripts/econ/au/govt/` + `scripts/econ/au/au_daily.py` in place; smoke `--ingest --limit 8` proven 8 of 8 official streams flowing end-to-end. **Final gate remaining**: registration in `scripts/imdr_daily.py:PIPELINES` (separate user sign-off per playbook hard rule).

Sister doc to `australia_prod_pipeline.md` (Track A — econ.fact_indicator). This doc covers Track B — `research.dim_report` + `research.fact_chunk` + Qdrant + SharePoint.

## Architecture

Same shape as Korea (the reference impl). Reuses `imdr.research.filings.ingest_filing` end-to-end:

```
fetch_{agency}.discover()  →  FilingItem rows
                                    │
                                    ▼
                       scripts.econ.au.govt.resolvers.resolve(item)
                       dispatches by `item.stream` →  ("pdf", bytes)
                                    │
                                    ▼
                       imdr.research.filings.ingest_filing
                                    │
                                    ▼
       [no classifier / no relevance filter — official sources always-keep]
                                    │
                                    ▼
       parse_pdf → chunk_doc → embed → write to:
         - research.dim_report     (1 row per filing, idempotent on content_hash)
         - research.fact_chunk     (N chunks per filing)
         - Qdrant collection       (1 vector per chunk, vendor_category in payload)
         - SharePoint mirror       ({YYYY}/{MM}/{DD}/econ/au/{vendor}/{slug}_{hash}.pdf)
```

Three resolver flavours, dispatched on `item.stream`:

| Flavour | Streams | How |
|---|---|---|
| Akamai-bypass render-to-PDF | `rba_governors_statement` · `rba_board_minutes` · `rba_speeches` | Fresh-profile headed Chrome (RBA 403s plain GET) → `page.emulate_media("print")` → `page.pdf(A4)` |
| Publisher-PDF fetch | `rba_smp` · `rba_fsr` | Same Akamai-bypass page nav, regex the `.pdf` link in the rendered HTML, `ctx.request.get()` against the warmed cookie session |
| Headless render-to-PDF | `treasury_publications` · `apra_{adi,gi}_performance` · `abs_{cpi,labour_force,national_accounts}_release` | Headless Chrome (no gating) → same `page.pdf()` |

Westpac CCI and NAB BSI **excluded** — both are `vendor_category='sell_side'` which `imdr.research.filings.ingest_filing` rejects. Westpac is already covered by sell-side ingest (`playground/research/ingest/crawler_westpac.py`); NAB has no sell-side fetcher yet.

## Fetcher table

8 production fetchers in `scripts/econ/au/govt/`, all returning a uniform `FetchResult` of `FilingItem`:

| Fetcher | Vendor | Stream | Cadence | Transport |
|---|---|---|---|---|
| `fetch_rba_governors_statement` | `rba` | `rba_governors_statement` | ~8/yr (cash-rate meetings, T+0) | Playwright Akamai bypass |
| `fetch_rba_board_minutes` | `rba` | `rba_board_minutes` | ~8/yr (T+14 after meeting) | Playwright Akamai bypass |
| `fetch_rba_smp` | `rba` | `rba_smp` | Quarterly (Feb / May / Aug / Nov) | Playwright Akamai bypass |
| `fetch_rba_fsr` | `rba` | `rba_fsr` | Semi-annual (Apr / Oct) | Playwright Akamai bypass |
| `fetch_rba_speeches` | `rba` | `rba_speeches` | Filtered (~25/yr after role + keyword filter) | Playwright Akamai bypass |
| `fetch_treasury` | `treasury_au` | `treasury_publications` | Variable (multiple per week) | plain httpx + headless Playwright (for resolver) |
| `fetch_apra_quarterly` | `apra` | `apra_adi_performance` / `apra_gi_performance` | 2/quarter | plain httpx + headless Playwright |
| `fetch_abs_commentary` | `abs` | `abs_cpi_release` / `abs_labour_force_release` / `abs_national_accounts_release` | Monthly / quarterly | plain httpx + headless Playwright |

## Invocation

Day-to-day prod entry point:

```
python -m scripts.econ.au.au_daily
```

This subprocesses `scripts.econ.au.govt.ingest_filings --ingest`, then queries `research.dim_report` for new AU filings and emails the daily summary.

Smoke / dev variants:

```
python -m scripts.econ.au.govt.ingest_filings --dry-run    # discover only, no writes
python -m scripts.econ.au.govt.ingest_filings --ingest --limit 3   # smoke 3 items
python -m scripts.econ.au.govt.ingest_filings --reset      # wipe per-vendor seen.json
python -m scripts.econ.au.au_daily --no-email              # full ingest, skip email
```

## Archive layout

```
data/econ/au/govt/
├── _last_run.log                                # orchestrator stdout, cross-vendor
├── rba/
│   ├── seen.json                                # rolling URL dedup for all 5 RBA streams
│   └── snapshots/{YYYY-MM-DD}.json              # per-day new-item manifest
├── treasury_au/
│   ├── seen.json
│   └── snapshots/{YYYY-MM-DD}.json
├── apra/
│   ├── seen.json
│   └── snapshots/{YYYY-MM-DD}.json
└── abs/
    ├── seen.json
    └── snapshots/{YYYY-MM-DD}.json
```

Per-vendor state matches the SharePoint mirror layout (`{YYYY}/{MM}/{DD}/econ/au/{vendor}/`) and the broader `data/econ/{cc}/{vendor}/` convention.

## Idempotency

Three independent layers:

1. **`seen.json` per vendor** — orchestrator skips any FilingItem whose `source_url` is already in the rolling set. Updated only AFTER successful ingest, so transient failures retry next run.
2. **`research.dim_report.content_hash`** — `imdr.research.filings.ingest_filing` short-circuits when `content_hash` already exists, returning the existing `report_id` and `sharepoint_path` (`already_existed=True`). Re-running the same filing is a no-op at the DB layer.
3. **SharePoint path hash suffix** — `{slug}_{hash8}.pdf` means content-changed re-ingests get a new SP path; identical content stays at one location.

## Failure modes

| Failure | Where surfaced | Recovery |
|---|---|---|
| Akamai 403 / JS challenge | `_render_to_pdf_akamai` raises `RuntimeError` from `_playwright.py:fetch_rba_html` | retry next run (Akamai gates lift after a few minutes) |
| Publisher PDF link missing on RBA SMP / FSR page | `_fetch_publisher_pdf` raises `RuntimeError` with the pattern that didn't match | regex pattern in `resolvers.py` needs an update if RBA changes the URL template |
| `ctx.request.get` returns non-2xx for publisher PDF | `_fetch_publisher_pdf` raises with status code | same — usually transient |
| ABS / Treasury / APRA HTML page changes layout | resolver's `wait_for_selector` times out → render-to-PDF still works (we use `h1` as the catch-all selector) | low-risk; only failure mode is the wait, not the parse |
| `imdr.research.filings.ingest_filing` rejects vendor_category | only happens if a sell_side vendor leaks into FETCHERS (currently impossible — westpac + nab explicitly excluded) | move stream out of `FETCHERS` or re-categorise the vendor |
| Qdrant / SharePoint / Gemini transient | item-level catch in `ingest_filings.py:_one()` logs `[ingest-fail]` and skips; orchestrator pipeline_results stays `rc=0` | next run retries (item not added to seen.json) |

## Smoke checks before scheduler wiring

| Check | Expected |
|---|---|
| `grep -r "playground\." scripts/econ/au/govt/` | Zero `playground.*` imports (path-insert for `research.ingest.qdrant_writer` is allowed — mirrors Korea) |
| Migration 092 applied | `SELECT vendor_code, vendor_category FROM dbo.dim_vendor WHERE vendor_code IN ('apra','treasury_au','nab')` returns 3 rows, all with `vendor_category` set |
| `--dry-run` smoke | 10 fetchers return `ok`, total `~67` new items, no DB writes |
| `--ingest --limit 8` smoke | 8 of 8 official streams resolve + ingest (or dedup for items already in DB); all show `sp=yes`; 0 `[resolve-fail]` / 0 `[ingest-fail]` |
| `--no-email` end-to-end | `au_daily` subprocesses + DB snapshot run clean; email skipped |
| Email render | Subject `[IMDR Daily AU] ✓ all ok — N new filings, M chunks (X min)`; vendor table populated |

Smoke results 2026-06-11 (`--ingest --limit 8`):

| Stream | Report ID | Chunks | SharePoint |
|---|---|---:|---|
| treasury | 6667 | 1 | ✅ |
| apra_quarterly | 6628 | 2 | ✅ |
| abs_commentary | 6629 | 22 | ✅ |
| rba_governors_statement | 6670 | 2 | ✅ |
| rba_board_minutes | 6151 | 9 | ✅ |
| rba_smp | 6148 | 83 | ✅ |
| rba_fsr | 6788 | 72 | ✅ |
| rba_speeches | 6671 | 8 | ✅ |

9 reports / 201 chunks in `research.dim_report` for country_code='AU' (Jun 2026 cohort).

## Final gate

Registration in `scripts/imdr_daily.py:PIPELINES`:

```python
{"cmd": [sys.executable, "-m", "scripts.econ.au.au_daily"], "estimated_tags": 0},
```

Build is complete; user flips the switch per the playbook hard rule (`econ_to_prod.md` § J.4 Step 4).

## Related

- [`au_cb_documents.md`](au_cb_documents.md) — agency inventory + crawl recipes
- [`../econ_to_prod.md`](../econ_to_prod.md) — Phase J playbook (followed verbatim)
- [`../../development/au_govt_filings.md`](../../development/au_govt_filings.md) — execution tracker
- [`../korea/korea_prod_pipeline.md`](../korea/korea_prod_pipeline.md) — Korea reference (mirror the shape)
