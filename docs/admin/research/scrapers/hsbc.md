# HSBC Global Investment Research — scraper notes

Status: **live** (since 2026-05-08). Scoped to macro/rates/FX/credit
via three productid filters 2026-06-02 (see
[#productid-scoping-2026-06-02](#productid-scoping-2026-06-02)).
Per-scope page 1 returns 35-46 rows; 25 fell inside today+7-days
window after dedup across scopes.

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

## productid scoping (2026-06-02)

The original crawler fetched the un-filtered firehose
(`productid=0`, all-products) and relied on
`classifiers/hsbc.py`'s Bloomberg ticker regex + `relevance.py`'s
single-name drop to remove equity. That worked but ingested ~half
the daily Reach catalogue before filtering.

After the 2026-06-02 in-portal nav probe
([taxonomy_probe/hsbc_deep.md](../../../../playground/research/taxonomy_probe/hsbc_deep.md))
revealed that HSBC's nav uses `productid` to scope its own product
homes, the crawler now walks three scoped listings instead:

| Scope | URL | Product space |
|---|---|---|
| economics | `?productid=5&variant=P53` | `Economics` + cross-listed |
| fx        | `?productid=3&variant=P30` | `Currencies` + cross-listed (HSBC lumps Commodities under CurrencyHome) |
| rates     | `?notproductid=8&variant=P38` | Fixed Income — `Credit Strategy`, `Rates`, etc. (excludes Equity Strategy product 8) |

Each scope opens its own `page` in the persistent context so
`rcRedisplayReportsTab` JS binds to the scoped landing's document
state. Article shortIds dedupe across scopes via `by_uuid`.

### Verification (deep probe, [taxonomy_probe/hsbc_full.md](../../../../playground/research/taxonomy_probe/hsbc_full.md))

One-page sample per scope on 2026-06-02:

| Scope | Rows | Single-name (Bloomberg ticker in title) | Sector / macro |
|---|---|---|---|
| economics | 38 | **0 (0%)** | 38 |
| fx        | 35 | **0 (0%)** | 35 |
| rates     | 46 | **0 (0%)** | 46 |

**119 pubs, 0 single-name leakage across all three scopes.** The
productid filter does the gating server-side — `_BB_TICKER` regex
in `classifiers/hsbc.py` and the downstream `relevance.py` drop now
serve as belt-and-suspenders for the rare cross-listed equity piece.

### Per-scope product-column composition

| Scope | Top products in `cells[3]` |
|---|---|
| economics | `Economics` (24) + multi-product cross-lists ("Economics , more... Currencies Rates Equity Strategy Asset Allocation") |
| fx        | `Currencies` (21) + multi-product cross-lists |
| rates     | `Credit Strategy` (15) + `Credit Strategy , more... Credit - High Grade Credit - High Yield` (9) + `Rates` (8) |

The "rates" scope label is mildly misleading — it's effectively
Fixed Income (Credit + Rates). Multi-product cross-lists where a
piece touches Economics/Currencies/Rates naturally surface across
all three scopes — dedup catches them.

### Cross-check against Deepak's hsbc-playwright profile

To validate the 3-scope choice independently, we mined Deepak's
inherited browsing profile at
`Z:\Business\Personnel\Arjun\playwrights\hsbc-playwright` and grouped
every URL he hit by path + query-shape. See
[taxonomy_probe/hsbc_deepak_gaps.md](../../../../playground/research/taxonomy_probe/hsbc_deepak_gaps.md).

| Deepak's URL | Visits | Our scope? |
|---|---|---|
| `Reach?productid=5&variant=P53` (Economics) | 13 | ✓ economics |
| `Reach?productid=3&variant=P30` (FX/Currencies) | 13 | ✓ fx |
| `Reach?notproductid=8&variant=P38` (Fixed Income) | 10 | ✓ rates |
| `Reach` (bare landing) | 14 | implicit landing redirect |
| `/ibcom/.../internal/login` | 3 | SSO transit |
| `/R/10/LPBwzZwGCzXQ` (direct report) | 2 | individual PDF nav |
| `Reach?searchbox=Precious Metals&tab=all` | 1 | **not scoped — see note** |

**Conclusion**: Deepak's day-to-day browsing pattern matched our 3
scopes exactly — same productid values, same variant codes. The one
URL outside our scopes was a single ad-hoc free-text search for
"Precious Metals" — that's interactive exploration, not a recurring
ingest pattern. Commodities content otherwise arrives via the `fx`
scope (HSBC lumps Commodities under `CurrencyHome` / `productid=3`).

`IndexedDB` does not exist on this profile (Reach isn't a SPA);
`Local Storage` leveldb scan found no cached scope URLs. Nothing more
to mine.

### Things observed but NOT wired

| Observation | Why not |
|---|---|
| `/O/{token}` aggregate URLs (19 across 3 scopes) | Landing-page indexes ("Macro Matters", "First Light"), no PDFs |
| Sub-title as separate `<div>` from title `<a>` | Currently concatenated into cells[1]; not blocking |
| Structured analyst ID via `openAnalystProfilesPage("331555")` | Useful for dedup but not filtering — deferred |
| Video flag `<img short_video.png>` | Already covered by "Video:" title prefix |
| `data-*` row attributes | None present — only `class="reportTableRow"` |
| Standalone `Sustainability` pubs (no cross-list) | Out of scope for macro/rates/FX/credit goal |

## Hard taxonomy probe + tightening (2026-06-03 formalisation)

HSBC had a substantive tightening pass on **2026-06-02** —
documented in the *Classifier & relevance filtering* and *productid
scoping* sections above. The 2026-06-03 formalisation pass added
the standard Phase-8 artefacts: DB audit, 7-day smoke in standard
format, and cleanup bucket for residual leakers.

### What was already done (2026-06-02 — see sections above)

1. **productid scoping** — `economics` (`productid=5`), `fx`
   (`productid=3`), `rates` (`notproductid=8`). Walks three
   server-side filtered listings instead of the all-products
   firehose. Deep probe verified 0/119 single-name leakage across
   all three scopes.
2. **Bloomberg-ticker single-name regex** in
   `classifiers/hsbc.py:_BB_TICKER` — `\(SYM EXCH\)` with bounded
   `\b` guards and 2-9-char SYM. 100% precision on the 3-day probe
   (5/15 dropped, 0 false positives).
3. **60-row backfill cleanup** via
   [`cleanup_hsbc_single_name.py`](../../../../playground/research/cleanup_hsbc_single_name.py).
4. **Deepak cross-check** — confirmed 3-scope choice matches his
   day-to-day browsing pattern (Reach?productid=5/3 + Reach?
   notproductid=8, no other scopes).

### Phase-8 standard artefacts (added 2026-06-03)

**DB audit**
([`taxonomy_probe/hsbc_db_audit.md`](../../../../playground/research/taxonomy_probe/hsbc_db_audit.md)) —
56 rows post-cleanup. Three issues found:

| issue | count | resolution |
|---|---|---|
| **5 non-canonical `asset_class`** rows from a single broken ingest 2026-05-21 (`Equities` ×2, `Currencies` ×2, `Economics` ×1 — captured rendered product-column text verbatim) | 5 | Bucket 12 DELETE → re-ingest under productid scoping classifies cleanly |
| 2 chart-pack duplicates (`European and US Credit: Weekly Chartpack`) | 2 | Bucket 12 DELETE |
| Zero region/country tag coverage on 56/56 rows | known gap | HSBC product field is generic (`Economics`/`Currencies`/`Rates`); would need title parsing — deferred |

Bucket 12 added to
[`cleanup_tier1_junk.py`](../../../../playground/research/cleanup_tier1_junk.py):
`hsbc-leakage` — DELETEs the 5 noncanonical + 2 chart-pack dupes.

**7-day smoke**
([`smoke_hsbc_7day.py`](../../../../playground/research/smoke_hsbc_7day.py))
in standard format (mirrors smoke_anz_7day.py / smoke_nomura_7day.py).
Log at
[`taxonomy_probe/hsbc_smoke_7day.log`](../../../../playground/research/taxonomy_probe/hsbc_smoke_7day.log).
The discovery-only legacy smoke
[`smoke_hsbc_scoped_discover.py`](../../../../playground/research/smoke_hsbc_scoped_discover.py)
is kept as the productid-wiring validator.

| stage | count |
|---|---|
| discovery kept (3 scopes deduped) | 22 (~3/day) |
| relevance kept | **22 (100%)** — single-name caught upstream by productid scoping |

**Composition** — pure macro/rates/fx/credit, zero EQUITY:

| class | count | % |
|---|---|---|
| MACRO | 9 | 41% |
| FX | 6 | 27% |
| RATES | 5 | 23% |
| STRATEGY | 1 | 5% |
| CREDIT | 1 | 5% |

`publication_type` 100% populated; `analysts` 100%. Region/country
tags 0% (the known gap).

**Sample kept titles**:
- MACRO: *"ECB Preview (June) Summer hiking (but for how long?)"*, *"Mexico Economics Robust exports offset subdued domestic conditions"*, *"Commodity Prices Snapshot Hormuz still closed…super-squeeze continues"*
- RATES: *"Global Rates Supply Outlook"*, *"Mexico Rates F-TIIE 2s10s Steepener"*, *"UK LDI/BPA update Resilience"*
- FX: *"HSBC Positioning Indicators"*, *"LatAm FX Trade Idea Sell USD-COP 2m NDF"*, *"FX - The week in 60 seconds"*
- CREDIT: *"European and US Credit: Weekly Chartpack"* (1 row; the duplicates are in the cleanup bucket)

### Why no code changes in this Phase-8 pass

Unlike other vendors where Phase 8 added new structured fields
(JPM bare scalars, MS cinfo, Goldman aemTags, etc.), HSBC's
existing **productid scoping** + **title-ticker regex** already
achieves the Phase-8 goal: zero single-name leakage, clean
macro/rates/fx/credit composition. The 2026-06-03 pass formalised
the artefacts (smoke, db audit, cleanup bucket) without changing
the crawler/filter/classifier.

## Files

* [`crawler_hsbc.py`](../../../../playground/research/ingest/crawler_hsbc.py)
* [`classifiers/hsbc.py`](../../../../playground/research/ingest/classifiers/hsbc.py) — product → asset_class + ticker mining
* [`ingest_today_hsbc.py`](../../../../playground/research/ingest_today_hsbc.py)
* [`smoke_hsbc_7day.py`](../../../../playground/research/smoke_hsbc_7day.py) — Phase-8 standard smoke (relevance + classifier + composition breakdown)
* [`smoke_hsbc_scoped_discover.py`](../../../../playground/research/smoke_hsbc_scoped_discover.py) — discovery-only smoke (productid wiring validator)
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
