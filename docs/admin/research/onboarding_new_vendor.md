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
   `playground/research/profiles/<vendor>/`. On first run it's empty —
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
   always the right target. Capture:
   * Request method + URL + path params.
   * Body shape (Goldman uses POST JSON with a facets DSL; ANZ uses
     GET with `param_limit` + `position`; Nomura uses an
     Elasticsearch DSL; MS uses a POST JSON with `compositeRequest`).
   * Whether responses contain enough metadata to skip a per-uuid
     follow-up (Goldman/Nomura yes; MS needs a `/frontmatter?uuid=…`
     call for the PDF URL).
   * Page size — push it as high as the server allows. 200 is a safe
     baseline; 500–1000 has worked for some.

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

* **Paginate** until `oldest-in-page < since` (early stop). Don't
  fetch the whole archive every run.
* **Use the persistent profile cookies** via `ctx.request.get/post`,
  not a fresh `requests.Session`. That's how the listing API
  authenticates.
* **Dedupe inside the run** — some listing APIs return overlapping
  pages.
* **Construct PDF URL during discovery**, not at fetch time — keep
  the per-PDF stage stateless.
* **Return `ReportRef`** with `uuid`, `title`, `publish_date`,
  `pdf_url`, `vendor_code`, `extra` (dict for vendor-specific fields).

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

---

## Phase 5 — Wire the runner

`playground/research/ingest_today_<vendor>.py`. Thin shim that:

1. Opens a Playwright context with the vendor's persistent profile.
2. Calls `discover_reports(...)`.
3. Applies the discovery filter, then the classifier, then
   `apply_relevance_filter`.
4. Hands the survivors to the shared `ingest_one` pipeline
   ([`pipeline.py`](../../../playground/research/pipeline.py)) which
   handles fetch / parse / hash / chunk / OneDrive / DB / Qdrant.

Copy [`ingest_today_anz.py`](../../../playground/research/ingest_today_anz.py)
or [`ingest_today_nomura.py`](../../../playground/research/ingest_today_nomura.py)
as the starting point — these have the canonical structure.

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

4. **Spot-check retrieval**:

   ```powershell
   C:/Users/adoshi/.conda/envs/imdr/python.exe playground/research/retrieve.py "<topic the new vendor covered>"
   ```

   Should return at least one citation from the new vendor.

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

## Reference reading

* [`index.md`](index.md) — the overall pipeline.
* [`scrapers/index.md`](scrapers/index.md) — the per-vendor inventory
  and the "Common patterns" reference.
* [`relevance_filter.md`](relevance_filter.md) — what the post-
  classifier filter drops.
* [`troubleshooting.md`](troubleshooting.md) — the recovery cookbook.
* `feedback_research_listing_api_discovery.md` (auto-memory) — why
  phase 2 comes before any DOM scraping.
