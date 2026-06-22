# India — Econ Documentation

Last updated: 2026-06-22 (OGD mandi prices pre-prod entry added)

IN macroeconomic data. **Status: prod-live — Track A Phase G complete 2026-06-19; Track B Phase J complete 2026-06-22.** 15 prod fetchers (Track A) + 16-stream govt-doc harvester (Track B) promoted to `scripts/econ/in/`; orchestrators wired into `imdr_daily.py` and `imdr_monthly.py`. (The quarterly orchestrator was folded into monthly 2026-06-19 — see Loading status below.)

RBI DBIE (Database on Indian Economy) is the primary RBI access path — SPA-driven, requires Playwright + network interception for some endpoints; XLSX Bulletin path avoids the SAP-BO iframe for most desk-relevant tables.

DBIE is being migrated to **RBI CIMS** (10 portals: BoP / FLAIR / SMS / FED / CISBI / FIRMS / etc.). No firm deprecation date. Discovery work needs to be ported as the migration lands.

## Access paths

| Path | Auth | Speed | Coverage | Status |
|---|---|---|---|---|
| **RBI DBIE** (legacy SPA) | None | Slow (Playwright + XHR capture) | Full RBI catalogue | **Discovery only** |
| **RBI CIMS** (10 portals) | None (presumed) | TBD | Migration successor | **Not probed** |
| **MOSPI** | None | n/a | CPI / IIP / GDP / NAS — real-economy | **No public API** — XLSX/HTML scraping only |
| **DGCIS** | None | n/a | Foreign-trade statistics (commodity-level) | **No public API** — XLSX scraping only |

India is the weakest API landscape in Asia. Real-economy series (CPI, IIP, GDP) are MOSPI-published with no programmatic access — only PDF/XLSX releases. Foreign trade (DGCIS) is similar. RBI is the only agency with structured access, and even that is SPA-mediated rather than REST. Commercial vendors (CEIC, Macrobond) are the typical workaround.

## Quick links

| Doc | Purpose |
|---|---|
| **[india_prod_pipeline.md](india_prod_pipeline.md)** | Production ops reference (Track A) — architecture, cadence map, invocation, archive layout, failure modes, smoke tests. |
| **[india_govt_prod_pipeline.md](india_govt_prod_pipeline.md)** | Production ops reference (Track B) — govt-doc harvester, 16-stream/15-folder table, invocation, failure modes, open items. |
| [in_coverage_plan.md](in_coverage_plan.md) | Full scoping doc: wiring-map × vendor matrix, per-cell candidate datasets, A→O phase plan. |
| [india_govt_doc_sources.md](india_govt_doc_sources.md) | Policy/fiscal document source inventory — full agency + tier inventory; all probed sources. |
| [in_nri_rates_sourcing.md](in_nri_rates_sourcing.md) | NRI / FCNR(B) / NRE / NRO deposit rate sourcing notes. |
| **[india_mandi_prices.md](india_mandi_prices.md)** | **PRE-PROD** — OGD Agmarknet daily mandi-price pipeline (data.gov.in resource 35985678…; dedicated star schema; migration 104 drafted, not applied). |
| [`_playground/rbi.md`](_playground/rbi.md) | RBI DBIE Playwright probes (XHR capture, payload inspection, SPA click-through). |
| [`_playground/rbi_explore.md`](_playground/rbi_explore.md) | Captured screenshots + HTML snapshots from probe runs. |

## Loading status

**Prod-live in `econ.fact_indicator` (2026-06-19):** 15 prod fetchers promoted from `playground/econ/in/` to `scripts/econ/in/{vendor}/` (clean absolute imports; libs already in `src/imdr/domains/econ/{mospi,upag}.py`). Two cadence-split orchestrators created using `scripts.econ._country_runner.run`:

| Orchestrator | Scheduler | frequency_scope | Fetchers |
|---|---|---|---|
| `scripts/econ/in/in_daily.py` | `scripts/imdr_daily.py:PIPELINES` | `["DAILY"]` | IMD rainfall (`imd.imd_rainfall`) |
| `scripts/econ/in/in_monthly.py` | `scripts/imdr_monthly.py:PIPELINES` | `["MONTHLY","WEEKLY","DAILY","QUARTERLY","ANNUAL"]` | bis_india · fao_fpi · rbi_fx_reserves · rbi_key_rates · mospi_cpi · mospi_iip · **mospi_nas_gdp** · dpiit_wpi · dpiit_core_industries · cga_monthly · dgcis_trade · upag_imc · **upag_msp** · **upag_aiapy** · **rbi_bulletin (last, headed Chrome)** |

Both wired 2026-06-19. The three quarterly/annual fetchers (`mospi_nas_gdp`, `upag_msp`, `upag_aiapy`) were originally in a separate `in_quarterly.py` but were folded into `in_monthly.py` on 2026-06-19; fetchers are idempotent (MERGE on PK) so running quarterly/annual data monthly is harmless. `scripts/imdr_quarterly.py` has no India entry. Code passed the §G.6 code-review gate (zero playground imports, no sys.path hacks, `country_code="IN"` everywhere).

**FCNR/NRI thread is LIVE**: RBI Bulletin T34 NRI Deposits (FCNR(B)/NR(E)RA/NRO × outstanding+flow, 8 indicators) is in `econ.fact_indicator`.

**OGD Agmarknet mandi prices — PRE-PROD (built 2026-06-22; migration 104 drafted, NOT applied; fetcher in playground, NOT wired)**: comprehensive daily per-mandi price series (~22,000 records/day; ~80M rows history; INR/quintal) via data.gov.in REST API resource `35985678-0d79-46b4-9ed6-6f13308a1d24`. Stored in a dedicated star schema (`econ.fact_india_mandi` + two dims) — NOT `econ.fact_indicator` (cardinality 50k–300k pseudo-indicator IDs would pollute the macro table). Env var: `IMDR_DATA_GOV_IN_API_KEY`. 44 unit tests passing. Gated on: (1) DBA applies migration 104; (2) `--load` validation; (3) promote `playground/econ/in/ogd/` → `scripts/econ/in/ogd/`; (4) wire into `in_daily.py`. See [`india_mandi_prices.md`](india_mandi_prices.md) for the full pipeline doc.

**Migration 103** (`migrations/103_seed_upag_vendor.sql`) seeded the `upag` vendor in `dbo.dim_vendor`. Migration 089 had omitted it — that was the blocker that prevented all three UPAg fetchers (IMC / MSP / AIAPY) from loading. All three are now loaded.

**rbi_bulletin.py requires headed Chrome** (TSPD anti-bot) — the monthly orchestrator must run on a host with a display; cannot run headless on a server. Chrome profile + XLSX cache live at `data/econ/in/rbi/_profile` and `_downloads` (gitignored via `data/*`). See [india_prod_pipeline.md](india_prod_pipeline.md) for the full constraint + failure-mode guidance.

### Cadence map (prod — wired 2026-06-19)

| Fetcher (prod path) | Cadence | Release window | Orchestrator |
|---|---|---|---|
| `scripts.econ.in.imd.imd_rainfall` | DAILY (monsoon Jun-Sep), snapshot otherwise | Refreshed daily on the IMD portal | `in_daily.py` → `imdr_daily.py` |
| `scripts.econ.in.bis.bis_india` | DAILY/MONTHLY/QUARTERLY | Continuous (BIS SDMX) | `in_monthly.py` → `imdr_monthly.py` |
| `scripts.econ.in.fao.fao_fpi` | MONTHLY | ~first Friday of month | `in_monthly.py` → `imdr_monthly.py` |
| `scripts.econ.in.rbi.rbi_fx_reserves` | WEEKLY | Continuous (DBIE) | `in_monthly.py` → `imdr_monthly.py` |
| `scripts.econ.in.rbi.rbi_key_rates` | EVENT | Per RBI MPC decision | `in_monthly.py` → `imdr_monthly.py` |
| `scripts.econ.in.mospi.mospi_cpi` | MONTHLY | ~12th for prior-month obs | `in_monthly.py` → `imdr_monthly.py` |
| `scripts.econ.in.mospi.mospi_iip` | MONTHLY | ~12th for M-2 obs | `in_monthly.py` → `imdr_monthly.py` |
| `scripts.econ.in.dpiit.dpiit_wpi` | MONTHLY | ~14th for prior-month obs | `in_monthly.py` → `imdr_monthly.py` |
| `scripts.econ.in.dpiit.dpiit_core_industries` | MONTHLY | ~last working day for M-2 obs | `in_monthly.py` → `imdr_monthly.py` |
| `scripts.econ.in.cga.cga_monthly` | MONTHLY | ~last working day for M-1 obs | `in_monthly.py` → `imdr_monthly.py` |
| `scripts.econ.in.dgcis.dgcis_trade` | MONTHLY | ~15-day lag; 290 POSTs ≈ 10 min first run | `in_monthly.py` → `imdr_monthly.py` |
| `scripts.econ.in.upag.upag_imc` | WEEKLY | Daily on Agmarknet portal (8-anchor snapshots) | `in_monthly.py` → `imdr_monthly.py` |
| `scripts.econ.in.rbi.rbi_bulletin` | MONTHLY | Bulletin publishes mid-month — **headed Chrome required** | `in_monthly.py` → `imdr_monthly.py` (runs last) |
| `scripts.econ.in.mospi.mospi_nas_gdp` | QUARTERLY + ANNUAL | Q4~May30 · Q1~Aug30 · Q2~Nov30 · Q3~Feb28 | `in_monthly.py` → `imdr_monthly.py` |
| `scripts.econ.in.upag.upag_msp` | ANNUAL | Kharif (Jun) + Rabi (Oct) announcement events | `in_monthly.py` → `imdr_monthly.py` |
| `scripts.econ.in.upag.upag_aiapy` | ANNUAL | Final Estimate ~3yr lag, Third Advance ~1yr lag | `in_monthly.py` → `imdr_monthly.py` |

### Coverage map snapshot (vendor × frequency)

| Vendor | Frequency | Indicators | Obs | Window |
|---|---|---:|---:|---|
| MOSPI | MONTHLY (CPI) | 78 | 150 | Jan-Apr 2026 (2024-base; 2012-base backfill deferred) |
| MOSPI | MONTHLY (IIP) | 20 | 3,350 | 2012-04 → 2026-03 |
| MOSPI | QUARTERLY + ANNUAL (NAS GDP) | 35 | 272 | 2022-23 base, 4 FY + 16 Q |
| DPIIT | MONTHLY (WPI) | 8 | 1,352 | 2012-04 → 2026-04 |
| DPIIT | MONTHLY (8-Core) | 18 | 3,150 | 2011-04 → 2026-04 |
| CGA | MONTHLY (fiscal) | 30 | 4,182 | 2014-04 → 2026-02 |
| IMD | DAILY (rainfall, monsoon) | 3 | 3 | 2026-06-10 snapshot |
| FAO | MONTHLY (FPI) | 6 | 2,622 | 1990-01 → 2026-05 |
| DGCIS | MONTHLY (HS-2 trade) | 198 | ~30,888 | 2013-04 → 2026-03 (Export + Import × 98 HS chapters + TOTAL) |
| **UPAg** | ANNUAL (MSP A31) | 28 | 353 | 2013-14 → 2026-27 (28 crops × INR/Qtl) |
| **UPAg** | ANNUAL (AIAPY A26) | 324 | 15,030 | **1966-67 → 2025-26** (37 crops × 4 seasons × Area/Production/Yield) |
| **UPAg** | WEEKLY (IMC mandi A33) | 16 | 128 | 4 sections × 3-5 commodities × 8 anchor dates per run (Agmarknet wholesale, INR/Qtl) |
| **RBI Bulletin** | MONTHLY/DAILY/WEEKLY/QUARTERLY (23 tables) | ~478 | ~1,188 | May 2026 snapshot (DB-verified 2026-06-19) — original 11 tables + **12 new (2026-06-18)**: T34 NRI Deposits (FCNR(B)/NR(E)RA/NRO Outstanding+Flow 8 ind/24 obs) · T35 Foreign Investment (19/120) · T36 LRS Remittances (11/33) · T30 FX Market Turnover (15/42) · T25 T-bill Ownership by tenor (15/45) · T38 ECB Registrations (33/96) · T5 RBI Standing Facilities (8/15) · T28 CDs (4/8 incl range) · T29 CP (4/8 incl range) · T3 LAF Daily (8/78) · T44 IIP Assets/Liab (27/108) · **T26 T-bill Auctions yield** (9/42). URL-discovery refactored: no more hard-coded monthly-hash URLs; scrapes `BS_ViewBulletin.aspx` at run start. |
| **New fetchers subtotal** | | **~1,216** | **~60,241** | |
| BIS | DAILY + MONTHLY + QUARTERLY | 6 | 24,957 | 1946 → 2026 |
| FRED | DAILY + MONTHLY + ANNUAL | 7 | 11,589 | 1990 → 2026 |
| RBI DBIE | WEEKLY + EVENT | 13 | 3,023 | 2015 → 2026 |
| **Pre-existing prod subtotal** | | **26** | **39,569** | |
| **GRAND TOTAL (DB-verified 2026-06-19)** | | **~1,242** | **~99,810** | |

Wiring-map §7.12 coverage (prod-live 2026-06-19): **8 ✅ + 6 ⚠ + 2 ❌** (was 1 ✅ / 4 ⚠ / 11 ❌ pre-session). ✅ cells: 1.3 External Demand (DGCIS + Bulletin T32) · 1.4 Macro Core (IIP + 8-Core + NAS GDP + Bulletin T23) · 2.2 Producer Prices (WPI + Bulletin T22) · 2.4 CPI Pressure (MOSPI CPI + Bulletin T19C + FAO FPI) · 3.2 Current Acc (Bulletin T40 BoP — eliminated the A5-A7 SAP-BO iframe requirement) · 3.3 Capital Acc (DBIE FX Reserves + Bulletin T33 + T34 NRI Deposits) · 3.4 FX/REER (BIS NEER+REER + Bulletin T37) · 4.4 Policy Reaction (DBIE Key Rates + BIS CBPOL + Bulletin T6/T11). Remaining ❌: 2.3 Domestic Costs (wages — Labour Bureau corp-firewall blocked) · 4.1 Demand Transmission (needs A7 DBIE Sectoral Deployment).

## Policy & fiscal document sources

**Full inventory**: see [`india_govt_doc_sources.md`](india_govt_doc_sources.md) — 10 sections across central bank · ministries · regulators · statistical agencies · fiscal documents · debt-management · pensions · elections · think-tanks. **237 PDFs / 250 MB harvested 2026-06-10** across 11 streams from 5 agency clusters (RBI / MoSPI / PPAC / MoF / DEA). **Track B Phase J PROD-LIVE 2026-06-22**: 15 streams active, 209 docs in `research.dim_report`, daily pipeline wired. Production ops: [`india_govt_prod_pipeline.md`](india_govt_prod_pipeline.md).

The summary table below shows the original Tier-1 RBI seeds; the full doc covers all probed agencies + tier/crawl-shape classification:

| Source | URL | Cadence | Notes |
|---|---|:---:|---|
| **RBI policy statements / resolutions** | rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx | per meeting | Repo-rate decisions. |
| **RBI MPC minutes** | rbi.org.in/Scripts/PublicationReport.aspx?ID=911 | per meeting | Votes + member-level explanations — high signal. |
| **RBI Monetary Policy Report** | rbi.org.in/Scripts/Publications.aspx?head=Monetary%20Policy%20Report | semi-annual | Forecast layer. |
| **RBI speeches** | rbi.org.in/scripts/BS_speechesview.aspx | regular | Governor / deputy governor. |

Sample resolution PDF for parser prototyping: `rbi.org.in/commonman/Upload/English/PressRelease/PDFs/PR1763MPC24022022.pdf`.

## Related

- [`india_prod_pipeline.md`](india_prod_pipeline.md) — **Track A production ops reference** (architecture, cadence, failure modes, smoke tests).
- [`india_govt_prod_pipeline.md`](india_govt_prod_pipeline.md) — **Track B production ops reference** (govt-doc harvester, stream table, invocation, failure modes, open items).
- [`../macro_economy_wiring_map.md`](../macro_economy_wiring_map.md) — IN coverage state (§7.12).
- [`../onboarding_new_country.md`](../onboarding_new_country.md) — onboarding playbook.
- [`../economics_data_ingest.md`](../economics_data_ingest.md) §2.5 — India / RBI deep dive + source catalogue.
- [`../econ_to_prod.md`](../econ_to_prod.md) — prod-promotion playbook (Track A Phase G + Track B Phase J).
- [`../../development/in_govt_filings.md`](../../development/in_govt_filings.md) — Track B execution tracker (open items, migration log).
