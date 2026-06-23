# US government policy filings — Track B execution tracker

**Status**: **PROMOTED + BACKFILLED + WIRED 2026-06-23 (PROD-LIVE).**

Ingest pipeline promoted to `scripts/econ/us/govt/`; `us_daily.py` rewritten to
dual-track; 145 US official-source reports / 2,320 chunks LIVE in
`research.dim_report` + Qdrant + SharePoint. Registered in
`scripts/imdr_daily.py:PIPELINES` 2026-06-23 — Track B filings now refresh
automatically on the daily scheduler cadence.

**Track B promotion date**: 2026-06-23 (probes + ingest_filings promoted;
us_daily dual-track built; backfill ingested; wired into `imdr_daily.py:PIPELINES` 2026-06-23).

**Discovery deliverable**: complete 2026-06-22 (Phase H) — 11 working probes /
354 documents in `playground/econ/us/govt/` (manifest-only); `daily_pull.py`
writing snapshot JSON.

---

## Why

Mycroft / Lois briefs see only sell-side commentary + Korea/India/Indonesia
official voices when answering questions about US rates / USD / FOMC outlook.
Adding the Fed, Treasury, and NY Fed corpus to the same RAG collection gives
the briefs access to official policy text — FOMC decision language, SEP dot-plot
narrative, Fed speeches, Beige Book anecdotal conditions, Treasury issuance plans,
and the NY Fed's pre-FOMC dealer survey.

---

## Architecture

```
federalreserve.gov · home.treasury.gov · newyorkfed.org
        │  (11 probe_*.py re-discover at ingest time — manifest-only design)
        │
        ▼
scripts/econ/us/govt/ingest_filings.py
        │  (--recent-years 2 for backfill; --since-days 7 for daily)
        │
        └─ resolve bytes (pdf_url → GET; None → HTML body-text extraction)
                │
                └─ imdr.research.filings.ingest_filing_sync
                        │
               ┌────────┼───────────┐
               ▼        ▼            ▼
       research.    Qdrant        SharePoint
       dim_report                econ/us/{vendor}/
       + fact_chunk
```

Reuses `imdr.research.filings.ingest_filing_sync` — same primitive as Korea +
India. No classifier / relevance filter (official sources always-keep).

Key difference from India: no pre-download step. US probes return
`FilingItem(title, source_url, pdf_url, ...)` at discovery time; bytes are
resolved at ingest time by `ingest_filings.py`. No `data/econ/us/govt/` disk
corpus.

---

## Scope — 11 streams

| Stream ID | Vendor | Category | 2yr count |
|---|---|---|---|
| `fomc_statements` | `fed` | `official_cb` | 16 |
| `fomc_minutes` | `fed` | `official_cb` | 15 |
| `fomc_sep` | `fed` | `official_cb` | 8 |
| `fomc_presconf` | `fed` | `official_cb` | 15 |
| `monetary_policy_report` | `fed` | `official_cb` | 3 |
| `beige_book` | `fed` | `official_cb` | 16 |
| `financial_stability_report` | `fed` | `official_cb` | 4 |
| `sloos` | `fed` | `official_cb` | 8 |
| `fed_speeches` | `fed` | `official_cb` | 40 |
| `treasury_refunding` | `treasury_us` | `official_ministry` | 12 |
| `nyfed_dealer_survey` | `nyfed` | `official_cb` | 8 |
| **Total** | — | — | **145 ingested** |

---

## Built (2026-06-23 — promotion + backfill)

| Artifact | Location | State |
|---|---|---|
| Migration 107 — `nyfed` vendor seed + confirm `fed`/`treasury_us` categories | `migrations/107_seed_us_official_vendors.sql` | **APPLIED 2026-06-23** |
| Shared http + session helper | `scripts/econ/us/govt/_http.py` | **PROMOTED** |
| FilingItem model | `scripts/econ/us/govt/_models.py` | **PROMOTED** |
| 11 probe modules | `scripts/econ/us/govt/probe_*.py` | **PROMOTED** |
| Manifest daily-pull (manifest-only, no ingest) | `scripts/econ/us/govt/daily_pull.py` | **PROMOTED** |
| Ingest orchestrator | `scripts/econ/us/govt/ingest_filings.py` | **PROMOTED** — `--recent-years` / `--since-days` / `--vendor` / `--limit` / `--dry-run` / `--no-qdrant` / `--no-embed` |
| US daily orchestrator | `scripts/econ/us/us_daily.py` | **REWRITTEN** — dual-track (Track A EIA + Treasury Debt; Track B ingest_filings --since-days 7); combined HTML email; ODBC Driver 18 engine |
| Backfill (2-year window) | 145 docs in `research.dim_report` | **INGESTED 2026-06-23** (143 new + 2 smoke = 145; 1 404 failure on discontinued PDF) |
| Registered in scheduler | `scripts/imdr_daily.py:PIPELINES` | **WIRED 2026-06-23** — entry: `{"cmd": [sys.executable, "-m", "scripts.econ.us.us_daily"], "estimated_tags": 0}` |

---

## Backfill state (2026-06-23)

**145 reports / 2,320 chunks** in `research.dim_report` + Qdrant + SharePoint.
Span: 2024-07 → 2026-06.

| Vendor | Reports | Chunks |
|---|---|---|
| `fed` | 125 | 2,192 |
| `treasury_us` | 12 | 28 |
| `nyfed` | 8 | 100 |
| **Total** | **145** | **2,320** |

1 document failed permanently (discontinued inter-meeting FOMC statement PDF
404s — HTML page exists, PDF removed). Not content-hash-deduped; will retry
on each run until probe updated. Benign.

---

## Migrations

| Migration | Purpose | Applied |
|---|---|---|
| `086_add_dim_vendor_category.sql` | `vendor_category` column on `dbo.dim_vendor`; CHECK constraint; 47-row backfill of all existing vendors | **2026-06-10** (cross-country, done for Korea) |
| `107_seed_us_official_vendors.sql` | Seeds / confirms `fed` (official_cb), `treasury_us` (official_ministry), `nyfed` (official_cb) in `dbo.dim_vendor` | **2026-06-23** |

---

## Scheduler entry — WIRED 2026-06-23

The following entry is now present in `scripts/imdr_daily.py:PIPELINES`:

```python
{"cmd": [sys.executable, "-m", "scripts.econ.us.us_daily"], "estimated_tags": 0},
```

This single entry runs both tracks via the dual-track orchestrator.
**Do not** add the sub-fetchers (`eia_energy`, `treasury_debt`,
`ingest_filings`) individually — `us_daily.py` calls them internally.

**Operational note:** `imdr_daily.py` must run under the conda `imdr` env
(Python 3.11) — tiktoken/qdrant_client required for Track B ingest.
`sys.executable` binds subprocesses to the active interpreter automatically.

---

## Open items

### 1 permanent 404 on discontinued FOMC PDF

The discontinued inter-meeting FOMC statement PDF 404s at resolution time.
The HTML body is available. Options:
- Add body-text fallback path when `pdf_url` is set but 404s.
- Add the URL to a skip list in `_models.py`.

### fed_speeches limit=40 cap

The `fed_speeches` probe is called with `limit=40` in `_STREAMS` to avoid
ingesting the full ~1,320-item JSON feed on each daily run. For historical
coverage, run `--vendor fed_speeches --recent-years 5` once.

### Tier-2 and Tier-3 streams (deferred)

CBO (RSS side-door working), BEA/Census narrative releases, NY Fed Liberty
Street Economics, regional Reserve Bank president speeches — all classified
in `us_govt_doc_sources.md` but not yet probed or wired. Each needs a probe
module + a `dim_vendor` INSERT before adding to `_STREAMS`.

### BLS news releases (bot-gated)

BLS RSS returns 403 to plain GET (confirmed 2026-06-22). A UA/header strategy
or Playwright transport is needed before `bls` can be added. Deferred.

---

## Replication notes

Pattern follows Korea (reference impl) and India. US differences:

- **No pre-download disk corpus** — Korea and India download PDFs to disk first;
  US probes return manifest-only items and `ingest_filings.py` resolves bytes
  at ingest time. No `seen.json` per vendor.
- **No body-text-only sources** — all US streams have a `pdf_url` or a plain-GET
  HTML page; no TLS-blocked PDF paths (contrast Korea MOTIR).
- **3 vendors across 11 streams** — Korea has 8 vendors across 7 fetchers; US
  groups 9 Fed streams under `fed`, 1 Treasury stream under `treasury_us`, and
  1 NY Fed stream under `nyfed`.
- **`--since-days 7` (not `--since-days 2`)** — Fed streams publish on varying
  schedules; a 7-day rolling window catches FOMC meetings, speeches, and
  quarterly publications without missing anything. Content-hash dedup makes
  the wider window cheap (mostly `SKIP (existed)` on re-runs).

---

## Related

- [`docs/admin/econ/united_states/united_states_govt_prod_pipeline.md`](../econ/united_states/united_states_govt_prod_pipeline.md) — full production ops reference (architecture, CLI, SharePoint layout, failure modes, smoke tests)
- [`docs/admin/econ/united_states/us_govt_doc_sources.md`](../econ/united_states/us_govt_doc_sources.md) — source inventory + tier classification (30+ streams)
- [`docs/admin/econ/united_states/index.md`](../econ/united_states/index.md) — US econ overview
- [`kr_govt_filings.md`](kr_govt_filings.md) — Korea Track B reference impl (template)
- [`in_govt_filings.md`](in_govt_filings.md) — India Track B execution tracker (immediate predecessor)
