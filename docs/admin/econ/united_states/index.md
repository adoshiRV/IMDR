# United States — Econ Documentation

Last updated: 2026-06-23 (completeness build-out: FRED-US scheduled + BIS REER + real PCE; 193 active / ~199k obs)

US macroeconomic data. FRED (Federal Reserve Economic Data, St. Louis Fed) is the primary vendor; covers ~170 series across rates, GDP, CPI, labour, credit, housing, sentiment, balance sheet, FX, BoP, and energy. Some series are FRED-native (US data); others are OECD mirrors hosted on FRED for cross-country comparisons.

## Access paths

| Path | Auth | Speed | Coverage | Status |
|---|---|---|---|---|
| **FRED REST API** | API key (`IMDR_ECON_FRED_KEY` + `IMDR_ECON_FRED_KEY2`) | Fast | Full FRED catalogue (~800k series) | **US-specific FRED series: PROMOTED to `scripts/econ/us/fred/` (2026-06-23) — 108 curated series on scheduled refresh; cross-country OECD mirror stays in playground** |
| **BLS Public Data API** | API key (`IMDR_ECON_BLS_KEY`) | Fast | CPI/PPI, employment, JOLTS, ECI, productivity — primary publisher | **PROMOTED to `scripts/econ/us/bls/` (2026-06-23)** |
| **BEA Data API** | API key (`IMDR_ECON_BEA_KEY`) | Fast | GDP/NIPA, personal income, ITA (BoP), IIP | **PROMOTED to `scripts/econ/us/bea/` (2026-06-23)** |
| **Census Bureau API** | API key (`IMDR_ECON_CENSUS_KEY`) | Fast | Retail sales (MARTS), housing starts/permits, international trade (intltrade) | **PROMOTED to `scripts/econ/us/census/` (2026-06-23)** |
| **Treasury Fiscal Data** | Keyless | Fast | Monthly Treasury Statement (MTS), Debt to the Penny | **PROMOTED to `scripts/econ/us/treasury/` (2026-06-23)** |
| **EIA v2** | API key (`IMDR_ECON_EIA_KEY`) | Fast | WTI / Brent / Henry Hub daily spot prices | **PROMOTED to `scripts/econ/us/eia/` (2026-06-23)** |

Dual-key rotation lives in the connector — per-request round-robin with 0.5s throttle. Added 2026-06-04 after a 429 storm during the BOPBCA/MBST/CFSI discontinued-series replacement work.

### Why FRED isn't the whole story

FRED is a *mirror* — most US headline series originate at BLS / BEA / Census and land on FRED with a publication lag. For real-time releases (CPI day, NFP day, retail sales) and for granular sub-series that FRED doesn't index, the source-agency APIs are the right primary. All three are JSON, free-key, and Tier-1 cleanliness — comparable to KOSIS/SingStat.

## What's loaded

**FRED-US baseline:** 106 active US-specific indicators after migration 106 reconcile (plus 41 OECD-mirror cross-country indicators in playground). **US-specific FRED series now on a scheduled refresh** via `scripts/econ/us/fred/fred_us_daily.py` (56 series, DAILY+WEEKLY, in `us_daily`) + `fred_us_monthly.py` (52 series, MONTHLY+QUARTERLY+ANNUAL, in `us_monthly`); previously loaded once from playground. `seed_us.yml` generated from the DB active-set: excludes the 26 migration-106-deactivated source-dup series (verified still inactive post-reload), carries post-106 categories, adds Philly Fed + Dallas Fed regional manufacturing surveys. Library: `src/imdr/domains/econ/fred_http.py` (`FredClient`). The cross-country OECD mirror (non-US FRED) intentionally stays in playground.

**Track A source agencies (BLS/BEA/Census/Treasury/EIA): PROMOTED to `scripts/econ/us/` 2026-06-23.** 15 fetchers + 3 new (BIS, FRED-US daily, FRED-US monthly), 2 orchestrators (`us_monthly` + `us_daily`), 68+ unit tests passing, G.6 code-review gate passed (0 blockers). **Completeness build-out 2026-06-23:** BIS `bis_us.py` (NEER+REER, cell 3.4 — flips ⚠️ → ✅); real PCE (T20806/DPCERX) added to `bea_personal_income`; FRED-US on scheduled refresh. **193 active indicators / ~198,775 obs total.** Score: **15 ✅ / 1 ⚠ / 0 ❌**. Migrations 105 + 106 applied. **Wired into `scripts/imdr_monthly.py:PIPELINES` + `scripts/imdr_daily.py:PIPELINES` 2026-06-23** — both orchestrators are registered and running on the existing scheduler cadence.

## Production (Track A)

**2026-06-23: promoted to `scripts/econ/us/` — wired into `imdr_monthly.py:PIPELINES` + `imdr_daily.py:PIPELINES` 2026-06-23 (PROD-LIVE). Completeness build-out (FRED-US scheduled + BIS REER + real PCE) completed 2026-06-23.**

| Orchestrator | Fetchers | Cadence | Status |
|---|---|---|---|
| `scripts/econ/us/us_monthly.py` | BLS ×5 · BEA ×4 · Census ×3 · Treasury MTS · BIS ×1 · FRED-US monthly ×1 | Monthly / Quarterly / Annual | **WIRED 2026-06-23** — in `imdr_monthly.py:PIPELINES` |
| `scripts/econ/us/us_daily.py` | EIA energy · Treasury Debt-to-Penny · FRED-US daily · Track B filings | Daily | **WIRED 2026-06-23** — in `imdr_daily.py:PIPELINES` |

`imdr_daily.py` scheduled task must run under the conda `imdr` env (Python 3.11) — Track B ingest requires tiktoken/qdrant_client; `sys.executable` binds subprocesses to whatever interpreter runs `imdr_daily.py`. No new Windows Task Scheduler entry needed; US rides the existing cadence.

See [`united_states_prod_pipeline.md`](united_states_prod_pipeline.md) for full ops reference (architecture, failure modes, invocation).

## Status & remaining work (2026-06-23)

### Track A — data series (`econ.fact_indicator`)

**PROMOTED + WIRED 2026-06-23. Completeness build-out also 2026-06-23.** 15 fetchers at `scripts/econ/us/{bls,bea,census,treasury,eia}/` + 3 new fetchers (`scripts/econ/us/fred/fred_us_daily`, `fred_us_monthly`, `scripts/econ/us/bis/bis_us`), 6 connector modules at `src/imdr/domains/econ/{bls,bea,census,treasury_fiscaldata,eia,fred}_http.py`, 2 orchestrators (`us_monthly` + `us_daily`). 68+ unit tests pass (incl. `test_fred_http.py`). G.6 code-review gate passed (0 blockers). Migrations 105 + 106 applied. **193 active indicators / ~198,775 obs** in `econ.fact_indicator`.

**Wired into `scripts/imdr_monthly.py:PIPELINES` + `scripts/imdr_daily.py:PIPELINES` 2026-06-23.**
`us_daily` ran end-to-end rc=0 on first scheduled run. US now auto-refreshes on the existing scheduler cadence alongside KR/ID/AU/NZ/IN. Score: **15 ✅ / 1 ⚠ / 0 ❌** (3.4 FX/REER closed; 4.1 Demand Trans is the cosmetic ⚠ that remains).

**Optional follow-ups (non-blocking, remaining after 2026-06-23):**

- **TIC** foreign holdings (cell 3.3 stock) — CSV/XML scrape, not in the fiscaldata API. BEA ITA financial-account flow already covers the cell.
- **ISM PMI** (Mfg + Services) and **Conference Board CCI** — subscription only; the 1.4 PMI leg stays a gap (Michigan UMCSENT is the free sentiment proxy).
- Regional Fed further surveys — beyond Philly + Dallas added in `seed_us.yml`.
- **Vintages** — BEA/BLS publish first vs revised prints; the scheduler uses vintage-0; point-in-time is supported by `FredClient` if a backtest later needs it.

### Track B — Fed / FOMC documents (`research.dim_report` + Qdrant)

**PROMOTED + BACKFILLED + WIRED 2026-06-23 (PROD-LIVE).**

11 stream probes + ingest orchestrator promoted to `scripts/econ/us/govt/`.
`us_daily.py` rewritten to dual-track (Track A daily indicators + Track B
filings). Migration 107 applied (seeds `nyfed` vendor; confirms `fed` +
`treasury_us` categories). **Backfill complete (2-year window, 2024-07 →
2026-06): 145 reports / 2,320 chunks LIVE in `research.dim_report` + Qdrant +
SharePoint.** By vendor: `fed` 125/2,192 · `treasury_us` 12/28 · `nyfed` 8/100.

**Wired into `scripts/imdr_daily.py:PIPELINES` 2026-06-23** via the `us_daily`
dual-track orchestrator. Track B filings now refresh automatically on the daily
scheduler cadence alongside India Track B. `imdr_daily.py` must run under the
conda `imdr` env (Python 3.11) — tiktoken/qdrant_client required; same
constraint India's Track B already imposes.

Ops reference: [`united_states_govt_prod_pipeline.md`](united_states_govt_prod_pipeline.md).
Execution tracker: [`../../development/us_govt_filings.md`](../../development/us_govt_filings.md).

**Deferred streams (optional follow-ups):**
- CBO (RSS side-door open), BEA/Census narrative releases, NY Fed Liberty Street, regional Reserve Bank speeches.
- BLS news-release RSS is bot-gated (403); transport work needed before `bls` can be added as a Track B stream.

## Pre-prod / sandbox reference

- [`_playground/index.md`](_playground/index.md) — full multi-vendor playground index (Track A + Track B).
- [`_playground/fred.md`](_playground/fred.md) — FRED: 173 indicators, seed.yml, validation scripts (FRED stays in playground — cross-country mirror layer).
- [`_playground/bls.md`](_playground/bls.md) — BLS playground originals (preserved as legacy sandbox; prod fetchers are at `scripts/econ/us/bls/`).
- [`_playground/bea.md`](_playground/bea.md) — BEA playground originals (preserved; prod fetchers at `scripts/econ/us/bea/`).
- [`_playground/census.md`](_playground/census.md) — Census playground originals (preserved; prod fetchers at `scripts/econ/us/census/`).
- [`_playground/treasury.md`](_playground/treasury.md) — Treasury playground originals (preserved; prod fetchers at `scripts/econ/us/treasury/`).
- [`_playground/eia.md`](_playground/eia.md) — EIA playground originals (preserved; prod fetchers at `scripts/econ/us/eia/`).

## Policy & fiscal document sources

Time-series APIs above; the table below covers **document-style** sources (statements, minutes, projections, speeches) for the Federal Reserve. These are not `econ.fact_indicator` material — they feed the policy-document / research pipeline.

| Source | URL | Cadence | Notes |
|---|---|:---:|---|
| **FOMC calendar & meeting materials** | federalreserve.gov/monetarypolicy/fomccalendars.htm | reference | Hub listing meeting dates, statements, minutes, press conf, SEP. Crawl trigger. |
| **FOMC statements archive** | (same calendar hub) | per meeting | Policy decision text. |
| **FOMC minutes archive** | (same calendar hub) | per meeting (3-week lag) | Discussion record. |
| **Summary of Economic Projections** | federalreserve.gov/monetarypolicy/fomcprojtabl... | quarterly | Dot plot + central tendency forecasts. URL pattern: `fomcprojtabl{YYYYMMDD}.pdf`. |
| **Monetary Policy Report** | federalreserve.gov/monetarypolicy/publications/mpr_default.htm | semi-annual | Congressional testimony. |
| **Speeches & testimony** | federalreserve.gov/newsevents/speeches-testimony.htm | regular | Chair, Governors, Reserve Bank presidents. |

Full agency × stream inventory (Fed + FOMC, 12 regional Reserve Banks, Treasury/OFR, BLS/BEA/Census, CBO, OMB, FDIC/OCC), Tier 1/2/3 classification, and crawl-pattern clusters: [`us_govt_doc_sources.md`](us_govt_doc_sources.md) (Track B / Phase H — discovery only; Tier-1 Fed probes in `playground/econ/us/govt/`).

## Related

- [`united_states_prod_pipeline.md`](united_states_prod_pipeline.md) — **Track A ops reference**: architecture, library-code table, per-vendor fetcher inventory, CLI flags, archive layout, failure modes, smoke tests, scheduler wiring (live 2026-06-23).
- [`united_states_govt_prod_pipeline.md`](united_states_govt_prod_pipeline.md) — **Track B ops reference**: 11-stream Fed/Treasury/NY Fed ingest, CLI flags, SharePoint layout, failure modes, scheduler wiring (live 2026-06-23).
- [`us_coverage_plan.md`](us_coverage_plan.md) — cell → exact source-ID mapping, build order, per-vendor API mechanics, and migration notes.
- [`united_states_indicator_inventory.md`](united_states_indicator_inventory.md) — wiring-map score, FRED category counts, and production fetcher inventory.
- [`us_govt_doc_sources.md`](us_govt_doc_sources.md) — Track B: full Fed/FOMC/agency × stream taxonomy (Tier 1/2/3), crawl patterns; updated with production fetcher inventory.
- [`../../development/us_govt_filings.md`](../../development/us_govt_filings.md) — Track B execution tracker (done / pending / migration log).
- [`../macro_economy_wiring_map.md`](../macro_economy_wiring_map.md) — coverage by cluster (US is the most-mapped country alongside Korea).
- [`../economics_data_ingest.md`](../economics_data_ingest.md) — schema + loader.
- [[project-econ-loaded]] — current live counts across all econ vendors.
