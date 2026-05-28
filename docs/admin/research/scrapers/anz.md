# ANZ — Research scraper

Pattern: **A. Listing-API firehose** (HTML-in-JSON tiles) + viewer
redirect chain to S3 (see [scrapers/index.md](index.md)).

## Daily volume

~10–20 reports/day. Discovered via the tile API in 1 page of 200
with date-sorted early-stop. The tile API was the SPA's own backing
endpoint — switching to it from DOM scrape didn't change per-day
counts (ANZ is a smaller research operation already saturated by
the DOM crawl), but made coverage paginatable / robust.

## Listing API (current — 2026-05-07)

```
GET https://research.anz.com/document_data_tiled_all
    ?param_limit=200
    &param_layout=wide
    &param_increment=200
    &param_libraries=Default
    &position=0
```

Response: ``{"content": ["<tile-html-1>", "<tile-html-2>", ...]}``.
Each tile is real HTML embedded in the JSON. We regex-extract the
metadata from the tile HTML rather than re-rendering it via Playwright.

Pagination: ``position=0, 200, 400, ...`` with ``param_limit=200``.
Tested up to ``param_limit=500`` successfully.

Per-tile regex extraction:

| field | regex source |
|---|---|
| `docRef` | onclick handler ``ref:'(<uuid>)'`` |
| `tile-publication-type` | e.g. "Malaysia Insight" |
| `tile-publication-date` | e.g. "07 May 2026" |
| `tile-title` `<a>` text | report title |
| `analysts` | onclick handler ``analysts:'(<comma-separated>)'`` |

## Portal

| | |
|---|---|
| Hostname | `research.anz.com` |
| Backend | SingleTrack CMS (Salesforce-based) |
| Sign-in URL | `https://research.anz.com` (login form) |
| Username | see `.env: IMDR_RESEARCH_ANZ_USERNAME` |
| Password | in `.env: IMDR_RESEARCH_ANZ_PASSWORD` |
| MFA | not enforced for this account currently |

## Profile

```
playground/research/profiles/anz/
```

Fresh profile — ANZ wasn't in the inherited playwrights folder, so
first interactive login is required. Sessions appear stable for at
least a few days.

## URL patterns

### Documents — public download form

```
https://research.anz.com/file/{slug}.pdf?docRef={uuid}&ch={n}
```

* `{slug}` — title slug (decorative — server keys off `docRef`). We
  pass `anything.pdf` to keep the crawler simple.
* `{uuid}` — SingleTrack `docRef` (UUID v4 lowercase).
* `{n}` — channel parameter (typically `2`). Optional; omitted in our
  builder.

This URL returns an HTML "Download Document" page that JS-redirects to
a viewer host — see [Fetch strategy](#fetch-strategy) below.

### Documents — canonical SingleTrack endpoint

```
https://publications.anz.com/SingletrackCMS__DownloadDocument?docRef={uuid}
```

This works for **footer/policy docs** but **NOT for actual research**
on `research.anz.com` (it 404s). Our builder uses `/file/anything.pdf`
which works for both.

### Hub pages crawled

Defined in [`crawler_anz.py`](../../../../playground/research/ingest/crawler_anz.py)
as `DEFAULT_HUB_URLS`:

```
https://research.anz.com/your_research            # personalised feed
https://research.anz.com/all_research             # full catalogue
https://research.anz.com/latest_research          # chronological recent
```

All three populate reliably in headless Chrome.

## Fetch strategy

**Redirect-chain extraction** (slow path). The chain:

1. GET `https://research.anz.com/file/anything.pdf?docRef={uuid}` →
   200 OK with `text/html`. Body is a "Download Document" page
   containing a hidden `<span class="redirect_url">` with the next URL.
2. JS redirects the browser to:
   `https://*.cloudfront.net/view?src=<URL-encoded signed S3 URL>&data=...&perms=...`
3. The viewer page loads the PDF inline from the signed S3 URL on
   `anz-singletrack.s3.ap-southeast-2.amazonaws.com` (signature
   expires in 24h).

`fetch.py` slow path:

1. Navigates the original URL via Playwright page (cookies preserved).
2. Polls `page.url` until it lands on a viewer host (cloudfront.net,
   amazonaws.com, execute-api).
3. Extracts the `src` (or `url`/`file`/`pdf`) query param,
   URL-decodes.
4. Fetches the decoded URL via `ctx.request.get(...)` — the body is
   the PDF binary.

## Listing extraction

Each report is a tile with this DOM (inspect via the saved HTML in
`playground/research/anz_explore/pages/`):

```html
<div class="tile-content">
  <div class="tile-publication">
    <span class="tile-publication-type">Malaysia Insight</span>
    <span class="tile-publication-date pull-right">07 May 2026</span>
  </div>
  <span class="tile-title">
    <a onclick="getComponent('modal').show('preview_body',
                {ref: '490cbb9c-...', analysts: 'Krystal Tan', title: 'Article Preview'})">
      Bank Negara Malaysia: Inflation in focus, no shift yet
    </a>
  </span>
</div>
```

Crawler runs JS that walks `.tile-content`, extracts:

| Field | Source |
|---|---|
| `docRef` | regex over the parent `onclick` attribute (`ref: '...'`) |
| `publication_type` | `.tile-publication-type` text (e.g. "Malaysia Insight") |
| `publish_date` | `.tile-publication-date` text → `parse_anz_date` |
| `title` | `.tile-title a` text |
| `analysts` | regex over `onclick` attribute (`analysts: '...'`) |

Parses `"07 May 2026"` / `"7 May 2026"` (with or without leading zero,
short or long month name).

## Non-PDF tiles

Some tiles aren't downloadable PDFs — e.g. `"5 in 5 with ANZ"` is a
podcast/video. They have a docRef but the redirect chain ends at
`https://publications.anz.com/SingletrackCMS__FileNotFound`.

The crawler currently keeps these in the discovered list and the
`fetch.py` slow path raises a `FetchError` when the viewer URL doesn't
have an extractable PDF source. The runner reports `[FAIL]` for these.

**TODO**: filter by `publication_type` to skip known non-PDF kinds
(probably `"Podcast"`, `"Video"`, `"5 in 5"`). Need to enumerate the
types we see during a few days of ingest before locking the filter.

## Watermarks

ANZ PDFs may carry licensee text. Existing watermark stripping in
`parse._normalise_for_hash()` handles "For the exclusive use of <email>"
patterns generically. ANZ-specific patterns haven't been observed yet
— if dedup ever produces unexpected duplicates from ANZ, look at
the trailing chars of the PDF text.

## Quirks

* **`/SingletrackCMS__DownloadDocument` only works on
  `publications.anz.com`** (footer policy docs); on `research.anz.com`
  it 404s. Use `/file/anything.pdf?docRef=...` for actual research.
* **Signed S3 URLs expire in 24h**. We always go through the redirect
  chain at fetch time — the URL we store in `dim_report.pdf_url` is
  the stable `/file/...` URL, not the signed S3 URL.
* **Per-fetch overhead is ~9s** vs ~2s for direct-fetch vendors —
  the slow path opens a Playwright page and waits for the viewer host
  to surface.

## Run

```
# Discover + ingest today (and yesterday) — embed off, fast iteration
python playground/research/ingest_today_anz.py

# With embeddings:
$env:IMDR_RESEARCH_EMBED = "true"
python playground/research/ingest_today_anz.py
```

## Last verified

2026-05-07 — pipeline working end-to-end via the tile API
(``/document_data_tiled_all``). **~19 reports/day** in window
(unchanged from DOM scrape — ANZ daily volume is already small;
the API switch was for reliability + paginatability rather than
coverage). Per-PDF wall-clock ~12s with embed off (slow-path
redirect chain to S3 dominates).
