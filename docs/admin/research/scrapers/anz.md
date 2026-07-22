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
C:/IMDR_LOCAL/research_profiles/anz/
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

## Hard taxonomy probe + tightening (2026-06-03)

Probe artefacts in
[`taxonomy_probe/anz_full.md`](../../../../playground/research/taxonomy_probe/anz_full.md),
[`taxonomy_probe/anz_db_audit.md`](../../../../playground/research/taxonomy_probe/anz_db_audit.md),
[`taxonomy_probe/anz_full_sample.json`](../../../../playground/research/taxonomy_probe/anz_full_sample.json).
Re-runnable probe at
[`probe_anz_full.py`](../../../../playground/research/probe_anz_full.py).

### Key win — flip `param_layout=wide` → `full`

Same endpoint, same auth, same paging. Body grows 60KB → 95KB at
size=50. **Exposes `tile-tags` (Topic + Sub-Topic pair) and
`tile-authors` inline on ~94% of tiles** — zero additional HTTP
requests. Vendor-native structured taxonomy replaces the
hard-coded 45-row publication_type table as the primary signal.

Tile-tags format: `[Sub-Topic, Topic]` per tile, e.g.
`["Rates & bonds - Aust", "Rates & bonds"]`,
`["Crude oil", "Commodities"]`, `["USD", "Foreign exchange"]`,
`["Housing - Aust", "Property & infrastructure"]`. Topic (12-value
enum) is the asset-class signal; Sub-Topic carries the country
suffix (`- Aust` / `- NZ` / `- Asia` / `- China` / `- US` / `- G3`).

### Filter design (added 2026-06-03)

`filters/anz.py` — first match wins:

1. Title-prefix admin (legacy: `5 in 5 with anz`, `invite:`,
   `webcast:`, `conference call:`, `expert access:`)
2. Title-substring `"(podcast)"` (legacy)
3. **`pubtype:<name>`** — exact match against `_EXCLUDED_PUB_TYPES_EXACT`:
   * Audio/video: `Podcast`, `This Week in NZ Economics (Podcast)`,
     `Client Calls & Webinars`, `Credit Strategy Webinars`
   * Internal curation: `Shortlist`, `The Vault`
   * `5 in 5 with ANZ` (defensive — also caught by title-prefix)
4. **`pubtype-discontinued:<name>`** — any pubtype ending `(Discontinued)`
5. **`topic:Climate / Sustainability / ESG`** — not in IMDR scope today

Conservative cut — `Blue Lens` and `ANZecdotes` were initially
included in the drop list per the probe enumeration but the smoke
confirmed both are legitimate daily macro briefs. Removed.

### Classifier — Tier-0 from tile-tags (added 2026-06-03)

`classifiers/anz.py` — first match wins:

1. **Tier-0a:** Topic → canonical (12-value map): `Foreign exchange→FX`,
   `Rates & bonds→RATES`, `Credit strategy→CREDIT`, `Commodities→COMMODITIES`,
   `Economic indicators / Fiscal policy / Monetary policy / Forecast update / Property & infrastructure / ANZ-observed data→MACRO`,
   `Trade recommendations→STRATEGY`, `Climate / Sustainability / ESG→ESG`.
2. **Tier-0b:** Sub-Topic suffix → country/region: `- Aust→AU`,
   `- NZ→NZ`, `- China→CN`, `- US→US`, `- Asia→region=APAC`,
   `- G3 / - G10→region=GLOBAL`, `- Pacific→region=APAC`.
3. **Tier-1:** legacy publication_type table (45 rules, kept as fallback).
4. **Tier-2:** pubtype keyword fallback (kept).

Bug fix: `Australian Economic Update` (with trailing `n`) wasn't
matching the legacy table key `australia economic update` because
of substring asymmetry. Added an alias.

### DB audit (107 rows, 2026-05-06 → 2026-06-01)

| issue | count | severity |
|---|---|---|
| **Non-canonical `asset_class`** — series names ("Vietnam Insight", "NZ Morning Focus", "Monetary Policy Expectations", "AUD Midweek Highlights") | **28 rows (26%)** | classifier wrote pubtype into asset_class when no rule matched |
| Empty `asset_class` | 8 rows | classifier returned "" |
| Zero region/country coverage | **59/107 (55%)** | region was only 1 value (apac); 6 country codes total |
| 2026-05-11 weekly ingest gap (1 row vs 20-50) | — | scraper failure that week (separate issue) |
| Encoding corruption / single-name leakage | 0 | clean |

Bucket 10 added to
[`cleanup_tier1_junk.py`](../../../../playground/research/cleanup_tier1_junk.py):
`anz-noncanonical-ac` — DELETE all 36 leakers (28 non-canonical +
8 empty); they re-ingest under Tier-0 with correct asset_class +
country anchor.

### 7-day smoke (2026-06-03)

Read-only via
[`smoke_anz_7day.py`](../../../../playground/research/smoke_anz_7day.py).
Log at
[`taxonomy_probe/anz_smoke_7day_v2.log`](../../../../playground/research/taxonomy_probe/anz_smoke_7day_v2.log).

| stage | count |
|---|---|
| raw cards processed | ~59 |
| discovery drops | 10 — 4 Shortlist, 4 `(podcast)`, 1 The Vault, 1 5-in-5 |
| discovery kept | 49 (~7/day) |
| relevance kept | **49 (100%)** — no single-name to drop |

**layout=full coverage on survivors**: topic 100%, sub_topic 90%,
tile_authors 100%.

**Composition** — pure macro/rates/fx/commodities:

| class | count | % |
|---|---|---|
| MACRO | 33 | 67% |
| RATES | 8 | 16% |
| COMMODITIES | 4 | 8% |
| FX | 4 | 8% |

Zero EQUITY, zero CREDIT, zero (empty) — the 36-row leak hole is
plugged at source.

**Country coverage** (was 45% pre-smoke): AU 18, NZ 9, CN 2, KR 1.

**Sample kept titles** confirm signal quality:
- MACRO: *"Australia's wage decision and final Q1 2026 GDP estimate"* / *"Australia's housing market: slowdown accelerates"* / *"China's urban unemployment"* / *"ANZ-Roy Morgan Australian Consumer Confidence"*
- RATES: *"STIR Update: staying short AUD; tighter liquidity near term"* / *"Daily Rates RV Pack"* / *"AUD Rates Weekly Snapshot"*
- FX: *"FX Strategy Weekly: USD at crossroads"* / *"South Korea: KRW unfairly beaten down"* / *"Pacific Island currencies stronger against the USD"*
- COMMODITIES: *"Commodity Call: nickel market rebalancing"* / *"Global oil market tracker: issue 3"*

## Last verified

2026-05-07 — pipeline working end-to-end via the tile API
(``/document_data_tiled_all``). **~19 reports/day** in window
(unchanged from DOM scrape — ANZ daily volume is already small;
the API switch was for reliability + paginatability rather than
coverage). Per-PDF wall-clock ~12s with embed off (slow-path
redirect chain to S3 dominates).

2026-06-03 — layout=full + Tier-0 classifier + publication_type
drop-list landed in playground (gitignored). 7-day smoke shows
~7/day kept post-discovery (100% kept at relevance), pure
MACRO 67% / RATES 16% / COMMODITIES 8% / FX 8% composition, 100%
country/region coverage on survivors with Sub-Topic geo.

## Rates series rescue (2026-06-15)

The 2026-06-10 noise-filter wiring collapsed kept RATES from ~8/week to ~1/week
by routing three ANZ titles through `MORNING_NOTE_PREFIXES` in `_noise.py`.
User directive 2026-06-14: these series are wanted for rates-event coverage.

Fix: added `_ANZ_RATES_KEEP` in `filters/anz.py` with three entries:

```python
_ANZ_RATES_KEEP: tuple[str, ...] = (
    "daily rates rv pack",       # daily relative-value table, genuine rates signal
    "aud rates weekly snapshot", # weekly rates positioning summary
    "nzgb tender",               # NZ govt bond tender, hard rates-supply event
)
```

These were also **removed from `_noise.MORNING_NOTE_PREFIXES`** in `_noise.py`
(the comment there now says "used to be here too, but ANZ wants those KEPT").
The keep-override check runs at the end of `should_exclude` — after the pubtype
and topic drops — so it only fires when the title is not already dropped by a
harder signal. All other ANZ morning-notes (`australian morning focus`,
`nz morning focus`, `charts that matter`) continue to drop via the shared classifier.

Effect: RATES recovered from ~1/week to ~6/week.

## Noise filter update (2026-06-10)

Shared cross-vendor noise classifier wired into
[`ingest/filters/_noise.py::classify_noise`](../../../../playground/research/ingest/filters/_noise.py)
and called as the final fallback inside [`filters/anz.py::should_exclude`](../../../../playground/research/ingest/filters/anz.py).
Three universal title-pattern families plus a cross-vendor EQUITY
conference / sales-event drop in [`relevance._is_equity_conf_event`](../../../../playground/research/ingest/relevance.py).

Smoke against the full 4,498-title `research.dim_report` corpus dropped
**56 anz docs** (prior to the 2026-06-15 rates-rescue fix):

| family | n | sample |
|---|---|---|
| chart-pack | 3 | NZGB tender preview chart pack and supply guidance |
| morning-note | 53 | Australian Morning Focus / NZ Morning Focus / Daily Rates RV Pack / Charts that Matter |
| event-admin | 0 | (none — covered by existing EXCLUDED_TITLE_PREFIXES tuple) |
| conf-event (EQUITY only) | 0 | (none in current corpus) |

Note: the 2026-06-15 fix removed "Daily Rates RV Pack", "AUD Rates Weekly
Snapshot", and "NZGB tender" from `MORNING_NOTE_PREFIXES`, so those 3 of the 53
morning-note drops are rescued going forward.

The conf-event rule fires only when `result.asset_class == EQUITY` so
MACRO-tagged "Takeaways" / "Trip Notes" titles (real policy / sovereign
macro content) pass through unaffected.

Test pins: [`test_noise_filter.py`](../../../../playground/research/test_noise_filter.py)
(116 chart-pack / morning-note / event-admin assertions),
[`test_relevance_conf_event.py`](../../../../playground/research/test_relevance_conf_event.py)
(35 conf-event assertions). Re-runnable smoke harnesses:
[`_smoke_noise_filter.py`](../../../../playground/research/_smoke_noise_filter.py),
[`_smoke_conf_event.py`](../../../../playground/research/_smoke_conf_event.py).

