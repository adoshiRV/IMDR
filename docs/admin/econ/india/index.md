# India — Econ Documentation

Last updated: 2026-06-05

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

Per [[project-econ-loaded]]: "RBI FX (5/1305), RBI Bulletin (31/168)" — 36 indicators discovered with 1473 metadata cells, **0 loaded**. Parquet exists at `playground/econ/rbi/sample_output/`.

## Policy & fiscal document sources

Document-style RBI sources — easier to access than the DBIE data SPA (most are plain HTML archive pages on `rbi.org.in`).

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
