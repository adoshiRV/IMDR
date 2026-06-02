# Westpac IQ — Research scraper

Pattern: **D — Inline-JSON cards with two-step PDF resolver.** Adobe
Experience Manager (AEM) microsite. Both hubs render the latest 50
article cards as inline JSON in the HTML; the PDF link is **inside
the card's `executiveSummary` HTML body** (relative
`/content/dam/public/.../*.pdf`). For Economics articles whose
hub-card `executiveSummary` is a stub, fall back to the detail page
(a small 98KB server-rendered shell) and regex an absolute
`<a href="https://library.westpaciq.com.au/.../pdf">` link.

This is a new pattern (D) in [`scrapers/index.md`](index.md). Unlike
B (direct-PDF + one-extra-GET) the listing is HTML not JSON and the
per-card body is already JSON-embedded in the hub; no listing API
exists.

Onboarded 2026-06-01 to 2026-06-02. First end-to-end ingest:
2026-06-02, 13 reports written (`dim_report.id` 2309–2347, with gaps
where other vendors interleaved).

## Portal

| | |
|---|---|
| Hostname | `www.westpaciq.com.au` |
| Sign-in URL | `https://www.westpaciq.com.au/` (login form) |
| Username | see `.env: IMDR_RESEARCH_WESTPAC_USERNAME` |
| Password | in `.env: IMDR_RESEARCH_WESTPAC_PASSWORD` |
| MFA | TBD — confirm during phase 1 interactive login |

## Profile

```
playground/research/profiles/westpac/
```

Fresh persistent Chrome profile. The inherited `westpac-probe` folder
under `Z:\...\playwrights\` was empty, so first interactive login is
required to seed cookies.

## Phase status

| Phase | Status | Notes |
|---|---|---|
| 0 — gate | done | Creds in `.env`, AU/NZ macro/rates/FX/credit/commodities vendor; in scope. No per-session MFA. |
| 1 — explore | done | `playground/research/explore_westpac.py`; 8 snapshots in `westpac_explore/`. |
| 2 — listing API | done | No JSON API; HTML hub pages with inline JSON cards. See below. |
| 3 — crawler | done | `ingest/crawler_westpac.py` with two-step PDF resolver (card es → detail-page fallback). |
| 4 — filter + classifier | done | `filters/westpac.py` (empty by design — to tune empirically). `classifiers/westpac.py` with primary-tag-only matching + theme/discipline routing. |
| 5 — orchestrator wiring | done | Registered in `ingest_today.py` and `classifiers/__init__.py`. |
| 6 — DB seed + smoke | done | Migration 061 applied 2026-06-02. First smoke (`--embed=false` no limit): 13 inserts + 3 dups across 4-day window. |
| 7 — promote | pending | Embed-on full run + vendors.yml flip. |

## Daily volume

Observed from the first 4-day smoke run (2026-05-30 to 2026-06-02):

| Bucket | Count | Notes |
|---|---:|---|
| Cards in window (Economics + Markets) | 21 | ~5/day, both hubs combined |
| PDF resolved from card `executiveSummary` | 12 | 92% of resolved — fast path |
| PDF resolved via detail-page fallback | 1 | Economics card with stub `executiveSummary` |
| Dropped `no_pdf` | 8 | All genuinely HTML-only briefings — see "Non-PDF assets" |
| **Net into corpus** | **13** | ~3/day |

Steady-state estimate: **~15–25 net PDFs/day** (the 4-day window was
mid-week; weekends are lighter).

## Listing source (Phase 2)

Westpac IQ is built on **Adobe Experience Manager (AEM)**. The two
hub pages

```
https://www.westpaciq.com.au/economics
https://www.westpaciq.com.au/markets
```

are **server-rendered HTML**. Each hub serves the latest 50 cards as
inline JSON blobs, with one full metadata object per article embedded
in the page HTML. The AEM `article-aggregator` JavaScript widget
hydrates the same data client-side and (presumably) handles
load-more via XHR, but **for daily ingest we don't need pagination**:
50 cards covers ~5 weeks of publications per hub.

Probed via `playground/research/probe_listing_apis.py` on 2026-06-01.
No JSON listing API was tripped during load — all captured responses
were AEM design-library assets (CSS/JS). The aggregator XHR only fires
on user interaction (scroll, filter, load-more). Probe output:
`westpac_explore/listing_apis.json` (all score=0).

### Per-card JSON schema (extracted from hub HTML)

| field | example | use |
|---|---|---|
| `articleId` | `"1780290383755"` | uuid (13-digit ms timestamp; per-doc) |
| `articleheadline` | `"Australian dwelling prices: Prices dip again"` | title |
| `publishdate` | `"2026-06-01T16:00:00.000+10:00"` | ISO 8601 with AEST/AEDT offset |
| `umbrella` | `"Economics"` / `"Markets"` | top-level section |
| `primarytag` | `"housing"` | primary topic |
| `secondaryTags` | `["housing"]` | extra topics |
| `publicationTag` | `"Economic Bulletins - Australia"` | series name |
| `articlePath` | `"/economics/2026/06/aus-cotality-dwelling-prices-may-2026"` | relative path to detail HTML |
| `articledescription` | `"May Cotality home value index: ..."` | short summary |
| `executiveSummary` | `"<p>The Cotality home value index...</p>"` | longer HTML summary |
| `newsAuthorDetails` | `[{authorName, bioCopy, ...}]` | author list |
| `authorTags` | `["westpaciq:authors/matthewhassan"]` | author slugs |
| `tagUrl` | `"/topic.housing"` | primary tag URL |
| `tagsValues` | `[]` | extra tag list |
| `timetoread` | `"5 mins"` | reading time |
| `isSecure` | `false` | (TBC) gates secure-only content |
| `fileReference` | `"https://library.westpaciq.com.au/.../image.jpg"` | hero image |

### Extraction

Each card is a JSON object embedded directly in the HTML. Cards
begin near an `"articleId"` key; the surrounding object can be lifted
with brace-matching (or by finding the article-aggregator container
and re-parsing its `data-` attribute, TBC during Phase 3).

## URL patterns

### Article detail (HTML)

```
https://www.westpaciq.com.au/{umbrella_path}/{YYYY}/{MM}/{slug}
```

Where `{umbrella_path}` is `economics` or `markets`. Examples:

* `https://www.westpaciq.com.au/economics/2026/06/aus-cotality-dwelling-prices-may-2026`
* `https://www.westpaciq.com.au/markets/2026/06/WhatsPricedIn20260601`

`articlePath` in the card JSON is a relative URL — prefix with
`https://www.westpaciq.com.au` to get the absolute.

### PDF (one extra GET)

```
https://library.westpaciq.com.au/content/dam/public/westpaciq/secure/{umbrella}/{subdir}/{country}/{YYYY}/{MM}/{filename}.pdf
```

Examples:

* `https://library.westpaciq.com.au/content/dam/public/westpaciq/secure/economics/documents/aus/2026/06/er20260601BullCotalityDwellingPrices.pdf`
* `https://library.westpaciq.com.au/content/dam/public/westpaciq/secure/markets/article/aus/2026/06/WhatsPricedIn_20260601.pdf`

**The PDF URL is not derivable from `articleId` or `articlePath`** —
the filename slug differs. To get the PDF URL the crawler must fetch
the article detail HTML and extract the first `href` matching
`https://library\.westpaciq\.com\.au/[^"]+\.pdf` (typically inside an
`<a class="icon-doc-link">` link labelled "Read full report").

### Topic / author / search

* Topic tag pages: `https://www.westpaciq.com.au/topic.{slug}` (e.g.
  `/topic.rba`, `/topic.fx`, `/topic.morningreport`). Not used by the
  crawler — `primarytag` and `secondaryTags` are already in the card.
* Author pages: `https://www.westpaciq.com.au/authors/{slug}`.
* Search: `https://www.westpaciq.com.au/search` (full-text search;
  may expose a different listing API — not yet probed).

## Fetch strategy — two-step PDF resolver

```
hub HTML (one GET per hub, 50 cards each)
  → parse cards (json.JSONDecoder.raw_decode around "articleId")
  → for each in-window card:
      step 1: regex executiveSummary for /content/dam/public/.../*.pdf
              → prefix with https://library.westpaciq.com.au, done.
      step 2 (only if step 1 misses): GET articlePath, regex
              <a href="https://library.westpaciq.com.au/.../pdf">.
      else: drop with reason="no_pdf".
```

Logs a one-line PDF-source breakdown at end of discovery
(`card_es=N, detail_page=N, no_pdf=N`) so the operator can see the
fast-path / fallback / drop ratio without grepping.

Persistent-profile cookies via `ctx.request.get()`. No custom
headers required (no `x-csrf-token`, `janus_user`, or similar).

### Why two steps?

* **Markets cards** carry the full article body (with PDF link) in
  `executiveSummary`. Their detail pages are a **2.6MB SPA shell**
  that does not expose the PDF as a real `<a href>` to a static
  fetch — the link only appears in the live DOM after JS runs in a
  headed Chrome session. Step 1 lifts the link straight out of the
  card.
* **Economics cards** vary. ~60% include the full body in
  `executiveSummary` (step 1 catches them). The other ~40% have a
  stub `executiveSummary` (under 1KB, no PDF link). For these, the
  detail page is a small server-rendered shell with the PDF link as
  a real `<a href="https://library...">`; step 2 catches it.
* **HTML-only Markets briefings** (FinanceAM, Around the Grounds,
  Strategy Views on a Page, daily AUD/NZD updates) genuinely have
  no PDF rendition — they're web-native. Both steps miss; the card
  is dropped with `no_pdf`. This is correct.

Discovered the hard way during the first smoke run on 2026-06-02 —
the naive detail-page regex flagged 15/21 candidates as `no_pdf` due
to the Markets SPA shell issue. The two-step resolver brings that
down to 8 legitimate drops.

## Watermarks / quirks

* Publication timestamps are in **Australian Eastern Time** (AEST
  `+10:00` / AEDT `+11:00`). Convert to UTC before storing — DST
  shift happens twice yearly. Source is ISO 8601 with explicit
  offset, so `datetime.fromisoformat()` parses correctly.
* The `articleId` is a 13-digit milliseconds-since-epoch value, not a
  UUID. Treat as opaque string; do not try to interpret as a date.
* `isSecure: false` was observed on the test article — true Westpac
  IQ articles are all behind login but the per-article flag may
  indicate further access restrictions (e.g. institutional-only).
  Confirm during Phase 6.
* Some markets articles use underscore-separated slugs
  (`WhatsPricedIn20260601`); some economics articles use hyphenated
  English slugs. Both reach `articlePath` cleanly.

## Non-PDF assets

Observed at first smoke run (8 legitimate `no_pdf` drops across a
4-day window):

* **HTML-only daily/weekly Markets briefings** that have no PDF
  rendition — the article body IS the deliverable:
  * `FinanceAM` (daily overnight wrap)
  * `Around the Grounds` (daily debt-markets briefing)
  * `Strategy Views on a Page` (daily strategy roundup)
  * `Australian Dollar update` (intraday FX colour)
* **HTML-only Economics briefings** in the same vein:
  * `Minimum wage and awards increase by X%` (short news bulletin)
* **Securitisation weekly notes** that are HTML pages
  (`ABSolute Coverage - Securitisation & Covered Bond Weekly Update`,
  `APRA ADI Statistics`).

These all return zero hits across both PDF-resolver steps and drop
with `[DROP] <uuid> no_pdf=no_pdf <title>` — exactly the
"no PDF rendition advertised by the vendor" condition per the
playbook's `no_pdf` (not `unparseable`) labelling rule.

Phase 1 snapshots also flagged occasional **video explainers**
("Federal Budget … with Chief Economist Luci Ellis") and
**infographics**. These either:

* Pair with a slide-deck PDF embedded in the executiveSummary — step
  1 catches them and they ingest normally; or
* Are pure-video / pure-image — step 1 + 2 miss, drop with `no_pdf`.

Audio/podcast title-keyword scan after first smoke: **0 hits**.

## Classifier notes

`classifiers/westpac.py` matches **primary tag only** — the editorial-
intended category. Secondary tags would otherwise mis-classify the
report: a Morning Report card ships with
`secondaryTags=['commodities', 'interestrates', 'usd', 'aud',
'australia']`, and first-match-wins on secondaries arbitrarily picks
"commodities" as asset_class. Primary-tag-only fixes that — Morning
Report's `primarytag="morningreport"` falls through to the
umbrella-aware default (MACRO for Economics, STRATEGY for Markets).

### Theme vs discipline tag routing

`research.dim_tag` enforces global uniqueness on the `tag` value
alone. If the classifier emits `Tag("theme", "commodities")` but a
`Tag("discipline", "commodities")` row already exists (which it does,
from BNP/HSBC/ANZ classifiers), the writer reuses the existing
discipline-categorised row — so the report ends up wrongly tagged
with discipline=commodities instead of theme=commodities.

Fix: route secondary tags that match the canonical asset-class
vocab (`fx`, `rates`, `credit`, `commodities`, `macro`, `equity`,
`esg`, `strategy`, plus AEM-spelling variants like `interestrates`)
to `TAG_DISCIPLINE`; emit the rest as `TAG_THEME`. See
`_SECONDARY_TO_DISCIPLINE` in `classifiers/westpac.py`. This mirrors
BNP's `_discipline_tags` pattern.

## Hard taxonomy probe + tightening (2026-06-03)

Probe artefacts in
[`taxonomy_probe/westpac_full.md`](../../../../playground/research/taxonomy_probe/westpac_full.md),
[`taxonomy_probe/westpac_db_audit.md`](../../../../playground/research/taxonomy_probe/westpac_db_audit.md),
[`taxonomy_probe/westpac_full_sample.json`](../../../../playground/research/taxonomy_probe/westpac_full_sample.json).
Re-runnable probe at
[`probe_westpac_full.py`](../../../../playground/research/probe_westpac_full.py).

### Wins

**1. Missing hub recovered.** Westpac IQ has THREE hubs, not two:
`/economics`, `/markets`, **`/thought-leadership`**. The crawler now
hits all three. Thought-leadership publishes Sustainability /
Innovation / Industry insights at monthly-ish cadence (50 cards span
~8 months — sparse but valuable macro-adjacent content per the
user's "trends ok" guidance).

**2. Structured fields lifted from inline card JSON.** ReportRef now
carries 5 additional fields probed from the 150-card sample:

| field | values observed | use |
|---|---|---|
| `inv_recomm_parent` | empty 73% / `Currencytickers` 12 / `topics` 8 / `investmentrecommendations` 8 / `swapsnz` 6 / `commoditytickers` 3 / `credittickers` 2 / `bondsotherglobaltickers` 2 | **Tier-0 asset_class** + single-name-credit drop |
| `inv_recomm_sub` | semicolon-delimited `category:value` pairs | **Bloomberg-ticker emission** for downstream RV joins |
| `youtube_id` | populated on 7/150 video explainers | `format:video` drop |
| `file_reference` | featured-image URL with semantic folder slugs | `format:podcasts` drop on `/podcasts/` slug |
| `hide_article` | string `'true'` on soft-deleted articles (1/150) | `hide-article` drop |

### Filter precedence (added 2026-06-03)

`filters/westpac.py` — first match wins:

1. `hide-article` (boolean from `hideArticle`)
2. `format:video` (`youtubeId` non-empty)
3. `format:<slug>` (`fileReference` matches `/podcasts/` / `/audio/` / `/video/`)
4. **`single-name-credit:credittickers`** — invRecommParentTag drop
5. Title-prefix admin (legacy, empty by default)
6. Title-substring (legacy, empty by default)

### Classifier Tier-0 (added 2026-06-03)

`classifiers/westpac.py`:

1. **Tier-0**: `invRecommParentTag` → canonical asset_class:
   `Currencytickers→FX`, `swapsau / swapsnz→RATES`,
   `commoditytickers→COMMODITIES`, `bondsotherglobaltickers→RATES`,
   `credittickers→CREDIT` (but filter-dropped at discovery).
2. **Tier-1**: existing primary_tag substring lookup (kept).
3. **Umbrella fallback**: Economics→MACRO, Markets→STRATEGY,
   **Thought leadership→ESG** (new).
4. **Tickers**: `_parse_inv_recomm_tickers` extracts Bloomberg
   tickers from `invRecommSubCategoriesTag` (`audcurncy`,
   `adsw10curncy`, `co1comdty`, etc.) and emits as `TAG_TICKER`.

### DB state

**Zero rows** — vendor seeded 2026-06-02 (yesterday), production
ingest hadn't run when the audit happened. Clean slate — no cleanup
work needed.

### 7-day smoke (2026-06-03)

Read-only via
[`smoke_westpac_7day.py`](../../../../playground/research/smoke_westpac_7day.py).
Log at
[`taxonomy_probe/westpac_smoke_7day.log`](../../../../playground/research/taxonomy_probe/westpac_smoke_7day.log).

| stage | count |
|---|---|
| hubs crawled | 3/3 — Economics (50), Markets (50), Thought-leadership (50) |
| raw cards processed | 150 — 134 unique (16 cross-hub overlap) |
| discovery drops | 0 (window had no podcasts/videos/hideArticle/credittickers) |
| in-window cards | 39 (~6/day, up from ~3/day pre-change) |
| relevance kept | **39 (100%)** |

`/thought-leadership` returned 50 cards but the oldest is
2024-10-31 — cadence is too slow for the 7-day window to show any
t/l cards. The structural fix is correct; over a 30-day window
we'd expect 3-5 sustainability/innovation pieces.

**Composition**:

| class | count | % |
|---|---|---|
| STRATEGY | 14 | 36% |
| MACRO | 13 | 33% |
| FX | 6 | 15% |
| RATES | 4 | 10% |
| COMMODITIES | 2 | 5% |

**Structured-signal coverage**: `inv_recomm_parent` 51%,
`inv_recomm_sub` 54% (ticker tags emitted), `youtube_id` 0%
(no videos this window), `is_secure` 54%.

**Country**: AU 16, NZ 3 (49% of survivors anchored).
**Region**: APAC 39/39.

**Sample kept titles**:
- MACRO: *"Australian dwelling approvals: turning point emerging?"*, *"Australian GDP: a preview bulletin"*, *"Westpac Card Tracker"*
- RATES: *"Estimating housing-related impacts on state revenues. - A$ & NZ$ Rates"*, *"NZGB Tender Preview"*, *"Review of RBNZ May 2026 Monetary Policy Statement"*
- FX: *"NZD FX Weekly"*, *"ForeX Focus"*, *"Macro FX Trade Ideas"*
- COMMODITIES: *"Australian Fuel Update"*, *"NZ Agri Bites"*
- STRATEGY: *"What's Priced In"*, *"Westpac Strategy Antipodean Daily Wrap"*, *"AUD Rates Morning Chartpacks"*

## Last verified

Phase 6 smoke completed 2026-06-02 (10 inserts + 3 dups). Phase 7
(embed-on + production flip) pending.

2026-06-03 — `/thought-leadership` hub added + structured-signal
filter (youtubeId / hideArticle / credittickers) + Tier-0
classifier from invRecommParentTag + Bloomberg-ticker emission
landed in playground (gitignored). 7-day smoke shows ~6/day kept
(up from ~3/day), 100% kept at relevance, pure
STRATEGY 36% / MACRO 33% / FX 15% / RATES 10% / COMMODITIES 5%
composition with 51% inv-parent coverage on survivors.
