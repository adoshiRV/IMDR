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
5. Title regex (final fallback)

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
