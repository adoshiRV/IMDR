# Research scrapers — vendor inventory

Per-vendor scraper documentation. One markdown file per vendor capturing
the portal's authentication flow, URL patterns, DOM structure, fetch
strategy, and known quirks.

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

| Code | Portal | Pattern | Status |
|---|---|---|---|
| `goldman` | marquee.gs.com | API `/research/search/reports/advanced-search` (POST, paginated, sort=time desc); `path` filtered to `/content/research/en/reports/` (PDF-bearing) | live, ~330 PDFs/day ([details](goldman.md)) |
| `anz` | research.anz.com | API `/document_data_tiled_all` (HTML-in-JSON tiles, paginated) + viewer redirect-chain to S3 | live, ~20/day ([details](anz.md)) |
| `nomura` | www.nomuranow.com/research/ | API `/research/japi/pub/search/query` (Elasticsearch DSL, paginated) → deterministic `.file` URL | live, ~100/day ([details](nomura.md)) |
| `jpm` | markets.jpmorgan.com | `POST /research/controller/graphql/query-v2` (GraphQL `operationName=research`, facets DSL in `researchQueryNodeChildren`, paginated by `start`+`pageSize`); deterministic PDF at `/research/PubServlet?action=open&doc={id}.pdf`. Custom `janus_user` header required. | live, ~150-220/day raw (~12% Daily Packages tagged) ([details](jpm.md)) |
| `ms` | ny.matrix.ms.com/eqr/research/portal/home/global | API `/portal-content-service/search` (POST, paginated, sort=d) → frontmatter JSON → PDF | live, ~500/day ([details](ms.md)) |
| `hsbc` | www.research.hsbc.com | Server-rendered HTML; `/Reach` landing page parsed; pagination via `rcRedisplayReportsTab` JS; `/R/10/{shortId}` is direct PDF | live, ~30 rows/page ([details](hsbc.md)) |
| `barclays` | live.barcap.com | Programmatic login (no MFA on trusted device); fresh profile per run; `page.evaluate(fetch())` for all API calls; `responseDetailLevel=FULL` to ship `eqSecurities` + `restrictions` + full `tags[]`; language allowlist (`eng` only) + asset-class allowlist + single-name drop at discovery | live, ~200/day raw → ~135/day kept ([details](barclays.md)) |
| `bnp` | markets360.bnpparibas.com | Pattern A — `PUT /contentportal/research-service/v1.1/research_documents` returns `documentLink` (JWS slink, directly fetchable as PDF). ~21/day discovered; ~12/day net after chart-pack drop ([details](bnp.md)) | live, ~12/day net |
| `ubs` | neo.ubs.com | TBD | not yet built |
| `socgen` | insight.sgmarkets.com | API `do-search-publications` (POST, skip/take, Bearer auth) on `api-z.sgmarkets.com`; PDFs via `preview/en` → `doc.sgmarkets.com/*.html?sid=…` with per-Playwright-session OIDC handshake (in-session `fetch_pdfs` like Barclays) | live, ~7-8/day net ([details](socgen.md)) |
| `bofa` | markets.ml.com | Liferay HTML scrape across 22 hubs + portlet `pdfResourceUrl` resolver POST → direct PDF on `research1.ml.com/C?q=<token>&e=<email>&h=<hash>` (HMAC self-auth). Programmatic login (PingFederate, like Barclays). | **PROD-HOLD** — code built, 2 reports in DB; orchestrator wiring removed pending Phase 8 ([details](bofa.md)) |
| `cacib` | research.ca-cib.com | TBD | not yet built |
| `stanc` | research.sc.com | Pattern A — `POST /research/api/common/global/search/newSearch` (Lucene `filterExpression`, sort `payload.publishedDateTime` desc, `resultSetLimit=500`); deterministic PDF at `/protected/rp/api/data/render/{reportId}`; session-cookie auth | live, ~4/day net ([details](stanc.md)) |
| `westpac` | www.westpaciq.com.au | Pattern D (new) — AEM hub HTML with inline per-card JSON; PDF lifted from card `executiveSummary` (`/content/dam/.../*.pdf`), fall back to detail-page regex for Economics stubs | live, ~15/day net ([details](westpac.md)) |

## Common patterns

Three approaches across the live vendors:

### A. Listing-API firehose (preferred — exhaustive)

The cleanest pattern: each portal's SPA backs its listing UI with a
JSON API that supports a high page-size + date sort. Hit the API
directly with the persistent profile cookies, paginate, early-stop
once oldest-in-page < since.

| Vendor | Listing API | Page size | Daily volume |
|---|---|---|---|
| goldman | `POST /research/search/reports/advanced-search` body `{facets:"()", language:"[\"en\"]", page, size, sort:"time", limitTo:"[\"\"]"}` | 200 (tested up to 500) | ~1000 |
| ms | `POST /portal-content-service/search` body `{compositeRequest:{search:"(text==*)", sort:"d", size, page}, arRequest:{...}}` | 500 | ~500 |
| nomura | `POST /research/japi/pub/search/query` Elasticsearch DSL with `range.publicationDate.gte` filter | 1000 | ~100 |
| barclays | `GET /RSX/content-archive/v1/REST/publication/search` (page-context fetch only — needs SPA origin) — `responseDetailLevel=FULL` ships `eqSecurities`, `eqIndustries`, `restrictions`, full `tags[]` | 200 | ~200 raw → ~135 kept |
| bnp | `PUT /contentportal/research-service/v1.1/research_documents` body `{domain:"RESEARCH", languages:["English"], startDate:"now-Nd/d", startIdx, numOfEntries}` | 200 (UI default 48) | ~21 (~12 net after chart-pack drop) |
| anz | `GET /document_data_tiled_all?param_limit=200&position=N` | 200 | ~20 |
| jpm | `POST /research/controller/graphql/query-v2` (`operationName=research`, facets DSL `researchQueryNodeChildren`, `sortOrder=PUBLICATION_DATE DESCENDING`); custom `janus_user` header threaded from `IMDR_RESEARCH_JPM_USERNAME` | 100 (tested; UI uses 25) | ~150-220 raw |
| stanc | `POST /research/api/common/global/search/newSearch` body `{expression:"*", filterExpression:"<Lucene>", resultSetLimit, sortBy:[{fieldName:"payload.publishedDateTime", direction:"Desc"}], includePayload:true, dapPolicy:"NextGen"}` — payload exposes `assetClassCodes[]`, `regionCountryIds[]`, `materialMentioned[].researchObjectCode` (Phase-8 signals all in v1) | 500 (tested up to 1000) | ~4/day net |

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
