# Indonesia — Econ Documentation

Last updated: 2026-06-05

ID macroeconomic data. **Status: pre-prod.** No native ingest.

Four source agencies: **Bank Indonesia (BI)** for monetary/banking/FX/external, **BPS** for CPI/national accounts/labour/trade, **Ministry of Finance** for budget/APBN, and **DJPPR** for government securities. **BPS** runs a free-key REST JSON API; **BI** has no public API (XLSX/PDF only); MoF + DJPPR are portal-style with some structured data exposed.

## Access paths

| Path | Auth | Speed | Coverage | Status |
|---|---|---|---|---|
| **BPS API** — `webapi.bps.go.id` | Free key (`BPS_API_KEY`) | Fast (REST JSON) | CPI, GDP, labour, trade, poverty, demographics | **Not onboarded** |
| **BPS release calendar** — `bps.go.id` | None | n/a | Official macro release dates | **Not onboarded** |
| **BI statistics portal** — `bi.go.id` | None | Slow (XLSX/PDF) | Monetary, external, financial, exchange-rate, payments | **Not onboarded** — no API |
| **BI SEKI** (Statistik Ekonomi Keuangan Indonesia) — `bi.go.id` | None | Slow (XLSX) | Money, credit, SBN, GDP, CPI, BoP, reserves, external debt | **Not onboarded** |
| **MoF APBN data** — `kemenkeu.go.id` | None | Slow (PDF/XLSX) | Budget, revenue, spending, fiscal-policy communication | **Not onboarded** |
| **DJPPR government securities** — `djppr.kemenkeu.go.id` | None | Mixed | SBN/SUN/SBSN auctions, issuance, primary dealers | **Not onboarded** |
| **FRED OECD mirror** | FRED API key | Fast | Headline ID series | Live (partial) |

BPS has API-grade access; BI does not. Closing the BI gap requires XLSX scraping of SEKI plus the per-topic statistics-portal landing pages.

## Policy & fiscal document sources

| Source | URL | Cadence | Notes |
|---|---|:---:|---|
| **BI Board of Governors policy news** | bi.go.id | per RDG meeting | BI-Rate decisions, RDG outcomes, macroprudential + rupiah policy. |
| **BI Monetary Policy Review** | bi.go.id | monthly | Between quarterly reports. |
| **BI Monetary Policy Report** | bi.go.id | quarterly | Forecasts, inflation, growth, credit, liquidity, outlook. |
| **BI calendar & advance release schedule** | bi.go.id | reference | RDG dates + statistics release schedule. |
| **BI governor speeches** | bi.go.id | regular | Governor policy speeches + annual-meeting communication. |
| **BI Financial Stability Review** | bi.go.id | semi-annual | Macro-financial risk, credit, macroprudential. |

## Related

- [`../macro_economy_wiring_map.md`](../macro_economy_wiring_map.md) — ID coverage state.
- [`../onboarding_new_country.md`](../onboarding_new_country.md) — onboarding playbook.
