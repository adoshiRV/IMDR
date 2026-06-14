# Research scrapers — vendor inventory

Last updated: 2026-06-15

Per-vendor scraper documentation. One markdown file per vendor capturing
the portal's authentication flow, URL patterns, DOM structure, fetch
strategy, and known quirks.

## Cross-cutting content quality (2026-06-15)

A pipeline-wide content-quality programme shipped 2026-06-15. Two
mechanisms work together — see
[`../content_quality.md`](../content_quality.md) for the full spec:

1. **Prose-density gate** (`ingest/prose_density.py`, wired in
   `ingest/pipeline.py` after parse) — skips any PDF whose extracted
   text is mostly numbers + disclaimer. Rule: `digit_frac >= 0.20 OR
   (prose_sentences <= 3 AND digit_frac >= 0.15)`. Calibrated at
   66/138 BOILERPLATE dropped, 0/49 RICH lost. Controlled by
   `Settings.research_prose_gate_enabled` (env
   `IMDR_RESEARCH_PROSE_GATE_ENABLED`, default ON).

2. **Per-vendor title drop-lists** — for image-chart-only docs whose
   extracted text is low-digit but near-empty prose (the gate misses
   them): explicit series-name lists in `filters/goldman.py`,
   `filters/barclays.py`, `filters/ms.py`, `filters/nomura.py`,
   `filters/citi.py`. DB uses `EXCLUDED_PRODUCT_TYPES = {"Charts"}`.

A deduplication fix also shipped: `pipeline.py` now gates on
`(vendor_code, pdf_path)` before fetch (previously only content-hash
was checked, defeated by per-download watermarks). Cleanup via
`cleanup_research_dupes.py` removed 471 surplus rows / ~11.7k surplus
chunks across 13 vendors.

## Add a new vendor

Quick reference — for the long-form end-to-end playbook (phase 0
gating, phase 2 listing-API discovery, phase 6 smoke runs, etc.) see
[`../onboarding_new_vendor.md`](../onboarding_new_vendor.md).

1. **Add a 10-line explorer wrapper** at
   `playground/research/explore_<vendor>.py`. Calls
   `portal_explorer.explore(vendor_code, portal_url)`.
2. **Run it interactively**, log into the portal, capture 5–10 snapshots
   of: post-login landing, listing/feed page, an actual report, search
   results.
3. **Inspect the snapshots** (`playground/research/<vendor>_explore/`) to
   identify the URL/DOM pattern.
4. **Build the per-vendor crawler** at
   `playground/research/ingest/crawler_<vendor>.py`. Returns
   ``list[ReportRef]`` (uuid + title + publish_date + pdf_url).
5. **Build the runner** at
   `playground/research/ingest_today_<vendor>.py`. Wraps the crawler
   and drives the pipeline.
6. **Document everything** — create
   `docs/admin/research/scrapers/<vendor>.md` from the template fields
   shown in the existing per-vendor docs.
7. **Seed the dim_vendor row** if needed:
   ```python
   INSERT INTO dbo.dim_vendor
       (vendor_code, display_name, vendor_type, is_active, ...)
       VALUES ('<vendor>', '<Display Name>', 'web', 1, ...);
   ```

## Vendors

| Code | Portal | Pattern | Auth realm | Status |
|---|---|---|---|---|
| `goldman` | marquee.gs.com | API `/research/search/reports/advanced-search` (POST, paginated, sort=time desc); 3 content paths ingested (Stage 1, 2026-06-12) — `/content/research/en/reports/` direct PDF + `/content/markets/en/...` HTML→PDF render (FICC desk, MarketStrats, GS MORNING) + `/content/research/en/blogs/` HTML→PDF render (US Econ Weekly, FX Wrap Up); models + insights still skipped; `_CHART_ONLY_TITLE_PREFIXES` added 2026-06-15 (GS Rates MarketStrats, Commodity Futures chart packs, CLO Secondary, etc.) | — | live, ~395/day ([details](goldman.md)) |
| `anz` | research.anz.com | API `/document_data_tiled_all` (HTML-in-JSON tiles, paginated) + viewer redirect-chain to S3 | — | live, ~20/day ([details](anz.md)) |
| `nomura` | www.nomuranow.com/research/ | API `/research/japi/pub/search/query` (Elasticsearch DSL, paginated) → deterministic `.file` URL; `_CHART_ONLY_TITLE_PREFIXES` added 2026-06-15 (USD/CNY Fix Model, G10 FX Month-End Model, FX and Rates Portfolio Update, Credit/Macro Portfolio Update); high-digit counterparts (Yen RV Analytics, Yen Rates Daily Monitor, etc.) caught by prose-density gate | — | live, ~100/day ([details](nomura.md)) |
| `jpm` | markets.jpmorgan.com | `POST /research/controller/graphql/query-v2` (GraphQL `operationName=research`, facets DSL in `researchQueryNodeChildren`, paginated by `start`+`pageSize`); deterministic PDF at `/research/PubServlet?action=open&doc={id}.pdf`. Custom `janus_user` header required. | — | live, ~150-220/day raw (~12% Daily Packages tagged) ([details](jpm.md)) |
| `ms` | ny.matrix.ms.com/eqr/research/portal/home/global | API `/portal-content-service/search` (POST, paginated, sort=d) → frontmatter JSON → PDF; `_CHART_ONLY_TITLE_PREFIXES` added 2026-06-15 (Strait of Hormuz Tracker, Key Data Watch Calendar, Factor Effectiveness, Key Forecasts) | — | live, ~500/day ([details](ms.md)) |
| `hsbc` | www.research.hsbc.com | Server-rendered HTML; `/Reach` landing page parsed; pagination via `rcRedisplayReportsTab` JS; `/R/10/{shortId}` is direct PDF | — | live, ~30 rows/page ([details](hsbc.md)) |
| `barclays` | live.barcap.com | Programmatic login (no MFA on trusted device); fresh profile per run; `page.evaluate(fetch())` for all API calls; `responseDetailLevel=FULL` to ship `eqSecurities` + `restrictions` + full `tags[]`; language allowlist (`eng` only) + asset-class allowlist + single-name drop at discovery; `_CHART_ONLY_TITLE_SUBSTRINGS` + QPS Presentation drop added 2026-06-15 | `rv-pingfed` | live, ~200/day raw → ~135/day kept ([details](barclays.md)) |
| `bnp` | markets360.bnpparibas.com | Pattern A — `PUT /contentportal/research-service/v1.1/research_documents` returns `documentLink` (JWS slink, directly fetchable as PDF). ~21/day discovered; ~12/day net after chart-pack drop ([details](bnp.md)) | — | live, ~12/day net |
| `ubs` | neo.ubs.com | Pattern A — `POST /api/search/v2/research-stream-advanced` (paginated via `_links.next` offset cursor) fired through `page.evaluate(fetch)` with `x-csrf-token` + `x-{,original-}client-component-id` headers; deterministic PDF at `/api/super-grid-provider-research/v1/document/{wireId}.pdf` (plain `ctx.request.get`). Headed Chrome required (HeadlessChrome UA rejected); programmatic login (no MFA), sessions persist across `ctx.close()` once `#rememberMe1fa` opt-out is left unchecked. | — | live, ~40/day raw → ~25/day net ([details](ubs.md)) |
| `socgen` | insight.sgmarkets.com | API `do-search-publications` (POST, skip/take, Bearer auth) on `api-z.sgmarkets.com`; PDFs via `preview/en` → `doc.sgmarkets.com/*.html?sid=…` with per-Playwright-session OIDC handshake (in-session `fetch_pdfs` like Barclays) | — | live, ~7-8/day net ([details](socgen.md)) |
| `bofa` | markets.ml.com | Liferay HTML scrape across 22 hubs + portlet `pdfResourceUrl` resolver POST → direct PDF on `research1.ml.com/C?q=<token>&e=<email>&h=<hash>` (HMAC self-auth). Programmatic login (PingFederate, like Barclays). | `rv-pingfed` | **PROD-HOLD** — code built, 2 reports in DB; orchestrator wiring removed pending Phase 8 ([details](bofa.md)) |
| `cacib` | research.ca-cib.com | TBD | — | not yet built |
| `citi` | www.citivelocity.com | Pattern A + B — `POST /cvr/publicationqueryws/eppublic/V1/publications.json?platformId=79` with `callerId: CVR` header; ISO-8601 `startDate`/`endDate` body; **omit `sortBy`** (backend has no string index on PublicationDate). Deterministic PDF at `/rendition/eppublic/uiservices/print?doc_id={pubId}&type=print&isJP=false`. Phase 8 tightening: `companies[].refType=PRI` + `isSubject=Y` is the canonical single-name signal (overrides productFocus); `_CITI_EQUITY_KEEP` allowlist + generic `n_tickers==1` check; sectors[] emitted as industry tags. ~70/day raw → ~18/day net (7-day smoke 5/5 gates pass: 98% macro-family, 2% EQUITY, 1% single-name leakage). | — | live through Phase 8 (2026-06-06; daily wiring pending) ([details](citi.md)) |
| `stanc` | research.sc.com | Pattern A — `POST /research/api/common/global/search/newSearch` (Lucene `filterExpression`, sort `payload.publishedDateTime` desc, `resultSetLimit=500`); deterministic PDF at `/protected/rp/api/data/render/{reportId}`; session-cookie auth | — | live, ~4/day net ([details](stanc.md)) |
| `westpac` | www.westpaciq.com.au | Pattern D (new) — AEM hub HTML with inline per-card JSON; PDF lifted from card `executiveSummary` (`/content/dam/.../*.pdf`), fall back to detail-page regex for Economics stubs | — | live, ~15/day net ([details](westpac.md)) |

## Common patterns

Three approaches across the live vendors:

### A. Listing-API firehose (preferred — exhaustive)

The cleanest pattern: each portal's SPA backs its listing UI with a
JSON API that supports a high page-size + date sort. Hit the API
directly with the persistent profile cookies, paginate, early-stop
once oldest-in-page < since.

| Vendor | Listing API | Page size | Daily volume |
|---|---|---|---|
| goldman | `POST /research/search/reports/advanced-search` body `{facets:"()", language:"[\"en\"]", page, size, sort:"time", limitTo:"[\"\"]"}`. **NB**: `language=["en"]` is UI locale not doc content — Japanese-language Tokyo editions still surface; filter at title-level via `_HAS_CJK` regex. Three path prefixes routed to two render modes (Stage 1, 2026-06-12): `/content/research/en/reports/` → direct PDF GET; `/content/markets/en/...` + `/content/research/en/blogs/` → playwright `page.pdf()` via `fetch_html_as_pdf` | 200 (tested up to 500) | ~1000 |
| ms | `POST /portal-content-service/search` body `{compositeRequest:{search:"(text==*)", sort:"d", size, page}, arRequest:{...}}` | 500 | ~500 |
| nomura | `POST /research/japi/pub/search/query` Elasticsearch DSL with `range.publicationDate.gte` filter | 1000 | ~100 |
| barclays | `GET /RSX/content-archive/v1/REST/publication/search` (page-context fetch only — needs SPA origin) — `responseDetailLevel=FULL` ships `eqSecurities`, `eqIndustries`, `restrictions`, full `tags[]` | 200 | ~200 raw → ~135 kept |
| bnp | `PUT /contentportal/research-service/v1.1/research_documents` body `{domain:"RESEARCH", languages:["English"], startDate:"now-Nd/d", startIdx, numOfEntries}` | 200 (UI default 48) | ~21 (~12 net after chart-pack drop) |
| anz | `GET /document_data_tiled_all?param_limit=200&position=N` | 200 | ~20 |
| jpm | `POST /research/controller/graphql/query-v2` (`operationName=research`, facets DSL `researchQueryNodeChildren`, `sortOrder=PUBLICATION_DATE DESCENDING`); custom `janus_user` header threaded from `IMDR_RESEARCH_JPM_USERNAME` | 100 (tested; UI uses 25) | ~150-220 raw |
| stanc | `POST /research/api/common/global/search/newSearch` body `{expression:"*", filterExpression:"<Lucene>", resultSetLimit, sortBy:[{fieldName:"payload.publishedDateTime", direction:"Desc"}], includePayload:true, dapPolicy:"NextGen"}` — payload exposes `assetClassCodes[]`, `regionCountryIds[]`, `materialMentioned[].researchObjectCode` (Phase-8 signals all in v1) | 500 (tested up to 1000) | ~4/day net |
| ubs | `POST /api/search/v2/research-stream-advanced?q=*&limit=N&offset=N` body `{}` — fired via `page.evaluate(fetch)` (direct `ctx.request.post` returns SPA HTML shell). Requires `x-csrf-token` (24h JWT sniffed from SPA's own first XHR during `/neo-research-document-search-page` warmup) + `x-client-component-id: FedPCC_pcc-client-stream-panel` + `x-original-client-component-id` (same value). Response per-doc carries `wireId`, `businessAreaCode` (Tier-0), `productCode`, `pubDate`, multi-value `region`/`country`, `ric`/`cdtRic` (single-name signal), `subjectCode`, `filesize`. Pagination via `_links.next.href`. Total archive 905K. | 100 (default; max untested) | ~40/day raw → ~25/day net |
| citi | `POST /cvr/publicationqueryws/eppublic/V1/publications.json?platformId=79` body `{startDate, endDate, pageStart, pageSize, sortDirection:"DESC", outputFormats:["PDF"], extendOutputFields:["TemplateCode","Link","EventDetails"]}`. Requires `callerId: CVR` header (else `401 CALLER_NOT_AUTHORIZED`). **Omit `sortBy`** — backend has no string range index on `PublicationDate` (`XDMP-ELEMRIDXNOTFOUND`); default sort is DESC by publishDate. ISO-8601 `yyyy-MM-dd'T'HH:mm:ss.SSS'Z'` required for dates. Response per-doc carries `pubId` (PDF anchor), `productFocus` (COMPANY/MULTICOMPANY/INDUSTRY/DISCIPLINE/OTHER — single-name signal), `productType`, `templateName`, `subjects[]` (49-value subject enum), `countries[]`/`regions[]` (Citi `B{NNNN}` IDs), `authors[]`, `restrictionLevel`. PDF at deterministic `/rendition/eppublic/uiservices/print?doc_id={pubId}&type=print&isJP=false`. | 500 (server-side cap) | ~200/day raw → ~25/day net |

Goldman, MS, Nomura and BNP responses include enough metadata (id +
title + date + authors + classification) that we can build ReportRefs
without a second per-uuid call. MS additionally hits a
`/frontmatter?uuid=...` API to get ``pdfRenditionUrl``; everywhere
else the PDF URL is deterministic from the listing record (BNP
returns the fetchable slink directly as ``documentLink``).

**BNP's session bootstrap quirk**: the listing API and the
``/evo/slink/...`` PDF endpoint both require per-user auth tokens
that the SPA mints client-side. Crawlers must ``page.goto(portal_url)``
once before the first API call — without that, the listing PUT hangs
and the slink GET returns non-PDF. See
[scrapers/bnp.md](bnp.md#listing-api-confirmed-2026-05-26).

Discovered systematically via [`probe_listing_apis.py`](../../../../playground/research/probe_listing_apis.py)
which sniffs every JSON XHR fired by each vendor's hub page and
scores responses for "looks like a listing" (UUID counts, listing-key
field names, body size). When adding a new vendor, run the probe
first — it's almost always the highest-scoring API call that's the
right target.

### B. Direct PDF (Goldman, Nomura, MS download steps)

Once the listing yields a UUID, the PDF URL is either deterministic
(Goldman: ``.html → .pdf`` path swap; Nomura:
``go.nomuranow.com/research/japi/publication/{id}.file``) or one
extra GET (MS: frontmatter API returns ``pdfRenditionUrl``). Fetch
goes through ``fetch.py``'s direct path — single ``ctx.request.get()``
returns ``%PDF-...`` bytes.

### C. Viewer redirect chain (ANZ-only)

ANZ's `/file/...?docRef=...` URL returns HTML that JS-redirects to a
signed cloudfront viewer with the S3 URL in a query parameter.
``fetch.py``'s slow path navigates the URL, reads the redirect, pulls
the signed PDF URL from ``?src=<encoded>``, and fetches it. Single
extra Playwright session per fetch.

Both patterns share `fetch.py` — direct is the fast path; if the
response isn't ``%PDF-...`` we fall through to the redirect-chain.

### D. HTML render via `page.pdf()` (Goldman markets/ + blogs/, 2026-06-12)

When the vendor publishes research as a server-rendered SPA article
rather than a downloadable PDF, the crawler tags the `ReportRef` with
`render_mode="html"` and the pipeline routes to `fetch_html_as_pdf`
in [`ingest/fetch.py`](../../../playground/research/ingest/fetch.py):
playwright opens the `.html` URL, smart-waits on
`document.body.innerText.length` until stable (max 25 s), scrolls
bottom→top to force lazy-loaded sections, re-polls body length after
the scroll, and snapshots `page.pdf()` bytes. The bytes feed the same
chunk → embed → DB pipeline as any other vendor PDF.

Currently consumed by Goldman for `/content/markets/en/...` (FICC desk
content — MarketStrats family, FXpresso Daily, GS MORNING desk
roundups, regional dailies) and `/content/research/en/blogs/` (US
Economics Weekly Update, Weekly FX Wrap Up, The Euro into the ECB).
This expanded GS coverage by 54% over the legacy single-prefix gate.

Two retry guards:
* **Post-scroll body collapse** — if scroll dropped body length below
  3 k chars, render is retried once in a fresh page (Marquee SPA
  flakiness producing 770-char "shell-only" PDFs).
* **PDF 401 auth flap** — for vendors using direct PDF GETs (pattern B),
  HTTP 401 triggers one context re-launch which re-reads SSO cookies
  from the profile dir on disk before declaring the session expired.

The dispatch is on `meta.render_mode` in `pipeline.ingest_one`; other
vendors keep the default `"pdf"` path. To extend to a new vendor,
augment the crawler's `_derive_fetch_target()`-equivalent to return
`render_mode="html"` for the appropriate path prefixes and ensure the
ReportMeta carries the field through.
