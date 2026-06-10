# India — Government & Quasi-Government Document Sources

Last updated: 2026-06-10
Status: **Phase H discovery — playground daily-pull running.** 237 PDFs / 250 MB harvested across 11 streams from 5 agency clusters (RBI / MoSPI / PPAC / MoF / DEA). Migrations 086 + 087 + 089 applied — `dim_vendor` carries the official categories for the India publishers. Phase-J prod promotion **not entered** yet; everything lives in `playground/econ/in/govt/`.

This file is the master inventory of **Indian policy / macro-relevant text** sources (Reserve Bank of India, central-govt ministries, financial regulators, statistical agencies, fiscal documents, debt management). Sell-side research (JPM/MS/Goldman/etc.) is already covered in the broader research/Qdrant corpus; this document is the **official-voice counterpart**, discriminated downstream by `dim_vendor.vendor_category`.

Sources already listed in [`index.md`](./index.md) § Policy & fiscal document sources are merged in below and marked **(already-known)**.

Crawl-complexity flag legend (per [onboarding_new_country.md](../onboarding_new_country.md#crawl-complexity-flag-for-document-sources)):
- **LOW** — single GET, parse list, follow links
- **MED** — search-hub with keyword filter / AJAX listing / SharePoint-style aspx
- **HIGH** — JS-rendered listing (`networkidle`), or Akamai-gated, or Laravel CSRF form
- **BLOCKED** — corp-firewall confirmed from RV network

India adds two new crawler shapes beyond the canonical 5 in onboarding §H.3:
**Shape 6 — encrypted-title aggregator** (PIB obfuscates titles inside JS-decoded blobs) and **Shape 7 — corp-firewall blocked** (DEA / Labour Bureau / EPFO unreachable from RV's network). See the Crawl-pattern clustering section near the end of this doc.

URLs marked with **❓** are unverified to current shape (page existed at one point but listing mechanism not confirmed in this research pass).

Tier markers per [§H.4](../onboarding_new_country.md#h4-tier-classification): **T1** moves FX/govt-bond curve within 24h or carries canonical policy text; **T2** colour/depth; **T3** reference.

---

## 1. Central bank — Reserve Bank of India (RBI)

| # | Stream | URL | Cadence | Lang | Listing | Auth | Crawl | Tier | Why it matters |
|---|---|---|---|---|---|---|---|:---:|---|
| 1.1 | MPC resolution (Press Release) **(already-known)** | https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx | 6/yr | EN | HTML listing | none | LOW | **T1** | Repo / SDF / MSF / CRR / SLR decisions — moves curve + INR within minutes |
| 1.2 | MPC Minutes **(already-known)** | https://www.rbi.org.in/Scripts/PublicationReport.aspx?ID=911 | 6/yr (~14d after meeting) | EN | HTML listing | none | LOW | **T1** | Per-member rationale + vote count |
| 1.3 | Monetary Policy Report (MPR) **(already-known)** | https://www.rbi.org.in/Scripts/Publications.aspx?head=Monetary%20Policy%20Report | semi-annual (Apr/Oct) | EN | HTML listing | none | LOW | **T1** | Inflation + GDP forecast bands, output-gap commentary |
| 1.4 | Financial Stability Report (FSR) | https://www.rbi.org.in/Scripts/Publications.aspx?head=Financial+Stability+Report | semi-annual (Jun/Dec) | EN | HTML listing | none | LOW | **T1** | Systemic-risk dashboard + stress-test results + macroprudential calls |
| 1.5 | RBI Bulletin — monthly | https://www.rbi.org.in/Scripts/BS_ViewBulletin.aspx | monthly | EN | HTML listing | none | LOW | **T2** | "State of the Economy" chapter + Bulletin tables (T19C CPI, T27 call money, etc.) |
| 1.6 | RBI Annual Report | https://www.rbi.org.in/Scripts/AnnualReportPublications.aspx | annual (Aug) | EN | HTML listing | none | LOW | **T2** | Comprehensive RBI year-in-review + balance-sheet narrative |
| 1.7 | RBI Notifications (regulatory) **(already-known)** | https://www.rbi.org.in/Scripts/NotificationUser.aspx | event-driven | EN | HTML listing | none | LOW | **T1 (selective)** | FCNR / NRI / FPI / ECB / CRR / SLR / LRS / macro-prudential / liquidity-ops / G-Sec auction notifications |
| 1.8 | Governor + Deputy Governor speeches **(already-known)** | https://www.rbi.org.in/scripts/BS_speechesview.aspx | irregular (~2-3/mo) | EN | HTML listing | none | LOW | **T1** | Forward-guidance signals between MPC meetings |
| 1.9 | RBI Working Papers | https://www.rbi.org.in/Scripts/PublicationsView.aspx?Id=1198 ❓ | rolling | EN | HTML listing | none | LOW | **T3** | Research-staff economic analysis |
| 1.10 | RBI Occasional Papers | https://www.rbi.org.in/Scripts/PublicationsView.aspx?Id=23 ❓ | irregular | EN | HTML listing | none | LOW | **T3** | Longer-form research |
| 1.11 | RBI Press Releases (all other) | https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx | daily-ish | EN | HTML listing | none | LOW | **T1 (filtered)** | OMO / VRRR / G-Sec auction results / FX intervention disclosures — overlaps 1.7 |

**RBI crawler note**: every listing page on `rbi.org.in/Scripts/*.aspx` uses ASP.NET WebForms but the PDF links are direct `https://rbidocs.rbi.org.in/rdocs/{Section}/PDFs/{filename}.PDF`. Plain `httpx.get` works; no PostBack required for the listing read. Our daily-pull harvester captures 30 PDFs from streams 1.1 / 1.5–1.8 in a single pass (the 30-per-source cap, not the source's true depth).

---

## 2. Cabinet ministries

| # | Stream | URL | Cadence | Lang | Listing | Auth | Crawl | Tier | Why it matters |
|---|---|---|---|---|---|---|---|:---:|---|
| 2.1 | **MoF / DEA** — Union Budget (Receipts/Expenditure books, Speech) **(already-known)** | https://www.indiabudget.gov.in/ | annual (Feb 1) | EN | HTML home with `<a href="doc/*.pdf">` | none | LOW | **T1** | Fiscal-deficit target, borrowing programme size, revenue assumptions |
| 2.2 | **MoF / DEA** — Economic Survey + Statistical Appendix **(already-known)** | https://www.indiabudget.gov.in/economicsurvey/ | annual (day before Budget) | EN | HTML home + chapter list | none | LOW | **T1** | Govt's official macro view, sectoral analysis — drives market expectations for Budget |
| 2.3 | **MoF / DEA** — Mid-Year Economic Analysis | https://dea.gov.in/ | annual (Dec) | EN | HTML listing | none | BLOCKED | **T2** | Mid-year fiscal review — DEA site `dea.gov.in` returns `ConnectError` from corp net 2026-06-10 |
| 2.4 | **MoF / CGA** — Monthly Accounts of GoI press notes | https://cga.nic.in/MonthlyReport.aspx | monthly | EN | ASP.NET PostBack table | none | MED | **T1** | Monthly receipts + expenditure + fiscal-deficit cumulative narrative (companion to the XLSM data) |
| 2.5 | **MoCI / DPIIT** — FDI policy notifications | https://dpiit.gov.in/ | event-driven | EN | Next.js SPA | none | HIGH | **T2** | FDI rules, PLI scheme launches/reviews |
| 2.6 | **MoPNG / PPAC** — monthly Flash Report + Indian Crude Basket **(already-known)** | https://www.ppac.gov.in/prices/internationalprices | monthly | EN | HTML listing with download.php links | none | LOW | **T2** | Crude price pass-through to CPI Fuel + Trade Deficit |
| 2.7 | **MoA** — MSP announcements + PM-KISAN | https://agricoop.gov.in/ ❓ | annual (Kharif May/Jun, Rabi Oct) | EN | HTML listing | none | MED | **T1 (cycle-relevant)** | MSP step-changes drive food CPI; PM-KISAN transfer events |
| 2.8 | **MoSPI** — CPI press releases **(already-known)** | https://www.mospi.gov.in/ via `/api/latest-release/get-web-latest-release-list` (search="CPI for") | monthly (~12th) | EN | JSON listing API | none | MED | **T1** | India CPI YoY headline — moves RBI rate expectations within minutes |
| 2.9 | **MoSPI** — IIP press releases **(already-known)** | same API, search="Quick Estimates of IIP" | monthly (~10th) | EN | JSON listing API | none | MED | **T1** | Industrial activity proxy |
| 2.10 | **MoSPI** — Quarterly + Annual GDP estimates **(already-known)** | same API, search="Provisional Estimates of Annual GDP" / "Quarterly Estimates of GDP" | quarterly + annual | EN | JSON listing API | none | MED | **T1** | The GDP print — moves curve on release |
| 2.11 | **MoSPI** — PLFS monthly + quarterly + annual bulletins **(already-known)** | same API, search="Periodic Labour Force" | monthly + quarterly + annual | EN | JSON listing API | none | MED | **T2** | Labour-force participation, unemployment headline |

**MoSPI crawler note** (high signal): all four MoSPI streams share **one listing API** at `POST https://www.mospi.gov.in/api/latest-release/get-web-latest-release-list`. Body: `{page_no, page_size, search_term, sort_field, sort_order, from_date, to_date, lang, data_source}`. The `file_one` field carries the PDF; the `file_two` field (when present) carries the data XLSX. This single endpoint unlocks every MoSPI publication.

---

## 3. Financial regulators

| # | Stream | URL | Cadence | Lang | Listing | Auth | Crawl | Tier | Why it matters |
|---|---|---|---|---|---|---|---|:---:|---|
| 3.1 | **SEBI** — board meeting outcomes | https://www.sebi.gov.in/sebiweb/home/HomeAction.do?doListingAll=yes&sid=4 ❓ | monthly | EN | HTML listing | none | MED | **T2** | Bond-market structure (FPI debt limits, T+1 settlement, derivative norms) |
| 3.2 | **SEBI** — circulars + policy releases | https://www.sebi.gov.in/sebiweb/home/HomeAction.do?doListing=yes&sid=1&ssid=5&smid=0 ❓ | event-driven | EN | HTML listing | none | MED | **T2** | Securities regulation — IPO rules, F&O changes |
| 3.3 | **IRDAI** — board outcomes + circulars | https://irdai.gov.in/circulars ❓ | regular | EN | HTML listing | none | MED | **T3** | Insurance-sector G-Sec demand context |
| 3.4 | **CBIC** — Customs notifications (BCD changes, tariff revisions) | https://www.cbic.gov.in/ ❓ | event-driven | EN | HTML listing | none | MED | **T2** | Trade-policy event corpus, basic-customs-duty changes feed into WPI |

---

## 4. Statistical agencies

Covered under §2 (MoSPI rows 2.8-2.11) since MoSPI IS the statistical agency under the MoSPI ministry. India doesn't split stat-office from ministry the way Korea (KOSTAT vs MOEF) or Japan does.

Additional statistical-side sources:

| # | Stream | URL | Cadence | Lang | Listing | Auth | Crawl | Tier | Why it matters |
|---|---|---|---|---|---|---|---|:---:|---|
| 4.1 | **DGCIS** — monthly trade press notes | https://tradestat.commerce.gov.in/ via PIB (DGCIS releases its monthly trade through PIB press notes; tradestat itself is data-side) | monthly (~15th) | EN | PIB press release | none | MED | **T1** | Headline merchandise exports + imports + trade balance — moves INR |
| 4.2 | **Labour Bureau** — CPI-IW, CPI-AL, WRI press notes | https://labourbureau.gov.in/ ❓ | monthly | EN | HTML listing | none | BLOCKED | **T2** | Worker-side CPI (DA hike trigger), wage indices — `labourbureau.gov.in` returns `ConnectError` from corp net 2026-06-10 |
| 4.3 | **DPIIT / OEA** — WPI press releases | https://eaindustry.nic.in/uploaded_files/Press_Release.pdf | monthly (~14th) | EN | single PDF (latest only) | none | LOW | **T1** | Wholesale price headline — companion to CPI for inflation read |
| 4.4 | **DPIIT / OEA** — 8-Core Industries Index press notes | https://eaindustry.nic.in/eight_core_infra/ | monthly (~end-of-month) | EN | HTML listing | none | LOW | **T1** | Sectoral output proxy leading IIP by ~10 days |

---

## 5. Fiscal documents (specialist)

| # | Stream | URL | Cadence | Lang | Listing | Auth | Crawl | Tier | Why it matters |
|---|---|---|---|---|---|---|---|:---:|---|
| 5.1 | **CGA** — Monthly Accounts of GoI (data XLSM) | https://cga.nic.in/MonthDashboardReport/Published/list.aspx → `/writereaddata/MonthAccount/MonthAccountDashboard/DAMA dashboard {Month YYYY} Data file.xlsm` | monthly (~end of next month) | EN | HTML listing | none | LOW | **T1** | The data side of fiscal release — feeds A14 series load, not Phase H |
| 5.2 | **DIPAM** — disinvestment proceeds + IPOs | https://dipam.gov.in/ | event-driven | EN | HTML home (304KB; needs deeper probe) | none | MED | **T2** | Disinvestment receipts feed budget arithmetic |
| 5.3 | **DJPPR equivalent — no Indian counterpart** | RBI publishes the borrowing calendar instead | semi-annual (H1, H2) | EN | RBI press release | none | LOW | **T1** | G-Sec + T-bill + SDL issuance size by tenor — covered under 1.7 |

---

## 6. Debt management / state banks / market infrastructure

RBI does India's debt-management role itself (no separate DMO). The Public Debt Office sits inside RBI and publishes via 1.7 + 1.11.

| # | Stream | URL | Cadence | Lang | Listing | Auth | Crawl | Tier | Why it matters |
|---|---|---|---|---|---|---|---|:---:|---|
| 6.1 | **CCIL** — daily MIBOR / MIFOR / G-Sec curve fixings | https://www.ccilindia.com/ | daily | EN | login-gated | desk creds needed | HIGH | **T1** | Onshore fixings — for time-series and curve construction |
| 6.2 | **NSE** — F&O turnover, daily settlement | https://www.nseindia.com/ | daily | EN | JSON API but bot-hostile | none | HIGH | **T2** | Equity-derivatives positioning |
| 6.3 | **BSE** — equivalent | https://www.bseindia.com/ | daily | EN | JSON API but bot-hostile | none | HIGH | **T2** | Same as 6.2 for BSE-listed F&O |

---

## 7. Pension / sovereign-wealth / state banks

| # | Stream | URL | Cadence | Lang | Listing | Auth | Crawl | Tier | Why it matters |
|---|---|---|---|---|---|---|---|:---:|---|
| 7.1 | **EPFO** — monthly payroll release | https://www.epfindia.gov.in/ | monthly | EN | HTML listing | none | BLOCKED | **T2** | Formal-sector employment proxy — `epfindia.gov.in` `ConnectError` from corp net |
| 7.2 | **PFRDA** — NPS scheme returns + AUM | https://www.pfrda.org.in/ ❓ | monthly | EN | HTML listing | none | MED | **T3** | Pension allocation flow signal |

---

## 8. Election + political-cycle infrastructure

| # | Stream | URL | Cadence | Lang | Listing | Auth | Crawl | Tier | Why it matters |
|---|---|---|---|---|---|---|---|:---:|---|
| 8.1 | **ECI** — election dates, results | https://www.eci.gov.in/ | irregular | EN | HTML listing | none | MED | **T1 (cycle-relevant)** | General + State elections → policy-continuity risk for INR/rates |
| 8.2 | **GST Council** — meeting outcomes | https://gstcouncil.gov.in/ | monthly | EN | HTML listing | none | MED | **T2** | Indirect-tax-rate council; structural for revenue |

---

## 9. Quasi-government think tanks

India lacks the Korea-style state-funded think tank ecosystem (KDI / KIEP). Closest analogues:

| # | Stream | URL | Cadence | Lang | Listing | Auth | Crawl | Tier | Why it matters |
|---|---|---|---|---|---|---|---|:---:|---|
| 9.1 | **NIPFP** — National Institute of Public Finance and Policy | https://www.nipfp.org.in/publications/ ❓ | irregular | EN | HTML listing | none | MED | **T3** | Fiscal/tax research |
| 9.2 | **ICRIER** — Indian Council for Research on International Economic Relations | https://icrier.org/publications/ ❓ | regular | EN | HTML listing | none | MED | **T3** | Trade + international economics |
| 9.3 | **NCAER** — National Council of Applied Economic Research | https://www.ncaer.org/ ❓ | irregular | EN | HTML listing | none | MED | **T3** | Macro forecasting (their BES survey) |

---

## 10. Other / cross-cutting

| # | Stream | URL | Cadence | Lang | Listing | Auth | Crawl | Tier | Why it matters |
|---|---|---|---|---|---|---|---|:---:|---|
| 10.1 | **PIB** — Press Information Bureau (all-government aggregator) | https://pib.gov.in/AllRelease.aspx?MinistryId={N} | daily | EN/HI | HTML listing with **client-decoded encrypted titles** | none | HIGH | **T2** | Single aggregator but PIB obfuscates release titles inside JS-decoded blobs — plain grep returns 0 hits. Needs Playwright + decode pass. |
| 10.2 | **IMD** — monsoon forecasts (LRF + updates) | https://mausam.imd.gov.in/responsive/longrange.php ❓ | seasonal (Apr + Jun for SW monsoon; Oct for NE) | EN | HTML listing | none | LOW | **T1** | Monsoon outlook is the single biggest macro variable for India ag/CPI |

---

## Crawl-pattern clustering

Mapping India's sources against the 5 canonical crawler shapes from [onboarding §H.3](../onboarding_new_country.md#h3-crawl-complexity-legend-per-row):

| Shape | India agencies that fit | Probed? |
|---|---|---|
| **Shape 1 — RSS-fan** | (none — Indian govt sites have no RSS endpoints on their press boards) | n/a |
| **Shape 2 — egov BBS GET-listing** | RBI all streams (1.1–1.11) · PPAC (2.6) · DPIIT/OEA (4.3, 4.4) · Budget (2.1) · Econ Survey (2.2) | ✅ all proven |
| **Shape 3 — egov BBS POST-listing** | MoSPI listing API (single endpoint covers 2.8–2.11) | ✅ proven |
| **Shape 4 — DT-rendered list / Akamai-gated** | CGA (2.4) — ASP.NET PostBack | ⚠ press notes deferred (XLSM is the data source) |
| **Shape 5 — JS-onclick article handler** | SEBI · IRDAI · CBIC · MoCI/DPIIT FDI (Next.js SPA) | ❌ deferred — needs Playwright session |
| **Shape 6 (new) — encrypted-title aggregator** | PIB (10.1) | ❌ deferred — needs JS-decode pass |
| **Shape 7 (new) — corp-firewall blocked** | DEA (2.3) · Labour Bureau (4.2) · EPFO (7.1) | ❌ blocked from corp net |

**India shape distribution differs from Korea**: Korea has heavy RSS-fan coverage (MOEF alone has 10 RSS boards); India has zero RSS endpoints on the agencies probed. Plain `httpx.get` + HTML scrape works for ~80% of India sources — simpler than Korea, but with fewer high-frequency signals.

---

## Per-agency body + PDF resolution recipes

Status of each Tier-1 agency's `(body_text, pdf_bytes)` paths for the `filings.ingest_filing` contract:

| Agency | body_text source | pdf_bytes source | Status |
|---|---|---|---|
| RBI (1.1–1.11) | none (PDF-only) | direct `rbidocs.rbi.org.in/rdocs/{Section}/PDFs/{file}.PDF` from listing | ✅ |
| MoSPI (2.8–2.11) | none | `file_one.path` from listing API → `mospi.gov.in/{path}` | ✅ |
| PPAC (2.6) | none | direct from listing page anchors | ✅ |
| MoF Budget (2.1) | none | `indiabudget.gov.in/doc/*.pdf` — 14/30 in sample; 16 return 503 (older years stale linkage) | ⚠ partial |
| DEA Econ Survey (2.2) | none | `indiabudget.gov.in/economicsurvey/doc/*.pdf` — 21/30 in sample | ⚠ partial |
| CGA (2.4 press) | none | not yet harvested — page is ASP.NET PostBack | ❌ defer |
| SEBI / IRDAI / CBIC / DPIIT-FDI | likely HTML body + linked PDFs | unverified | ❌ defer to Playwright pass |

**Why no body_text for any India source today**: every probed agency publishes the policy text as a downloadable PDF rather than HTML-body, so `pdf_bytes` is always the canonical path. Korea differs here — KCS publishes JPG scans (no PDF), MOTIR has TLS-blocked PDFs and we fall back to body. India's homogeneity is convenient.

---

## Discovery deliverable status (Phase H stop-here checklist)

Per [onboarding_new_country.md §H.7](../onboarding_new_country.md#h7-discovery-deliverable--stop-here):

- [x] `india_govt_doc_sources.md` populated (this file)
- [x] `playground/econ/in/govt/daily_pull.py` — bulk harvester
- [x] `playground/econ/in/govt/_test_downloads.py` — pre-flight verifier
- [x] `playground/econ/in/govt/ingest_filings.py` — ingest helper that calls `imdr.research.filings.ingest_filing_sync` once per PDF
- [x] `data/econ/in/govt/{vendor}/2026/06/10/*.pdf` — **237 PDFs / 250 MB** harvested
- [x] `data/econ/in/govt/_manifest_2026-06-10.json` — proves idempotency hook for re-runs
- [x] Migrations 086 / 087 / 089 applied — India official vendors seeded with `vendor_category=official_*`

**Discovery deliverable: COMPLETE.** Promotion to `scripts/econ/in/govt/` + `scripts/econ/in/in_daily.py` + scheduler registration is the Phase-J workflow — see [`../econ_to_prod.md`](../econ_to_prod.md) Track B.

---

## Recommended priority tiers

**Tier 1 — build first** (market-moving on release OR carries canonical policy text):

- RBI: 1.1 MPC resolution · 1.2 MPC minutes · 1.3 MPR · 1.4 FSR · 1.8 Governor speeches · 1.7 + 1.11 selective Notifications (FCNR / NRI / FPI / liquidity-ops / G-Sec auction)
- MoF / DEA: 2.1 Union Budget · 2.2 Economic Survey · 5.3 RBI borrowing calendar (via 1.7)
- CGA: 2.4 Monthly Accounts of GoI press notes (companion to A14 data)
- MoSPI: 2.8 CPI · 2.9 IIP · 2.10 GDP estimates
- DPIIT/OEA: 4.3 WPI press release · 4.4 8-Core Industries
- DGCIS: 4.1 monthly trade press notes (via PIB)
- IMD: 10.2 monsoon forecasts (LRF + updates)
- CCIL: 6.1 daily fixings (subject to credentials)
- ECI: 8.1 election dates (cycle-relevant)

**Tier 2 — build after Tier 1 + once topic filter exists**:

- RBI: 1.5 Bulletin · 1.6 Annual Report
- MoSPI: 2.11 PLFS bulletins
- PPAC: 2.6 monthly Flash Report + Indian Crude Basket
- DPIIT: 2.5 FDI policy notifications
- DEA: 2.3 Mid-Year Economic Analysis (blocked)
- SEBI: 3.1 / 3.2 board outcomes + circulars
- CBIC: 3.4 Customs notifications
- Labour Bureau: 4.2 CPI-IW / CPI-AL / WRI (blocked)
- DIPAM: 5.2 disinvestment proceeds
- EPFO: 7.1 monthly payroll (blocked)
- GST Council: 8.2 meeting outcomes
- PIB: 10.1 aggregator (needs decode pass)

**Tier 3 — defer until 1-2 operational**:

- RBI: 1.9 Working Papers · 1.10 Occasional Papers
- IRDAI: 3.3 board outcomes
- NSE / BSE: 6.2 / 6.3 F&O daily reports
- PFRDA: 7.2 NPS returns
- All §9 think tanks (NIPFP / ICRIER / NCAER)

## Open questions

1. **PIB title-decode** (10.1) — what JS payload decrypts the release titles? If decodable, PIB becomes the single best aggregator endpoint for India (covers GST monthly collection releases that have no clean direct source — see [`in_coverage_plan.md`](in_coverage_plan.md) §A23 deprioritisation).
2. **CCIL access** (6.1) — desk has terminal login; are machine-readable credentials available? Unblocks MIBOR / MIFOR / G-Sec curve / OIS daily fixings.
3. **CGA press notes** (2.4) — ASP.NET PostBack table not yet probed. Are the monthly press notes actually distinct from the XLSM dashboard's narrative text, or do they duplicate? If duplicate, skip; if not, deferred to a Playwright pass.
4. **DEA Mid-Year Analysis** (2.3) — `dea.gov.in` is corp-net blocked. Is the document published anywhere else (PIB? indiabudget.gov.in mirror?)?
5. **MoA / MSP archive** (2.7) — `agricoop.gov.in` reachable but not yet probed. URL pattern + listing API unknown.
6. **Stale Budget URLs** — the home-page link list at `indiabudget.gov.in` references 25 PDFs that return persistent 503 (e.g. `/doc/AFS/afs1.pdf`). Sub-page crawl into `/doc/afs/allafs.htm` may recover them — defer to next pass.
7. **Budget historical years** — current harvester captures latest Budget only. Backfill of earlier years' AFS / Receipts / Expenditure books requires per-year discovery (URL patterns change between fiscal years).
8. **RBI Notifications archive depth** — current 30-PDF cap on stream 1.7 only captures the most recent month or two. For the FCNR-MIFOR worked example, deep history of FCNR notifications would need a pagination loop on `NotificationUser.aspx`.

## Worked examples

- **Korea** is the canonical reference — see [`../korea/govt_doc_sources.md`](../korea/govt_doc_sources.md). 7 agencies + KOSTAT via existing `mods` vendor; 5 crawler shapes proven; 307+ items in `research.dim_report` post-Phase-J as of 2026-06-10.
- **Australia** is the lighter discovery example — see [`../australia/au_cb_documents.md`](../australia/au_cb_documents.md). 6 fetchers, ~33 items/day baseline.

India's Phase-H artefacts now mirror the Korea+AU shape. Phase J (promotion + scheduler) deferred to user sign-off.
