# UBS Neo — Research scraper

**Status: LIVE 2026-06-06 (Phases 0–8 done). Daily orchestrator
wiring (`imdr_daily.py`) pending user OK per
`feedback_no_prod_wiring_without_permission`.**

End-to-end pipeline proven against three sample wireIds. Three
endpoints, no `/shared/{hash}` mint dance, no per-doc frontmatter
round-trip:

1. **Login** — programmatic via [`login_ubs.py`](../../../../playground/research/ingest/login_ubs.py).
   Idempotent: `is_authenticated()` short-circuits when cookies are
   still valid (sessions persist across `ctx.close()` for days-to-
   weeks — verified 2026-06-05). `login()` runs only on first use
   of the profile or after expiry.
2. **Listing** — `POST /api/search/v2/research-stream-advanced?q=*&limit=N&offset=N`
   body `{}`, fired via `page.evaluate(fetch)` with `x-csrf-token`
   (captured from the SPA's own first XHR) + `x-client-component-id`
   + `x-original-client-component-id`. Returns rich per-doc JSON.
3. **PDF** — `GET /api/super-grid-provider-research/v1/document/{wireId}.pdf`
   via plain `ctx.request.get`. No CSRF, no special headers.
   Returns `%PDF-1.4` bytes whose size matches the listing API's
   `filesize` field exactly.

```python
# (after login_ubs.login(ctx, ...))

# 1) Warm up + capture x-csrf-token (page.on('response') reads
# response.request.all_headers() — page.on('request') unreliable).
# Visit /home, then /neo-research-document-search-page — that fires
# the listing XHR which carries the SPA's CSRF token.

# 2) Listing — needs page-context fetch (direct ctx.request.post
# returns SPA shell). Body is empty {} — all filtering is via
# query params or the `query` URL-DSL described under "Filter DSL".
listing_url = "https://neo.ubs.com/api/search/v2/research-stream-advanced?q=*&limit=100&offset=0"
headers = {
    "content-type": "application/json", "accept": "*/*",
    "x-client-component-id": "FedPCC_pcc-client-stream-panel",
    "x-original-client-component-id": "FedPCC_pcc-client-stream-panel",
    "x-csrf-token": captured_csrf,
}
# Paginate via response._links.next.href (offset cursor).

# 3) PDF — plain ctx.request.get is sufficient.
pdf_url = f"https://neo.ubs.com/api/super-grid-provider-research/v1/document/{wireId}.pdf"
resp = await ctx.request.get(pdf_url)
pdf_bytes = await resp.body()   # starts with b"%PDF-"
```

End-to-end smoke: [`probe_full_e2e.py`](../../../../playground/research/ubs_explore/probe_full_e2e.py).
Three saved sample PDFs: `sg_uec92139.pdf`, `sg_uec91967.pdf`,
`sg_xrm86382.pdf` (in `playground/research/ubs_explore/`).

## Portal

| | |
|---|---|
| Hostname | `neo.ubs.com` |
| Landing | `https://neo.ubs.com/home` (SSO bounces to `/static/login.html` if unauthed) |
| Username | `.env: IMDR_RESEARCH_UBS_USERNAME` (`adoshi@rvcapital.com`) |
| Password | `.env: IMDR_RESEARCH_UBS_PASSWORD` |
| MFA | **None observed** 2026-06-05 on this user/device. Username + password suffices. `rememberMe1fa` checkbox ticked by `login_ubs.py`. |
| Profile dir | `C:/IMDR_LOCAL/research_profiles/ubs/` (isolated, used only by automation; NOT Deepak's recon profile) |
| Headless | **`headless=False` REQUIRED** — UBS rejects `HeadlessChrome/N` UA; bounces every request to `/static/login.html`. Same BoFA precedent (`crawler_bofa.py:630-637`). |

## Auth + session model

**Sessions persist across `ctx.close()`** — verified 2026-06-05 via
[`probe_session_persistence.py`](../../../../playground/research/ubs_explore/probe_session_persistence.py).
`UBS_NEO_USER` is persistent (2027 expiry); the SAML-bearing
`UBS_NEO_AUTH` / `UBS_NEO_SESSION` / `UBS_NEO_WEBSHELL_ENTITLED`
cookies are nominally session-scoped but Playwright's persistent-
profile user-data-dir preserves them across launches. Sessions last
days-to-weeks, like Goldman/JPM — **NOT** the BoFA pattern (BoFA
truly re-auths every run).

So `login_ubs.login()` runs only when `is_authenticated()` short-
circuits to False — i.e. first use of the profile, or after a real
expiry event. Most crawler runs incur **zero login overhead**.

### Three independent gotchas (all verified 2026-06-05/06)

1. **`headless=True` invalidates the session.** UBS rejects the
   `HeadlessChrome/N` UA — every API call bounces to
   `/static/login.html`. Verified separately from #2 by retrying
   headless against a profile that was logged-in headed (with
   remember-me ON) — still bounces. The crawler MUST use
   `headless=False`.
2. **Ticking `#rememberMe1fa` is an OPT-OUT.** The "1fa" suffix =
   "after first-factor auth". Ticking it tells the server to NOT
   remember the session — that's what initially made sessions look
   session-only. `login_ubs.py` now leaves the checkbox alone.
3. **Stale UBS cookies in the persistent profile hide the login
   form.** When the lazy-relogin path fires (session expired naturally,
   warmup bounces to `/static/login.html`), the persistent profile's
   leftover UBS cookies (`UBS_NEO_LOGIN_PAGE`, `UBS_NEO_RELOADTIME`,
   `UBS_NEO_APPS`, etc.) put UBS in a bad-state UI mode — `#email_input`
   renders into the DOM but is **not visible** (covered by a
   session-recovery overlay). Playwright's `Locator.fill` then times
   out with `element is not visible`. `login_ubs.py` now calls
   `ctx.clear_cookies()` on `*.ubs.com` cookies (preserving unrelated
   Adobe analytics etc.) **before** navigating to the login page, so
   the form renders from a known cookieless state. Observed
   orchestrator failure 2026-06-06 against a profile whose session had
   expired naturally; fixed by the cookie-clear and confirmed by a
   clean orchestrator run that wrote 3 reports end-to-end.

Long-term session durability (hours → days → weeks) is **unverified**.
Back-to-back `ctx.close()` + `launch_persistent_context()` round-trips
preserve the session; the real test is the first daily orchestrator
run after a 24h gap. If sessions die overnight, the lazy-relogin
pattern catches it (auth-fail on warmup → `login_ubs.login()` →
retry).

### Login form structure (snapshot 2026-06-05)

Two-step flow, no MFA. Captured via [`probe_login_form.py`](../../../../playground/research/ubs_explore/probe_login_form.py).

**Step 1 (email)**:
* Input: `#email_input` (text)
* Button: `<button>Next</button>` (no id; select by visible text)

**Step 2 (password)**:
* Input: `input[name="password_input"]` (no id)
* Checkbox: `#rememberMe1fa` — opt-OUT of remember-me. **Do NOT
  tick** — default (unchecked) keeps remember-me ON.
* Button: `<button>Next</button>`

If MFA appears later (device trust revoked), extend `login_ubs.py`
with an MFA-poll pattern from `login_barclays.py`.

## Listing API

| | |
|---|---|
| Method | `POST` |
| Endpoint | `https://neo.ubs.com/api/search/v2/research-stream-advanced` |
| Default params | `?q=*&limit=N&offset=N` (cursor in response `_links.next.href`) |
| Body | `{}` |
| Total archive (`matchedDocuments`) | **905,877** as of 2026-06-05 |
| Required headers | `x-csrf-token`, `x-client-component-id: FedPCC_pcc-client-stream-panel`, `x-original-client-component-id: FedPCC_pcc-client-stream-panel`, `content-type: application/json` |
| Must call via | `page.evaluate(fetch(...))` — direct `ctx.request.post` returns the 702KB SPA HTML shell (the server's SPA-routing middleware filters direct-request UA/origin) |

The `x-csrf-token` is a 24h-TTL JWT, user-bound, injected by the SPA
JS bundle. The crawler captures it from the SPA's own first
research-stream-advanced XHR during a `/neo-research-document-search-page`
warmup visit. JWT payload decodes to
`{"sub":"PCC<user-hash>", "iat":..., "exp":iat+86400}`.

### Per-doc response schema

```json
{
  "matchedDocuments": 905877,
  "categories": {
    "research": {
      "matchedDocuments": 905877,
      "results": [{
        "wireId":                 "uec92139",
        ".id":                    "researchMetadata-uec92139",
        "title":                  "Orlen SA \"Positive revision ...\" (Neutral)",
        "documentTitle":          "Orlen SA",
        "documentHeadline":       "Positive revision despite tax pressure - 1Q26 review",
        "summaryText":            "We welcome ...",
        "hookText":               "...",
        "businessAreaCode":       "B.STOCK",
        "businessArea":           "Stock",
        "productCode":            "P.STOCK.ISS.COM.0001041137.A",
        "productName":            "Orlen SA",
        "region":                 "Poland",         // or list[str]
        "primaryRegion":          "Poland",
        "country":                "Poland",         // or list[str]
        "subjectCode":            ["S.CHGUPPT", "S.EMERGING"],
        "pubDate":                "2026-06-08T00:00:00.000",
        "documentStatus":         "Published",
        "publishingEntity":       "UBS Limited",
        "ric":                    "PKN.WA",         // or list[str] for sector pubs
        "cdtRic":                 "PKN.WA",
        "cdtIssuerBloombergCode": "PKN PW",
        "filesize":               537010,
        "pageCount":              16,
        "primaryGpn":             "43679557",
        "primaryAnalystName":     "Rafael De La Fuente",
        "author":                 ["Alex de Azara", "Andrea Casaverde", ...],
        "gpn":                    ["43313376", "43510432", ...],
        "fileType":               "Acrobat",
        "responsiveRenditionUrl": "/api/cobalt/71888b60-5388-11f1-8216-ff2eb6ed7631/index.html",
        "neoUrlPath":             "/pubs/jun26/uec92139.pdf",  // see Red herrings — NOT the PDF endpoint
        "chronicleId":            "71888b60-5388-11f1-8216-ff2eb6ed7631",
        "cdeId":                  101255696,
        "australianRetailReady":  false,
        "isGlobalAccessAllowed":  true,
        "isNonUSAccessAllowed":   true,
        "shareable":              true,
        "_links": { "self": {...}, "author": [...], "primaryAnalyst": {...} }
      }]
    },
    "_links": {
      "self": { "href": "...?q=*&offset=0&limit=3" },
      "next": { "href": "...?q=*&offset=3&limit=3" }
    }
  }
}
```

Full reference dump: [`listing_api_full3.json`](../../../../playground/research/ubs_explore/listing_api_full3.json).

### Field → IMDR mapping

| listing field | meaning | crawler use |
|---|---|---|
| `wireId` | Canonical doc ID (5-letter+5-digit) | **primary key** for `dim_report.vendor_doc_id`; PDF filename |
| `title` / `documentTitle` / `documentHeadline` | Title variants | `dim_report.title` (use `title` — combines series + headline) |
| `summaryText` / `hookText` | Abstracts | `dim_report.context` (concat with title) |
| `pubDate` | Publication timestamp | `dim_report.pub_date` + early-stop cursor |
| `businessAreaCode` | Tier-0 taxonomy (see below) | classifier — primary asset-class signal |
| `productCode` | Series taxonomy (see below) | classifier — single-name detection (`P.STOCK.ISS.COM.*.A`) |
| `region` / `primaryRegion` / `country` | Geography (scalar or list) | classifier — country tag |
| `subjectCode` | Subject tags (`S.*`) | classifier — additional tags |
| `ric` / `cdtRic` / `cdtIssuerBloombergCode` | Tickers | **single-name signal** when populated (drops single-name unless Macro-tagged) |
| `author` / `primaryAnalystName` / `primaryGpn` / `gpn` | Analyst info | `dim_report.author` (`primaryAnalystName` as display, `primaryGpn` as id) |
| `filesize` | PDF size in bytes | sanity-check vs fetched bytes |
| `pageCount` | PDF page count | metadata |
| `chronicleId` | UUID (also in `responsiveRenditionUrl`) | de-dup key vs Deepak history `/api/cobalt/{uuid}/index.html` |
| `documentStatus` | `"Published"` etc | drop non-`Published` |
| `australianRetailReady` / `isGlobalAccessAllowed` / `isNonUSAccessAllowed` | Access flags | informational |
| `shareable` | bool | informational |
| `fileType` | `Acrobat` / `Excel` / etc | drop non-`Acrobat` (only PDFs are parseable) |
| `neoUrlPath` | **NOT the PDF URL** — see Red herrings | ignore |
| `responsiveRenditionUrl` | `/api/cobalt/{uuid}/index.html` HTML rendition | not used (we fetch PDF directly) |

### Filter DSL (`/articles?query=…` URL-DSL)

The SPA's `/articles?filterType=advanced&query={JSON}` deep-links use
a JSON filter DSL that's almost certainly the same shape the listing
API accepts in the request body (untested — the SPA itself sends
body `{}` and uses query params). Skeleton observed in captured
hrefs:

```json
{
  "filters": {
    "andFilters": {
      "businessAreaCode": ["B.ECONOMIC"],
      "productCode": ["P.ECONOMIC.REGN.GEN.EU.C"],
      "languageCode": ["en"]
    },
    "orFilters": {
      "productName_OR": ["Global Oil Fundamentals"],
      "gpn_OR": ["43327822", "43281813"],
      "fileType_OR": ["Acrobat", "Excel", "PDF", "XLS", "ZIP", "HTM"]
    }
  }
}
```

Extra query-string params on the `/articles?…` URL — not necessarily
respected by the API directly: `pubType` (CSV enum:
`livedesk-video, commentary, idea, evidence-lab, morningmeeting,
researchcommentary, thoughtleader, global-banking-data-lab`),
`tagsOperator` (`OR`/`AND`), `tags` (JSON array), `title` (display
label only).

### Business area codes (Tier-0 taxonomy)

| code | description |
|---|---|
| `B.ECONOMIC` | Economics |
| `B.STRATEGY` | Equity Strategy |
| `B.ASSALOC` | Global / Asset Allocation Strategy |
| `B.FX` | FX Strategy |
| `B.RATES` | Rates Strategy |
| `B.EM` | Emerging Markets |
| `B.CRSTRATEGY` | Credit Strategy |
| `B.STOCK` | Single-name / sector equity (drop unless Macro per relevance filter) |

### Product code grammar

`P.{DOMAIN}.{SCOPE}.GEN.{REGION}.{LETTER}` for series; structure varies
slightly per business area. Key patterns:

| pattern | example | meaning |
|---|---|---|
| `P.STRATEGY.REGN.GEN.GL.S` | Global Equity Strategy | regional series |
| `P.ECONOMIC.REGN.GEN.EU.C` | European Economic Perspectives | regional Economics |
| `P.FX.REGN.GEN.GL.I` | Global FX Strategy | global FX |
| `P.RATES.REGN.GEN.GL.N` | Weekly Supply Preview | global Rates |
| `P.STRATEGY.CTRY.GEN.TH.I` | Thailand Market Strategy | country-anchored |
| `P.STOCK.SECT.GEN.{SECTOR}.{X}` | N.A. Chems & Pkg'g | sector equity |
| `P.STOCK.ISS.COM.{ISSUERID}.A` | Broadcom Inc. (`205055007`) | **single-name equity** — drop signal |

## PDF endpoint

```
GET https://neo.ubs.com/api/super-grid-provider-research/v1/document/{wireId}.pdf
```

Deterministic from `wireId` alone. Backs the "Access document" button
in the SPA's article reader. Verified 2026-06-05 against three
wireIds — all return `%PDF-1.4` bytes with sizes matching the listing
API's `filesize` field exactly:

| wireId | bytes | listing-API `filesize` |
|---|---|---|
| `uec92139` | 537,010 | 537,010 |
| `uec91967` | 1,573,159 | "1.5 MB" in app preview |
| `xrm86382` | 1,524,003 | "1.5 MB" in app preview |

Fetch via plain `ctx.request.get(pdf_url)` — no CSRF token needed
(GET is safe-method), no special headers. Session cookies from the
post-login profile are sufficient. This is the **Goldman / Nomura
family** per the playbook — cheapest possible fetch.

## ID family

| ID | example | where it appears |
|---|---|---|
| `wireId` (5+5) | `uec92139` | **PRIMARY KEY** — listing API field, PDF endpoint path, SPA reader URL, cross-doc citations |
| `chronicleId` (UUID) | `c1bc7c8c-5ea9-11f1-85af-1587bd2db393` | listing API field; HTML rendition path `/api/cobalt/{uuid}/index.html` |
| `cdeId` (numeric) | `101255696` | listing API field; internal back-end ID |
| `pubId` (`U{12-digit}`) | `U122632360851` | figure anchor prefix in the rendered HTML reader; not exposed in listing API |
| `hash` (~14-char base62) | `d2W90zdo47yuMIe` | `/shared/{hash}/` permalink URL **— red herring**, not needed for ingest |

## URL patterns (inventory)

For reference and cross-doc citation handling:

| Type | URL template | Example |
|---|---|---|
| Portal landing | `/home` | — |
| Discover feed | `/feed/discover/{suggested,latest,most-read}` | `/feed/discover/latest` |
| Following feed | `/feed/all` | — |
| Strategy hub | `/macrostrategy`, `/macrostrategyequity` | `/macrostrategy` |
| Asset-class hub | `/economics`, `/strategy`, `/fx`, `/rates` | `/economics` |
| Articles search (UI) | `/articles?filterType=advanced&query={JSON}&type=research&pubType=…` | see Filter DSL above |
| Doc search (UI) | `/neo-research-document-search-page` | the dropdown-faceted UI |
| Doc content (SPA reader, permalink) | `/shared/{hash}/` | `/shared/d2W90zdo47yuMIe/` |
| Doc content (SPA reader, wireId) | `/article-reader/research/{wireId}` | `/article-reader/research/uec92031` (returns 404 if visited directly; only the SPA's in-app router resolves it) |
| Doc content (HTML rendition) | `/api/cobalt/{region\|uuid}/{uuid}/index.html` | `/api/cobalt/chn/ea82f759-…/index.html` |
| **PDF download** | `/api/super-grid-provider-research/v1/document/{wireId}.pdf` | canonical — see above |
| Tag stream | `/feed/stream/tag/{tag}` | `/feed/stream/tag/XAU` |
| Company stream | `/feed/stream/company/{ric}` | `/feed/stream/company/2875.T` |
| Analyst profile | `/profile/PSI{psid}` or `/person/{psid}` | `/profile/PSI43459535` |
| LiveDesk | `/livedesk?{post,Tag,Author,featured,tab}=…` | `/livedesk?tab=Top` |
| Login | `/static/login.html?origin=…` | SSO entry |

## Expected content focus

Per Deepak's `ubs-playwright` history (see
[`playground/research/deepak_recon/ubs-playwright.md`](../../../../playground/research/deepak_recon/ubs-playwright.md)):

| title prefix | visits |
|---|---|
| Global Macro Chart of the Day | 18 |
| Global Strategy | 14 |
| Latin American Economic Perspectives | 14 |
| Strategy & Economics | 12 |
| Australian Economic Comment | 11 |
| China Economic Comment | 9 |
| Latin American Economic Comment | 8 |
| European Economic Perspectives | 6 |
| European Economic Comment | 6 |
| US Economic Perspectives | 5 |
| Japan Macro Watch | 4 |
| APAC / EMEA / UK / India / NZ Economic Comments + Perspectives | 2-4 each |

Overwhelmingly macro / strategy / regional Economics — direct
universe overlap. Minimal single-name leakage observed in the recon
(one Global Equity Derivatives Strategy entry; handful of
`UBS Neo - Research - Video: …` items that the discovery filter
should drop).

Pre-Phase-3 daily-volume estimate: **~30-60/day raw**, **~25-50/day
kept** after standard video / chart-pack drops. To be confirmed
empirically once the crawler ingests 2-3 days.

## Phase-1 captures (2026-06-05)

8 snapshots, two sessions, all preserved in
[`playground/research/ubs_explore/`](../../../../playground/research/ubs_explore/):

**Session A** (`15:21Z–15:27Z`):

| idx | url | notable |
|---|---|---|
| 0–3 | `/home` | landing — Knowledge Network feed, 15→70 links as widgets render |
| 4 | `/feed/discover/suggested` | discover hub — chronological recent reports |
| 5–6 | `/macrostrategy` | Strategy & Economics — Macro Strategy hub |
| 7 | `/neo-research-document-search-page` | search page (39,108 Economics docs) |

**Session B** (`16:35Z`): two captures of one Global Strategy report
(`uec91646` "Rates and risk after 60 bps real rate move in 60 days",
20 May 2026) at `/shared/d2W90zdo47yuMIe/`. Confirmed the reader is
in-page HTML with **Print / Download / Share / Ask the Analyst**
toolbar.

## 7-day smoke (2026-06-06)

Two passes:

| metric | Phase 3 v1 | Phase 8 (tight) |
|---|---|---|
| Discovered (after crawler-level drops) | 211 | 195 (16 First-Read drops at discovery) |
| Kept post-relevance | 148 (70%) | **119 (61%) — ~20/day net** |
| MACRO | 46 (31%) | 47 (40%) |
| EQUITY | 58 (39%) — sector wraps + dailies | **28 (24%) — genuine macro-flavored only** |
| STRATEGY | 26 (18%) | 26 (22%) |
| ESG | 12 (8%) | 12 (10%) |
| RATES | 5 (3%) | 5 (4%) |
| FX | 1 (1%) | 1 (1%) |

**Phase 8 tightening (2026-06-06)** — after the hard taxonomy probe
identified `_UBS_EQUITY_KEEP` as too loose (standalone cadence words
`weekly|daily|morning|monitor|database|tracker|brief|wrap` were
letting sector noise through), two changes:

1. **`First Read:` discovery-time drop** in `filters/ubs.py`
   `EXCLUDED_TITLE_PREFIXES` — UBS Equity Research's single-event
   quick-take format ("First Read: China hotel RevPAR ...", "First
   Read: Vale Indonesia Tbk ..."). Most post-single-name-drop
   survivors are sector event-driven noise. -16 docs/week.
2. **Cadence-with-anchor secondary check** in `relevance.py`'s
   UBS branch: `_UBS_EQUITY_CADENCE_WITH_ANCHOR_RE` requires
   cadence keywords (Morning/Weekly/Daily/Top of Mind/Wrap/Brief)
   to co-occur with a macro anchor (global/cross-asset/allocation/
   macro/strategy/economic/rates/fx/regional). `_UBS_EQUITY_KEEP`
   itself tightened to **high-signal-only keywords** (strategy,
   portfolio, cross-asset, allocation, outlook, thematic,
   positioning, top of mind, earnings preview/season, global
   research, markets now). Net effect: -29 EQUITY/week.

Noise removed post-Phase-8: Morning Expresso, China Autos Pricing
Database, Greater China Banks Daily, UBS Event Calendar, First Read:
single-event sector notes. Kept: SA commodity monitor, Thailand
Market Strategy, China Equity Strategy, Macau Gaming Evidence Lab,
Investor Positions Indonesia.

Country coverage: 22 US + 15 AU + 6 JP + 5 CN + 4 ID + 3 IN + 3 FR +
smaller weights for CA/AR/TH/CH/UK/TR/ZA/SE/HK/KR/MY/SG/CO.

Region buckets: 31 apac + 24 global + 23 americas + 18 emea + 5 latam.

Full logs: [`_smoke_ubs_7day_2026-06-06.log`](../../../../playground/research/_smoke_ubs_7day_2026-06-06.log)
(Phase 3) + [`_smoke_ubs_7day_2026-06-06_phase8.log`](../../../../playground/research/_smoke_ubs_7day_2026-06-06_phase8.log)
(Phase 8). Probe summary at [`taxonomy_probe/ubs_full.md`](../../../../playground/research/taxonomy_probe/ubs_full.md).

## Phase 3 architecture (live 2026-06-06)

| layer | file | role |
|---|---|---|
| Login | [`login_ubs.py`](../../../../playground/research/ingest/login_ubs.py) | Programmatic, idempotent, lazy-relogin |
| Crawler | [`crawler_ubs.py`](../../../../playground/research/ingest/crawler_ubs.py) | `discover_reports(profile_dir, since, until)` → `list[ReportRef]` |
| Filter | [`filters/ubs.py`](../../../../playground/research/ingest/filters/ubs.py) | Drops single-name (productCode / RICs), non-Acrobat, non-Published |
| Classifier | [`classifiers/ubs.py`](../../../../playground/research/ingest/classifiers/ubs.py) | `businessAreaCode` → asset_class; country/region resolution |
| Relevance | [`relevance.py`](../../../../playground/research/ingest/relevance.py) — `vendor_code == "ubs"` branch | Default-drop EQUITY unless macro-subject or title-keyword keep allowlist |
| Orchestrator | [`ingest_today.py`](../../../../playground/research/ingest_today.py) `_load_vendor_registry()` | `"ubs": VendorSpec(code="ubs", discover=ubs_discover)` |
| DB seed | [`migrations/080_seed_ubs_dim_vendor.sql`](../../../../migrations/080_seed_ubs_dim_vendor.sql) | `INSERT INTO dim_vendor` (idempotent) |

## Open items

- [x] **Phase 2a** — PDF URL → `/api/super-grid-provider-research/v1/document/{wireId}.pdf`.
- [x] **Phase 2b** — listing API shape, headers, pagination.
- [x] **Phase 2c** — primary key choice → `wireId`.
- [x] **Phase 2d** — session model + programmatic login (`login_ubs.py`).
- [x] **Phase 3** — crawler / filter / classifier scaffolding live.
- [x] **Phase 4** — wired into `ingest_today.py` orchestrator (2026-06-06).
- [x] **Phase 5** — `dim_vendor` seed migration written (080).
- [ ] **Phase 5b** — DBA to apply migration 080 + first orchestrator run
  (`python ingest_today.py --vendors ubs --embed false --limit 3`).
- [ ] **Phase 6** — First full `--embed true` day; eyeball `dim_report`
  + Qdrant chunks + retrieval spot-check.
- [x] **Phase 8** — Hard taxonomy probe + tightening done 2026-06-06.
  `First Read:` discovery-drop + `_UBS_EQUITY_CADENCE_WITH_ANCHOR_RE`
  added. EQUITY survivors 58 → 28; total kept 148 → 119 (~20/day).
  Probe summary: [`taxonomy_probe/ubs_full.md`](../../../../playground/research/taxonomy_probe/ubs_full.md).
- [ ] **Phase 9** — wire into production scheduler (`scripts/imdr_daily.py`
  or whatever cadence we want UBS to run on). Pending user OK per
  `feedback_no_prod_wiring_without_permission`.

## Red herrings — do not pursue

* **`/shared/{hash}/{wireId}.pdf`** — works for `d2`-prefix hashes
  minted via the SPA's natural click flow, but the only programmatic
  mint we found (`POST /api/share/v1/articles/{wireId}` body
  `{"target":"<wireId>"}`) returns `d1`-prefix hashes that bounce to
  a broken URL. The super-grid endpoint above bypasses the whole
  share-link mechanism.
* **`/api/cobalt/{uuid}/index.pdf`** — `.html` rendition path doesn't
  swap to `.pdf`; returns 404.
* **`/pubs/{monYY}/{wireId}.pdf`** — `neoUrlPath` field in the listing
  response. The `.pdf` extension is a routing red herring; returns
  HTML SPA shell.
* **`POST /api/share/v1/articles/{wireId}`** with `{"target":...}`
  body returns 200 with a `link` containing a `d1`-prefix hash —
  these hashes do NOT serve PDFs.

## Phase-2 PDF-fetch failures (for context, not for crawler use)

Three strategies failed against `d1` shared-link URLs before we
discovered the super-grid endpoint:

* `page.evaluate(fetch(...).arrayBuffer())` — blocked by UBS's
  `neo-shims@2.0.0.min.js` fetch interceptor: `TypeError: Failed to fetch`.
* `ctx.request.get(...)` — TLS handshake fails mid-write:
  `EPROTO EC0E0000 SSL routines: tls_get_more_records: packet`.
* `page.goto(pdf_url) + page.expect_download(...)` — 15s timeout.

These failures applied **only** to the wrong-mint `d1` URL. The
super-grid endpoint works on `ctx.request.get` first try.

## Reference

- [Onboarding playbook](../onboarding_new_vendor.md) — long-form workflow.
- [Deepak recon](../../../../playground/research/deepak_recon/ubs-playwright.md) — pre-Phase-1 footprint.
- [Vendor row](../../../../playground/research/vendors.yml) — credentials + profile path.
- [`login_ubs.py`](../../../../playground/research/ingest/login_ubs.py) — programmatic login.
- [`probe_full_e2e.py`](../../../../playground/research/ubs_explore/probe_full_e2e.py) — end-to-end smoke probe.
- [`probe_login_form.py`](../../../../playground/research/ubs_explore/probe_login_form.py) — login form selector capture.
- [`listing_api_full3.json`](../../../../playground/research/ubs_explore/listing_api_full3.json) — full per-doc response shape.
- [`crawler_bofa.py:630-637`](../../../../playground/research/ingest/crawler_bofa.py) — precedent for `headless=False` + programmatic-login + session-only cookies.
- [`crawler_barclays.py:106-127`](../../../../playground/research/ingest/crawler_barclays.py) — `_PAGE_FETCH_JS` + `_PAGE_FETCH_PDF_JS` precedent for in-page CSRF-bearing fetch.
- [`crawler_goldman.py`](../../../../playground/research/ingest/crawler_goldman.py) — closest crawler template (deterministic PDF + rich listing metadata).

## Noise filter update (2026-06-10)

Shared cross-vendor noise classifier wired into
[`ingest/filters/_noise.py::classify_noise`](../../../../playground/research/ingest/filters/_noise.py)
and called as the final fallback inside [`filters/ubs.py::should_exclude`](../../../../playground/research/ingest/filters/ubs.py).
Three universal title-pattern families plus a cross-vendor EQUITY
conference / sales-event drop in [`relevance._is_equity_conf_event`](../../../../playground/research/ingest/relevance.py).

Smoke against the full 4,498-title `research.dim_report` corpus dropped
**6 ubs docs**:

| family | n | sample |
|---|---|---|
| chart-pack | 6 | Healthcare Facilities & Managed Care "Weekly Chartbook: Hospital Vols, T..."; EM Multi Asset Chartpack; Global Macro Chart of the Day (#96–#98); Semis Monthly Chart Pack |
| morning-note | 0 | (none — Morning Expresso already handled via `_UBS_EQUITY_CADENCE_WITH_ANCHOR_RE`) |
| event-admin | 0 | (none) |
| conf-event (EQUITY only) | 0 | (none — UBS B.STOCK + n_rics single-name filter already catches stock-pick takeaways at discovery) |

The conf-event rule fires only when `result.asset_class == EQUITY` so
MACRO-tagged "Takeaways" / "Trip Notes" titles (real policy / sovereign
macro content) pass through unaffected.

Test pins: [`test_noise_filter.py`](../../../../playground/research/test_noise_filter.py)
(116 chart-pack / morning-note / event-admin assertions),
[`test_relevance_conf_event.py`](../../../../playground/research/test_relevance_conf_event.py)
(35 conf-event assertions). Re-runnable smoke harnesses:
[`_smoke_noise_filter.py`](../../../../playground/research/_smoke_noise_filter.py),
[`_smoke_conf_event.py`](../../../../playground/research/_smoke_conf_event.py).


## Credit coverage (2026-07-17)

Credit-coverage audit ([dev-doc](../../development/credit_bofa.md)): covered-bond / structured-credit notes filed under the Rates desk (`businessAreaCode=B.RATES`) were tagged RATES (e.g. "Global Rates Comment: Covered Bonds …"). `classifiers/ubs.py` now upgrades a `B.RATES`/unclassified note to CREDIT when the title names a credit product, via the shared `canonical.looks_like_credit`. Only upgrades RATES/"" → CREDIT (never EQUITY/FX/MACRO). Test: `tests/unit/research/test_credit_title_override.py`. **Open:** UBS IG/HY credit strategy may sit in an un-scraped Neo hub — discovery-scope probe deferred.
