# Citi Velocity — Research scraper

**Status: LIVE through Phase 8 (2026-06-06) — daily orchestrator wiring deferred**

Pattern: **A. Listing-API firehose** with **B. deterministic PDF URL**.
A single POST to the publication-query service returns all docs in a
date range; the PDF rendition URL is built directly from the integer
`pubId` (no per-doc frontmatter call).

## Portal

| | |
|---|---|
| Hostname | `www.citivelocity.com` |
| Sign-in URL | `https://www.citivelocity.com/cv2/go/RSCH_LANDING_PAGE` |
| Username | `.env: IMDR_RESEARCH_CITI_USERNAME` (`adoshi@rvcapital.com`) |
| Password | `.env: IMDR_RESEARCH_CITI_PASSWORD` |
| MFA | None observed at first interactive login (2026-06-06) — session cookies in persistent profile suffice |

**Distinct from the Citi Velocity data API**:
`api.citivelocity.com` is a separate host with OAuth2 client-credentials
auth, used by [`src/imdr/connectors/citi_velocity.py`](../../../src/imdr/connectors/citi_velocity.py)
for FX / rates / equity / commodities data feeds (env keys
`IMDR_CITI_CLIENT_ID` / `IMDR_CITI_CLIENT_SECRET`). Those credentials
**do not** grant research access — research is a separate product on
the SPA-fronted portal.

## Profile

```
playground/research/profiles/citi/
```

Created 2026-06-06 via interactive login through `explore_citi.py`. The
SPA wraps menu items in shadow DOM ("layer/host"); the listing UI is
not directly clickable via Playwright headless — but the API is reachable
once the session cookie is in the profile.

## Listing API

```
POST https://www.citivelocity.com/cvr/publicationqueryws/eppublic/V1/publications.json
     ?platformId=79
```

**Required headers** (sniffed via `probe_citi_pubapi.py`):

| header | value |
|---|---|
| `callerId` | `CVR` (without this → `401 CALLER_NOT_AUTHORIZED`) |
| `Content-Type` | `application/json` |
| `Accept` | `application/json` |

**Request body**:

```json
{
  "startDate": "2026-06-01T00:00:00.000Z",
  "endDate":   "2026-06-06T23:59:59.999Z",
  "pageStart": 0,
  "pageSize":  500,
  "sortDirection": "DESC",
  "outputFormats": ["PDF"],
  "extendOutputFields": ["TemplateCode", "Link", "EventDetails"]
}
```

**Quirks discovered while probing**:

- `startDate` must be ISO 8601 `yyyy-MM-dd'T'HH:mm:ss.SSS'Z'`. Plain
  `yyyymmdd` returns `412 PARAMETER_ERROR`.
- **Do NOT send `sortBy`**. The backend MarkLogic complains
  `XDMP-ELEMRIDXNOTFOUND: cts:element-reference(... "PublicationDate"
  "type=string") -- No string element range index for PublicationDate`.
  Omit `sortBy`; the default ordering is publish-date DESC which is
  what we want.
- `pageSize` is capped server-side at ~500 (verified: requesting 500
  returns 499 results).
- `outputFormats: ["PDF"]` server-side filters out videos, audio,
  Excel/Data, HTML-only docs — saves us a per-doc format check.

**Response shape**:

```json
{
  "count": 99,
  "total": 1001,
  "publications": [
    {
      "publishDate": "2026-06-02T09:34:14.000Z",
      "pubHeadline": "EGB Supply Monthly: ...",
      "distHeadline": "EGB Supply Monthly: ...",
      "pubTitle": "...",
      "pubSynopsis": "We forecast …",
      "htmlSynopsis": "...",
      "pubId": "30435046",          // ← the doc id used in the PDF URL
      "pubKey": "11109128",
      "productFocus": "DISCIPLINE", // COMPANY|MULTICOMPANY|INDUSTRY|
                                    // DISCIPLINE|OTHER|UNFOCUSED
      "productType": "VWPOINT",     // FYI|VWPOINT|Action|ID|...
      "productId": "VWPOINT@10~5860@10",
      "templateName": "Note",       // Note|Report|Data|Video|...
      "subjects":  [{"id":"RLV", "name":"Relative Value"}, ...],
      "regions":   [{"id":"B1042","name":"Western Europe"}, ...],
      "countries": [{"id":"B1053","name":"Netherlands"}, ...],
      "authors":   [{"analystId":"11212","name":{"en":"..."},
                     "type":"PRI", "isACAnalyst":"Y", ...}],
      "primaryAuthor": "11212",
      "pageCount": 15,
      "renditionUrl": "https://.../rendition/eppublic/documentService/<base64>",
      "renditionCopyUrl": "...",
      "restrictionLevel": "N",       // "N"=public, "CR1"=restricted
      "isVideo": false, "isAudio": false, "isPresentation": false,
      "isPrimer": false,
      "isClientPerspective": true,   // 100% true — NOT a filter signal
      "isComposerCP": true,          // 100% true — NOT a filter signal
      "files": [...], "vendorFiles": [...], "metadata": {...},
      "periodical": null
    }
  ]
}
```

**Daily volume observed** (5-day window 2026-06-02 → 2026-06-06):

- `total = 1001` raw across 5 days = **~200/day** before any filtering.
- `productFocus=COMPANY` (single-name equity): 49% of sample.
- `productFocus=INDUSTRY` (sector): 22%.
- `productFocus=DISCIPLINE` (cross-asset / macro / strategy): 16%.
- After the relevance filter's `equity-vendor-default-drop:citi` branch:
  **125 kept / 5 days = ~25/day net**.

## PDF URL — deterministic

```
GET https://www.citivelocity.com/rendition/eppublic/uiservices/print
    ?doc_id={pubId}&type=print&isJP=false
```

Returns raw `application/pdf` bytes when called with the persistent
profile's session cookies.

The alternative URLs we discovered (`renditionUrl` /
`renditionCopyUrl`, both pointing at
`/rendition/eppublic/documentService/<base64>`) return the SPA shell
HTML (`text/html`), NOT the PDF — they require client-side JS to
fetch the PDF. The `print` endpoint is the cleanest direct fetch.

## Drop signals applied at crawler stage

In `crawler_citi._drop_reason`:

1. `isVideo=true` → drop format
2. `isAudio=true` → drop format
3. `isPresentation=true` → drop format
4. `templateName in {Video, Audio, Presentation, Catalyst Watch}` →
   drop format (defensive; `outputFormats=["PDF"]` should already
   filter most non-PDF docs)
5. `restrictionLevel = "CR1"` → drop restricted

`isClientPerspective` and `isComposerCP` are NOT filter signals — both
are true on 100% of the sample.

## Classifier (Tier-0)

In `classifiers/citi.classify`:

- `productFocus=COMPANY|MULTICOMPANY` → `EQUITY` (single-/multi-name)
- `productFocus=INDUSTRY` → `EQUITY` (sector) unless any
  `subjects[].id == CMD` then → `COMMODITIES`
- `productFocus=DISCIPLINE|OTHER|UNFOCUSED` → dive into `subjects[]`:
  - Macro signals (`CBK`, `MON`, `INF`, `MAC`, `ECA`, `ECO`, `GRT`,
    `PA`, `TRD`, `EMM`, `EMC`, `USH`) → `MACRO`
  - Commodities (`CMD`) → `COMMODITIES`
  - Strategy / cross-asset (`RLV`, `FLW`, `STV`, `MPO`, `ETF`, `THM`,
    `OLK`, `DED`, `CMP`, `PRI`, `FLS`, `IFAS`) → `STRATEGY`
  - No subject hit → `STRATEGY` catch-all

Country resolution: Citi internal `B{NNNN}` IDs → ISO 3166 alpha-2 via
a 47-entry lookup table built from the observed sample. Falls back to
`canonical.normalize_country()` on the human-readable name when the ID
isn't in the table.

Region resolution: Citi has 2-3 region IDs per logical region
(`B1031 + B1291` both = "North America"); we key on the lowercase
name → canonical bucket (`americas / emea / apac / latam / global`).

Emitted tags:
- `vendor_pubtype` = `productType` (FYI / VWPOINT / Action / …)
- `format` = `templateName` (Note / Report / Data / …)
- `discipline` = canonical asset class (lowercased)
- `region`, `country`, `theme` (subject names), `author` (primary first)

## Relevance filter

`relevance.py` has a `citi` branch in `is_single_name_equity()` that
mirrors the JPM/Goldman/UBS pattern:

- 1 ticker tag → `equity-vendor-default-drop:1-ticker` (always)
- Title matches `_CITI_EQUITY_KEEP` (strategy/cross-asset/allocation/
  positioning/outlook/thematic/themes/earnings season/global research/
  flagship/primer/deep dive/flows weekly|monthly/central banks/
  inflation/monetary policy/global (equity|economic|macro|markets)
  (strategy|weekly|monthly|outlook)) → **keep**
- Otherwise → `equity-vendor-default-drop:citi`

Observed effect on the 5-day window: 353 / 478 dropped (74%);
125 / 478 = 26% kept. Composition of survivors is dominated by macro
(US Econ Weekly, Central Banks, Inflation), strategy (Relative Value,
Flows), and country/region anchors.

## First DB writes (2026-06-06 smoke)

Three reports inserted with `IMDR_RESEARCH_EMBED=false`:

| dim_report.id | pubId    | title                                            | asset_class | author              |
|---:|---|---|---|---|
| 4129 | 30436013 | US Corporate Mutual Fund Flows                   | STRATEGY    | Daniel Sorid        |
| 4130 | 30436011 | Uncomfortably neutral (Canada Economics Weekly)  | MACRO       | Veronica Clark      |
| 4131 | 30436007 | Payroll acceleration but dovish catalysts ahead  | MACRO       | Andrew Hollenhorst  |

## Phase 8 — Hard taxonomy probe + tightening (2026-06-06)

**Done same-day as Phase 0–6** (below the playbook's "≥1 week of ingest"
threshold, but the listing API exposes enough native signal to tighten
without DB history). Key win: **`companies[]` array gives us the
canonical primary-subject signal that `productFocus` only approximates**.

### Deep probe finds

Top-level keys we were ignoring:

| field | coverage | what it carries |
|---|---|---|
| `companies[]` | 60/99 | `{id, isSubject:"Y"/"N", refType:"PRI"/"SEC", ticker, name:{en,...}}`. `refType=PRI` + `isSubject=Y` is THE primary-subject signal. |
| `tickers[]` | 60/99 | parallel bare-string array (`["BOLSAA.MX"]`, `["FR"]`). Same length as companies[]. |
| `sectors[]` | 74/99 | Citi `B{NNNN}` sector IDs with multilingual `{en,ja,...}` names. Equity-sector / GICS-flavoured (Airlines, Diversified Banks, Steel, Aluminum, etc.). |
| `metadata.{TemplateCode,EventDetails,DistHeadline}` | 99/99 | More granular than `templateName` (`REPORT`/`NOTE`/`CWNOTE`); EventDetails is empty in current sample. |
| `relatedPublications[]` | 91/99 | Series cross-refs — could feed periodical-detection. |
| `periodical` | 15/99 | Series cadence marker. |
| `excludeFromAnalystPage` | 100/99 | Universal `true` — NOT a filter signal. |
| `isClientPerspective`/`isComposerCP` | 100/99 each | Universal `true` — NOT filter signals. |

`productId` has only 8 distinct prefix values (ACTION / ANALYTICAL /
BLOG / COMPENDIUM / ESSENTIALS / FYI / NONRSCHREPLAY / VWPOINT) — all
share the `@10~5860@10` suffix, so 5860 is a platform constant, not
a desk code. No additional Tier-1 signal beyond `productType`.

### Tier-0 signal (post-tightening)

`companies[].refType=PRI` + `isSubject=Y` is the canonical
primary-subject signal. Cross-tab against `productFocus` on the
99-doc sample:

| productFocus | n_pri=0 | n_pri=1 | n_pri≥2 |
|---|---:|---:|---:|
| COMPANY (49) | 0 | 48 | 1 |
| MULTICOMPANY (4) | 0 | 0 | 4 |
| INDUSTRY (22) | 15 | 0 | 7 |
| DISCIPLINE (16) | 16 | 0 | 0 |
| OTHER (6) | 6 | 0 | 0 |
| UNFOCUSED (2) | 2 | 0 | 0 |

All single-name research lives in `n_pri=1`. `DISCIPLINE/OTHER/UNFOCUSED`
docs always have `n_pri=0` — these are pure macro/strategy.

### Five edits shipped 2026-06-06

| step | file | change |
|---|---|---|
| A | `crawler_citi.py` | `ReportRef` extended with `companies: tuple[tuple[ticker,name_en,ref_type,is_subject], ...]`, `tickers_arr: tuple[str, ...]`, `sectors: tuple[tuple[id, name_en], ...]`. New helpers `_extract_companies()` + `_extract_sectors()` populate them from the listing response. |
| B | `filters/citi.py` | No change — format/restriction drops at crawler stage are already sufficient (8/99 = 8% drop rate). Title-prefix tuples stay empty per playbook. |
| C | `classifiers/citi.py` | Tier-0 asset class: `_has_primary_company()` now overrides `productFocus` — any doc with `refType=PRI` + `isSubject=Y` is EQUITY (unless `subjects[].id=CMD` flips to COMMODITIES). New tag emissions: `TAG_TICKER` from `companies[].ticker` (PRI subjects only, also backfills from `tickers[]`), `TAG_COMPANY` from `companies[].name.en` (PRI only), `TAG_INDUSTRY` from `sectors[].name.en`. |
| D | (cleanup) | Skipped — only 3 reports in DB (IDs 4129–4131), no historical leakers to delete. |
| E | `smoke_citi_7day.py` | New 7-day smoke harness with 5 acceptance gates. |

The relevance.py `citi` branch from Phase 5 still applies, but with
ticker tags now emitted, the generic `n_tickers == 1` check on line
417 fires BEFORE the citi branch's title-keep allowlist — single-name
drops are now caught even when the title would have hit the allowlist.

### 7-day smoke results (2026-06-06)

```
discovered 473 raw, 125 kept (26%); kept rate ~18/day net

drop reasons:
  243  equity-vendor-default-drop:1-ticker    (single-name PRI subject)
  106  equity-vendor-default-drop:citi        (sector wraps without PRI)

[GATE 1] PASS — listing endpoint returned 200 + 473 hits
[GATE 2] PASS — drop reasons clean, samples match category
[GATE 3] PASS — kept ratio 26% (target >=15% for equity-heavy vendor)
[GATE 4] PASS — composition: 98% macro-family, 2% EQUITY
                (target >=80% macro-family, <=20% EQUITY)
[GATE 5] PASS — single-name ticker leakage on kept set: 1/125 (1%)
                (target <=5%)

kept asset_class distribution:
  74 (59%)  STRATEGY
  43 (34%)  MACRO
   5 (4%)   COMMODITIES
   3 (2%)   EQUITY

kept region distribution (multiplicity):
  36 americas | 24 apac | 22 emea | 13 global | 7 latam
```

The 22 `equity-vendor-default-drop:citi` reason drops on the 99-doc
audit are all sector wraps (Airlines, Diversified Banks, Steel,
Aluminum, Restaurants, Auto, Health Care) — correctly dropped per
"no single-name equity / credit, trends ok" posture.

### Sticky decisions captured in memory

- [`memory/feedback_citi_listing_api_no_sortby.md`](../../../../memory/feedback_citi_listing_api_no_sortby.md)
  — sortBy gotcha on the listing API
- [`memory/project_citi_onboarding.md`](../../../../memory/project_citi_onboarding.md)
  — Phase 0–8 state

## Phase progress

- [x] Phase 0 — registered in `vendors.yml`
- [x] Phase 1 — interactive login (persistent profile 2026-06-06)
- [x] Phase 2 — listing API discovery
- [x] Phase 3 — `crawler_citi.py`
- [x] Phase 4 — `filters/citi.py` + `classifiers/citi.py`
- [x] Phase 5 — wired into orchestrator + relevance branch
- [x] Phase 6 — embed-off smoke (3 reports inserted, IDs 4129–4131)
- [ ] Phase 6b — embed-on full-day ingest (deferred per user)
- [ ] Phase 7 — daily orchestrator wiring in `scripts/imdr_daily.py` (deferred — needs explicit OK per project policy)
- [x] Phase 8 — hard taxonomy probe + tightening (`companies[]/tickers[]/sectors[]` → Tier-0 single-name + industry signals, smoke 5/5 gates pass)

## Last verified

2026-06-06 — Phase 0–8 complete. 3 reports in `research.dim_report`
(IDs 4129–4131, written pre-Phase-8 so they lack the new ticker /
company / industry tags — backfill not needed at this volume). 7-day
smoke shows ~18/day net with 1% single-name leakage. Daily orchestrator
wiring pending user OK per [`memory/feedback_no_prod_wiring_without_permission`](../../../../memory/feedback_no_prod_wiring_without_permission.md).
