# HSBC Global Investment Research — scraper notes

Status: **live** (since 2026-05-08). Smoke test: 2 PDFs ingested in
~4 s each. Page 1 of the listing returned 31 rows (today + ~2 weeks
back); 20 fell inside the today + yesterday window.

## Portal

* Home: `https://www.research.hsbc.com/ibcom/in/reach/servlet/ReachHome`
* All Reports: `https://www.research.hsbc.com/ibcom/in/reach/servlet/Reach`
* Auth: SSO via `<HSBC_USERNAME>` (long-lived cookie in persistent profile)
* Profile: `playground/research/profiles/hsbc/` (created 2026-05-08)

## Architecture (what we found, what's different from the other 4 vendors)

**No JSON listing API.** `probe_listing_apis.py` captured 0 JSON XHR
candidates on both the home and All Reports pages. The portal is fully
server-rendered HTML — closer to a 2010-era webapp than a SPA.

**The PDF URL is the listing link.** Every report row has a
`/R/10/{shortId}` href (e.g. `/R/10/SpJDQFLg9PSd`). Following that URL
triggers an immediate PDF download — there is no detail page, no
viewer iframe, no separate `/download` endpoint. This is the cleanest
shape of any vendor — even simpler than Nomura's deterministic
`{id}.file` URLs.

Confirmed by Playwright erroring with `Page.goto: Download is starting`
when navigating to a sample link.

**Listing endpoint is parametrised but session-bound.**
Pagination + filters are driven by:

```
GET /ibcom/in/reach/servlet/ReachReportSearch
    ?SortColumn=pubdate
    &SortOrder=true        # true = descending (newest first)
    &Page=1
    &RowsPerPage=15
    &MaxNumberOfRows=75
    &productid=0           # 0 = all products
    &notproductid=0
    &sectorid=0
    &analystid=0
    &periodicalid=0
    &indexid=0
    &companyvisit=false
    &marketid=0
    &subjectid=0
    &starrating=0
    &title=
    &filetype=
    &SearchName=ReachResultData
    &datespecific=all      # date-range filter; see DD/MM fields below
    &datefromday=&datefrommonth=
    &datetoday=&datetomonth=
    &pageaction=search
    &searchbox=
    &languageid=0
```

The browser invokes this via `rcRedisplayReportsTab("allReports", "...")`
on column-header clicks and pagination. The response is **HTML
fragment**, not JSON, that gets injected into the All Reports tab.

**Important quirk.** Calling `ReachReportSearch` directly via
Playwright's `ctx.request.get()` (with cookies from the persistent
profile + Referer + `X-Requested-With: XMLHttpRequest`) returns the
unauthenticated landing page (~16 KB) instead of the report rows. The
session evidently requires more than the cookie — likely a
JS-set token, sessionStorage value, or an Origin/SameSite restriction
that doesn't get attached on raw fetches.

**Workaround:** the crawler must use `page.goto()` (a real browser
navigation) rather than the request API. `page.goto(Reach)` returns
the fully populated 176 KB listing page with 31 report links + the
table DOM intact. Pagination via `page.evaluate()` calling
`rcRedisplayReportsTab(...)`, or by constructing the full
ReachReportSearch URL and `page.goto(...)` it.

## Row structure (parsed from `hsbc_explore/listing.html`)

Each report = one `<tr>` with cells:

| Index | Field | Example |
|---|---|---|
| 0 | Date | `08-May-26` (DD-MMM-YY) |
| 1 | Title | `Equity Snap: Lonza (LONN SW) Q1 update: …` |
| 2 | Video icon | (often empty) |
| 3 | Product | `Equities`, `Rates`, `Economics`, `FX`, `Fixed Income` |
| 4 | Analyst | `Yifeng Liu, PhD … more` (UI affordance text leaks in) |
| 5 | Pages | `7` |

Each row contains 2 `/R/10/` anchors (clickable title + a related
"more" link with truncated suffix); dedupe by stripping suffixes
shorter than 8 chars or by using the row anchor with the longest href.

## Mapping to ReportRef

```python
ReportRef(
    uuid             = shortId,            # e.g. "SpJDQFLg9PSd" — 12-char alphanumeric
    title            = cell[1],
    publish_date     = parse_DDMMMYY(cell[0]),
    pdf_url          = "https://www.research.hsbc.com/R/10/" + shortId,
    publication_type = cell[3],            # Product → asset_class
)
```

## Coverage strategy for "everything published today"

1. `page.goto(/ibcom/in/reach/servlet/Reach)` — sorted by pubdate desc
   by default.
2. Parse table rows.
3. Stop once the oldest row's date is < `since`.
4. Otherwise advance via `rcRedisplayReportsTab(...)` with `Page=N+1`,
   parse, repeat.

`RowsPerPage` default appears to be 15. Whether higher values (100,
500) are accepted server-side wasn't verified — the direct-XHR probes
all hit the auth wall before reaching the listing.

## Pagination implementation

The crawler reuses the same `page` object across calls. Page 1 is
the rows already on the loaded `/Reach` landing. Pages 2+ invoke
`rcRedisplayReportsTab('allReports', '/ibcom/in/reach/servlet/ReachReportSearch?...')`
via `page.evaluate` — same JS the UI uses on column-header sort and
"Next" clicks. It fires a same-origin XHR (which evidently *does* have
the session token the page-context retains), the response HTML
replaces the All Reports tab body, and we re-read `page.content()`.

There is no short-page early-stop: HSBC returns ~31 rows per landing
regardless of our `RowsPerPage` param. Pagination stops when:
* Oldest row's date < `since` (pubdate-desc sort guarantees no further
  pages can be in window).
* Empty page (true end of catalogue).
* `_MAX_PAGES` safety cap (50 pages × ~31 rows = ~1500 reports —
  more than any realistic daily window).

## Classifier & relevance filtering (2026-06-02)

The HSBC ``Equities`` feed is dominated by single-name corporate
coverage — ~5/day APAC + global names (Akeso, Broadcom, Meituan,
Mengniu, NMDC, Rasan, etc.). The classifier mines tickers from the
title and the relevance filter drops them.

**Title shape (observed):** `{Company} ({SYM} {EXCH}) {Buy|Hold|Sell|Initiate}: {topic}`

  * Examples: `Meituan (3690 HK) Buy: ...`, `Rasan (RASAN AB) Initiate at Buy: ...`,
    `Broadcom Inc (AVGO US) Buy: ...`, `MphasiS (MPHL IN) Buy: ...`
  * SYM is 2–9 alphanumeric chars (Indian + UAE tickers run up to 9:
    `MAXHEALT IN`, `ADNOCDIS UH`, `DALBHARA IN`).
  * EXCH is a Bloomberg country code: `HK, CH, US, IN, KS, KQ, TT, JP,
    AB, LN, FP, GR, IM, SM, SE, NO, DC, SP, PM, TB, VN, KP, AU, NZ,
    SJ, RM, EY, MM, MX, UH, UQ, ...` (full list in
    [`classifiers/hsbc.py`](../../../../playground/research/ingest/classifiers/hsbc.py)
    `_BB_TICKER`).
  * Tightened with `(?<![A-Za-z0-9])...(?![A-Za-z0-9])` so we don't
    match phrases like "Q4 26", "FY26e AI", or "AI EU".

**What stays kept**

  * `product = "Equity Strategy"` — these are sector / top-down /
    flows notes. The classifier maps them to `STRATEGY` asset_class
    so they bypass the EQUITY check entirely.
  * Equity reports with no parenthesised ticker — sector / regional
    wraps (e.g. "China Consumer Moving with momentum...", "Korea
    Non-life Insurance 1Q26", "MENAT Real Estate Trends").
  * Reports with 2+ tickers (paired comparison / sector basket).

**Verification.** Sample from the 2026-06-02 dry probe of a 3-day
window: 15 reports discovered → 5 dropped (single-name) → 10 kept
(7 sector/regional + 1 Equity Strategy + 2 Economics + 1
Sustainability). All 5 dropped reports were the targeted single-name
notes; no false drops. See
[`probe_hsbc_single_name.py`](../../../../playground/research/probe_hsbc_single_name.py).

**Backfill cleanup.** 60 single-name HSBC reports ingested before the
filter landed were removed on 2026-06-02 via
[`cleanup_hsbc_single_name.py`](../../../../playground/research/cleanup_hsbc_single_name.py)
(60 dim_report rows + 1,119 fact_chunk rows + 60 PDFs from
OneDrive/SharePoint). No embeddings had been generated for these.

## Files

* [`crawler_hsbc.py`](../../../../playground/research/ingest/crawler_hsbc.py)
* [`classifiers/hsbc.py`](../../../../playground/research/ingest/classifiers/hsbc.py) — product → asset_class + ticker mining
* [`ingest_today_hsbc.py`](../../../../playground/research/ingest_today_hsbc.py)
* `dim_vendor` row: `id=13, code='hsbc', display_name='HSBC Global Investment Research', vendor_type='web'`

## Files captured during discovery (reference)

* `playground/research/hsbc_explore/listing.html` — 176 KB rendered
  All Reports page (31 reports, pubdate-desc)
* `playground/research/hsbc_explore/report_responses.jsonl` — every
  XHR fired during a `/R/10/` navigation (zero PDF candidates →
  confirms direct download)
* `playground/research/hsbc_explore/listing_apis.json` — empty (no
  JSON XHRs intercepted on hub pages)
* `playground/research/hsbc_explore/reach_rpp{15,100,500}.html` —
  failed XHR-style direct-fetch attempts (auth wall; for reference)
