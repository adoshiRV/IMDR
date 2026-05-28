# Barclays Live (Investment Bank Research) — scraper notes

Status: **live** (since 2026-05-08).

* Discovery: ~**450 publications/day** via the publication-search
  firehose (~200/page, paginated until oldest crosses ``since``).
* Ingest: <1 s/PDF (pre-cached during discovery, pipeline reads bytes
  directly via ``ingest_one(pdf_bytes=...)``).
* Coverage: pubDate-desc full catalogue scan, not the home tile subset.

## Why Barclays is structurally different

The other 5 research vendors use a stable persistent profile + a
JSON listing API (or HTML scrape) reachable with cookies alone.
Barclays Live is hostile to that pattern in three ways:

1. **PingFederate session tokens rotate aggressively.** Cookies
   captured in one Playwright run go stale by the next; every
   navigation redirects to ``/UAB/ct_logon_basic``. Persistent
   profiles work for *one* session and poison subsequent ones.
2. **No MFA in practice** — but only on device-trusted IPs. Risk-based
   auth lets username + password through on this machine. If Barclays
   later requires email-OTP, see the MFA-extension stub at the bottom
   of [`login_barclays.py`](../../../../playground/research/ingest/login_barclays.py).
3. **API endpoints reject ``ctx.request.get``** even with the right
   cookies — they need the full SPA-injected request shape (CSRF
   tokens, Origin, etc.). All API calls must be made via
   ``page.evaluate('fetch(...)')`` from inside the SPA's origin.

These quirks dictate the architecture below.

## Architecture

```
Discovery (`discover_reports`):

1. ensure_clean_profile(profile_dir)            # nuke stale state
2. login(ctx, username, password)
   - dismiss OneTrust cookie banner
   - fill input[name="user"] + input[name="password"]
   - click button#submit  → page lands on /BU/
3. open_warm_page → goto(/BU/), wait for [data-pubid]
4. firehose loop (page_num = 1..MAX_PAGES):
     fetch /publication/search?pageSize=200&pageNumber={N}
       (page-context fetch, with mid-run re-login on auth-wall)
     for each publication:
       parse basicInfo.pubDate
       if oldest_in_page < since → break  (early stop)
       pick documents[] entry where channel='PRINT' & mediaType='application/pdf'
       record metadata (no PDF download yet)
     follow data.pageInfo.nextPageUrl until done or date threshold hit
5. Return metadata-only ReportRefs

Runner then applies the relevance filter (drops single-name equity)
on metadata. For survivors, `fetch_pdfs(profile_dir, refs)` opens a
second Playwright session and streams `(ref, pdf_bytes)` tuples
straight to `ingest_one(..., pdf_bytes=...)`. Nothing touches disk.
```

### Mid-run re-login

`_fetch_json_with_relogin` and `_fetch_pdf_bytes_with_relogin` wrap each
page-context fetch with up to `_MAX_RELOGIN_ATTEMPTS` retries. On any
of: HTML response (auth wall), non-200 status, exception during fetch,
they call `login(ctx, ...)` again and re-open the warmed `/BU/` page,
then retry. Long crawls cross PingFederate token rotations — without
this, every run with >50 fetches breaks halfway through.

## Endpoints discovered

| Purpose | URL | Notes |
|---|---|---|
| Home (warm-up) | `https://live.barcap.com/BU/` | Just for SPA hydration; not parsed for content anymore |
| Login | `https://live.barcap.com/UAB/ct_logon_basic?resumePath=...` | PingFederate; redirected to from `/BU/` if not authed |
| **Publication firehose** | `/RSX/content-archive/v1/REST/publication/search?pageSize=200&pageNumber=N&responseDetailLevel=STANDARD&includeSource=BARRENJOEY` | JSON, pubDate-desc; `data.publications[]` + `data.pageInfo.nextPageUrl` |
| Per-pubId lookup | `/RSX/content-archive/v1/REST/publication/search?pubId={pubId}` | Same shape; used by article-viewer pages |
| Document download | `/RSX/content-archive/REST/document/{docId}` | Direct PDF bytes |

### Response shape

```
{
  "data": {
    "pageInfo": {
      "pageNumber": 1, "pageSize": 200,
      "currentPageUrl": "...", "nextPageUrl": "...&pageNumber=2",
      "recordCount": 200
    },
    "publications": [
      {
        "basicInfo": {
          "pubId": "<24-hex>",
          "pubDate": "2026-05-08",
          "releasedDateTime": "2026-05-08T08:00:00Z",
          ...
        },
        "documents": [
          {
            "docId": "<24-hex>",
            "channel": "PRINT",
            "mediaType": "application/pdf",
            "url": "/RSX/content-archive/REST/document/<docId>",
            ...
          },
          ...
        ],
        "titles": [{"type": "PUBLICATION", "value": "..."}],
        "classifications": [{"type": "PRODUCT", "value": "..."}],
        ...
      },
      ...
    ]
  },
  "status": ...
}
```

`pageSize=1000` works server-side, but per-page response payloads
balloon to ~35 MB. We default to **200** to balance throughput
against memory + page-context fetch time.

## Selectors

* Cookie accept: `#onetrust-accept-btn-handler`
* Username:      `input[name="user"]`
* Password:      `input[name="password"]`
* Submit:        `button#submit`
* Tile attr:     `[data-pubid]`

## Known limitations

* **`pubDateRange` server-side filter is a no-op** — empirical: same 50
  results returned for `1+day` / `1+week` / `1+year` / `50+years`.
  Filter happens client-side from `basicInfo.pubDate`.
* **`includeSource` is a no-op** — tested with `BARRENJOEY`, `BARCLAYS`,
  `BARCAP`, `RESEARCH`, `ALL`, omitted entirely → identical responses.
  The portal SPA passes `BARRENJOEY` (Barclays' Australian partnership)
  but the server ignores it. The 200-pub firehose returns the full
  Barclays Research catalogue the user has entitlement for — confirmed
  by title diversity (Thematic Investing, single-stock European/US
  names, EM flows, etc., not Australia-specific).
* **dim_vendor row reused.** Barclays already had a `dim_vendor` row
  (id=2, type=`file`) from the SKEW Excel feed. We share it — same
  firm, just different feed. Other research vendors got their own row.
* **Classifications field is sparse.** `responseDetailLevel=STANDARD`
  returns empty `classifications[]` on most publications. Asset-class
  hints come from the title only. `responseDetailLevel=FULL` (or
  `EXTENDED`) might be richer; not yet tested.

## Files

* [`login_barclays.py`](../../../../playground/research/ingest/login_barclays.py)
* [`crawler_barclays.py`](../../../../playground/research/ingest/crawler_barclays.py)
* [`ingest_today_barclays.py`](../../../../playground/research/ingest_today_barclays.py)

## Pipeline contract change

`ingest_one` gained an optional `pdf_bytes: bytes | None` parameter.
When supplied, it skips `fetch_pdf` and uses those bytes directly.
Used only by Barclays today; other 5 vendors still go through fetch.
Barclays needs this because its API only honours `page.evaluate('fetch(...)')`
(needs the SPA's Origin/headers), not the pipeline's `ctx.request.get`.
