# Australia — Central Bank + Treasury Document Sources

Last updated: 2026-06-10

The data-time-series side of AU econ is in [`australia_indicator_inventory.md`](australia_indicator_inventory.md). This doc inventories the **document-style sources** — Board minutes, SMP, FSR, Budget Papers, etc. These feed the research-document pipeline (PDF → research store), **not** `econ.fact_indicator`.

Status: discovery scaffold + **4 fetchers** landed 2026-06-10 at [`playground/econ/au/govt/`](../../../../playground/econ/au/govt/) (mirror of the proven Korea pattern). Live fetchers cover the full **RBA Tier-1 stack** — Governor's Statement (decision, T+0), Board Minutes (T+14), SMP (quarterly forecasts), FSR (semi-annual stability review). Daily snapshots at `playground/econ/au/govt/data/snapshots/{YYYY-MM-DD}.json` with rolling dedup via `data/seen.json`. **NO DB writes yet** — manifest-only until the research-doc pipeline (`research.dim_report` / `research.fact_chunk`) absorbs filings.

**Reachability finding (2026-06-10 probe):** Treasury, Budget, and APRA hosts all return 200 OK over plain HTTPS — including a verified PDF download from `apra.gov.au/sites/default/files/*` (the same Drupal path pattern that's blocked for AOFM). The corp TLS-inspection block on AOFM is **host-specific, not path-based**. This promotes Treasury + APRA out of the Tier-3 manual-skip bucket and into Tier-2 build candidates with plain httpx (no Playwright needed).

---

## RBA — Reserve Bank of Australia

| Document | URL | Cadence | Format | Macro use | Download method |
|---|---|---|:---:|---|---|
| **Governor's Statement** (cash-rate decision) — **LIVE 2026-06-10** | listing: `rba.gov.au/monetary-policy/int-rate-decisions/{YYYY}/` · detail: `rba.gov.au/media-releases/{YYYY}/mr-{YY}-{NN}.html` | 8/yr (post-meeting, T+0) | HTML | The decision itself — read first | `playground/econ/au/govt/fetch_rba_governors_statement.py` (Playwright headed, fresh `profile_rba_gov/` per run); discovery-only, no PDF fetch |
| **Board minutes** — **LIVE 2026-06-10** | listing: `rba.gov.au/monetary-policy/rba-board-minutes/{YYYY}/` · detail: `.../{YYYY-MM-DD}.html` | 8/yr (T+14 after meeting) | HTML | Voting / debate / forward guidance hints — higher signal than the Governor's Statement | `playground/econ/au/govt/fetch_rba_board_minutes.py` (Playwright headed, fresh `profile_rba_minutes/` per run); discovery-only |
| **Statement on Monetary Policy (SMP)** — **LIVE 2026-06-10** | listing: `rba.gov.au/publications/smp/` · detail: `.../{YYYY}/{feb\|may\|aug\|nov}/` | Quarterly (Feb/May/Aug/Nov) | HTML + PDF | The forecast anchor — GDP/CPI/unemployment forecast revisions | `playground/econ/au/govt/fetch_rba_smp.py` (Playwright headed, fresh `profile_rba_smp/` per run); discovery-only |
| **Financial Stability Review (FSR)** — **LIVE 2026-06-10** | listing: `rba.gov.au/publications/fsr/` · detail: `.../{YYYY}/{apr\|oct}/` | Semi-annual (Apr + Oct) | HTML + PDF | Systemic risk + housing/credit stress | `playground/econ/au/govt/fetch_rba_fsr.py` (Playwright headed, fresh `profile_rba_fsr/` per run); discovery-only |
| **Speeches** (Governor / DG / senior) — deferred | `rba.gov.au/speeches/{YYYY}/` | ~80-120/yr | HTML | Bulk is noise; ~10/yr from Governor / Deputy are policy-shifting | Build deferred until a topic-filter design exists (otherwise drowns the daily snapshot in noise) |
| **RBA Bulletin** — skip | `rba.gov.au/publications/bulletin/{YYYY}/{mmm}/` | Quarterly | HTML + PDF | Research articles — academic, lags real-time policy | Not worth automating; occasional manual read |
| **RBA Annual Report** — skip | `rba.gov.au/publications/annual-reports/{YYYY}/` | Annual (October) | PDF | Institutional ops view | Not market-moving |
| **Chart Pack** — skip | `rba.gov.au/chart-pack/` | Monthly | PDF | Chart deck over data we already have | Adds no information; all underlying series already in DB |
| **Conference papers** — skip | `rba.gov.au/publications/confs/` | Annual conference | PDF | Research-grade analysis | Not desk-relevant |

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

**Treasury gating (probed 2026-06-10):** **NOT blocked.** `treasury.gov.au/publication` returns 200 OK with full HTML over plain httpx; `budget.gov.au/{YYYY-YY}/` likewise. PDF download path not yet probed — Treasury wraps most publications behind detail-page HTML so the per-doc PDF URL requires a 2-step crawl. Build with plain httpx, no Playwright needed.

---

## APRA — Australian Prudential Regulation Authority

| Document | URL | Cadence | Format | Macro use | Download method |
|---|---|---|:---:|---|---|
| **Quarterly ADI Performance Statistics** | `apra.gov.au/quarterly-authorised-deposit-taking-institution-statistics` | Quarterly | XLSX + PDF | Bank-sector capital, NPL, profitability ratios | `.gov.au` — likely firewall; test required |
| **Quarterly ADI Property Exposures** | `apra.gov.au/quarterly-authorised-deposit-taking-institution-property-exposures` | Quarterly | XLSX | Bank exposure to housing — leverage/LVR distribution | Same |
| **Quarterly General Insurance Performance** | `apra.gov.au/quarterly-general-insurance-performance-statistics` | Quarterly | XLSX | Insurance-sector aggregate | Same |
| **Insight magazine articles** | `apra.gov.au/insight` | Monthly-ish | PDF / HTML | Regulatory commentary, macropru signals | Same |
| **Annual Report** | `apra.gov.au/annual-reports` | Annual (October) | PDF | Sector-wide regulatory view | Same |

**APRA gating (probed 2026-06-10):** **NOT blocked.** Both `apra.gov.au/quarterly-*` HTML pages AND PDFs/XLSXs at `apra.gov.au/sites/default/files/*` return 200 OK over plain httpx (188 KB PDF retrieved, valid `%PDF-1.6` header). Same Drupal path pattern that AOFM uses, but APRA's host is NOT subject to the corp firewall — the AOFM block is host-specific. Build with plain httpx, no Playwright needed.

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

## Priority decisions (rationale captured 2026-06-10)

Honest signal/effort ranking for a macro hedge-fund desk that already pulls AU rates, FX, curve, inflation, and credit data:

- ✅ **Built (Tier 1, 4 fetchers, ~22 docs/yr):** Governor's Statement + Board Minutes + SMP + FSR. Covers the decision (T+0), the deliberation (T+14), the quarterly forecast revision, and the semi-annual stability review. Highest signal of the entire RBA publication catalogue.
- 🟡 **Build candidates (Tier 2):** Treasury (reachable, no Playwright) + APRA (reachable, no Playwright) + Speeches (Akamai, needs filter design) + ABS commentary (low signal). The Treasury + APRA reachability finding (2026-06-10 probe) is new — they were previously assumed firewall-blocked but aren't.
- 🔴 **Manual / skip (Tier 3):** AOFM (host-specific corp-firewall block, manual Edge), RBA Bulletin/Annual Report/Chart Pack/Conference papers (low desk signal).

Concretely **what we read first** when something happens on AU rates:
1. Governor's Statement (T+0 — already in `data/snapshots/`)
2. Board Minutes (T+14 — already in `data/snapshots/`)
3. SMP for the latest quarterly forecast revision (already in `data/snapshots/`)
4. FSR if the question is housing/banking/macro-financial stability (already in `data/snapshots/`)

That stack is the 80/20 for an RBA view.

## Implementation notes

- The IMDR research-document pipeline (`research.*` schema, picasso/lois agents) is the natural home — these are PDF documents to be parsed + embedded, not time-series to be inserted in `econ.fact_indicator`.
- Discovery layer lives at [`playground/econ/au/govt/`](../../../../playground/econ/au/govt/), mirroring the Korea pattern at `playground/econ/kr/govt/`. Each agency gets its own `fetch_*.py` returning a `FetchResult` with `FilingItem` rows. `daily_pull.py` is the orchestrator; `_models.py` carries the dataclasses + rolling-dedup via `data/seen.json`; `_http.py` is plain-httpx (no TLS pinning needed — unlike Korea).
- Per-vendor doc scrapers live at `docs/admin/research/scrapers/{vendor}.md` for sell-side research; CB scrapers would follow the same shape (`docs/admin/research/scrapers/{rba,aofm,treasury,apra}.md`).
- The Playwright `profile_d2/` pattern used by `playground/econ/rba/fetch_d2_e_tables.py` is the proven Akamai bypass — re-used in `fetch_rba_governors_statement.py` via fresh `profile_rba_gov/` per run.
- AOFM documents have the same `*.gov.au` firewall block as AOFM XLSX files; same workaround (manual Edge or IT whitelist).

## Build order

### Tier 1 — LIVE (full RBA Tier-1 stack, ~22 docs/yr)

| # | Source | Fetcher | Status |
|---|---|---|---|
| 1 | RBA Governor's Statement (cash-rate decisions) | `fetch_rba_governors_statement.py` | ✅ LIVE 2026-06-10 — 3 decisions for 2026 (~8/yr cadence) |
| 2 | RBA Board Minutes | `fetch_rba_board_minutes.py` | ✅ LIVE 2026-06-10 — 3 minutes for 2026 (~8/yr cadence) |
| 3 | RBA SMP (Statement on Monetary Policy) | `fetch_rba_smp.py` | ✅ LIVE 2026-06-10 — 6 SMPs since 2025 (4/yr cadence) |
| 4 | RBA FSR (Financial Stability Review) | `fetch_rba_fsr.py` | ✅ LIVE 2026-06-10 — 2 FSRs since 2024 (2/yr cadence) |

### Tier 2 — Build when needed (reachability re-confirmed 2026-06-10)

| # | Source | Fetcher (planned) | Status |
|---|---|---|---|
| 5 | Treasury Budget Papers / MYEFO / PEFO / Final Budget Outcome / IGR | `fetch_treasury_publications.py` | **Reachability ✅** — `treasury.gov.au/publication` + `budget.gov.au/{YYYY-YY}/` both 200 OK over plain httpx. Build with plain httpx (no Playwright). Cadence is twice-a-year (May Budget + Dec MYEFO) — high signal per event, low daily volume. |
| 6 | APRA Quarterly ADI / Property Exposures / GI Performance | `fetch_apra_quarterly.py` | **Reachability ✅** — PDF + XLSX download confirmed at `apra.gov.au/sites/default/files/*`. Build with plain httpx (no Playwright). Largely overlaps RBA E1+E2 which we already load — supplementary detail. |
| 7 | RBA Speeches | `fetch_rba_speeches.py` | Akamai-gated (Playwright). High-volume noise (~80-120/yr) — build only after a topic-filter design (e.g. Governor + Deputy only, or speeches with "monetary policy" / "inflation" / "labour market" in title). Otherwise drowns the daily snapshot. |
| 8 | ABS commentary releases (CPI / Labour Force / National Accounts) | `fetch_abs_commentary.py` | Plain HTTPS — easy to build. Low signal (ABS narrative around prints we already track quantitatively). Add when the research-doc pipeline ingests filings. |

### Tier 3 — Manual / skip

| # | Source | Why skipped |
|---|---|---|
| 9 | AOFM Annual Report / Issuance Calendar / Investor presentations | Corp TLS-inspection on `*.gov.au/sites/default/files/*` is **host-specific to `aofm.gov.au`** — NOT blocked for APRA's same path pattern (probed 2026-06-10). Workaround = manual Edge per [`_playground/aofm.md`](_playground/aofm.md). ~5 docs/yr; manual capture acceptable. |
| 10 | RBA Bulletin / Annual Report / Chart Pack / Conference papers | Low-signal for a rates desk: Bulletin is academic, Annual Report is institutional, Chart Pack is charts-over-data-we-have, Conference is research-grade. Not worth automating. |

## Related

- [`australia_indicator_inventory.md`](australia_indicator_inventory.md) — the data-side counterpart
- [`index.md`](index.md) — country overview
- [`_playground/aofm.md`](_playground/aofm.md) — AOFM-specific gating context
- [`_playground/rba.md`](_playground/rba.md) — RBA Akamai gating context
