# India Govt-Doc Pipeline — Production Reference

Last updated: 2026-06-22

Operations reference for the India Track B government-document ingest that reached
production on 2026-06-22. For the broader India data landscape (Track A series,
indicator inventory, wiring map), see [index.md](index.md).

---

## Architecture

```
RBI / MoSPI / PPAC / MoF / DEA
        │  (16 harvest streams; 15 folder targets — cga skipped, no PDFs)
        ▼
scripts/econ/in/govt/daily_pull.py   ← 16-stream PDF harvester
        │
        ├─ per-stream URL listing    ← plain httpx GET (rbi.org.in Shape 2/3)
        │
        └─ write PDFs to disk        ← data/econ/in/govt/{vendor}/{Y}/{M}/{D}/*.pdf
                                        + data/econ/in/govt/_manifests/{date}.json
                                           │
                                           ▼
scripts/econ/in/govt/ingest_filings.py   ← disk-walk → research pipeline
        │
        ├─ recency guard (--since-days N, default 2)
        │
        ├─ imdr.research.filings.ingest_filing_sync
        │         │
        │         ├─ [skip: classifier, relevance filter — official sources always-keep]
        │         │
        │         ├─ parse_pdf
        │         │
        │         └─ chunk → embed → write
        │                              │
        │                    ┌─────────┼─────────────┐
        │                    ▼         ▼              ▼
        │             research.    Qdrant           SharePoint
        │             dim_report   research_gemini  {YYYY}/{MM}/{DD}/
        │             + fact_chunk _embedding_2     econ/in/{vendor}/
        │                          _3072d
        │
        └─ idempotency: content_hash dedup; already_existed skips re-ingest
```

Country daily orchestrator (`scripts/econ/in/in_daily.py`) runs three subprocess
pipelines in order:

1. `scripts.econ.in.imd.imd_rainfall` — Track A rainfall indicator → `econ.fact_indicator`
2. `scripts.econ.in.govt.daily_pull` — harvest PDFs to disk (all 16 streams)
3. `scripts.econ.in.govt.ingest_filings --since-days 2` — ingest recent → `research.dim_report`

One consolidated email after each run with two snapshots: Track A IMD indicator rows +
Track B `official_*` filings for country IN. Pattern mirrors `au_daily.py` / `kr_daily.py`.
Engine: ODBC Driver 18.

---

## Harvest streams and vendor mapping

15 folders are actively ingested. `cga` has no downloadable PDFs (ASP.NET PostBack
listing only) and is skipped by `daily_pull.py`.

| # | Stream | Vendor code | vendor_category | doc_type | Cadence |
|---|---|---|---|---|---|
| 1 | RBI speeches | `rbi` | `official_cb` | `speech` | ~2–3/month |
| 2 | RBI MPC minutes | `rbi` | `official_cb` | `mpc_minutes` | 6/year |
| 3 | RBI Monetary Policy Report | `rbi` | `official_cb` | `monetary_policy_report` | Semi-annual (Apr/Oct) |
| 4 | RBI Financial Stability Report | `rbi` | `official_cb` | `financial_stability_report` | Semi-annual (Jun/Dec) |
| 5 | RBI press releases (all) | `rbi` | `official_cb` | `press_release` | Daily-ish |
| 6 | RBI Bulletin | `rbi` | `official_cb` | `bulletin` | Monthly |
| 7 | RBI Notifications | `rbi` | `official_cb` | `notification` | Event-driven |
| 8 | RBI Annual Report | `rbi` | `official_cb` | `annual_report` | Annual (Aug) |
| 9 | MoSPI CPI press release | `mospi` | `official_statistics` | `press_release` | Monthly (~12th) |
| 10 | MoSPI IIP press release | `mospi` | `official_statistics` | `press_release` | Monthly (~10th) |
| 11 | MoSPI GDP estimates | `mospi` | `official_statistics` | `press_release` | Quarterly + Annual |
| 12 | MoSPI PLFS bulletins | `mospi` | `official_statistics` | `bulletin` | Monthly + Quarterly + Annual |
| 13 | PPAC petroleum prices | `ppac` | `official_ministry` | `price_report` | Monthly |
| 14 | Union Budget (MoF) | `mof_in` | `official_ministry` | `budget` | Annual (Feb 1) |
| 15 | Economic Survey (DEA) | `dea_in` | `official_ministry` | `economic_survey` | Annual (day before Budget) |
| — | CGA Monthly Accounts press notes | *(cga)* | — | — | **Skipped** — ASP.NET PostBack, no PDFs reachable without Playwright |

Vendor seeds: migration 089 seeded `rbi`, `mospi`, `ppac`, `mof_in`, `dea_in` in
`dbo.dim_vendor` with their respective `vendor_category` values. Migration 086 added the
`vendor_category` column (cross-country, applied 2026-06-10 for Korea).

---

## Cadence

| Layer | Trigger | Where registered |
|---|---|---|
| **Harvest** (`daily_pull.py`) | Daily, as part of `in_daily.py` | `scripts/imdr_daily.py:PIPELINES` |
| **Ingest recent** (`ingest_filings.py --since-days 2`) | Daily, as part of `in_daily.py` | `scripts/imdr_daily.py:PIPELINES` |
| **Manual backfill** (`ingest_filings.py --all`) | On demand | Not wired — run by hand |

Wired into `scripts/imdr_daily.py:PIPELINES` via `scripts.econ.in.in_daily` 2026-06-22.
Migrations 086 + 089 applied.

---

## On-demand invocation

### Full daily run

```
python -m scripts.econ.in.in_daily
```

### Run harvest only (no ingest)

```
python -m scripts.econ.in.govt.daily_pull
```

### Run ingest only

```
# Ingest PDFs from the last 2 days (default — matches the daily cron)
python -m scripts.econ.in.govt.ingest_filings --since-days 2

# Ingest all PDFs on disk (full backfill)
python -m scripts.econ.in.govt.ingest_filings --all
```

### CLI flags — `ingest_filings.py`

| Flag | Effect |
|---|---|
| `--since-days N` | Only walk date-folders from today − N days (default 2). Keeps daily runs fast. |
| `--all` | Walk the entire `data/econ/in/govt/` tree regardless of date. Use for backfill or after a gap. |
| `--dry-run` | Discover filings and report counts, but do not write to DB / Qdrant / SharePoint. |
| `--no-embed` | Ingest to DB only; skip Qdrant vector embedding. Use when re-indexing metadata without re-embedding. |
| `--no-qdrant` | Alias for `--no-embed`. |
| `--vendor CODE` | Restrict the walk to a single vendor folder (e.g. `--vendor rbi`). |
| `--limit N` | Stop after N filings processed (useful for smoke-testing without running the full corpus). |

---

## Runtime state and archive layout

All runtime state is per-machine and gitignored via the top-level `data/*` rule.

```
data/econ/in/
├── govt/
│   ├── rbi/
│   │   └── 2026/
│   │       └── 06/
│   │           └── 22/
│   │               ├── rbi_speech_20260622_001.pdf
│   │               └── rbi_mpc_minutes_20260622.pdf
│   ├── mospi/
│   │   └── 2026/06/22/*.pdf
│   ├── ppac/
│   │   └── 2026/06/22/*.pdf
│   ├── mof_in/
│   │   └── 2026/06/22/*.pdf
│   ├── dea_in/
│   │   └── 2026/06/22/*.pdf
│   └── _manifests/
│       └── 2026-06-22.json      ← per-run harvest manifest (URLs + file paths)
```

SharePoint PDFs land at `{YYYY}/{MM}/{DD}/econ/in/{vendor}/{slug}_{hash8}.pdf` via
local OneDrive sync (`C:\Users\adoshi\OneDrive - RV Capital...\Trade Knowledge Core - IMDR\`).

Unlike Korea, India has **no** `seen.json` per vendor (the recency guard via `--since-days`
is the primary dedup gate). Idempotency for the ingest step is handled by `content_hash`
dedup in `ingest_filing_sync` — re-ingesting a file that is already in `research.dim_report`
returns `already_existed=True` and skips all downstream writes.

---

## Idempotency model

Two layers of dedup:

1. **Harvest (`daily_pull.py`)** — skips files already on disk (checks for the target
   `.pdf` path before downloading). Re-running harvest is safe.
2. **Ingest (`ingest_filings.py`)** — `ingest_filing_sync` computes a `content_hash` of
   the PDF bytes and checks `research.dim_report` before writing. Already-ingested files
   are skipped; the function returns `already_existed=True`. This means `--all` is safe to
   run repeatedly — it will skip the 209 already-ingested discovery-backfill docs and only
   write genuinely new ones.

---

## Backfill state

**Discovery backfill ingested 2026-06-11**: 209 official docs across 5 vendors.

| Vendor | n | Notes |
|---|---|---|
| `rbi` | 130 | Speeches + MPC minutes + MPR + FSR + press releases + bulletin + notifications + annual report |
| `mospi` | 31 | CPI + IIP + GDP + PLFS press releases |
| `dea_in` | 21 | Economic Survey editions |
| `mof_in` | 14 | Union Budget documents |
| `ppac` | 13 | PPAC monthly petroleum price reports |
| **Total** | **209** | Verified via `research.dim_report` count 2026-06-11 |

---

## Failure modes

### Harvest fails for a stream

**Symptom**: `daily_pull.py` exits with rc≠0; one or more vendor folders have no new
PDFs for today's date.

**Fix**: Re-run `daily_pull.py` standalone. The harvester skips already-downloaded files
so a retry is safe. Check `data/econ/in/govt/_manifests/{date}.json` for which streams
completed.

### Ingest item fails

**Symptom**: `[ingest-fail]` in the run log for a specific file.

**Cause**: PDF parse error, Qdrant timeout, SharePoint auth refresh needed.

**Fix**: Failed items are **not** added to the ingest record (not content-hash deduped),
so they will be picked up automatically on the next daily run via `--since-days 2`.
For manual retry: `python -m scripts.econ.in.govt.ingest_filings --since-days 2 --vendor rbi`.

### source_url is a file:// placeholder

**Known limitation (TODO)**: `ingest_filing_sync` currently writes a `file://...` path
as `source_url` rather than the real HTTP URL from the harvest manifest. Wiring the
manifest's real HTTP URL into the ingest call is an open TODO (does not affect
searchability — all text content is in `fact_chunk` and Qdrant).

### TSPD / bot-detection on rbi.org.in

India's RBI site uses Akamai TSPD for the Bulletin XLSX downloads (not for the PDF
harvester). The PDF harvest streams use plain `httpx.get` and are not TSPD-gated. If a
stream starts failing with 403 / challenge pages, check whether the URL has moved to the
new CIMS portal family (RBI is migrating DBIE → CIMS; the PDF listing pages may migrate too).

### in_daily.py — one pipeline failure does not abort others

The three subprocess pipelines in `in_daily.py` run sequentially. A non-zero exit from
`daily_pull` (e.g. one stream 404s) does not abort `ingest_filings`. The consolidated
email reports each pipeline's rc and flags `FAILED` in the subject if any rc≠0.

---

## Smoke tests

```bash
# 1. Smoke-harvest: check that the harvester discovers files without downloading
python -m scripts.econ.in.govt.daily_pull --dry-run

# 2. Smoke-ingest: ingest last 2 days, skip Qdrant embed (fast)
python -m scripts.econ.in.govt.ingest_filings --since-days 2 --no-embed

# 3. Full daily run (no email)
python -m scripts.econ.in.in_daily --no-email

# 4. Spot-check one vendor
python -m scripts.econ.in.govt.ingest_filings --since-days 7 --vendor rbi --limit 5

# 5. Verify idempotency: run ingest twice — second run should report 0 new rows
python -m scripts.econ.in.govt.ingest_filings --since-days 2
python -m scripts.econ.in.govt.ingest_filings --since-days 2
# Expect: second run logs all already_existed=True, 0 new rows in dim_report
```

---

## Open items

1. **source_url wiring** — `ingest_filing_sync` writes `file://...` as `source_url`;
   the harvest manifest (`_manifests/{date}.json`) carries the real HTTP URL for each
   file. Wiring manifest URL → ingest call is deferred. Tracking: noted in
   [`in_govt_filings.md`](../../development/in_govt_filings.md).

2. **CGA press notes** — `cga.nic.in/MonthlyReport.aspx` uses ASP.NET PostBack to
   render the download table; plain `httpx` returns no links. Deferred — needs
   a Playwright pass or a different URL shape. Tracking: `in_govt_filings.md`.

3. **CIMS migration risk** — RBI is migrating DBIE and PDF listing pages to 10 new CIMS
   portals. Monitor for 404s on `rbi.org.in/Scripts/*.aspx` — if they start redirecting,
   the harvest URL list in `daily_pull.py` will need updating.

---

## Related

- [index.md](index.md) — India econ overview (Track A + Track B status)
- [india_prod_pipeline.md](india_prod_pipeline.md) — Track A series pipeline (IMD + MOSPI + RBI + DPIIT + CGA + DGCIS + UPAg + BIS + FAO)
- [india_govt_doc_sources.md](india_govt_doc_sources.md) — full source inventory (all agencies, tier classification, crawl shapes)
- [`../../development/in_govt_filings.md`](../../development/in_govt_filings.md) — Track B execution tracker (open items, migration log)
- [`../economics_data_ingest.md`](../economics_data_ingest.md) — country roster + schema reference
- [`../econ_to_prod.md`](../econ_to_prod.md) — prod-promotion playbook (Track B Phase J)
- [`../korea/korea_prod_pipeline.md`](../korea/korea_prod_pipeline.md) — Korea reference impl (Track A + Track B, both live)
