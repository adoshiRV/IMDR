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

## Hard taxonomy probe + tightening (2026-06-03)

Probe artefacts in
[`taxonomy_probe/nomura_full.md`](../../../../playground/research/taxonomy_probe/nomura_full.md),
[`taxonomy_probe/nomura_db_audit.md`](../../../../playground/research/taxonomy_probe/nomura_db_audit.md),
[`taxonomy_probe/nomura_full_sample_star.json`](../../../../playground/research/taxonomy_probe/nomura_full_sample_star.json).
Re-runnable probe at
[`probe_nomura_full.py`](../../../../playground/research/probe_nomura_full.py).

### Key win — `assetClassId` scalar + `companies[]` single-name signal

The crawler was mapping 9 of 62 fields on the ES response. Probe
surfaced two strong vendor-native signals we were ignoring:

| field | values | role |
|---|---|---|
| **`assetClassId`** | 4-value enum: `EQ` / `FI` / `FX` / `EC` | Tier-0 asset-class scalar (Nomura's MS-`ASSET_CLASS_LEVEL2` analogue) |
| **`companies[]`** | array of `{ticker, securityType, name, id}` populated on ~63% of docs | Single-name detection — `assetClassId=="EQ" AND companies!=[]` is deterministic |
| `publishingOrganisation` | 5-value enum (`JE`/`AE`/`FI`/`FX`/`EC`) | publishing desk; JE+AE = single-name equity desks |
| `themes` / `subThemes` | curator macro vocab (`Central Bank`, `BOJ`, `Inflation`, `Fiscal Policy`) | sparse (29% / 23%) — emitted as TAG_THEME |
| `reportTitles[].en` | publication-series enum | noise denylist signal (`MBS Data Reports`, `Japan Small Cap`, `Agency * Report`) |
| `deleted` / `displayInGRP` / `replacementPublicationId` | vendor lifecycle flags | drop superseded / hidden / deleted rows |

### Filter precedence (added 2026-06-03)

`filters/nomura.py` — first match wins:

1. **`vendor-deleted`** — `deleted == true`
2. **`not-displayed`** — `displayInGRP == false`
3. **`superseded:<id>`** — `replacementPublicationId` set
4. **`noise-report-title:<name>`** — `reportTitles[].en` substring match against `{mbs data reports, japan small cap, agency mbs lockup, agency mbs buyout, gnm buyout reports, fhl exchange reports}`
5. **`single-name-equity:companies=<n>`** — `assetClassId == "EQ" AND companies != []` (gated by `drop_single_name`)
6. **`title-prefix:'<p>'`** — legacy admin

### Classifier — Tier-0 from assetClassId

`classifiers/nomura.py`:

1. **Tier-0**: `assetClassId` → canonical: `EQ→EQUITY`, `FX→FX`,
   `EC→MACRO`, `FI→split` (RATES default; CREDIT if `assetClasses[]`
   contains Credit / Securitized / MBS / CLO / ABS / HY).
2. **Tier-1**: `assetClasses[].en` string substring match (legacy).
3. **Tier-2**: pubtype + title text-regex (legacy MBS/CLO fallback).

**Tickers** emitted from both `companies[]` (new, structured) AND
title-mined `(TICKER EX)` patterns (legacy) — deduped while
preserving order.

**Themes** from `themes` + `subThemes` lists → `TAG_THEME`
(capped 5 + 3 to avoid bloated tag sets on multi-themed reports).

### DB audit (378 rows, 2026-05-07 → 2026-06-01)

| issue | count | severity |
|---|---|---|
| **Non-canonical `asset_class`** — Nomura publication series leaking ("Equity Report" 14, "MBS Data Reports" 14, "Japanese Equity Quantitative S" 5 truncated, "Strategy Trade" 3, …) | **83 (22%)** | classifier wrote pubtype into asset_class when no rule matched |
| Empty `asset_class` | 12 (3%) | classifier returned "" |
| **Single-name EQUITY leakage** — `(Buy)/(Sell)/(Neutral)/(Reduce)` rating-flag titles | **~49 (36% of EQUITY)** | no ticker tags exist → ticker-count detector couldn't catch them |
| Region tag coverage | 81.5% (good) | — |
| Country coverage | thin (JP/WW/EU only) | — |
| Encoding corruption / podcast leakage | 0 | clean |

Bucket 11 added to
[`cleanup_tier1_junk.py`](../../../../playground/research/cleanup_tier1_junk.py):
`nomura-leakage` — DELETEs ~144 rows (83 non-canonical + 12 empty +
49 single-name EQUITY with rating-flag titles). Re-ingest under
Tier-0 + new single-name filter cleans them.

### 7-day smoke (2026-06-03)

Read-only via
[`smoke_nomura_7day.py`](../../../../playground/research/smoke_nomura_7day.py).
Log at
[`taxonomy_probe/nomura_smoke_7day.log`](../../../../playground/research/taxonomy_probe/nomura_smoke_7day.log).

| stage | count |
|---|---|
| raw cards processed | ~385 |
| discovery drops | **269** — 254 `single-name-equity:companies=N`, 36 `noise-report-title:MBS*`, others |
| discovery kept | 116 (~17/day) |
| relevance kept | **116 (100%)** — no relevance drops needed (single-name caught at discovery) |

**Structured-field coverage on survivors**: `assetClassId` 100%,
`publishingOrganisation` 100%, `companies` 0% (all populated cards
caught at discovery — exactly the intent), `themes` 29%,
`subThemes` 23%.

**Composition** — clean macro/rates/fx with sector EQUITY:

| class | count | % |
|---|---|---|
| FX | 33 | 28% |
| MACRO | 29 | 25% |
| RATES | 28 | 24% |
| EQUITY | 26 | 22% |

Zero non-canonical asset_class, zero empty — the 36-row leak hole
is plugged at source.

**Country coverage** (was JP/WW/EU only pre-fix): JP 65, WW 7, EU 2.
**Region**: apac 101, global 19, americas 18, emea 9.

The 26 EQUITY survivors are sector / quant / multi-name research
(`Japanese equities factor geek`, `Japan Research Pack`,
`China factory automation data`, `Rolled aluminum product
statistics`) — no single-name leakage. The 254 single-name-equity
drops are textbook stock notes with `(Buy)/(Neutral)/(Sell)` flags
(e.g. *"Tokyo Century (8439 JP) (Buy)"*, *"Sony Financial Group
(8729 JP) (Buy)"*, *"Adani Port & SEZ (ADSEZ IN) (Buy)"*).

**Deepak cross-check** (`taxonomy_probe/nomura_deepak.md`):
Economics 20 visits, FX 9, Macro Strategy 9, Rates 9 — pure macro
focus, zero equity-research visits. Confirms scope.

**Sample kept titles**:
- MACRO: *"Asia Insights - Korea: Strong chip prices drive exports higher"*, *"First Insights - Euro area: Services prices drive inflation higher"*, *"US Daily Commentary - Review & Preview"*
- RATES: *"Yen RV Analytics"*, *"Yen Rates Daily Monitor"*, *"Australia Rates Insights"*, *"Nomura Quant Insights - AI rally"*
- FX: *"FX Insights - Inflows to US equities accelerated"*, *"JPY Intraday Comment"*, *"USD/CNY fix model - Projection: 6.7762"*

## Last verified

2026-05-07 — pipeline working end-to-end via the new ES search API.
**~107 reports/day** in English (was ~31 with DOM scrape of /m/Home).
Per-PDF wall-clock ~5-7s with embed off.

2026-06-03 — `assetClassId` Tier-0 + `companies[]` single-name
drop + noise-report-title denylist + vendor-lifecycle flags
(deleted/displayInGRP/replacementPublicationId) landed in
playground (gitignored). 7-day smoke shows **~17/day kept** (was
~100/day raw with single-name pollution), 100% kept at relevance,
clean FX 28% / MACRO 25% / RATES 24% / EQUITY 22% (all sector).
269 discovery drops (~70% drop rate, mostly single-name stock
notes).

## Noise filter update (2026-06-10)

Shared cross-vendor noise classifier wired into
[`ingest/filters/_noise.py::classify_noise`](../../../../playground/research/ingest/filters/_noise.py)
and called as the final fallback inside [`filters/nomura.py::should_exclude`](../../../../playground/research/ingest/filters/nomura.py).
Three universal title-pattern families plus a cross-vendor EQUITY
conference / sales-event drop in [`relevance._is_equity_conf_event`](../../../../playground/research/ingest/relevance.py).

Smoke against the full 4,498-title `research.dim_report` corpus dropped
**18 nomura docs**:

| family | n | sample |
|---|---|---|
| chart-pack | 2 | Agency MBS Chart Book - Conventional 30-Year MBS; Japan Equity Flow Monitor (Chart Book) June 26 |
| morning-note | 14 | Matsuzawa Morning Report - <subject> (14 daily Japan equity sales-trader recaps) |
| event-admin | 0 | (none — covered by existing EXCLUDED_TITLE_PREFIXES tuple) |
| conf-event (EQUITY only) | 2 | Quick Note - Chipbond Technology Corporation (6147 TT); Quick Note - Global AI Trend Tracker (corporate-event content) |

The conf-event rule fires only when `result.asset_class == EQUITY` so
MACRO-tagged "Takeaways" / "Trip Notes" titles (real policy / sovereign
macro content) pass through unaffected.

Test pins: [`test_noise_filter.py`](../../../../playground/research/test_noise_filter.py)
(116 chart-pack / morning-note / event-admin assertions),
[`test_relevance_conf_event.py`](../../../../playground/research/test_relevance_conf_event.py)
(35 conf-event assertions). Re-runnable smoke harnesses:
[`_smoke_noise_filter.py`](../../../../playground/research/_smoke_noise_filter.py),
[`_smoke_conf_event.py`](../../../../playground/research/_smoke_conf_event.py).

## Content audit (2026-06-15)

Last updated: 2026-06-15

Two additional drop layers added to `filters/nomura.py` based on a
content audit of surviving publications — both operate in `should_exclude`
after the noise-report-title and single-name-equity checks.

### Layer 1 — `_CHART_ONLY_TITLE_PREFIXES` (new prefix drops)

Five low-value series where extracted text is title + disclaimer with
near-zero analytical prose (chart images only, unreadable by PyMuPDF):

| prefix | series description |
|---|---|
| `usd/cny fix model` | FX fixing model — pure model-output table |
| `g10 fx month-end model` | month-end FX model output — trade table + disclaimer |
| `fx and rates portfolio update` | position table, minimal prose |
| `credit portfolio update` | position table, minimal prose |
| `macro portfolio update` | position table, minimal prose |

These are anchored title-prefix matches (case-insensitive after
`normalize_title`). Matched via the same `match_title_prefix` helper as
`EXCLUDED_TITLE_PREFIXES`, then `classify_noise` is the final fallback.

Note: in the 7-day smoke the "USD/CNY fix model" series appeared in the
kept set under FX (e.g. *"USD/CNY fix model - Projection: 6.7762"*) —
it is now dropped.

### Layer 2 — prose-density gate (high-volume number-dump series)

The following high-volume series are NOT in the per-series prefix list
because they are caught further upstream by the shared prose-density
gate (digit-density threshold in `_noise.py`):

| series | token volume | description |
|---|---|---|
| Yen RV Analytics | ~89k tokens/day | Yield-curve table dump |
| Yen Rates Daily Monitor | ~89k tokens/day (combined est.) | Daily JGB analytics |
| SDR FX Analysis | high | SDR basket FX data table |
| Agency MBS Chart Book | high | MBS chart deck (now also caught by chart-pack family) |
| Agency Worst Billion / Prepayment / Lockup / Issuance / Buyout reports | high | Agency MBS operational data |
| FHL Exchange Report | high | FHLB exchange data table |
| FX and Rates Weekly Analytics | high | Weekly analytics table dump |

These series are digit-heavy enough that the prose-density gate fires
independently; the `_CHART_ONLY_TITLE_PREFIXES` list is defence-in-depth
for any image-only variants that slip the density check.

