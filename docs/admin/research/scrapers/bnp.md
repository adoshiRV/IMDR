# BNP Paribas — Research scraper

> **Status**: Phase 1 (explore-only). No crawler, no filter, no
> classifier yet. This page captures what's known before any
> interactive exploration. Update as we learn more.

## Portal

| | |
|---|---|
| Hostname | `markets360.bnpparibas.com` |
| Portal home (SPA route) | `https://markets360.bnpparibas.com/contentportal/portal-content-service/markets360` |
| SSO host | `ssologin.bnpparibas.com/cib/LoginForm.aspx` (client path); employees use `ssoforms.cib.echonet` (SAML2, internal-only) |
| Username | `rmahadevan@rvcapital.com` (Rajesh Mahadevan, confirmed at phase-1 login 2026-05-26) |
| Password | not in `.env` yet — Chrome profile retained it after manual login |
| MFA | None observed at first login (one-shot username/password via SiteMinder) |

`.env IMDR_BNP_URL` points at the SPA route, **not** a JSON API. The
captured HTML shows `<base href="/contentportal/portal-content-service/">`
and renders an Angular app (`gmportal-search-filter`,
`gmportal-search-page`, `gmportal-tag-filter`) — build version
`7.15.1-3-1a3f61d`. Report cards load via XHR after the SPA boots; the
captured post-login HTML is the bare shell (0 headings, 1 link).

The listing API will be a sub-path under `/contentportal/portal-content-service/`
loaded via XHR — same shape as Morgan Stanley's
`/portal-content-service/search` but mounted under
`/contentportal/`. Confirm in phase 2 via
[`probe_listing_apis.py`](../../../../playground/research/probe_listing_apis.py).

The URL stored in `.env` is the **content-service path**, not the
portal home. The path shape — `…/portal-content-service/…` — is
**identical to Morgan Stanley Matrix's** backing API
(`/portal-content-service/search`); see [ms.md](ms.md). Strong prior
that BNP runs the same Salesforce-based portal framework, which would
mean:

* Listing via `POST /portal-content-service/search` with a similar
  `{compositeRequest: {search, sort, size, page}, arRequest: {...}}`
  body.
* Per-document `/frontmatter?uuid=…` to retrieve the `pdfRenditionUrl`.
* Pagination via `page` + `size`.

This is a hypothesis to **test in phase 2**, not a fact. If `.env`'s
URL turns out to be a different shape, scrap this assumption and run
[`probe_listing_apis.py`](../../../../playground/research/probe_listing_apis.py)
from scratch.

## Profile

```
playground/research/profiles/bnp/
```

Fresh profile — not in the inherited playwrights folder. First
interactive login required.

## Pattern

TBD. Hypothesis: **A. Listing-API firehose** (same as MS) + a "fetch
signed link by UUID" call before each PDF GET (similar to MS's
`/frontmatter?uuid=…` lookup that returns `pdfRenditionUrl`). Confirm
in phase 2.

## Per-report URL anatomy (phase 1 sample, 2026-05-26)

Two observed shapes for the same publication:

**Short form** (likely a server-side shortener mapping → the signed
form below):

```
https://markets360.bnpparibas.com/evo/slink/rLMtKbwEU380Ff
```

**Signed form** (a JWS — `header+payload+signature` with `+` replacing
the usual `.` separator, since `.` is reserved in URL paths here):

```
https://markets360.bnpparibas.com/evo/slink/<HEADER>+<PAYLOAD>+<SIGNATURE>
```

The header is the literal `eyJhbGciOiJIUzI1NiJ9` (`{"alg":"HS256"}`).
The payload is a base64url-encoded JSON object. The signature is an
HMAC-SHA256 binding the (uuid, publication-id, user-id, channel)
tuple — i.e. the signed link is **user-scoped**.

Example decoded payload (from the sample link):

```json
{
  "iss": "bnpp-evo",
  "sub": "ab5e3e95-c5c3-414f-9508-e729255bef22",
  "publication-id": 924840,
  "user-id-type": "ECO",
  "publication-type": "Deep Dive",
  "user-id": "ECO-EY31H1",
  "link-channel": "PORTAL",
  "distribution-id": null,
  "topic-ids": null
}
```

| field | meaning |
|---|---|
| `iss` | always `"bnpp-evo"` (Evolution platform) |
| `sub` | **stable document UUID** — use as `report.uuid` |
| `publication-id` | **secondary stable ID** (numeric, 6 digits) — keep alongside UUID |
| `publication-type` | matches the card chip (`Deep Dive`, `Quant Vault`, `Data Watch`, `Focus`) — use as `vendor_pubtype` |
| `user-id-type` | `ECO` for our client account |
| `user-id` | Rajesh's account ID (`ECO-EY31H1`); leaks into signatures |
| `link-channel` | `PORTAL` (vs presumably `EMAIL`) |
| `distribution-id` / `topic-ids` | usually null on portal-channel links |

Implications for the crawler:

* The listing API will return the UUID + publication-id as plain
  fields. No need to scrape signed links from the SPA.
* PDF fetch will either (a) compose a deterministic URL from UUID,
  or (b) ask a "create signed link" endpoint for a fresh JWS at
  fetch time — to be determined in phase 2.
* Signed links **embed our user-id** in the JWS payload. Don't
  share them outside the ingest pipeline; don't store them in DB.
  Store the stable UUID in `dim_report.vendor_uid` instead.
* Watermark stripping — bank PDFs often embed the recipient email
  or user-id; check parsed text for `ECO-EY31H1`,
  `rmahadevan@rvcapital.com`, "rajesh.mahadevan" patterns and add
  to `parse._normalise_for_hash()` if found.

## Daily volume

UI shows **16,299 results over Last 3 Years** in the MARKETS 360
section (API `totalHit: 16300`) → **~15/day** average. First live API
probe on 2026-05-26 confirmed **18 reports published that day**, all
from MARKETS 360 / Strategy & Economics, spanning Blog (5), Data Watch
(8), Deep Dive (1), Focus (1), Quant Vault (1), Trade Ideas (1).

## Listing API (confirmed 2026-05-26)

```
PUT https://markets360.bnpparibas.com/contentportal/research-service/v1.1/research_documents
Content-Type: application/json
```

**Request body**:

```json
{
  "domain": "RESEARCH",
  "searchText": null,
  "startIdx": null,
  "numOfEntries": 48,
  "publicationTypes": null,
  "issuers": null,
  "tickers": null,
  "regions": null,
  "assetClasses": null,
  "authors": null,
  "languages": ["English"],
  "startDate": "now-3y/d",
  "endDate": null,
  "industryGroups": null,
  "currentTimeZone": "Asia/Singapore"
}
```

**Body field meanings** (and how they map to the UI filter panel):

| API field | UI control | Notes |
|---|---|---|
| `domain` | top-nav (MARKETS 360, CREDIT 360, …) | `"RESEARCH"` covers MARKETS 360; CREDIT 360 likely a different value (TBD) |
| `searchText` | search bar | null = no full-text filter |
| `startIdx` | pagination | offset; `null` = page 1; `48` = page 2 |
| `numOfEntries` | (n/a) | page size — request was 48, response returned 46 (server caps?). Push higher in phase 3 |
| `publicationTypes` | publication-type chip filter | list of strings, null = all. Values: `Blog`, `Deep Dive`, `Quant Vault`, `Data Watch`, `Focus`, `Trade Ideas`, … |
| `issuers` / `tickers` / `industryGroups` | (single-name filters) | list, null = all. Populated rows = single-name research → candidate for relevance-filter drop |
| `regions` | region facet | list. Values: `Asia Pacific`, `Europe`, `CEEMEA`, `North America`, `Latin America` |
| `assetClasses` | asset-class facet | list. Values: `FX`, `Rates`, `Economics`, `Equity Derivatives Strategy`, `Cross Asset`, `Macro Quant`, `Commodities`, `Sustainability`, `Credit` |
| `authors` | AUTHOR facet (Select from 86) | author UUIDs (matches `/author-service/.../authors`) |
| `languages` | LANGUAGE facet | `English` / `French` / `Japanese` / `Chinese` |
| `startDate` | VIEW FROM presets | Elasticsearch date-math: `now-3y/d`, `now-1d/d`, `now-1w/d`, etc. |
| `endDate` | (custom range upper) | null = open |
| `currentTimeZone` | (client tz) | influences day-boundary on date math |

**For daily ingest** use:

```json
{
  "domain": "RESEARCH", "numOfEntries": 200, "startIdx": null,
  "languages": ["English"], "startDate": "now-1d/d", "endDate": null,
  "currentTimeZone": "UTC",
  ... // all other filters null
}
```

then paginate `startIdx += 200` until the response has fewer than 200
docs (or oldest `publishDate` < since).

**Response shape**:

```json
{
  "totalHit": 16300,
  "researchDocuments": [
    {
      "id": "924982",
      "documentLink": "https://markets360.bnpparibas.com/evo/slink/<JWS>",
      "attachmentLinks": [],
      "primaryAuthor": "Oliver Brennan",
      "publishDate": "Tue, 26 May 2026 11:21:00 GMT",
      "lastModifiedTime": "Tue, 26 May 2026 11:21:00 GMT",
      "readCount": 0,
      "title": "FX vol strategy weekly: ...",
      "summary": "<HTML blob, ~2-4KB, contains inline links to related slinks>",
      "tags": {
        "assetClasses": ["FX"],
        "authors": ["Oliver Brennan"],
        "industryGroups": [],
        "languages": ["English"],
        "publicationTypes": ["Blog"],
        "regions": ["Asia Pacific","Europe","CEEMEA","North America","Latin America"],
        "tickers": [],
        "issuers": [],
        "quantModels": []
      }
    },
    ...
  ]
}
```

**Field → ReportRef mapping**:

| `ReportRef` field | source |
|---|---|
| `uuid` | derive by decoding `documentLink` JWS payload's `sub`, OR keep `id` and call it `vendor_uid` |
| `vendor_uid` (numeric) | `id` |
| `title` | `title` |
| `publish_date` | parse `publishDate` (RFC 2822) |
| `pdf_url` | `documentLink` — **directly fetchable** with `ctx.request.get()` after SPA bootstrap |
| `primary_author` | `primaryAuthor` |
| `authors` | `tags.authors` |
| `asset_class` | `tags.assetClasses` (first or joined) |
| `regions` | `tags.regions` |
| `publication_type` | `tags.publicationTypes[0]` |
| `abstract` | `summary` (HTML — strip tags for classifier context) |
| `single_name_signals` | `tags.tickers` + `tags.issuers` + `tags.industryGroups` non-empty = candidate for single-name-equity drop |

**Full-day sample** (2026-05-26, 21 reports, pulled via paginated probe
2026-05-27) — full JSON saved to
[`bnp_explore/probe_pdf/bnp_full_day_2026-05-26.json`](../../../../playground/research/bnp_explore/probe_pdf/bnp_full_day_2026-05-26.json):

```
id      publishDate            pub-type     asset-class                                    title                                                                            summary
924934  Tue 02:00 GMT          Trade Ideas  FX, Rates                                      EM rates: Take profit on KRW 1y receiver...                                      Two received positions in front-end KRW rates (narrative)
924939  Tue 04:33 GMT          Blog         Rates                                          Japan: 40y JGB auction comment                                                   Auction size & market supply analysis (narrative)
924944  Tue 05:47 GMT          Blog         Economics, FX, Rates                           EM Asia: What you need to know this week (25-31 May)                             Weekly preview (narrative)
924961  Tue 06:50 GMT          Data Watch   FX                                             FX options strike maps (26 May 2026)                                             "Update of the latest values and charts"  <-- CHART-PACK
924962  Tue 07:08 GMT          Data Watch   Macro Quant                                    BNP Paribas Risk Premium Index Update                                            "Update of the latest values."            <-- CHART-PACK
924965  Tue 07:42 GMT          Data Watch   Macro Quant                                    MarFA Macro Update                                                               "Update of the latest values"             <-- CHART-PACK
924966  Tue 07:44 GMT          Data Watch   Macro Quant                                    MarFA Trading Update                                                             "Update of the latest values"             <-- CHART-PACK
924969  Tue 08:41 GMT          Data Watch   Equity Deriv, Macro Quant                      BNP Paribas EU Equity Positioning Indicator                                      "Update of the latest values"             <-- CHART-PACK
924970  Tue 08:44 GMT          Data Watch   Equity Deriv, Macro Quant                      BNP Paribas US Equity Positioning Indicator                                      "Update of the latest values"             <-- CHART-PACK
924971  Tue 08:45 GMT          Data Watch   Equity Deriv, Macro Quant                      BNP Paribas Japan Equity Positioning Indicator                                   "Update of the latest values"             <-- CHART-PACK
924972  Tue 08:48 GMT          Data Watch   Equity Deriv, Macro Quant                      BNP Paribas China Equity Positioning Indicator                                   "Update of the latest values"             <-- CHART-PACK
924973  Tue 08:52 GMT          Data Watch   Equity Deriv, Macro Quant                      BNP Paribas US Tactical Equity Indicator                                         "Update of the latest values"             <-- CHART-PACK
924974  Tue 09:18 GMT          Blog         Economics, FX, Rates                           EM/CEEMEA: What you need to know this week                                       US-Iran de-escalation (narrative)
924976  Tue 09:20 GMT          Focus        Rates                                          G10 rates: Eurex futures rolls M6 – U6                                           Schatz/Bobl/Bund/Buxl/IK roll analysis (narrative)
924977  Tue 09:37 GMT          Data Watch   FX                                             FX vol weekly chart pack                                                         "updates key indicators..." (one-line description, pure charts inside)
924980  Tue 10:47 GMT          Quant Vault  Equity Deriv, Cross Asset, Macro Quant         HEXA weekly update 26 May                                                        "Latest update of HEXA" (model output)
924840  Tue 11:00 GMT          Deep Dive    Economics, Equity Deriv, FX, Rates, Credit     Fed: The balance sheet under Warsh                                               KEY MESSAGES + analysis (flagship piece)
924982  Tue 11:21 GMT          Blog         FX                                             FX vol strategy weekly: EUR downside the weak side                               EUR put vol, USDJPY, HUF vol (narrative)
924830  Tue 13:07 GMT          Blog         FX, Rates                                      EM/LATAM: What you need to know this week                                        Colombia election + LATAM preview (narrative)
924983  Tue 13:11 GMT          Focus        Commodities                                    Sulphur: High stakes, high prices for metals producers                           KEY MESSAGES + market analysis (narrative)
924992  Tue 15:51 GMT          Data Watch   FX                                             BNPP cross-border flow monitor update                                            KEY MESSAGES + flow analysis (narrative — exception to chart-pack pattern)
```

**Aggregates** (21 reports on 2026-05-26):

| Publication-type | Count | Share |
|---|---:|---:|
| Data Watch | 11 | 52% |
| Blog | 5 | 24% |
| Focus | 2 | 10% |
| Trade Ideas | 1 | 5% |
| Quant Vault | 1 | 5% |
| Deep Dive | 1 | 5% |

| Asset-class (multi-tagged) | Count |
|---|---:|
| FX | 9 |
| Macro Quant | 9 |
| Rates | 7 |
| Equity Derivatives Strategy | 7 |
| Economics | 3 |
| Cross Asset | 1 |
| Credit | 1 |
| Commodities | 1 |

| Region (multi-tagged) | Count |
|---|---:|
| Asia Pacific | 14 |
| North America | 12 |
| Europe | 11 |
| CEEMEA | 10 |
| Latin America | 10 |

**Single-name signals (tickers / issuers / industryGroups populated)**:
**0 of 21** — BNP Markets360 is a pure macro / strategy desk; the
existing `relevance.py` single-name-equity drop will never trigger.

## Filter scope — recommendation

Two signals to filter on, both at the **discovery-filter** stage
(`filters/bnp.py`) so we never fetch the PDF or burn embedding spend.

### 1. Chart-pack drop (proposed, default ON)

Half of BNP Markets360's daily output is **recurring chart-pack
"Data Watch" updates** whose entire PDF is figures + tables with
essentially no narrative text. PyMuPDF will extract nothing useful,
embeddings won't retrieve anything meaningful, and they recur every
day with the same title.

**Drop heuristic** — match on the `summary` field. **Gotcha**: BNP
prefixes every summary with a literal ``| `` decoration, e.g.
``"| Update of the latest values |"``. The matcher must strip leading
non-alphanumerics before the prefix check, else nothing matches. This
is handled in `filters.match_summary_prefix` (HTML-strip → collapse
whitespace → lowercase → strip leading punctuation → `startswith`):

```python
# filters/bnp.py
EXCLUDED_SUMMARY_PREFIXES = ("update of the latest values",)
# matched via filters.match_summary_prefix, which strips the leading "| ".
```

> **Incident (2026-05-27)**: the first production ingest leaked 16
> chart-packs (across 2026-05-25/26) into DB + OneDrive + Qdrant
> because the original matcher did a bare `startswith` that the
> leading ``| `` defeated. Fixed in `match_summary_prefix`; the leaked
> rows were removed via
> [`cleanup_bnp_chartpacks.py`](../../../../playground/research/cleanup_bnp_chartpacks.py)
> (re-fetches summaries, applies the fixed filter, deletes the exact
> matches). Regression pinned by
> [`test_bnp_filter.py`](../../../../playground/research/test_bnp_filter.py).

Applied to today's 21 reports this drops **9** (43%):

* All 5 BNP Paribas Equity Positioning Indicators (EU/US/Japan/China/US-Tactical)
* MarFA Macro Update + MarFA Trading Update
* BNP Paribas Risk Premium Index Update
* FX options strike maps

It correctly **keeps** the FX vol weekly chart pack (one-line
descriptive summary, still mostly figures — leave for now, can
tighten later if PDF text is empty) and the BNPP cross-border flow
monitor update (has a real KEY MESSAGES summary).

### 2. Pub-type pass-through (no drops)

All six observed publication types (Blog, Data Watch, Focus, Trade
Ideas, Quant Vault, Deep Dive) are PDF-bearing research. No
non-PDF tile types observed (no Podcast / Video / "5 in 5" equivalent
in MARKETS 360). Don't pre-filter on `publicationType`.

### 3. Single-name-equity (existing filter, no change)

`relevance.py`'s single-name drop runs post-classifier. BNP Markets360
never populates `tickers` / `issuers` / `industryGroups`, so this
filter is a no-op for BNP — confirmed against 21/21 today.

If we ever wire **CREDIT 360** (separate top-nav, separate `domain`),
that may pull single-issuer notes — re-evaluate the filter then.

### 4. Language

Pin the API call to `languages: ["English"]`. The full UI offers
French/Japanese/Chinese; we only want English.

### Resulting net daily volume

* **Discovered** (API, English only, MARKETS 360): ~18–21/day (21 sampled)
* **After chart-pack drop**: ~10–12/day kept (12 today)
* **After single-name relevance filter**: same (no-op for BNP)
* **Net into the per-PDF pipeline**: ~10–12/day

That's high signal density — comparable to Goldman/MS post-filter
volume per "useful piece per day" rather than per "discovered piece".

### Watermark stripping (note for parse stage)

BNP PDFs likely embed `ECO-EY31H1` or `rmahadevan@rvcapital.com` as a
per-download watermark (consistent with the JWS payload encoding the
user-id). After first ingest, inspect the parsed text for either
string and add to `parse._normalise_for_hash()` so the
content-hash idempotency check works across daily re-fetches.

## Filter panel — observed from UI (2026-05-26)

The captured screenshot of the left-rail filter panel:

| UI control | Options | API mapping |
|---|---|---|
| AUTHOR | ALL / Select from **86** | `authors: [uuid,...]` (author UUIDs from `/author-service/.../authors`) — we always send null (no per-author filter) |
| AUTHOR TEAM | ALL / **MARKET 360** / **DESK STRATEGY** | not surfaced in captured body — ignore; we want both teams |
| LANGUAGE | **ENGLISH** / FRANÇAIS / 日本語 / 中文(简) | `languages: ["English"]` |
| VIEW FROM | TODAY / 3 DAYS / 1 WEEK / 1 MONTH / 6 MONTHS / 1 YEAR / **LAST 3 YEARS** / CUSTOM | `startDate: "now-Nd/d"` / `now-Nw/d` / `now-Ny/d` |

## Asset-class facet (left-nav of main listing)

Confirmed values from screenshot + today's observed reports:

* `Commodities`, `Cross Asset`, `Economics`,
  `Equity Derivatives Strategy`, `FX`, `Macro Quant`, `Rates`,
  `Sustainability`. **Plus** `Credit` (seen in today's "Fed balance
  sheet" Deep Dive — likely shows up for CREDIT 360 too).

All are IMDR-relevant. Single-name signals (`tags.tickers`,
`tags.issuers`, `tags.industryGroups`) get checked by the existing
relevance filter.

## Listing UI observations (2026-05-26, phase 1)

Pulled from the post-login MARKETS 360 page; useful for the
discovery-filter / classifier design later.

**Asset-class facets** (left-nav, queryable on the API):

* `COMMODITIES`, `CROSS ASSET`, `ECONOMICS`,
  `EQUITY DERIVATIVES STRATEGY`, `FX`, `MACRO QUANT`, `RATES`,
  `SUSTAINABILITY` — all IMDR-relevant; no blanket filter needed,
  the existing single-name-equity relevance filter should handle
  the noise.

**Author teams**: `MARKET 360`, `DESK STRATEGY` — tag both.

**Publication types** observed in card chips: `DEEP DIVE`,
`QUANT VAULT`, `DATA WATCH`, `FOCUS`. Use as `vendor_pubtype` in
the classifier.

**Language facet**: ENGLISH default; also French, Japanese, Chinese.
Lock API call to ENGLISH only.

**Date filter** (UI presets): `TODAY / 3 DAYS / 1 WEEK / 1 MONTH /
6 MONTHS / 1 YEAR / LAST 3 YEARS / CUSTOM` — strongly implies the
API takes a date range parameter; prefer server-side `since=` over
scroll-and-stop.

**Adjacent sections** in top nav (not yet scoped):
`MY FEED, MARKETS 360, CREDIT 360, QUANT VAULT, SUSTAINABILITY,
MEDIA LIBRARY, BLOGS, FORECASTS, CALENDARS`. Start with MARKETS 360;
revisit CREDIT 360 once macro ingest is stable.

**Signed-in principal**: Rajesh Ayodya Mahadevan
(`rmahadevan@rvcapital.com`, RV Capital Management Private —
Singapore). Profile retained the username; first interactive login
took manual password entry. Add `IMDR_RESEARCH_BNP_USERNAME` /
`…_PASSWORD` to `.env` once we're ready to automate.

## Phase 1 capture (2026-05-26)

Artefacts under
[`playground/research/bnp_explore/`](../../../../playground/research/bnp_explore/):

| idx | URL | notes |
|---|---|---|
| 0 | `ssologin.bnpparibas.com/cib/Select.aspx?...` | SSO landing — two paths: "I AM A BNP PARIBAS EMPLOYEE" (SAML2, internal) vs "I AM A BNP PARIBAS CLIENT" (LoginForm) |
| 1 | `ssologin.bnpparibas.com/cib/LoginForm.aspx?...` | LoginForm for client path; Chrome had `rmahadevan@rvcapital.com` saved |
| 2–3 | `markets360.bnpparibas.com/contentportal/portal-content-service/markets360` | Post-login SPA landing (Angular `gmportal-*` shell, 317 KB HTML, 0 visible headings) |

Listing UI confirmation came from screenshot inspection (16,299
results, facets, publication-types) rather than DOM scraping — the
HTML is a JS-rendered SPA shell.

## Onboarding plan

See [`../onboarding_new_vendor.md`](../onboarding_new_vendor.md) for
the full workflow. Per-phase status for BNP:

| Phase | Status |
|---|---|
| 0. Decide whether to onboard | done — ~15/day volume confirmed |
| 1. Explore-only | done — interactive login captured 2026-05-26 ([artefacts](../../../../playground/research/bnp_explore/)) |
| 2. Listing API discovery | done 2026-05-26 — `PUT /contentportal/research-service/v1.1/research_documents`. PDF fetch confirmed via `documentLink`. Full-day pull (21 reports on 2026-05-26) 2026-05-27 |
| 3. Crawler | **done 2026-05-27** — [`crawler_bnp.py`](../../../../playground/research/ingest/crawler_bnp.py) (async, paginated PUT, bootstrap-via-SPA, date-windowed early stop) |
| 4. Filter + classifier | **done 2026-05-27** — [`filters/bnp.py`](../../../../playground/research/ingest/filters/bnp.py) drops chart-pack boilerplate; [`classifiers/bnp.py`](../../../../playground/research/ingest/classifiers/bnp.py) maps `assetClasses`/`regions`/`authors` to canonical tags; registered in `classifiers/__init__.py` |
| 5. Runner | **done 2026-05-27** — [`ingest_today_bnp.py`](../../../../playground/research/ingest_today_bnp.py) |
| 6. DB seed + smoke | seed migration written ([`059_seed_bnp_dim_vendor.sql`](../../../../migrations/059_seed_bnp_dim_vendor.sql)); needs apply + smoke run |
| 7. Document + register | this doc + [`scrapers/index.md`](index.md) updated; `vendors.yml` to flip `profile_status` to `production` after first successful ingest |

## Last verified

* 2026-05-26 — interactive login + first slink-PDF fetch.
* 2026-05-27 — full listing API mapped + paginated full-day pull
  (21 reports / 2026-05-26 / 0 single-name signals).
* 2026-05-27 — `crawler_bnp.py` / `filters/bnp.py` / `classifiers/bnp.py`
  / `ingest_today_bnp.py` written + import-tested. Migration
  `059_seed_bnp_dim_vendor.sql` applied (`dim_vendor.id=15`).
* 2026-05-27 — first production ingest (window 2026-05-24..27, embed
  ON). Surfaced + fixed the leading-``|`` filter bug; cleaned up 16
  leaked chart-packs (295 chunks) from DB + Qdrant + OneDrive. 19 real
  reports retained. Filter regression pinned by `test_bnp_filter.py`
  (14 tests, all green).
* 2026-05-27 — wired BNP into the multi-vendor orchestrator
  ([`ingest_today.py`](../../../../playground/research/ingest_today.py)),
  which is the path that runs the classifier and writes
  `asset_class`/`country`/`context`/tags. (The per-vendor
  `ingest_today_bnp.py` does **not** enrich — same as every other
  vendor's per-vendor script. Use the orchestrator for the canonical
  daily run.) Backfilled the 19 first-run rows in place via
  `_backfill_bnp_context.py` (no re-embed): 19/19 now have context,
  136 tag links, 0 with publication-type-as-asset_class.
* 2026-05-27 — fixed a latent bug in `db._upsert_tag`: it looked up
  tags by `(category, value)` but `uq_research_dim_tag` is unique on
  `value` alone, so any value that already existed under a different
  category (e.g. `fx`/`macro`/`credit` live under `discipline`) threw
  an IntegrityError. Now looks up by value and reuses the existing row.
  BNP's classifier emits asset-class echoes under `discipline` to match.
* 2026-05-27 — fixed fetch timeouts: 7-8 large chart-heavy PDFs (Fed
  Deep Dive, MarFA chart packs, iQFS HICP, G10 FCI) `[FAIL]`'d with
  `APIRequestContext.get: Timeout 30000ms exceeded` — they stream for
  31-42 s even though the response is `200 application/pdf`. Raised the
  fetch timeout to 120 s (`fetch._FETCH_TIMEOUT_MS`, both fetch paths).
  Re-ingested via the orchestrator with embed ON: **26 reports total,
  0 thin, 0 failed, 478 chunks, 180 tag links, all embedded**.

## Hard taxonomy probe + tightening (2026-06-03)

Probe artefacts in
[`taxonomy_probe/bnp_full.md`](../../../../playground/research/taxonomy_probe/bnp_full.md)
and
[`taxonomy_probe/bnp_db_audit.md`](../../../../playground/research/taxonomy_probe/bnp_db_audit.md).
Re-runnable probe script at
[`probe_bnp_full.py`](../../../../playground/research/probe_bnp_full.py).

### DB audit (72 rows, 2026-05-24 → 2026-06-01)

BNP is **the cleanest vendor we've audited**: zero NULL/empty
asset_class, zero non-canonical values, zero encoding corruption,
zero duplicate titles, zero ticker tags, zero CREDIT rows, zero
single-name leakage. The only material issue: **9 format-leaks** — 8
Quant Vault chart-packs (HEXA, MarFA™, iQFS™, G10 FCI, Global FX
Positioning Tracker) + 1 ``Markets 360 Presentations`` slide deck —
slipped past the existing summary-prefix filter because their
summaries didn't start with ``"Update of the latest values"``.

### Structured signals lifted from listing payload (added 2026-06-03)

Crawler now persists 5 additional structured fields on `ReportRef`:

| field | source | use |
|---|---|---|
| `quant_models` | `tags.quantModels` | **chart-pack detector** — 17 distinct model names observed (MarFA™, Data Pool, TEi, STEER™, Regime Navigator, FEFA, ComFA™, BEER+, Quant Trades of the Week, Equity Positioning Indicator, FX Positioning Tracker, Commodity Positioning Tracker, Financial Conditions Indicator, Global Macro CTA Tracker, Tactical Equity Indicator (TEi), Data Trackers, Quant Highlights). Non-empty ⇒ drop |
| `publication_class` | top-level `publicationClass` | "RESEARCH" / "COMMENTARY" — defensive allowlist; 100% coverage on survivors |
| `tickers` / `issuers` / `industry_groups` | `tags.tickers` / `tags.issuers` / `tags.industryGroups` | always empty on Markets360 today — defensive single-name catch in case CREDIT 360 subdomain is wired in |

### Filter precedence (added 2026-06-03)

`filters/bnp.py` — first-match-wins:

1. Title-prefix admin (`invite:` / `webcast:` / `conference call:` / `expert access:`)
2. `pubtype:Markets 360 Presentations` (slide decks)
3. Single-name (`tickers` / `issuers` / `industry_groups` non-empty) — defensive
4. **`quant-model:<name>`** — `quant_models` non-empty (structured chart-pack signal)
5. `summary-prefix:'update of the latest values'` (legacy boilerplate-text rule)

### 7-day smoke (2026-06-03)

Read-only via
[`smoke_bnp_7day.py`](../../../../playground/research/smoke_bnp_7day.py).
Log at
[`taxonomy_probe/bnp_smoke_7day.log`](../../../../playground/research/taxonomy_probe/bnp_smoke_7day.log).

| stage | count |
|---|---|
| raw cards processed | ~99 |
| discovery drops | 58 — 51 `quant-model:<name>`, 5 `summary-prefix`, 2 `pubtype:Markets 360 Presentations` |
| discovery kept | 41 (~6/day) |
| relevance kept | **41 (100%)** — no single-name to drop |

**Composition (clean macro/rates/fx/commodities):**

| class | count | % |
|---|---|---|
| MACRO | 16 | 39% |
| FX | 8 | 20% |
| RATES | 8 | 20% |
| STRATEGY | 5 | 12% |
| COMMODITIES | 4 | 10% |

Regions: apac 16, global 9, latam 8, emea 6, americas 6.

**Sample kept titles** (macro/rates/fx/commodities stream):
- MACRO: *"Japan: How the naphtha shortage could play out"* / *"China economic tracker"* / *"South Korea: Inflation accelerates in May"*
- RATES: *"EM rates: Entering long 2050 Coltes position"* / *"Japan: 10y JGB auction comment"*
- FX: *"FX vol strategy weekly"* / *"BNPP cross-border flow monitor"*
- COMMODITIES: *"Energy: Middle East scenarios update"* / *"Gas: Close long Jun26 TTF call spread upon expiry"*

### Trade-off — strict quant-model drop

The `quant_models` filter is broad and catches some borderline
analytical titles (Regime Navigator, STEER™ signals, Commodity
positioning, FEFA, Quant Highlights). User decision 2026-06-03:
**keep the strict rule** — clean macro/rates/fx/commodities stream
is the goal, and the borderline cases are mostly chart-heavy
quant-model output anyway. If specific names turn out to be useful,
add a `_KEEP_QUANT_MODELS` allowlist in `filters/bnp.py`.

### DB cleanup

Bucket 9 added to
[`cleanup_tier1_junk.py`](../../../../playground/research/cleanup_tier1_junk.py):
`bnp-chartpacks` — drops rows whose `vendor_pubtype` is `Markets 360
Presentations` or `Quant Vault`. Sweeps the 9 historical leakers so
they don't pollute embeddings. They'll be re-discovered cleanly
under the new filter (then immediately re-dropped).

## Run

**Canonical daily run — use the orchestrator** (it classifies +
embeds; see [`../index.md`](../index.md#running-the-daily-ingest)):

```
IMDR_RESEARCH_EMBED=true python playground/research/ingest_today.py --vendors bnp
```

The per-vendor `ingest_today_bnp.py` script **skips the classifier**
(thin rows: no context/tags/embeds) — use it only for discovery/fetch
debugging:

```powershell
# Discovery/fetch smoke only (NOT for production — produces thin rows):
$env:IMDR_RESEARCH_EMBED = "false"
$env:IMDR_RESEARCH_LIMIT = "3"
C:/Users/adoshi/.conda/envs/imdr/python.exe playground/research/ingest_today_bnp.py
```

Prereqs:

* Apply migration `059_seed_bnp_dim_vendor.sql` (seeds the
  `dbo.dim_vendor` row).
* The Chrome profile at `playground/research/profiles/bnp/` must hold
  an authenticated session — run `explore_bnp.py` once to log in.
  Sessions appear stable for at least a few days; if the listing API
  starts returning empty / login redirects, re-run `explore_bnp.py`
  to refresh.

## Noise filter update (2026-06-10)

Shared cross-vendor noise classifier wired into
[`ingest/filters/_noise.py::classify_noise`](../../../../playground/research/ingest/filters/_noise.py)
and called as the final fallback inside [`filters/bnp.py::should_exclude`](../../../../playground/research/ingest/filters/bnp.py).
Three universal title-pattern families plus a cross-vendor EQUITY
conference / sales-event drop in [`relevance._is_equity_conf_event`](../../../../playground/research/ingest/relevance.py).

Smoke against the full 4,498-title `research.dim_report` corpus dropped
**10 bnp docs**:

| family | n | sample |
|---|---|---|
| chart-pack | 10 | MarFA Macro Chart Pack; FX vol weekly chart pack; Global Tactical Asset Allocation Chartbook |
| morning-note | 0 | (none) |
| event-admin | 0 | (none — covered by existing EXCLUDED_TITLE_PREFIXES tuple) |
| conf-event (EQUITY only) | 0 | (none — chart-pack drop catches these earlier via summary-prefix + quantModels) |

The conf-event rule fires only when `result.asset_class == EQUITY` so
MACRO-tagged "Takeaways" / "Trip Notes" titles (real policy / sovereign
macro content) pass through unaffected.

Test pins: [`test_noise_filter.py`](../../../../playground/research/test_noise_filter.py)
(116 chart-pack / morning-note / event-admin assertions),
[`test_relevance_conf_event.py`](../../../../playground/research/test_relevance_conf_event.py)
(35 conf-event assertions). Re-runnable smoke harnesses:
[`_smoke_noise_filter.py`](../../../../playground/research/_smoke_noise_filter.py),
[`_smoke_conf_event.py`](../../../../playground/research/_smoke_conf_event.py).

