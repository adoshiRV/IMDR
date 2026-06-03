# BofA Securities — Research scraper

**Status: PROBE (Phase 1 complete 2026-06-03 — awaiting Phase 2 sign-off)**

Pattern: **HTML scraping** (Liferay server-rendered portal), NOT a JSON
listing API. Closest analogue in our stack: HSBC. Document delivery via
**signed `rsch.baml.com` URLs** embedded in the listing HTML (no
frontmatter round-trip needed).

## Portal

| | |
|---|---|
| Hostname | `markets.ml.com` (legacy Merrill Lynch domain) |
| Product name | **BofA Securities Mercury®** |
| Sign-in URL | `https://markets.ml.com/home` |
| Username | `.env: IMDR_RESEARCH_BOFA_USERNAME` (`arjdoshi01`) |
| Password | `.env: IMDR_RESEARCH_BOFA_PASSWORD` |
| MFA | **none observed at first login 2026-06-03** — session cookies in persistent profile suffice |
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

| Asset class | Hub URL |
|---|---|
| Equities — Regional Overview | `markets.ml.com/researchlibrary/global1` |
| Equities — ETF Analytics | `markets.ml.com/researchlibrary/exchange-traded-funds` |
| Equities — Structured Products | `markets.ml.com/structured-products` |
| Economics — Global | `markets.ml.com/economics-overview` |
| Economics — Country | `markets.ml.com/economics-country` |
| Economics — Interactive Forecasts | `markets.ml.com/researchlibrary/forecastsummaryreport` |
| Technical Analysis | `markets.ml.com/researchlibrary/technical-analysis` |
| Credit — Global | `markets.ml.com/researchlibrary/global` |
| Credit — Strategy Americas | `markets.ml.com/credit-strategy-americas` |
| Credit — High Grade | `markets.ml.com/high-grade` |
| Credit — High Yield/Distressed | `markets.ml.com/high-yield-distressed` |
| Credit — Securitized (MBS) | `markets.ml.com/mbs` |
| Credit — EM FI Strategy & Econ | `markets.ml.com/emerging-markets-global` |
| Credit — EM Equity Strategy | `markets.ml.com/gem-equity-strategy-and-equity-fundamental` |
| Credit — **GEMs Corporate Credit** | `markets.ml.com/em-corporate-credit` |
| Credit — Municipal | `markets.ml.com/municipal` |
| Rates — Regional | `markets.ml.com/global-overview` |
| Rates — Inflation-Linked | `markets.ml.com/inflation` |
| FX — G10 Strategy | `markets.ml.com/researchlibrary/global-fx-strategy` |
| FX — Global FX | `markets.ml.com/foreign-exchange` |
| Commodities | `markets.ml.com/researchlibrary/commodities` |
| Investment Themes | `markets.ml.com/researchlibrary/investment-themes` |
| **Advanced Search (firehose candidate)** | `markets.ml.com/researchlibrary/advancedsearch` |

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

The HTML viewer URL is the same as the PDF URL except for the `cmd=PDF`
suffix. This is great — no second round-trip needed to convert a
viewer link to a PDF link.

### Static assets (Excel forecast workbooks)

`https://static1.markets.ml.com/RLApp-portlet/RLDocuments/*.xlsx` —
e.g. `BofAML_Global_Macro_Forecasts.xlsx`. Likely a candidate for
direct download in a later phase (not covered by the standard PDF
ingest path).

## Listing API

**No JSON listing endpoint. Per-hub HTML scrape, with lazy URL
resolution via a Liferay portlet resource endpoint.**

### Per-hub HTML scrape (Phase 2 probe — 2026-06-03)

23 hubs walked end-to-end (`playground/research/probe_bofa_listing.py`):

* 256 distinct tiles parsed across 22 hubs (Advanced Search +
  Structured Products returned 0).
* 154 distinct "series" — taxonomy now mapped at
  `playground/research/bofa_explore/series_by_hub.md`.
* 70% of tiles carry a numeric `report_id` (from
  `_checkAnalystHover('<id>', ...)` JS handler in the anchor tag).

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

Confirms the portal exposes JSON via the `p_p_lifecycle=2` pattern.
The Advanced Search results-listing endpoint (if any) was not yet
discovered — the "Search" button uses a JS validator function
(`_SearchCriteriaPortlet_..._myInputSearchValidator()`) before the
form actually submits, so a naive Playwright click times out. Worth
re-investigating in Phase 8 if per-hub walking becomes a volume
bottleneck.

## Fetch strategy — REVISED (2026-06-04)

**Direct GET on the `pdfResourceUrl` endpoint** — the symmetric
counterpart to `htmlResourceUrl` discovered after the initial probe.
`pdfResourceUrl` resolves to **`research1.ml.com/C?q=<token>&e=<urlenc-email>&h=<hash>`** which returns `application/pdf` bytes via a single
authenticated GET. The HMAC `h=` parameter self-authenticates the
URL — no cookies, no SAML handshake required (verified by fetching
from a clean unauthenticated context).

Implementation: [`fetch_bofa.py`](../../../../playground/research/ingest/fetch_bofa.py)
exposes `fetch_pdf(url, profile_dir) → bytes` with the same signature
as `fetch.py`'s standard fetcher. `pipeline.py` dispatches by URL host
to route `research1.ml.com` / `rsch.baml.com` URLs through this
vendor-specific fetcher.

### Expired-report interstitial

For older reports (publication date > ~6 months back), the first GET
returns a ~2KB ASP.NET interstitial page with a "Proceed" button:

```html
<form method="post" action="./?q=<token>&e=<email>&h=<hash>">
  <input type="hidden" name="__VIEWSTATE" value="..." />
  <input type="hidden" name="__VIEWSTATEGENERATOR" value="..." />
  <input type="hidden" name="__EVENTVALIDATION" value="..." />
  <input type="submit" name="Proceed" value="Proceed" />
</form>
```

`fetch_bofa.py` parses the form fields and POSTs back to the
urljoin'd action URL (which collapses to `/?q=...` — the form action
`./?q=...` resolves to the parent path because Liferay treats `/C`
as a file, not a directory). The Proceed POST returns a meta-refresh
to `https://research1.ml.com/C` (no query); after the session cookie
is set, re-fetching the original `/C?q=...` URL returns the PDF.

### Known failure mode

A small number of tiles surface a variant URL pattern **`research1.ml.com/C/?q=<token>...`** (note the trailing slash before `?`). These return non-PDF HTML even after the Proceed flow and aren't currently recoverable. Empirically these correspond to theme / strategy reports with no PDF rendition. They fail gracefully (one `FAIL` line in the run log) and are dropped from ingest — investigate in Phase 8 if volume is material.

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
* Empirically (2026-06-03) no MFA on `arjdoshi01` — username + password
  is sufficient. If MFA gets enabled later, extend with the
  Outlook-poll pattern referenced in `login_barclays.py`.

Login flow verified end-to-end on 2026-06-03 — full 23-hub probe
completes in ~3 minutes including the ~15s login round-trip.

## Watermarks / quirks

TBD.

## Daily volume

TBD — confirm against 24h of clean ingest after Phase 6 smoke.

## Phase status

- [x] Phase 0 — Gate check + `vendors.yml` entry (2026-06-03).
- [x] Phase 1 — Interactive login + 10 snapshots (2026-06-03). No MFA.
- [x] Phase 1.5 — `login_bofa.py` programmatic login (2026-06-03). Same PingFederate stack as Barclays.
- [x] Phase 2 — 23-hub probe complete (2026-06-03): 256 tiles, 154 series. Per-hub HTML scrape chosen over Advanced Search (latter has a JS-validator submit that requires a force-click probe).
- [x] Phase 2.5 — URL resolver pattern locked (2026-06-03): `htmlResourceUrl` template + `pidvalue` substitution → POST → signed `rsch.baml.com/r?q=...`. Validated end-to-end at `test_bofa_resolver.py`.
- [x] Phase 2.6 — PDF fetch identified as SAML autopost (2026-06-03): must use Playwright `page.goto()` for the cross-domain `rsch.baml.com/acs` handshake; subsequent fetches can reuse the session cookie. ANZ-style.
- [x] Phase 2.7 — **PDF endpoint corrected** (2026-06-04): the `htmlResourceUrl` path serves HTML viewer pages (SAML autopost). The symmetric `pdfResourceUrl` resolves to **`research1.ml.com/C?q=<token>&e=<email>&h=<hash>`** which returns `application/pdf` bytes via a single GET — **self-authenticating via HMAC**, no SAML, no cookies required (verified by fetching from a clean unauthenticated context).
- [x] Phase 3 — `crawler_bofa.py` + `fetch_bofa.py` + `filters/bofa.py` + `classifiers/bofa.py` built (2026-06-04). 22 production hubs walked, tile-level 3-stage drop (admin / hub-blanket / series-regex single-name / MBS data-table), URL resolution via `pdfResourceUrl` POST → `research1.ml.com` PDF endpoint.
- [x] Phase 3.5 — 2-hub smoke (economics_overview + credit_em_corporate, 2026-06-04): 27 parsed → 4 dropped (single-name corp) → 22 kept → 100% URL resolution.
- [x] Phase 3.6 — Deep probes A+B+C+D (2026-06-04): confirmed per-tile has no hidden structured signals (no `data-*` attrs), discovered audio/email sibling ResourceUrls, Advanced Search firehose not viable.
- [x] Phase 4 — Filter + classifier wired + registered in `classifiers/__init__.py` + `canonical.VENDOR_DISPLAY`.
- [x] Phase 5 — Orchestrator wired: `bofa` registered in `_load_vendor_registry()`; `pipeline.fetch_pdf` dispatches by URL host (research1.ml.com / rsch.baml.com → `fetch_bofa.fetch_pdf`).
- [x] Phase 6 — Migration `076_seed_bofa_dim_vendor.sql` applied 2026-06-04. First DB-write smoke: 2 reports inserted (ids 3134/3135), 22 chunks, 9 tag rows.
- [ ] Phase 6c — Full-day embed-on smoke + retrieval check.
- [ ] Phase 7 — Promote in `scrapers/index.md` + flip `vendors.yml` to `production`.
- [ ] Phase 8 — Hard-taxonomy probe + tightening (after ≥1 week live).
- [ ] Phase 4 — Discovery filter + classifier.
- [ ] Phase 5 — Wire into orchestrator (`ingest_today.py`).
- [ ] Phase 6 — `dim_vendor` seed migration + first smoke run.
- [ ] Phase 7 — Promote in `scrapers/index.md` table.
- [ ] Phase 8 — Hard taxonomy probe + structured tightening (run *before* extended ingest per the STANC pattern, since user posture is strict on single-name).

## Last verified

2026-06-03 — Phase 0 setup only; no portal interaction yet.
