# Indonesia — Government & Quasi-Government Document Sources

Last updated: 2026-09-21 (Phase H discovery + Phase J promotion)

Track B inventory for Indonesia, per [`../onboarding_new_country.md` § Phase H](../onboarding_new_country.md#phase-h--government--cb-document-sources-track-b).
**Status: **PROD-LIVE 2026-09-21** — 537 reports / 8,411 chunks in `research.dim_report` + Qdrant + SharePoint (zero SQL↔Qdrant drift); `scripts.econ.id.id_daily` registered in `scripts/imdr_daily.py:PIPELINES`, replacing the two individual ID entries it supersedes.** Ops reference in
[indonesia_govt_prod_pipeline.md](indonesia_govt_prod_pipeline.md), which also
records the Qdrant batching bug the full ingest uncovered (framework-wide, not
ID-specific).

Track A (time-series) is separate and already live — 356 indicators across
BPS/BI/BIS/DJPPR, see [indonesia_indicator_inventory.md](indonesia_indicator_inventory.md).
Anything that lands in `econ.fact_indicator` belongs there, not here. The rule of
thumb that decided every ambiguous row below: **the BRS number is Track A; the BRS
narrative is Track B.**

## Discovery result in one table

| Agency | Tier | Streams | Discovered | Ingestable | `vendor_category` | Transport | Status |
|---|:---:|:---:|---:|---:|---|---|:---:|
| **BI** (Bank Indonesia) | 1 | 10 | 79 | 79 | `official_cb` | httpx + `.aspx` parse | ✅ built |
| **DJPPR** (debt mgmt) | 1 | 3 | 519 | 425 | `official_ministry` | httpx + JSON CMS API | ✅ built |
| **OJK** (fin. regulator) | 1 | 3 | 30 | 30 | `official_regulator` (mig 129) | httpx + `.aspx` parse | ✅ built |
| **BPS** (statistics) | 1 | 1 (+2 opt-in) | 10 / 1,904 | 10 | `official_statistics` | httpx + WebAPI (key) | ✅ built |
| **Kemenkeu** (MoF) | 1 | 0 | 0 | 0 | *not seeded* | — | ❌ BLOCKED |

## Production fetchers (2026-09-21)

11 modules at [`scripts/econ/id/govt/`](../../../../scripts/econ/id/govt/):
`_http.py` · `_models.py` · `_bi_aspnet.py` · `resolvers.py` ·
`fetch_{bi,bps,djppr,ojk,kemenkeu}.py` · `ingest_filings.py`, orchestrated by
[`scripts/econ/id/id_daily.py`](../../../../scripts/econ/id/id_daily.py).
67 unit tests at `tests/unit/test_econ/test_id_govt_parsers.py` (plus 19 in
`test_bi_data_series.py` for the Track A additions).

The 94-row discovered-vs-ingestable gap is DJPPR's undated reference
artefacts — recorded in the daily manifest, deliberately not ingested.

**638 items on the first run; 0 on the second** — dedup is idempotent. The code was
promoted out of `playground/econ/id/govt/`, which was then removed rather than left
as a duplicate of the prod tree.

---

## 1. Central bank — Bank Indonesia (BI)

The highest-signal source by a distance: the BI-Rate decision, the monthly policy
review, the quarterly policy report and the semi-annual FSR are all here, and all
on one page template.

| Stream | URL | Cadence | Lang | Crawl | Tier | Built |
|---|---|:---:|:---:|:---:|:---:|:---:|
| News releases (ID) | `bi.go.id/id/publikasi/ruang-media/news-release/default.aspx` | ~2-3/wk | id | direct GET | 1 | ✅ |
| News releases (EN) | same, `/en/` | ~2-3/wk | en | direct GET | 1 | ✅ |
| **BI-Rate decision (RDG)** | *no dedicated URL* — a news release, see below | monthly | id+en | direct GET | **1** | ✅ |
| Tinjauan Kebijakan Moneter (policy review) | `?Kategori=laporan kebijakan moneter` | monthly | id | direct GET | 1 | ✅ |
| Laporan Kebijakan Moneter (policy report) | same category, title-filtered | quarterly | id | direct GET | 1 | ✅ |
| Kajian Stabilitas Keuangan (FSR) | `?Kategori=kajian stabilitas keuangan` | semi-annual | id | direct GET | 1 | ✅ |
| Analisis Inflasi | `?Kategori=analisis inflasi` | monthly | id | direct GET | 1 | ✅ |
| Perkembangan Uang Beredar | `?Kategori=perkembangan uang beredar` | monthly | id | direct GET | 2 | ✅ |
| Neraca Pembayaran / IIP report | `?Kategori=neraca pembayaran dan posisi investasi internasional indonesia` | quarterly | id | direct GET | 2 | ✅ |
| Laporan Perekonomian Indonesia (annual) | `?Kategori=laporan perekonomian` | annual | id | direct GET | 2 | ✅ |
| Governor speeches | `bi.go.id/id/publikasi/ruang-media/pidato-dewan-gubernur/default.aspx` | ~annual | id+en | direct GET | 2 | ✅ |

### 1.1 The RDG decision has no dedicated page — and BI renamed it

The single most important document in this whole inventory arrives as an ordinary
**news release**, not as its own stream. Worse, BI changed the headline convention:
it used to publish "Hasil Rapat Dewan Gubernur {Month} {Year}" and now leads with
the rate itself.

Confirmed instance (2026-08-19, release seq 162, a **14,413-character** statement):

> BI-Rate Tetap 5,75%: Memperkuat Stabilitas, Mendorong Pertumbuhan Ekonomi

`fetch_bi.RDG_TITLE` matches both spellings and promotes the row to
`doc_type="decision"` so the corpus can separate canonical policy text from routine
press.

⚠️ **Do not loosen that pattern to a bare "board of governors"** — that phrase also
appears on personnel announcements ("Inauguration of Members of the Bank Indonesia
Board of Governors", 2026-09-02), which were mis-tagged as decisions before the
pattern was tightened. Pinned by
`tests/unit/test_econ/test_id_govt_parsers.py::test_rdg_title_ignores_non_decisions`.

### 1.2 The 21 report categories (BI's own list, not ours)

`publikasi/laporan/default.aspx` accepts a server-side `?Kategori=` filter. This is
**not documented anywhere on the site** — it was recovered from an ASP.NET
`pageRedirect` payload (see § Probe evidence), which also leaked the complete
category enumeration:

```
laporan perekonomian · laporan tahunan bank indonesia
laporan ekonomi dan keuangan syariah · kajian stabilitas keuangan
laporan pelaksanaan tugas dan wewenang bank indonesia · laporan kebijakan moneter
laporan nusantara · perkembangan ekonomi keuangan dan kerja sama internasional
perkembangan uang beredar
neraca pembayaran dan posisi investasi internasional indonesia
survei konsumen · survei kegiatan dunia usaha · survei perbankan
survei harga properti residensial di pasar primer · survei penjualan eceran
survei proyeksi indikator makro ekonomi · perkembangan properti komersial
prompt manufacturing index · analisis inflasi · buku dedikasi untuk negeri
laporan lainnya
```

A sibling `?Periode=` accepts `bulanan,triwulan,semesteran,tahunan`. Categories are
lower-case with literal spaces; they live in `_bi_aspnet.BI_REPORT_CATEGORIES`.

Two notes on this list:
- **`?id=<slug>` is a decoy.** `Default.aspx?id=tinjauan-kebijakan-moneter` returns
  byte-identical output to the unfiltered page. Only `?Kategori=` filters.
- **TKM and LKM share one bucket.** "laporan kebijakan moneter" returns both the
  monthly review and the quarterly report; they separate only by title prefix.

### 1.3 `/id/` runs AHEAD of `/en/`

On 2026-09-21 the Indonesian news-release listing was at **17 Sep** while the English
mirror was still at **10 Sep** — a full week of lag. Both are fetched. Prefer `/id/`
for recency and `/en/` when English text matters.

### 1.4 Not onboarded from BI

| Stream | Why not |
|---|---|
| Survei Perbankan (banking survey) | ✅ **onboarded to Track A** 2026-09-21 as `bi_bank_survey` — the survey *series* is the signal, not the PDF |
| Prompt Manufacturing Index | ✅ **onboarded to Track A** 2026-09-21 as `bi_pmi` — BI's own PMI, quarterly, 2010 Q1→ |
| Laporan Nusantara (regional) | Tier 3 — regional colour, low market impact |
| Peraturan / PBI (regulations) | Tier 3 — legal text, not policy reasoning |
| SEKI advance release calendar | ❓ not found as a structured page — see Open items |

---

## 2. Cabinet ministries — Ministry of Finance (Kemenkeu) ❌ BLOCKED

**Tier 1 by importance, zero streams built.** Full write-up in
[`scripts/econ/id/govt/fetch_kemenkeu.py`](../../../../scripts/econ/id/govt/fetch_kemenkeu.py).

What we want: **APBN KiTa** (monthly budget-realisation), tax-revenue prints, the
annual Nota Keuangan/RAPBN, fiscal-policy communication.

Why it is not reachable — three findings, in order:

1. `www.kemenkeu.go.id` is an **Angular SPA**. Every route returns the identical
   27,009-byte shell. No server-rendered listing exists to parse.
2. **The data API is not discoverable statically.** All four JS bundles (~1.1 MB)
   contain zero `kemenkeu.go.id` API URLs and zero `/api/v{n}` paths — only
   `media.kemenkeu.go.id/API/GetAsset/...` image endpoints. `/feed`, `/rss`,
   `/rss.xml`, `/wp-json/wp/v2/posts`, `kemenkeu-prime.../api/...` all return the
   shell or 404. `sitemap.xml` is static routes only.
3. **The browser route needed to discover it is blocked by RV's corp firewall.**
   Playwright headless Chromium gets an interstitial:

   ```
   Web Page Blocked!
   URL: www.kemenkeu.go.id/informasi-publik/publikasi/siaran-pers
   Attack ID: 20000051
   ```

Per playbook § H.6 this is **not** yet a confirmed block. It is host- and
transport-specific: plain httpx retrieves the SPA shell from the same machine, and
the sibling host `djppr.kemenkeu.go.id` is fully reachable. That is the AOFM-vs-APRA
pattern from Australia — a proxy rule on one host, not a `.go.id` blanket rule.

> ### ✅ H.6 gate RESOLVED 2026-09-21 — it is our proxy, not the site
>
> The user confirmed `www.kemenkeu.go.id` **loads normally in their own
> browser**. Combined with the probe evidence (plain httpx retrieves the SPA
> shell; Chromium gets the interstitial), the diagnosis is settled: RV's
> corporate firewall blocks the *automated browser*, the site is healthy, and
> the sibling host `djppr.kemenkeu.go.id` is unaffected.
>
> **Next step is an IT request, not more engineering.** Draft:
>
> > Please allowlist `www.kemenkeu.go.id` (Indonesian Ministry of Finance) for
> > outbound automated HTTP from the research workstation. It is currently
> > blocked by the web filter — "Web Page Blocked! Attack ID: 20000051" — when
> > loaded by headless Chromium, while the same host loads normally in a
> > desktop browser and responds to plain HTTPS requests from the same
> > machine. It is a public government statistics/budget portal
> > (APBN KiTa monthly budget-realisation releases); we need it for the same
> > macro-data pipeline that already reads `djppr.kemenkeu.go.id`,
> > `bi.go.id`, `bps.go.id` and `ojk.go.id`. No credentials or POSTs involved
> > — read-only page and PDF fetches.
>
> Once allowed: open the press listing in DevTools, capture the XHR the SPA
> issues, and build a JSON fetcher in `fetch_kemenkeu.py`. Do **not** resume
> guessing endpoints — steps 1-2 above already exhausted that.

**Impact is contained**, which is why this was deferred rather than escalated
mid-task: Track A never depended on MoF — fiscal aggregates come from BI SEKI
IV.1-3 (`bi_fiscal`) and debt/issuance from DJPPR, both live. What is missing is the
APBN KiTa *narrative*, and DJPPR's `siaranpers` carries much of the debt-side story.

### Other ministries — not surveyed

Trade (Kemendag), Industry (Kemenperin), Manpower (Kemnaker), Coordinating Ministry
for Economic Affairs (Kemenko Perekonomian) are **Tier 2/3 and unprobed**. Deliberate:
MoF is the only Tier-1 ministry, and it is blocked, so surveying its Tier-2 siblings
before that gate is resolved would be work in the wrong order.

---

## 3. Financial-system regulators — OJK

OJK matters because Indonesia splits the central-bank mandate: BI owns monetary
policy and macroprudential, **OJK owns banking and capital-market supervision** and
publishes the bank-level data behind the credit cycle.

| Stream | URL | Cadence | Lang | Crawl | Tier | Built |
|---|---|:---:|:---:|:---:|:---:|:---:|
| Siaran Pers (ID) | `ojk.go.id/id/berita-dan-kegiatan/siaran-pers/Default.aspx` | ~weekly | id | direct GET | 1 | ✅ |
| Press Releases (EN) | same, `/en/` | ~weekly | en | direct GET | 2 | ✅ |
| Laporan Tahunan (annual report) | `ojk.go.id/id/data-dan-statistik/laporan-tahunan/Default.aspx` | annual | id | direct GET | 2 | ✅ |
| Statistik Perbankan Indonesia | `.../statistik-perbankan-indonesia/Default.aspx` | monthly | id | — | — | ❌ see below |

**Two gotchas, both cost a stream if missed:**

1. **The two mirrors disagree on date ORDER, not just month name.** `/id/` serves
   `9 September 2026` (D Month YYYY); `/en/` serves `August 31, 2026`
   (Month D, YYYY). Parsing only the first silently returned **zero** English rows.
2. **`list-group-item` is also the nav class** — ~370 menu entries per page. Rows
   are identified by the presence of `a.group-item-title`, which nav items lack.

**Statistik Perbankan Indonesia is not a Track B stream.** It renders a data-download
page with zero `a.group-item-title` nodes. It is a **Track A candidate** (bank-level
statistics as series) and is filed under § Track A follow-ups below rather than
carried here as a permanently-empty fetch.

⚠️ **OJK may have renamed its decision release too.** The Dewan Komisioner (Board of
Commissioners) monthly meeting result is classically "Hasil Rapat Dewan Komisioner
Bulanan", which `fetch_ojk.DK_TITLE` matches. But the 2026-09-07 release reads
"Kinerja dan Intermediasi Sektor Jasa Keuangan Terjaga Mendukung..." — which is
RDK-shaped in substance and does **not** match. Unresolved; see Open items.

### Not surveyed
LPS (deposit insurance) and IDX/KSEI/KPEI (market infrastructure) — Tier 2/3, no probes run.

---

## 4. Statistical agency — BPS

**BPS is the cautionary tale of this onboarding: the portal is unusable and the API
makes it irrelevant.**

`www.bps.go.id` sits behind a **Cloudflare interactive challenge** — every plain GET
returns HTTP 403, `cf-mitigated: challenge`, and a "Just a moment..." body. That
includes `/en/pressrelease` and `/en/release-calendar`. Scraping it would need
Playwright plus challenge-solving.

None of that is necessary. The **BPS WebAPI** at `webapi.bps.go.id` is not
challenged, uses the same free `IMDR_BPS_API_KEY` Track A already depends on, and
returns the press releases with body text **and** a PDF link in the listing row.
**So this fetcher makes no HTML request at all.**

| Model | Stream | Total | Cadence | Tier | Built |
|---|---|---:|:---:|:---:|:---:|
| `pressrelease` | BRS — the narrative behind CPI/GDP/trade | **1,904** | ~monthly batches | 1 | ✅ on |
| `publication` | yearbooks, methodology, sector reports | 5,898 | continuous | 2 | ⚪ opt-in |
| `news` | BPS activity news + joint statements | 823 | irregular | 3 | ⚪ opt-in |

Only `pressrelease` is on by default: it is the commentary accompanying every
headline print Track A already ingests as numbers. Enable the others with
`discover(include_optional=True)`.

**BPS paginates properly** — `data[0]` carries `{page, pages, per_page, count, total}`
and `/page/{n}/` works — so backfill to all 1,904 BRS is a matter of raising
`max_pages`. This is the only agency here where that is true.

### Two BPS gotchas

1. **Encoding.** The API sends UTF-8 but does not always say so; httpx then guesses
   Latin-1 and turns apostrophes into U+FFFD ("Indonesia?s exports"). Setting
   `r.encoding = "utf-8"` before reading `.text` is required, not cosmetic.
2. **The PDF URL is not identity.** Its `?f=` token is **re-signed on every request**,
   so the same document returns under a different URL each run. Using it as the dedup
   key made all 10 rows re-report as new every run. Identity is the synthetic
   `bps://{stream}/{brs_id}`; the volatile link rides in `pdf_url`. Pinned by
   `test_bps_row_to_item_uses_stable_id_not_volatile_pdf_url`.

### The release calendar is still a gap
`bps.go.id/en/release-calendar` is Cloudflare-gated and the WebAPI exposes no
calendar model. See Open items — this is the one item from the original source list
that neither track covers.

---

## 5. Debt management — DJPPR

The publisher behind Indonesia's govt-bond supply, so its press stream is the Tier-1
read for IndoGB: retail-sukuk offer windows, coupon resets, issuance-calendar changes,
rating actions.

| Slug | Stream | Rows | Cadence | Tier | Built |
|---|---|---:|:---:|:---:|:---:|
| `siaranpers` | press releases | **426** (full archive) | ~weekly | 1 | ✅ |
| `jadwallelang` | SBN issuance + debt-switch calendars | 26 | annual | 2 | ✅ |
| `sbnritel` | retail-SBN term sheets | 67 | per-series | 2 | ✅ |
| `hasillelangsuratberhargasyariahnegara` | SBSN auction results | 1 | **DEAD** | — | ❌ |

`siaranpers` returns the **entire 426-item archive in one response**, so DJPPR needs
no pagination at all.

### Three host gotchas

1. **Use the apex host.** `www.djppr.kemenkeu.go.id` fails TLS hostname verification
   (`CERTIFICATE_VERIFY_FAILED`). `djppr.kemenkeu.go.id` is fine.
2. **A missing slug answers HTTP 200** with `Data.Title == "404"` and a 2,305-char
   `PageContentLive`. Check the title, never the status code.
3. **The CMS disagrees with itself on field-name case.** `siaranpers` emits
   `@judul`/`@tanggal`/`@link`; the SBSN page emits `@Judul`/`@Tanggal`. Exact-case
   matching silently yields zero rows on half the pages — hence the
   case-insensitive `_field()` helper.

Slug discovery is **by probe only**: the nav is JS-assembled and the API payload
carries no hrefs, so there is no machine-readable route list.

### Per-auction results are not reachable
The SBSN results page resolves but is a **dead template**: one row, last updated
**12 January 2021**, carrying no link field. Its SUN (conventional bond) sibling
could not be found — ~25 slug spellings all returned the 404 shape. See Open items.

Not blocking: Track A already carries SBN ownership (`djppr_sbn_ownership`,
36 indicators) and BI SRBI auction yields as series, and DJPPR announces every
auction *outcome* that matters through `siaranpers`.

---

## 6-10. Categories not surveyed

The playbook asks for ten agency categories. Five were surveyed (§1-5). The rest are
recorded as **unprobed**, with the reasoning, rather than padded with unverified URLs:

| # | Category | Indonesian candidates | Tier | Why unprobed |
|---|---|---|:---:|---|
| 6 | Quasi-govt think tanks | LPEM-FEB UI, CSIS Indonesia, INDEF, LPPI | 3 | Para-public voice; Korea's KDI-class signal has no direct ID analogue with an official mandate |
| 7 | Fiscal council / legislative research | *none exists* | — | Indonesia has no NABO/PBO-equivalent independent fiscal institution |
| 8 | Market infrastructure | IDX (`idx.co.id`), KSEI, KPEI | 2 | Exchange notices; useful for equity/settlement colour, not macro policy |
| 9 | Pensions & SWF | BPJS, INA (Indonesia Investment Authority), Danantara | 2 | Allocation-flow signal; INA is young and discloses little |
| 10 | Other / cross-cutting | Kemenko Perekonomian, BKPM/Kementerian Investasi, Bulog (food prices) | 2-3 | Bulog is the most interesting (rice-price intervention feeds CPI) |

**Recommended next probe if Track B is extended: Bulog + Badan Pangan Nasional** —
Indonesia's CPI is unusually food-driven and administered rice prices are a policy
instrument, so the food-agency press stream has higher macro signal than the
remaining ministries.

---

## Crawl-pattern clustering

Indonesia needs **three** fetcher templates, not the five Korea needed. Mapped to the
playbook's shapes:

| Shape | Playbook analogue | Agencies | Transport | Module |
|---|---|---|---|---|
| **A — ASP.NET/SharePoint `.aspx` listing** | Shape 4 (DT-rendered list), non-gated | BI (10 streams), OJK (3) | plain httpx | `_bi_aspnet.py`, `fetch_ojk.py` |
| **B — JSON CMS page API** | *new for ID* — no Korea/AU analogue | DJPPR | plain httpx | `fetch_djppr.py` |
| **C — Official statistics WebAPI** | Shape 6 (data-portal) | BPS | plain httpx + key | `fetch_bps.py` |
| **D — SPA with undiscoverable API** | *new* — worse than any KR/AU shape | Kemenkeu | ❌ blocked | `fetch_kemenkeu.py` |

Shape A splits into two parsers because BI and OJK run different row markup on the
same CMS family — BI's `div.media.media--pers` vs OJK's `li.list-group-item`. They
are NOT interchangeable.

**No Playwright is needed for any built stream**, and none of the Korea-style
patient-retry TLS work applies: every reachable Indonesian edge behaves normally
(BI ~0.6s, DJPPR/BPS sub-second). `_http.patient_get` defaults to 4 attempts, not
Korea's 10.

---

## Per-agency body + PDF resolution recipes

Playbook § H.3 requires both paths per agency. Probed 2026-09-21:

| Agency | `body_text` | `pdf_bytes` | Resolver |
|---|---|---|---|
| **BI** | ✅ `#layout-page-content` | ⚠️ sometimes, `#layout-lampiran` | `resolvers.resolve_bi()` |
| **BPS** | ✅ `abstract` in the listing row | ✅ `pdf` in the listing row | none needed |
| **DJPPR** | ⚠️ repeater title only; detail page is SPA | ✅ `/media/{GUID}` links | none needed |
| **OJK** | ✅ `div.caption` (abstract) + server-rendered detail | ✅ direct `.pdf` hrefs | ⏳ not built |

BI is the only agency needing real HTML work. Measured on 11 consecutive releases
(seq 180-190, 3-17 Sep 2026): body text **821-5,006 characters**, the RDG statement
**14,413**. Clean anchors:

| Anchor | Carries |
|---|---|
| `#layout-title` | headline (strip the trailing "Siaran Pers" label) |
| `#layout-date` | exact publish datetime — **M/D/YYYY**, e.g. `9/17/2026 7:00 PM` |
| `#layout-page-content` | body |
| `#layout-lampiran` | attachments (where PDFs appear) |
| `#layout-sumber-data` | issuing department |

Two BI resolution gotchas:
- **Missing pages return HTTP 200** with full site chrome (~133,451 bytes,
  `<title>Bank Indonesia</title>`). `resolvers.is_missing()` tests for an absent
  `#layout-title` — structural, so it survives a template tweak that changes the
  byte count.
- **Zero-width characters.** BI's SharePoint rich-text fields are littered with
  ZWSP/ZWJ that survive `html.unescape` and wreck token counts. `_text()` strips them.

---

## Probe evidence (2026-09-21)

### BI pagination is a dead end — and that is how `?Kategori=` was found

Every route to page 2 fails from plain httpx:

| Attempt | Result |
|---|---|
| `?page=2`, `?Page=2`, `?Halaman=2`, `?PageIndex=2`, `?start=10`, `?Index=2`, `?p=2`, `?Tahun=2024` | page 1 unchanged, every time |
| `__doPostBack` to each of 5-7 `DataPager` targets, full hidden-input set echoed, **with** `X-MicrosoftAjax: Delta=true` | HTTP 200, 7 rows — **the same 7 rows** |
| same **without** the delta header | HTTP 200, 198 KB, 10 rows — but the **unfiltered** listing: the postback drops `?Kategori=` |
| SharePoint REST `/_api/web/lists` | **HTTP 401** (anonymous REST disabled) |

The consolation prize was decisive. On the reports listing the delta postback replied
with a `pageRedirect` to BI's own filter URL:

```
1|#||4|805|pageRedirect||%2fid%2fpublikasi%2flaporan%2fdefault.aspx
  %3fKategori%3dlaporan perekonomian%2claporan tahunan bank indonesia%2c...
  %26Periode%3dbulanan%2ctriwulan%2csemesteran%2ctahunan|
```

That payload is the source of the 21-category list in §1.2 and of `?Periode=`.
Neither is documented on the site.

**Consequence:** every BI/OJK fetcher is **page-1-only**. That is sufficient for a
daily pull (page 1 always holds everything published since yesterday), and because
`?Kategori=` narrows the reports listing to one family, page 1 of each category is
10 rows of a monthly-or-slower series — **1-3 years of history per stream with no
paging at all**.

### BI news releases ARE enumerable — the real backfill path

Detail URLs are `sp_{28}{seq}{yy}.aspx`: `28` is the Communication Department code,
`seq` the release number within the year, `yy` the 2-digit year. Release
"No.28/184/DKom" of 2026 is `sp_2818426.aspx`.

**The sequence is dense.** Verified 2026: seq 180-190 all resolve (157-162 KB each);
191+ return the disguised 404. So walking `seq` backwards is a complete backfill path
for BI news releases — the only way to reach BI's archive from plain httpx, given
pagination is dead. Implemented as `resolvers.probe_bi_sequence()`
(discovery/backfill only — **not** called by the daily pull; each hit is ~160 KB).

This is how the 2026-08-19 RDG statement was located after it proved absent from
page 1.

### Host reachability sweep

| Host | Result |
|---|---|
| `www.bi.go.id` | ✅ 200, ~0.6s, no gate |
| `webapi.bps.go.id` | ✅ 200, key-authenticated |
| `www.bps.go.id` | ❌ **403 Cloudflare challenge** (`cf-mitigated: challenge`) |
| `djppr.kemenkeu.go.id` + `api-djppr...` | ✅ 200 (apex host only — `www.` fails TLS) |
| `www.kemenkeu.go.id` | ⚠️ httpx gets the SPA shell; **Chromium blocked by corp firewall** |
| `ojk.go.id` | ✅ 200, server-rendered |

---

## Open items

Ordered by value, not by effort.

| # | Item | Impact | Next step |
|---|---|---|---|
| 1 | **Kemenkeu/MoF blocked** — APBN KiTa unavailable | Tier-1 gap: no fiscal narrative | 🚦 user verifies `www.kemenkeu.go.id` in their own browser (§2 gate) |
| 2 | **BPS release calendar** — Cloudflare-gated, no API model | Only original-list item neither track covers; would feed `calendar.cb_events` | Check whether TE/BQL already carry ID release dates before building anything |
| 3 | **Is OJK's RDK release renamed?** `DK_TITLE` may be matching nothing | Silently missing OJK's decision text | Resolve the 2026-09-07 detail page; widen `DK_TITLE` if confirmed |
| 4 | **DJPPR SUN auction results** — slug unknown, SBSN page dead since Jan 2021 | Per-auction detail; outcomes still arrive via `siaranpers` | Ask user to send the URL from their browser's nav |
| 5 | **BI archive backfill** — enumerator exists, never run at scale | 2026 only reaches seq 190; prior years unfetched | Run `probe_bi_sequence` per year, throttled, once Phase J is approved |
| 6 | **OJK detail resolver** not built | Only abstracts, not full body | Mirror `resolve_bi()` once OJK streams are promoted |
| 7 | **BI SEKI advance release schedule** not found as a structured page | Nice-to-have | Re-probe `bi.go.id/id/statistik/` |

### Track A follow-ups surfaced by this Track B pass

Not Track B work — recorded so they are not lost:

| Candidate | Cell | Note |
|---|---|---|
| **BI Prompt Manufacturing Index** — ✅ **BUILT 2026-09-21** (`bi_pmi`, 20 indicators) | 1.4 | **BI publishes its own PMI, free.** Verified live via `?Kategori=prompt manufacturing index` — quarterly, current to Q2 2026 (published 2026-07-17). [id_coverage_plan.md](id_coverage_plan.md) currently records Manufacturing PMI as ❌ "S&P Global / paid / use SKDU equiv"; that is true of the *monthly* S&P series but BI's quarterly index is a closer concept match than SKDU and costs nothing. Cell 1.4 is already ✅, so this deepens a sub-bullet rather than flipping a cell |
| **BI Survei Perbankan** — ✅ **BUILT 2026-09-21** (`bi_bank_survey`, 33 indicators) | 4.1 | A lending-standards survey — the cell the playbook flags as ❌ for most EM. Verified live, quarterly, current to Q2 2026 (published 2026-07-20). Distinct from SKDU (`bi_skdu_macro`), which is the *business* survey |
| **OJK Statistik Perbankan Indonesia** | 4.2 | Bank-level statistics; would deepen balance-sheet coverage beyond BI SEKI I.3/I.4 |

---

## Related

- [index.md](index.md) — Indonesia econ landing page
- [indonesia_indicator_inventory.md](indonesia_indicator_inventory.md) — Track A, 356 indicators
- [indonesia_govt_prod_pipeline.md](indonesia_govt_prod_pipeline.md) — Track B ops reference + go-live checklist
- [`../onboarding_new_country.md`](../onboarding_new_country.md) — the playbook (Phase H)
- [`../econ_to_prod.md`](../econ_to_prod.md) — Phase J promotion (**not entered**)
- [`../korea/govt_doc_sources.md`](../korea/govt_doc_sources.md) — the fully-promoted reference
- [`../australia/au_cb_documents.md`](../australia/au_cb_documents.md) — the discovery-shape reference
