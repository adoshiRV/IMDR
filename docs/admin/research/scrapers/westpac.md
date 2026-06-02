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

## Last verified

Phase 6 smoke completed 2026-06-02 (10 inserts + 3 dups). Phase 7
(embed-on + production flip) pending.
