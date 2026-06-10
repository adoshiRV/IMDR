# Australia government policy filings — execution tracker

**Status**: **PROD-BUILT 2026-06-11.** `scripts/econ/au/govt/` tree + `scripts/econ/au/au_daily.py` are in place; smoke proven 8 of 8 official streams writing to `research.dim_report` + Qdrant + SharePoint. **Final gate remaining**: registration in `scripts/imdr_daily.py:PIPELINES` (user OK per playbook hard rule).

Mirror of [`kr_govt_filings.md`](kr_govt_filings.md) (Korea reference). Started 2026-06-10 (playground discovery) → 2026-06-11 (Phase J end-to-end build + smoke).

## Scope

8 prod fetchers across 4 official AU vendors:

| Vendor | Code | Category | Streams | Cadence | Body type |
|---|---|---|---|---|---|
| Reserve Bank of Australia | `rba` | official_cb | 5 (Gov Stmt / Board Minutes / SMP / FSR / Speeches) | ~25/yr combined | HTML + publisher PDF (SMP/FSR only) |
| Department of the Treasury | `treasury_au` | official_ministry | 1 (publications) | Multiple per week | HTML |
| Australian Prudential Regulation Authority | `apra` | official_regulator | 2 (ADI / GI performance) | Quarterly | HTML + XLSX |
| Australian Bureau of Statistics | `abs` | official_statistics | 3 (CPI / Labour Force / National Accounts release commentary) | Monthly / quarterly | HTML |

**Excluded** (vendor_category='sell_side' rejected by `imdr.research.filings.ingest_filing`):
- Westpac IQ Consumer Sentiment — already covered by sell-side ingest (`playground/research/ingest/crawler_westpac.py`)
- NAB Monthly Business Survey — no sell-side fetcher yet. Playground discovery stays as the reference until that gap is filled.

## Execution log

| Date | Step | Result |
|---|---|---|
| 2026-06-10 | Playground discovery (Phase H) | 10 fetchers built in `playground/econ/au/govt/`, 67 items/day in manifest snapshots |
| 2026-06-11 | E2E ingest smoke from playground (3 paths) | `body_text`, publisher-PDF, HTML-render-to-PDF all proven via `_e2e_ingest_one.py` / `_e2e_ingest_pdf.py` / `_e2e_render_pdf.py` |
| 2026-06-11 | Westpac CCI PDF URL fix | `library.westpaciq.com.au` host (not `www.`), discovered via the sell-side `crawler_westpac.py` reference |
| 2026-06-11 | Migration 092 drafted + applied | apra (official_regulator) + treasury_au (official_ministry) + nab (sell_side) seeded |
| 2026-06-11 | Phase J Step 1: helpers + fetchers → `scripts/econ/au/govt/` | `_models.py` rewritten for per-vendor partitioning under `data/econ/au/govt/{vendor}/` |
| 2026-06-11 | Phase J Step 2: `resolvers.py` built | 3 transport flavours dispatched on `item.stream`; covers all 8 official streams |
| 2026-06-11 | Phase J Step 3: `daily_pull.py` → `ingest_filings.py` | Renamed; orchestrator now mirrors Korea's per-vendor seen.json + snapshot layout |
| 2026-06-11 | Phase J Step 4 PARTIAL: `au_daily.py` built | Country-level entry; PIPELINES list ready; not yet registered in `imdr_daily.py` |
| 2026-06-11 | E2E smoke `--ingest --limit 8` | 8/8 streams green, 1 new (FSR), 7 dedup; 0 `[resolve-fail]` / 0 `[ingest-fail]` |

## Bugs fixed during the prod build

| Symptom | Fix |
|---|---|
| `Error: It looks like you are using Playwright Sync API inside the asyncio loop` | Wrapped sync `resolvers.resolve(item)` in `asyncio.to_thread()` from `ingest_filings.py:_one()` |
| `ValueError: vendor_code='treasury' not in dbo.dim_vendor` | Renamed `vendor_code` from `'treasury'` → `'treasury_au'` in `fetch_treasury.py` to match migration 092 seed |
| `Error: Response has been disposed` on RBA SMP / FSR resolver | In `resolvers._fetch_publisher_pdf`, read `r.body()` BEFORE `ctx.close()` (Playwright APIResponse body invalid after ctx disposal) |
| `vendor_code='westpac' has vendor_category='sell_side'; filings ingest accepts only official_* categories` | Removed `fetch_westpac_cci` + `fetch_nab_business_survey` from `FETCHERS` in `ingest_filings.py`. Documented exclusion + sell-side coverage in code comments |
| Playwright Chrome profile dirs (~hundreds of MB) staged for commit | Added `scripts/**/profile_*/` + `playground/**/profile_*/` to `.gitignore` |

## Smoke results (2026-06-11)

```
=== Australia govt filings daily pull — 2026-06-11 05:34:21 ===
  seen.json: 0 known items pre-run (aggregated across vendors)
  treasury                        ok   fetched= 17  new= 17  (0.8s)
  apra_quarterly                  ok   fetched=  2  new=  2  (0.1s)
  abs_commentary                  ok   fetched=  3  new=  3  (1.0s)
  rba_governors_statement         ok   fetched=  3  new=  3  (7.6s)
  rba_board_minutes               ok   fetched=  3  new=  3  (10.8s)
  rba_smp                         ok   fetched=  6  new=  6  (8.6s)
  rba_fsr                         ok   fetched=  2  new=  2  (6.9s)
  rba_speeches                    ok   fetched= 17  new= 17  (9.3s)

  TOTAL new: 53
  ingesting (embed=yes, limit=8) ...
  [dedup]        treasury        report_id=6667 chunks=1
  [dedup]        apra_quarterly  report_id=6628 chunks=2
  [dedup]        abs_commentary  report_id=6629 chunks=22
  [dedup]        rba_governors_statement  report_id=6670 chunks=2
  [dedup]        rba_board_minutes        report_id=6151 chunks=9
  [dedup]        rba_smp                  report_id=6148 chunks=83
  [ingested]     rba_fsr                  report_id=6788 chunks=72 sp=yes
  [dedup]        rba_speeches             report_id=6671 chunks=8

  INGEST: 1 new, 0 failed (limit=8)
```

## DB state

```sql
SELECT v.vendor_code, v.vendor_category, COUNT(DISTINCT r.id) AS reports, COUNT(c.id) AS chunks
FROM research.dim_report r
JOIN dbo.dim_vendor v ON v.id = r.vendor_id
LEFT JOIN research.fact_chunk c ON c.report_id = r.id
WHERE r.country_id = (SELECT id FROM dbo.dim_country WHERE country_code = 'AU')
  AND v.vendor_category LIKE 'official_%'
GROUP BY v.vendor_code, v.vendor_category;

vendor_code | vendor_category     | reports | chunks
rba         | official_cb         |       6 |    176
treasury_au | official_ministry   |       1 |      1
abs         | official_statistics |       1 |     22
apra        | official_regulator  |       1 |      2
```

9 official AU reports / 201 chunks total. SharePoint mirror at `{YYYY}/{MM}/{DD}/econ/au/{vendor}/{slug}_{hash}.pdf` for every row.

## Remaining work

1. **Scheduler registration** (GATED): one-line add to `scripts/imdr_daily.py:PIPELINES`:
   ```python
   {"cmd": [sys.executable, "-m", "scripts.econ.au.au_daily"], "estimated_tags": 0},
   ```
2. Optional: write a sell-side NAB crawler to unlock NAB Monthly Business Survey ingest.
3. Optional: investigate Westpac CCI cookie/session capture so the CCI PDF flows through sell-side ingest (currently not in the sell-side daily yet — only the broader Westpac IQ /economics + /markets hubs are).

## Related

- [`../econ/australia/australia_govt_prod_pipeline.md`](../econ/australia/australia_govt_prod_pipeline.md) — prod pipeline reference
- [`../econ/australia/au_cb_documents.md`](../econ/australia/au_cb_documents.md) — agency inventory
- [`kr_govt_filings.md`](kr_govt_filings.md) — Korea reference (this doc's template)
- [`../econ/econ_to_prod.md`](../econ/econ_to_prod.md) — Phase J playbook
