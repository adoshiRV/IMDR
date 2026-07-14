# United States Govt-Doc Pipeline — Production Reference (Track B)

Last updated: 2026-06-23

Operations reference for the US Track B government-document ingest that was promoted
and backfilled on 2026-06-23. For the broader US data landscape (Track A series,
indicator inventory, wiring map), see [index.md](index.md). For source discovery
background (tier classification, all 30+ agency streams), see
[us_govt_doc_sources.md](us_govt_doc_sources.md).

---

## Architecture

```
federalreserve.gov · home.treasury.gov · newyorkfed.org
        │  (11 active streams — manifest-only probes re-discover at ingest time)
        │
        ▼
scripts/econ/us/govt/  ← 11 probe_*.py + _http.py + _models.py + daily_pull.py
        │
        │  ingest_filings.py --recent-years N   (backfill)
        │  ingest_filings.py --since-days 7     (daily fast-path)
        │
        ├─ for each FilingItem in window:
        │    ├─ item.pdf_url set  → httpx GET pdf_url  → pdf_bytes
        │    └─ item.pdf_url None → httpx GET source_url → BeautifulSoup body_text
        │
        └─ imdr.research.filings.ingest_filing_sync
                 │
                 ├─ [skip: classifier, relevance filter — official sources always-keep]
                 │
                 ├─ parse_pdf  OR  synthesize_document_from_text
                 │
                 └─ chunk → embed → write
                                     │
                           ┌─────────┼─────────────┐
                           ▼         ▼              ▼
                     research.    Qdrant           SharePoint
                     dim_report   research_gemini  {YYYY}/{MM}/{DD}/
                     + fact_chunk _embedding_2     econ/us/{vendor}/
                                  _3072d
```

**Key difference from India Track B**: India walks pre-downloaded PDFs from disk
(`data/econ/in/govt/{folder}/`). US probes are manifest-only — they return
`FilingItem` objects with metadata + URLs; `ingest_filings.py` resolves document
bytes at ingest time (no separate harvest step, no local PDF store).

Country daily orchestrator (`scripts/econ/us/us_daily.py`) is a **dual-track**
design that mirrors `scripts/econ/in/in_daily.py`:

1. `scripts.econ.us.eia.eia_energy` — Track A WTI / Brent / Henry Hub daily spot
2. `scripts.econ.us.treasury.treasury_debt` — Track A Debt to the Penny daily
3. `scripts.econ.us.govt.ingest_filings --since-days 7` — Track B rolling window

Each subprocess runs in isolation; one failure does not abort the others. A
combined HTML email reports both tracks with per-pipeline RC, elapsed time,
Track A obs count, and Track B new filings / chunks count.

Engine: ODBC Driver 18 for SQL Server (required for `NVARCHAR(MAX) NULL` params
in `research.dim_report.pdf_text` / `context`).

---

## Stream table

| # | Stream ID | Vendor code | vendor_category | doc_type | Cadence | 2yr-window |
|---|---|---|---|---|---|---|
| 1 | `fomc_statements` | `fed` | `official_cb` | `decision` | ~8/yr (per meeting) | 16 |
| 2 | `fomc_minutes` | `fed` | `official_cb` | `minutes` | ~8/yr (~3-wk lag) | 15 |
| 3 | `fomc_sep` | `fed` | `official_cb` | `report` | 4/yr (Mar/Jun/Sep/Dec) | 8 |
| 4 | `fomc_presconf` | `fed` | `official_cb` | `report` | ~8/yr (all meetings since 2019) | 15 |
| 5 | `monetary_policy_report` | `fed` | `official_cb` | `report` | Semi-annual (Feb/Jul) | 3 |
| 6 | `beige_book` | `fed` | `official_cb` | `report` | 8/yr (~2 wks pre-FOMC) | 16 |
| 7 | `financial_stability_report` | `fed` | `official_cb` | `report` | Semi-annual (May/Nov) | 4 |
| 8 | `sloos` | `fed` | `official_cb` | `report` | Quarterly | 8 |
| 9 | `fed_speeches` | `fed` | `official_cb` | `speech` | ~15–20/mo (JSON feed) | 40 |
| 10 | `treasury_refunding` | `treasury_us` | `official_ministry` | `report` | Quarterly (QRA + TBAC) | 12 |
| 11 | `nyfed_dealer_survey` | `nyfed` | `official_cb` | `report` | ~8/yr (pre-FOMC SME) | 8 |

2yr-window counts are from the 2026-06-23 backfill (`--recent-years 2`).

**Probe source details:**
- Streams 1–9 all originate from `www.federalreserve.gov`. Streams 1–8 use
  the FOMC calendar hub (`fomccalendars.htm` ~164 KB, Shape B — single GET,
  slug-keyed `{YYYYMMDD}`). Stream 9 uses the JSON backing feed
  (`/json/ne-speeches.json`) — the HTML listing is JS-rendered, but the feed is
  a plain GET (~1,320 items).
- Stream 10 (`treasury_refunding`) is `home.treasury.gov` — QRA announcement +
  TBAC charge/presentation PDFs. TBAC detail pages carry no inline PDF; the PDF
  is on the "most-recent documents" hub (`/system/files/221/TreasuryPresentation*.pdf`).
  Real announcement date parsed from `field-news-publication-date` on the detail
  page.
- Stream 11 (`nyfed_dealer_survey`) is `newyorkfed.org` — the NY Fed renamed
  SPD (Survey of Primary Dealers) + SMP (Survey of Market Participants) into the
  consolidated Survey of Market Expectations (SME). Hub: `newyorkfed.org/markets/
  market-intelligence/survey-of-market-expectations`.

**doc_type mapping** (probe → DocType stored in `dim_report`):

| Probe doc_type | Stored doc_type | Streams |
|---|---|---|
| `decision` | `decision` | `fomc_statements` |
| `minutes` | `minutes` | `fomc_minutes` |
| `projection` | `report` | `fomc_sep` |
| `transcript` | `report` | `fomc_presconf` |
| `speech` | `speech` | `fed_speeches` |
| `testimony` | `speech` | (when testimony in feed) |
| `report` | `report` | MPR / Beige Book / FSR |
| `survey` | `report` | `sloos` / `nyfed_dealer_survey` |
| `refunding` | `report` | `treasury_refunding` |

---

## Vendor mapping

| vendor_code | display_name | vendor_category | dim_vendor.id | Migration |
|---|---|---|---|---|
| `fed` | Federal Reserve | `official_cb` | (existing row) | Pre-existing; migration 107 confirmed 0 rows → seeded |
| `treasury_us` | U.S. Treasury | `official_ministry` | (existing or new row) | Migration 107 |
| `nyfed` | NY Federal Reserve | `official_cb` | (new row) | Migration 107 |

Migration 107 (`seed_us_official_vendors.sql`) applied 2026-06-23. It seeds
the `nyfed` vendor row and confirms `fed` + `treasury_us` have `vendor_category`
set correctly. All three rows in `dbo.dim_vendor` after migration:

```sql
-- confirm after migration 107
SELECT vendor_code, display_name, vendor_category
FROM   dbo.dim_vendor
WHERE  vendor_code IN ('fed','treasury_us','nyfed');
```

---

## Invocation

### Backfill (run once, or after a large gap)

```bash
# Conda imdr env required (tiktoken / qdrant_client / embed stack)
conda activate imdr

# Dry-run first — check window item counts per stream
python -m scripts.econ.us.govt.ingest_filings --recent-years 2 --dry-run

# Full 2-year backfill with embeddings
python -m scripts.econ.us.govt.ingest_filings --recent-years 2

# Filter to one stream
python -m scripts.econ.us.govt.ingest_filings --recent-years 2 --vendor fomc_statements
```

### Daily fast-path (mirroring us_daily.py's wiring)

```bash
python -m scripts.econ.us.govt.ingest_filings --since-days 7
```

### Full dual-track daily run

```bash
python -m scripts.econ.us.us_daily
python -m scripts.econ.us.us_daily --no-email   # skip email send
```

### CLI flags — `ingest_filings.py`

| Flag | Effect |
|---|---|
| `--recent-years N` | Ingest docs published within the last N years (default 2). Use `--recent-years 20` for a full historical backfill. |
| `--since-days N` | Daily fast-path: only ingest docs published in the last N days. Overrides `--recent-years`. Content-hash dedup makes the rolling window idempotent. |
| `--vendor STREAM_ID [...]` | Restrict to one or more stream IDs (e.g. `fomc_statements`). Default: all 11 streams. |
| `--limit N` | Max items per stream. For smoke tests without full corpus. |
| `--dry-run` | Discover items and print counts; no bytes fetched, no DB/Qdrant/SharePoint writes. |
| `--no-qdrant` | Skip Qdrant upsert. DB + SharePoint only. |
| `--no-embed` | Skip embedding; chunks land in DB without vectors. |

---

## Conda environment gotcha

**The ingest stack requires the `imdr` conda environment (Python 3.11).**

`tiktoken`, `qdrant_client`, and the Voyage/Gemini embed wrappers are
installed there. The system Python 3.13 environment does **not** have these
packages and will raise `ModuleNotFoundError` on the first embed call.

Always activate before running ingest:

```bash
conda activate imdr
python -m scripts.econ.us.govt.ingest_filings --dry-run   # verify env
```

The `us_daily.py` orchestrator uses `sys.executable` (the active interpreter
at launch time) for all subprocess calls. If the scheduler task is registered
pointing at the `imdr` env's Python binary, this is handled automatically.

---

## SharePoint layout

US official docs land in the IMDR SharePoint library at:

```
{YYYY}/{MM}/{DD}/econ/us/{vendor_code}/{slug}_{hash8}.pdf
```

Example (FOMC statement from 2026-06-17):

```
2026/06/17/econ/us/fed/fomc_statement_20260617_a1b2c3d4.pdf
```

Delivery: local OneDrive sync at
`C:\Users\adoshi\OneDrive - RV Capital...\Trade Knowledge Core - IMDR\`
which OneDrive then uploads to the SharePoint library (same mechanism as
Korea + India).

HTML-body sources (e.g. Fed speeches when no PDF available) are searchable
via SQL + Qdrant only — no PDF artefact on the file share.

---

## Idempotency

`ingest_filing_sync` computes a `content_hash` of the document bytes (PDF)
or body text and checks `research.dim_report` before writing. If the hash
exists, it returns `already_existed=True` and skips all downstream writes
(DB, Qdrant, SharePoint). This means:

- Running `--recent-years 2` twice is safe — the second run logs all
  `SKIP (existed)` and writes 0 new rows.
- Running `--since-days 7` on a daily schedule is safe even if an earlier
  day's window overlaps yesterday's run.
- Failed items are **not** content-hash-recorded, so they will be retried
  automatically on the next daily run.

---

## Failure modes

### A stream's discover() call fails

**Symptom**: `DISCOVER FAILED: ...` in the ingest log for that stream.
Other streams are unaffected (per-stream isolation).

**Fix**: Re-run `ingest_filings.py --since-days 7 --vendor <stream_id>`.
Common causes: federalreserve.gov calendar hub momentarily unavailable,
TBAC PDF URL pattern changed (check `probe_treasury_refunding.py`).

### A document PDF 404s at resolution time

**Symptom**: `FAIL fetch pdf ...` in the log; `stats.failed += 1`.

**Known instance (2026-06-23 backfill)**: 1 discontinued inter-meeting
FOMC statement PDF 404s — the HTML page exists but the companion PDF was
removed. This is benign; the HTML body is still indexable. The item is
not content-hash-deduped, so daily runs will retry and continue to fail
until the URL is patched in the probe.

**Fix**: For transient 404s, the next daily run retries automatically.
For permanent 404s, update the probe's URL pattern or add the item to a
skip list in `_models.py`.

### Embed / Qdrant call fails mid-batch

`ingest_filing_sync` is per-item isolated. A Qdrant timeout on item N
does not abort item N+1. The failed item is not hash-deduped and will be
retried on the next run. If Qdrant is persistently unavailable, use
`--no-qdrant` to land metadata in DB only, then re-index separately.

### Wrong Python environment

**Symptom**: `ModuleNotFoundError: No module named 'tiktoken'`.

**Fix**: `conda activate imdr` and re-run. See the conda gotcha section above.

---

## Live corpus state (2026-06-23)

Backfill completed 2026-06-23 with `--recent-years 2` (window: 2024-07 → 2026-06).

| Vendor | Reports | Chunks | Notes |
|---|---|---|---|
| `fed` | 125 | 2,192 | 9 streams; spans FOMC statements/minutes/SEP/presconf/MPR/Beige/FSR/SLOOS/speeches |
| `treasury_us` | 12 | 28 | QRA + TBAC quarterly refunding (short docs, low chunk count) |
| `nyfed` | 8 | 100 | NY Fed Survey of Market Expectations (SME) |
| **Total** | **145** | **2,320** | **Plus 2 smoke-test docs = 145 reports** |

**1 document failed** (permanent 404): a discontinued inter-meeting FOMC
statement PDF. The HTML page exists; adding body-text resolution as fallback
is an open item. Benign — does not affect the 145 indexed docs.

Span: **2024-07 → 2026-06**. All docs indexed in `research.dim_report`,
`research.fact_chunk`, Qdrant, and SharePoint (PDF sources only).

---

## Smoke tests

```bash
conda activate imdr

# 1. Dry-run — check stream counts without fetching bytes
python -m scripts.econ.us.govt.ingest_filings --dry-run --recent-years 2

# 2. Spot-check one stream, skip embed
python -m scripts.econ.us.govt.ingest_filings --vendor fomc_statements --limit 3 --no-embed

# 3. Idempotency check — second run should report 0 new rows
python -m scripts.econ.us.govt.ingest_filings --since-days 7
python -m scripts.econ.us.govt.ingest_filings --since-days 7
# Expect: all SKIP (existed), 0 ingested

# 4. Daily orchestrator (no email)
python -m scripts.econ.us.us_daily --no-email
```

---

## Scheduler wiring — LIVE (2026-06-23)

`us_daily.py` is **registered** in `scripts/imdr_daily.py:PIPELINES` as of
2026-06-23. The dual-track orchestrator now runs automatically on the daily
scheduler cadence. No new Windows Task Scheduler entry was needed — US rides
the existing cron.

Entry now present in `scripts/imdr_daily.py:PIPELINES`:

```python
{"cmd": [sys.executable, "-m", "scripts.econ.us.us_daily"], "estimated_tags": 0},
```

This single entry runs both Track A daily series (EIA + Treasury Debt) and
Track B filings (`ingest_filings --since-days 7`) via the dual-track
orchestrator. **Do not** add `scripts.econ.us.eia.eia_energy`,
`scripts.econ.us.treasury.treasury_debt`, or
`scripts.econ.us.govt.ingest_filings` as separate PIPELINES entries —
`us_daily.py` already calls all three internally.

**Operational note (conda env):** `imdr_daily.py` scheduled task must run under
the conda `imdr` env (Python 3.11). Track B ingest requires tiktoken and
qdrant_client, which are not available in the system Python 3.13 env.
`sys.executable` binds all subprocesses to whatever interpreter runs
`imdr_daily.py`. Same requirement India's Track B already imposes — no new
setup needed if the existing task already points at the `imdr` env.

Verification: `us_daily` ran end-to-end rc=0 on first scheduled run
(EIA + Treasury-debt idempotent MERGE; Track B filings all-skip on clean corpus).

---

## Related

- [index.md](index.md) — US econ overview (Track A + Track B status)
- [us_govt_doc_sources.md](us_govt_doc_sources.md) — full agency × stream inventory (30+ streams, Tier 1/2/3, crawl shapes)
- [united_states_prod_pipeline.md](united_states_prod_pipeline.md) — Track A ops reference (BLS / BEA / Census / Treasury / EIA)
- [`../../development/us_govt_filings.md`](../../development/us_govt_filings.md) — Track B execution tracker (done / pending / migration log)
- [`../economics_data_ingest.md`](../economics_data_ingest.md) — country roster + schema reference
- [`../econ_to_prod.md`](../econ_to_prod.md) — prod-promotion playbook (Track B Phase J)
- [`../india/india_govt_prod_pipeline.md`](../india/india_govt_prod_pipeline.md) — India Track B reference impl
- [`../korea/korea_prod_pipeline.md`](../korea/korea_prod_pipeline.md) — Korea Track A + B (earliest reference impl)
