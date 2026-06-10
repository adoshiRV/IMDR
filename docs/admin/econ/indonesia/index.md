# Indonesia — Econ Documentation

Last updated: 2026-06-10 (bi_sbn_position — Phase I)

ID macroeconomic data. **Status: 308 indicators × 114,106 observations live in `econ.fact_indicator` as of 2026-06-10.** Split across four vendors: BPS (`vendor_code='bps'`, 82 indicators) + BI (`vendor_code='bi'`, 184 indicators across SEKI tables, Survey publications, bank rates, SRBI auction yields, and SBN position by holder) + BIS (`vendor_code='bis'`, 6 indicators) + DJPPR (`vendor_code='djppr'`, 36 indicators). **All 16 wiring-map cells covered; 13 of 16 are full ✅** — only 2.1 Input Costs (one full source — could derive more), 3.1 Terms of Trade (NBToT derivable in analytics from existing BPS export/import price indices), and 3.4 FX/REER strengthening (BIS reserves composition pending) remain ⚠ partial. **Prod-live 2026-06-09/10**: 28 fetchers live under `scripts/econ/{bps,bi,bis,djppr}/`, orchestrator at `scripts/econ/id/id_monthly.py`; wired into `scripts/imdr_monthly.py:PIPELINES` 2026-06-09. `scripts.econ.bis.bis_indonesia` and `scripts.econ.bi.bi_srbi` are also registered in `scripts/imdr_daily.py:PIPELINES` for same-day capture of event-driven series (BI policy rate + SRBI auction yields).

Four source agencies: **Bank Indonesia (BI)** for monetary/banking/FX/external, **BPS** (Badan Pusat Statistik) for CPI/national accounts/labour/trade, **Ministry of Finance** (Kemenkeu) for budget/APBN, and **DJPPR** (Direktorat Jenderal Pengelolaan Pembiayaan dan Risiko) for government securities. **BPS** runs a free-key REST JSON API; **BI** has no public API (XLSX/PDF only); MoF + DJPPR are portal-style with some structured data exposed.

## Build status (2026-06-10)

Wiring map [§7.17](../macro_economy_wiring_map.md#717-indonesia-id) shows 5/16 cells flipped ❓→⚠️ (1.3, 1.4, 2.2, 2.3, 2.4). Onboarding follows the [`../onboarding_new_country.md`](../onboarding_new_country.md) playbook, BPS-first.

| Phase | Status |
|---|:---:|
| A. Docs scaffolding (this file + inventory + coverage plan + targets) | ✅ 2026-06-08 |
| B. BPS API discovery (`playground/econ/bps/discovery/`) — 4 subcats × 52 subjects × 1,655 vars catalogued | ✅ 2026-06-08 |
| C. BPS fetchers — CPI / Trade / GDP / PPI/WPI / Labour shipped (23 indicators × 2,599 obs); sectoral decomp + current-base PPI/WPI deferred to C2 | ✅ 2026-06-08 |
| D. BI/SEKI XLSX scraping (monetary, BoP, reserves, external debt) | ⏳ pending |
| E. MoF APBN + DJPPR SBN | ⏳ pending |
| C2. BPS follow-on fetchers — GDP components (24) + CPI groups (11) + current-base prices (8) + Sakernas (12) + IP (4) | ✅ 2026-06-08 |
| D. BI SEKI XLSX scrapers — Money Supply / FX Reserves / BoP (24 indicators × 2,996 obs) | ✅ 2026-06-08 |
| D2. BI SEKI fiscal expansion — Fiscal aggregates IV.1-3 (6 annual) + SBN position IV.4 (5 monthly) + external debt SULNI VI.1 (8 quarterly) | ✅ 2026-06-08 |
| D3. BI SEKI banking expansion — Monetary Base I.2 (5 monthly) + Commercial Bank BS I.3 (8 monthly) + Bank Credit I.4 (15 monthly × 5 bank groups) | ✅ 2026-06-08 |
| D4. BIS SDMX cross-country gauges — NEER + REER + DSR + Credit-to-GDP ratio/gap + BI policy rate (6 indicators × 8,811 obs); migration 084 applied | ✅ 2026-06-08 |
| D5. BI Survey publications — Consumer Survey SK (9 indicators), Retail Sales SPE (9 indicators), Business Survey SKDU (18 indicators) → **36 new indicators × 3,204 obs**, closes cell 1.1 | ✅ 2026-06-09 |
| D6. SKDU macro (T2 Capacity + T5 Selling Prices + T6 Inflation Expectations) + Bank rates SEKI I.25/I.26/I.28 → **55 new indicators × 1,349 obs**, closes cells 2.3 + 4.3 | ✅ 2026-06-09 |
| E. MoF APBN realisasi (PDF-only, MoF portal 500-erroring) | ⏳ deferred — covered by BI SEKI IV.1-3 |
| F. Loader run + DB validation — **159 indicators × 22,204 obs** loaded across BPS + BI + BIS; migrations 081 (BPS vendor), 082 (idr/idr_bn/SEMIANNUAL dims), 083 (BI vendor), 084 (BIS vendor) applied | ✅ 2026-06-08 |
| G. Production wiring (`scripts/econ/id/id_monthly.py`) | ✅ 2026-06-09 — orchestrator registered in `scripts/imdr_monthly.py:PIPELINES`; `scripts.econ.bis.bis_indonesia` also in `scripts/imdr_daily.py:PIPELINES` |
| H. BI SRBI auction yields — 3 indicators (6M/9M/12M), 485 obs, event cadence ~2×/week, 2023-09-15→; wired into `scripts/imdr_daily.py:PIPELINES` 2026-06-10; parser at `src/imdr/domains/econ/bi_srbi.py`; 13 unit tests | ✅ 2026-06-10 |
| I. BI SEKI IV.4 SBN position by holder — 19 indicators × 3,630 obs, monthly 2008-12→2026-05; 4 headline totals (SUN/ON/SPN/SBSN) + 8 ON bank-type holder decomp + 7 SPN bank-type holder decomp; reuses `bi_seki.py` (no new library); wired into `id_monthly.py` 2026-06-10; no new unit tests (parser covered by existing `_bi_seki` test suite) | ✅ 2026-06-10 |

## Access paths

| Path | Auth | Speed | Coverage | Status |
|---|---|---|---|---|
| **BPS API** — `webapi.bps.go.id` | Free key (`IMDR_BPS_API_KEY`) | Fast (REST JSON) | CPI, GDP, labour, trade, poverty, demographics | **Live in DB** (2026-06-08) — 82 indicators × 5,242 obs; auto-loaded via `id_monthly` in `imdr_monthly.py` |
| **BPS release calendar** — `bps.go.id` | None | n/a | Official macro release dates | **Not onboarded** |
| **BI SEKI** (Statistik Ekonomi Keuangan Indonesia) — `bi.go.id/SEKI/tabel/` | None | Slow (XLSX) | Money, fiscal, credit, SBN, BoP, reserves, external debt | **Live** (2026-06-08/10) — 10 SEKI tables scraped: Money Supply (I.1), Monetary Base (I.2), Bank BS (I.3), Bank Credit (I.4), Bank Rates (I.25/I.26/I.28), Fiscal Revenue/Spending/Financing (IV.1/2/3), SBN Outstanding (IV.4 aggregate), **SBN Position by Holder (IV.4 TABEL4_4 — 19 indicators: 4 totals + 8 ON holder + 7 SPN holder, monthly 2008-12→, added 2026-06-10)**, BoP (V.1), FX Reserves (V.9), External Debt SULNI (VI.1). Legacy multi-period sheets, deeper BoP sub-tables (V.2-V.8) deferred |
| **BI Survey publications** — `bi.go.id/.../Documents/{SK,spe,SKDU}.zip` | None | Slow (XLSX in ZIP) | Consumer Survey IKK, Retail Sales SPE, Business Survey SKDU | **Live** (2026-06-09) — 3 surveys scraped: SK Tabel 1 (Consumer Confidence + 8 sub-indices monthly 2012-2025), SPE Tabel 1 (Real Retail Sales Index + 8 categories monthly 2012-2025), SKDU T1 Kegiatan Usaha (Business Activity TOTAL + 17 sectors quarterly 2022-2025). **36 indicators × 3,204 obs** — closes cell 1.1 |
| **BI SRBI auction pages** — `bi.go.id/id/publikasi/lelang/operasi-moneter/Pages/Hasil-Lelang-SRBI-{D}-{Bulan}-{YYYY}.aspx` | None | Fast (HTML, ~2×/week) | SRBI 6M/9M/12M weighted-average winning auction yield | **Live** (2026-06-10) — 3 indicators × 485 obs, 2023-09-15 (SRBI launch) → 2026-06-10; event frequency (~Wed + Fri); wired into `scripts/imdr_daily.py:PIPELINES`. Tenors present: started 1/3/6/9/12M at launch; current cycle 6/9/12M only (since mid-2024). 302 = no auction that day — skip. |
| **MoF APBN data** — `kemenkeu.go.id` | None | Slow (PDF/XLSX) | Budget, revenue, spending, fiscal-policy communication | **Not onboarded** |
| **DJPPR government securities** — `djppr.kemenkeu.go.id` | None | Mixed | SBN/SUN/SBSN auctions, issuance, primary dealers | **Not onboarded** |
| **FRED OECD mirror** | `IMDR_ECON_FRED_KEY` | Fast | Headline ID series | Live (partial) via [`playground/econ/fred/seed.yml`](../../../../playground/econ/fred/seed.yml) |
| **BIS Data Portal** — `stats.bis.org/api/v2/` | None (public SDMX-JSON) | Fast | Cross-country gauges: NEER/REER, DSR, Credit-to-GDP, policy rates | **Live** (2026-06-08) — 6 indicators × 8,811 obs via [`playground/econ/bis/fetch_indonesia.py`](../../../../playground/econ/bis/fetch_indonesia.py) |

BPS has API-grade access; BI does not. Closing the BI gap requires XLSX scraping of SEKI plus the per-topic statistics-portal landing pages.

## BPS API key — registration

The BPS Developer Portal issues free application keys; approval is typically instant once email is verified.

1. Browse to the **BPS Web API Documentation** at `https://webapi.bps.go.id/documentation/` and follow the link to register / **Daftar**.
2. Fill the form (name, email, organisation, intended use). Indonesian language is the default — Google Translate handles it cleanly.
3. Verify the confirmation email. The portal calls the key an "application key" (`api_key`); newly issued keys carry `status=actif` (active).
4. Paste the key into `.env` as:

   ```
   IMDR_BPS_API_KEY=<your-key>
   ```

5. The key is consumed by every BPS request as a query-string parameter: `?key={IMDR_BPS_API_KEY}`. There is no separate header or OAuth flow.

**Support contact**: `dataweb@bps.go.id` — for API/portal issues (key activation, quota questions, dataset queries).

**Rate limits**: BPS does not publish a documented rate ceiling, but the Korea-pattern caution still applies — throttle to ~1 req/sec in playground discovery. Treat any sustained 429/503 as a request to back off.

## Quick links

| Topic | Doc |
|---|---|
| **Production pipeline ops reference** | [indonesia_prod_pipeline.md](indonesia_prod_pipeline.md) |
| ID coverage by wiring-map cell (4×4 tracker) | [indonesia_indicator_inventory.md](indonesia_indicator_inventory.md) |
| BPS API technical reference (endpoints, gotchas, composite-key parser) | [bps_api_reference.md](bps_api_reference.md) |
| BPS dataset IDs → wiring-map cells | [id_coverage_plan.md](id_coverage_plan.md) |
| Concrete `dim_indicator` shopping list | [id_indicator_targets.md](id_indicator_targets.md) |
| Phase C fetcher results + per-fetcher var_ids (BPS) | [_playground/bps.md](_playground/bps.md) |
| Phase D + D2 fetcher results + SEKI table map (BI) | [_playground/bi.md](_playground/bi.md) |
| Phase D4 fetcher results + SDMX dataflow map (BIS) | [_playground/bis.md](_playground/bis.md) |
| Onboarding playbook (5-step workflow) | [`../onboarding_new_country.md`](../onboarding_new_country.md) |
| Indicator catalogue (the *what*) | [`../country_econ_blueprint.md`](../country_econ_blueprint.md) |
| Macro-economy wiring-map §7.17 (ID grid) | [`../macro_economy_wiring_map.md#717-indonesia-id`](../macro_economy_wiring_map.md#717-indonesia-id) |
| Korea worked reference example | [`../korea/`](../korea/) |

## Policy & fiscal document sources

Document-style sources for Bank Indonesia, Ministry of Finance, and DJPPR. **Not** `econ.fact_indicator` material — feeds the policy-document / research pipeline. Crawl-complexity flag per [`../onboarding_new_country.md`](../onboarding_new_country.md#crawl-complexity-flag-for-document-sources).

| Source | URL | Cadence | Notes |
|---|---|:---:|---|
| **BI Board of Governors policy news** | bi.go.id (search "Rapat Dewan Gubernur" / "BoG Meeting") | per RDG meeting | BI-Rate decisions, RDG outcomes, macroprudential + rupiah policy. Search-hub. |
| **BI Monetary Policy Review** | bi.go.id (search "Tinjauan Kebijakan Moneter" / "Monetary Policy Review") | monthly | Between quarterly reports. Search-hub. |
| **BI Monetary Policy Report** | bi.go.id (search "Laporan Kebijakan Moneter" / "Monetary Policy Report") | quarterly | Forecasts, inflation, growth, credit, liquidity, outlook. Search-hub. |
| **BI calendar & advance release schedule** | bi.go.id/en/statistik/seki/ | reference | RDG dates + statistics release schedule. |
| **BI governor speeches** | bi.go.id (search "Pidato Gubernur") | regular | Governor policy speeches + annual-meeting communication. Search-hub. |
| **BI Financial Stability Review** | bi.go.id (search "Kajian Stabilitas Keuangan" / "Financial Stability Review") | semi-annual | Macro-financial risk, credit, macropru. Search-hub. |
| **MoF Press releases** | kemenkeu.go.id/informasi-publik/publikasi/siaran-pers | regular | Tax/budget/macro fiscal communication. Direct archive — low complexity. |
| **DJPPR SBN auction calendar** | djppr.kemenkeu.go.id/page/loadViewer?idViewer=12217 | weekly | SUN/SBSN auction announcements. AEM CMS pattern — low complexity. |

## Source-agency contacts

To be filled as discovery progresses. Anchors:

- **Bank Indonesia** — Department of Statistics, Jl. M.H. Thamrin No.2, Jakarta. General contact via bicara@bi.go.id (BI Contact Center).
- **BPS** — Pusat Pelayanan Statistik, Jl. Dr. Sutomo No.6-8, Jakarta. `dataweb@bps.go.id` for API/portal/dataset issues.
- **DJPPR** — djppr@kemenkeu.go.id for SBN data queries.

## Related

- [`../macro_economy_wiring_map.md`](../macro_economy_wiring_map.md) — ID coverage state (§7.17).
- [`../onboarding_new_country.md`](../onboarding_new_country.md) — 5-step onboarding playbook.
- [`../country_econ_blueprint.md`](../country_econ_blueprint.md) — what to look for (4 engines × 4 cells).
- [`../korea/`](../korea/) — worked reference: 172 indicators across 4 vendors.
