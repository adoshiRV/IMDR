# BofA Securities — Research scraper

**Status: LIVE 2026-07-17 (firehose).** Code fully built + Phase-8
tightened. **Wired into the orchestrator** (`ingest_today.py`) via
`crawler_bofa_firehose`, `auth_realm="rv-pingfed"` (serialised with
Barclays to avoid concurrent PingFederate logins). Firehose ≈14/day.
**MFA solved** — the email security-token challenge is auto-cleared by
`login_bofa.py`: it reads the 8-digit token from Outlook `Research\BOFA`
(`bofamarkets@bofa.com`, "BofA Mercury Portal Token") and submits it, and
also handles a **trusted-session direct landing** (no token). Credit hubs
are **keep-by-default** (single-name issuer + sector credit are wanted —
see [`../../development/credit_bofa.md`](../../development/credit_bofa.md)).
**Verified live 2026-07-17**: the scheduled `--embed` cycle logged
in unattended ("login OK"), inserted 64 / 0 failed (66 discovered,
`filter_removed=0`), across MACRO/RATES/FX/CREDIT/STRATEGY/COMMODITIES;
`smoke_bofa_retrieval.py` 3/3 PASS (BofA chunks searchable in Qdrant).
PDFs land under `{publish_date}/bofa/`. See "Login" section below.

Pattern: **HTML scraping** (Liferay server-rendered portal), NOT a JSON
listing API. Closest analogue in our stack: HSBC. Document delivery via
**signed `rsch.baml.com` URLs** embedded in the listing HTML (no
frontmatter round-trip needed).

> **Two channels.** BofA research also arrives via the Outlook **email**
> channel (`research@rvcapital.com` → `BOFA` folder, ~72/month, all
> desk/sales commentary, body-only). That path is independent of this
> portal scraper and runs through the lenient email pipeline
> (`source='email'`, `vendor_code='bofa'`) — see
> [`../outlook_email_channel.md`](../outlook_email_channel.md).
>
> **⚠ Channel note (updated 2026-07-17).** The **portal** is now LIVE in
> the orchestrator and delivers BofA credit (firehose). The separate
> **email** channel (`ingest_outlook.py`) remains **stalled since
> 2026-06-29** — and even when running it carried desk/sales commentary
> only (FX / macro / rates — Patrick Law USDCNH, Arvin The G10 Spot Views,
> FX Vol, Hartnett Flow Show), **zero CREDIT**. So the portal is the BofA
> credit source; email-channel revival is tracked separately (Fold 2b in
> [`../../development/credit_bofa.md`](../../development/credit_bofa.md)),
> see [`../outlook_email_channel.md`](../outlook_email_channel.md).

## Orchestrator wiring — LIVE (2026-07-17)

BofA is wired into the orchestrator (firehose). Prerequisites + the
four-file registration, all now satisfied:

**Prerequisites — done:**

1. ✅ **MFA handler** — `login_bofa.py` reads the emailed security token
   from Outlook `Research\BOFA` (`_read_portal_token` via win32com) and
   submits it; `_resolve_post_submit` also handles a trusted-session
   direct landing. E2E live test passed (`is_authenticated=True`,
   `Home - BofA Markets`).
2. ✅ **Firehose integration decision** — **firehose only**
   (`crawler_bofa_firehose.py`); hub crawler retired from the prod path.
3. ✅ **Phase 6c embed smoke** — scheduled `--embed` cycle (2026-07-17)
   ran unattended: inserted 64 / 0 failed (66 discovered, `filter_removed=0`);
   `smoke_bofa_retrieval.py` **3/3 PASS** (BofA chunks searchable in Qdrant).

**Four-file registration — state:**

1. ✅ **`ingest_today.py`** — `from ingest.crawler_bofa_firehose import
   discover_reports as bofa_discover` + `"bofa": VendorSpec(code="bofa",
   discover=bofa_discover, auth_realm="rv-pingfed")` in
   `_load_vendor_registry()`.
2. ✅ **`classifiers/__init__.py`** — `"bofa"` in `_VENDOR_CODES` +
   dispatcher branch (active since 2026-06-22).
3. ✅ **`pipeline.py`** — `_is_bofa_url` → `fetch_bofa_pdf` dispatch
   (active; `research1.ml.com` / `rsch.baml.com` SAML fetch).
4. ✅ Smoke `EMBED=false LIMIT=2 python ingest_today.py --vendors bofa` —
   inserted 2, failed 0.

**Operational note:** the orchestrator logs into BofA once per cycle
(every 3h), each triggering one "Mercury Portal Token" email (auto-read).
That's ~8 logins/day; if BofA fraud-flags the cadence, reduce BofA's run
frequency (the `feedback_bofa_mfa_slow_relogin` caution is about *rapid*
re-login, not spaced cycles). The 2 legacy manual-smoke reports
(`dim_report` ids 3134, 3135) remain.

## Portal

| | |
|---|---|
| Hostname | `markets.ml.com` (legacy Merrill Lynch domain) |
| Product name | **BofA Securities Mercury®** |
| Sign-in URL | `https://markets.ml.com/home` |
| Username | `.env: IMDR_RESEARCH_BOFA_USERNAME` (`arjdoshi01`) |
| Password | `.env: IMDR_RESEARCH_BOFA_PASSWORD` |
| MFA | **Triggered 2026-06-15** — see "Login" section. `login_bofa.py` does not yet handle MFA (Phase 1 assumed none). Barclays-style Outlook MFA-poll needed before prod. |
| Document delivery host | `rsch.baml.com` (signed URLs with `q + e + h` params) |
| Static asset host | `static1.markets.ml.com` (e.g. `BofAML_Global_Macro_Forecasts.xlsx`) |

## Profile

```
playground/research/profiles/bofa/
```

Fresh profile — no inherited Z:\…\playwrights\ Chrome profile observed.
First interactive login required.

## Expected content focus

BofA Securities operates one of the broader sell-side research desks
globally. Coverage spans:

- US + Europe + Asia macro / economics
- Rates (US Treasuries, EUR rates, EM rates)
- FX (G10 + EM)
- Credit (US HY, US IG, European credit, EM credit — both sovereign and corporate)
- Commodities (energy, metals, agriculture)
- Equity strategy (cross-asset + sector + single-stock)
- ESG / thematic / quant

Pre-Phase-1 estimate: **~30-50 reports/day raw** (mid-to-large
volume vendor, similar to Morgan Stanley/Goldman tier).

**Critical posture per user directive 2026-06-03**: drop single-name
equity AND single-name corporate credit. Sovereign credit, macro,
rates, FX, commodities all in scope. The signal-discovery focus in
Phase 2 / Phase 8 must identify:

1. Single-name equity discriminator (ticker count, asset_class flag,
   security identifier, etc.)
2. Single-name corporate-credit discriminator (issuer field,
   sector code, derivedSectorId equivalent — like STANC's 9022)

## URL patterns (confirmed from Phase 1 snapshots, 2026-06-03)

### Hub pages (asset-class landing — server-rendered HTML)

21 production hubs in `HUB_URLS` (verified against `crawler_bofa.py`
as of 2026-06-15). Advanced Search and Structured Products are excluded
from the production walk (both returned 0 tiles in the Phase 2 probe).
Interactive Forecasts (`/researchlibrary/forecastsummaryreport`) is
also excluded — it was in the Phase 1 snapshot list but not promoted
to the production hub set (returns 0 `Table_report` tiles).

| Asset class | Hub key | Hub URL |
|---|---|---|
| Economics — Global | `economics_overview` | `markets.ml.com/economics-overview` |
| Economics — Country | `economics_country` | `markets.ml.com/economics-country` |
| Investment Themes | `investment_themes` | `markets.ml.com/researchlibrary/investment-themes` |
| Rates — Regional | `rates_regional` | `markets.ml.com/global-overview` |
| Rates — Inflation-Linked | `rates_inflation` | `markets.ml.com/inflation` |
| FX — G10 Strategy | `fx_g10` | `markets.ml.com/researchlibrary/global-fx-strategy` |
| FX — Global FX | `fx_global` | `markets.ml.com/foreign-exchange` |
| Commodities | `commodities` | `markets.ml.com/researchlibrary/commodities` |
| Futures | `futures` | `markets.ml.com/futures/overview` |
| Credit — Global | `credit_global` | `markets.ml.com/researchlibrary/global` |
| Credit — Strategy Americas | `credit_strategy_americas` | `markets.ml.com/credit-strategy-americas` |
| Credit — High Grade | `credit_high_grade` | `markets.ml.com/high-grade` |
| Credit — High Yield/Distressed | `credit_high_yield` | `markets.ml.com/high-yield-distressed` |
| Credit — Securitized (MBS) | `credit_securitized` | `markets.ml.com/mbs` |
| Credit — EM FI Strategy & Econ | `credit_em_fi` | `markets.ml.com/emerging-markets-global` |
| Credit — GEMs Corporate Credit | `credit_em_corporate` | `markets.ml.com/em-corporate-credit` |
| Credit — Municipal | `credit_municipal` | `markets.ml.com/municipal` |
| Equities — Regional Overview | `equity_regional` | `markets.ml.com/researchlibrary/global1` |
| Equities — ETF Analytics | `equity_etf` | `markets.ml.com/researchlibrary/exchange-traded-funds` |
| Equities — EM Equity Strategy | `equity_em_equity` | `markets.ml.com/gem-equity-strategy-and-equity-fundamental` |
| Technical Analysis | `technical_analysis` | `markets.ml.com/researchlibrary/technical-analysis` |
| *(Advanced Search — not a production hub)* | — | `markets.ml.com/researchlibrary/advancedsearch` |

### Tile structure (embedded inside hub HTML)

Each report tile is a `<table>` block with these load-bearing attributes:

```html
<table id="Table_report <SERIES>_<TITLE>"
       summary="Table of report <SERIES> <TITLE>">
  <a aria-label="Html <ANALYST/SUBJECT> report opens in a new window"
     onclick="getUrlFromWebserviceForIdHTML('https://rsch.baml.com/r?q=<token>&e=<email>&h=<hash>')">
  ...
</table>
```

For example, on the home page (snapshot 0):
```
<series> = "U.S. Business and Information Services"
<title>  = "Feeding the AI infrastructure build-out; A hyperscale growth opp for ARMK/CGP/SW..."
<analyst-subject> = "Wells Fargo & Company"   (from aria-label)
signed URL: rsch.baml.com/r?q=OEJ!Di5UKtFVCa7qb!lKkg&e=adoshi%40rvcapital.com&h=R0oD8g
```

Numeric report IDs are also embedded in JavaScript onclick handlers
like `_multiDataReports_WAR_researchlibrary_portlet_INSTANCE_*_checkAnalystHover('12978792', ...)` —
useful for cross-referencing tiles with their detail pages.

### Pagination

Liferay portlet action URL:
```
markets.ml.com/<hub>?p_p_id=multiDataReports_WAR_researchlibrary_portlet_INSTANCE_<X>
                   &p_p_lifecycle=0
                   &action=more
                   &pageidx=<N>
                   &pagesize=25
                   &tabname=<tabname>
                   &island=<series>
                   &emCountry=<optional>
                   ...
```

### Document URL pattern

Single deterministic format:

```
HTML viewer:  https://rsch.baml.com/r?q=<token>&e=<urlenc-email>&h=<short-hash>
PDF:          https://rsch.baml.com/r?q=<token>&e=<urlenc-email>&h=<short-hash>&cmd=PDF
```

Where:
- `q` = base64-like 22-char report token (server-side encrypted report id)
- `e` = URL-encoded subscriber email (`adoshi%40rvcapital.com`)
- `h` = 6-char HMAC-like signature (per-(report,user) pair)

`&cmd=PDF` works for most report types and avoids a second round-trip.
However, **some report types do not serve PDF bytes via `&cmd=PDF`** —
they 302-redirect to an HTML viewer page (Liferay DXP) instead. For
those, the viewer itself exposes the PDF via a re-minted
`research1.ml.com/C?...` URL. See "Fetch strategy — Case 3" below.

### Static assets (Excel forecast workbooks)

`https://static1.markets.ml.com/RLApp-portlet/RLDocuments/*.xlsx` —
e.g. `BofAML_Global_Macro_Forecasts.xlsx`. Likely a candidate for
direct download in a later phase (not covered by the standard PDF
ingest path).

## Listing API

**No JSON listing endpoint. Per-hub HTML scrape, with lazy URL
resolution via a Liferay portlet resource endpoint.**

### Per-hub HTML scrape (Phase 2 probe — 2026-06-03; updated 2026-06-15)

Phase 2 probe walked 23 candidate hubs (`playground/research/probe_bofa_listing.py`).
Advanced Search + Structured Products returned 0 tiles; Interactive Forecasts
also returned 0 tiles. **21 hubs** were promoted to `HUB_URLS` in
`crawler_bofa.py`:

* Phase 2 probe: 256 distinct tiles parsed across the productive hubs.
* 154 distinct "series" — taxonomy mapped at
  `playground/research/bofa_explore/series_by_hub.md`.
* 70% of tiles carry a numeric `report_id` (from
  `_checkAnalystHover('<id>', ...)` JS handler in the anchor tag).
* **2026-06-15 full-hub smoke**: 141 unique reports with resolvable PDF
  URLs, date span 2025-12-08 → 2026-06-15 (65 drops: 36 mbs-datatable,
  20 equity-hub-blanket, 7 title-prefix:reminder, 2 single-name-corporate).
  By hub asset-class hint: CREDIT 74, STRATEGY 20, MACRO 18, COMMODITIES
  14, EQUITY 6, RATES 6, FX 3.

Per-tile metadata extracted via regex:

```
<table id="Table_report <SERIES>_<TITLE>"
       summary="Table of report <SERIES> <TITLE>">
  <a id="_multiDataReports_WAR_researchlibrary_portlet_INSTANCE_<X>_<REPORT_ID>"
     onclick="javascript:htmlIconClickOnCachedPortlet('<REPORT_ID>',
                       '_multiDataReports_WAR_researchlibrary_portlet_INSTANCE_<X>_')">
    <span class="bold-text">SERIES</span>
    <br>
    <span class="white-text">TITLE</span>
  </a>
  ...
  <span>PRIMARY_AUTHOR</span> (via navigateToResearchSearchProxy)
  ...
  DATE  (e.g. "29-May-2026 03:27:58 PM")
</table>
```

The "series" slot mixes flagship series names (Global Rates Weekly,
Inflation Strategist) AND single-name subjects (Kosmos Energy Ltd,
AA2000 = Aeropuertos Argentina 2000). This double-use is exactly the
discriminator we want — anything ticker-shaped in the series slot is
single-name material to drop.

### URL resolver (Phase 2.5 probe — 2026-06-03)

Hub tiles don't embed pre-resolved signed URLs (unlike the home page).
The JS function `htmlIconClickOnCachedPortlet(pid, namespace)` resolves
on click via a Liferay portlet resource endpoint:

```javascript
function htmlIconClickOnCachedPortlet(pid, namespace) {
    var inputid = namespace + "htmlResourceUrl";
    var url = document.getElementById(inputid).value;  // Liferay resource URL template
    url = url.replace("pidvalue", pid);                // substitute report ID
    jQuery.ajax({type: 'POST', url: url, success: ...}); // POST → response is signed URL
}
```

So the crawler's URL resolution path is:

1. Each hub HTML contains one or more `<input id="<NAMESPACE>htmlResourceUrl"
   value="<TEMPLATE>">` hidden inputs. The template is a Liferay resource URL:
   ```
   markets.ml.com/<hub>?p_p_id=multiDataReports_WAR_researchlibrary_portlet_INSTANCE_<X>
     &p_p_lifecycle=2&p_p_state=normal&p_p_mode=view
     &p_p_resource_id=getHtmlUrl
     &p_p_cacheability=cacheLevelPage
     &_multiDataReports_WAR_researchlibrary_portlet_INSTANCE_<X>_pid=pidvalue
   ```
2. Substitute `pidvalue` → actual `report_id`, POST → response is plain
   text: `https://rsch.baml.com/r?q=<token>&e=<urlenc-email>&h=<hash>`
3. Sanity-tested against report 12980737 (AA2000) — POST returned 200 OK
   with body `https://rsch.baml.com/r?q=whOrU3CBhJxZ5fO91loSPg&...`.

Validated end-to-end at
`playground/research/test_bofa_resolver.py`.

### Liferay JSON endpoints (informational)

Two `p_p_lifecycle=2` JSON endpoints discovered on the Advanced Search
page during the Phase 2 probe (both autocomplete-only, not listings):

* `POST /researchlibrary/advancedsearch?p_p_id=MercuryDynamicAutocompletePortlet_INSTANCE_autosuggest&p_p_lifecycle=2&...`
* `POST /researchlibrary/advancedsearch?p_p_id=MercuryDynamicAutocompletePortlet_INSTANCE_autosearch&p_p_lifecycle=2&...`

Both return `{"status":"success"}` acknowledgements only — not facet
or result data. The portal exposes JSON via the `p_p_lifecycle=2`
pattern but these two are not listing endpoints.

### Advanced Search firehose (COMPLETE — 2026-06-15)

> **Correction**: the Phase 2/3 doc note that the "Advanced Search
> results-listing endpoint was not yet discovered" and that a naive
> Playwright click timed out is now **superseded**. The firehose module
> is built, smoke-tested, and produces 2.3x the hub-crawler volume.

`markets.ml.com/researchlibrary/advancedsearch` (the
`SearchCriteriaPortlet`) is a full-taxonomy, paginated search
surface. Module: `playground/research/ingest/crawler_bofa_firehose.py`.

**Why it matters**: the per-hub crawler scrapes each hub's "latest ~N
per series" snapshot — approximately 240 tiles total, ~42 kept/week.
The real BofA feed is ~1,227 reports/week (verified live: all-disciplines
+ "Last 1 Week" = "1-25 of 1227"). The firehose queries Advanced Search
per macro-relevant discipline, skipping single-name equity bulk
(Equity-Fundamental alone is ~112,323 in the archive). Each
discipline-week is well under the 250-result UI pagination cap —
e.g. Economics + Last 1 Week = 48.

**Taxonomy (live-enumerated from `breadth_advsearch_taxonomy.json`)**:

- **Discipline** (asset-class axis): Economics, Commodities, Credit,
  Credit Strategy, Currency Strategy, Country Investment Strategy,
  Cryptocurrency & Digital Assets, Asset-Backed Securities,
  Convertibles, Equity - Fundamental, Emerging Markets
  Economics/Credit/Debt Strategy/Equity Strategy, etc.
- **Region**: Africa, AsiaExJapan, Australasia, Emerging Market
  Africa/Asia/Europe/MiddleEast, Emerging Markets Global, Europe,
  Global, Japan, Latin America, Middle East, North America.
- **Industry**: GICS sectors (Banks, Energy, Materials, …).
- **Subject**: Asset Allocation, Country Overview, Economic Analysis,
  Earnings Preview, ETF Research, etc.
- **Core Reports** (named series catalog): Best Ideas, China Macro
  Weekly, Credit Market Strategist, Economic Commentary, EM
  Daily/Weekly/Monthly, European Economics, Global Economic Analysis,
  Global Economic Calendar, etc.
- **Analyst directory**: hundreds of individual analysts + teams.
- **Date Range**: Today / Last 24h / Last 1 Week / Last 2 Weeks /
  Last 1 Month / Last 3 Months / Custom Range.
- Additional: company/ticker field, keyword field, flags
  (excludeModel, referencedTicker/Analyst/Disciplines).

**Results-row DOM** (different portlet from hub `multiDataReports` tiles):

- Row anchor: `_SearchSummaryPortlet_WAR_rlapp_portlet_INSTANCE_<INST>_<report_id>`
  with `onclick="javascript:htmlIconClickOnCachedPortlet('<report_id>',...)"`.
- Series in first `<span aria-hidden="true">` inside the anchor.
- Title/subtitle in `<span class="white-text" aria-hidden="true">`.
- Date + analyst in `.dark-grey-text` span and `navigateToResearchSearchProxy('...')`.
- PDF template: `<input id="_SearchSummaryPortlet_..._pdfResourceUrl" value="...pidvalue...">` —
  resolved identically to the hub crawler's `pdfResourceUrl` POST.
- Pagination: `<img alt="go to next page results">` next-control;
  hard cap at 10 pages (250 results).

**Critical timing**: discipline `<select>` triggers an async re-render.
Without `wait_for_load_state("networkidle")` + 1.5s settle after the
discipline select, you read stale all-time counts (e.g. "4423" instead
of the real weekly "48").

**Query flow** (`_query_discipline`):
1. `page.goto` Advanced Search → `networkidle` + 2.5s settle.
2. Derive `SearchCriteriaPortlet` INSTANCE id at runtime via regex
   (can change between sessions).
3. `select_option(#disciplineDropDown, label=discipline)` → `networkidle` + 1.5s.
4. `select_option(#dateRangeDropDown, label=date_label)` → 0.8s.
5. `click('input[value="Search"]')` → `networkidle` + 4.5s.
6. Pagination loop: parse rows → apply full drop stack → resolve PDF URLs → next-page.

**`_DISCIPLINE_TO_HUB`** (16 macro disciplines → existing synthetic hub keys,
verified against `crawler_bofa_firehose.py`):

| Discipline | Hub key |
|---|---|
| Economics | `economics_overview` |
| Emerging Markets Economics | `economics_country` |
| Country Investment Strategy | `economics_overview` |
| Currency Strategy | `fx_global` |
| Rates Strategy | `rates_regional` |
| Fixed Income Strategy | `rates_regional` |
| Fixed Income Technical Analysis | `technical_analysis` |
| Technical Analysis | `technical_analysis` |
| Quantitative Strategy | `technical_analysis` |
| Commodities | `commodities` |
| Multi-Asset Strategy | `investment_themes` |
| Investment Strategy | `investment_themes` |
| Credit Strategy | `credit_global` |
| High Yield Strategy | `credit_high_yield` |
| Emerging Markets Debt Strategy | `credit_em_fi` |
| Emerging Markets Credit | `credit_em_corporate` |

**250-cap guard**: if a discipline's total result count exceeds 250,
`_query_discipline_sub_partitioned` re-runs day-by-day with Custom Range
`fromDate`/`toDate` (format `MM/DD/YYYY`). Built and tested; not yet
exercised in practice (no weekly discipline came close to the cap in the
2026-06-08→15 smoke).

**Dedup**: a `seen_ids: set[str]` is shared across all disciplines in a
single `discover_reports` call. The firehose and hub crawler dedup cleanly
by `report_id` if both paths are run, since `ReportRef.uuid = report_id`
in both.

**Applies the full Phase-8 drop stack**: `_drop_reason` (admin/hub-blanket/
series-regex single-name/MBS data-table) + `credit_hub_drop_reason` +
`should_exclude` from `filters.bofa` — same as the hub crawler.

**Entry point**: `discover_reports(profile_dir, *, disciplines=None, since=None,
until=None, resolve_urls=True) -> list[ReportRef]`. Performs programmatic
login at the start of each run. Default date window: "Last 1 Week".

**1-week smoke (2026-06-08 → 2026-06-15, 16 disciplines)**:

| Metric | Value |
|---|---|
| Total kept | **98** (~14/day) |
| vs hub crawler | 2.3x (42/week hub) |
| MACRO | 38% (37) |
| RATES | 22% (22) |
| STRATEGY | 21% (21) |
| FX | 11% (11) |
| CREDIT | 5% (5) |
| COMMODITIES | 2% (2) |

Tests: `tests/unit/research/test_bofa_firehose.py` (31 tests).
Smoke harness: `playground/research/_smoke_bofa_firehose.py`.

**Status**: **LIVE 2026-07-17** — the firehose IS the prod path for BofA
(firehose-only decision; hub crawler retired from the orchestrator).

**Central-bank coverage**: no dedicated CB facet. CB content reached via
Discipline=Economics + Region + Core Reports series (e.g. Economic
Commentary, Global Economic Analysis).

**Macro events**: "Global Economic Calendar" exists as a named Core Report
series. "Conference Call" / "Conference Call Invitation" series appear in
hubs and are dropped as admin noise by the crawler. There is an
InlineAlertPortlet for Real-Time / Daily email alerts but no standalone
events/calendar API was verified.

**Audio / podcast**: per-tile `audioResourceUrl` resolves to a "Voice Blast
Player" HTML page. One sampled report (12983699) returned an empty player
(`window.location.href=''`) — no audio attached. Not currently ingested.

## Fetch strategy — REVISED (2026-06-19)

Three cases are implemented in
[`fetch_bofa.py`](../../../../playground/research/ingest/fetch_bofa.py).
`fetch_pdf(url, profile_dir) → bytes` dispatches in order:
`%PDF-` magic → return; expired interstitial → `_fetch_via_proceed_page`;
viewer HTML → `_fetch_via_viewer`; else `FetchError`.
`pipeline.py` routes `research1.ml.com` / `rsch.baml.com` URLs through
this vendor-specific fetcher.

**Case 1 — Direct PDF** (recent reports): a single GET on
`research1.ml.com/C?q=<token>&e=<urlenc-email>&h=<hash>` returns
`application/pdf` bytes directly. The HMAC `h=` parameter
self-authenticates — no cookies, no SAML handshake required.
Confirmed on 5 recent reports.

**Case 2 — Email "download" link / `&cmd=PDF` path**: the form is
`rsch.baml.com/r?q=<token>&e=<recipient-email>&h=<hash>`; appending
`&cmd=PDF` returns the PDF for most report types. Verified with
`e=adoshi@rvcapital.com`. Note: this path does NOT cover all report
types — see Case 3 for the viewer case.

### Expired-report interstitial (CORRECTED 2026-06-15 — now recoverable)

> **Correction**: the doc previously stated that expired-interstitial
> reports "aren't currently recoverable" and cited a "33% fail-rate"
> at N=3. Both claims are **wrong**. The interstitial is reliably
> recoverable via the mechanism below; the fail-rate figure was based
> on a single mis-classified failure at N=3.

For older reports the first GET returns a ~2KB ASP.NET interstitial
("Expired") with a "Proceed" button:

```html
<form method="post" action="./?q=<token>&e=<email>&h=<hash>" id="GetDoc">
  <input type="hidden" name="__VIEWSTATE" value="..." />
  <input type="hidden" name="__VIEWSTATEGENERATOR" value="..." />
  <input type="hidden" name="__EVENTVALIDATION" value="..." />
  <input type="submit" name="Proceed" value="Proceed" />
</form>
```

**Why a plain `ctx.request.post` does not work**: the Proceed
acknowledgement is bound to the live POST→meta-refresh→redirect
navigation. Replaying via the request client lands back on the
interstitial; the resulting `/C/?q=...` (trailing slash) URL returns
the interstitial again on a bare GET. Additionally, Chrome renders
the recovered PDF inline, so `response.body()` would return the
PDF-viewer shell, not PDF bytes.

**Current approach** (`_fetch_via_proceed_page` in `fetch_bofa.py`):

1. `_ensure_pdf_downloads(profile_dir)` — sets
   `plugins.always_open_pdf_externally=True` in the Chrome profile's
   `Preferences` file **before** context launch, so Chrome downloads
   PDFs instead of rendering them inline. Idempotent.
2. Fast path: `ctx.request.get(url)` — if the response is PDF bytes,
   return immediately.
3. If response matches the expired interstitial pattern (< 20 KB,
   contains "Expired" and `name="Proceed"`): open a new page,
   `page.goto(url)`, click `#Proceed`, await the resulting download
   event, stream to a temp file, read back and verify `%PDF-` magic.

**Verified**: report 12905458 ("2026: Attitude determines altitude",
Global Macro Year Ahead) recovered as a 59-page, 2,050,835-byte
`%PDF-1.6` document. The 5-vendor code-promotion smoke run
(2026-06-15) fetched 5/5 reports OK including one via this path.

### Case 3 — HTML viewer / re-mint (forwarded & foreign-recipient links — 2026-06-19)

Some `rsch.baml.com/r?q=...&e=<recipient>&h=...` links 302-redirect to
an **HTML report viewer** (Liferay DXP; title like "BofA - India Watch"
/ "Report - Liferay DXP", ~1.9 MB) rather than returning PDF bytes.
Appending `&cmd=PDF` is the **wrong mechanism** for this report type —
it still lands in the viewer rather than triggering a direct PDF
response.

**Key mechanism — re-mint:** when our authenticated session renders the
viewer, BofA re-mints the PDF link bound to our entitlement. The viewer
HTML contains a fresh `research1.ml.com/C?q=<new-token>&e=adoshi%40rvcapital.com&h=<new-hash>`
URL, **ignoring the recipient address baked into the original link**.
Entitlement follows who is logged in, not the `e=` email in the URL.
This means **forwarded links and links addressed to BofA employees or
other recipients are fetchable** via our session.

> **Correction to earlier characterisation**: previous doc text described
> viewer-landing reports as "HTML-only / no PDF rendition" or "not
> recoverable". That was wrong — they do have a PDF; it is reached via
> this re-mint mechanism.

**Implementation** (`fetch_bofa.py`):

- `_looks_like_viewer(body, url)` — conservative HTML-viewer detector:
  returns `False` for `%PDF-` magic and for the expired interstitial;
  triggers when the body is ≥ 10 KB HTML and contains `research1.ml.com`
  or `Liferay`, or when the final URL host is `rsch.baml.com`.
- `_extract_reminted_pdf_url(html)` — pure function; regexes the re-minted
  `research1.ml.com/C?...` URL from the viewer HTML (handles both `&`
  and `&amp;` encoding), decodes `&amp;` → `&`, returns `None` if absent.
- `_fetch_via_viewer(ctx, url)` — navigates to the viewer URL, waits for
  `networkidle` + 2s settle (Liferay SPA hydration), reads page content:
  1. **Primary**: extract re-minted URL via `_extract_reminted_pdf_url`,
     GET it with `ctx.request.get`. If it returns `%PDF-` bytes, done.
     If it returns the expired interstitial, route to `_fetch_via_proceed_page`.
  2. **Fallback**: if the re-minted URL is absent or does not yield a PDF,
     click the PDF button (`a[title="PDF"]`, with three additional selector
     fallbacks) via `expect_download` and read the downloaded file.

**Tests**: `tests/unit/research/test_bofa_fetch.py` — 10 pure-function
tests for `_extract_reminted_pdf_url` and `_looks_like_viewer`; fixture
is the saved viewer HTML. Full research suite 694/694 pass.

**Verified (2026-06-19)**: original link addressed to
`jamshed.d.sidhva@bofa.com` → recovered a valid 7-page `%PDF-1.6`,
1.27 MB, doc 12985511 ("India Watch"), via the re-minted
`e=adoshi@rvcapital.com` URL.

**Ingestion implication**: the Outlook **forwarded-link archetype**
(links embedded in email bodies addressed to a BofA employee or
forwarded to us from an external recipient) and HTML-viewer report
types that previously would have failed with "did not return PDF" are
now fetchable end-to-end. This makes the BofA Outlook email channel
(see the channel note at the top of this doc and
[`../outlook_email_channel.md`](../outlook_email_channel.md)) a viable
source of resolvable PDF links, not just body-only commentary.

## Fetch strategy — historical (2026-06-03 probe, superseded)

**C. Viewer redirect chain (SAML autopost)** — the resolved signed
URL on `rsch.baml.com` does NOT serve PDF bytes directly. It goes
through a cross-domain SAML POST binding:

1. First GET to `https://rsch.baml.com/r?q=<token>&...&cmd=PDF`
   returns HTML (`text/html;charset=utf-8`, ~15KB) containing a
   `<form action="https://rsch.baml.com/acs">` with a `RelayState`
   pointing back to `https://rsch.baml.com/report?...&cmd=PDF`.
2. The HTML auto-submits via JS — POSTs a SAML assertion to
   `rsch.baml.com/acs`.
3. `/acs` accepts the assertion, sets a `rsch.baml.com` session
   cookie, then redirects to the final report URL.
4. The final URL serves the actual PDF (or a viewer that wraps it).

`ctx.request.get()` does NOT execute the auto-submit JS — it just
returns the form HTML. **Fetching must use Playwright `page.goto()`**
to handle the handshake (ANZ-style redirect-chain pattern).

Implementation plan for Phase 3:

* `fetch_bofa.py` — `async def fetch_pdf(ctx, signed_url) -> bytes` that:
  - Navigates a fresh `page` to `signed_url + "&cmd=PDF"`
  - Waits for the SAML autopost to complete (`page.wait_for_load_state("networkidle")`)
  - Captures the final URL + body via Playwright's response interception
  - First fetch per crawl is heaviest (~5-8s for the SAML round-trip);
    subsequent fetches reuse the session cookie established on
    `rsch.baml.com` → can use `ctx.request.get()` directly (TBD;
    confirm whether the SAML cookie scope is per-tab or per-context).

## Login

**Programmatic — same PingFederate stack as Barclays.** BofA's session
tokens are in non-persistent JS storage (sessionStorage / session-only
cookies) that don't survive Playwright's `context.close()`. The
persistent profile DOES save durable cookies but NOT the Premia auth
ticket. Empirically headless and headed runs both redirect to login
once the original explorer session has aged out (~minutes via the
PingFederate IDP timeout).

Implementation: `playground/research/ingest/login_bofa.py`
(2026-06-03 — same shape as `login_barclays.py`):

* `is_authenticated(ctx)` — quick check via `markets.ml.com/home`
  title (`Home - BofA Markets` vs `Login - BofA Markets`).
* `login(ctx, username, password)` — fills `#userid`, blurs (triggers
  `getUserStatus()` webservice), fills `#password`, clicks
  `button[aria-label="Login button"]` (which calls `doLogin()` JS).
  Settles ~5s after the SAML round-trip back to `/home`.
* OneTrust cookie banner is dismissed first (`#accept-recommended-btn-handler`
  or `#onetrust-accept-btn-handler`).

**MFA — SOLVED (2026-07-17).** The second factor is an **email security
token** ("Restricted Access Authentication" / "Additional Verification"):
an 8-digit token emailed from `bofamarkets@bofa.com`, subject **"BofA
Mercury Portal Token"**, body "Your token is: NNNNNNNN", valid 5 minutes,
filed by Outlook rules in the **`Research\BOFA`** folder. `login_bofa.py`
handles it end-to-end:
* `_resolve_post_submit(page)` — after Log In, resolves BOTH outcomes:
  a trusted-session **direct landing on Mercury home (no token)** OR the
  token page (tolerant of render lag).
* `_read_portal_token()` — polls `Research\BOFA` via **local Outlook
  (`win32com`)** for the freshest token (`_TOKEN_RE`, <4 min old); the
  shared `Win32OutlookClient` reads only the Inbox, so this navigates to
  the subfolder itself. (Not Graph — local MAPI.)
* `_submit_token()` — fills the `Token` field + clicks Submit.
E2E verified: `is_authenticated=True`, `Home - BofA Markets`.

**Operational caution**: do NOT rapid re-login against `markets.ml.com`.
Each login is a PingFederate SAML round-trip that the portal monitors for
automation patterns. Repeated logins risk both re-triggering MFA and
account suspension. Mitigate by:
- Reusing one authenticated session per run (do not `ctx.close()` + reopen
  mid-run).
- Spacing out portal hits — the firehose crawler already opens one
  Playwright page per discipline sequentially.
- Relying on the persistent profile to extend session lifetime between
  daily runs.

Login flow verified (pre-MFA trigger) on 2026-06-03 — full 21-hub crawl
completed in ~3 minutes including the ~15s login round-trip.

## Watermarks / quirks

TBD.

## Daily volume

TBD — confirm against 24h of clean ingest after Phase 6 smoke.

## Phase status

- [x] Phase 0 — Gate check + `vendors.yml` entry (2026-06-03).
- [x] Phase 1 — Interactive login + 10 snapshots (2026-06-03). No MFA.
- [x] Phase 1.5 — `login_bofa.py` programmatic login (2026-06-03). Same PingFederate stack as Barclays.
- [x] Phase 2 — 23-candidate-hub probe complete (2026-06-03): 256 tiles, 154 series across 21 productive hubs. Per-hub HTML scrape chosen as primary discovery path; Advanced Search firehose subsequently confirmed working 2026-06-15 (see "Advanced Search firehose" section).
- [x] Phase 2.5 — URL resolver pattern locked (2026-06-03): `htmlResourceUrl` template + `pidvalue` substitution → POST → signed `rsch.baml.com/r?q=...`. Validated end-to-end at `test_bofa_resolver.py`.
- [x] Phase 2.6 — PDF fetch identified as SAML autopost (2026-06-03): must use Playwright `page.goto()` for the cross-domain `rsch.baml.com/acs` handshake; subsequent fetches can reuse the session cookie. ANZ-style.
- [x] Phase 2.7 — **PDF endpoint corrected** (2026-06-04): the `htmlResourceUrl` path serves HTML viewer pages (SAML autopost). The symmetric `pdfResourceUrl` resolves to **`research1.ml.com/C?q=<token>&e=<email>&h=<hash>`** which returns `application/pdf` bytes via a single GET — **self-authenticating via HMAC**, no SAML, no cookies required (verified by fetching from a clean unauthenticated context).
- [x] Phase 3 — `crawler_bofa.py` + `fetch_bofa.py` + `filters/bofa.py` + `classifiers/bofa.py` built (2026-06-04). **21 production hubs** walked (Advanced Search + Structured Products excluded — both return 0 tiles), tile-level 3-stage drop (admin / hub-blanket / series-regex single-name / MBS data-table), URL resolution via `pdfResourceUrl` POST → `research1.ml.com` PDF endpoint.
- [x] Phase 3.5 — 2-hub smoke (economics_overview + credit_em_corporate, 2026-06-04): 27 parsed → 4 dropped (single-name corp) → 22 kept → 100% URL resolution.
- [x] Phase 3.6 — Deep probes A+B+C+D (2026-06-04): confirmed per-tile has no hidden structured signals (no `data-*` attrs), discovered audio/email sibling ResourceUrls. Advanced Search firehose characterised (see "Advanced Search firehose" section above — verified working 2026-06-15).
- [x] Phase 4 — Filter + classifier wired + registered in `classifiers/__init__.py` + `canonical.VENDOR_DISPLAY`.
- [x] Phase 5 — Orchestrator **wired LIVE 2026-07-17** (firehose; `auth_realm=rv-pingfed`). Registrations active in `ingest_today.py` + `classifiers/__init__.py` + `pipeline.py`. Smoke inserted ids 19325-6. See "Orchestrator wiring" section above.
- [x] Phase 6 — Migration `076_seed_bofa_dim_vendor.sql` applied 2026-06-04. First DB-write smoke: 2 reports inserted (ids 3134/3135), 22 chunks, 9 tag rows.
- [ ] Phase 6c — Full-day embed-on smoke + retrieval check.
- [x] Phase 7 — **LIVE 2026-07-17**: (a) MFA handler DONE (email token), (b) firehose-only decision DONE, (c) Phase 6c embed smoke DONE (scheduled cycle: 64 ins/0 fail; `smoke_bofa_retrieval.py` 3/3 PASS). `vendors.yml` → `production`; `index.md` → LIVE.
- [x] Phase 8 — **COMPLETE (2026-06-15)**. Hard-taxonomy/volume audit +
  tightening done and validated against a 1-week smoke
  (2026-06-08 → 2026-06-15). See "Phase 8 tightening" section below.

## Deep coverage probe (2026-06-04 — partial; updated 2026-06-15)

Ran `probe_bofa_coverage.py` (sub-probes A pagination / B rsch.baml /
C multimedia / D fetch-rates) to characterize true archive depth
before promotion. Results:

- **A — Series pagination**: `submitMorePage` callback regex matched
  only 2 of 4 representative series; pagination URL itself returned
  0 tiles. Needs rework — defer to a focused follow-up probe.

- **B — rsch.baml.com surface** (**CORRECTED 2026-06-15**):
  The previous note that "`/search` is a 133KB Liferay PortalSearch
  with structured filter fields (assetClass, mlDiscipline,
  focusRegion...)" is **wrong**. That claim came from the 2026-06-04
  probe snapshot `rsch_baml_search.html` which was mis-interpreted.
  Verified live on 2026-06-15: `rsch.baml.com/`, `/search`, and
  `/analyst` all render as a per-report token-viewer page ("BofA -
  HTML Report" or "BofA - Restricted Report") with **zero filter
  dropdowns**. `rsch.baml.com` is the **per-report viewer host** for
  links delivered via email — it is not a browseable search portal.
  Any `/search?...` query string is treated as a report token, not a
  search query. There is no filter UI here.

- **C — Multimedia**: `/researchlibrary/rlmultimedia_ext` and
  `/researchlibrary/RLMultimedia` both render full Liferay pages but
  with **0 `Table_report` tiles** — they use a different tile
  structure that the current regex doesn't catch. Probably video
  cards. Defer until we decide whether multimedia is in scope.

- **D — Fetch success rate** (**RESOLVED 2026-06-15**): earlier
  probe crashed mid-run. The 2026-06-15 smoke confirms the fetch
  path is stable; see "Fetch strategy" section above.

Artefacts: `bofa_explore/coverage_*.md`,
`bofa_explore/rsch_baml_search.html` (the HTML that was
mis-characterised as a search portal),
`bofa_explore/breadth_advsearch_taxonomy.json`,
`bofa_explore/breadth_search_results.html`.

## Unknowns to resolve before prod

All Phase-8 blockers are cleared. Remaining open items are post-wiring
observations, not blockers.

1. ~~**True daily volume**~~ — **RESOLVED 2026-06-15**: 1-week smoke
   (2026-06-08 → 2026-06-15) measured **~6/day** kept (42 total in the
   window). 64 of the total drops were outside the date window
   (historical tiles returned by hubs); actual daily-cadence volume is
   stable.
2. ~~**PDF fetch success rate**~~ — **RESOLVED 2026-06-15**: 5/5 OK in
   the code-promotion smoke including one expired-interstitial recovery.
   Not a blocker; expand the sample after the DB-load smoke.
3. ~~**`/C/?q=...` failure rate**~~ — **RESOLVED 2026-06-15**: the
   expired-interstitial is recoverable via `_fetch_via_proceed_page`.
   See "Fetch strategy" section.
4. ~~**Single-name leakage**~~ — **RESOLVED 2026-06-15**: zero
   single-name leaks in the 1-week smoke (42 kept docs). The credit-hub
   allowlist gate (Phase 8) eliminated the Samsung C&T / VF Corporation
   / FedEx class that the earlier series-regex missed. Bare-brand series
   names are now covered by the default-drop posture.
5. ~~**Drop-set false positives**~~ — **RESOLVED 2026-06-15**: the
   old "32%" figure was from a pre-Phase-8 run. Post-Phase-8 funnel:
   240 parsed → 42 kept (64 outside date window, 134 actively dropped).
   Active drop breakdown: credit-hub-nonmacro 47, mbs-datatable 36,
   equity-hub-blanket 20, single-name-corporate 3, noise/title-regex 6,
   before-since 64 (date-window). No false positives identified in the
   42 kept.
6. ~~**Classifier accuracy**~~ — **RESOLVED 2026-06-15**: 1-week smoke
   composition: MACRO 38% (16) · STRATEGY 9 · CREDIT 9 · COMMODITIES 4
   · EQUITY 2 · FX 1 · RATES 1. Country resolved 14/42 with no known
   wrong tags (IPCA→BR correct, BR/IN/CN/RS/PE/ID all correct).

**Remaining steps before prod** (in priority order):

1. **MFA handler** — extend `login_bofa.py` with Barclays-style Outlook
   OTP poll. Blocker for any repeated automated run. See "Login" section.
2. **Firehose integration decision** — `crawler_bofa_firehose.py` is built
   and smoke-tested (98 kept/week, 2.3x hub crawler). Decide: replace hub
   crawler, augment (both paths, dedup by `report_id`), or hub-only. The
   two paths are additive. See "Advanced Search firehose" section.
3. **Phase 6c embed smoke** — ✅ DONE 2026-07-17: scheduled `--embed`
   cycle inserted 64 / 0 failed; `smoke_bofa_retrieval.py` 3/3 PASS.
4. **Orchestrator wiring + DB-load smoke** — ✅ DONE: firehose registered
   in `ingest_today.py` (`auth_realm=rv-pingfed`); smoke inserted ids 19325-6.

**Open minor tuning items** (not blockers for prod wiring):

- "Today in European Credit" is a daily morning recap that currently
  passes the credit-hub allowlist via the `morning credit` pattern. It
  is borderline (high-cadence, low-analytical) but deliberately kept
  until live volume confirms the content quality.
- One or two LatAm aggregate-EQUITY items survive the equity-hub blanket
  (they are strategy-level, not single-name) but are tagged EQUITY by
  the hub. These may be reclassified to STRATEGY in a future pass once
  live volume confirms the series content.

## Phase 8 tightening (COMPLETE — 2026-06-15)

A 1-week discovery-only smoke (2026-06-08 → 2026-06-15, no PDF download)
surfaced four quality issues; all were fixed and re-validated. Changes span
the crawler, filter, and classifier.

### 1. Wiring-gap fix (`crawler_bofa.py`)

BofA was the only vendor crawler that never called its filter's
`should_exclude()` — so `filters/bofa.py` was entirely dead code. Fixed:
`_walk_hub` now calls `filters.bofa.credit_hub_drop_reason(hub, series, title)`
and `filters.bofa.should_exclude(title=...)` after the existing
`_drop_reason` pass, mirroring the `crawler_citi` / `crawler_ms` call
pattern. Both calls are sequential in the `_walk_hub` loop; confirmed in
`playground/research/ingest/crawler_bofa.py::_walk_hub` lines 515–531.

### 2. Credit-hub keep-allowlist (`filters/bofa.py::credit_hub_drop_reason`)

Credit hubs now **default-DROP** unless the tile matches a
macro/sovereign or credit-strategy KEEP signal. This mirrors the existing
equity-hub blanket-drop. The eight hubs in scope: `credit_global`,
`credit_strategy_americas`, `credit_high_grade`, `credit_high_yield`,
`credit_securitized`, `credit_em_fi`, `credit_em_corporate`,
`credit_municipal`.

Keep signals checked in order:
1. `_CREDIT_STRATEGY_KEEP_RE` against series then title: `strategist`,
   `strategy`, `situation room`, `fixed income`, `best ideas`, `cross-asset`,
   `credit derivatives`, `market review`, `securitized products strategy`,
   `securitization weekly`, `agency mbs weekly`, `high yield & loan`.
2. `_SOVEREIGN_EM_KEEP_RE` against series then title: `watch`,
   `economic weekly`, `economic viewpoint`, `economic monitor`,
   `emerging insight`, `gems`, `eemea`, `em `, `macro`, `morning credit`,
   `european morning credit`, `asia economic`.
3. `_MACRO_TITLE_KEYWORDS` tuple (blob = series + title): `cpi`, `ipca`,
   `inflation`, `monetary`, `central bank`, `rate cut/hike/decision`,
   `election`, `politics`, `sovereign`, `fiscal`, `gdp`, `imf`, `monsoon`,
   `liquidity`, `fx reserves`, plus CB acronyms (bcb/copom/bccch/banxico/
   rbi/boj/pboc/bok/fomc/ecb/boe).

Drop reason shape: `credit-hub-nonmacro:<series[:30]>`.

This single rule fixed three leak classes:
- **Single-name issuers** where the series was a bare brand name the
  corporate-suffix regex didn't catch: Samsung C&T, Victoria's Secret,
  VF Corporation, Campbell's, FedEx "Nuts & Bolts".
- **Pure-sector credit wraps**: Food & Beverage, Consumer Products,
  Retail/Restaurant, Packaged Food Reference Card, Petrochemical Monitor,
  Utilities & Power Weekly, Health Care Policy Weekly, etc.
- **Data packs** in `credit_securitized` with generic/date titles
  (Hybrid Arm Package, PassThrough Package, Servicer Tracker).

### 3. Noise additions

**`filters/_noise.py::EVENT_ADMIN_PREFIXES`** (cross-vendor):
added `in 1hr`, `in 1 hr`, `in 2hr`, `in 2 hr`, `in 30 mins` — fixes
BofA "In 1hr: European Credit Research" leak.

**`filters/bofa.py::EXCLUDED_TITLE_SUBSTRINGS`**: added
`virtual commodity conference` and ` credit conference`.

**`filters/bofa.py::_DATE_ONLY_TITLE_RE`**: regex backstop for
date-only / boilerplate titles: `"12 June 2026"`, `"11-Jun-26 Close"`,
`"Week ending June 12, 2026"`.

### 4. Classifier — EM-macro reclassification (`classifiers/bofa.py::_em_macro_reclassify`)

Reports from `credit_em_*` hubs (or with a series matching
`_EM_MACRO_SERIES_RE`: Watch / Economic Weekly / Emerging Insight /
GEMs / EEMEA / Asia Economic / What's priced in) are reclassified from
CREDIT → MACRO when the title also hits `_MACRO_KEYWORDS_RE`. Credit-strategy
series (`_CREDIT_STRATEGY_SERIES_RE`: Strategist / Situation Room / Fixed
Income Strategy / High Yield & Loan) are explicitly exempt and stay CREDIT.
This is why MACRO jumped from 6 → 16 in the re-run.

### 5. Classifier — country fix (`classifiers/bofa.py::_country_from_text`)

Bug fixed: the old substring `"us "` matched inside "plus" / "versus" /
"consensus", tagging Brazil IPCA reports as US. Now uses word-boundary
regex for short codes (US/UK/EU). New CB/series anchors added:
`IPCA/BCB/Copom→BR`, `BCCh→CL`, `Banxico→MX`, `RBI→IN`, `BoJ→JP`,
`PBoC→CN`, `BoK→KR`, `Fed/FOMC→US`, `ECB→EU`, `BoE→UK`, plus named
series anchors (`Brazil Watch→BR`, `India Watch→IN`, `China Viewpoint→CN`,
`Japan Rates/Watch→JP`). Countries added: Serbia (RS), Armenia (AM).

### 6. Tests

New: `tests/unit/research/test_bofa_filters.py` +
`tests/unit/research/test_bofa_classifier.py` (123 BofA tests total).
Full research unit suite: 510/510 pass.

### Smoke validation (before → after)

| Metric | Before (pre-Phase-8) | After (Phase-8) |
|---|---|---|
| Kept (1-week window) | 70 | **42** (~6/day) |
| MACRO | 6 (9%) | **16 (38%)** |
| STRATEGY | — | 9 |
| CREDIT | 44 (63%) | 9 |
| COMMODITIES | — | 4 |
| EQUITY | — | 2 |
| FX | — | 1 |
| RATES | — | 1 |
| Single-name leaks | several | **0** |
| EM-macro mislabelled | yes (IPCA→US) | **0** |
| Country resolved | 9/70 (wrong) | 14/42 (correct) |

Drop funnel (240 parsed total, 64 outside date window, 134 actively dropped):

| Drop reason | Count |
|---|---|
| before-since (date window) | 64 |
| credit-hub-nonmacro | 47 |
| mbs-datatable | 36 |
| equity-hub-blanket | 20 |
| single-name-corporate | 3 |
| noise / title-substring / date-only-title | 6 |
| no_url (resolver failure) | 2 |

## Last verified

2026-07-17 — **LIVE.** MFA solved (email security token auto-read from Outlook `Research\BOFA` by `login_bofa.py`; handles token + trusted-session-no-token). Credit hubs keep-by-default (single-name issuer + sector credit; `crawler_bofa._drop_reason` + `filters/bofa.credit_hub_drop_reason` relaxed). Single live download test: real `%PDF-1.5` fetched via SAML. Wired into orchestrator (firehose, `auth_realm=rv-pingfed`); `EMBED=false LIMIT=2` smoke inserted ids 19325-6 (0 failed). `smoke_bofa_retrieval.py` added; `vendors.yml`→production; `index.md`→LIVE. Full detail: [`../../development/credit_bofa.md`](../../development/credit_bofa.md).

2026-06-19 — Fetch Case 3 (HTML viewer / re-mint) implemented and verified live: `_fetch_via_viewer` + `_extract_reminted_pdf_url` + `_looks_like_viewer` added to `fetch_bofa.py`; 10 new pure-function tests in `tests/unit/research/test_bofa_fetch.py`; full research suite 694/694 pass. Forwarded / foreign-recipient `rsch.baml.com` links (e.g. `e=jamshed.d.sidhva@bofa.com`) confirmed fetchable via viewer re-mint (doc 12985511, 7-page, 1.27 MB). Earlier "HTML-only / not recoverable" characterisation corrected.

2026-06-16 — Phase 8 COMPLETE: wiring-gap fixed, credit-hub allowlist added, noise additions, classifier EM-macro reclassification + country fix, 123 new tests. Hub 1-week smoke: 42 kept (6/day), 0 single-name leaks. Firehose module (`crawler_bofa_firehose.py`) built + 31 tests + 1-week smoke: 98 kept (14/day, 2.3x hub). MFA now observed on login — `login_bofa.py` must be extended before prod. Phase 5 registration reverted to PROD-HOLD (comments confirmed in all three entry-point files).

## Noise filter update (2026-06-10)

Shared cross-vendor noise classifier wired into
[`ingest/filters/_noise.py::classify_noise`](../../../../playground/research/ingest/filters/_noise.py)
and called as the final fallback inside [`filters/bofa.py::should_exclude`](../../../../playground/research/ingest/filters/bofa.py).
Three universal title-pattern families plus a cross-vendor EQUITY
conference / sales-event drop in [`relevance._is_equity_conf_event`](../../../../playground/research/ingest/relevance.py).

Smoke against the full 4,498-title `research.dim_report` corpus dropped
**0 bofa docs**:

| family | n | sample |
|---|---|---|
| chart-pack | 0 | (no drops yet — 2 reports in DB from manual smoke) |
| morning-note | 0 | (no drops yet) |
| event-admin | 0 | (no drops yet) |
| conf-event (EQUITY only) | 0 | (no drops yet) |

The conf-event rule fires only when `result.asset_class == EQUITY` so
MACRO-tagged "Takeaways" / "Trip Notes" titles (real policy / sovereign
macro content) pass through unaffected.

Test pins: [`test_noise_filter.py`](../../../../playground/research/test_noise_filter.py)
(116 chart-pack / morning-note / event-admin assertions),
[`test_relevance_conf_event.py`](../../../../playground/research/test_relevance_conf_event.py)
(35 conf-event assertions). Re-runnable smoke harnesses:
[`_smoke_noise_filter.py`](../../../../playground/research/_smoke_noise_filter.py),
[`_smoke_conf_event.py`](../../../../playground/research/_smoke_conf_event.py).

