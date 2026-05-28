# Goldman Sachs — Marquee research scraper

Pattern: **A. Listing-API firehose** + direct PDF (see
[scrapers/index.md](index.md)).

## Daily volume

~330 PDF reports/day across all GIR disciplines (post path-filter).
Discovered via ``/research/search/reports/advanced-search`` — fetched
in ~3–5 pages of 200 with date-sorted early-stop.

The raw search API returns ~470/day across all content types but only
``/content/research/en/reports/`` paths have PDFs — the others are
interactive Excel models, blogs, MarketView audio/video. We filter at
discovery time so fetch_pdf isn't wasted on items that 404 or return
empty bodies.

## Listing API (current — 2026-05-07)

```
POST https://marquee.gs.com/research/search/reports/advanced-search
Content-Type: application/json

{
  "facets":   "()",
  "language": "[\"en\"]",
  "page":     1,
  "size":     200,
  "sort":     "time",
  "limitTo":  "[\"\"]"
}
```

Response top-level: ``totalRecords`` (≈1.29M), ``totalPerPage``,
``pagination``, **``documents``** (the list).

Per-document fields used:

| field | notes |
|---|---|
| `id` | UUID |
| `title` / `distributionHeadline` | report title |
| `path` | `/content/research/en/.../<uuid>.html` — HTML viewer URL |
| `downloadPath` | currently always `null` — we derive PDF URL from `path` |
| `publicationDateTime` | epoch ms UTC |
| `authors` | array of name strings |
| `sourceDisplayName` | e.g. "Research \| Equity" |

Pagination: ``page=1, 2, 3, ...`` with ``size=200``. Sort=time (date
desc). Early-stop on oldest_in_page < ``since``.

PDF URL: prefer ``downloadPath`` when populated (always set on
``/content/research/en/reports/`` items); else derive by swapping
``.html`` → ``.pdf`` on ``path``. **Skip the document entirely** if:

* ``downloadPath`` is null AND
* ``path`` doesn't start with ``/content/research/en/reports/``

The 4 Goldman content types in the search index and their PDF status:

| Path prefix | Has PDF? | Notes |
|---|---|---|
| `/content/research/en/reports/` | ✓ — `downloadPath` populated | The actual research-report PDFs |
| `/content/research/en/models/` | ✗ — empty body | Interactive Excel/web model — not a PDF |
| `/content/markets/en/...` | ✗ — 404 | MarketView audio / video / commentary |
| `/content/research/en/blogs/` | ✗ — 404 | Blog post |

Filter applied in `_derive_pdf_url()` so non-PDF items are dropped at
discovery (``kept += 1`` only for items with a resolvable PDF).

## Fetch strategy

Direct GET on the derived PDF URL. ``fetch.py`` fast path returns
`%PDF-...` bytes immediately on the persistent-profile cookies.

## Legacy approach (DOM scrape — superseded)

## Portal

| | |
|---|---|
| Hostname | `marquee.gs.com` |
| Sign-in path | SSO via marquee.gs.com homepage |
| Username | see `.env: IMDR_RESEARCH_GS_USERNAME` |
| Password | in `.env: IMDR_RESEARCH_GS_PASSWORD` |
| MFA | typically email/app-based on first device; persistent thereafter |

## Profile

```
playground/research/profiles/goldman/
```

First run: launch `explore_goldman.py`, sign in interactively. Subsequent
runs reuse cookies. Sessions appear stable for several weeks.

## URL patterns

### Reports — public-facing path

```
https://marquee.gs.com/content/research/en/reports/{YYYY}/{MM}/{DD}/{uuid}.html
https://marquee.gs.com/content/research/en/reports/{YYYY}/{MM}/{DD}/{uuid}.pdf
```

* `{YYYY}/{MM}/{DD}` — publish date encoded in path.
* `{uuid}` — Goldman's stable internal id (e.g.
  `721599cb-abbc-498a-b841-33bb3f653801`).
* `.html` is the in-portal viewer; `.pdf` is the download. **Same UUID
  serves both**. Listing pages link to `.html`; we swap suffix to
  `.pdf` at fetch time.

### Authors

```
https://marquee.gs.com/content/research/authors/{uuid}.html
```

Eventual `dim_author` integration. Not currently consumed.

### Hub pages crawled

Defined in [`crawler_goldman.py`](../../../../playground/research/ingest/crawler_goldman.py)
as `DEFAULT_HUB_URLS`:

```
https://marquee.gs.com/s/home                                # MarketFeed digest, post-login
https://marquee.gs.com/content/markets/home.html
https://marquee.gs.com/content/markets/products/rates.html
https://marquee.gs.com/content/markets/products/fx.html
https://marquee.gs.com/content/markets/products/credit.html
https://marquee.gs.com/content/markets/products/commodities.html
https://marquee.gs.com/content/markets/products/emerging-markets.html
https://marquee.gs.com/content/markets/products/equities.html
https://marquee.gs.com/content/themes/macro-markets.html
```

`/s/home` and `/content/markets/home.html` are the most reliable; the
per-product pages are SPA-loaded and sometimes return only chrome (5
raw anchors) in headless Chrome. The hub set has heavy overlap so
unreliable pages don't typically miss reports.

### Tracking parameters

URLs come decorated with `?mq_utm_source=...&mq_utm_campaign=...`. Strip
before canonicalising — only the path matters for dedup.

## Fetch strategy

**Direct GET**. `ctx.request.get(<.pdf URL>)` returns `%PDF-...` bytes
in one round trip with the persistent-profile cookies. No redirect
chain, no viewer page. Goldman is the cleanest of the vendors so far.

## Listing extraction

Crawler walks each hub page in headless Chrome, waits for the SPA to
populate (~2.5s + networkidle), then runs JS that pulls every
`<a href="/content/research/en/reports/...">` link:

```javascript
() => Array.from(document.querySelectorAll('a[href]')).map(a => ({
    href: a.href,
    text: (a.innerText || '').trim().slice(0, 200),
}))
```

Each href is parsed for ``YYYY/MM/DD/{uuid}.html``. Title comes from
the anchor `innerText`. When the same UUID appears across multiple hubs
with different anchor texts, the longest non-author-looking text wins.

### Author-byline filter

Some anchors are author bylines, e.g. ``"Jane Doe and 3 others"``. The
crawler skips these as title candidates with a small heuristic:
contains `" and "` and is short (<= 6 words), or ends with `" others"`.

## Watermarks

Goldman PDFs include a 32-char hex unique-id at the bottom of the last
page (e.g. `15ba8a22fa6f49ada94e2d8ce72eb1f5`) and the licensee email
(`For the exclusive use of RESEARCH@RVCAPITAL.COM`). Both are stripped
by `parse._normalise_for_hash()` before content-hashing — see
[`parse.py`](../../../../playground/research/ingest/parse.py).

## Quirks

* `publishing.gs.com` (in `.env: IMDR_RESEARCH_GS_URL`) appears to be
  an older URL that redirects. Use `marquee.gs.com` for everything.
* SPA route changes destroy the JS execution context for ~1s; the
  crawler retries on `Execution context was destroyed`.
* HTML responses on the per-product pages are often very large (> 2 MB);
  the explorer truncates at 2 MB to keep the explore folder manageable.

## Run

```
# Discover + ingest today (and yesterday) — embed off, fast iteration
python playground/research/ingest_today_goldman.py

# With embeddings (Gemini Embedding 2 default):
$env:IMDR_RESEARCH_EMBED = "true"
python playground/research/ingest_today_goldman.py
```

Other env knobs documented in
[`ingest_today_goldman.py`](../../../../playground/research/ingest_today_goldman.py).

## Last verified

2026-05-08 — pipeline working end-to-end via advanced-search +
path-type filter. **~330 PDF reports/day** discovered (was ~6 with DOM
scrape; was ~470/day before filter — the difference is non-PDF content
types we now skip at discovery). Per-PDF wall-clock ~3s with embed off,
fail rate dropped 50% → ~5%.
