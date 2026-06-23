# United States — Government & Quasi-Government Document Sources

Last updated: 2026-06-23
Status: **PROD-LIVE 2026-06-23.** Tier-1 Federal Reserve + Treasury
+ NY Fed streams promoted to `scripts/econ/us/govt/`. **145 reports / 2,320 chunks
LIVE** in `research.dim_report` + Qdrant + SharePoint (backfill 2026-06-23,
2-year window 2024-07 → 2026-06). Vendors: `fed` (official_cb) · `treasury_us`
(official_ministry) · `nyfed` (official_cb). Migration 107 applied.
`scripts/imdr_daily.py:PIPELINES` registration: **WIRED 2026-06-23** via the `us_daily` dual-track entry.

Probe coverage proven 2026-06-22 — **11 streams / 354 documents** (titles+URLs+dates,
manifest-only). `daily_pull.py` writes `data/snapshots/{YYYY-MM-DD}.json`.
Ingested 2-year window counts shown in the stream table below.

| Stream | Probe | Discovery docs | Ingested (2yr) | Signal |
|---|---|---:|---:|---|
| FOMC statements | `probe_fomc_statements` | 45 | 16 | rate decision |
| FOMC press-conf transcripts | `probe_fomc_presconf` | 89 | 15 | Powell Q&A — highest intraday signal |
| FOMC minutes | `probe_fomc_minutes` | 43 | 15 | reaction-function detail |
| SEP (dot-plot) | `probe_fomc_sep` | 22 | 8 | rate-path projections |
| Monetary Policy Report | `probe_mpr` | 38 | 3 | semi-annual framework + testimony |
| Beige Book | `probe_beige_book` | 16 | 16 | 8×/yr anecdotal growth/prices |
| SLOOS | `probe_sloos` | 16 | 8 | credit-cycle turn |
| Financial Stability Report | `probe_financial_stability` | 14 | 4 | tail-risk map |
| Fed speeches & testimony | `probe_fed_speeches` | 40 | 40 | of ~1,320 JSON feed |
| Treasury Quarterly Refunding (QRA + TBAC) | `probe_treasury_refunding` | 23 | 12 | **bond supply — long-end driver** |
| NY Fed Survey of Market Expectations (SPD/SMP/SME) | `probe_nyfed_surveys` | 8 | 8 | Street's pre-FOMC expectations |
| **Total** | — | **354** | **145** | — |

Discovery docs = manifest-only count from 2026-06-22 probe.
Ingested = 2-year window (`--recent-years 2`, backfill 2026-06-23).

Clickable index of all 354: `playground/econ/us/govt/fomc_documents.html` (Artifact).

**Probe findings (confirmed during Phase J ingest):**
- Press-conf transcript PDFs live at `.../mediacenter/files/FOMCpresconf{YYYYMMDD}.pdf` (capitalised stem), not `/monetarypolicy/files/`.
- Speeches HTML is JS-rendered → use the JSON feed `/json/ne-speeches.json`.
- **NY Fed renamed** the Survey of Primary Dealers (SPD) + Survey of Market Participants (SMP) into the consolidated **Survey of Market Expectations (SME)**; live hub `newyorkfed.org/markets/market-intelligence/survey-of-market-expectations` (plain GET, ~210 KB, 416 PDFs). Series tag in `extras`. **A distinct `nyfed` vendor was seeded in migration 107** (operationally separate from `fed`).
- Treasury Refunding: TBAC report detail pages carry no inline PDF (`pdf_url=None`); the TBAC presentation/charge PDFs are on the "most-recent documents" hub (`/system/files/221/TreasuryPresentationToTBAC*.pdf`). Real announcement date from the detail page's `field-news-publication-date`, not the template header `<time>`.
- Beige Book HTML↔PDF pairing is by byte-adjacency (slug `{YYYYMM}` ≠ PDF release date `{YYYYMMDD}`).
- **1 permanent 404**: one discontinued inter-meeting FOMC statement PDF is missing (HTML page exists, PDF was removed). The item retries on each run; benign until the probe is patched.
- Two bot-gated streams (BLS RSS, CBO HTML → 403) still need transport work before inclusion.

**Macro data releases that are Track A, not Track B** (noted, not probed here): regional-Fed
manufacturing/activity surveys (Empire State, Philly Fed, Dallas, Richmond, Kansas City,
Chicago Fed NFCI/CFNAI), the H.4.1 balance sheet and H.8 bank credit, and SOFR/EFFR —
these are time-series for `econ.fact_indicator`, candidates for a future US Track A expansion.

---

## Production fetchers (promoted 2026-06-23)

```
scripts/econ/us/govt/
├── _http.py                   shared http session + patient_get
├── _models.py                 FilingItem dataclass + ProbeResult
├── daily_pull.py              manifest-only daily snapshot (no ingest)
├── ingest_filings.py          ingest orchestrator (resolves bytes + calls ingest_filing_sync)
├── probe_beige_book.py
├── probe_fed_speeches.py
├── probe_financial_stability.py
├── probe_fomc_minutes.py
├── probe_fomc_presconf.py
├── probe_fomc_sep.py
├── probe_fomc_statements.py
├── probe_mpr.py
├── probe_nyfed_surveys.py
├── probe_sloos.py
└── probe_treasury_refunding.py
```

`ingest_filings.py` re-discovers all 11 streams at ingest time (no pre-downloaded
disk corpus). Each `FilingItem` carries `source_url` + optional `pdf_url`; bytes
are resolved over plain httpx at ingest time. Full CLI reference and ops details:
[`united_states_govt_prod_pipeline.md`](united_states_govt_prod_pipeline.md).

This file is the master inventory of **US policy / macro-relevant text**
sources (Federal Reserve Board + FOMC, the 12 regional Reserve Banks,
U.S. Treasury + OFR, the statistical agencies BLS/BEA/Census, the fiscal
council CBO, OMB, and the bank regulators FDIC/OCC). Sell-side research
(JPM/MS/Goldman/etc.) is already covered in the broader research/Qdrant
corpus; this document is the **official-voice counterpart** that has not
been ingested yet.

The 6 entries already listed in [`index.md`](./index.md) under "Policy &
fiscal document sources" are merged in below and marked **(already-known)**.
Anything without that tag was newly surfaced by 2026-06-22 web research +
reachability probing.

The **Federal Reserve is the Tier-1 priority** and the only agency probed
end-to-end in this pass: FOMC statements, minutes (~3-week lag), Summary of
Economic Projections (SEP dot-plot, `fomcprojtabl{YYYYMMDD}.pdf`), press-
conference transcripts, the semi-annual Monetary Policy Report, and
speeches/testimony. Everything else is table-only + Tier-classified for a
later build pass.

Crawl-complexity flag legend (per [onboarding §H.3](../onboarding_new_country.md)):
- **LOW** — RSS / JSON feed, or stable static HTML listing (single GET).
- **MED** — search-hub, paginated HTML listing, or JSON listing with params.
- **HIGH** — JS-rendered SPA, login-aware, or session-coupled archive.
- **BOT-GATED** — plain GET returns 403 (bot filter); a parallel feed or
  Playwright transport is required. Confirmed live on BLS + CBO HTML pages
  (2026-06-22) — both have a working RSS/feed side-door.

URLs marked **❓** are unverified to current listing shape in this pass.

---

## 1. Central bank — Federal Reserve Board + FOMC (Tier-1 priority)

All Federal Reserve Board content lives under `www.federalreserve.gov` and is
**plain-GET friendly** (probed 2026-06-22: HTTP 200, no Akamai, no TLS reset
from RV's network for HTML, RSS, JSON, and PDF endpoints). No Playwright
needed for any stream here — the one JS-rendered listing (speeches) has a
public JSON backing feed.

| # | Stream | URL | Cadence | Lang | Listing | Auth | Crawl | Why it matters |
|---|---|---|---|---|---|---|---|---|
| 1.1 | **FOMC statements** **(already-known)** | federalreserve.gov/monetarypolicy/fomccalendars.htm → `/newsevents/pressreleases/monetary{YYYYMMDD}a.htm` | per meeting (~8/yr) | EN | calendar hub (1 GET), slug-keyed | none | LOW | The policy decision text — moves UST curve + USD on release. Impl-note PDF `monetary{YYYYMMDD}a1.pdf`. **Probed ✅** |
| 1.2 | **FOMC minutes** **(already-known)** | same hub → `/monetarypolicy/fomcminutes{YYYYMMDD}.htm` (+ `.pdf` under `/files/`) | per meeting, ~3-wk lag | EN | calendar hub (1 GET), slug-keyed | none | LOW | Vote/dissent detail + staff outlook discussion. **Probed ✅** |
| 1.3 | **Summary of Economic Projections (SEP)** **(already-known)** | same hub → `/monetarypolicy/files/fomcprojtabl{YYYYMMDD}.pdf` (+ `.htm`) | 4×/yr (Mar/Jun/Sep/Dec) | EN | calendar hub (1 GET), slug-keyed | none | LOW | Dot-plot + central-tendency macro forecasts — the rate-path anchor. **Probed ✅** |
| 1.4 | **FOMC press-conference transcripts** | same hub → `/mediacenter/files/FOMCpresconf{YYYYMMDD}.pdf` (+ `fomcpresconf{YYYYMMDD}.htm`) | per projection meeting (and all meetings since 2019) | EN | calendar hub (1 GET), slug-keyed | none | LOW | Chair Q&A — often more market-moving than the statement. `fomcpresconf` slug appears 131× on the calendar hub. |
| 1.5 | **FOMC implementation note** | same hub → `/newsevents/pressreleases/monetary{YYYYMMDD}a1.htm` | per meeting | EN | calendar hub | none | LOW | Administered-rate settings (IORB, ON RRP, discount). Captured as `pdf_url` on the statement item. |
| 1.6 | **Monetary Policy Report (MPR)** **(already-known)** | federalreserve.gov/monetarypolicy/publications/mpr_default.htm | semi-annual (Feb/Jul) | EN | static HTML listing | none | LOW | Congressional-testimony companion; full macro narrative + special topics. (200 OK / 98 KB.) |
| 1.7 | **Speeches & testimony** **(already-known)** | listing federalreserve.gov/newsevents/speeches-testimony.htm (JS) → JSON feed `/json/ne-speeches.json` (+ `/json/ne-testimony.json`) | regular (~15-20/mo) | EN | **HTML listing is JS-rendered**; JSON feed is the firehose (~1,320 items) | none | LOW (via JSON feed) | Forward guidance from Chair/Governors. HTML page hydrates client-side — used the JSON backing feed instead of Playwright. **Probed ✅** |
| 1.8 | **Press releases — all (firehose)** | RSS `/feeds/press_all.xml`; monetary-only `/feeds/press_monetary.xml` | daily-ish | EN | RSS | none | LOW | Catch-all: balance-sheet ops, swap lines, regulatory + enforcement. RSS 200 OK / 15 KB. |
| 1.9 | **Beige Book** (Summary of Commentary on Current Economic Conditions) | federalreserve.gov/monetarypolicy/beige-book-default.htm | 8×/yr (~2 wks pre-FOMC) | EN | static HTML listing → per-edition HTML/PDF | none | LOW | The 12-district anecdotal-conditions read — direct FOMC input; US "regional report" analogue. |
| 1.10 | **Financial Stability Report** | federalreserve.gov/publications/financial-stability-report.htm | semi-annual (May/Nov) | EN | static HTML | none | LOW | Asset-valuation / leverage / funding-risk read. |
| 1.11 | **FEDS Notes / Finance & Economics Discussion Series (working papers)** | federalreserve.gov/econres/feds/index.htm · `/econres/notes/feds-notes/` | rolling | EN | static HTML listing | none | MED | Methodology preview of staff thinking; lower urgency. |
| 1.12 | **H.4.1 / H.8 / H.6 release commentary** | federalreserve.gov/releases/ | weekly/monthly | EN | static HTML | none | LOW | Statistical-release landing pages — the narrative wrapper, not the data (data is Track A / FRED). |

**Fed note**: the FOMC calendar hub (`fomccalendars.htm`, ~164 KB) is a
single server-rendered page carrying every meeting's statement / minutes /
SEP / press-conf / impl-note link going back years. One GET feeds streams
1.1–1.5; the date is parsed straight from the `{YYYYMMDD}` URL slug, so no
per-row date-cell scraping is needed.

---

## 2. Regional Reserve Banks (12 districts)

Each district bank publishes its own research, regional surveys, and
president speeches. NY Fed is Tier-1 (it runs the Desk / open-market ops);
the rest are Tier-2/3 colour. Several regional manufacturing surveys are the
canonical Track-A series (Empire State, Philly Fed) — those time series are
Track A; the **press commentary** around them is Track B.

| # | Stream | URL | Cadence | Lang | Listing | Auth | Crawl | Why it matters |
|---|---|---|---|---|---|---|---|---|
| 2.1 | **NY Fed — press / news** | newyorkfed.org/press | daily-ish | EN | HTML listing (heavy page ~4 MB) | none | MED | Desk operations, SOMA, reverse-repo, FX-swap ops — the operational arm of the FOMC. 200 OK. |
| 2.2 | **NY Fed — RSS hub** | newyorkfed.org/rss | release-driven | EN | RSS index (multiple feeds) | none | LOW | Per-topic feeds (markets, research, press). 200 OK / 95 KB — preferred over the heavy HTML page. |
| 2.3 | **NY Fed — Liberty Street Economics (blog)** | libertystreeteconomics.newyorkfed.org | ~weekly | EN | HTML / RSS | none | LOW | High-signal staff commentary (r*, reserves, repo). |
| 2.4 | **NY Fed — research / staff reports** | newyorkfed.org/research | rolling | EN | HTML listing | none | MED | SCE (Survey of Consumer Expectations) narrative, primary-dealer survey. |
| 2.5 | **Reserve Bank president speeches (11 other districts)** | per-district sites (e.g. richmondfed.org, dallasfed.org, kansascityfed.org, …) | regular | EN | per-district HTML / RSS | none | MED | FOMC-voter forward guidance; aggregate via per-district feeds. ❓ per-site shape varies. |
| 2.6 | **Regional survey commentary** (Empire State, Philly Fed, Dallas, KC, Richmond, Chicago) | per-district release pages | monthly | EN | HTML / PDF | none | MED | The narrative wrapping the survey print (the diffusion-index series itself is Track A). |
| 2.7 | **Jackson Hole symposium papers/program** (KC Fed) | kansascityfed.org/research/jackson-hole-economic-symposium/ | annual (Aug) | EN | HTML | none | LOW | Set-piece policy-direction event. |

---

## 3. U.S. Treasury + OFR

| # | Stream | URL | Cadence | Lang | Listing | Auth | Crawl | Why it matters |
|---|---|---|---|---|---|---|---|---|
| 3.1 | **Treasury press releases** | home.treasury.gov/news/press-releases | daily-ish | EN | HTML listing (paginated) | none | MED | Sanctions (OFAC), Secretary statements, debt-limit, tariff/trade. 200 OK / 114 KB. |
| 3.2 | **Quarterly Refunding Statement + TBAC** | home.treasury.gov/policy-issues/financing-the-government/quarterly-refunding | quarterly | EN | HTML → PDF | none | MED | Coupon-issuance sizing — the single biggest UST supply signal. Tier-1 within Treasury. |
| 3.3 | **Treasury International Capital (TIC) commentary** | home.treasury.gov/data/treasury-international-capital-tic-system | monthly | EN | HTML → PDF | none | LOW | Foreign-holdings narrative (data leg is Track A). |
| 3.4 | **OFR (Office of Financial Research) — research & analysis** | financialresearch.gov (research/analysis + Financial Stability Report) | rolling + annual | EN | HTML listing | none | MED | Systemic-risk monitoring; repo/MMF stress notes. (Root 200; `/research-and-analysis/` path 404 in probe — needs re-discovery of the current listing URL ❓.) |
| 3.5 | **Treasury auction results / issuance** | treasurydirect.gov | per auction | EN | data portal | none | MED | Auction tails/bid-cover — borderline Track A (data portal, see §H Shape F). |

---

## 4. Statistical agencies (release commentary)

The headline series (CPI, NFP, GDP, retail) are Track A (BLS/BEA/Census APIs
+ FRED). Track B here is the **narrative news release** that accompanies each
print — distinct from the time series.

| # | Stream | URL | Cadence | Lang | Listing | Auth | Crawl | Why it matters |
|---|---|---|---|---|---|---|---|---|
| 4.1 | **BLS — news releases** | bls.gov/bls/news-release/ ; RSS `/feed/bls_latest.rss` | per release | EN | RSS / HTML | none | **BOT-GATED** | CPI/PPI/Employment Situation/JOLTS/ECI release text. **RSS returned 403 to plain GET (2026-06-22)** — BLS bot-filters; needs a header/UA strategy or Playwright. Confirm against browser before declaring blocked (per §H.6). |
| 4.2 | **BEA — current releases** | bea.gov/news/current-releases | per release | EN | HTML listing | none | LOW | GDP/NIPA, PCE, personal income, international transactions narratives. 200 OK / 61 KB. |
| 4.3 | **Census — economic indicators** | census.gov/economic-indicators/ | per release | EN | HTML listing | none | LOW | Retail (MARTS/MRTS), housing starts, durable goods, advance trade. 200 OK / 76 KB. |

---

## 5. Fiscal council & legislative research — CBO

| # | Stream | URL | Cadence | Lang | Listing | Auth | Crawl | Why it matters |
|---|---|---|---|---|---|---|---|---|
| 5.1 | **CBO — all publications** | cbo.gov/publications/all ; RSS `cbo.gov/publications/all/rss.xml` | rolling | EN | RSS / HTML | none | **BOT-GATED (HTML)** | Independent budget & economic projections, scoring, long-term outlook — the counterweight to OMB. **HTML page 403 to plain GET; the RSS feed is 200 OK / 15 KB** — use the RSS side-door (per §H.6). |
| 5.2 | **CBO — Budget & Economic Outlook** | cbo.gov/about/products/major-recurring-reports | 2×/yr (+ updates) | EN | HTML → PDF | none | MED | Baseline deficit/debt path — sovereign-supply + rating input. |
| 5.3 | **CBO — Long-Term Budget Outlook** | (within 5.2) | annual | EN | PDF | none | LOW | Demographic/fiscal-sustainability projections. |

---

## 6. Budget office — OMB

| # | Stream | URL | Cadence | Lang | Listing | Auth | Crawl | Why it matters |
|---|---|---|---|---|---|---|---|---|
| 6.1 | **OMB — landing / President's Budget** | whitehouse.gov/omb/ | annual (Feb) + ad hoc | EN | HTML listing | none | MED | The Administration's budget request + MID-SESSION REVIEW — fiscal-stance signal. 200 OK / 224 KB. (whitehouse.gov is reorganised each administration — pin the current OMB path ❓.) |
| 6.2 | **OMB — Statements of Administration Policy (SAP)** | whitehouse.gov/omb/legislative/statements-of-administration-policy/ ❓ | event-driven | EN | HTML | none | MED | Veto-threat / bill-position signal on fiscal legislation. |

---

## 7. Financial-system regulators — FDIC / OCC

| # | Stream | URL | Cadence | Lang | Listing | Auth | Crawl | Why it matters |
|---|---|---|---|---|---|---|---|---|
| 7.1 | **FDIC — press releases** | fdic.gov/news/press-releases | daily-ish | EN | HTML listing | none | MED | Bank failures/resolutions, deposit-insurance, QBP commentary. 200 OK / 91 KB. |
| 7.2 | **FDIC — Quarterly Banking Profile (QBP)** | fdic.gov/analysis/quarterly-banking-profile/ | quarterly | EN | HTML → PDF | none | MED | Aggregate bank-sector health (NIM, NPLs, deposits) — credit-cycle read. |
| 7.3 | **OCC — news releases** | occ.gov/news-issuances/news-releases/ | regular | EN | HTML listing | none | MED | National-bank supervision, CRA, enforcement. (Probed `/index.html` 404 — current listing path differs; re-discover ❓.) |
| 7.4 | **OCC — bulletins** | occ.gov/news-issuances/bulletins/ | regular | EN | HTML listing | none | MED | Supervisory guidance — bank-capital / risk-management rule changes. |

> The **Federal Reserve Board** is also the lead bank holding-company
> supervisor; its supervision/regulation press lands via 1.8 (`press_all`).
> Macroprudential bank-stress (CCAR/DFAST) results are a Fed stream, captured
> there.

---

## Recommended priority tiers

### Tier 1 — must-have for policy reasoning (10 streams)

Drives UST / USD / equity within 24h of release, OR carries the canonical
policy text behind a market-moving decision.

- 1.1 FOMC statements
- 1.2 FOMC minutes
- 1.3 Summary of Economic Projections (SEP)
- 1.4 FOMC press-conference transcripts
- 1.6 Monetary Policy Report
- 1.7 Fed speeches & testimony
- 1.8 Fed press-release firehose (RSS)
- 1.9 Beige Book
- 2.1/2.2 NY Fed press + RSS (Desk / open-market ops)
- 3.2 Treasury Quarterly Refunding + TBAC

### Tier 2 — useful colour (≈11 streams)

Depth / divergence / sector signal; not market-moving on release.

- 1.5 FOMC implementation note (captured as pdf_url on the statement)
- 1.10 Fed Financial Stability Report
- 2.3 NY Fed Liberty Street Economics
- 2.6 Regional survey commentary (Empire/Philly/Dallas/KC/Richmond/Chicago)
- 2.7 Jackson Hole symposium
- 3.1 Treasury press releases
- 3.3 Treasury TIC commentary
- 3.4 OFR research + Financial Stability Report
- 4.2 BEA current releases · 4.3 Census economic indicators
- 5.1/5.2 CBO publications + Budget & Economic Outlook
- 7.1/7.2 FDIC press + Quarterly Banking Profile

### Tier 3 — reference / sectoral / academic (≈9 streams)

Defer until Tier 1–2 operational.

- 1.11 FEDS Notes / FEDS working papers
- 1.12 Fed statistical-release landing pages
- 2.4 NY Fed research / staff reports
- 2.5 Other-district president speeches (11 sites)
- 4.1 BLS news releases (bot-gated; revisit transport)
- 5.3 CBO Long-Term Budget Outlook
- 6.1/6.2 OMB budget + SAPs
- 7.3/7.4 OCC news + bulletins
- 3.5 Treasury auction results (borderline Track A data portal)

---

## Crawl-pattern clustering

Mapping each source to one of the 5 crawler shapes from
[onboarding §H.3](../onboarding_new_country.md). The US set is dominated by
two shapes — a single calendar/listing GET (Fed) and RSS/JSON feeds.

### Shape A — RSS / JSON feed (single GET, parse, normalise)
Lowest complexity. The Fed speeches JSON firehose, the Fed press RSS feeds,
the NY Fed RSS hub, and the CBO RSS side-door all fit here.

**Members**: 1.7 (`/json/ne-speeches.json`), 1.8 (`/feeds/press_all.xml`,
`press_monetary.xml`), 2.2 (NY Fed RSS), 2.3 (Liberty Street RSS), 5.1 (CBO
`rss.xml`), 4.1 (BLS RSS — **bot-gated**, transport TBD).

### Shape B — Calendar/index HTML hub, slug-keyed (single GET, regex over hrefs)
The defining US shape: one ~164 KB calendar/index page lists every
sub-document, and the date is parsed from the `{YYYYMMDD}` URL slug. No
pagination, no date-cell scraping, no JS. This is a variant of the §H "Shape
D — HTML-listing on a govt portal" but exceptionally clean.

**Members**: 1.1, 1.2, 1.3, 1.4, 1.5 (all off `fomccalendars.htm`), 1.6 MPR,
1.9 Beige Book, 1.10 FSR, 1.11 FEDS, 1.12 release pages.

### Shape D — Paginated HTML listing on a govt portal (walk pages)
Server-rendered table/card listings that paginate. URL patterns differ per
agency; no JS rendering. The non-Fed agencies mostly land here.

**Members**: 2.1 NY Fed press, 2.4 NY Fed research, 2.6 regional surveys,
3.1 Treasury press, 3.2 Refunding, 3.3 TIC, 3.4 OFR, 4.2 BEA, 4.3 Census,
5.2 CBO outlook, 6.1/6.2 OMB, 7.1/7.2 FDIC, 7.3/7.4 OCC.

### JS-rendered listing (avoided via backing feed)
Only the Fed **speeches HTML page** (1.7) is JS-hydrated — and it has a
public JSON backing feed, so it resolves under Shape A without Playwright.
Per [[feedback-js-rendered-dont-bail]], the JSON side-door is preferred over
launching a browser. **No US Tier-1 stream requires Playwright** (contrast
RBA's Akamai gate in AU).

### Shape F — data portal / out-of-scope-for-doc-corpus
Time-series / auction data portals, not document-corpus crawl shape.

**Members**: 3.5 TreasuryDirect auctions (data portal).

**Implication**: ~all in-scope US streams collapse into **Shape A (feeds) +
Shape B (Fed calendar hub) + Shape D (paginated portals)**. The Fed Tier-1
build needs exactly **two transports**: one slug-keyed calendar parser
(shared across statements/minutes/SEP/press-conf) and one JSON-feed parser
(speeches). That's why the four probes are this thin.

---

## Per-stream resolution recipes (probed 2026-06-22)

Body + PDF resolution paths for the Tier-1 streams that were probed. All
resolve over plain httpx (HEAD/GET 200, correct content-type confirmed).

| Stream | source_url (HTML/detail) | pdf_url | Notes |
|---|---|---|---|
| FOMC statement | `…/pressreleases/monetary{YYYYMMDD}a.htm` (200, text/html) | `…/files/monetary{YYYYMMDD}a1.pdf` (200, application/pdf, ~224 KB) | `a` = statement, `a1` = implementation note, `b` = balance-sheet plan. Probe keeps the `a` statement; attaches `a1` PDF. |
| FOMC minutes | `…/fomcminutes{YYYYMMDD}.htm` | `…/files/fomcminutes{YYYYMMDD}.pdf` (200, ~416 KB) | `publish_date` recorded = meeting date; actual release ~3 wks later. |
| SEP | `…/fomcprojtabl{YYYYMMDD}.htm` | `…/files/fomcprojtabl{YYYYMMDD}.pdf` (200, ~1.2 MB) | Only the 4 projection meetings carry an SEP (~half the statement count). |
| Fed speeches | `…/newsevents/speech/{speaker}{YYYYMMDD}a.htm` (200, text/html) | none (speeches are HTML) | Speaker + location carried in `extras` from the JSON feed fields `s` / `lo`. |

---

## Probe evidence (2026-06-22)

Discovery scripts in `playground/econ/us/govt/` fetched each Tier-1 Federal
Reserve stream and saved raw listing artifacts under `raw/{stream}/`. All
probes use plain httpx via `_http.py:make_session()` — no Playwright, no
anti-detection flags.

| Probe | Stream | Items | Latest | Shape |
|---|---|:---:|---|---|
| `probe_fomc_statements.py` | fomc_statements | 45 | 2026-06-17 | B (calendar hub) |
| `probe_fomc_minutes.py` | fomc_minutes | 43 | 2026-04-29 (meeting date) | B (calendar hub) |
| `probe_fomc_sep.py` | fomc_sep | 22 | 2026-06-17 | B (calendar hub) |
| `probe_fed_speeches.py` | fed_speeches | 40 (of ~1,320 in feed) | 2026-06-06 | A (JSON feed) |

`daily_pull.py` runs all four, dedups via rolling `data/seen.json`, and
writes a **manifest-only** snapshot (title/url/date/doc_type/pdf_url — NO
document bodies) to `data/snapshots/{YYYY-MM-DD}.json`. First run: 150 new
items across 4 streams. Second run: 0 new (idempotency confirmed).

---

## Open questions

1. **BLS bot-gate** — `bls.gov/feed/bls_latest.rss` returns 403 to plain GET
   (2026-06-22). Confirm it loads in the user's browser, then decide:
   UA/header tweak, the BLS data-API release-schedule endpoint, or Playwright.
   (Per §H.6 — don't declare blocked without the browser check.)
2. **CBO HTML 403 / RSS 200** — the CBO publications HTML page is bot-gated
   but its RSS feed is open. Use RSS as the primary crawl spine for CBO.
3. **OFR + OCC listing paths** — `financialresearch.gov/research-and-analysis/`
   and `occ.gov/news-issuances/news-releases/index.html` both 404'd in the
   probe; the sites are up (roots 200) but the listing URLs have moved.
   Re-discover current paths before scoping a fetcher.
4. **OMB path stability** — whitehouse.gov is reorganised each administration;
   pin the live OMB / President's-Budget / SAP paths at build time.
5. **Regional Reserve Banks** — 12 separate sites with bespoke shapes. Is the
   value (11 non-NY president speeches + 6 regional surveys) worth per-site
   fetchers, or is NY Fed + a speech-aggregator enough for v1?
6. **Statistical-release narrative vs Track A data** — confirm the doc corpus
   wants the BLS/BEA/Census *news-release text* given the series themselves
   already land in `econ.fact_indicator` via FRED + the source APIs.
7. **vendor_category mapping** — Fed/NY Fed = `official_cb`; Treasury/OMB =
   `official_ministry`; FDIC/OCC = `official_regulator`; BLS/BEA/Census =
   `official_statistics`; CBO/OFR = `official_thinktank` (or a new
   `official_fiscal_council`?). Settle before the Phase-J vendor-seed migration.

---

## Cross-refs

- [`index.md`](./index.md) — US econ overview (Track A + Track B status).
- [`united_states_govt_prod_pipeline.md`](united_states_govt_prod_pipeline.md) — Track B ops reference (architecture, CLI, SharePoint layout, failure modes).
- [`../../development/us_govt_filings.md`](../../development/us_govt_filings.md) — Track B execution tracker (done / pending / migration log).
- [`../onboarding_new_country.md`](../onboarding_new_country.md) § Phase H — Track B playbook.
- [`../korea/govt_doc_sources.md`](../korea/govt_doc_sources.md) — the worked reference inventory.
- [`../australia/au_cb_documents.md`](../australia/au_cb_documents.md) — the lighter discovery example.
- `playground/econ/us/govt/` — the Tier-1 Fed probes + `daily_pull.py` (playground originals preserved as legacy sandbox).
