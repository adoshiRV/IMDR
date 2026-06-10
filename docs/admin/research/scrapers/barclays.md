# Barclays Live (Investment Bank Research) — scraper notes

Status: **live** (since 2026-05-08). Asset-class allowlist + single-name
drop added 2026-06-02 (see [#asset-class-allowlist-2026-06-02](#asset-class-allowlist--single-name-drop-2026-06-02)).
Language filter added 2026-06-02 (see [#language-filter-2026-06-02](#language-filter-2026-06-02)).

* Discovery: ~**200 publications/day** raw via the publication-search
  firehose (`responseDetailLevel=FULL`, ~200/page, paginated until
  oldest crosses ``since``).
* After filter: **~135/day kept** (≈33% drop) — 70 macro/rates/FX/credit/
  commodities + 65 multi-name sector equity (sector-by-ticker AND
  themed-sector). Single-name equity (`eq_securities=1`), small-cluster
  equity (`2-5`), no-context equity (`eq_securities=0 AND
  eq_industries<2`), single-name credit (title-paren match), admin
  posts, event invites all dropped at discovery.
* Ingest: <1 s/PDF (pre-cached during discovery, pipeline reads bytes
  directly via ``ingest_one(pdf_bytes=...)``).
* Coverage: pubDate-desc full catalogue scan, not the home tile subset.

## Why Barclays is structurally different

The other 5 research vendors use a stable persistent profile + a
JSON listing API (or HTML scrape) reachable with cookies alone.
Barclays Live is hostile to that pattern in three ways:

1. **PingFederate session tokens rotate aggressively.** Cookies
   captured in one Playwright run go stale by the next; every
   navigation redirects to ``/UAB/ct_logon_basic``. Persistent
   profiles work for *one* session and poison subsequent ones.
2. **No MFA in practice** — but only on device-trusted IPs. Risk-based
   auth lets username + password through on this machine. If Barclays
   later requires email-OTP, see the MFA-extension stub at the bottom
   of [`login_barclays.py`](../../../../playground/research/ingest/login_barclays.py).
3. **API endpoints reject ``ctx.request.get``** even with the right
   cookies — they need the full SPA-injected request shape (CSRF
   tokens, Origin, etc.). All API calls must be made via
   ``page.evaluate('fetch(...)')`` from inside the SPA's origin.

These quirks dictate the architecture below.

## Architecture

```
Discovery (`discover_reports`):

1. ensure_clean_profile(profile_dir)            # nuke stale state
2. login(ctx, username, password)
   - dismiss OneTrust cookie banner
   - fill input[name="user"] + input[name="password"]
   - click button#submit  → page lands on /BU/
3. open_warm_page → goto(/BU/), wait for [data-pubid]
4. firehose loop (page_num = 1..MAX_PAGES):
     fetch /publication/search?pageSize=200&pageNumber={N}&responseDetailLevel=FULL
       (page-context fetch, with mid-run re-login on auth-wall)
     for each publication:
       parse basicInfo.pubDate
       if oldest_in_page < since → break  (early stop)
       extract basicInfo.language, asset_class_name,
               eq_securities_count, is_event, is_non_research,
               debt_restricted
       apply filters/barclays.should_exclude_by_language
              (drop non-English, e.g. Japanese Tokyo desk notes)
       apply filters/barclays.should_exclude         (title-prefix admin)
       apply filters/barclays.should_exclude_by_asset_class
              (allowlist + single-name equity + single-name credit + events)
       pick documents[] entry where channel='PRINT' & mediaType='application/pdf'
       record metadata (no PDF download yet)
     follow data.pageInfo.nextPageUrl until done or date threshold hit
5. Return metadata-only ReportRefs

`relevance.is_single_name_equity` still runs downstream as a
belt-and-suspenders catch — the asset-class filter now does most of
the work but a stray (`TICKER XX`) title that slipped past would still
be caught by the relevance pass.

For survivors, `fetch_pdfs(profile_dir, refs)` opens a second
Playwright session and streams `(ref, pdf_bytes)` tuples straight to
`ingest_one(..., pdf_bytes=...)`. Nothing touches disk.
```

### Mid-run re-login

`_fetch_json_with_relogin` and `_fetch_pdf_bytes_with_relogin` wrap each
page-context fetch with up to `_MAX_RELOGIN_ATTEMPTS` retries. On any
of: HTML response (auth wall), non-200 status, exception during fetch,
they call `login(ctx, ...)` again and re-open the warmed `/BU/` page,
then retry. Long crawls cross PingFederate token rotations — without
this, every run with >50 fetches breaks halfway through.

## Endpoints discovered

| Purpose | URL | Notes |
|---|---|---|
| Home (warm-up) | `https://live.barcap.com/BU/` | Just for SPA hydration; not parsed for content anymore |
| Login | `https://live.barcap.com/UAB/ct_logon_basic?resumePath=...` | PingFederate; redirected to from `/BU/` if not authed |
| **Publication firehose** | `/RSX/content-archive/v1/REST/publication/search?pageSize=200&pageNumber=N&responseDetailLevel=FULL` | JSON, pubDate-desc; `data.publications[]` + `data.pageInfo.nextPageUrl`. `FULL` ships `restrictions{}`, `eqSecurities[]`, `eqIndustries[]`, and the full 28-type `tags[]` taxonomy. `STANDARD` returns empty `classifications[]` and no `eqSecurities` — drop in favour of `FULL`. |
| Per-pubId lookup | `/RSX/content-archive/v1/REST/publication/search?pubId={pubId}` | Same shape; used by article-viewer pages |
| Document download | `/RSX/content-archive/REST/document/{docId}` | Direct PDF bytes |

### Response shape

```
{
  "data": {
    "pageInfo": {
      "pageNumber": 1, "pageSize": 200,
      "currentPageUrl": "...", "nextPageUrl": "...&pageNumber=2",
      "recordCount": 200
    },
    "publications": [
      {
        "basicInfo": {
          "pubId": "<24-hex>",
          "pubDate": "2026-05-08",
          "releasedDateTime": "2026-05-08T08:00:00Z",
          ...
        },
        "documents": [
          {
            "docId": "<24-hex>",
            "channel": "PRINT",
            "mediaType": "application/pdf",
            "url": "/RSX/content-archive/REST/document/<docId>",
            ...
          },
          ...
        ],
        "titles": [{"type": "PUBLICATION", "value": "..."}],
        "classifications": [{"type": "PRODUCT", "value": "..."}],
        ...
      },
      ...
    ]
  },
  "status": ...
}
```

`pageSize=1000` works server-side, but per-page response payloads
balloon to ~35 MB. We default to **200** to balance throughput
against memory + page-context fetch time.

## Selectors

* Cookie accept: `#onetrust-accept-btn-handler`
* Username:      `input[name="user"]`
* Password:      `input[name="password"]`
* Submit:        `button#submit`
* Tile attr:     `[data-pubid]`

## Known limitations

* **`pubDateRange` server-side filter is a no-op** — empirical: same 50
  results returned for `1+day` / `1+week` / `1+year` / `50+years`.
  Filter happens client-side from `basicInfo.pubDate`.
* **`includeSource` is a no-op** — tested with `BARRENJOEY`, `BARCLAYS`,
  `BARCAP`, `RESEARCH`, `ALL`, omitted entirely → identical responses.
  The portal SPA passes `BARRENJOEY` (Barclays' Australian partnership)
  but the server ignores it. The 200-pub firehose returns the full
  Barclays Research catalogue the user has entitlement for — confirmed
  by title diversity (Thematic Investing, single-stock European/US
  names, EM flows, etc., not Australia-specific).
* **dim_vendor row reused.** Barclays already had a `dim_vendor` row
  (id=2, type=`file`) from the SKEW Excel feed. We share it — same
  firm, just different feed. Other research vendors got their own row.
* **`classifications[]` is always empty.** Originally suspected to be a
  `responseDetailLevel=STANDARD` quirk, but `FULL` returns empty
  `classifications[]` too (verified 2026-06-02 probe, 0/100 pubs
  carried any). Asset-class signal lives in `pubSeriesInfo[0].
  assetClassInfo.assetClass` — see the next section.
* **No structured single-name credit signal.** `eqSecurities[]` is purely
  an equity field — populates only on Equity Fundamental pubs and is
  always empty for Credit Fundamental. Single-name credit detection
  falls back to a title-paren regex (e.g. `Ford Motor (F US)`).
  `tags[type=BOOKSHELF_ANALYST]` and `tags[type=TRADE_ID]` may carry
  the same signal but their semantics aren't fully characterised yet.

## Asset-class allowlist + single-name drop (2026-06-02)

Discovery used to fetch the firehose and rely on `relevance.is_single_
name_equity`'s title-paren regex to drop single-name pubs downstream.
After the 2026-06-02 in-portal taxonomy probe
([taxonomy_probe/barclays_full.md](../../../../playground/research/taxonomy_probe/barclays_full.md)),
the crawler scopes server-side detail and the per-vendor filter applies
explicit asset-class / single-name rules at discovery.

### Signals from `responseDetailLevel=FULL`

| Field | Path | What it tells us |
|---|---|---|
| `asset_class_name` | `pubSeriesInfo[0].assetClassInfo.assetClass.name` | Canonical Barclays asset-class label (18 known names). The cleanest taxonomy axis — replaces L1_BRANDING substring guessing. |
| `asset_class_id` | same `.id` | Stable integer ID per asset class. |
| `eq_securities_count` | `len(eqSecurities)` | Number of equity tickers covered. **1** = single-name, **2-5** = small cluster, **>=6** = sector/strategy, **0** = themed or non-equity. |
| `eq_industries_count` | `len(eqIndustries)` | Sector-breadth signal. Used to admit themed sector pieces with `eq_securities==0` AND `eq_industries>=2` (e.g. "European Retail Valuation Sheet", "U.S. REITs: Comp Sheet" — analytical sector content that doesn't list specific tickers). |
| `is_event` | `any tag.type == "EVENT_TYPE"` | Conference Call / Conference invitation (no analytical content). |
| `is_non_research` | `tag.type=="NON_RESEARCH_CONTENT" code=="true"` OR `pubSeriesInfo[0].displayName contains "(Non-Research"` | Explicit non-research flag. |
| `debt_restricted` | `restrictions.debtRestricted` | Pub is licensed to debt-only audiences (~36% of pubs). Confirms credit-flavoured content. |

### Filter rules

Implemented in [filters/barclays.py](../../../../playground/research/ingest/filters/barclays.py):

1. **Title-prefix legacy drops** — `invite:`, `reminder:`, `webcast:`,
   `starts in`, `today:`, `tomorrow`, `save the date`, `replay:`, …
   (still useful; some old pubs predate the structured event tags).
2. **Asset-class allowlist** — keep iff `asset_class_name` is one of:
   - **Macro**: Economics, Global Macro, Macro Product Management, Emerging Markets
   - **Rates**: Interest Rates, Interest Rates - Analytics
   - **FX**: Foreign Exchange
   - **Credit**: Credit Fundamental, Credit Product Management, Credit Strategy, Securitization - Analytics
   - **Commodities**: Commodities
   - **Cross-asset**: QPS - FICC
   - **Equity Fundamental** (conditionally — see below)
   All other asset classes (`Equity Product Management`, `Equity Non-
   Fundamental`, `Data Science & Applied AI - Equity`, `Sustainable
   Investing - Equity`, `Sustainable Investing - FICC`, unknown) are
   dropped at discovery.
3. **Equity Fundamental gating** — keep iff:
   * `eq_securities >= 6` (sector by ticker count), OR
   * `eq_securities == 0 AND eq_industries >= 2` (themed sector
     content — valuation sheets, sector models, daily sector briefs
     that don't list specific tickers).

   Drops single-name (`eq_securities == 1`), small cluster (`2-5`), and
   "no-context" pubs (`eq_securities == 0 AND eq_industries < 2`).
4. **Single-name credit** — drop `Credit Fundamental` when the title
   carries a `(TICKER)` or `(TICKER XX)` ticker paren. The regex
   matches both single-word (`(IFF)`, `(DVN)`, `(GAP)`) and Bloomberg-
   style (`(IBM US)`) formats. Lowercase content like `(May 2026)` is
   rejected because the regex requires all-caps/digit/dot after the
   leading letter. Best-effort because no structured `crSecurities[]`
   analog exists.
5. **Events + non-research** — drop on `is_event` OR `is_non_research`.

### Empirical hit rate

One-day FULL smoke (2026-06-02, 200 raw pubs, 2 pages) after the
themed-sector keep + broader credit-paren regex updates:

| Bucket | Mapped count |
|---|---|
| CREDIT | 34 |
| EQUITY (sector + themed sector) | 65 |
| MACRO | 18 |
| RATES | 11 |
| STRATEGY (QPS - FICC) | 3 |
| FX | 2 |
| COMMODITIES | 1 |
| **Total kept** | **134 / 200 (67%)** |

Drops (66 pubs) — predominantly single-name + small-cluster equity
(`eq_securities=1-5`), a few "no-context" Equity Fundamental
(`eq_securities=0 AND eq_industries<2`), admin / event posts, and
non-allowlisted classes (Equity Product Management, Sustainable
Investing - Equity / -FICC, Equity Non-Fundamental, DS&AI-Equity).

### Known taxonomy values (extend `_ASSET_CLASS_NAME_MAP` when probe adds new ones)

```
Economics                            (id=2)  → MACRO
Global Macro                         (id=4)  → MACRO
Macro Product Management             (id=43) → MACRO
Emerging Markets                             → MACRO
Interest Rates                       (id=8)  → RATES
Interest Rates - Analytics                   → RATES
Foreign Exchange                             → FX
Credit Fundamental                   (id=9)  → CREDIT
Credit Product Management            (id=11) → CREDIT
Credit Strategy                              → CREDIT
Securitization - Analytics                   → CREDIT
Commodities                                  → COMMODITIES
QPS - FICC                                   → STRATEGY
Equity Fundamental                   (id=12) → EQUITY (gated on eq_securities_count)
Equity Product Management            (id=14) → drop (admin)
Equity Non-Fundamental                       → drop (quant equity)
Data Science & Applied AI - Equity           → drop
Sustainable Investing - Equity               → drop
Sustainable Investing - FICC                 → drop (ambiguous; revisit if macro-flavoured)
```

### Cross-check against Deepak's barclays-playwright profile

To validate the asset-class allowlist independently, we mined Deepak's
inherited browsing profile at
`Z:\Business\Personnel\Arjun\playwrights\barclays-playwright` and
grouped every URL he hit by path + query-shape. See
[taxonomy_probe/barclays_deepak_gaps.md](../../../../playground/research/taxonomy_probe/barclays_deepak_gaps.md).

Unlike HSBC (where we scope by `productid` query param), the Barclays
filter operates on **API metadata** (`pubSeriesInfo.assetClassInfo`,
`eqSecurities`, `tags[]`). Deepak's URL history therefore validates
the allowlist *contents*, not the *scope*.

| Deepak's URL | Visits | Maps to allowlist? |
|---|---|---|
| `/BU/research/macro/interest-rates/pubs` | 17 | ✓ `Interest Rates` → RATES |
| `/BU/research/macro/economics/pubs` | 4 | ✓ `Economics` → MACRO |
| `/BU/research/macro/emerging-markets/pubs` | 4 | ✓ `Emerging Markets` → MACRO |
| `/BU/research/content/publication-viewer?...restriction=DEBT` (1 article, 7 hits) | 7 | ✓ Credit content via `Credit Strategy` / `Credit Fundamental` / `Credit Product Management` |
| `/as/authorization.oauth2`, `/UAB/ct_logon_basic`, `/pa/oidc/cb` | 13 | SSO transit |

**Findings:**

1. **All three `/BU/research/macro/{slug}/` sector landings Deepak
   browsed map directly into our allowlist**: `interest-rates` →
   `Interest Rates`, `economics` → `Economics`, `emerging-markets` →
   `Emerging Markets`. The early YAML had only `interest-rates`
   evidenced; this confirms the URL slug set is at least three wide.
2. **Only 1 article was actually opened** ("US Fixed Income
   Issuance: AI-fueled IG supply") — `restriction=DEBT`, Credit content.
   Our allowlist captures it via the four credit asset classes.
3. **No FX / Commodities / Sustainability / Equity URLs** in this
   profile. Deepak's browsing focused on rates, macro economics and
   credit — exactly the macro/rates/FX/credit target buckets. The
   absence of FX/Commodities URLs doesn't suggest a gap (we cover them
   via API-metadata `Foreign Exchange` and `Commodities` asset class
   names), just that this profile was used for FI-focused work.
4. **Local Storage leveldb** cached the same 3 sector pages +
   publication-viewer URL — no hidden scopes, no cached SPA state
   revealing alternate filter axes.

**Verdict**: our 13-entry asset-class allowlist is a superset of every
category Deepak's URL pattern touched. No new asset classes to add, no
URL-scoping shortcut available (the API metadata is more authoritative
than the URL slug anyway).

## Language filter (2026-06-02)

Barclays publishes Tokyo desk notes in Japanese on the same asset
classes we keep for English content (Interest Rates, FX, Global Macro,
Economics). Without a language gate they pass the allowlist and land
in the corpus as broken-encoding `??????` rows (see DB cleanup log
below for the historical mess).

### Signal

`basicInfo.language` — ISO 639-2 alpha-3, always populated.

### Probe results

[`probe_barclays_language.py`](../../../../playground/research/probe_barclays_language.py)
swept the most recent 1,882 pubs (2026-06-02). Output:
[`taxonomy_probe/barclays_language.md`](../../../../playground/research/taxonomy_probe/barclays_language.md).

| language | count |
|---|---|
| `eng` | 1,835 |
| `jpn` | 47 |

All 47 `jpn` pubs sit under `Interest Rates`, `Foreign Exchange`,
`Global Macro`, or `Economics` — i.e. they'd be ingested today without
this filter. Zero `eng`-labelled pubs carried CJK characters in the
title, so the language field alone is reliable — no regex backstop.

### Rule

Allowlist on the language code. Implemented in
[`filters/barclays.py::should_exclude_by_language`](../../../../playground/research/ingest/filters/barclays.py):

```
_KEEP_LANGUAGES = {"eng", ""}   # missing allowed defensively
```

Anything else drops with reason `language:'<code>'`. Allowlist semantics
on purpose: if Barclays adds Chinese (`zho`) or Spanish (`spa`)
tomorrow, those drop by default — no silent ingestion.

The language check runs **first** in the discovery loop (cheapest:
single string compare, no title parsing, no asset-class extraction).

Tests: [`test_barclays_filter.py`](../../../../playground/research/test_barclays_filter.py)
pins five real Japanese pub titles + the allowlist semantics
(`jpn`/`zho`/`spa`/`fra`/`deu` all drop; `eng`/empty pass).

## DB cleanup log

### Tier-1 junk sweep (2026-06-02)

DB audit
([taxonomy_probe/db_audit_2026_06_02.md](../../../../playground/research/taxonomy_probe/db_audit_2026_06_02.md))
flagged 56 Barclays rows for deletion via
`cleanup_tier1_junk.py`:

* **30 broken-encoding titles** — Japanese / CJK characters lost on
  insert showed up as runs of `?` in the title (`??????·??????:
  ????????????????????`). The source delivered Japanese, the persist
  path corrupted to cp1252; unreadable for RAG. **Going forward** these
  pubs are dropped at discovery by the language filter (see above);
  the post-ingest check `title LIKE '%??????%'` remains as a defensive
  backstop in case Barclays ships a `language="eng"` pub with CJK
  characters in the title (none observed in the 1,882-pub probe).
* **27 admin / morning-summary / event-invite rows** — `Barclays
  Americas Morning Research Summary`, `Barclays European Morning
  Research Summary`, `Barclays Americas Small Cap Research Summary`,
  `AFX, GN, COLOB *NEXT WEEK* Barclays Conversations with...`,
  `Amplifon CEO & CFO *TOMORROW* Barclays Conversations with the C...`.
  No analytical content — should be caught by the discovery filter
  (extend `EXCLUDED_TITLE_PREFIXES` / non-research detection) so
  fresh ingests don't re-add them.

Cascade: 1,563 `fact_chunk` rows + 34 `map_report_tag` + 1,563 Qdrant
points + 56 OneDrive PDFs deleted alongside.

## Files

* [`login_barclays.py`](../../../../playground/research/ingest/login_barclays.py)
* [`crawler_barclays.py`](../../../../playground/research/ingest/crawler_barclays.py)
* [`ingest_today_barclays.py`](../../../../playground/research/ingest_today_barclays.py)

## Pipeline contract change

`ingest_one` gained an optional `pdf_bytes: bytes | None` parameter.
When supplied, it skips `fetch_pdf` and uses those bytes directly.
Used only by Barclays today; other 5 vendors still go through fetch.
Barclays needs this because its API only honours `page.evaluate('fetch(...)')`
(needs the SPA's Origin/headers), not the pipeline's `ctx.request.get`.

## Noise filter update (2026-06-10)

Shared cross-vendor noise classifier wired into
[`ingest/filters/_noise.py::classify_noise`](../../../../playground/research/ingest/filters/_noise.py)
and called as the final fallback inside [`filters/barclays.py::should_exclude`](../../../../playground/research/ingest/filters/barclays.py).
Three universal title-pattern families plus a cross-vendor EQUITY
conference / sales-event drop in [`relevance._is_equity_conf_event`](../../../../playground/research/ingest/relevance.py).

Smoke against the full 4,498-title `research.dim_report` corpus dropped
**69 barclays docs**:

| family | n | sample |
|---|---|---|
| chart-pack | 46 | CBOT Ultrabond Futures Multi-factor Analysis; Municipal Strategy: Daily Chart Decks; European Media Valuation Sheet |
| morning-note | 6 | Before the Bell: Your Daily Best of Barclays Research |
| event-admin | 7 | Reminder Tomorrow: Analyst Access: Build America 250; Final Reminder: Corporate Access: Credit Investor Trip; Webinar TOMORROW: Rundown on the Rundown |
| conf-event (EQUITY only) | 10 | Private Equity Funds: Takeaways from Bain's mid-year report; ASCO Breast Cancer KOL Lunch; European Software & Payments: Takeaways from Money20/20 |

The conf-event rule fires only when `result.asset_class == EQUITY` so
MACRO-tagged "Takeaways" / "Trip Notes" titles (real policy / sovereign
macro content) pass through unaffected.

Test pins: [`test_noise_filter.py`](../../../../playground/research/test_noise_filter.py)
(116 chart-pack / morning-note / event-admin assertions),
[`test_relevance_conf_event.py`](../../../../playground/research/test_relevance_conf_event.py)
(35 conf-event assertions). Re-runnable smoke harnesses:
[`_smoke_noise_filter.py`](../../../../playground/research/_smoke_noise_filter.py),
[`_smoke_conf_event.py`](../../../../playground/research/_smoke_conf_event.py).

