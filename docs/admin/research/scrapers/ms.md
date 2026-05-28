# Morgan Stanley — Matrix research scraper

Pattern: **A. Listing-API firehose** → frontmatter JSON → direct PDF
(see [scrapers/index.md](index.md)). Three HTTP calls per report:
listing (paginated POST), per-uuid frontmatter (parallel), PDF GET.

## Daily volume

~500 reports/day across all asset classes. Discovered via the
``/portal-content-service/search`` POST API in 1–2 pages of 500 with
date-sorted early-stop.

## Listing API (current — 2026-05-07)

```
POST https://ny.matrix.ms.com/eqr/research/webapp/portalservices/portal-content-service/search
Content-Type: application/json
```

Body:

```json
{
  "compositeRequest": {
    "search":     "(text==*)",
    "sort":       "d",
    "noSearch":   false,
    "gn":         false,
    "didyoumean": false,
    "countMode":  "best",
    "showcard":   true,
    "size":       500,
    "page":       1
  },
  "arRequest": {
    "skipSpellCheck":    false,
    "queryID":           "<random uuid>",
    "userJourneyId":     "<random uuid>",
    "invokeAskResearch": false,
    "dateFilter":        "",
    "filtersMap": {"queryWithoutStopwords": ""}
  }
}
```

Response: ``rcsResponse.sd.t`` (=10000 max per query),
``rcsResponse.sd.h`` (this page count), **``rcsResponse.reportcards``**
is the list.

Per-card fields used:

| field | notes |
|---|---|
| `id` | UUID |
| `hl` | headline = title |
| `pd` | ISO datetime |
| `ab` | abstract |
| `a.n` | first author name |

Pagination: ``page=1, 2, ...`` with ``size=500``. Sort=d (date desc).
Early-stop on oldest_in_page < ``since``.

## Frontmatter API (per-uuid PDF resolution)

## Portal

| | |
|---|---|
| Hostname | `ny.matrix.ms.com` |
| Hub URL | `https://ny.matrix.ms.com/eqr/research/portal/home/global` (the master cross-asset feed) |
| SSO | `login.matrix.ms.com` (login-mfa flow with **email verification link** — link must be opened in the Playwright browser instance, not the user's normal browser) |
| Username | see `.env: IMDR_RESEARCH_MS_USERNAME` |
| Password | `IMDR_RESEARCH_MS_PASSWORD=check_email` — the actual MFA arrives in email per login |

## Profile

```
playground/research/profiles/ms/
```

First-run setup is interactive: login → click "send verification email"
→ open the email and **paste the link into the Playwright Chrome
window's address bar**. That authenticates the persistent session;
subsequent runs are silent until the cookies expire.

## URL chain

### Step 1 — listing

```
https://ny.matrix.ms.com/eqr/research/portal/home/global
```

The master cross-asset feed. A probe (see ``probe_ms.py``) found
``/home/global`` returns the most UUIDs (78 unique anchors at peak),
beating ``/portal/feed`` (24, personalised) and per-asset-class
``/page/{slug}/overview`` pages (10–35). Several asset-class slugs
(``themes``, ``forecasts``, ``equities``, ``fx_em_strategy``,
``securitized_products``, ``municipal_strategy``, ...) bounce to
``/portal/search?q=...`` — they're search-driven, not standalone hubs.
Settling on ``/home/global`` covers everything in one crawl.

### Step 2 — frontmatter API per UUID

```
GET https://ny.matrix.ms.com/eqr/article/webapp/services/published/article/frontmatter?uuid={uuid}
```

Returns JSON:

```json
{
  "uuid": "d6243af0-400b-11f1-9722-317872234fd6",
  "frontMatter": {
    "productType": "Idea",
    "topicHeadline": "CEEMEA Sovereign Credit, Economics and Macro Strategy",
    "region": "EEMEA",
    "articleHeadline": "Correction: Cleaner Shock Response This Time",
    "publicationDateTime": "2026-05-07T11:51:43.000Z",
    "publicationDate": "2026-05-07",
    "authorList": [{"firstName": "Neville", "lastName": "Mandimika", ...}, ...],
    "pdfRenditionUrl": "/eqr/article/webapp/services/published/rendition/pdf/EMSOVEREIGN_20260507_1151.pdf?cobaltId=02a5-...&uuid=d6243af0-..."
  }
}
```

Fields the crawler consumes:

| Field | Use |
|---|---|
| `articleHeadline` | report title |
| `topicHeadline` | publication type / asset_class hint |
| `publicationDateTime` / `publicationDate` | publish_date for filtering |
| `authorList` (array) | analysts (flattened to comma-separated names) |
| `pdfRenditionUrl` | direct PDF URL (relative — prefix with ``https://ny.matrix.ms.com``) |

`pdfRenditionUrl` already includes a `cobaltId` session token. We do
NOT need to navigate the article viewer or capture a download event —
this URL serves PDF bytes on a direct authenticated GET.

### Step 3 — PDF fetch

```
GET https://ny.matrix.ms.com/eqr/article/webapp/services/published/rendition/pdf/{TYPE_CODE}_{YYYYMMDD}_{HHMM}.pdf?cobaltId={token}&uuid={uuid}
```

`{TYPE_CODE}` is server-generated from the report (``EMSOVEREIGN``,
``AUDIO``, etc.). We don't construct this URL — we use the
``pdfRenditionUrl`` from the frontmatter response verbatim.

Response: ``Content-Type: application/pdf`` with ``%PDF-...`` bytes.

## Discover-vs-resolve concurrency

The crawler issues `frontmatter` calls in parallel (default
``_FRONTMATTER_PARALLEL = 10``). Each call is light JSON. For ~40
items the resolution phase typically completes in 2–3 seconds.

## Listing extraction

Anchor pattern in the listing HTML:

```
https://ny.matrix.ms.com/eqr/article/webapp/{uuid}?ch=rp&sch=...&rt=...
```

`{uuid}` is the only thing we extract from the listing — title and
date come from the frontmatter API, which is more reliable than the
listing's relative-time string.

JS extractor walks every ``a[href]`` whose URL matches the
``/eqr/article/webapp/<uuid>`` regex (case-insensitive; UUID v4
format).

## Wait-for-ready

The MS portal is a heavy SPA — listing items mount well after
``domcontentloaded``. Crawler waits via ``page.wait_for_function``
for at least one matching anchor to appear in the DOM (timeout 30s),
then a 4s settle.

## Watermarks

Not yet observed — `parse._normalise_for_hash()` already strips
generic patterns. If MS dedup ever produces unexpected duplicates,
inspect the bottom of the extracted text for a per-download
identifier and add to the watermark regex list.

## Quirks

* **Email verification link is single-use.** First-run setup must
  paste the link from the email into the Playwright browser window;
  clicking it in your normal browser consumes the link and leaves the
  Playwright session unauth'd. Re-trigger if needed.
* **Listing wraps articles in anchors with `target="_blank"` style
  navigation.** The probe found that clicking opens a new tab — we
  don't need to navigate; the URL pattern alone gives us the UUID.
* **`asset_class` column is VARCHAR(30)**; some MS topic-headlines run
  longer (e.g. "Vanguard International Semiconductor"). The DB write
  truncates safely — we should widen the column when promoting out of
  playground.
* **`cobaltId` in pdfRenditionUrl is short-lived** (likely tied to
  the user's session). We always re-fetch frontmatter at ingest time;
  no value in caching the URL.
* **78 UUIDs reported by the probe; 39 returned at next run.** The
  feed pagination / personalisation makes the count vary. /home/global
  is still the most comprehensive single hub.

## Run

```
python playground/research/ingest_today_ms.py

# With embeddings:
$env:IMDR_RESEARCH_EMBED = "true"
python playground/research/ingest_today_ms.py
```

## Last verified

2026-05-07 — pipeline working end-to-end via the new search-API
listing path. **~579 reports/day** in window after frontmatter
resolution (was ~14 from DOM scrape of /home/global). Per-PDF
wall-clock ~3s with embed off.
