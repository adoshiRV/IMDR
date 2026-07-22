# Onboarding a new research vendor — end-to-end workflow

This is the long-form playbook for adding a new sell-side research portal
(e.g. BNP Paribas Markets360, UBS Neo, SG Markets) to the IMDR research-
RAG system. The terse 7-step list in [`scrapers/index.md`](scrapers/index.md#add-a-new-vendor)
is the quick-reference; this doc is what to read the first time.

The pipeline a new vendor must plug into is described in
[`index.md`](index.md): discovery → discovery filter → classifier →
relevance filter → per-PDF pipeline (fetch / parse / hash / chunk /
upload / embed / write). Onboarding mostly means standing up stages 1–3
for the new vendor while reusing the existing stage 4+ infrastructure.

The phases below are deliberately ordered so each one is independently
shippable — we stop at the end of each phase, verify, then move on. Do
not skip ahead; the discovery API in phase 2 is what unlocks everything
downstream, and getting it wrong burns days.

**Phase 8 — Hard taxonomy probe + structured tightening** is run
**after** the vendor has ≥1 week of production ingest. It uses the
vendor's *own* listing-API taxonomy to replace title-string heuristics
with deterministic structured signals. Don't skip it — it's where the
real cleanup happens. The pattern is the same every time: spawn 3-4
parallel probe agents → find the vendor-native signal → ship five
edits (crawler / filter / classifier / cleanup / smoke) → docs + memory.
Run it once per vendor; expect 1-2 hours per vendor.

---

## Phase 0 — Decide whether to onboard

Quick gate before any code is written.

* Does the vendor have research that's relevant to our universe (macro,
  rates, FX, EM, commodities)? Single-name equity desks are mostly
  filtered out by [`relevance.py`](../../../playground/research/ingest/relevance.py) —
  if that's all the vendor publishes, skip.
* Do we have credentials? Check `.env` for an `IMDR_RESEARCH_<VENDOR>_*`
  triplet (`URL`, `USERNAME`, `PASSWORD`). If not, ask the user before
  starting — credentials usually require requesting a research seat
  from the bank.
* Is the portal MFA'd in a way that breaks automation? Email-based MFA
  is fine (we just log in interactively once into a persistent profile).
  Hardware-token MFA every session is a blocker — flag and stop.

Add an entry to [`playground/research/vendors.yml`](../../../playground/research/vendors.yml)
with `profile_status: probe` to record what we know so far. Do this
even if we're not yet committing to onboarding — the audit is the seed
for the eventual `src/imdr/vendors/research/` registry.

---

## Phase 1 — Explore-only

**Goal**: log into the portal interactively, capture enough snapshots to
understand the URL/DOM/API patterns. No crawler code yet.

1. **Add the explorer wrapper**:
   `playground/research/explore_<vendor>.py` — a ~10-line file that
   calls `portal_explorer.explore(vendor_code, portal_url)`. Copy
   [`explore_anz.py`](../../../playground/research/explore_anz.py) and
   adjust the constants. The wrapper is intentionally trivial; all the
   capture logic lives in [`portal_explorer.py`](../../../playground/research/portal_explorer.py).

2. **First interactive run**. From a terminal that can pop a Chrome
   window:

   ```powershell
   C:/Users/adoshi/.conda/envs/imdr/python.exe playground/research/explore_<vendor>.py
   ```

   The persistent profile lives at
   `C:/IMDR_LOCAL/research_profiles/<vendor>/`. On first run it's empty —
   sign in interactively, complete any MFA. Subsequent runs reuse the
   cookies; no re-auth needed unless the vendor times the session out.

3. **Capture snapshots**. Press Enter in the terminal at each of these
   states:
   * Post-login landing page.
   * The listing / hub feed (chronological recent reports).
   * One report open in the viewer (note: the viewer URL is usually
     **not** the PDF URL — see phase 2).
   * Any search-results page.
   * Anything that looks like an admin/non-PDF tile (invites,
     conference calls, podcasts).

   Output lands in `playground/research/<vendor>_explore/`:
   * `screenshots/` — full-page PNGs.
   * `pages/` — raw HTML when < 2 MB.
   * `snapshots.jsonl` — structured index with title + URL.

4. **Snapshot review**. Open the HTML files and look for:
   * URL patterns — do report URLs share a prefix? Is there a UUID/ID?
   * Network requests — does the SPA load listing data via XHR? (Use
     Chrome DevTools' Network tab during the live session; the
     explorer captures HTML but not network logs.)
   * Login domain — note the SSO host (e.g. `sso.sgmarkets.com`).

5. **Document scope in `scrapers/<vendor>.md`** (stub it now, fill in
   as we learn more): portal hostname, login URL, MFA notes, observed
   URL patterns, gut estimate of daily volume. See
   [`scrapers/anz.md`](scrapers/anz.md) for the canonical structure.

**Stop here, sanity-check with the user.** Phase 2 commits to a
discovery strategy; getting alignment now prevents wasted scraping
work.

---

## Phase 2 — Find the listing API (do this before DOM-scraping)

**Hard rule** — never start with DOM scraping. We learned this the
hard way: switching Goldman Sachs from DOM to API took daily counts
from 6 to 1013; Morgan Stanley from 14 to 579. The cost of finding
the API first is one script's worth of effort; the cost of skipping
it is missing 95% of the publications. See feedback memory
`feedback_research_listing_api_discovery.md`.

1. **Probe**. Add the vendor to
   [`playground/research/probe_listing_apis.py`](../../../playground/research/probe_listing_apis.py)
   and run it against the listing/hub page. The probe sniffs every
   JSON XHR fired during page load + scroll and scores each for
   "looks like a listing" (UUID counts, listing-key field names like
   `reports`/`publications`/`documents`/`results`, body size).

2. **Inspect the top candidates**. The highest-scoring API is almost
   always the right target — but not always. We've seen page-config
   blob endpoints (AEM `*.model.json`) outscore the real listing API
   because they happen to embed many UUIDs. **Read the response body
   before assuming**: real listing APIs return per-doc metadata
   (title / publish_date / authors / classification); page-config
   blobs return widget layout. Pick the one with per-doc metadata.
   Capture:
   * Request method + URL + path params.
   * Body shape — four families we've seen:
     - **REST POST + facets DSL** (Goldman: `POST` JSON with
       `facets/language/page/size/sort`).
     - **REST GET + cursor** (ANZ: `GET` with `param_limit` +
       `position`).
     - **Elasticsearch DSL** (Nomura: `POST` body is a literal ES
       query).
     - **GraphQL** (`POST` to a `/graphql` or `/query-v2` endpoint
       with `{operationName, query, variables}`). For GraphQL,
       capture the **full query string verbatim** from the SPA
       request body — even if it contains redundancies (e.g.
       duplicate variable declarations). The server tolerates the
       captured shape; "cleaning it up" risks server-side
       validation regressions on future runs.
   * **Headers**, not just body. Sniff the request headers for
     SPA-injected custom values — `janus_user: <username>`,
     `x-csrf-token: ...`, `x-tenant-id: ...` are all real patterns
     we've seen. The server may validate them. Thread these into
     the crawler from `.env` (do **not** hard-code) and send them
     on every API call.
   * Whether responses contain enough metadata to skip a per-uuid
     follow-up (Goldman/Nomura yes; MS needs a `/frontmatter?uuid=…`
     call for the PDF URL).
   * Page size — push it as high as the server allows. 200 is a safe
     baseline; 500–1000 has worked for some. Some servers cap silently
     and just return the first N; check by comparing `len(results)`
     against the page-size requested.

3. **Figure out the PDF URL**. Two patterns we've seen:
   * **Deterministic from UUID** — Goldman swaps `.html` → `.pdf`;
     Nomura builds `go.nomuranow.com/research/japi/publication/{id}.file`.
     Cheapest fetch.
   * **One extra GET** — MS hits a frontmatter API to retrieve
     `pdfRenditionUrl`. Adds one round-trip per report.
   * **Viewer redirect chain** — ANZ-only so far. The "PDF URL" is
     an HTML page that JS-redirects to a signed S3 URL. Handled by
     `fetch.py`'s slow path. Avoid this if there's any alternative —
     it's ~5x slower per fetch.

4. **Confirm with a curl-style call**. From a Playwright REPL inside
   the persistent-profile context, `ctx.request.get(...)` / `.post(...)`
   the listing endpoint. Confirm the response is JSON, paginated, and
   returns recognisable report metadata.

5. **Document the API** in `scrapers/<vendor>.md` (full request/
   response shape, page-size limits, early-stop strategy). This is the
   single most valuable section of the doc — future you will need it
   when the vendor changes their API.

**Stop here, decide pattern in `scrapers/index.md`'s "Common patterns"
table** (firehose-A, direct-PDF-B, viewer-redirect-C). If a new
pattern, add a sub-section.

---

## Phase 3 — Build the crawler

`playground/research/ingest/crawler_<vendor>.py`. Returns
`list[ReportRef]` from the listing API. Pattern:

```python
def discover_reports(
    ctx: BrowserContext,
    since: date,
    limit: int | None = None,
) -> list[ReportRef]:
    ...
```

Conventions (see existing crawlers under
[`playground/research/ingest/`](../../../playground/research/ingest/)):

* **Session-prime before the first POST**. Many SPAs only set the
  full auth state (session cookie + CSRF + per-user tokens) after
  the JS bundle finishes booting. A bare `page.goto(...,
  wait_until="domcontentloaded")` is usually **not enough** — the
  first listing-API call from a freshly-spawned context returns
  401/405/302-to-login because the SPA hasn't yet plumbed in the
  state the server expects. Add both:
  ```python
  await prime.wait_for_load_state("networkidle", timeout=20000)
  await prime.wait_for_timeout(5000)   # extra settle
  ```
  Then close the prime page and start your API calls.
* **Paginate** until `oldest-in-page < since` (early stop). Don't
  fetch the whole archive every run.
* **Use the persistent profile cookies** via `ctx.request.get/post`,
  not a fresh `requests.Session`. That's how the listing API
  authenticates.
* **Dedupe inside the run** — some listing APIs return overlapping
  pages.
* **Construct PDF URL during discovery**, not at fetch time — keep
  the per-PDF stage stateless.
* **Drop non-PDF refs at parse time**. Most vendors' listing APIs
  return a mix of formats — PDF, Excel/CSV (data products), video
  (Kaltura/FLV), audio (podcasts), HTML-only (web-native articles).
  The shared `parse.py` is PDF-text only. Filter for
  `application/pdf` (or the vendor's equivalent) in the listing
  response's `documentFormats` / `mimeType` field, and **count the
  drops with a clear label** — `no_pdf=NN` not `unparseable=NN`.
  "Unparseable" suggests broken content; the reality is "wrong
  format for a prose RAG". Document the actual format distribution
  in `scrapers/<vendor>.md` so future-you knows what's behind the
  drop count.
* **Drop publisher-flagged non-research at the crawler stage**.
  Many vendors ship per-doc flags that are cleaner signals than
  title-regex matching: `isResearch=N`, `documentType=Video`,
  `productCategory=Podcast`, `audienceType=Internal`. Match these
  in `_parse_doc` (or just after) and log a `[DROP] <uuid> <reason>
  <title[:60]>` line per item so the operator can audit volumes.
  These belong in the crawler, not in `filters/<vendor>.py`
  (which handles title-prefix patterns).
* **Locale-safe date parsing**. Vendors ship `publish_date` in many
  formats — epoch milliseconds (Goldman), ISO (BNP), RFC-822-ish
  ctime strings (`"Wed May 27 17:27:27 UTC 2026"`, JPM).
  `datetime.strptime("%a %b %d ...")` is **locale-aware** and breaks
  on non-en_US systems. Hand-roll a parser with a month-name dict or
  use `email.utils.parsedate_to_datetime` (RFC-strict only).
  `dateutil.parser.parse` works too but adds a dependency.
* **Return `ReportRef`** with `uuid`, `title`, `publish_date`,
  `pdf_url`, `vendor_code`, plus any vendor-specific metadata fields
  the classifier will consume (analysts, business_group, tickers,
  content_types, etc.). Use a frozen dataclass with slots, not a
  dict, so the contract is typed.

Test the crawler in isolation:

```python
# Quick REPL test:
from playground.research.ingest.crawler_<vendor> import discover_reports
# wire up a Playwright context, then:
refs = discover_reports(ctx, since=date.today() - timedelta(days=1))
print(len(refs), refs[:3])
```

If counts look reasonable vs the portal's UI (within ~10%), move on.

---

## Phase 4 — Discovery filter + classifier

Both run pre-fetch, so cheap-to-build but high-leverage.

### 4a. Discovery filter — `filters/<vendor>.py`

`should_exclude(ref: ReportRef) -> tuple[bool, str]`. Returns `(True,
reason)` to drop admin/logistics posts before they're fetched.
Common reasons:

* Title prefix matches `invite:`, `webcast:`, `conference call:`.
* Publication type is `Podcast`, `Video`, `5 in 5` (ANZ).
* Doc class is `marketing` not `research` (rare; mostly title-based).

Logs as `[SKIP] <vendor>: <title> — reason='<reason>'`. See
[`filters/anz.py`](../../../playground/research/ingest/filters/anz.py)
for the shape.

**Tune empirically, not pre-emptively.** Ship the file with an empty
`EXCLUDED_TITLE_PREFIXES = ()` tuple if you haven't seen the vendor's
admin-title patterns in real data. Run 3 days of discovery first,
then populate the tuple based on the `[DROP]` log lines and audit
output. Pre-populating from guesswork (other vendors' patterns)
risks false positives on real research.

### 4b. Classifier — `classifiers/<vendor>.py`

`classify(ref: ReportRef, raw_metadata: dict) -> ClassifyResult`.
Maps the vendor's classification fields to IMDR's taxonomy:

* `asset_class` — `macro`, `rates`, `fx`, `credit`, `equity`,
  `commodities`, `multi-asset`.
* `country_code` / `region` — ISO 3166 country, or `EM`, `DM`,
  `APAC`, etc.
* `tags` — ticker / region / discipline / `vendor_pubtype`.
* `context` — short text blob (the title plus any 1-line summary
  the vendor provides). Used as a tag-friendly RAG payload.

The classifier runs **twice** in the pipeline (once for the
relevance filter, once at write-time) so it must be deterministic.
No DB / network calls. Pure function over `(ref, raw_metadata)`.

The classifier output is what
[`ingest/relevance.py`](../../../playground/research/ingest/relevance.py)
uses to drop single-name equity research by default — make sure
single-name equity reports get tagged accurately so the filter can
catch them.

**Asset-class blanket drops with a keep-allowlist.** When a vendor
publishes high-volume content in a domain we mostly don't want
(e.g. one bank's equity stream is 50%+ of its raw output), don't
blanket-drop everything in that asset class — you'll lose the
macro-flavored equity subset (cross-asset positioning, regional
market wraps, top-down sector strategy). The right pattern is a
**vendor-specific branch in `relevance.py`** that drops the asset
class **unless** the title matches a keep-allowlist regex (e.g.
``strategy|portfolio|positioning|monthly|outlook|cross-asset|...``).
See the JPM branch in
[`is_single_name_equity()`](../../../playground/research/ingest/relevance.py)
for the template. Single-name (n_tickers==1) always drops regardless
of the allowlist match.

---

## Phase 5 — Wire the runner

**The orchestrator is the canonical path.** Wire your new vendor
into [`playground/research/ingest_today.py`](../../../playground/research/ingest_today.py)
— specifically its `_load_vendor_registry()`. Two-line change:

```python
from ingest.crawler_<vendor> import discover_reports as <vendor>_discover
...
"<vendor>": VendorSpec(code="<vendor>", discover=<vendor>_discover),
```

Plus register the classifier in
[`ingest/classifiers/__init__.py`](../../../playground/research/ingest/classifiers/__init__.py)
(`_VENDOR_CODES` + the dispatcher branch) so
`get_classifier("<vendor>")` resolves.

**Why orchestrator-first**: the orchestrator
(`ingest_today.py`) **threads classifier output into `ReportMeta`**
— `asset_class`, `country_code`, `tags`, `context` all populate
`research.dim_report` and `research.map_report_tag` automatically.
The legacy per-vendor `ingest_today_<vendor>.py` shims do **not**
do this — they pass `asset_class=""` and an empty `meta.tags`, so
the classifier output is computed (for `apply_relevance_filter`'s
single-name check) then thrown away. Existing rows written via
the standalone path show up in the DB without `asset_class` /
`context` / tags. See the JPM backfill case below for the cleanup
pain that creates.

**When to also build a standalone `ingest_today_<vendor>.py`**:
basically never. The orchestrator supports `--vendors <code>` for
isolated runs. If you absolutely need a single-vendor shim (e.g. a
non-standard fetch path like BNP's pre-fetched PDFs), make it a thin
wrapper that calls the same `ingest_one` and passes the
classifier-enriched `ReportMeta`. Do not copy the legacy
`asset_class=""` template — that's the trap.

---

## Phase 6 — DB seed + first smoke run

1. **Seed `dim_vendor`** if the row doesn't exist:

   ```sql
   INSERT INTO dbo.dim_vendor
       (vendor_code, display_name, vendor_type, is_active, created_at)
   VALUES
       ('<vendor>', '<Display Name>', 'web', 1, SYSUTCDATETIME());
   ```

   `dim_vendor.vendor_code` is the FK target for `research.dim_report`.
   Check first — most vendors are already seeded from other domains.

2. **Smoke run with embed off**:

   ```powershell
   $env:IMDR_RESEARCH_EMBED = "false"
   $env:IMDR_RESEARCH_LIMIT = "3"
   C:/Users/adoshi/.conda/envs/imdr/python.exe playground/research/ingest_today_<vendor>.py
   ```

   Confirms discovery, filter, fetch, parse, hash, chunk, DB write
   work end-to-end on a tiny sample. Expect 3 PDFs in OneDrive, 3
   rows in `research.dim_report`, N rows in `research.fact_chunk`.

3. **Embed-on smoke** — drop the limit, turn embed on:

   ```powershell
   $env:IMDR_RESEARCH_EMBED = "true"
   Remove-Item Env:IMDR_RESEARCH_LIMIT
   C:/Users/adoshi/.conda/envs/imdr/python.exe playground/research/ingest_today_<vendor>.py
   ```

   First full-day run. Save the log under
   `playground/research/_ingest_today_<vendor>_<YYYY-MM-DD>.log`.

4. **Audit the discovered set before promoting**. Write
   `smoke_<vendor>_audit.py` — re-discover + classify a few days
   of output and print:
   * `asset_class` distribution (% per bucket; flag if `(empty)` is >5%).
   * Drop reasons + counts (`[DROP]` lines).
   * Title-keyword scan for **podcast / replay / webcast / audio /
     reminder** patterns — should be `0` hits after the
     publisher-flag drops in Phase 3. If anything leaks through,
     either the crawler's hard-flag list is incomplete or the
     vendor uses a flag we haven't sniffed.
   * Sample titles per asset_class bucket so the operator can
     eyeball whether the classifier is mapping correctly.
   See [`smoke_jpm_audit.py`](../../../playground/research/smoke_jpm_audit.py)
   as a template — adapt it per vendor.

5. **Spot-check retrieval — harnessed**:

   ```powershell
   C:/Users/adoshi/.conda/envs/imdr/python.exe playground/research/smoke_<vendor>_retrieval.py
   ```

   Add a `smoke_<vendor>_retrieval.py` that wraps
   [`retrieve.py`](../../../playground/research/retrieve.py) with
   3 vendor-flavored queries (`--vendor <code> --k 3`) and exits
   non-zero if any returns zero hits. Mechanical sanity check for
   "did the new vendor's chunks make it into Qdrant?" Run after
   every embed-on full-day pass for the first week.
   See [`smoke_jpm_retrieval.py`](../../../playground/research/smoke_jpm_retrieval.py)
   as a template.

6. **If your first smokes used a legacy standalone runner**:
   the rows already in `dim_report` will have empty
   `asset_class` / tags / context (per the Phase-5 trap above).
   Idempotency on `content_hash` means a re-run through the
   orchestrator will hit `[DUP]` and **not** enrich the existing
   rows. You need a **one-off backfill script** —
   `backfill_<vendor>_meta.py` — that:
   * Pulls the unenriched rows (`asset_class IS NULL OR = ''` for
     the new vendor).
   * Re-discovers refs for the same date window via the crawler.
   * Matches each DB row to a discovered ref by
     `(title, publish_date)`.
   * Runs the classifier on the matched ref.
   * `UPDATE`s `dim_report.{asset_class, country_id, context}`
     and `INSERT`s into `map_report_tag` (with dedup).
   See [`backfill_jpm_meta.py`](../../../playground/research/backfill_jpm_meta.py).
   Idempotent — re-runs are no-ops once `asset_class` is set.

---

## Phase 7 — Document + register

1. **Finalise** `docs/admin/research/scrapers/<vendor>.md` — fill in
   every section: portal, profile, URL patterns, fetch strategy,
   listing API, watermarks, quirks, daily volume observed, last
   verified date.

2. **Add a row** to the "Vendors" table in
   [`scrapers/index.md`](scrapers/index.md). Mark `live` once the
   smoke run produced ≥1 day of clean ingest.

3. **Update the daily-volume table** in
   [`index.md`](index.md#pipeline) once we have 24h of data. The
   table reflects what survives each gatekeeper.

4. **Promote `vendors.yml`** — flip `profile_status` from `probe` to
   `production`.

5. **(Optional) Schedule** the daily run by adding the vendor to
   `scripts/imdr_daily.py` if production code has moved out of
   `playground/`. Currently all research lives in `playground/` —
   leave the scheduler hook for the promotion-to-`src/imdr/` cleanup.

---

## Phase 8 — Hard taxonomy probe + structured tightening

A new vendor reaches Phase 7 with a "working but loose" ingest:
title-prefix filter only, classifier off whatever publication-type
table you hand-curated, and country/region coverage that's whatever
the listing surface happens to expose. **Phase 8 is the
vendor-native-signal pass** that tightens this loop using the
listing API's *own* taxonomy fields rather than your title regex.

Run Phase 8 after the vendor has ≥1 week of production ingest. The
DB audit gets meaningful, the smoke window is real, and the drift
between "what we ingest" and "what the desk publishes" is visible.

Pattern proven 2026-06-02→03 across JPM / MS / Goldman / BNP / ANZ /
Westpac. Each vendor took 1-2 hours from probe start to docs-
committed. See per-vendor memory entries linked below.

### Phase 8.1 — Spawn 3-4 parallel agents

The probe has independent strands; run them concurrently:

| agent | task |
|---|---|
| **Explore — current stack** | Read crawler / filter / classifier / scraper-doc / explore script / smoke logs. Identify which API fields we parse vs ignore. Cite file:line. |
| **imdr-dbm — DB audit** | Use `mcp__imdr-db__query` SELECTs. Count NULL/empty/non-canonical asset_class. Single-name leakage. Encoding corruption. Country/region tag coverage. Format leakage (podcast/video/chart-pack titles). Save to `playground/research/taxonomy_probe/<vendor>_db_audit.md`. |
| **general-purpose — hard probe** | Read crawler + probe artefacts. Enumerate **every** key on the listing response (not just the ones we map). Identify vendor-native taxonomy: assetClass / region / single-name / format / pubtype enums. Stage a read-only probe at `playground/research/probe_<vendor>_full.py`; execute only if metadata-only (no PDFs, no DB writes). Save to `playground/research/taxonomy_probe/<vendor>_full.md` + JSON dumps. |
| **Explore — Deepak cross-check** | Only if `Z:\Business\Personnel\Arjun\playwrights\<vendor>-playwright\` exists. READ the on-disk Chrome profile (Bookmarks, History — do NOT launch the browser). Save URL/hub visit distribution to `<vendor>_deepak.md`. Skip if no profile. |

Brief each agent like a smart colleague — file paths, what to read,
what shape the report should take. Reserve full prompts for findings
docs; the agent results come back into the main context as compact
summaries.

### Phase 8.2 — Find the vendor-native taxonomy signal

Every vendor we've audited has one. The pattern is **always**:
a top-level structured field (or array of structured tags) carrying
the desk's own asset-class / region / format / single-name
enumeration. Confirmed analogues:

| vendor | the signal |
|---|---|
| JPM | bare-scalar `regions` / `assetClasses` / `sectors` / `countries` in the GraphQL result (added via field projection) + `businessGroup` drop |
| MS | `cinfo.srcinfo` / `cinfo.ptcinfo` (single-name) + frontmatter `region` + `topicHeadline` → ASSET_CLASS_LEVEL2 map (from `lookupall/allbylanguagecode`) |
| Goldman | `aemTags[]` (19 axes) — `productFocus=Issuer` is the single-name signal; `girAssetTypes` is the FICC-aware asset-class; `subjects` for Macro/Micro |
| BNP | `tags.quantModels` non-empty (chart-pack) + `tags.assetClasses` (already used as Tier-0) |
| Barclays | `pubSeriesInfo.assetClassInfo` + `eqSecurities[]` count + 28-type `tags[]` |
| ANZ | `tile-tags` `[Sub-Topic, Topic]` pair (unlock with `param_layout=full` — was stripped at `wide`) |
| Westpac | `invRecommParentTag` (Currencytickers / swapsau / commoditytickers / credittickers / …) + `invRecommSubCategoriesTag` (Bloomberg tickers) |

**If you can't find a vendor-native signal in 30 minutes of probe,
the vendor probably doesn't have one** — fall back to a tighter
title/pubtype rule set and document the gap. Most vendors do
expose one; it's just buried (Goldman's `aemTags` resolve via the
same response's `facetList`; ANZ's tags only exist at the
`layout=full` URL parameter).

### Phase 8.3 — Ship five edits (A-E)

This is the same five-step package every time:

| step | file | what changes |
|---|---|---|
| A | `crawler_<vendor>.py` | Parse the new structured fields onto `ReportRef`. Keep existing fields verbatim — additive only. If the signal is GUID-based, resolve to human names at parse time (Goldman pattern). If the response carries a facet dictionary in the same body, build the lookup once per crawl. |
| B | `filters/<vendor>.py` | Add structured drops layered **before** existing title rules. Standard precedence: format flags (audio/video booleans) → format strings (file path slug, doc type) → non-research source (allow-list) → single-name (focus/cinfo/issuer/ticker count) → vendor-specific drop (chart-pack model, discontinued pubtype, etc.) → legacy title-prefix. First match wins. |
| C | `classifiers/<vendor>.py` | New Tier-0 from the structured signal → canonical asset_class. Keep existing logic as Tier-1 fallback. Surface country/region from the new fields if present. Emit any Bloomberg tickers / industry tags. |
| D | `cleanup_tier1_junk.py` | Add a bucket per vendor for the historical leakers the new rules now catch (non-canonical asset_class rows, format leaks, single-name leaks). DELETE-only (the new ingest will re-discover them and re-drop cleanly). Skip if DB is empty for this vendor. |
| E | `smoke_<vendor>_7day.py` | Mirror `smoke_anz_7day.py` / `smoke_bnp_7day.py`: per-day discovered/kept, structured-field coverage, drop reason breakdown with 5 samples each, kept asset_class/region/country distribution, sample titles per class. |

Do A→E in order. Each step should compile cleanly before the next.

### Phase 8.4 — Sanity-test on real probe data

Before running the 7-day smoke, validate the parser + filter +
classifier against actual cards from the probe sample:

```python
# Pull a real card from playground/research/taxonomy_probe/<vendor>_full_sample.json
# Run it through the crawler's tile parser (or whatever extracts ReportRef-shaped dicts)
# Then through filter.should_exclude(...)
# Then through classifiers.<vendor>.classify(...)
# Assert: filter precedence is correct (drop reasons fire on the right cases),
#         classifier resolves the right asset_class on 4-6 representative samples.
```

This catches off-by-one regex bugs (e.g. unquoted `class=tag`
attribute on ANZ, `'true'` string instead of bool on Westpac
`hideArticle`, `australian` vs `australia` substring mismatches)
before you spend 10 minutes on a smoke that's broken at parse time.

### Phase 8.5 — Run the 7-day smoke

```bash
C:/Users/adoshi/.conda/envs/imdr/python.exe \
    playground/research/smoke_<vendor>_7day.py \
    > playground/research/taxonomy_probe/<vendor>_smoke_7day.log 2>&1
```

Read the log end-to-end. Key things to check:

1. **Hub coverage** — did all configured hubs return cards?
2. **Discovery drop reasons** — do the counts look right? Spot-check
   the 5 sample titles per reason; if any look legit (i.e. a real
   macro brief got dropped as a chart-pack), the rule is too tight.
3. **Relevance kept ratio** — JPM/MS/Goldman/BNP/ANZ/Westpac all
   landed at 99-100% kept *post-discovery* once tightening was
   complete. If your vendor is below 90%, either the classifier is
   leaking sector EQUITY into the relevance path (loosen Tier-0 to
   catch more) or the relevance default-drop is firing on legit
   content (consult `relevance.py` vendor branches).
4. **Asset-class composition** — should be **macro/rates/fx/
   credit/commodities-dominated**, with EQUITY ≤ 10% (sector-only)
   and zero junk classes.
5. **Country/region coverage on survivors** — should be ≥ 60%
   after Phase 8. If lower, the vendor signal probably exposes
   country and you're not extracting it.

Iterate if needed — a v1 smoke that exposes a bug + v2 fix is
normal. Westpac and ANZ both needed a one-line fix between v1 and
v2 (`Blue Lens` over-drop on ANZ; nothing material on Westpac).

### Phase 8.6 — Apply the vendor-specific posture

User instruction *"GET ALL and full deep coverage, no single-name
equity/credit, trends ok"* (2026-06-03) becomes per-vendor:

- **MS**: strict drop on EQUITY (no Macro-subject equivalent on MS,
  sector wraps are mostly noise). See
  `memory/feedback_ms_strict_sector_equity_drop.md`.
- **Goldman**: strict drop default with a narrow allowlist —
  `Macro` subject tag OR title matches
  `strategy|portfolio|cross-asset|allocation|outlook|thematic|
  positioning|earnings season|global research`. See
  `memory/feedback_goldman_tightening.md`.
- **BNP**: strict drop on any `quantModels` non-empty (chart-pack
  signal). See `memory/feedback_bnp_strict_quantmodels.md`.
- **ANZ**: no equity in vendor taxonomy → no decision needed. See
  `memory/feedback_anz_layout_full.md`.
- **Westpac**: drop on `credittickers` parent (single-name credit);
  keep all other `invRecomm` parents. See
  `memory/feedback_westpac_three_hubs.md`.

If a vendor's relevance branch needs a `_<VENDOR>_EQUITY_KEEP`
title-regex allowlist, model it on `_JPM_EQUITY_KEEP` /
`_GS_EQUITY_KEEP` / `_DB_EQUITY_KEEP` in
`playground/research/ingest/relevance.py`.

### Phase 8.7 — Docs + memory + commit

1. **Update `docs/admin/research/scrapers/<vendor>.md`** — append
   a "Hard taxonomy probe + tightening (`<date>`)" section with:
   probe links, key win (the single sentence: what signal we
   started using), filter precedence table, classifier Tier-0
   table, DB audit summary, 7-day smoke result, any vendor-specific
   posture trade-off.
2. **Add a `memory/feedback_<vendor>_<rule>.md` file** if there's a
   sticky vendor-specific decision (strict-equity-drop, structured
   chart-pack rule, weird HTML quirk, etc.) — future sessions need
   to see it before they touch the filter again.
3. **Index it in `MEMORY.md`** with a one-line hook.
4. **Commit docs only** (`docs/admin/research/scrapers/<vendor>.md`).
   Code stays in gitignored `playground/`. Commit message format:
   ```
   research/<vendor>: <key-win> + Tier-0 + 7-day smoke

   Doc-only update capturing the <date> <vendor> probe pass. Code
   stays in gitignored playground/.

   What landed in <vendor>.md:
   - Hard taxonomy probe — <key signal + count of distinct values>
   - Filter precedence — <new drop reasons>
   - Tier-0 classifier — <signal → canonical map>
   - DB audit — <count of leakers + buckets cleaned>
   - 7-day smoke — <kept/day> kept, composition <top classes>
   - <Posture decision> — <accepted vs. tightened, with rationale>
   ```

### Phase 8 anti-patterns

- **Don't write filter rules from probe-agent guesses alone.**
  Agent-3 reports often over-classify legitimate content as drop
  candidates (ANZ `Blue Lens` was a real macro brief, not internal
  collation). Always cross-check the dropped-titles sample from
  the smoke before trusting an enum-based drop.
- **Don't commit code to git.** Research stays in
  `playground/research/` — gitignored. Only the docs commit.
- **Don't ship without running the smoke.** The smoke is the
  forcing function that surfaces parse bugs, false-positive drops,
  and integration issues. If it didn't run cleanly end-to-end,
  the changes aren't done.
- **Don't add `EQUITY` to the relevance default-keep set.** Per
  the user's instruction (2026-06-03 and prior), the macro/rates/
  fx/credit/commodities stream is the goal. EQUITY survives only
  with vendor-specific allowlists (Macro-subject, cross-asset
  title keywords) — never as default-keep.
- **Don't loosen a vendor branch in `relevance.py` without checking
  the memory entry first.** Each strict-drop decision is documented
  in `memory/feedback_<vendor>_*.md` with the rationale. Loosening
  re-opens the noise we already paid to filter out.

---

## Cross-cutting rules

These apply to every research vendor — review before phase 1:

* **Playground-only**: every script in this workflow lives under
  `playground/research/`. Production code lives in `src/imdr/` and is
  promoted in a separate cleanup pass. See feedback memory
  `feedback_playground_only_for_exploration.md`.
* **SharePoint scope**: PDFs go to OneDrive-synced
  `Trade Knowledge Core - IMDR\…`. Never write outside that folder.
  See feedback memory `feedback_sharepoint_research_scope.md`.
* **No anti-detection**: never add stealth plugins, automation-
  hiding Chrome flags, or aggressive parallelism on a vendor portal.
  Risks account suspension. See feedback memory
  `feedback_no_anti_detection_research.md`.
* **Login pages → navigate to the protected URL**, never override
  with login-form hacks. If discovery hits a login screen, `goto()`
  the post-login URL directly and let SSO redirect through. If it
  fails, stop (don't evade). See feedback memory
  `feedback_login_navigate_protected_url.md`.
* **Tests + pinned error messages**: every module that lands in
  `src/imdr/` (post-promotion) needs unit tests with exact error-
  string assertions. During the playground phase, tests are
  optional but encouraged for the crawler's parsing logic. See
  feedback memory `feedback_always_write_tests.md`.

---

## Common pitfalls

These are the traps we've actually fallen into. Read once before
starting; refer back when something is misbehaving.

1. **Confusing labels in crawler logs.** "Unparseable" sounds like
   parse failure but in practice is almost always "no PDF rendition
   advertised by the vendor" — i.e. the doc is an Excel/CSV/video/
   audio/HTML asset, not a broken PDF. Name the counter for the
   actual condition (`no_pdf`, `wrong_format`) — operators read these
   logs and the labelling drives the wrong investigation.
2. **The first listing-API POST returns 405 / 401 / a redirect to
   login.** The persistent profile's cookies are valid, but the SPA
   hasn't booted yet so the per-request token isn't bound. Fix is
   always the same: `wait_for_load_state("networkidle")` +
   `wait_for_timeout(5000)` after the session-prime `goto()`. See
   Phase 3.
3. **The highest-scoring probe response isn't always the listing
   API.** AEM page-config blobs (`*.model.json`) score high on UUID
   counts but return widget layout. Always read the response body
   before committing to an endpoint.
4. **Locale-sensitive date parsing breaks on non-en_US systems.**
   `strptime("%a %b %d ...")` localises month + day-of-week names.
   Hand-roll with a month dict; don't trust the system locale.
5. **The classifier output is silently discarded when using the
   legacy standalone runner pattern.** `apply_relevance_filter`
   uses the classifier output internally, then the legacy
   `ingest_today_<vendor>.py` builds `ReportMeta` with
   `asset_class=""` — so nothing classifier-side reaches
   `dim_report`. **Use the orchestrator** (`ingest_today.py`),
   not a copy-pasted standalone shim.
6. **`content_hash` idempotency is one-way.** Once a doc is in
   `dim_report` with empty meta, re-running won't enrich it — the
   write skips with `[DUP]`. Plan a one-off `backfill_<vendor>_meta.py`
   if your early smokes used the legacy path. See Phase 6 step 6.
7. **Vendor-injected custom headers.** Sniff request headers, not
   just body. Patterns like `janus_user: <username>`, `x-csrf-token`,
   `x-tenant-id` may be silently required. Thread from `.env`.
8. **Blanket asset-class drops lose macro-flavored content.** If
   a vendor publishes mostly equity, the relevance filter should
   drop equity *with a keep-allowlist* (FTM regional wraps,
   strategy/portfolio/positioning weeklies, sector themes), not all
   of it. Audit the actual title distribution before deciding.
9. **GraphQL queries are sticky-typed.** Copy the captured query
   string verbatim — don't try to clean up duplicate variable
   declarations or unused fields. The server's parser tolerates
   what the SPA actually sends; deviations risk regressions.
10. **Daily volume varies 5-10× from pre-launch estimates.**
    "About 20-50/day" guesses are routinely wrong by an order of
    magnitude once you see the full firehose. Build the audit
    script first, ingest a 2-3 day window second, set the daily-
    volume table from observation.

---

## Definition of done — checklist

Before declaring a vendor **LIVE** (Phase 7 promotion), confirm:

**Code in place** (all under `playground/research/`):
- [ ] `explore_<vendor>.py` — Phase 1 wrapper.
- [ ] `ingest/crawler_<vendor>.py` — discover_reports + session-prime
  pattern + locale-safe date parsing + non-PDF drop + publisher-flag drop.
- [ ] `ingest/filters/<vendor>.py` — title-prefix stub (may be empty).
- [ ] `ingest/classifiers/<vendor>.py` — `classify()` populates
  `asset_class`, `country_code`, `tags`, `context`.
- [ ] `<vendor>` added to `_VENDOR_CODES` + dispatcher branch in
  `ingest/classifiers/__init__.py`.
- [ ] `<vendor>` added to `_load_vendor_registry()` in
  `ingest_today.py` (the orchestrator).
- [ ] `smoke_<vendor>_audit.py` — asset-class distribution + drop
  reasons + audio/video leakage scan.
- [ ] `smoke_<vendor>_retrieval.py` — 3-query Qdrant spot-check.
- [ ] `backfill_<vendor>_meta.py` — only if your first smokes used a
  legacy standalone runner; otherwise skip.

**DB + ops state**:
- [ ] `migrations/NNN_seed_<vendor>_dim_vendor.sql` written, applied,
  and verified (`SELECT * FROM dbo.dim_vendor WHERE vendor_code='<v>'`).
- [ ] First end-to-end smoke (`--embed false --limit 2-3`) wrote
  rows to `research.dim_report` + chunks to `research.fact_chunk`,
  PDF files synced to OneDrive/SharePoint.
- [ ] First full-day `--embed true` run completed; chunks landed in
  Qdrant; `smoke_<vendor>_retrieval.py` passes.

**Docs**:
- [ ] `scrapers/<vendor>.md` filled in: portal, profile, URL
  patterns, listing API request/response shape, auth headers, PDF
  URL pattern, volume table (raw / kept / drop reasons), Non-PDF
  Assets section.
- [ ] Row added to `scrapers/index.md` `Vendors` table and to the
  `Common patterns / A. Listing-API firehose` table (or whichever
  pattern subsection applies).
- [ ] `vendors.yml` flipped from `profile_status: probe` →
  `production`, with last_session_date updated.
- [ ] All commits ship docs only (code lives under `playground/*`,
  gitignored).

---

## Reference reading

* [`index.md`](index.md) — the overall pipeline.
* [`scrapers/index.md`](scrapers/index.md) — the per-vendor inventory
  and the "Common patterns" reference.
* [`relevance_filter.md`](relevance_filter.md) — what the post-
  classifier filter drops.
* [`troubleshooting.md`](troubleshooting.md) — the recovery cookbook.
* `feedback_research_listing_api_discovery.md` (auto-memory) — why
  phase 2 comes before any DOM scraping.
