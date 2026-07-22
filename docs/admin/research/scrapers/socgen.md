# SG Markets (Société Générale) — Research scraper

Pattern: **A (Listing-API firehose) + B (direct-PDF) with one-time
per-session OIDC handshake for the PDF host.** Confirmed Phase 2
2026-06-03.

* Listing: `POST api-z.sgmarkets.com/.../search/do-search-publications`
  with `skip`/`take` pagination and rich facet criteria. Returns
  pre-resolved `category` / `categoryGroup` / `product` / `universe`
  per hit (Tier-0 asset class baked in).
* Per-doc enrichment: `POST .../publications/do-get-publication-extracts/en
  {"pubHeadIds":[...]}` for `thirds[]` (single-name signal),
  `numberOfPages`, `videoProviderId`, `authors`, `keywords`, `sectors`.
* PDF resolution: `GET .../publications/{id}/preview/en?source=Website`
  → `fileUrl` on `doc.sgmarkets.com`. First hit of the fileUrl
  triggers an OIDC dance with `sso.sgmarkets.com/sgconnect`; second
  hit (with the resulting cookie) returns `application/pdf` directly
  from the same URL.

Onboarding started **2026-06-03**. Phase 1 + Phase 2 done; Phase 3
(crawler build) pending sanity-check. See
[`../onboarding_new_vendor.md`](../onboarding_new_vendor.md).

## Portal

| | |
|---|---|
| Hostname | `insight.sgmarkets.com` |
| Sign-in URL | `https://sso.sgmarkets.com/` (SG|Connect OIDC) |
| Username | `dsuri@rvcapital.com` — confirmed at Phase 1 login 2026-06-03 |
| Password | not in `.env`; cookies cached in the persistent profile. `IMDR_RESEARCH_SOCGEN_{URL,USERNAME,PASSWORD}` triplet to be added before any unattended automation. |
| MFA | not enforced on this device — Phase 1 login completed in one shot without an MFA prompt. |

## Profile

```
C:/IMDR_LOCAL/research_profiles/socgen/
```

Fresh persistent Chrome profile (created 2026-06-03). The inherited
`socgen-playwright` folder under
`Z:\Business\Personnel\Arjun\playwrights\` is **contaminated** with 435
unrelated saved logins (chatgpt.com, claude.ai, hotel sites, etc. — see
`vendors.yml` socgen entry) and must not be reused for automation.

## Phase status

| Phase | Status | Notes |
|---|---|---|
| 0 — gate | done | In scope (SG publishes macro/rates/FX/credit research across DM + EM). No creds needed for Phase 1 (interactive login + persistent profile cookies). |
| 1 — explore | done | 7 snapshots in `socgen_explore/`. Hubs / URL patterns / search firehose surfaced. |
| 2 — listing API | done | `do-search-publications` (POST, skip/take) confirmed as primary listing. Request shape + auth + PDF resolution chain mapped. |
| 3 — crawler | done | `ingest/crawler_socgen.py` + `ingest/filters/socgen.py`. Discovery returns 15 clean ReportRefs over a 2-day window. |
| 4 — filter + classifier | done | `ingest/filters/socgen.py` (Bernstein-keep allowlist) + `ingest/classifiers/socgen.py` (Tier-0 `category_group` → canonical asset class + Tier-1 product keyword fallback + region/country heuristics). |
| 5 — orchestrator wiring | done | Registered in `ingest_today.py` `_load_vendor_registry()` and `classifiers/__init__.py`. SG branch added to the in-session fetch path (see Phase 6 finding below). |
| 6 — DB seed + smoke | done | Migration `074_seed_socgen_dim_vendor.sql` applied 2026-06-03. Smoke run (`--vendors socgen --limit 3 --since 2026-06-02 --embed false`): 3/3 inserted, asset_class/region/country/tags all populated correctly. |
| 7 — promote | done | `vendors.yml: socgen.profile_status = production` (2026-06-03). Embed-on smoke + audit + retrieval all clean. Daily-scheduler wiring still pending — leave for the production-cleanup promotion to `src/imdr/`. |
| 8 — hard probe + tightening | done | Brand-based filter (SCB/ATM enum + isCompanyDoc + endDate), referential resolution (authors/keywords), classifier sharpening (Corporate sub-mapping + category-name region scan + universe:X theme leak fix). See "Hard taxonomy probe + tightening" section below. |

## Hubs surfaced in Phase 1

`insight.sgmarkets.com` exposes multiple per-business-line hubs plus a
unified search page. From the 2026-06-03 explore snapshots:

| Hub | URL | Tabs observed |
|---|---|---|
| **Latest reports** | `/page/latestreports` | All Macro / Bernstein / Autonomous / X-Asset & Strategy / Macro Blog / Economics / Quant / Index |
| **Sales & Trading** | `/page/salesandtrading` | Home / Equity / Fixed Income & Currencies / Data & Analytics / ESG by SG (sub-tabs: All / Equity / FIC / Cross Asset / QIS) |
| **FIC Financing** | `/page/ficfinancing` | — |
| **Unified search** | `/search?types=1` | `types=1` = Publications; also `Videos` and `Live news` |
| Likely additional | Overview / AskSGResearch / Macro Blog / Economics / X-Asset & Strategy / Quant, Index & ETF / Sustainability / Bernstein (top nav) | not all snapshotted in Phase 1 |

The unified `/search?types=1` page reported **9999+ results** with no
date floor (`From date = 31 Dec 2000`) — confirmed Phase 2 as a
classic Elasticsearch deep-pagination ceiling on the
`do-search-publications` endpoint.

The hub pages (`/page/{shortName}`) don't fire their own listing
endpoint — they're widget-config blobs (`GET .../pages/{shortName}`
returns layout + parameters). The actual listing data comes from
`POST .../publications/do-get-recent-publications` with a hard-coded
`researchCategoryIds` filter per hub, which is just a filtered slice
of the same firehose. **Conclusion: the unified search is a strict
superset of every hub** — crawl the firehose, ignore the hubs.

### Search faceting

`/search?types=1` exposes faceted filters (all rendered as type-ahead
selects, so values come from the backend):

```
From date / To date / Companies / Universe / Category / Product
Sector / Sub-sector / Tags / Languages / Authors / Region / Country
Types  (Publications | Videos | Live news)
Number of pages (1 to 10 | 10 to 25 | 25 to 50 | 50 or more)
```

Sort: "Latest first" (= `sortBy: "Newest"` in the API).

Phase-2 confirmed every facet has a corresponding `facetCriteria.*`
field in the listing-API request body (`authorIds` / `productIds` /
`categoryIds` / `universeIds` / `tagIds` / `subSectorIds` /
`sectorIds` / `thirdIds` / `countries` / `regions` / `languages` /
`types`). Date/page-count buckets are passed at the top level (not
yet probed — Phase 3 will test if the listing accepts
`fromDate` / `toDate` / `numberOfPagesRange` keys).

## Daily volume

From the Phase-3 crawler smoke on 2026-06-03 against a 2-day window
(`since = today - 2`, `until = today`):

| Stage | Count | Notes |
|---|---:|---|
| Raw in window | ~95 | one search page (`take=200`) returned 200 hits; after date-window filter, ~95 remained |
| `[DROP] restricted` | 8 | `subscriptionRequired=true` (Index Watch series) |
| `[SKIP] product:Bernstein` | 51 | Equity single-name notes; allowlist saved a few cross-asset wraps |
| `[DROP] no_fileUrl` | 21 | HTML-only / web-native pubs — see [Non-PDF assets](#non-pdf-assets) |
| **Net into corpus** | **15** | ~7–8/day kept after Bernstein-keep allowlist |

Composition of the 15 survivors:

| category_group | n | top products |
|---|---:|---|
| Corporate | 4 | Morning Briefing, Special, ABS Europe Trading |
| Emerging | 3 | EM Looking Glass, EM/FX Asia Pulse, EM Trade Idea Monitor |
| Credit | 2 | ABS Europe Trading, Credit Market Wrap Up |
| Economics | 2 | On Our Minds Euro Area, Europe Macro Radar |
| Cross Asset Strategy | 1 | SG Inflation Newsflow Monitor |
| Quant | 1 | ETF Positioning |
| Rates | 1 | FI Special |
| Commodities | 1 | Commodity Compass Analytics |

Zero single-name (`thirds[] == []`) in survivors — the Bernstein
default-drop + thirds-aware downstream policy is working as designed.

**"Corporate" category_group** is undocumented in the Phase-2 enum
sketch but observed cleanly in survivors. It looks like SG's
organizational label for Global Markets / Sales & Trading desk
publications (Morning Briefings, ABS desk comments, ad-hoc "Special"
notes). Treat as a valid macro-flavoured group; the classifier will
need to map it onto canonical asset classes (likely Credit / Rates /
Multi-Asset depending on product).

**Steady-state estimate**: ~7–10 PDFs/day net into corpus,
~40 raw/day before filters. Refresh after first Phase-6 full-day run.

## URL patterns

### Publication detail page

```
https://insight.sgmarkets.com/publication/{pub_id}?lang=en
```

* `{pub_id}` — sequential numeric ID. Observed range in Phase 1
  snapshots: 362038 – 362073 (35 distinct IDs visible across one
  hub view, IDs incremented in chronological order — newer = higher).
* `?lang=en` — locale; SG also publishes in French (`fr`), German
  (`de`), Japanese (`ja`) per language facet. Pin `en` at discovery
  unless we explicitly want translations.

### Document/PDF URL

```
https://doc.sgmarkets.com/en/3/0/{tenant_id}/{pub_head_id}.html?sid={session}
```

* Separate host `doc.sgmarkets.com` (not `insight.sgmarkets.com`).
* `{tenant_id}` — opaque ID (`1109453` observed); account-static, so
  stable across requests for our profile.
* `{pub_head_id}` — same `pubHeadId` as in the listing response.
* `.html` extension — **counter-intuitively, this is the canonical
  PDF endpoint** after the OIDC handshake (see [Fetch strategy](#fetch-strategy-phase-2--confirmed-2026-06-03)
  below). `.pdf` substitute returns 404.
* `sid` — per-fetch session token returned by
  `preview/en.fileUrl` — do not cache; always re-resolve via
  `preview/en` before each fetch.

## Listing API (Phase 2 — confirmed 2026-06-03)

All listing/data calls hit the host `api-z.sgmarkets.com`. Probe
scripts: [`playground/research/probe_listing_apis.py`](../../../playground/research/probe_listing_apis.py),
[`playground/research/probe_socgen_request.py`](../../../playground/research/probe_socgen_request.py),
[`playground/research/probe_socgen_pdf_resolve.py`](../../../playground/research/probe_socgen_pdf_resolve.py),
[`playground/research/probe_socgen_fetch.py`](../../../playground/research/probe_socgen_fetch.py).
Cached probe output under [`playground/research/socgen_explore/`](../../../playground/research/socgen_explore/).

### Primary listing — `do-search-publications`

```
POST https://api-z.sgmarkets.com/services/insight/search/private/v1/api/v1/search/do-search-publications
Authorization: Bearer <oauth2 access_token>
Content-Type: application/json
Origin: https://insight.sgmarkets.com
```

Request body:

```json
{
  "searchInTitleOnly": false,
  "facetCriteria": {
    "authorIds": [],
    "types": ["Report"],
    "languages": [],
    "productIds": [],
    "categoryIds": [],
    "universeIds": [],
    "tagIds": [],
    "subSectorIds": [],
    "sectorIds": [],
    "thirdIds": [],
    "countries": [],
    "regions": []
  },
  "sortBy": "Newest",
  "skip": 0,
  "take": 10,
  "explain": false
}
```

Pagination: `skip` + `take`. Default `take=10`; push higher (200 is
the working baseline elsewhere). Sort `"Newest"` returns descending
publication date — pair with date-window early-stop in the crawler.

Response shape (`hits[]`, one record per pub):

| field | example | use |
|---|---|---|
| `pubHeadId` | `362077` | the canonical publication ID — match `/publication/{id}` |
| `publicationId` | `425765` | internal search-index ID; not used by the SPA URL |
| `title` | `"EV TRACKER - April 2026: ..."` | report title |
| `localizedTitles[].title` | `"EV TRACKER ... (39p)"` | title + page-count suffix |
| `publicationDate` | `"2026-06-02T20:30:08"` | timestamp (no TZ — UTC inferred) |
| **`categoryGroup.name`** | `"Equity"` / `"Macro"` / `"Fixed Income"` | **Tier-0 asset class** |
| `categoryGroup.researchCategoryGroupId` | `5` | numeric enum |
| `category.name` | `"Equity Sector"` / `"Macro Strategy"` | sub-class |
| `category.researchCategoryId` | `6` | numeric enum |
| `categories[]` / `categoryGroups[]` | `[{...}]` | plural arrays — a doc may be tagged into multiple buckets (e.g. a cross-asset note may carry both Macro and Fixed Income). Prefer `categoryGroup` (singular) as the primary Tier-0 and treat plurals as secondary tags. |
| `product.name` | `"Bernstein"` / `"FX G10 Forecasts"` | publication series — Tier-1 |
| `product.id` | `6464` | series ID |
| `universe.name` | `"GRS"` | publishing universe scope |
| `readCount` | `0` | view count (decorative) |

### Per-doc enrichment — `do-get-publication-extracts/en`

```
POST .../publications/do-get-publication-extracts/en
{"pubHeadIds": [362077, 362076, 362075, ...]}
```

Batch endpoint. Returns full per-doc records with fields **not in the
search response**:

| field | use |
|---|---|
| `thirds[]` | **Single-name signal.** Empty `[]` = macro/cross-asset; populated = covers specific companies (`{thirdId, targetPrice, currency, tsr, recommendation}`). Drop single-name per `relevance.py`. |
| `videoProviderId` / `videoIdentifier` | Non-null = video. Drop. |
| `numberOfPages` | Page count. `null` = HTML-only / video / non-paginated — likely drop. |
| `authors[]` | Array of author UUIDs. Resolve via `do-get-authors` referential (cached). |
| `keywords[]` | Array of keyword IDs. Resolve via `do-get-keywords`. |
| `sectors[]` | Array of sector IDs. Resolve via `do-get-sectors`. |
| `summary` | Short text blurb — RAG-friendly tag content. |
| `mifidSubscriptionRequired` / `subscriptionRequired` | Paywall flags. We have access; flags inform `subscriptionMessage` display only. |
| `translations[]` | Translations of this doc into other languages (Fr / Ja). Keep `lang=en` only. |

### Per-doc PDF resolver — `preview/en`

```
GET .../publications/{pubHeadId}/preview/en?source=Website
```

Returns:

```json
{
  "fileUrl": "https://doc.sgmarkets.com/en/3/0/1109453/362070.html?sid=82fd6cb25a095979667ee71d50f4fb24",
  "bernsteinFileUrl": "https://insight.sgmarkets.com/publication/362070?lang=en",
  "contents": [{"content": "<ul><li><p>ETF primary market flows in May ...</p></li>...</ul>"}],
  "readingDuration": null,
  ...
}
```

The `contents[].content` field carries an **HTML body of the report's
key bullets** (executive summary or full article for short pubs).
RAG-friendly even before the PDF is fetched.

### Reference data (fetch once per session, cache)

| Endpoint | Use |
|---|---|
| `POST .../referentials/do-get-products` | Product (publication series) catalog — id → name |
| `POST .../referentials/do-get-sectors` | Sector catalog |
| `POST .../referentials/do-get-thirds` | Companies catalog (596 KB body) — id → ticker/name |
| `POST .../persons/do-get-authors` | Author catalog (596 KB body) — UUID → name |
| `POST .../referentials/do-get-keywords` | Keyword catalog |
| `GET .../referentials/countries` | Country list |
| `GET .../referentials/languages` | Language list |

### Auth

* **`Authorization: Bearer <jwt>`** on every api-z call. The token is
  stored by the SPA at
  `localStorage['SGWTConnectStorage.{guid}.AUTH']` as a JSON blob
  with `access_token` (~1.6 KB). Pull it via
  `page.evaluate("localStorage.getItem(...)")` after priming the
  session.
* The token refreshes silently via an iframe handshake against
  `sso.sgmarkets.com/sgconnect/oauth2`. Token lifetime not measured —
  Phase 6 will time the first expiry; assume re-prime every ~50 min
  until proven longer.
* `Origin: https://insight.sgmarkets.com` is required; api-z is
  configured `same-site` so cookies pass automatically when the
  Origin is on `sgmarkets.com`.
* The token has `sub` = `dsuri@rvcapital.com` (decoded JWT not stored
  in the doc; verify on the wire if account-binding becomes a Phase-6
  question).

### Historical backfill — Elasticsearch `from+size ≤ 10000` ceiling

The `/search?types=1` UI reports **9999+ results** — a classic ES
deep-pagination ceiling. To backfill historical SG research beyond
10K records, two options:

1. **Time-window slice**: paginate with `skip=0..9999` within a date
   window (e.g. month-by-month) using `From date`/`To date` facets.
   No extra API support needed.
2. **`search_after` cursor** (if supported by `do-search-publications`):
   pass the last hit's sort key as a cursor. Phase 3 will test which
   the API accepts.

Daily-incremental crawl stays under the ceiling trivially.

## Frontend stack

Vite-built SPA. Entry point: `<script type="module"
src="/2.89.53.be4298c/assets/index-By8PSfzj.js">` (build hash will
drift). Bootstrap loaders visible:

* `https://sdk.privacy-center.org/3c3fcd53-b757-4124-b50f-51f8f34383da/loader.js` — Didomi consent banner.
* `https://sgwt-cdn-widgets.sgmarkets.com/widgets/sgwt-connect/v4/sgwt-connect.js` — the **`sgwt-connect`** widget owns the OIDC token lifecycle and writes the access_token to `localStorage['SGWTConnectStorage.{guid}.AUTH']`. This is the integration point for any future programmatic auth path.
* `sgwt-account-center`, `sgwt-help-center`, `sgwt-mini-footer`, `sgwt-splash-screen`, `sgwt-web-analytics` — standard SG widget set; irrelevant to ingest.

Post-hydration HTML carries `publication/{id}` references inline in
the rendered card DOM — useful for sanity-checking probe results
against what the SPA actually shows the user.

## Fetch strategy (Phase 2 + 6 — confirmed 2026-06-03)

**Pattern: B (direct-PDF) with a per-Playwright-session OIDC
handshake against `doc.sgmarkets.com`.** Not the slow viewer-redirect-C
pattern that the `.html` extension initially suggested.

**Phase-6 correction (2026-06-03)**: the OIDC handshake cookies on
`doc.sgmarkets.com` (`.AspNetCore.Cookies*`, `TS*`,
`SGX_PRD_authN_sticky_id`) are **session-scoped** and do NOT survive
`ctx.close()`. The crawler's discovery ctx cannot pre-warm the
fetcher's ctx. The orchestrator therefore routes SG (alongside
Barclays) through an in-session `fetch_pdfs` path: same Playwright
ctx does discovery → preview/en resolve → OIDC handshake (one
`page.goto(fileUrl)`) → `ctx.request.get(fileUrl)` for the binary.
See `ingest/crawler_socgen.py::fetch_pdfs`.

The chain we observed (`probe_socgen_fetch.py` + headed network capture):

1. `GET preview/en` → returns `fileUrl =
   doc.sgmarkets.com/en/3/0/{tenant}/{pubHeadId}.html?sid={token}`.
   The tenant ID `1109453` is account-static; the `sid` token rotates
   per request.
2. First `GET fileUrl` from a fresh session → **HTML shell (3051 bytes,
   `text/html`)** — the SG|Connect viewer SPA. It then triggers an
   OIDC dance:
   * `GET sso.sgmarkets.com/sgconnect/oauth2/authorize?client_id=f3b409d3-e7ed-419a-a973-8ef7eaa7a670&redirect_uri=...`
   * `POST doc.sgmarkets.com/signin-oidc` (302)
   * `GET fileUrl` (302) → final `GET fileUrl` (200, **`application/pdf`**).
3. After the OIDC cookie is set on `doc.sgmarkets.com` for the
   session, **every fileUrl returns `application/pdf` directly from
   `ctx.request.get()`** — no SPA, no viewer, no slow redirect chain.

**Implementation in the Phase 3 crawler**: prime the session by
visiting one arbitrary fileUrl in a Playwright page (lets the OIDC
SPA complete the handshake and set the `doc.sgmarkets.com` cookie),
then use `ctx.request.get(file_url)` for every subsequent fetch.
Treat any `Content-Type: text/html` response as "OIDC cookie
expired" and re-prime.

Substituting `.pdf` for `.html` in the URL returns 404 — there is no
direct-PDF shortcut; the `.html` extension is the canonical PDF
endpoint (counter-intuitive but confirmed).

## Watermarks / restrictions

No watermark / DRM headers observed on the api-z responses during
Phase 2. Sample PDF content not yet inspected — pull one PDF during
the Phase-6 smoke and skim for visible-watermark / personalisation
text before declaring this section done.

Per-publication `subscriptionRequired=true` may surface on some
pubs (e.g. Index Watch — observed at pubHeadId 362073). When set,
the api-z layer returns the metadata + summary but the PDF host
will refuse the binary fetch. Treat as an admin-drop (`reason=
restricted`) at the crawler.

## Non-PDF assets

`/search?types=1` enumerates three types in the UI: **Publications**,
**Videos**, **Live news**. The crawler pins
`facetCriteria.types = ["Report"]` to filter Videos and Live news at
the listing API.

Even within `Report`, two additional non-PDF sub-classes exist:

* **`numberOfPages == null`** on the extract — dropped at the crawler
  stage as `no_pages`.
* **`fileUrl == null`** on the `preview/en` resolver — i.e. the
  publication has metadata + an HTML body in `contents[].content` but
  no PDF rendition. Phase-3 smoke (2026-06-03) saw 21 of 36 post-
  filter survivors fall into this bucket. The crawler drops these as
  `no_fileUrl` because the downstream pipeline is PDF-only.

  Worth considering for a future text-only ingest mode (the
  `contents[].content` HTML is RAG-ready). Out of scope for now.

Format distribution will be re-measured during Phase 6 smoke.

## Quirks

* **`.html` extension is the canonical PDF endpoint.** `doc.sgmarkets.com/
  …/{pubHeadId}.html?sid=…` returns `application/pdf` once the
  per-session OIDC cookie is set. The `.pdf` substitute returns 404.
  Future you will Google "SG PDF URL `.html`" — leave a sticky comment
  in the crawler.
* **`sid` token is per-fetch, not per-session.** Always re-resolve
  via `preview/en` immediately before fetching the PDF; do not cache
  fileUrl across docs.
* **Bearer is in localStorage, not cookies.** Other vendors (JPM) use
  custom request headers; SG uses standard `Authorization: Bearer`,
  but the token only exists in `localStorage` — `ctx.cookies()` will
  not expose it. Pull via `page.evaluate("localStorage.getItem(...)")`.
* **Cross-host cookie hop.** `insight.sgmarkets.com` and
  `doc.sgmarkets.com` share the `sgmarkets.com` parent, so the
  persistent profile carries the right cookies to both — but
  `doc.sgmarkets.com` runs its own OIDC handshake on first hit
  (`/signin-oidc`), separate from `api-z.sgmarkets.com`. Plan for
  both sessions to expire independently.
* **9999+ result cap on `do-search-publications`** — Elasticsearch
  `from+size <= 10000` ceiling. Daily incremental clears it
  trivially; backfill needs date-window slicing (deferred per
  Phase-3 posture below).
* **Translations.** A given report can ship in EN + FR + JA;
  `translations[]` on the extract records which other locales exist.
  Crawler pins `language="EN"` via `facetCriteria.languages = ["EN"]`
  (preferred) or post-filters by `publicationExtract.language`.

## Hard taxonomy probe + tightening (2026-06-03)

Phase 8 run on the same day SG went live (atypical — usually we wait
for ≥1 week of production data — but the user explicitly requested it).
Per the playbook §8 pattern, four agents probed in parallel
(current-stack audit, DB audit, hard listing-response probe, Deepak
playwright cross-check), then five edits shipped.

### Probe findings (in `playground/research/taxonomy_probe/`)

* `socgen_full.md` — full enumeration of `do-search-publications.hits[]`
  + `publicationExtracts[]` + `preview/en` response keys. Identified
  five high-value unmapped signals:
  - `products[productId].brand` — "SG" / "SCB" (Bernstein) / "ATM"
    (Autonomous) enum, cleaner than the legacy product-name string
    match.
  - `products[productId].isCompanyDoc` (bool) — vendor-native per-
    product single-name flag.
  - `products[productId].endDate` — non-null = discontinued series.
  - `keywords[]` resolved via `do-get-keywords` — flat `{id, name}`
    catalog (~500 entries: country names, ISO currency codes, themes).
  - `authors[]` resolved via `do-get-authors` — UUID → display name.
* `socgen_db_audit.md` — 5-row sanity audit. Clean (no encoding /
  duplicates / non-canonical asset_class). One micro-leak: row 2379
  has a `theme = "universe:Sales and Trading"` tag from the Phase-4
  classifier that the new classifier rewrites as a clean
  `Tag('universe', 'Sales and Trading')`. With 1 leaked row, no
  cleanup DELETE bucket is justified; future ingests will not
  reproduce it.
* `socgen_deepak.md` — read-only inventory of Deepak's legacy
  contaminated playwright profile (`Z:\…\playwrights\socgen-playwright`).
  Top hosts: `doc.sgmarkets.com` (166), `sso.sgmarkets.com` (106),
  `insight.sgmarkets.com` (17). He bypassed the portal entirely
  (direct PDF retrieval), so no new hubs / URL patterns surfaced.
  Validates that our crawler's `insight.sgmarkets.com` discovery model
  is comprehensive vs his asymmetric usage.

### Critical request-shape correction

Phase-2 cached responses suggested `do-get-products`, `do-get-keywords`,
and `do-get-authors` were bulk catalog dumps. They are **not** — the
SPA captures show they require `{"productIds": […]}` /
`{"keywordIds": […]}` / `{"icIds": […]}` request bodies; an empty
body returns HTTP 400. Phase-8 crawler collects IDs from `hits[]`
and `extracts[]`, then batch-resolves in parallel (chunks of 100).

### Five edits shipped

| Step | File | Change |
|---|---|---|
| A — crawler | `ingest/crawler_socgen.py` | Added `_resolve_products` / `_resolve_keywords` / `_resolve_authors` helpers + `_ProductMeta` cache. New ReportRef fields: `product_brand`, `product_is_company_doc`, `product_end_date`, `authors` (resolved display names), `keyword_names`. Discovery flow reordered: collect IDs from hits/extracts → batch-resolve referentials → run filter. Renamed `author_names` → `authors` so the orchestrator's `_normalize_authors` picks it up for `dim_report.authors`. |
| B — filter | `ingest/filters/socgen.py` | New drop reasons (precedence order, first-match wins): `product:translation` → `title:non-latin-script` → `product:retired` (endDate non-null) → `product:isCompanyDoc` → `product-brand:SCB` / `product-brand:ATM` (with `_SG_EQUITY_KEEP` allowlist) → `product:Bernstein` legacy name-match (defence-in-depth). The brand-based drop generalises the Bernstein-keep allowlist to both equity-acquisition brands (SCB + ATM). |
| C — classifier | `ingest/classifiers/socgen.py` | (1) "Corporate" `category_group` now disambiguates via product name keywords (Credit / FX / Rates → matching canonical, else STRATEGY) instead of blanket STRATEGY. (2) Region scan now includes `category.name` blob (e.g. "Europe Macro Radar" → emea even when title is neutral). (3) Replaced opaque `socgen:{uuid}` author tags with resolved `Tag('author', "First Last")`. Fall-back to opaque form only when referential didn't resolve. (4) Emit resolved keywords as `Tag('theme', name)` (capped at 8 per doc). (5) Fixed `universe:X` theme leak — emits `Tag('universe', name)` in its own category instead of stuffing into the global theme namespace. |
| D — cleanup | n/a | Skipped. 5-row DB sample has one micro-leak (the `universe:Sales and Trading` theme on row 2379). With only 1 leaked row + future-ingest immunity, a DELETE bucket is overkill. Documented for visibility. |
| E — smoke | `playground/research/smoke_socgen_7day.py` | Mirror of `smoke_anz_7day.py` / `smoke_bnp_7day.py`. Tracks per-day discovered/kept, referential field coverage, drop reason breakdown, kept asset_class/region/country distribution, sample titles per class. |

### 7-day smoke result (2026-05-27 → 2026-06-02)

Probe ([`smoke_7day_v2.log`](../../../playground/research/socgen_explore/smoke_7day_v2.log)):

```
Per-day discovered (after crawler-level drops):
  2026-05-27   7    2026-05-28   7    2026-05-29   8
  2026-06-01   7    2026-06-02   8                       ~7-8/day

Crawler-stage drops:
  product-brand:SCB:    196   Bernstein single-name + sector wraps (1 cross-asset wrap survived)
  product-brand:ATM:     53   Autonomous (financials boutique)
  restricted:            20   subscriptionRequired Index Watch series
  no_fileUrl:            11   HTML-only / web-native pubs
  product:translation:    2   Japanese Translation - Rates & FX

Referential coverage:
  products=39/39   keywords=20/20   authors=154/154   (100% / 100% / 100%)
  product_brand resolved on 37/37 survivors (100%)
  authors resolved on 37/37 (100%)
  keyword_names resolved on 17/37 (46%)   [not every doc has keywords assigned]

Relevance filter (post-discovery): 37 kept, 0 dropped (100% kept — single-name
already drops upstream via filter, so relevance.py doesn't fire)

Kept composition:
  MACRO 14 (38%)   STRATEGY 12 (32%)   CREDIT 4   RATES 3   FX 3   COMMODITIES 1
  zero EQUITY survivors — Bernstein/ATM brand drops doing their job

Geography:
  Region: global 30, emea 5, apac 2  (81% non-default region)
  Country: EU 4, CO 1, IN 1, CN 1  (19% with country anchor)
```

### Acceptance gates ([playbook §8.5](../onboarding_new_vendor.md#phase-85--run-the-7-day-smoke))

* ✅ Hub coverage — N/A; we crawl the unified firehose.
* ✅ Discovery drop reasons — counts plausible; brand-based drops dominate as expected. Spot-checks of the 5 sample titles per reason show clean classification.
* ✅ Relevance kept ratio 100% (≥90% target).
* ✅ Asset-class composition macro/strategy-dominated, zero EQUITY survivors.
* ✅ Region coverage 81% (≥60% target). Country coverage 19% — acceptable given SG doesn't expose per-doc country in the listing response; the title/category heuristic is the only path.

### Phase 8 anti-patterns observed + avoided

* Empty-body referential probe returned 400 (caught in v1 smoke; fixed before commit).
* `_TRANSLATION_PRODUCT_RE` is broad on purpose — no false positives observed across the 7-day window (only the two Japanese Translation rows matched, both correctly).

---

## Phase 3 posture (agreed 2026-06-03)

Decided before crawler build, to be revisited after first 7-day smoke:

* **Single-name drop policy — vendor-specific Bernstein-keep allowlist
  (Goldman-style).** Default-drop any hit with `product.name ==
  "Bernstein"` (SG's acquired equity-research arm; high volume,
  almost all single-name). Other equity hits drop when `thirds[]` is
  non-empty **unless** the title matches a `_SG_EQUITY_KEEP` regex
  (`strategy|portfolio|cross-asset|allocation|outlook|thematic|
  positioning|earnings season|global research`). Modelled on the
  Goldman tightening pattern (`_GS_EQUITY_KEEP` in
  [`playground/research/ingest/relevance.py`](../../../playground/research/ingest/relevance.py)).
  Tune empirically once Phase 6 smoke shows the actual `product.name`
  distribution.
* **Historical backfill — deferred.** Phase 3 crawler ingests
  yesterday + today only (`since = today - 1 day`). A separate
  one-off `backfill_socgen.py` later will wrap the same crawler with
  widening date windows to dodge the ES `from+size ≤ 10000` ceiling.

## Last verified

2026-06-03 — **Phases 0 → 8 done.** Final state:

* Embed-off smoke ([`smoke_orchestrator_v2.log`](../../../playground/research/socgen_explore/smoke_orchestrator_v2.log)) — 3/3 inserted (`dim_report.id` 2379-2381), asset_class / region / country / tags all populated correctly, 36 chunks landed in `research.fact_chunk`.
* Embed-on smoke ([`smoke_orchestrator_embed_v1.log`](../../../playground/research/socgen_explore/smoke_orchestrator_embed_v1.log)) — 2 new IDs (2382 EM Looking Glass, 2383 ETF Market Pulse), 24 Qdrant points (`gemini-embedding-2`).
* Audit ([`audit_v1.log`](../../../playground/research/socgen_explore/audit_v1.log)) — 17/17 survivors over 3-day window have a valid asset_class; 0 audio/podcast/reminder leakage; 0 single-name leakage. **Japanese-translation leak fixed** by the Phase-8 `product:translation` + `title:non-latin-script` filter (see Hard Taxonomy Probe section).
* Retrieval ([`retrieval_v1.log`](../../../playground/research/socgen_explore/retrieval_v1.log)) — 4/5 queries returned SG citations; 5th hit a pre-existing `retrieve.py` cp1252 encoding bug while printing a Unicode glyph, not a SG retrieval failure.
* **Phase 8 — 7-day smoke** ([`smoke_7day_v2.log`](../../../playground/research/socgen_explore/smoke_7day_v2.log)) — 37 net survivors across 2026-05-27 → 2026-06-02 (~7-8/day), referential coverage 100% products / 100% authors / 46% keywords, brand-based filter killing 196 SCB + 53 ATM + 2 translation + 20 restricted + 11 no_fileUrl, asset_class composition 38% MACRO / 32% STRATEGY / rest CREDIT+RATES+FX+COMMODITIES, 81% non-default region.

**Daily-scheduler wiring not yet done** — playbook §7.5 says leave the
scheduler hook for the promotion-to-`src/imdr/` cleanup. SG runs via
`python -m playground.research.ingest_today --vendors socgen` on
demand for now.

## Noise filter update (2026-06-10)

Shared cross-vendor noise classifier wired into
[`ingest/filters/_noise.py::classify_noise`](../../../../playground/research/ingest/filters/_noise.py)
and called as the final fallback inside [`filters/socgen.py::should_exclude`](../../../../playground/research/ingest/filters/socgen.py).
Three universal title-pattern families plus a cross-vendor EQUITY
conference / sales-event drop in [`relevance._is_equity_conf_event`](../../../../playground/research/ingest/relevance.py).

Smoke against the full 4,498-title `research.dim_report` corpus dropped
**3 socgen docs**:

| family | n | sample |
|---|---|---|
| chart-pack | 2 | Korean Treasury Bonds – NSS Rich/cheap; ROMGB Chart Pack - June 2026 |
| morning-note | 0 | (none) |
| event-admin | 1 | Client Web Conference Invitation – Fed Digest & Market Implications -18-Jun-2026 |
| conf-event (EQUITY only) | 0 | (none — SocGen Bernstein/SCB/ATM brand filter already catches single-name equity) |

The conf-event rule fires only when `result.asset_class == EQUITY` so
MACRO-tagged "Takeaways" / "Trip Notes" titles (real policy / sovereign
macro content) pass through unaffected.

Test pins: [`test_noise_filter.py`](../../../../playground/research/test_noise_filter.py)
(116 chart-pack / morning-note / event-admin assertions),
[`test_relevance_conf_event.py`](../../../../playground/research/test_relevance_conf_event.py)
(35 conf-event assertions). Re-runnable smoke harnesses:
[`_smoke_noise_filter.py`](../../../../playground/research/_smoke_noise_filter.py),
[`_smoke_conf_event.py`](../../../../playground/research/_smoke_conf_event.py).

