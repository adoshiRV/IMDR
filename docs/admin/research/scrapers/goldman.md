# Goldman Sachs — Marquee research scraper

Pattern: **A. Listing-API firehose** + direct PDF (see
[scrapers/index.md](index.md)).

## Daily volume

~**395 reports/day** across all GIR disciplines + FICC desk content
(post-filter, post-Stage-1 path-relax — see the 2026-06-12 update at
the bottom for context). Discovered via ``/research/search/reports/
advanced-search`` — fetched in ~3–6 pages of 200 with date-sorted
early-stop.

The raw search API returns ~470/3 day-window across all content types.
Three path prefixes now yield ingestible content (Stage 1, 2026-06-12):

* ``/content/research/en/reports/`` → direct PDF GET (the legacy fast path)
* ``/content/markets/en/...`` → playwright `page.pdf()` render
* ``/content/research/en/blogs/`` → playwright `page.pdf()` render

Models (`/content/research/en/models/`) and GS.com insights
(`/content/insights/en/reports/`) are still skipped at discovery —
interactive Excel widgets and marketing fluff, respectively.

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

The 5 Goldman content types in the search index, their render mode,
and what we do with them (updated 2026-06-12, Stage 1):

| Path prefix | Render mode | Status | Notes |
|---|---|---|---|
| `/content/research/en/reports/` | **`pdf`** (direct GET) | ingested | The classic research-report PDFs (~50% of firehose) |
| `/content/markets/en/...` | **`html`** (playwright `page.pdf()`) | ingested | FICC desk content — MarketStrats family, GS MORNING, regional dailies, GS What is Priced In (~35% of firehose) |
| `/content/research/en/blogs/` | **`html`** (playwright `page.pdf()`) | ingested | Research blogs — US Economics Weekly Update, FX Wrap Up, The Euro into the ECB (~5/week) |
| `/content/research/en/models/` | — | **skipped** | Interactive Excel/web tools — no useful narrative text |
| `/content/insights/en/reports/` | — | **skipped** | GS.com marketing (Talks at GS, Exchanges podcast) — already source-allow-list filtered |

Routing is in `_derive_fetch_target()` in
[`crawler_goldman.py`](../../../../playground/research/ingest/crawler_goldman.py)
which returns `(url, render_mode)`. Each `ReportRef` carries the
`render_mode` field which propagates through `ReportMeta` into
`pipeline.ingest_one`, which dispatches to `fetch_pdf` or
`fetch_html_as_pdf`.

## Fetch strategy

Two paths depending on `ReportRef.render_mode`:

* **`render_mode="pdf"`** — `fetch_pdf` direct GETs the `.pdf` URL via
  the persistent-profile cookies. On HTTP 401 the playwright context is
  re-launched once (re-reads SSO cookies from disk) before declaring
  failure. Same fast path as before Stage 1.
* **`render_mode="html"`** — `fetch_html_as_pdf` opens the `.html` URL
  in headless playwright, polls `document.body.innerText.length` until
  stable (max 25 s), scrolls bottom→top to force lazy-loaded sections,
  re-polls body length after scroll, and emits `page.pdf()` bytes. If
  the post-scroll body collapsed below 3 k chars the whole render is
  retried once in a fresh page (Marquee SPA flakiness — see retry guards
  in [`fetch.py`](../../../../playground/research/ingest/fetch.py)).

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
C:/IMDR_LOCAL/research_profiles/goldman/
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

## Hard taxonomy probe (2026-06-02)

Full read-only probe of the search-API response shape. Detailed
write-up in
[`taxonomy_probe/goldman_full.md`](../../../../playground/research/taxonomy_probe/goldman_full.md);
the probe script
[`probe_goldman_full.py`](../../../../playground/research/probe_goldman_full.py)
is re-runnable (read-only — no DB write, no PDF fetch).

### Key finding — `aemTags[]` is the master taxonomy

Each document carries an `aemTags[]` array of strings shaped like
``research:<axis>/<parent_guid>/<child_guid>[-Primary]`` spanning 19
distinct axes. The GUIDs resolve via a `facetList` block returned in
the **same response** — free, deterministic, no extra calls. This is
GS's equivalent of JPM's `regions/assetClasses/sectors/countries`
and MS's `cinfo.srcinfo`. The first cut of the crawler ignored it
completely.

Axes we now parse and structure on `ReportRef`:

| aemTag axis | resolves via facet | what it carries |
|---|---|---|
| `sources` | Sources (7 buckets) | "Research" / "FICC and Equities" / "GS.com" / "Investment Banking" / "Asset Management" / "Wealth Management" / "Goldman Sachs Global Institute" |
| `reportTypes` | Report Types (9) | "Flow" / "Analysis & Insight" / "Model" / "Compendium" / "Audio" / "Video" / "Blogs / Commentary" / "Presentation" / "IB_Marketing" |
| `productFocus` | Focus (3) | **"Issuer" / "SectorIndustry" / "Country"** — **canonical single-name signal** |
| `regions` | Regions/Countries (93) | super-regional buckets (Americas, Europe, Asia Pacific, EMEA, …) |
| `countries` | Regions/Countries (93) | ISO-level country names; `-Primary` suffix marks the canonical entry |
| `subjects` | Subjects (110) | Central Banks, Earnings, Inflation, ECB, Federal Reserve, Macro, Micro, … |
| `girAssetTypes` / `girDisciplines` | Sub-sources/Assets (67) | "Equity Research" / "Currencies / FX" / "Rates" / "Credit" / "Commodities" / "Economics Research" / "Portfolio Strategy Research" / 50+ currencies |
| `industries` | Industries (451) | Reuters-style sector hierarchy |
| `giractions` | Actions (28) | EPS Estimate Change / Price Target Change / Rating Change / Forecast Change / … |

### Filter design (Tier-0 deterministic drops at discovery)

`filters/goldman.py` — first-match-wins precedence:

1. `format:podcast` / `format:video` — listing booleans (legacy, kept)
2. `report-type:<value>` — drop any of {Audio, Video, Blogs / Commentary, Presentation, IB_Marketing}
3. `source:<value>` — drop when `sources` is populated but contains nothing in {Research, FICC and Equities}
4. **`focus:Issuer`** — single-name research, **the main drop** (catches ~8% more than `primaryCompanyTickers==1`)
5. `single-name:1-ticker` — fallback for legacy docs with no `aemTags.productFocus` axis
6. `title-prefix:'<prefix>'` — invite/webcast admin posts (legacy)

### Tier-0 classifier

`classifiers/goldman.py` — first-match-wins:

1. `focus=="Issuer"` OR `primaryCompanyTickers` non-empty → EQUITY
2. **`girAssetTypes` → canonical** via the 9-row map (`Currencies / FX → FX`, `Rates → RATES`, `Credit → CREDIT`, `Commodities → COMMODITIES`, `Economics Research → MACRO`, `Portfolio Strategy Research → STRATEGY`, `Equity Research / Equities → EQUITY`, `ESG → ESG`). **This was the missing layer** — 61/200 docs ship empty `disciplines[]` (the FICC desks) and the old classifier fell through to title regex, often returning empty.
3. `disciplines[]` substring (legacy fallback)
4. `sourceDisplayName` substring (legacy fallback)
5. Title regex (legacy fallback)
6. **Tier-3.5 desk-title** (`_from_desk_title`, gated `render_mode=="html"`) — `/content/markets/` desk-daily naming patterns (added 2026-06-12)
7. **Tier-4 structured backfill** — `Macro` in subjects → MACRO; `industries`/non-Issuer focus → EQUITY (added 2026-06-10)
8. **Tier-5 content-title** (`_from_content_title`, ungated) — content-signal regex for metadata-less docs (added 2026-06-14; see the 2026-06-14 section)

Country code from `primary_country` (aemTags `countries-Primary`) →
`normalize_country` → ISO 2-char. Was hardcoded `None` before.

`subjects[]` aemTags emitted as `TAG_THEME` (replaces the deprecated
`curatedKeywords[]`, which is empty on 100% of probe sample). First 5
`industries[]` aemTags emitted as `TAG_INDUSTRY`.

## DB audit (2026-06-02)

Detailed write-up in
[`taxonomy_probe/goldman_db_audit.md`](../../../../playground/research/taxonomy_probe/goldman_db_audit.md).
480 rows, 2026-05-06 → 2026-05-29 (batch ingest, 12-day gap May 8-19).

| issue | count | severity |
|---|---|---|
| **Blank `asset_class` + zero tags** (2026-05-21 + 2026-05-25 batches) | **144 rows (30%)** | pipeline / classifier failure — invisible to search; FICC desk content where `disciplines[]` was empty |
| `asset_class='EQUITY'` (single-name leakage; every row has 2+ ticker tags) | 204 (42%) | discovery filter didn't catch — relevance filter not tuned to GS ticker-padding |
| **Zero RATES / FX classifications** despite "BOJ JGB Path", "FX Forecast" titles | 107 collapsed into MACRO | classifier missed FICC content |
| Zero country / region coverage (country_code hardcoded `None`) | 480/480 | structural — fixed via aemTags `countries-Primary` |
| Encoding corruption | 0 | clean |
| Non-canonical asset_class strings | 0 | clean (GS publication type lives in `vendor_pubtype` tag) |

Cleanup buckets 7 + 8 added to
[`cleanup_tier1_junk.py`](../../../../playground/research/cleanup_tier1_junk.py):
- `goldman-empty-classifier` — 144 rows; DELETE → daily re-ingest under Tier-0
- `goldman-equity-leak` — 204 EQUITY rows; DELETE → re-ingest, single-name drops at discovery via `focus=Issuer`

## 7-day smoke (2026-06-03)

Read-only via
[`smoke_goldman_7day.py`](../../../../playground/research/smoke_goldman_7day.py).
Log at
[`taxonomy_probe/goldman_smoke_7day.log`](../../../../playground/research/taxonomy_probe/goldman_smoke_7day.log).

**Volume — 7-day window (since=2026-05-27 until=2026-06-03):**

| stage | count |
|---|---|
| raw cards processed | ~1136 |
| discovery drops | 716 (63%) — focus:Issuer 370, single-name:1-ticker 310, format:podcast 17, audio/video 0, blogs 7, GS.com 5, video-bool 5, presentation 1, webcast-prefix 1 |
| discovery kept | 420 (~60/day) |
| relevance kept (v1, loose) | 414 (99% of post-discovery) — 6 extra single-name catches |
| relevance kept (v2, tightened 2026-06-03) | **266 (63% of post-discovery, ~38/day)** — drops 149 sector-only EQUITY via the Goldman branch below |

**Field coverage on 420 survivors:** sources 100%, gir_asset_types
98%, subjects 82%, regions 71%, countries 64%, focus 44%, industries
34%, report_types 79%.

**Kept asset_class distribution:**

After the v2 tightening (Goldman branch in `relevance.py`):

| class | count | % | comment |
|---|---|---|---|
| MACRO | 112 | **42%** | Euro Inflation, Balance of Payments, Fair Work Commission, Earnings Season Takeaways |
| **RATES** | 70 | **26%** | (was 0 in DB) Canadian Rates Weekly, GS Rates MarketStrats, Treasury RV, Global IR Gamma — the FICC stream now picked up by Tier-0 |
| STRATEGY | 21 | 8% | Asian equity market daily, Cross-Asset, Yield builds |
| EQUITY | **19** | 7% | post-tightening — daily "Ratings and Target Price Changes" digests (Macro-tagged), "This Week in Global Research", "Inside the Model", "Positioning ahead", "Weekly sector news, positioning data" |
| **FX** | 14 | 5% | (was 0 in DB) GS FX MarketStrats, FXpresso Daily, USD/CAD USMCA |
| (empty) | 12 | 5% | execution analytics (Futures Cost-to-Trade) + French-language reports |
| COMMODITIES | 11 | 4% | Brent volatility, Copper, Hormuz |
| CREDIT | 7 | 3% | GS Credit Volatility Report, Corporate Credit |

**Country coverage now working** (was 0/480): top countries US 72,
CN 38, BR 23, JP 21, AU 20, KR 11, DE 9, UK 8. Regions: apac 111,
americas 86, emea 55, latam 38.

**Sample kept titles** confirm the FICC-desk recovery:
- RATES: *"Canadian Rates Weekly"* / *"Treasury RV Report"* / *"GS Rates MarketStrats - Global Bond Futures Carry"*
- FX: *"GS FX MarketStrats | FXpresso Daily"* / *"USD/CAD and The USMCA Review"*
- CREDIT: *"Corporate Credit Look Into Housing"* / *"GS Credit Volatility Report"*

### Posture on sector EQUITY — tightening (2026-06-03)

The first-cut smoke kept 168 EQUITY survivors (40% of total kept).
Review of those titles surfaced a clear split:
* **131 `focus=SectorIndustry`** — pure sector noise (Watches round-up,
  TV Viewership Tracker, ASCO conference notes, Container shipping,
  Hospital occupancy, Hyundai monthly wholesale, per-name covers).
  All carry `subj=[Micro]` only.
* **37 `focus=(empty)`** — daily wraps + multi-stock digests, mixed
  quality. ~8 carry a `Macro` subject tag (the desk's cross-asset /
  research-summary content); ~29 are Micro-only sector content.

User decision: tighten. Added a Goldman branch to
[`relevance.is_single_name_equity`](../../../../playground/research/ingest/relevance.py):

```
if vendor_code == "goldman" and asset_class == EQUITY:
    if n_tickers == 1:                              -> drop
    if "Macro" in subject-tags:                     -> keep
    if title matches _GS_EQUITY_KEEP allowlist:     -> keep
    else:                                            -> drop
```

`_GS_EQUITY_KEEP` keywords: ``strategy | portfolio | cross-asset |
allocation | outlook | thematic | themes | positioning | earnings
season | earnings preview | global research | cross-sector``.

GS-native `Macro` subject tag is the cleaner signal — Subjects facet
has Macro (51K catalog-wide) vs Micro (217K). 100% of SectorIndustry
survivors are Micro-only; the macro-flavoured daily wraps carry Macro.

Net 7-day result after tightening: **266 kept (was 414), ~38/day**.
EQUITY survivors 168 → 19 (kept the daily "Ratings and Target Price
Changes" multi-stock digests with Macro tag, "This Week in Global
Research", "Inside the Model", "Positioning ahead", "Weekly sector
news, positioning data"; dropped sector noise + per-name SectorIndustry
covers).

Two edge cases lost — *Berlin Mietspiegel* (German RE macro) and
*China Trade Tracker* — accepted at ~2-3/week. Both classify EQUITY
because the Equity Research desk publishes them; could be recovered
by mapping `subj=[Trade Policy]` → MACRO in a future pass.

## Last verified

2026-05-08 — pipeline working end-to-end via advanced-search +
path-type filter. **~330 PDF reports/day** discovered (was ~6 with DOM
scrape; was ~470/day before filter — the difference is non-PDF content
types we now skip at discovery). Per-PDF wall-clock ~3s with embed off,
fail rate dropped 50% → ~5%.

2026-06-03 — Tier-0 + aemTags filter + Tier-0 classifier landed in
playground (gitignored). 7-day smoke (loose v1) showed ~60 kept/day
after 63% discovery drop. Then user-requested tightening on sector
EQUITY: added Goldman branch to `relevance.is_single_name_equity`
with `Macro` subject-tag bypass + cross-asset title allowlist
(`_GS_EQUITY_KEEP`). v2 = **38 kept/day**, EQUITY 168 → 19,
composition MACRO 42% / RATES 26% / STRATEGY 8% / EQUITY 7% /
FX 5% / COMMODITIES 4% / CREDIT 3%. RATES, FX, and country/region
populated for the first time.

## Noise filter update (2026-06-10)

### Shared discovery-noise classifier

A cross-vendor noise classifier was wired into
[`ingest/filters/_noise.py::classify_noise`](../../../../playground/research/ingest/filters/_noise.py)
and now runs as the final fallback inside [`filters/goldman.py::should_exclude`](../../../../playground/research/ingest/filters/goldman.py).
Three universal title-pattern families:

* **chart-pack** — pure-data / chart-only SKUs (`*Analytics*`,
  `*Rich/Cheap*`, `*Chart Pack/Book/Deck*`, `*Vol Package*`,
  `*Reference Sheet*`, `*Multi-factor Analysis*`, etc.).
* **morning-note** — daily sales-recap titles (anchored prefix match);
  for Goldman the firing patterns are `"US Morning Update"` and
  `"Asian equity market daily update"`.
* **event-admin** — invites / reminders / "Starts in 1 hour" pings not
  already caught by the per-vendor `EXCLUDED_TITLE_PREFIXES` tuple.

Smoke against the full 4,498-title `research.dim_report` corpus dropped:

| family | drops at Goldman | sample |
|---|---|---|
| chart-pack | 13 | `Ratings and Target Price Changes - June 08, 2026 as of 5:30 AM ET`; `Monthly Activity Chartbook: Moderation in April investment activity` |
| morning-note | 17 | `US Morning Update`; `Asian equity market daily update` |
| event-admin | 0 | (already covered by `EXCLUDED_TITLE_PREFIXES`) |

### Cross-vendor EQUITY conference / sales-event drop

The 2026-06-03 v2 tightening kept 19 EQUITY survivors via the
`_GS_EQUITY_KEEP` keyword allowlist. The 2026-06-10 content audit
(content samples at [`_takeaway_samples.txt`](../../../../playground/research/_takeaway_samples.txt))
found that many of those 19 survivors were actually conference / sales-
event noise whose titles contained macro-flavoured keywords like
`themes` / `positioning` / `cross-sector` — they passed `_GS_EQUITY_KEEP`
but their content was stock-pick takeaways.

Added [`relevance._is_equity_conf_event`](../../../../playground/research/ingest/relevance.py)
which fires BEFORE the per-vendor allowlist for any EQUITY-tagged doc
whose title hits the cross-vendor conf-event regex (takeaways stem,
KOL, trip notes, NDR, dbAccess / Communacopia, sector-X conferences).
MACRO-tagged Goldman titles like *"Earnings Season Takeaways: Resilient,
but for How Long?"* bypass via the asset_class gate.

Goldman smoke: **27 additional drops** — the residual leak set incl.
`Trip Takeaways: Banks Shift to Defensive Balance Sheet Management`,
`NDR takeaways: Membership, IP, store upgrade`, `Asia Communacopia +
Technology — Key Takeaways: 3,000 robotaxis`, `Takeaways from Trump-Xi
Meeting [Replay]`, `Investor day sets 2030 growth targets`, `Game
Conference Takeaways`, `Lunch with Construtora Lindenberg`.

### Tier-4 classifier asset_class backfill

The 2026-06-02 DB audit flagged **144 Goldman rows with blank
`asset_class`** — `disciplines[]` was empty AND `girAssetTypes[]` was
empty, so Tiers 0-3 returned blank. Those docs silently bypassed the
single-name + sector-equity drops in `relevance.py` because
`if result.asset_class != ASSET_CLASS_EQUITY: return False, ""` exits
early on blank.

Added a Tier-4 fallback to [`classifiers/goldman.py::classify`](../../../../playground/research/ingest/classifiers/goldman.py):

```
if not asset_class:
    if any(s.lower() == "macro" for s in subjects):
        asset_class = MACRO
    elif industries or (focus and focus != "Issuer"):
        asset_class = EQUITY
```

Rationale:
- Goldman tags `industries` only on company/sector content; any doc
  with `industries[]` populated is single-name or sector-equity and
  belongs in the default-drop pipeline.
- `Macro` in `subjects[]` is GS's cleanest macro signal (the Subjects
  facet has Macro = 51K catalog-wide vs Micro = 217K).
- Other `focus` values (`Multi-Issuer`, `Companies`, etc.) without an
  asset_class also route to EQUITY.

Recovered ~22 conference-takeaway docs that previously bypassed
relevance.py (Asia Communacopia Tech Key Takeaways, India Supply Chain
Resilience Virtual Conference, AGA Financial Forum, European Utilities
Conference, etc.). Combined with the cross-vendor `_is_equity_conf_event`
regex, all 22 now drop on the next discovery cycle.

### Tests + smoke harnesses

* [`test_noise_filter.py`](../../../../playground/research/test_noise_filter.py) — 116 tests pin the chart-pack / morning-note / event-admin patterns
* [`test_relevance_conf_event.py`](../../../../playground/research/test_relevance_conf_event.py) — 35 tests pin the conf-event regex + gating contract
* [`_smoke_noise_filter.py`](../../../../playground/research/_smoke_noise_filter.py) — per-vendor drop tabulation against `dim_report`
* [`_smoke_conf_event.py`](../../../../playground/research/_smoke_conf_event.py) — would-drop / would-keep / macro-bypass tabulation

## Stage 1 + 2 — path-relax + HTML render + classifier patch (2026-06-12)

### Motivation

A 7-day unfiltered probe ran on 2026-06-11 against
`/research/search/reports/advanced-search` and bucketed 1,200 docs by
path prefix:

```
/content/research/en/reports/   557   (45%)   — ingested
/content/markets/en/...         414   (35%)   — silently dropped
/content/research/en/models/    220   (18%)   — silently dropped
/content/research/en/blogs/       5   (<1%)   — silently dropped
/content/insights/en/reports/     4   (<1%)   — silently dropped
```

**54% of GS content was being silently dropped** by the old
`_PDF_PATH_PREFIX = "/content/research/en/reports/"` gate in
`_derive_pdf_url()`. The dropped paths included the entire GS Rates
MarketStrats franchise (Bond Report / Bond Futures Carry / IR Gamma /
Best Trades / Movers / Seasonality), the FXpresso Daily, FX Carry Vol
Monitor, GS MORNING desk-roundups, Treasury RV Reports, plus the
research blogs (US Economics Weekly Update, Weekly FX Wrap Up).

Probe artefact: [`_probe_goldman_unfiltered.jsonl`](../../../../playground/research/_probe_goldman_unfiltered.jsonl).

### Stage 1 — path-relax + HTML render

Five file edits, summarised:

1. **`ingest/crawler_goldman.py`** — `_RENDERABLE_PATH_PREFIXES` map
   replaces the single-prefix gate. `_derive_fetch_target()` returns
   `(url, render_mode)`. `ReportRef` gains a `render_mode` field
   (`"pdf"` or `"html"`).
2. **`ingest/models.py`** — `ReportMeta.render_mode: str = "pdf"` added.
3. **`ingest/fetch.py`** — new `fetch_html_as_pdf()`:
   `domcontentloaded` → smart-wait (poll `document.body.innerText.length`
   until 2 consecutive reads match, max **25 s**, min body 1.5 k chars)
   → scroll-bottom-then-top → re-poll body length → `page.pdf()`. If
   post-scroll body < **3 k chars** the whole render is retried once in
   a fresh page (Marquee SPA flakiness).
4. **`ingest/pipeline.py`** — `ingest_one` dispatches on
   `meta.render_mode`: `"html"` routes to `fetch_html_as_pdf`,
   `"pdf"` keeps the legacy `fetch_pdf` flow.
5. **`ingest_today.py`** — threads `ref.render_mode` into the
   `ReportMeta(...)` call. **One-line bug** discovered in the first
   prod run (the unified orchestrator missed this; legacy
   `ingest_today_goldman.py` had it). Fixing it took the same
   2026-06-09..06-12 backfill from **5.6% → 88.5% success rate**.

### Stage 1 — blog-allow + CJK filter (`ingest/filters/goldman.py`)

* `"Blogs / Commentary"` removed from `_EXCLUDED_REPORT_TYPES` — it was
  blocking exactly the weekly franchises we want (US Economics Weekly
  Update, FX Wrap Up, Weekly Commodities Wrap Up, The Euro into the
  ECB, The Dollar into US CPI).
* `_HAS_CJK` regex added — drops GS Tokyo's Japanese-language daily
  editions (`【GS】LDNデイリーコメント`, `【GS】NYデイリーコメント`,
  `高盛晨读`) that the advanced-search `language=["en"]` body filter
  doesn't catch (that flag is UI locale, not document content). Mirrors
  the same regex used in `filters/jpm.py` and `filters/db.py`.

### Stage 1 — fetch reliability guards (`ingest/fetch.py`)

Two retry guards added after the first 30-ref observe showed 95%
success with 5% failing on two distinct shapes:

* **HTML body too short** — `_HTML_POST_SCROLL_MIN_BODY_LEN = 3000` +
  `_HTML_RETRY_ON_SHORT_BODY = 1`. Catches the case where the page
  hydrated past the smart-wait threshold but the scroll-bottom step
  triggered a content collapse, and `page.pdf()` captured the partial
  state (the "770-char outliers"). Render is retried once in a fresh
  page; second short body fails hard.
* **PDF HTTP 401** — `_PDF_401_RETRY = 1`. Goldman's persistent-profile
  session intermittently returns 401 on direct PDF GETs even when
  `auth check --vendor goldman` reports the session live (~5% of GETs).
  Closing and re-launching the playwright context re-reads SSO cookies
  from the profile dir and clears the stale in-memory session.

### Stage 2 — false-trail probes (no content gap found)

Two follow-up probes ran to check for content not in the advanced-
search firehose:

* **Publications probe** ([`_probe_goldman_publications.py`](../../../../playground/research/_probe_goldman_publications.py))
  rendered the 6 "Featured Publications" UUIDs advertised on
  `marquee.gs.com/content/markets/home.html`. **Verdict: containers
  only.** Each publication page is ~2.5 k chars of nav chrome + 11
  outbound links to `/content/markets/en/.../{uuid}.html` children that
  Stage 1 already covers. 3 of the 6 franchises (MAPS RoadMap Weekly,
  Two-Minute Views, Editor Picks) haven't published a new issue since
  2023-2024 — defunct.
* **Roundup link-mining probe** ([`_probe_goldman_roundup_links.py`](../../../../playground/research/_probe_goldman_roundup_links.py))
  rendered 3 typical roundups (GS MORNING, GS What is Priced In, Top
  Stories 2026-06-11) and extracted every `<a href>` pointing at GS
  content paths, cross-referenced against the 1,200-UUID firehose.
  **Verdict: near-zero gap** — across all 3 roundups, only 3 outbound
  article links, of which 2 were already in the firehose and 1 was a
  timing artefact (article published just before our snapshot).
  Roundups talk inline; they don't link out.

**Both probes returned negative, ruling out further discovery work on
GS.** Stage 1 is the complete fix; the firehose is the only content
source worth wiring.

### Tier-3.5 desk-naming classifier (`ingest/classifiers/goldman.py`)

The 2026-06-12 backfill landed 127 rows with empty `asset_class` — all
from `/content/markets/...` paths where the doc carries no resolved
`girAssetTypes` / `disciplines` / `subjects` metadata. GS desk dailies
follow consistent naming patterns:

```
GS <SECTOR>:          → EQUITY (drops via relevance default-drop)
GS <REGION> <CADENCE> → MACRO
GS CLO / LevFin       → CREDIT
GS Ags                → COMMODITIES
```

`_from_desk_title()` runs as a new tier between Tier-3 (legacy title
regex) and Tier-4 (structured-backfill subjects/industries), gated on
`render_mode == "html"` so it only fires for `/content/markets/` and
`/content/research/en/blogs/` paths.

Sample rules (full pattern set in [classifiers/goldman.py](../../../../playground/research/ingest/classifiers/goldman.py)):

| Pattern | Asset class | Examples |
|---|---|---|
| `^(GS )?<SECTOR>` near start | EQUITY | "GS CONSUMER:", "GS INDUSTRIALS:", "GS TMT TODAY", "GS FINS & REITs Daily" |
| `## Marketcolour`, `EQUITIES COLOR`, `HK MARKET WRAP` | EQUITY | "## Marketcolour + P911...", "US EQUITIES COLOR: TECH UNWIND" |
| `Alpha Generat` stem | EQUITY | "Hanwha Engine - Key Takeaways (GS Korea Alpha Generation Call)" |
| `CLO`, `LevFin`, `Leveraged Finance` | CREDIT | "GS CLO Secondary Weekly Commentary", "GS EMEA LevFin Digest" |
| `GS Ags`, `Agriculture` | COMMODITIES | "GS Ags: Cheap Vol" |
| `(GS )?<Region> <Cadence>` | MACRO | "GS US Daily Download", "GS CEEMEA Today", "GS CHINA OPEN", "GS Korea Weekly", "ASIA: NEED TO KNOW" |
| Standalone franchise (`Duttenhoefer`, `Armchair QB`, `Macro to Micro`, `Top Stories`, `IR Kick-Start`) | MACRO | "Duttenhoefer's Daily", "Armchair QB - Japan" |

### One-shot backfill of existing rows

[`_backfill_goldman_asset_class.py`](../../../../playground/research/_backfill_goldman_asset_class.py)
runs the new `_from_desk_title()` against every Goldman row in
`research.dim_report` with empty `asset_class`. Two-pass commit
(after fixing `Alpha Generator` → `Alpha Generat` stem) re-classified
**113 of 147 historical blanks** into:

| Class | Rows backfilled |
|---|---|
| MACRO | 49 |
| EQUITY | 57 (55 + 2 Alpha Generation Call) |
| CREDIT | 6 |
| COMMODITIES | 1 |

The residual ~34 stay blank — wildly varied shapes (single-name
initiations without ticker, "## US Strategy" without a sector word,
"GS Daily \| <sector body>" without a region anchor, generic "Different"
/ "Lithium + DVN + CASY" / "Swedish Initiation - Boliden to Sell").
Chasing each shape with another regex rule is whack-a-mole; downstream
queries that filter `asset_class IN ('RATES','FX','MACRO',…)` skip them
which is the correct behaviour for ambiguous content.

### Final state — 2026-06-09..06-12 window post-backfill

| asset_class | n | examples |
|---|---|---|
| MACRO | 67 | GS desk dailies + IR Kick-Start + ECB/BoE/BoJ previews |
| EQUITY | 55 | Sector spec-sales + Alpha Generation Call single-name |
| RATES | 36 | GS Rates MarketStrats family (6 daily reports × 3 days), Treasury RV, Fed Communication |
| (blank) | 34 | Ambiguous one-liners; relevance queries skip |
| FX | 24 | FXpresso Daily, FX Carry Vol Monitor, FX Forward Point Roll Monitor |
| CREDIT | 14 | GS CLO, EMEA LevFin Digest, Credit Volatility Report |
| COMMODITIES | 13 | Including GS Ags |

**Goldman is now ingesting all 7 asset classes** for the first time —
previously RATES/FX/COMMODITIES landed only a handful of docs per week
because the desk content lived under `/content/markets/` and was
silently dropped at discovery.

## Stage 3 — coverage audit + DB reconciliation + Tier-5 classifier + blank backfill (2026-06-14)

### Read-only coverage audit

Full-instrumented 7-day read-only smoke
([`smoke_goldman_7day_full.py`](../../../../playground/research/smoke_goldman_7day_full.py))
re-implements the discovery pagination inline so it tallies **every**
stage — raw API → discovery-filter drops (by reason) → path-prefix gate
→ relevance drops → classifier — with zero DB / Qdrant / PDF side
effects. 7-day window 2026-06-07..06-14:

```
raw API docs in window        1,464
  − discovery-filter drops      628  (focus:Issuer 348, single-name 189,
                                      podcast 28, chart-pack 26, cjk 15,
                                      video 8, morning-note 9, GS.com 4, …)
  − path-prefix gate drops       43  (models/insights)
  = survivors                   793  (488 html / 305 pdf)
  − relevance drops             311  (equity-default 282, conf-event 20, 1-tkr 9)
  = kept                        482
```

A franchise/CB-event coverage audit (same script) confirmed **all major
recurring franchises are kept in text**: GS Rates MarketStrats 32/32,
Swaption/rates-vol 12/12, Treasury RV 7/7, FX Monitors 8/8, FXpresso 5/5,
Commodity Futures 6/6, FOMC/Fed 29 kept, ECB 21, BoJ 4. Every discovery
drop in the CB/franchise buckets is intentional (Japanese re-writes of
kept English docs, podcasts that dupe kept written content, chart-only
SKUs). `US Morning Update` confirmed a correct drop — it is the GS
**equity**-desk daily recap (source `Research | Equity`, gir
`Equity Research`, subject `Micro`, authors Hussey/Herr/Garg), distinct
from the kept FICC `GS MORNING` / `GS What is Priced In`. RBA was absent
the audit week (meeting fell the following Tuesday; preview publishes the
day before — a timing artefact, not a coverage gap). Probe of the
`US Morning Update` content lives at
[`_probe_goldman_us_morning_update.py`](../../../../playground/research/_probe_goldman_us_morning_update.py).

### DB reconciliation — pre/post 06-12-fix drift

DB held **985 Goldman rows**; the 06-07..06-12 slice was a mix of pre-
and post-fix ingests. Pre-fix (≤ 06-11) leaked sector / spec-sales /
single-name EQUITY and under-ingested RATES/FX (markets-path content was
dropped at discovery before the 06-12 path-relax). The tell: per-day
EQUITY ran 8→18→20→19→**3**, collapsing on 06-12 when the fixes landed;
DB EQUITY 68 / RATES 37 inverted the current-code smoke's EQUITY 19 /
RATES 100.

### Stale-leak cleanup — end-to-end delete (272 rows)

[`cleanup_goldman_stale.py`](../../../../playground/research/cleanup_goldman_stale.py)
replays the **real** `filters/goldman.should_exclude` (title-only —
conservative, can only fire a subset of discovery reasons) +
`relevance.is_single_name_equity` (Goldman branch) against persisted DB
state, reusing the tested end-to-end delete path from
[`cleanup_filter_violations.py`](../../../../playground/research/cleanup_filter_violations.py)
(Qdrant points + OneDrive/SharePoint PDF + DB FK cascade). Dry-run
reviewed for RATES/FX/macro false-positives (none), then committed:

| reason | n |
|---|---|
| relevance: equity-vendor-default-drop | 208 |
| relevance: equity-conf-event | 34 |
| discovery: noise chart-pack (Ratings & TP Changes / Chartbook) | 13 |
| discovery: noise morning-note (Asian equity / US Morning Update) | 17 |
| **total deleted** | **272** (5,304 Qdrant points, 269 PDFs) |

EQUITY collapsed ~204 → 34 (the legit Macro-tagged / allowlist survivors).

### Tier-5 content-title classifier — the blank-asset_class fix

Audit of the residual **169 blank-`asset_class`** rows found they were
not desk-daily named franchises (Tier-3.5) but ordinary research with no
resolved `girAssetTypes`/`disciplines`/`subjects` (markets- AND reports-
path docs with empty aemTags). Blank rows **bypass relevance.py** (its
single-name/sector drops early-exit when `asset_class != EQUITY`), so
equity leak landed silently. Added **Tier-5** `_from_content_title` to
[`classifiers/goldman.py`](../../../../playground/research/ingest/classifiers/goldman.py)
— ungated final fallback (after Tier-4), content-signal regex ordered
**MACRO → RATES → FX → COMMODITIES → STRATEGY → EQUITY**:

| signal family | → class | examples |
|---|---|---|
| central banks (`BoG/BoI/SARB/FOMC`, `\d+bps?`, `rate hike/cut`), econ releases (`PMIs`, `trade balance`, `current account`, `inflation`, `unemployment`, `fiscal`), country-prefix (`Mexico:`/`USA:`/`Euro Area—`), sovereign rating actions | MACRO | "BoG On Hold", "USA: FOMC Minutes", "Mexico: Moody's Downgrades…Foreign Currency" |
| `treasury valuation`, `yield reversal/curve`, `bond selloff`, `swaption`, `rate reality` | RATES | "US Treasury Valuations…Yield Reversal" |
| `NOK`, `Korean Won`, `won poised`, `de-dollar` | FX | "The NOK Oil Proposition" |
| `stock/inventory draws`, `crude oil import` | COMMODITIES | "Visible Stock Draws Accelerate" |
| `^US/Global/EM Strategy`, `cross-asset`, `asset allocation` | STRATEGY | "## US Strategy - Capex" |
| earnings (`1Q26`/`first take`/`EPS`/`guidance`/`read-across`), ratings (`upgrade`/`downgrade`/`initiation`), events (`takeaways`/`conference`/`NDR`/`mgmt`), sector compounds, GS equity-desk prefixes (`GS KOREA`/`GS EU HC`/`GS Focus Idea`) | EQUITY | "1Q26 First Take", "Asia Communacopia Takeaways", "GS KOREA: …" |

**Ordering is load-bearing**: macro is checked first so sovereign
"Downgrades" and country-prefixed releases aren't stolen by the equity
`downgrade`/`results` stems. Post-code-review hardening (2026-06-14):
`bps?` plural, `central bank`/`conference board` macro phrases, rating-
agency-name sovereign guard (`Moody's/Fitch` + rating verb), dead
`trade:` made standalone, `[12]H\d{2}`, and the dangerous broad equity
stems scoped — bare `results?` → `results? (beat|miss|preview|recap|
in-line)`, bare `sector` → `sector (check|specific|valuation|…)`, bare
`downgrade`/`upgrade` anchored, ambiguous `^GS:`/`GS Daily |` dropped
(safer blank than a false equity-delete). Pinned by **74 tests** in
[`test_goldman_tier5_classifier.py`](../../../../playground/research/test_goldman_tier5_classifier.py)
(macro-keep, equity-drop, tail classes, junk-stays-blank, macro-before-
equity ordering, and FP guards for sovereign downgrade / Conference Board
/ Auction Results).

### Blank backfill — end-to-end (169 rows)

[`backfill_goldman_blanks.py`](../../../../playground/research/backfill_goldman_blanks.py)
reclassified the 169 blanks via Tier-5, consistent with the live
pipeline: **45 UPDATE** (MACRO 34 / RATES 3 / FX 2 / COMMODITIES 2 /
STRATEGY 1 / EQUITY allowlist-survivors 3), **74 EQUITY-leak DELETE**
end-to-end (1,108 Qdrant points, 74 PDFs), **50 left blank** (genuine
junk + ambiguous one-liners — left rather than risk deleting macro;
downstream class-filtered queries correctly skip them). Validation tool:
[`_validate_goldman_tier5.py`](../../../../playground/research/_validate_goldman_tier5.py).

### Final Goldman state (713 rows)

| asset_class | n |
|---|---|
| MACRO | 384 |
| STRATEGY | 50 |
| RATES | 41 |
| EQUITY | 37 |
| FX | 33 |
| CREDIT | 22 |
| COMMODITIES | 22 |
| (blank) | 50 |

## Chart-only series drops (2026-06-15)

Content audit 2026-06-15 confirmed the following series produce PDFs whose
extractable text is title + disclaimer only — the analysis lives in chart images
that PyMuPDF cannot OCR. Added as `_CHART_ONLY_TITLE_PREFIXES` in `filters/goldman.py`,
applied via `match_title_prefix` after the admin-prefix check and before `classify_noise`.

| Series prefix | Family | Notes |
|---|---|---|
| `commodity futures volatility report` | Commodities | Futures vol surface chart deck |
| `commodity futures curve report` | Commodities | Futures curve chart deck |
| `commodity pre post roll report` | Commodities | Pre/post roll data charts |
| `gs rates marketstrats` | Rates | Covers Bond Report / Bond Futures Carry / Movers / Best Trades / Seasonality |
| `gs marketstrats \| the tail stratbook` | Strategy | Tail-risk chart deck |
| `views from the treasury desk` | Rates/FX | Treasury desk chart series |
| `fx forward point roll` | FX | FX forward point roll data charts |
| `fx carry vol monitor` | FX | FX carry vol chart series |
| `gs credit marketstrats` | Credit | CDS positioning + volume charts |
| `gs credit reports - credit volatility report` | Credit | Credit vol chart pack |
| `gs clo secondary` | Credit | CLO secondary market run sheets |
| `gs what is priced in` | Macro | Raw CB meeting probability numbers + boilerplate |

Drop reason logged as `title-prefix:'<prefix>'`. These are also caught
defence-in-depth by the prose-density gate if the title match is missed.

Note: the GS Rates MarketStrats family was previously ingested as RATES (confirmed
by the 2026-06-12 state table above, e.g. "GS Rates MarketStrats - Global Bond
Futures Carry"). These now drop at discovery.

## Last verified

2026-06-15 — `_CHART_ONLY_TITLE_PREFIXES` added to `filters/goldman.py` (12 series
prefixes confirmed low-value by content audit). These complement the Tier-5
classifier and prose-density gate as a discovery-stage drop.

2026-06-14 — Coverage audit (read-only) confirmed all major macro / CB /
rates-FX franchises kept in text. DB reconciled to current logic: **272
stale-leak rows deleted end-to-end** (DB + Qdrant + SharePoint) via
`cleanup_goldman_stale.py`; **Tier-5 content-title classifier** added +
hardened post-review (74 tests); **169 blank rows backfilled** (45
reclassified-kept / 74 equity-leak deleted / 50 residual blank). Goldman
now 713 rows, EQUITY down to 37, blank down to 50. Tier-5 propagates the
fix to all future ingests.

2026-06-12 — Stage 1 + 2 + classifier patch landed. Backfill of
2026-06-09..06-12 window: **243 inserted / 51 dup / 37 fail / 88.5%
success** (was 5.6% the day before with the `render_mode` threading
bug). Cross-asset coverage normalised: RATES 36 / FX 24 / CREDIT 14 /
COMMODITIES 13 / MACRO 67 / EQUITY 55 (over 3 days). 113 historical
blank-asset_class rows re-classified by the Tier-3.5 desk-naming
patterns + Alpha Generation Call fix.
