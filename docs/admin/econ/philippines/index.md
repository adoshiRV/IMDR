# Philippines — Econ Documentation

Last updated: 2026-06-05

PH macroeconomic data. **Status: pre-prod.** No native ingest.

Two source agencies: **Bangko Sentral ng Pilipinas (BSP)** for monetary/banking/FX/external statistics, and **Philippine Statistics Authority (PSA)** for CPI/national accounts/labour/trade. Fiscal lives with **DBM** (budget) and **Bureau of the Treasury** (debt/auctions). BSP runs on SharePoint — the listing pages are HTML-rendered (probe confirmed HTTP 200, structured lists exposed).

## Access paths

| Path | Auth | Speed | Coverage | Status |
|---|---|---|---|---|
| **BSP statistics portal** — `bsp.gov.ph` | None | Mixed (some XLSX, some HTML) | Monetary, banking, credit, external, FX, payments, surveys | **Not onboarded** |
| **PSA statistics portal** — `psa.gov.ph` | None | Slow (mostly XLSX/PDF) | CPI, national accounts, labour, trade, poverty, demographics | **Not onboarded** |
| **PSA release calendar** — `psa.gov.ph` | None | n/a | Release-date schedule | **Not onboarded** |
| **DBM budget portal** — `dbm.gov.ph` | None | n/a (PDF/XLSX) | BESF, National Expenditure Program, budget assumptions | **Not onboarded** |
| **Bureau of the Treasury auctions** — `treasury.gov.ph` | None | n/a (HTML/PDF) | Treasury bill/bond offerings, results, NG debt + deficit | **Not onboarded** |
| **FRED OECD mirror** | FRED API key | Fast | Headline PH series | Live (partial) |

PH has **no formal data API** at the central-bank or stats-office level — XLSX/PDF scraping territory. Closest API-grade flow is BSP's SharePoint listing pages (structured lists queryable directly).

## Policy & fiscal document sources

`bsp.gov.ph` is crawler-friendly (HTTP 200 on probe). All BSP archive pages are SharePoint `SitePages/.../{name}.aspx`.

| Source | URL | Cadence | Notes |
|---|---|:---:|---|
| **BSP monetary policy decisions** | bsp.gov.ph/SitePages/PriceStability/MonetaryPolicyDecision.aspx | per meeting | Monetary Board policy decisions. |
| **BSP Monetary Board highlights** | bsp.gov.ph (highlights archive) | per meeting | Minutes-equivalent — policy reasoning + inflation forecast discussion. |
| **BSP Monetary Policy Report** | bsp.gov.ph/Pages/PriceStability/MPRArchives.aspx | quarterly | Flagship publication (replaced older Inflation Report). |
| **BSP Financial Stability Report** | bsp.gov.ph | semi-annual | Systemic risk + macroprudential. |
| **BSP governor speeches** | bsp.gov.ph/SitePages/MediaAndResearch/SpeechesList.aspx | regular | Governor / deputy governors. |
| **BSP policy meeting calendar** | bsp.gov.ph | reference | Monetary Board dates + MPR schedule. |

## Related

- [`../macro_economy_wiring_map.md`](../macro_economy_wiring_map.md) — PH coverage state.
- [`../onboarding_new_country.md`](../onboarding_new_country.md) — onboarding playbook.
