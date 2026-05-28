# Nomura — Nomura Now research scraper

Pattern: **A. Listing-API firehose** + direct PDF (see
[scrapers/index.md](index.md)) — cleanest fetch shape of any vendor.
Download URL is deterministic; listing API is full Elasticsearch DSL.

## Daily volume

~100 reports/day in English. Discovered via the ES search API in 1
page of 1000 with server-side date-range filter.

## Listing API (current — 2026-05-07)

```
POST https://www.nomuranow.com/research/japi/pub/search/query
Content-Type: application/json
```

Body (Elasticsearch query DSL):

```json
{
  "query": {"bool": {"must": [
    {"bool": {"should": [{"term": {"language": "en"}}]}},
    {"range": {"publicationDate": {"gte": "<since>"}}}
  ]}},
  "sort": {"publicationDate": {"order": "desc"}},
  "size": 1000,
  "_source": [
    "id","title","publicationDate","analysts","periodicals",
    "primaryPeriodicals","assetClasses"
  ],
  "from": 0
}
```

Response: ``hits.total.value`` (~511K total in index),
``hits.hits[]`` array. Each hit has ``_id`` (numeric publication ID,
same as the URL path segment) and ``_source`` (metadata).

Pagination: ``from=0, 1000, 2000, ...`` with ``size=1000``. Sort by
``publicationDate`` desc. Server-side range filter eliminates pre-window
rows.

Per-hit fields used:

| field | notes |
|---|---|
| `_id` | numeric publication id (Nomura's report_id) |
| `_source.title` | report title |
| `_source.publicationDate` | ISO datetime |
| `_source.analysts[]` | list of analyst objects (name.en preferred) |
| `_source.periodicals[]` | publication category (e.g. "Asia Insights") — used for our `publication_type` column |
| `_source.assetClasses[]` | asset class fallback if no periodical |

## Fetch strategy

## Portal

| | |
|---|---|
| Hostname | `www.nomuranow.com` |
| Entry path | `/research/` (the bare host bounces around — go straight to `/research/`) |
| Hub page | `https://www.nomuranow.com/research/m/Home` |
| Sign-in | login form on portal |
| Username | see `.env: IMDR_RESEARCH_NOMURA_USERNAME` |
| Password | in `.env: IMDR_RESEARCH_NOMURA_PASSWORD` |
| URL env var | `IMDR_RESEARCH_NOMURA_URL=https://www.nomuranow.com` |

## Profile

```
playground/research/profiles/nomura/
```

## URL patterns

### PDF download (deterministic)

```
https://go.nomuranow.com/research/japi/publication/{report_id}.file
```

The same path with `?appname=GRPUI` (no `.file` suffix) is the in-portal
viewer redirect; it sends the user to a signed CDN URL. We don't need
to resolve that — appending `.file` returns the PDF directly.

`{report_id}` is a 7-digit numeric identifier (e.g. `1298112`).

### Hub page

```
https://www.nomuranow.com/research/m/Home
```

Per-asset-class hubs exist (`/m/Economics`, `/m/Equity`, `/m/FX`,
`/m/Rates`, `/m/SP__Credit`, `/m/Macro%20Strategy`, `/m/Quants`) but
the Home page already merges everything. We crawl just `/m/Home`.

### Tracking parameters

The anchor URLs include `?appname=GRPUI`. We strip them — only
`report_id` matters.

## Fetch strategy

**Direct GET**. `ctx.request.get(<.file URL>)` returns
`application/pdf;charset=UTF-8` with `%PDF-...` bytes immediately, on
the persistent-profile cookies. No redirect chain to resolve, no
viewer hop, no signed-URL scraping.

The smart `fetch.py` fast path handles this with no extra round trips
— same as Goldman.

## Listing extraction

### Two view modes — same data, different DOM

The Latest Research listing renders in either:

* **Tile view** (default in fresh sessions; default in headless) —
  cards in a grid. Wrapper: `.col-lg-4 > .card`. Authors in
  `.card-header`, title in `.card-body .card-title`, abstract in
  `.synopsis`, tags in `.card-footer` first div, date inside
  ``PublicationCard_actionButtons__*`` div as
  ``<small><b>X minutes ago</b></small>``.
* **List view** (user toggle, sticky once selected) — denser layout.
  Wrapper: `.list-group-item.list-group-item-light`. Date is the
  first ``<small>``; authors are subsequent ``<small>`` with
  ``.text-uppercase``; tags + PDF icon trail.

Both views ship the same anchor:

```html
<a href="https://go.nomuranow.com/research/japi/publication/1298112?appname=GRPUI"
   target="1298112"
   rel="noopener"
   class="...">
  Asia Insights - Malaysia: BNM on a still-neutral hold
</a>
```

### Anchor-first extraction

Since wrapper classes differ between views (and React's CSS-modules
hashes shift between deploys), the JS extractor seeds on
``a[target=<numeric>]``, walks up to the nearest enclosing
``.card`` / ``.list-group-item.list-group-item-light``, and looks
within for the metadata. See `_LIST_EXTRACT_JS` in
[`crawler_nomura.py`](../../../../playground/research/ingest/crawler_nomura.py).

| Field | Source |
|---|---|
| `report_id` | anchor `target` attribute (numeric) |
| `title` | anchor `innerText` |
| `abstract` | `.synopsis` (tile) or `.text-muted` (list) |
| `publish_date` | regex over any `<small>` matching ``"\d+ (minute|hour|day|week|month)s? ago"`` / ``"yesterday"`` / ``"just now"`` |
| `authors` | `.card-header small` (tile) or `.text-uppercase` smalls (list), de-duped |
| `tags` | `[title^="Asset Class:"]`, `[title^="Regions:"]`, `[title^="periodicals.en:"]`, `[title^="Sectors:"]` |
| `hasPdf` | presence of `i.fa-file-pdf` (currently best-effort — inconsistent across views) |

### Wait-for-ready

Nomura's React shell renders before items mount. Crawler waits via
``page.wait_for_function`` for at least one numeric-target anchor to
appear in the DOM (``a[target]`` with `/^\d+$/`), then a 4s settle.
Networkidle timeout 20s is observed but tolerated to fail.

### Date parsing

Relative date strings are converted to absolute UTC dates:

* ``"X seconds/minutes/hours ago"`` → today (UTC)
* ``"X days ago"`` → today − X days
* ``"X weeks ago"`` → today − 7 X
* ``"X months ago"`` → today − 30 X (coarse, fine for date filters)
* ``"yesterday"`` → today − 1
* ``"just now"`` → today

For older items the listing may switch to absolute formats (``"7 May
2026"`` etc.); the parser tries a small set of common formats as
fallback.

## Watermarks

Not yet observed — `parse._normalise_for_hash()` already strips
generic patterns (32-char hex on its own line, ``"For the exclusive
use of <email>"``). If Nomura PDFs ever cause unexpected dedup
failures, inspect the bottom of the extracted text for a
license/serial pattern and add to the watermark regex list.

## Quirks

* **Tile vs List view rendering differs.** Headless Chrome lands in
  Tile view by default; the user's interactive explorer was in List
  view. Anchor-first extraction handles both.
* **`fa-file-pdf` icon is unreliable** — only some items show it
  in List view, and Tile view rarely shows it. We don't currently
  filter on it. Items that turn out to be non-PDF (podcasts, videos)
  fail at fetch with a clear error and surface as ``[FAIL]`` in the
  runner output.
* **CSS Modules hashes** (e.g. `PublicationCard_synopsis__7DHUL`)
  may shift between deploys. We use stable selectors only:
  `.card`, `.card-body`, `.card-header`, `.card-footer`,
  `.synopsis`, `[title^="..."]`.
* **`.list-group-item-light` is not a stable wrapper class** because
  the SPA may render in Tile view by default. Don't depend on it.

## Run

```
python playground/research/ingest_today_nomura.py

# With embeddings:
$env:IMDR_RESEARCH_EMBED = "true"
python playground/research/ingest_today_nomura.py
```

## Last verified

2026-05-07 — pipeline working end-to-end via the new ES search API.
**~107 reports/day** in English (was ~31 with DOM scrape of /m/Home).
Per-PDF wall-clock ~5-7s with embed off.
