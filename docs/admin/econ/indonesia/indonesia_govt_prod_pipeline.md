# Indonesia — Track B govt-filings production pipeline

Last updated: 2026-09-21

Ops reference for the Indonesia government/central-bank **document** pipeline
(Track B → `research.dim_report` + `research.fact_chunk` + Qdrant + SharePoint).

For the time-series pipeline (Track A → `econ.fact_indicator`) see
[indonesia_prod_pipeline.md](indonesia_prod_pipeline.md). For the source
inventory and how each transport was found see
[id_govt_doc_sources.md](id_govt_doc_sources.md).

> ## ✅ STATUS: PROD-LIVE
>
> | Step | State |
> |---|:---:|
> | Code promoted to `scripts/econ/id/govt/` | ✅ 2026-09-21 |
> | Unit tests (70 + 19 Track A) | ✅ 2026-09-21 |
> | Migration 129 applied (`ojk` → id=87) | ✅ 2026-09-21 |
> | Full ingest | ✅ 2026-09-21 — **537 reports / 8,411 chunks** |
> | SQL↔Qdrant reconciliation | ✅ **zero drift** across all 537 |
> | `id_daily` end-to-end, rc=0 | ✅ 2026-09-21 |
> | Registered in `scripts/imdr_daily.py:PIPELINES` | ✅ 2026-09-21 |
>
> Registration **replaced** the two individual ID entries
> (`scripts.econ.id.bis.bis_indonesia`, `scripts.econ.id.bi.bi_srbi`) — both
> live in `id_daily.py:TRACK_A_PIPELINES`, so keeping them would have
> double-run Indonesia. Verified by AST: exactly one `econ.id` entry.
>
> ### Ingest result
>
> | Vendor | Reports | SQL chunks | Qdrant | Drift |
> |---|---:|---:|---:|---:|
> | `bi` | 79 | 3,589 | 3,589 | 0 |
> | `djppr` | 418 | 984 | 984 | 0 |
> | `ojk` | 30 | 3,668 | 3,668 | 0 |
> | `bps` | 10 | 170 | 170 | 0 |
> | **Total** | **537** | **8,411** | **8,411** | **0** |
>
> Embeddings via `gemini-embedding-2` into
> `research_gemini_embedding_2_3072d`.
>
> ### Known standing failure (1/run, benign)
>
> One DJPPR press row fails `resolve` every run: its listing links to
> `…debt2healthswab…` and **DJPPR's own CMS 404s on that slug** (and on the
> correctly-spelled `…swap…`). Their page is dead, not our parsing. It stays
> out of `seen.json` and retries daily, which is deliberate — it self-heals
> if DJPPR fixes the link, and one labelled line is better than silently
> dropping a row.
>
> `kemenkeu` also reports `ok=NO` every run by design — see
> [id_govt_doc_sources.md](id_govt_doc_sources.md) §2.

## Architecture

```
scripts/econ/id/id_daily.py                    ← country daily orchestrator
  ├── scripts.econ.id.bis.bis_indonesia        (Track A, already daily)
  ├── scripts.econ.id.bi.bi_srbi               (Track A, already daily)
  └── scripts.econ.id.govt.ingest_filings --ingest
        ├── fetch_bi.discover()        → 10 streams
        ├── fetch_bps.discover()       → 1 stream (2 more opt-in)
        ├── fetch_djppr.discover()     → 3 slugs
        ├── fetch_ojk.discover()       → 3 streams
        ├── fetch_kemenkeu.discover()  → always ok=False (documented blocker)
        │
        ├── dedup vs data/econ/id/govt/{vendor}/seen.json
        ├── resolvers.is_ingestable()  → drops undated reference artefacts
        ├── resolvers.resolve()        → ("pdf", bytes) | ("text", str)
        └── imdr.research.filings.ingest_filing()
              → research.dim_report + research.fact_chunk
              → Qdrant (embed unless --no-embed)
              → SharePoint mirror
```

## Fetcher table

| Module | Vendor | `vendor_category` | Streams | Discovered | Ingestable |
|---|---|---|---:|---:|---:|
| `fetch_bi.py` | `bi` | `official_cb` | 10 | 79 | 79 |
| `fetch_bps.py` | `bps` | `official_statistics` | 1 (+2 opt-in) | 10 | 10 |
| `fetch_djppr.py` | `djppr` | `official_ministry` | 3 | 519 | 425 |
| `fetch_ojk.py` | `ojk` | `official_regulator` **(new, mig 129)** | 3 | 30 | 30 |
| `fetch_kemenkeu.py` | — | *not seeded* | 0 | 0 | 0 |
| **Total** | | | **17** | **638** | **544** |

The 94-row gap between discovered and ingestable is DJPPR's undated
reference artefacts (issuance calendars, retail-SBN term sheets). They are
recorded in the daily manifest but deliberately not ingested — see
Idempotency below.

## Resolve contract — mixed, unlike Australia

ID resolvers may return `("text", str)` as well as `("pdf", bytes)`.
`scripts/econ/au/govt/resolvers.py` is PDF-only by a 2026-06-11 decision;
Indonesia follows **Korea's** mixed contract because BI is HTML-first and
not gated, so rendering its pages to PDF would mean adding a browser
dependency to a plain-httpx pipeline purely to re-encode text we already
hold. Rationale in the `resolvers.py` module docstring.

Measured on the 2026-09-21 smoke:

| Stream | Resolves to | Size |
|---|---|---|
| BI `news_release` | text | 5,006 chars |
| BI `news_release_en` | text | 2,693 chars |
| BI `financial_stability` (KSK 47) | **pdf** | 10.8 MB |
| BI `policy_review_tkm` | **pdf** | 7.8 MB |
| BI `money_supply_report` | **pdf** | 5.0 MB |
| BI `bop_report` | **pdf** | 2.9 MB |
| BPS `press_release_brs` | **pdf** | 3.4 MB |
| DJPPR `press_release` | **pdf** | 0.3–0.6 MB |
| OJK `press_release` | **pdf** | 0.16 MB |
| OJK `annual_report` | **pdf** | 12.0 MB |

So most streams do land a publisher PDF; the text path is the fallback that
keeps BI's news releases and speeches from being lost.

> **One-word trap.** The resolve kind is `"text"`. `scripts/econ/au/govt`
> tests `kind == "body"`, which never matches its own PDF-only literal —
> harmless there, silent data loss here. Pinned by
> `test_ingest_maps_text_kind_not_body_kind`.

## Cadence

Daily, even though most agencies publish far less often. Empty days are
evidence the cadence is what we think it is, not a bug. What IS a bug: a
fetcher going `ok=False` (other than kemenkeu), or an agency silent longer
than its threshold:

| Agency | Stale after | Driven by |
|---|---:|---|
| `bi` | 14 d | near-daily press |
| `ojk` | 21 d | ~weekly press |
| `bps` | 45 d | monthly BRS batches |
| `djppr` | 60 d | irregular issuance press |
| `kemenkeu` | — | no items to go stale |

## Invocation

```bash
# discovery only — no DB writes (use this to check health)
python -m scripts.econ.id.govt.ingest_filings --dry-run

# full ingest
python -m scripts.econ.id.govt.ingest_filings --ingest

# smoke: a handful of items, round-robin across agencies, no embedding
python -m scripts.econ.id.govt.ingest_filings --ingest --no-embed --limit 4

# one agency
python -m scripts.econ.id.govt.ingest_filings --ingest --only bi

# re-discover everything (ignores seen.json)
python -m scripts.econ.id.govt.ingest_filings --reset

# country orchestrator (Track A + Track B + email)
python -m scripts.econ.id.id_daily
python -m scripts.econ.id.id_daily --no-email
python -m scripts.econ.id.id_daily --track-b-only
```

`--limit` round-robins across agencies, so a low limit covers as many
agencies as possible rather than N items from the first one.

## Archive layout

```
data/econ/id/govt/
  _last_run.log                       ← orchestrator stdout, cross-vendor
  bi/
    seen.json                         ← rolling source_url dedup
    snapshots/{YYYY-MM-DD}.json       ← that day's new-items manifest
  bps/  djppr/  ojk/  kemenkeu/       ← same shape
```

Per-vendor partitioning is required by `econ_to_prod.md` § J.5 item 5; all
paths come from `_models.py` (`DATA_DIR`, `vendor_dir`, `vendor_seen_file`,
`vendor_snapshots_dir`) so nothing hard-codes them.

## Idempotency

Three separate layers, which matters because each catches a different thing:

1. **`seen.json`** — keyed `"{vendor}|{source_url}"`. Written **only for
   items that resolved AND ingested successfully**, so a transient failure
   is retried next run rather than silently swallowed.
2. **`filings.ingest_filing` content hash** — a re-ingested document
   returns `already_existed=True` with the existing `report_id`; no
   duplicate row, no re-embed.
3. **`is_ingestable()`** — drops rows we discover but never want as corpus
   documents. Today that is exactly the undated reference artefacts
   (`extras["undated"] == "1"`). The check runs BEFORE the resolver lookup;
   inverting that order would ingest issuance calendars dated "today".

Verified: first discovery run 638 new, second run 0 new.

## Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| `kemenkeu ok=NO` every run | **Expected.** Documented blocker | none — see [id_govt_doc_sources.md](id_govt_doc_sources.md) §2 |
| `bi ... 0 RDG` | Usually correct — the rate decision is off page-1 unless it landed in the last ~2 weeks | confirm via `resolvers.probe_bi_sequence()` |
| BI `[resolve-fail] ... page missing` | BI unpublished/moved the `.aspx`; a 404 arrives as HTTP 200 | none; the item stays out of `seen.json` and retries |
| BPS `not a PDF (first bytes ...)` | The signed `?f=` token expired between discovery and resolve | re-run; discovery re-signs it |
| All BI streams fail at once | `bi.go.id` down or template changed | check `parse_rows` against a saved page; 67 unit tests pin the markup |
| `bps ok=NO ... IMDR_BPS_API_KEY` | Key missing from `.env` | same key Track A uses |
| Every BPS row re-reports as new | The volatile PDF URL became the dedup identity again | identity must be `bps://{stream}/{brs_id}` |
| `ojk` returns 0 English rows | The `/en/` mirror's `Month D, YYYY` date order regressed | `test_ojk_parses_us_ordered_english_date` |

## Two pytest landmines the ID promotion tripped

Both were found by the 2026-09-21 review gate, both are framework-wide rather
than Indonesia-specific, and both share a cause: **Indonesia was the first
country whose test file imported these production modules.** Anyone adding a
`{cc}/govt` test suite will hit them next.

### 1. Importing `{cc}_daily.py` under pytest destroys output capture

Every `scripts/econ/{cc}/{cc}_daily.py` (au, id, in, kr, us) and several
`{cc}_monthly.py` rewrap the streams at **module level**:

```python
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
```

That is deliberate — Windows subprocess output needs UTF-8 — and harmless
when the module is run as a script. Under pytest it replaces the *captured*
streams, and the wrapper later closes pytest's temp file:

```
ValueError: I/O operation on closed file.
```

Capture is then broken for the **entire session**. Observed cost of one such
import: **3,381 errors** across unrelated suites (test_vendors, test_fx, …),
with the real test results buried. It reads like a catastrophic breakage and
is actually one line in one test file.

**Do not import a country orchestrator from a test.** Read the registered
`PIPELINES` with `ast` instead — see
`test_id_daily_track_b_runs_ingest_not_discovery_only`. That also tests the
better thing: what is registered in the source, not what an import exposes.

Fixing the six orchestrators to rewrap only under `__main__` would be the
deeper fix, but it is a cross-country change and was deliberately not made as
a one-off divergence for Indonesia.

### 2. Bare `_http` / `_models` collide across countries in pytest

Every `scripts/econ/{cc}/govt/` tree does `sys.path.insert(0, <its own dir>)`
then `from _http import ...` — a **bare, unqualified** module name. pytest
collects all test files into ONE process, so whichever country imports first
wins `sys.modules["_http"]` for the whole session.

This lay dormant for AU/KR/US because no test file imported those production
modules. Indonesia's `test_id_govt_parsers.py` was the first, and because
`id` sorts before `us` it made `test_us_govt_probes.py` resolve US's
`from _http import save_raw` against **Indonesia's** `_http.py` — taking
three pre-existing US test modules down with `ImportError: cannot import
name 'save_raw'`. Caught by the 2026-09-21 review gate, not by the ID suite
itself (which passed in isolation the whole time).

The fix in `test_id_govt_parsers.py` is to pop the bare names out of
`sys.modules` and remove the directory from `sys.path` immediately after the
import block — the already-imported objects hold live references, so only
future imports are affected. **Any new `scripts/econ/{cc}/govt/` test file
must do the same**, or it will collide with Indonesia's in turn.

The durable fix is to make these trees real packages with relative imports.
That touches KR/AU/US/ID at once and was deliberately left out of the ID
promotion; worth doing before a fifth country lands.

Always validate with the whole directory, never one file:

```bash
python -m pytest tests/unit/test_econ/ --co -q    # expect 0 errors
```

## Smoke tests

```bash
# unit — 67 tests, no network
python -m pytest tests/unit/test_econ/test_id_govt_parsers.py -q

# collection must be clean across the whole dir (see the gotcha above)
python -m pytest tests/unit/test_econ/ --co -q

# discovery health, writes nothing
python -m scripts.econ.id.govt.ingest_filings --dry-run

# end-to-end on 4 items, no embedding
python -m scripts.econ.id.govt.ingest_filings --ingest --no-embed --limit 4
```

## Go-live checklist — COMPLETE 2026-09-21

All four steps done. Kept for the next country's reference:

1. ✅ Applied `migrations/129_seed_id_official_vendors.sql` — `ojk` id=87;
   assertions passed (pre-existing ID vendor categories unchanged, no NULLs).
2. ✅ `--ingest --no-embed --limit 4` smoke, then `--limit 8` with embedding
   to exercise the Qdrant path before committing to the full run.
3. ✅ Full `--ingest` — 515 ingested, 7 failed. **Failures were investigated,
   not waved through**: 1 was a real resolver bug (DJPPR rows that link
   straight at a media file, now fixed + tested), 1 is dead upstream, and 5
   were the Qdrant batching bug below.
4. ✅ Registered `scripts.econ.id.id_daily` and removed the two superseded
   entries.

### What step 3 uncovered — read this before promoting another country

Five OJK annual reports (527-733 chunks, 327-422pp) failed with
`ResponseHandlingException: [WinError 10053]`. The cause was NOT transient:

`playground/research/ingest/qdrant_writer.py:upsert_chunks` carried the
comment *"Single call — qdrant-client handles batching internally."*
**It does not.** `upsert(points=[...])` is one HTTP request; at 3072
dimensions a few hundred points is tens of MB and the connection is aborted
mid-write. Fixed by batching at `UPSERT_BATCH_POINTS = 128`.

The failure mode was worse than a crash, and is what to watch for elsewhere:

- `ingest_filing` writes `dim_report` + `fact_chunk` **before** embedding, so
  the SQL side looked complete while Qdrant held zero vectors.
- The retry hit `already_existed=True` and **short-circuited without
  re-embedding**, printing `0 new, 0 failed` — which reads as success.
- The daily email counts SQL chunks, not vectors, so it would have shown
  green forever.

13 ID reports / 3,101 chunks were silently unsearchable until a direct
SQL↔Qdrant reconciliation found them. Repaired with the existing
`playground/research/reembed_report.py`.

**This affects every country, not just ID** — any report large enough to trip
the old single-call limit. Two follow-ups are NOT done and want their own
decision: (a) audit KR/US/AU/IN for the same drift, (b) make
`ingest_filing` verify vectors before treating `already_existed` as
nothing-to-do.

## Related

- [id_govt_doc_sources.md](id_govt_doc_sources.md) — source inventory, transports, open items
- [indonesia_prod_pipeline.md](indonesia_prod_pipeline.md) — Track A ops reference
- [`../econ_to_prod.md`](../econ_to_prod.md) — Phase J playbook
- [`../korea/`](../korea/) — the fully-live Track B reference
- [`../australia/australia_govt_prod_pipeline.md`](../australia/australia_govt_prod_pipeline.md) — the other prod-built-not-registered country
