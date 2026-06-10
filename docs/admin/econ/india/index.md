# India — Econ Documentation

Last updated: 2026-06-10

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

**Live as of 2026-06-10: 26 indicators × 39,569 observations in `econ.fact_indicator`.**

| Vendor | Indicators | Obs | Coverage |
|---|---:|---:|---|
| BIS | 6 | 24,957 | NEER/REER broad · Private-NFS DSR · Credit-to-GDP ratio + gap · RBI repo daily 1946→ |
| FRED | 7 | 11,589 | CPI YoY + level (1990→) · IIP (1994→2023) · Real GDP PWT annual · Call money · INR/USD daily + monthly |
| RBI DBIE | 13 | 3,023 | FX reserves Total/FCA/Gold/SDR/IMF (weekly 2015→) + Key Rates snapshot (Repo · SDF · Reverse Repo · CRR · SLR · CPI YoY · WPI YoY · WACR) |
| **Total** | **26** | **39,569** | |

7 of 16 wiring-map cells now covered (2 ✅ + 5 ⚠) including 4.4 Policy Reaction (now ✅ with event-stamped Repo/SDF/CRR/SLR snapshot). See [`in_coverage_plan.md`](in_coverage_plan.md) §"Final India Checklist" for the full punch-list (A0 + A1 + A5(partial) + A21 + A22 done; A2–A20 remaining).

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
