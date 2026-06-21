# India government policy filings — Track B execution tracker

**Status**: **PROD-WIRED 2026-06-22.** Registered in `scripts/imdr_daily.py:PIPELINES`
via `scripts.econ.in.in_daily`; runs daily under the existing IMDR cron.

**Track B promotion date**: 2026-06-22 (scripts promoted + orchestrator rewritten +
scheduler wired).

**Discovery deliverable**: complete 2026-06-11 (Phase H) — 237 PDFs / 250 MB harvested
across 11 streams from 5 agency clusters (RBI / MoSPI / PPAC / MoF / DEA); 209 docs
ingested into `research.dim_report` as backfill.

---

## Why

Mycroft / Lois briefs currently only see sell-side commentary when answering questions
about India macro / INR / rates. Adding official-voice documents (RBI MPC minutes,
MoSPI GDP / CPI releases, Budget + Economic Survey, PPAC petroleum prices) to the same
RAG corpus closes that gap with one `vendor_category` filter.

---

## Architecture

```
daily_pull.py (16-stream PDF harvester)
        │
        └─ data/econ/in/govt/{vendor}/{Y}/{M}/{D}/*.pdf
                           + _manifests/{date}.json
                                │
                                ▼
ingest_filings.py (--since-days 2)
                                │
                                └─ imdr.research.filings.ingest_filing_sync
                                        │
                               ┌────────┼───────────┐
                               ▼        ▼            ▼
                       research.    Qdrant        SharePoint
                       dim_report                econ/in/{vendor}/
                       + fact_chunk
```

Reuses `imdr.research.filings.ingest_filing_sync` — same primitive as Korea. No
classifier / relevance filter (official sources always-keep).

---

## Scope — 16 harvest streams, 15 ingested

| Vendor code | Category | Streams |
|---|---|---|
| `rbi` | `official_cb` | speeches · MPC minutes · MPR · FSR · press releases · Bulletin · Notifications · Annual Report (8 streams) |
| `mospi` | `official_statistics` | CPI · IIP · GDP · PLFS bulletins (4 streams) |
| `ppac` | `official_ministry` | petroleum prices (1 stream) |
| `mof_in` | `official_ministry` | Union Budget (1 stream) |
| `dea_in` | `official_ministry` | Economic Survey (1 stream) |
| *(cga — skipped)* | — | ASP.NET PostBack listing — no PDFs reachable; 1 stream deferred |

**Speeches are covered**: `rbi_speeches` stream → `doc_type=speech`.

---

## Built (2026-06-22 prod promotion)

| Artifact | Location | State |
|---|---|---|
| Migration 086 — `vendor_category` column + CHECK + backfill | `migrations/086_add_dim_vendor_category.sql` | **APPLIED 2026-06-10** (cross-country, done for Korea) |
| Migration 089 — 5 India official vendor seeds | `migrations/089_seed_in_official_vendors.sql` | **APPLIED** — seeds `rbi / mospi / ppac / mof_in / dea_in` with `vendor_category` |
| 16-stream PDF harvester | `scripts/econ/in/govt/daily_pull.py` | **PROMOTED to scripts/** |
| Ingest helper | `scripts/econ/in/govt/ingest_filings.py` | **PROMOTED** — `--since-days N` / `--all` / `--dry-run` / `--no-embed` / `--no-qdrant` / `--vendor CODE` / `--limit N` |
| Package init | `scripts/econ/in/govt/__init__.py` | **PROMOTED** |
| IN daily orchestrator | `scripts/econ/in/in_daily.py` | **REWRITTEN** — dual-track: Track A IMD rainfall + Track B harvest + ingest; combined email with two snapshots; ODBC Driver 18 engine |
| Registered in scheduler | `scripts/imdr_daily.py:PIPELINES` | **WIRED 2026-06-22** via `scripts.econ.in.in_daily` (same module path as Track A wiring 2026-06-19; no re-wire needed) |
| Discovery backfill | 209 docs in `research.dim_report` | **INGESTED 2026-06-11** (pre-promotion, from playground harvester run) |
| Test downloads verifier | `playground/econ/in/govt/_test_downloads.py` | **Stays in playground** — pre-flight verifier, not a prod script |
| Harvest manifest | `data/econ/in/govt/_manifests/{date}.json` | Per-machine, gitignored |
| PDF corpus | `data/econ/in/govt/{vendor}/{Y}/{M}/{D}/*.pdf` | Per-machine, gitignored |

---

## Discovery backfill (2026-06-11)

**209 official docs** ingested into `research.dim_report` from the Phase-H playground
harvester run:

| Vendor | n |
|---|---|
| `rbi` | 130 |
| `mospi` | 31 |
| `dea_in` | 21 |
| `mof_in` | 14 |
| `ppac` | 13 |
| **Total** | **209** |

The 209 docs are content-hash-deduped in `ingest_filing_sync` — running
`ingest_filings.py --all` will skip them (returns `already_existed=True`).

---

## Migrations

| Migration | Purpose | Applied |
|---|---|---|
| `086_add_dim_vendor_category.sql` | `vendor_category` column on `dbo.dim_vendor`; CHECK constraint; 47-row backfill of all existing vendors | **2026-06-10** |
| `089_seed_in_official_vendors.sql` | Seeds 5 India official vendors (`rbi / mospi / ppac / mof_in / dea_in`) with `vendor_category` | **Applied** |

Migration 087 is Korea's per-country seed. India's is 089.

---

## Daily model

The `--since-days 2` recency guard means `ingest_filings.py` only walks the last 2 days
of date-folders. This keeps the daily run fast (~seconds for most days) even as the on-disk
corpus grows. The harvest step (`daily_pull.py`) already skips files on disk, so only
genuinely new PDFs are fetched each day.

For any gap longer than 2 days (e.g. after a missed cron), use `--since-days N` or
`--all` to catch up.

---

## Open items

### source_url wiring (TODO)

`ingest_filing_sync` currently writes a `file://...` path as `source_url` in
`research.dim_report`. The harvest manifest (`data/econ/in/govt/_manifests/{date}.json`)
carries the real HTTP source URL for each PDF. Wiring the manifest URL into the ingest
call would make the `source_url` column clickable / useful for provenance queries.

This is a code change in `scripts/econ/in/govt/ingest_filings.py` (pass the manifest
URL through to `ingest_filing_sync`). Deferred — does not affect searchability (all text
is in `fact_chunk` and Qdrant).

### CGA press notes (deferred — ASP.NET PostBack)

`cga.nic.in/MonthlyReport.aspx` renders the download link list via ASP.NET PostBack.
Plain `httpx.get` returns no links. A Playwright-based resolver is needed before CGA
press notes can be harvested (separate from the CGA XLSM data already in
`econ.fact_indicator` via Track A). Deferred to a future sprint.

---

## Replication notes

Pattern follows Korea exactly (the reference impl — see
[`kr_govt_filings.md`](kr_govt_filings.md)). India differences:

- **No `seen.json` per vendor** — Korea's `seen.json` dedup is replaced by the
  `--since-days` recency guard + `content_hash` dedup in `ingest_filing_sync`.
- **No body-text sources** — every probed India agency publishes PDFs; there is no
  `body_text` path for any active stream (contrast Korea MOEF/MOTIR which are RSS/HTML).
- **No per-vendor backfill helper** — Korea built `backfill_kr_govt.py`; India's
  equivalent is `ingest_filings.py --all` (the `--since-days` guard is simply omitted).
- **CGA is the only deferred stream** — Korea has no analogous PostBack-blocked source.

---

## Related

- [`docs/admin/econ/india/india_govt_prod_pipeline.md`](../econ/india/india_govt_prod_pipeline.md) — production ops reference (architecture, streams, invocation, failure modes, smoke tests)
- [`docs/admin/econ/india/india_govt_doc_sources.md`](../econ/india/india_govt_doc_sources.md) — source inventory + tier classification + crawl shapes
- [`docs/admin/econ/india/index.md`](../econ/india/index.md) — India econ overview
- [`kr_govt_filings.md`](kr_govt_filings.md) — Korea Track B reference impl (template for India)
- Memory: [[project_rbi_fcnr_bulletin_t34]] · [[project_bps_onboarding]] (Indonesia reference)
