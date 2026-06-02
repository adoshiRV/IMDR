# Deutsche Bank — Research scraper

Status: **Phase 2 complete, Phase 3 (build crawler) pending** (2026-06-02).

Pattern: **A. Listing-API firehose** + **C. Viewer-redirect chain to a
signed PDF URL on the same host** (the redirect is intra-domain, not
cross-domain like ANZ).

## Daily volume

**Approx. 35/day** (Phase 3 isolation test, 2026-06-02 — 140 reports
over a 4-day window from `crawler_db.discover_reports`, pre-relevance
filter). To be re-measured after the first full-day smoke and after
the relevance filter drops single-name equity (~59% of refs carry
ticker tags). API `count` field reports a 10,000-row total archive.

## Portal

| | |
|---|---|
| Hostname | `research.db.com` |
| Portal URL | `https://research.db.com/research` |
| Sign-in | corporate SSO; no interactive login needed on the operator's machine (transparent redirect on first hit) |
| Username | n/a (SSO session) |
| `.env` key | `IMDR_RESEARCH_DB_URL` (URL only; user/pass commented out, unused while SSO works) |
| MFA | not observed |

A separate DB property, `www.dbresearch.com` ("Research Institute"),
is out of scope for this `db` vendor and tracked at
[`docs/admin/development/db_research_institute_onboarding.md`](../../development/db_research_institute_onboarding.md).

## Profile

```
playground/research/profiles/db/
```

Persistent profile created 2026-06-01. SSO redirects transparently;
no manual sign-in required. Session reuse via persistent cookies has
been verified across multiple back-to-back script invocations
(probe + inspector + PDF resolver).

## Listing API (current — 2026-06-02)

```
GET https://research.db.com/research/api/1.0/research/latest
    ?includeFacets=false
    &itemsPerPage=20            # server caps at 20 — anything higher returns HTTP 400 with a self-explanatory error
    &sortBy=date
    &sortOrder=desc
    &startIndex=0               # offset, increment by itemsPerPage to paginate
```

`includeFacets=false` cuts the bandwidth substantially — facets aren't
needed by the crawler. The SPA itself uses `itemsPerPage=10`; we
double it to 20 for fewer round-trips.

Response shape:

```jsonc
{
  "data": {
    "count": 10000,         // total docs in the archive (signal for early-stop sanity)
    "items": [
      {
        "documentKey": "2795-74a6c29a_7c7c_41e4_87de_25f6eb8e3d87_604-20260601",
        "title": "Thematic Research: This Month in Geopolitics: June 2026 ",
        "dateAsOf": "2026-06-01T15:56:04.000Z",
        "productType": "Report",                   // "Report" | "Presentation" | "Alert" | ...
        "presComponentFormat": "PDF",              // every report seen so far advertises PDF
        "periodicalId": "50061",
        "periodicalName": "Thematic Research",     // strong asset-class signal
        "region": "Global|Americas|Europe|Japan|Asia Ex Japan|Middle East|Africa|Latin America",
        "topics": [
          {"id": "RS0071", "name": "Thematic Research", "template": "MA"}
        ],
        "analysts": [
          {"id": "755D14ED-A5A1-D46D-05ED-31BEE8FD5B17", "name": "Helen Belopolsky"}
        ],
        "companies": [
          // For thematic / macro reports this is a single empty stub.
          // For single-name research, populated with ticker symbols.
          {"isPrimary": false, "name": "", "symbol": "", "wsodCompany": "", "xid": ""}
        ],
        "abstract": "...",                         // ~paragraph plain text
        "abstractFormatted": "...",                // HTML
        "synopsis": "...",                         // short blurb
        "synopsisFormatted": "...",
        "pageCount": 6,
        "isDemotion": "",
        "isInBriefcase": false
      }
    ]
  }
}
```

Pagination: `startIndex=0, 20, 40, ...` with `itemsPerPage=20`.
Early-stop once `min(item.dateAsOf) < since`.

Authentication: persistent-profile cookies are sufficient; no
custom headers required. (`ctx.request.get(...)` works directly.)

## documentKey → URL mapping

```
documentKey = "2795-74a6c29a_7c7c_41e4_87de_25f6eb8e3d87_604-20260601"
                │   └────────── middle ─────────────────────┘  └──────┘
                │                                                YYYYMMDD
                └── product code (2795 = Markets research?)
```

The crawler builds the canonical viewer URL deterministically:

```python
def doc_key_to_rid(doc_key: str) -> str:
    _prefix, middle, _yyyymmdd = doc_key.split("-", 2)
    return middle.replace("_", "-")

# 74a6c29a-7c7c-41e4-87de-25f6eb8e3d87-604
```

Then:

```
https://research.db.com/research/Document?rid={rid}&kid=RP0001&documentType=R
```

`kid=RP0001` and `documentType=R` are static for every doc observed
in Phase 2. Verify in Phase 6 whether other `kid` values exist for
non-standard publication kinds.

Note: the SPA also accepts a Crockford-ULID-style `rid` (e.g.
`01KSZ3Q8RT052YGQ76W0NYG9SA`) — but the listing API never returns
that format. UUID-with-suffix is the canonical form for our crawler.

The `wt_cc1=IND-...` Webtrekk tracker is **not** required and is
stripped before persisting.

## PDF URL pattern (resolved at fetch time)

The `/research/Document?rid=...` URL serves an HTML wrapper (~48 KB)
that JS-redirects the browser to a per-fetch signed URL on the
**same host**:

```
https://research.db.com/research/namedFileProxy/{docKey_minus_date}/{uuid_underscored}_604.pdf
    ?filetoken=<base64-signed-token>
```

* The `{docKey_minus_date}` is the first two segments of `documentKey`
  joined by `-` (e.g. `2795-74a6c29a_7c7c_41e4_87de_25f6eb8e3d87_604`).
* The `{uuid_underscored}_604.pdf` is the middle segment plus `.pdf`.
* `filetoken` is per-fetch; can't be precomputed.

We store the **canonical Document URL** in `dim_report.pdf_url`
(stable across re-runs), not the signed namedFileProxy URL.

## Fetch strategy

Viewer-redirect-C. The shared `playground/research/ingest/fetch.py`
slow path needs a small extension to recognise this pattern:

* `_VIEWER_HOSTS` currently only matches `cloudfront.net`,
  `amazonaws.com`, `execute-api`. The DB redirect stays on
  `research.db.com`, so we need a generic "URL path ends with `.pdf`
  (with or without query)" predicate instead of (or in addition to)
  the host-based check.
* Once detected, `page.url` is the PDF URL directly — GET it through
  `ctx.request.get(...)` with the same context's cookies.

Per-fetch wall-clock estimate: ~3–5s (faster than ANZ's cross-host
S3 redirect since it stays on `research.db.com`).

## Discovery filter (`filters/db.py`)

Three drops applied in order:

1. **CJK / Japanese-language titles** — DB ships Japanese editions of
   US/Japan econ notes (e.g. `US Economic Notes (Japanese): 今週の予定`,
   `Japan Economic Perspectives: 日本経済見通し：…`). The English-language
   originals are already ingested; the Japanese translations are
   unreadable to downstream RAG consumers, so we drop pre-fetch on
   any title containing CJK characters (Hiragana / Katakana / CJK
   Unified Ideographs / CJK Symbols & Punctuation). Reason logged
   as `cjk:'japanese'`. ~2 docs/4-day window.

2. **`EXCLUDED_TITLE_PREFIXES`** (currently `("expert call",)`) —
   added 2026-06-02 after the Phase-6 audit, which caught 3
   `Expert Call: ...` items over 4 days — all event invites /
   KOL setup notes, no PDF research. Matching via the shared
   [`filters.match_title_prefix`](../../../../playground/research/ingest/filters/__init__.py)
   helper (same as ANZ/Barclays), which normalises decoration chars
   (`*`, `~`, leading punctuation) before the prefix check.

3. **`EXCLUDED_PRODUCT_TYPES`** — wired but empty; populate if a
   productType ever proves reliably non-research.

Behaviour pinned by [`test_db_filter.py`](../../../../playground/research/test_db_filter.py).

## Crawler-stage drops

The listing returns multiple `productType` values. Phase 2 saw three;
the Phase 3 isolation run (2026-06-02, 140 refs over 4 days) surfaced
two more:

| productType | share | example |
|---|---|---|
| `Report` | 67.9% | "Jupiter: Changing gear? A detailed review …" |
| `Comment` | 17.1% | "Geely: May Volume Flat YoY and MoM, Overseas Sales Rise to New Record" |
| `Alert` | 12.1% | "Expert Call: R&D call series: LUN Tuesday @3pm TO BE RESCHEDULED" |
| `Charts` | 1.4% | "Autos & Auto Technology: China NEV demand leading indicator …" |
| `Presentation` | 1.4% | "European Securitisation Report: 30th Annual European Leveraged Finance Conference" |

Per the 2026-06-02 onboarding decision (keep everything, decide in
Phase 6 audit), the crawler does **not** drop any productType.
`filters/db.py` ships with an empty `EXCLUDED_PRODUCT_TYPES`
frozenset — populate after the Phase-6 audit confirms which values
are reliably non-research.

`presComponentFormat == "PDF"` is enforced at parse time — anything
else is counted as `no_pdf=N` in the crawler funnel (5 in the
isolation run, all silently dropped). Per the playbook, **don't
mislabel this as `unparseable`** — these are PDFs the vendor flagged
as a different format.

## Classifier (`classifiers/db.py`)

Live. Mapping cascade (first hit wins):

1. **`topics[].template`** — DB's two-letter template codes. Mapped:
   * `EQ` → `ASSET_CLASS_EQUITY`
   * `MA` → `ASSET_CLASS_STRATEGY` (multi-asset)
   * `FI` → defaults to `RATES`, **but** if the topic name contains a
     credit keyword (`credit`, `securitis/z`, `high yield`, `high
     grade`, `loan`, `investment grade`) it promotes to `CREDIT`; if
     it contains a macro keyword (`econom`, `inflation`, `macro`,
     `outlook`) it promotes to `MACRO`.
2. **Unknown / empty template fallback** — walk the topic name:
   * `quant` → `STRATEGY` (catches "Quantitative Strategy" topics
     on Quant Pulse / Quantcraft, which DB ships without a template)
   * Macro keywords (same set as above) → `MACRO`
   * Otherwise skip and try the next topic.
3. **`periodicalName` fallback** — for refs with no topics, the
   series name is the next-best signal. Same credit / fixed-income /
   macro keyword logic.
4. **Title-regex final fallback** — generic FX / credit / rates /
   commodities / macro / strategy / equity word lists; used when all
   three earlier passes return empty.

Tag emissions:

* `Tag('vendor_pubtype', periodicalName)` and `Tag('vendor_pubtype',
  productType)` — raw vendor labels.
* `Tag('theme', topic.name)` — deduped, in topic order.
* `Tag('region', bucket)` — DB's pipe-separated `region` field
  mapped through `canonical.normalize_region` (americas / emea /
  apac / latam / global).
* `Tag('author', name)` — first 4 analysts in listing order.
* `Tag('ticker', symbol)` — Reuters convention (e.g. `GSK.L`),
  populated only when the listing's `companies[]` carries a non-empty
  symbol. Drives the single-name signal in
  [`relevance.py`](../../../../playground/research/ingest/relevance.py).

`country_code` comes from the same `region` field via
`canonical.normalize_country`; if multiple segments map to different
codes the classifier returns `"WW"` (worldwide) rather than picking
one. ~56% of refs resolve a country in the 2026-06-02 audit window.

Behaviour pinned by [`test_db_crawler.py`](../../../../playground/research/test_db_crawler.py)
(documentKey transform + date parsing). Classifier mapping changes
should be guarded by a focused unit test before the next promotion.

### Vendor-specific drops (relevance.py)

Two DB-specific branches in
[`relevance.py`](../../../../playground/research/ingest/relevance.py)
sit alongside the shared single-name-equity rule. Both use a
**keep-allowlist** pattern: blanket-drop the asset class unless the
title matches a curated set of keywords.

**EQUITY drop** — DB EQUITY is dominated by sector wraps / daily
focuses / weekly trackers / conference notes; not what the macro
RAG is for. Keep only top-down strategy:

```
strategy | portfolio | cross-asset | outlook | thematic |
positioning | forecast | world outlook | early morning reid
```

Net survival ≈1/day (effectively just `World Outlook`). Single-name
(n_tickers=1) is always dropped regardless of title — same shape as
the JPM branch, just tighter keywords.

**CREDIT drop** (added 2026-06-02) — drops single-name HY/IG notes
(Whirlpool, Accendra Health, EquipmentShare, Cruise Yacht, eDreams
ODIGEO, …). The classifier emits both `Tag('ticker', ...)` and
`Tag('company', ...)` so the relevance filter has a count signal,
but DB's listing API **leaves `companies[]` empty for credit notes**
— ticker/company counts can't catch them. Falling back to a
title-keyword keep-allowlist:

```
weekly | monthly | daily | relative value | rel val | relval |
sector | industry | strategy | outlook | thematic | cross-asset |
securitisation | securitization | clo | cmbs | mbs | hy |
corporate credit | covered bond | aircraft market |
credit supply | supply monitor
```

Net: ~6 single-name CREDIT drops per 4-day window, ~16 kept
(securitisation series, HY weekly relval, corporate credit RV
monitors, sector RV alerts, CRE debt research, etc.).

## Non-PDF assets

Phase 2 only saw `presComponentFormat == "PDF"`. The `Alert` product
type is technically a PDF flyer but contains no research content
— drop at crawler stage.

If other `presComponentFormat` values appear (xls, video, audio),
filter at the crawler with the playbook's `no_pdf=N` counter
(not `unparseable=N` — playbook pitfall #1).

## Watermarks

TBD — first PDF inspection in Phase 6.

## Quirks

* **`itemsPerPage` capped at 20**. Server validates against a fixed
  max; pushing higher returns HTTP 400 with a clear message.
  Crawler must use `itemsPerPage=20`.
* **Two `rid` formats accepted in the URL** — UUID-with-`-604`-suffix
  (used by the listing API) and Crockford ULID (used by some older
  links). Always emit the UUID form derived from `documentKey`.
* **`kid=RP0001` is static** for all docs seen in Phase 2. Don't try
  to derive it from the payload; just hard-code.
* **Strip `wt_cc1=IND-…` Webtrekk tracker** from any URL persisted
  to `dim_report.pdf_url`. The doc is fully addressed by
  `(rid, kid=RP0001, documentType=R)`.
* **`/research/Document` ALWAYS returns the HTML wrapper** (~48 KB),
  even when called from a properly-cookied request context. The PDF
  binary lives one navigation away at
  `/research/namedFileProxy/.../*.pdf?filetoken=…`. Skipping the
  navigation step is not an option.

## URL patterns reference

| Kind | URL |
|---|---|
| Portal root | `https://research.db.com/research` |
| Latest hub | `https://research.db.com/research/Research/Latest` |
| Topic hub | `https://research.db.com/research/Topics/{Topic}?topicId={RB####\|RS####}` |
| Listing API | `https://research.db.com/research/api/1.0/research/latest?…` |
| Article (viewer) | `https://research.db.com/research/Article?rid={rid}&kid=RP0001&documentType=R` |
| Document (PDF wrapper) | `https://research.db.com/research/Document?rid={rid}&kid=RP0001&documentType=R` |
| PDF binary (per-fetch signed) | `https://research.db.com/research/namedFileProxy/{docKey_no_date}/{uuid_under}_604.pdf?filetoken=…` |
| Shareable short link | `https://research.db.com/research/TinyUrl/{CODE}` |

## Probe / inspector artefacts

Phase 2 left these behind in [`playground/research/db_explore/`](../../../../playground/research/db_explore/):

* `listing_apis.json` — full probe captures (sorted by score).
* `listing_apis_top.txt` — one-line top-N summary.
* `listing_sample.json` — one 20-item page from the listing API.
* `listing_fields.txt` — keys + sample items (item[0], item[1], item[-1]).
* `document_wrapper_sample.html` — the HTML viewer wrapper served by
  `/research/Document?rid=…`.

The two ad-hoc inspectors at
[`playground/research/inspect_db_listing.py`](../../../../playground/research/inspect_db_listing.py)
and
[`playground/research/inspect_db_pdf.py`](../../../../playground/research/inspect_db_pdf.py)
are kept (alongside `explore_db.py`) for re-running if the API
changes.

## Last verified

* 2026-06-01 — Phase 1 explore, 18 snapshots captured.
* 2026-06-02 — Phase 2 API discovery: listing endpoint confirmed,
  per-item shape mapped, documentKey→URL transform verified, fetch
  pattern identified as viewer-redirect-C on same host.
* 2026-06-02 — Phase 3 isolation test: crawler discovered 140
  reports over a 4-day window; pagination + early-stop + classifier
  + filter all behave correctly. Two additional `productType`
  values (`Comment`, `Charts`) surfaced — not seen in the Phase-2
  sample.

## documentKey ID format note

Phase 3 confirmed DB ships **two distinct documentKey shapes** in the
same listing response:

1. `2795-{uuid_underscored}_604-{YYYYMMDD}` — the common case
   (UUID v1/v4 with `_` separators), middle segment yields
   `{uuid}-604` after `_→-` swap.
2. `2795-{CrockfordULID26}-{YYYYMMDD}` — sometimes the middle
   segment is already a 26-char Crockford-base32 ULID. Our
   `_doc_key_to_rid` transform handles both — the `_→-` swap is a
   no-op on the ULID form.

Either form is a valid `rid` in the URL.
