# Australia — Central Bank + Treasury Document Sources

Last updated: 2026-06-10

The data-time-series side of AU econ is in [`australia_indicator_inventory.md`](australia_indicator_inventory.md). This doc inventories the **document-style sources** — Board minutes, SMP, FSR, Budget Papers, etc. These feed the research-document pipeline (PDF → research store), **not** `econ.fact_indicator`.

Status: discovery-only. None of these documents are auto-ingested yet. The table below is the download checklist when the document pipeline is built (or for monthly manual capture).

---

## RBA — Reserve Bank of Australia

| Document | URL | Cadence | Format | Macro use | Download method |
|---|---|---|:---:|---|---|
| **Governor's Statement** (cash-rate decision) | `rba.gov.au/monetary-policy/int-rate-decisions/{YYYY}/` | 8/yr (post-meeting, T+0) | HTML | The decision itself — read first | Akamai gated; Playwright |
| **Board minutes** | `rba.gov.au/monetary-policy/rba-board-minutes/` | 8/yr (T+14 after meeting) | HTML | Voting / debate / forward guidance hints | Akamai gated; Playwright |
| **Statement on Monetary Policy (SMP)** | `rba.gov.au/publications/smp/{YYYY}/{mmm}/` | Quarterly (Feb/May/Aug/Nov) | HTML + PDF | The forecast anchor; revisions in here | Akamai gated; Playwright |
| **Financial Stability Review (FSR)** | `rba.gov.au/publications/fsr/{YYYY}/` | Semi-annual (Apr + Oct) | HTML + PDF | Systemic risk + housing/credit stress | Akamai gated; Playwright |
| **Speeches** (Governor / DG / senior) | `rba.gov.au/speeches/{YYYY}/` | ~80-120/yr | HTML | Forward guidance + research views | Akamai gated; Playwright |
| **RBA Bulletin** | `rba.gov.au/publications/bulletin/{YYYY}/{mmm}/` | Quarterly | HTML + PDF | Research articles on AU macro/financial topics | Akamai gated; Playwright |
| **RBA Annual Report** | `rba.gov.au/publications/annual-reports/{YYYY}/` | Annual (October) | PDF | Institutional view + ops detail | Akamai gated; Playwright |
| **Chart Pack** | `rba.gov.au/chart-pack/` | Monthly | PDF | RBA's standard chart deck — single PDF | Akamai gated; Playwright |
| **Conference papers** | `rba.gov.au/publications/confs/` | Annual conference | PDF | Research-grade analysis | Akamai gated; Playwright |

**RBA gating:** all `rba.gov.au` paths return HTTP 403 to plain `requests`/`httpx`. Use the existing Playwright pattern (`playground/econ/rba/profile/`) — first nav usually works. The stats tables use this; documents work the same way.

---

## AOFM — Australian Office of Financial Management

| Document | URL | Cadence | Format | Macro use | Download method |
|---|---|---|:---:|---|---|
| **Annual Report** | `aofm.gov.au/publications/annual-reports` | Annual (October) | PDF | Funding strategy, market commentary, debt-cost analysis | **Corp-firewall blocked** — manual Edge per [`_playground/aofm.md`](_playground/aofm.md) |
| **Issuance calendar** (forward) | `aofm.gov.au/publications/issuance-calendar` | Quarterly | PDF | Next-quarter TB/TIB/TN auction schedule | Same |
| **Investor presentation** | `aofm.gov.au/publications/investor-presentations` | Quarterly + ad-hoc | PDF (slide deck) | AOFM's pitch to bond buyers; positioning view | Same |
| **Market notices** (auction announcements) | `aofm.gov.au/news` | Per auction | HTML | Tender size + maturity | Same |
| **Debt issuance strategy** | `aofm.gov.au/publications/debt-issuance-strategy` | Annual (May) | PDF | Year-ahead programme guidance | Same |

**AOFM gating:** see [`_playground/aofm.md`](_playground/aofm.md) — file-download path on `aofm.gov.au/sites/default/files/*` is blocked from `rvsg-fs01`. Manual Edge or IT whitelist.

---

## Treasury (Department of the Treasury)

| Document | URL | Cadence | Format | Macro use | Download method |
|---|---|---|:---:|---|---|
| **Federal Budget Papers** (BP1-BP5) | `budget.gov.au/{YYYY-YY}/content/bp1/` ... | Annual (May) | PDF + XLSX | Full fiscal projections, sector forecasts, debt path | `.gov.au` — likely same firewall issue as AOFM; manual Edge |
| **MYEFO** (Mid-Year Economic & Fiscal Outlook) | `budget.gov.au/myefo/{YYYY-YY}/` | Annual (December) | PDF + XLSX | Mid-year fiscal revisions | Same |
| **Pre-election Economic & Fiscal Outlook (PEFO)** | `treasury.gov.au` | Pre-election (~3yr) | PDF | Pre-election fiscal baseline | Same |
| **Final Budget Outcome** | `budget.gov.au/fbo/{YYYY-YY}/` | Annual (September) | PDF | Realised vs forecast — credibility check | Same |
| **Intergenerational Report (IGR)** | `treasury.gov.au/publication/intergenerational-report-{YYYY}` | Every 5 yrs | PDF | 40-yr fiscal/demographic projection | Same |
| **Treasury Round-Ups / research papers** | `treasury.gov.au/publication` | Periodic | PDF | Treasury economics commentary | Same |

**Treasury gating:** `budget.gov.au` and `treasury.gov.au` are both `.gov.au` — assume same TLS-inspection block as AOFM until tested. **Test with one PDF before automating.**

---

## APRA — Australian Prudential Regulation Authority

| Document | URL | Cadence | Format | Macro use | Download method |
|---|---|---|:---:|---|---|
| **Quarterly ADI Performance Statistics** | `apra.gov.au/quarterly-authorised-deposit-taking-institution-statistics` | Quarterly | XLSX + PDF | Bank-sector capital, NPL, profitability ratios | `.gov.au` — likely firewall; test required |
| **Quarterly ADI Property Exposures** | `apra.gov.au/quarterly-authorised-deposit-taking-institution-property-exposures` | Quarterly | XLSX | Bank exposure to housing — leverage/LVR distribution | Same |
| **Quarterly General Insurance Performance** | `apra.gov.au/quarterly-general-insurance-performance-statistics` | Quarterly | XLSX | Insurance-sector aggregate | Same |
| **Insight magazine articles** | `apra.gov.au/insight` | Monthly-ish | PDF / HTML | Regulatory commentary, macropru signals | Same |
| **Annual Report** | `apra.gov.au/annual-reports` | Annual (October) | PDF | Sector-wide regulatory view | Same |

**APRA quarterly statistics partly overlap RBA E1+E2 in our DB** — APRA is the source-of-truth for bank-sector aggregates (RBA D2/E-tables aggregate APRA's underlying ADI reports). Treat as supplementary detail, not primary.

---

## ABS — Australian Bureau of Statistics (document-only releases)

The data side (SDMX) is fully covered under [`_playground/abs.md`](_playground/abs.md). These are the document-style ABS releases that include analytical commentary on top of the time-series:

| Document | URL | Cadence | Format | Macro use | Download method |
|---|---|---|:---:|---|---|
| **CPI Methodology + commentary** | `abs.gov.au/statistics/economy/price-indexes-and-inflation/consumer-price-index-australia/{period}` | Each release | HTML + XLSX | ABS's own narrative on the CPI print | Plain HTTPS works (already used for SDMX) |
| **Labour Force release commentary** | `abs.gov.au/statistics/labour/employment-and-unemployment/labour-force-australia/{period}` | Monthly | HTML | Headline numbers + ABS commentary | Plain HTTPS |
| **National Accounts releases** | `abs.gov.au/statistics/economy/national-accounts/australian-national-accounts-national-income-expenditure-and-product/{period}` | Quarterly | HTML | GDP release + commentary | Plain HTTPS |

ABS plays nicely with our existing pipeline — these are an easy add when we want them.

---

## Priority for ingest (when document pipeline is built)

1. **RBA Governor's Statement + Board minutes** — 16 docs/yr; THE highest-information sources
2. **RBA SMP** — 4/yr; the forecast anchor
3. **RBA FSR** — 2/yr; macropru / financial stability
4. **Treasury Budget + MYEFO** — 2/yr; full fiscal view (Budget paper 1 is the macro chapter)
5. **AOFM Annual Report + Issuance Strategy** — 2/yr; debt-management forward view
6. **RBA Speeches** — high frequency but variable signal; consider topic-filtering
7. **APRA Quarterly ADI stats** — 4/yr; complements RBA E-tables already in DB
8. **RBA Bulletin** — 4/yr; deeper research articles

## Implementation notes

- The IMDR research-document pipeline (`research.*` schema, picasso/lois agents) is the natural home — these are PDF documents to be parsed + embedded, not time-series to be inserted in `econ.fact_indicator`.
- Per-vendor doc scrapers live at `docs/admin/research/scrapers/{vendor}.md` for sell-side research; CB scrapers would follow the same shape (`docs/admin/research/scrapers/{rba,aofm,treasury,apra}.md`).
- The Playwright profile used for RBA stats tables (`playground/econ/rba/profile/`) can be reused for RBA documents — same Akamai layer.
- AOFM documents have the same `*.gov.au` firewall block as AOFM XLSX files; same workaround (manual Edge or IT whitelist).

## Related

- [`australia_indicator_inventory.md`](australia_indicator_inventory.md) — the data-side counterpart
- [`index.md`](index.md) — country overview
- [`_playground/aofm.md`](_playground/aofm.md) — AOFM-specific gating context
- [`_playground/rba.md`](_playground/rba.md) — RBA Akamai gating context
