# India — Econ Documentation

Last updated: 2026-06-11

IN macroeconomic data. **Status: pre-prod.** RBI DBIE (Database on Indian Economy) is the discovery target — SPA-driven, requires Playwright + network interception to capture the underlying API patterns.

DBIE is being migrated to **RBI CIMS** (10 portals: BoP / FLAIR / SMS / FED / CISBI / FIRMS / etc.). No firm deprecation date. Discovery work needs to be ported as the migration lands.

## Access paths

| Path | Auth | Speed | Coverage | Status |
|---|---|---|---|---|
| **RBI DBIE** (legacy SPA) | None | Slow (Playwright + XHR capture) | Full RBI catalogue | **Discovery only** |
| **RBI CIMS** (10 portals) | None (presumed) | TBD | Migration successor | **Not probed** |
| **MOSPI** | None | n/a | CPI / IIP / GDP / NAS — real-economy | **No public API** — XLSX/HTML scraping only |
| **DGCIS** | None | n/a | Foreign-trade statistics (commodity-level) | **No public API** — XLSX scraping only |

India is the weakest API landscape in Asia. Real-economy series (CPI, IIP, GDP) are MOSPI-published with no programmatic access — only PDF/XLSX releases. Foreign trade (DGCIS) is similar. RBI is the only agency with structured access, and even that is SPA-mediated rather than REST. Commercial vendors (CEIC, Macrobond) are the typical workaround.

## Pre-prod

- [`in_coverage_plan.md`](in_coverage_plan.md) — full scoping doc: wiring-map × vendor matrix (RBI DBIE + CIMS + MOSPI + DGCIS + MoF + DPIIT + CCIL + NSDL + BIS), per-cell candidate datasets, A→O phase plan.
- [`_playground/rbi.md`](_playground/rbi.md) — RBI DBIE Playwright probes (XHR capture, payload inspection, SPA click-through).
- [`_playground/rbi_explore.md`](_playground/rbi_explore.md) — captured screenshots + HTML snapshots from probe runs.

## Loading status

**Prod-live in `econ.fact_indicator`:** BIS · FRED · RBI DBIE (26 indicators × 39,569 obs from prior sessions).

**Pre-prod playground** (built + smoke-tested 2026-06-11 from `playground/econ/in/{vendor}/`, awaiting cadence sign-off + prod promotion): **13 fetchers / ~908 indicators / ~62,100 obs** across MOSPI CPI/IIP/NAS · DPIIT WPI/8-Core · CGA monthly · IMD rainfall · FAO FPI · DGCIS trade (A13) · UPAg MSP (A31) · UPAg AIAPY (A26) · **UPAg IMC mandi prices (A33)** · RBI Bulletin (A4, 8 tables). Library helpers at [`src/imdr/domains/econ/mospi.py`](../../../src/imdr/domains/econ/mospi.py) (MOSPI listing API) and [`src/imdr/domains/econ/upag.py`](../../../src/imdr/domains/econ/upag.py) (Plotly Dash callback decoder). Orchestrator scaffold at [`playground/econ/in/in_monthly.py`](../../../playground/econ/in/in_monthly.py).

A subset (197 indicators × 15,081 obs) was loaded into the DB during an earlier 2026-06-11 build session as part of `run_main` default behaviour; that code was pulled back to `playground/` pending cadence + sign-off review. Rows stay in place (idempotent MERGE on PK) so re-runs cost nothing. The newer fetchers built later in the session (DGCIS, UPAg MSP/AIAPY, RBI Bulletin) ran `--no-load` only — no DB rows from those.

### Cadence map (release calendar — drives prod scheduler choice)

| Vendor / fetcher | Cadence | Release window | Suggested scheduler |
|---|---|---|---|
| MOSPI CPI ([`mospi_cpi.py`](../../../playground/econ/in/mospi/mospi_cpi.py)) | MONTHLY | ~12th of month for prior-month obs | `imdr_monthly.py` (13th UTC retry) |
| MOSPI IIP ([`mospi_iip.py`](../../../playground/econ/in/mospi/mospi_iip.py)) | MONTHLY | ~12th of month for M-2 obs | `imdr_monthly.py` |
| MOSPI NAS GDP ([`mospi_nas_gdp.py`](../../../playground/econ/in/mospi/mospi_nas_gdp.py)) | QUARTERLY + ANNUAL | Q4 ~May 30 · Q1 ~Aug 30 · Q2 ~Nov 30 · Q3 ~Feb 28 | `imdr_quarterly.py` (or monthly idempotent) |
| DPIIT WPI ([`dpiit_wpi.py`](../../../playground/econ/in/dpiit/dpiit_wpi.py)) | MONTHLY | ~14th of month for prior-month obs | `imdr_monthly.py` |
| DPIIT 8-Core ([`dpiit_core_industries.py`](../../../playground/econ/in/dpiit/dpiit_core_industries.py)) | MONTHLY | ~last-working-day for M-2 obs | `imdr_monthly.py` |
| CGA fiscal ([`cga_monthly.py`](../../../playground/econ/in/cga/cga_monthly.py)) | MONTHLY | ~last working day for M-1 obs | `imdr_monthly.py` |
| IMD rainfall ([`imd_rainfall.py`](../../../playground/econ/in/imd/imd_rainfall.py)) | DAILY (monsoon Jun-Sep), snapshot otherwise | Refreshed daily on the IMD portal | `imdr_daily.py` during monsoon |
| FAO FPI ([`fao_fpi.py`](../../../playground/econ/in/fao/fao_fpi.py)) | MONTHLY | ~first Friday of month | `imdr_monthly.py` |
| DGCIS trade ([`dgcis_trade.py`](../../../playground/econ/in/dgcis/dgcis_trade.py)) | MONTHLY | ~15-day lag for prior-month | `imdr_monthly.py` (290 POSTs ≈ 10 min first run; later runs can re-fetch latest ~6 mo only) |
| UPAg MSP ([`upag_msp.py`](../../../playground/econ/in/upag/upag_msp.py)) | ANNUAL | Kharif (Jun) + Rabi (Oct) announcement events | `imdr_quarterly.py` (or monthly idempotent) |
| UPAg AIAPY ([`upag_aiapy.py`](../../../playground/econ/in/upag/upag_aiapy.py)) | ANNUAL | Final Estimate ~3yr lag, Third Advance ~1yr lag | `imdr_quarterly.py` (or monthly idempotent) |
| UPAg IMC mandi prices ([`upag_imc.py`](../../../playground/econ/in/upag/upag_imc.py)) | WEEKLY | Daily on Agmarknet portal | `imdr_weekly.py` or `imdr_monthly.py` (8-anchor sliding snapshots) |
| RBI Bulletin ([`rbi_bulletin.py`](../../../playground/econ/in/rbi/rbi_bulletin.py)) | MONTHLY | Bulletin publishes mid-month | `imdr_monthly.py` — **requires headed Chrome (TSPD)**, can't run on a server without display |

Two cadence-honest options for prod wiring:
1. **Single monthly trigger** (Indonesia/Korea pattern) — all 12 fetchers + RBI go into `imdr_monthly.py` since fetchers are MERGE-idempotent; daily IMD just gets ≤30 stale-day re-runs per month. Simplest, validated elsewhere.
2. **Cadence-split** — IMD into `imdr_daily.py` (correct freshness), MSP + NAS GDP + AIAPY into `imdr_quarterly.py`, rest into `imdr_monthly.py`. Better for the rainfall-driven CPI-food narrative if daily rainfall freshness matters.

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
| **RBI Bulletin** | MONTHLY/DAILY/WEEKLY (8 tables) | 144 | 533 | May 2026 snapshot (T19C CPI / T27 Call Money / T23 IIP / T6 Money Stock / T11 Reserve Money / T37 NEER-REER / T22 WPI / T2 RBI Balance Sheet) |
| **Pre-prod subtotal** | | **~908** | **~62,100** | |
| BIS | DAILY + MONTHLY + QUARTERLY | 6 | 24,957 | 1946 → 2026 |
| FRED | DAILY + MONTHLY + ANNUAL | 7 | 11,589 | 1990 → 2026 |
| RBI DBIE | WEEKLY + EVENT | 13 | 3,023 | 2015 → 2026 |
| **Prod subtotal** | | **26** | **39,569** | |

Wiring-map §7.12 coverage if all 12 pre-prod fetchers land in prod: **5 ✅ + 7 ⚠ + 4 ❌** (was 1 ✅ / 4 ⚠ / 11 ❌ pre-session). New ✅ cells closed this session: 1.4 Macro Core (IIP + 8-Core + NAS GDP + Bulletin IIP); 2.2 Producer Prices (WPI); 2.4 CPI Pressure (MOSPI + Bulletin T19C + FAO); 3.3 Capital Acc (DBIE FX Reserves — was already ✅); 4.4 Policy Reaction (DBIE Key Rates + BIS + Bulletin Money Stock + Reserve Money); **Cluster 4 agriculture broadly covered** via UPAg MSP (input price) + UPAg AIAPY (output area/production/yield, 60 FYs). Remaining ❌: 2.3 Domestic Costs (wages — Labour Bureau corp-firewall blocked); 3.1 Terms of Trade (derivable); 3.2 Current Account (needs A6 DBIE SAP-BO iframe); 4.1 Demand Transmission (needs A7 DBIE Sectoral Deployment).

## Policy & fiscal document sources

**Full inventory**: see [`india_govt_doc_sources.md`](india_govt_doc_sources.md) — 10 sections across central bank · ministries · regulators · statistical agencies · fiscal documents · debt-management · pensions · elections · think-tanks. **237 PDFs / 250 MB harvested 2026-06-10** across 11 streams from 5 agency clusters (RBI / MoSPI / PPAC / MoF / DEA); discovery deliverable per Phase-H complete.

The summary table below shows the original Tier-1 RBI seeds; the full doc covers all probed agencies + tier/crawl-shape classification:

| Source | URL | Cadence | Notes |
|---|---|:---:|---|
| **RBI policy statements / resolutions** | rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx | per meeting | Repo-rate decisions. |
| **RBI MPC minutes** | rbi.org.in/Scripts/PublicationReport.aspx?ID=911 | per meeting | Votes + member-level explanations — high signal. |
| **RBI Monetary Policy Report** | rbi.org.in/Scripts/Publications.aspx?head=Monetary%20Policy%20Report | semi-annual | Forecast layer. |
| **RBI speeches** | rbi.org.in/scripts/BS_speechesview.aspx | regular | Governor / deputy governor. |

Sample resolution PDF for parser prototyping: `rbi.org.in/commonman/Upload/English/PressRelease/PDFs/PR1763MPC24022022.pdf`.

## Related

- [`../macro_economy_wiring_map.md`](../macro_economy_wiring_map.md) — IN coverage state.
- [`../onboarding_new_country.md`](../onboarding_new_country.md) — onboarding playbook.
- [`../economics_data_ingest.md`](../economics_data_ingest.md) §sources — RBI CIMS family vendor entry.
