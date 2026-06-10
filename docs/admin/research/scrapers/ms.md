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

## Hard taxonomy probe (2026-06-02)

Full read-only probe of the search-API response shape. Detailed
field-by-field write-up in
[`taxonomy_probe/ms_full.md`](../../../../playground/research/taxonomy_probe/ms_full.md);
the staged probe script
[`probe_ms_full.py`](../../../../playground/research/probe_ms_full.py)
is **un-run** (would need browser launch + login).

### Key finding — we throw away ~80% of the listing payload

The `reportcards[i]` card carries ~25 keys. The crawler currently
maps **5** (`id`, `pd`, `hl`, `ab`, `a`). Every taxonomy signal
sits in the unparsed remainder:

| card field | sample | role |
|---|---|---|
| `dt` / `af` | `application/pdf` / `pdf` / `html` / `ppt` / `audio/*` / `video/*` | format — drop non-PDF at card stage instead of paying the per-uuid frontmatter GET |
| `lang` | `eng` | language (server-side already filters this in `idol[0].hr`, but no harm checking) |
| `pn` | `Idea` / `Insight` / `Foundation` / `Update` | coarse business-group analogue (4 values) |
| `pst` / `pstc` | `Note` / `StandaloneRiskReward` / `Audio` / `Video` / `BluePaper` / `Earnings` … | finer publication-subtype |
| `pc` / `pcat1` | `9` / `PublisherDefined` | numeric product code + category |
| `topic` | `Gold Fields Limited` | usually the *company name* on single-name notes — single-name signal |
| `pt` | `GFIJ.J` | primary ticker |
| `cinfo.srcinfo[]` | `[{ticker:"GFIJ.J", src:"Equal-weight", isAtp:true}]` | **non-empty ⇔ MS has a stock rating ⇔ single-name research** |
| `cinfo.ptcinfo[]` | `[{ticker:"GFIJ.J", ptc:"77000.00", cy:"ZAX"}]` | price-target list — same precedence |
| `cinfo.ivcinfo[]` | `[{industry:"EEMEA - Metals & Mining", ...}]` | sector taxonomy |

Frontmatter (per-uuid, second hop) carries `productType`,
`topicHeadline`, **`region`** (`EEMEA`/`Europe`/`Asia Pacific`/
`North America`/`Global`/`Latin America`), `industryViewDetails[]`.
Today only `topicHeadline` is used; `region` is harvested but
hardcoded to `country_code = None` at `classifiers/ms.py:168`.

Server-side curation DSL embedded in
`portal-content-service/content/auto/Home` reveals MS's internal
query language:
`(product==PC10);(periodical!=Audio);(periodical!=Video);
(productsubtypecode!=DataPackage);(articleformat!=pdf);…` —
i.e. `product`, `periodical`, `productsubtypecode`, `articleformat`
are server-side queryable knobs we might push the entire filter onto.

### Filter design — MS Tier-0 (deterministic, vendor-native)

Same shape as JPM's `filters/jpm.py`, multi-signal — MS scatters the
businessGroup analogue across `pn`/`pst`/`pstc`. Precedence (first
match wins):

1. **format drop**: `dt != "application/pdf"` AND `af != "pdf"` → drop at card stage (saves N frontmatter hops)
2. **language drop**: `lang not in {"eng",""}` → drop (parallels Barclays' belt-and-braces language filter)
3. **single-name drop**: `len(cinfo.srcinfo) > 0` OR `len(cinfo.ptcinfo) > 0` OR (`pt` non-empty AND `topic` is a company name) → drop, gated by `Settings.research_drop_single_name_equity`
4. **pst exclude-list**: `pst in {"Audio","Video"}` AND no transcript-PDF → drop
5. **title-prefix admin drops**: unchanged (today's 5 prefixes)

### Tier-0 classifier (asset_class assignment)

Lift the same approach as JPM: map structured signals → canonical
class before falling back to title regex.

```
productType / pn / pst / pstc / topicHeadline / hub-slug
                       ↓
   { MACRO | RATES | FX | CREDIT | COMMODITIES | EQUITY | STRATEGY }
                       ↓
       fall back to title regex (today's logic) only if blank
```

The 18 non-canonical asset_class rows in the DB audit (§ DB cleanup
log below) are exactly the rows where the classifier wrote the raw
MS series name into `asset_class` because Tier-0 was missing.

### Live-probe enumerations (2026-06-02)

Full dumps + reasoning in
[`taxonomy_probe/ms_enums.md`](../../../../playground/research/taxonomy_probe/ms_enums.md).
The probe hit three endpoints with our profile cookies:

- `POST /portal-content-service/search` (50 cards, full body)
- `GET  /portal-data-service/data/lookupall/allbylanguagecode` (1.7MB master taxonomy)
- `GET  /portal-content-service/content/auto/Home` (curation DSL)

**Headline**: the cards themselves carry **NO `assetClass*` field**.
MS publishes its taxonomy *separately* via `lookupall` (18 entity
types including `ASSET_CLASS_LEVEL2` (8 buckets) + `ASSET_CLASS_LEVEL3`
(43 sub-buckets) + `REGION` (9) + `PRODUCT` (5 PC?? codes) + `COUNTRY`
(249) + `INDUSTRY` (275) + `SECTOR` (11) + `GICS_INDUSTRY` (84) +
`PRODUCT_SUBJECT` (35) + `REPORT_TYPE` (12) + `THEME` / `COLLECTION` /
`PERIODICAL` / `DISCIPLINE` / `AUTHOR`). Asset class must be derived
client-side by joining the card's `pn`/`pst`/`topic`/`a.role`/
`cinfo.ivcinfo[]` against this catalog.

**ASSET_CLASS_LEVEL2 → canonical mapping** (8 buckets, all confirmed):

| ACL2 | → canonical |
|---|---|
| Commodities | COMMODITIES |
| Credit Derivatives, Credit Strategy, Securitized Products | CREDIT |
| Currencies / FX | FX |
| Global Economics | MACRO |
| Interest Rates | RATES |
| Emerging Markets | split via ACL3 (Sovereign/Corporate Credit → CREDIT; Currency/FX → FX; else MACRO) |

**PRODUCT codes (5)** — `pn` field on cards maps 1:1:
`PC10=BluePaper`, `PC20=Insight`, `PC30=Idea`, `PC40=Update`, `PC50=Foundation`.

**REGION (9)** — matches `frontMatter.region` exactly:
AXJ (Asia Emerging Markets), Asia Pacific, EEMEA, Europe, Eurozone,
Global, Japan, Latin America, North America.

**Single-name skew is severe.** In the 50-card live window (2026-06-02):

| signal | count |
|---|---|
| `cinfo.srcinfo` non-empty | **47/50** |
| `cinfo.ptcinfo` non-empty | 47/50 |
| `pt` non-empty | 39/50 |
| `af != "pdf"` (html/xls — wasted frontmatter call today) | 15/50 |

~94% of the most-recent MS publications in the date-sort window are
single-name equity. Current filter drops zero of them. Adding the
`cinfo.srcinfo`-non-empty drop would slash ingest ~10× and only keep
the macro/rates/fx/credit/commodities flow.

**Facet probing — 0/6 succeeded.** The server rejects undocumented
`compositeRequest` keys (`facets`, `includeFacets`, `aggs`,
`aggregations`, `returnFacets`, `facetFields`) with HTTP 400.
Take-away: there is no in-band aggregation endpoint; we use
`lookupall` for the universe instead.

**MS-internal curation DSL** is visible in `auto/Home`:
`(product==PC10);(periodical!=Audio);(productsubtypecode!=DataPackage);
(articleformat!=pdf);(articleformat!=ppt)` — this is the
front-end's filter language. Pushing our entire Tier-0 filter
server-side via this DSL is an open idea (not yet attempted; would
need DEV/QA traffic to find the compositeRequest field that accepts
it).

## Deepak cross-check (2026-06-02)

Full extraction at
[`taxonomy_probe/ms_deepak.md`](../../../../playground/research/taxonomy_probe/ms_deepak.md).

Deepak's browser history at `Z:\Business\Personnel\Arjun\
playwrights\ms-playwright\Default\History` shows:

| hub slug | visits |
|---|---|
| `asia_pacific_economics` | 46 |
| `fx_em_strategy` | 30 |
| `japan_economics` | 30 |
| `fx_g10_strategy` | 29 |
| `commodities` | 28 |
| `rates_strategy` | 7 |
| `global_macro_strategy` | 3 |
| `global_fx_strategy` | 3 |

Zero equity-research, zero wealth-management, zero S&T-tool visits.
Pure macro/rates/fx/commodities with Asia-Pacific bias. Our crawler
hits `/home/global` (the master cross-asset feed) so we mechanically
capture everything he browses; the question is purely **what we
keep**. The DB audit shows we currently leak single-name equity into
non-EQUITY classes — Deepak would not have looked at any of them.

## DB cleanup log

### Tier-1 junk sweep (2026-06-02) — initial

The DB audit
([taxonomy_probe/db_audit_2026_06_02.md](../../../../playground/research/taxonomy_probe/db_audit_2026_06_02.md))
flagged **5 MS rows** where the classifier wrote a company name (not
a canonical asset class) into the `asset_class` column:

* `Metlen Energy & Metals PLC` (×2)
* `Ningbo Ronbay New Energy Techn`
* `BAIC BluePark New Energy`
* `India Fuel Retailers`

Double bug: wrong `asset_class` *and* the rows are single-name
equity that should have dropped at `relevance.is_single_name_equity`.
All 5 rows removed by
[`playground/research/cleanup_tier1_junk.py`](../../../../playground/research/cleanup_tier1_junk.py)
2026-06-02.

### MS-targeted audit (2026-06-02) — full picture

Full breakdown in
[`taxonomy_probe/ms_db_audit.md`](../../../../playground/research/taxonomy_probe/ms_db_audit.md).
164 rows total, 2026-05-07 → 2026-06-01. Three clusters of junk
remain on top of the 5 already swept:

| priority | issue | count | action |
|---|---|---|---|
| HIGH | HTML entities in `title` (`&ndash;`, `&amp;`, `&rsquo;`, `&auml;`) | 23 | `html.unescape()` in crawler + retroactive UPDATE |
| HIGH | Non-canonical `asset_class` (raw MS series name written verbatim, often truncated at varchar(30)) | 18 | Reclassify via Tier-0 to canonical (all 18 also have zero `map_report_tag` entries — single early-ingest bug, dates cluster on 2026-05-20/21) |
| HIGH | Single-name equity leakage via company-name `vendor_pubtype` into MACRO/COMMODITIES/CREDIT | 14 | Drop at discovery using `cinfo.srcinfo`/`ptcinfo`/`pt` (NOT title regex) |
| MEDIUM | Devon Energy duplicate (same title, two `report_id`s) | 2 | Verify via `content_hash`, dedupe |
| MEDIUM | Zero region/country coverage (164/164 rows have empty `region` and NULL `country_id`) | 164 | Persist frontmatter `region` (already on the wire) |

Confirmed single-name leakers ingested wrong:
AirTAC International, AppLovin Corp, Ashok Leyland, Bridgestone,
Credit Agricole (×2), Devon Energy (×2 — duplicate),
Gujarat Energy, LifeStance Health, Shanghai Putailai New Energy,
Siemens Energy, Stora Enso, Yokohama Rubber. None were tagged
EQUITY; they leaked into MACRO (6) / COMMODITIES (6) / CREDIT (2).

## Last verified

2026-05-07 — pipeline working end-to-end via search-API listing.
**~579 reports/day** in window after frontmatter resolution
(was ~14 from DOM scrape of /home/global). Per-PDF wall-clock
~3s with embed off.

2026-06-02 — hard taxonomy probe + DB audit complete; code
changes pending (Tier-0 classifier, single-name drop on
`cinfo.srcinfo`/`ptcinfo`, format-stage drop on `dt`/`af`,
`html.unescape()` on title, persist `region`).

2026-06-02 — code package landed in playground (gitignored):
extended `ReportRef` with 10 structured fields, added
`should_exclude_by_card`, Tier-0 classifier using topicHeadline →
ACL2 → canonical, cleanup buckets 4-6, `smoke_ms_7day.py`.

## 7-day smoke (2026-06-02)

Read-only run via
[`playground/research/smoke_ms_7day.py`](../../../../playground/research/smoke_ms_7day.py).
Logs at
[`taxonomy_probe/ms_smoke_7day_v2.log`](../../../../playground/research/taxonomy_probe/ms_smoke_7day_v2.log).

**Filter-bug fix (v1 → v2)**: the first pass dropped on the card's
`af` field (`pdf` / `html` / `xls` / `ppt`) — but `af` is the
front-end **viewer format**, NOT the underlying doc type. The probe
sample showed every PDF-bearing card ships `dt='application/pdf'`
**with** `af='html'` (MS just renders PDFs as HTML in the browser).
v1 mass-dropped ~99% of the macro/rates/fx/credit stream as
`format:html`. v2 keys the filter off `dt` instead — recovers the
real PDF cards. Diff is one constant + a one-word docstring change
in [`filters/ms.py`](../../../../playground/research/ingest/ms.py).

**Volume — 7-day window (since=2026-05-26 until=2026-06-02):**

| stage | count | comment |
|---|---|---|
| raw cards processed | ~1500 | ~212/day |
| discovery drops | 1214 | `single-name:cinfo` 787, `doctype:application/xls` 370, others 57 |
| discovery kept | 269 | post-filter pre-classifier |
| relevance kept | **136 (~19/day)** | clean macro/rates/fx/credit |
| relevance drops | 133 | all `single-name-equity:ms-default-drop` — sector EQUITY |

**Discovery breakdown:** 595 single-1-ticker + 56 single-2-ticker +
27 single-3-ticker + 26 single-4-ticker + … + 8 single-11-ticker —
the `cinfo.srcinfo` length distribution is the cluster-coverage
shape (most reports cover 1 stock; a few cluster-coverage notes hit
30+ tickers). All correctly dropped as single-name research.

**Kept distribution — clean macro/rates/fx/credit:**

| class | count | % |
|---|---|---|
| MACRO | 59 | 43% |
| CREDIT | 29 | 21% |
| STRATEGY | 20 | 15% |
| COMMODITIES | 13 | 10% |
| RATES | 11 | 8% |
| FX | 4 | 3% |

Zero EQUITY surviving — exactly the goal.

**Field coverage on kept refs:** `region` 100%, `publication_type`
100%, `industries` 40%, `cinfo-tickers` 0% (single-name caught at
discovery).

**Region distribution on kept refs:** americas 37, apac 32, emea 30,
global 27, latam 10. Country codes resolved for WW (27), EU (24),
JP (6); other regions emit only the broader `Tag('region', …)`.

**Sample kept titles:**
- MACRO: *"Chile and Peru Trip Notes: Fiscal Discipline, Reform
  Upside"* / *"Australia: Minimum Wage Increase of 4.75% for FY27"*
  / *"Disinflation, interrupted?"* / *"India: April-26 IIP Grows
  at a Faster Clip"*
- RATES: *"Why So Soft, Repo?"* / *"Government Bond Auctions: The
  Month Ahead"* / *"Downward Repricing of the Inflation Risk
  Premium"*
- FX: *"FX Positioning Indicates Investors Increased Long NZD
  Positions"* / *"The Disinflation Trade"*
- CREDIT: *"Private Credit in India – Opportunities and Risks"* /
  *"European ABS Chartbook"* / *"EM Technical Watch: Spotlight on
  Lower-Rated Issuers"*
- COMMODITIES: *"Strait of Hormuz - Daily Tracker #78"* / *"Weekly
  Oil Stock Summary"*
- STRATEGY: *"Weekly Warm-up: Fundamental Backdrop Improving for
  Cyclicals"* / *"Global In the Flow – May Recap"*

### Trade-off — strict drop on sector EQUITY (accepted 2026-06-02)

The 133 relevance drops are NOT single-name (those were caught at
discovery). They're **sector-level EQUITY** that the Tier-0
classifier couldn't map to a non-EQUITY canonical class
(topicHeadlines like *"Auto Parts"*, *"Brokers, Asset Managers &
Exchanges"*, *"IT Hardware"*, *"Chemicals"*, *"China Autos & Shared
Mobility"*). They fall through to the MS-default-drop branch in
`relevance.py:207-220`.

User decision 2026-06-02: **keep the filter strict** — accept
dropping sector EQUITY. The macro/rates/fx/credit stream is what
we want, and ~19/day of clean signal is the right shape. Revisit
if downstream users miss the sector wraps.

## Noise filter update (2026-06-10)

Shared cross-vendor noise classifier wired into
[`ingest/filters/_noise.py::classify_noise`](../../../../playground/research/ingest/filters/_noise.py)
and called as the final fallback inside [`filters/ms.py::should_exclude`](../../../../playground/research/ingest/filters/ms.py).
Three universal title-pattern families plus a cross-vendor EQUITY
conference / sales-event drop in [`relevance._is_equity_conf_event`](../../../../playground/research/ingest/relevance.py).

Smoke against the full 4,498-title `research.dim_report` corpus dropped
**4 ms docs**:

| family | n | sample |
|---|---|---|
| chart-pack | 4 | US Credit Strategy Chartbook; European ABS Chartbook; Chart of the Day: China's Manufacturing PMI vs. AirTAC's Monthly Sales |
| morning-note | 0 | (none — MS has no daily-recap series in current corpus) |
| event-admin | 0 | (none) |
| conf-event (EQUITY only) | 0 | (none — MS EQUITY default-drop already catches conf-takeaways via `single-name-equity:ms-default-drop`) |

The conf-event rule fires only when `result.asset_class == EQUITY` so
MACRO-tagged "Takeaways" / "Trip Notes" titles (real policy / sovereign
macro content) pass through unaffected.

Test pins: [`test_noise_filter.py`](../../../../playground/research/test_noise_filter.py)
(116 chart-pack / morning-note / event-admin assertions),
[`test_relevance_conf_event.py`](../../../../playground/research/test_relevance_conf_event.py)
(35 conf-event assertions). Re-runnable smoke harnesses:
[`_smoke_noise_filter.py`](../../../../playground/research/_smoke_noise_filter.py),
[`_smoke_conf_event.py`](../../../../playground/research/_smoke_conf_event.py).

