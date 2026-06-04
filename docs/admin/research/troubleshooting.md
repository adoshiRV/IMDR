# Research ingest — troubleshooting

The research ingest never returns a silent zero. When a crawler can't
make progress, it emits a categorised line with one of the categories
below. The orchestrator (`ingest_today.py`) prints a per-vendor *funnel*
showing how many refs survived each stage, plus a named scenario for
the post-discover empty case.

Read top-to-bottom when triaging: vendor crawler line first (HTTP /
network / layout), then orchestrator funnel, then post-ingest
`[INS]/[DUP]/[FAIL]` per-report counts.

## Categories

All categories use the same line shape so they're greppable:

```
  [LEVEL] {vendor}.{context}: {category}; {detail}{action_hint}
```

`LEVEL` is `ERR` for non-recoverable, `WARN` for recoverable-with-retry,
`OK` for healthy lines (rare; mostly used in the probe scripts).

| Category | Trigger | Operator action |
|----------|---------|-----------------|
| `auth_expired` | HTTP 401/407 from the listing API | Re-run `playground/research/explore_{vendor}.py` to refresh the persistent Chrome profile cookies. |
| `auth_missing` | HTTP 403 | First-time login, or the session was downgraded out of the content scope. Same fix as `auth_expired`. |
| `login_html` | HTTP 200 OK *but* the body is a login page (vendor framework redirected the API URL to its SSO instead of returning JSON) | Equivalent to `auth_expired` — re-run `explore_{vendor}.py`. |
| `rate_limited` | HTTP 429 | Back off and retry later. The crawler treats this as a soft failure (returns `[]` for that page); the orchestrator funnel will show 0 discovered. |
| `server_error` | HTTP 5xx | Vendor-side outage. Retry later. |
| `not_found` | HTTP 404 | The listing endpoint moved. Check the vendor's docs page (`docs/admin/research/scrapers/{vendor}.md`). |
| `bad_response` | HTTP 200 but JSON parse failed, or shape didn't match what the caller expected | Schema drift on the vendor side. The crawler prints a 200-char body preview; eyeball it. |
| `network_error` | Exception before any HTTP response (DNS, connection refused, TLS, timeout) | Check VPN / corporate DNS. |
| `navigation_timeout` | Playwright `page.goto()` exceeded its timeout (HSBC + ANZ-warmup paths) | Vendor portal is slow or unreachable. Try the URL manually in a real browser. |
| `listing_layout_changed` | DOM hook a crawler expected (a JS function, a selector) wasn't on the page (HSBC) | The vendor changed their portal HTML. The crawler needs a code update. |
| `empty_window` | HTTP 200, parse OK, listing genuinely returned zero reports in the requested date window | No-op. Skip the vendor for this run. |

## Orchestrator-level scenarios

When `_run_vendor` finishes with zero refs to ingest, it prints one of
these named scenarios (in addition to whatever the crawler logged):

| Scenario | Means | Where to look |
|----------|-------|---------------|
| `DISCOVER_THREW` | `vendor.discover()` raised an exception | The crawler's stack trace is printed inline; usually a Playwright connect/launch failure or `AnzApiError`. |
| `DISCOVER_ZERO` | `vendor.discover()` returned `[]`. | Scroll up for the crawler's `[ERR]` / `[WARN]` line — that has the category. If there isn't one, the window is genuinely empty (`empty_window`). |
| `FILTER_DROPPED_ALL` | The relevance filter classified every discovered ref as single-name equity. | Expected when the date window happens to be all equity-research. Not an error. |
| `LIMIT_ZERO` | `--limit` truncated the post-filter list to zero (defensive). | Shouldn't normally happen — implies `--limit 0` was treated as a positive cap somewhere. |

The funnel line shows the per-stage counts so the "where did N refs go" question is one glance:

```
  funnel: discovered=199  after_relevance_filter=42  after_limit=5  (filter_removed=157, limit_cap=5)
```

## Discovery filters — admin / event titles

Each vendor crawler runs a discovery-time title filter
([`ingest/filters/{vendor}.py`](../../../playground/research/ingest/filters/))
*inside* `discover_reports`, before the relevance filter and before any
HTTP fetches. Matched titles surface as `[SKIP] title-prefix:'<prefix>' ...`
log lines in the crawler output. The filter exists to drop pure
admin/event chatter that has no analytical content:

- meeting invites, webinar registrations, save-the-date pings
- reminders for upcoming calls
- time-imminent pings (`***STARTS IN 1 HOUR***: ...`)
- republished / rescheduled / replay announcements
- recurring hosted-call series brands (e.g. `Analyst Access:`)

### Title normalization

Vendor titles routinely arrive with decorative leading punctuation
(`***STARTS IN ...***:`, `** Reminder: IN AN HOUR **`, `~~ Today ~~`).
A naïve `startswith("reminder:")` misses all of these. The shared
[`normalize_title()`](../../../playground/research/ingest/filters/__init__.py)
helper canonicalises titles before matching:

1. Lower-case + strip surrounding whitespace.
2. Replace `*` and `~` (decoration chars) with spaces.
3. Collapse runs of whitespace to single spaces.
4. Collapse ` :` → `:` so decoration-stripped colons line up.
5. Strip any remaining leading non-alphanumeric characters.

Worked examples:

| Raw title | Normalised |
|-----------|------------|
| `***STARTS IN 1 HOUR 1PM ET***: Barclays Hosted: ...` | `starts in 1 hour 1pm et: barclays hosted: ...` |
| `** Tomorrow ** Reminder: foo` | `tomorrow reminder: foo` |
| `***Today***: Kone/TKE deal: ...` | `today: kone/tke deal: ...` |
| `UPDATE Reminder: Barclays: EU Strategy` | `update reminder: barclays: eu strategy` |

After normalisation, a tuple of plain lower-case prefixes catches
everything. Each vendor module is just the data (a tuple) + a one-line
wrapper; the matching logic lives once in `filters/__init__.py`.

### Adding a new admin pattern

1. Find the leaked title in `dim_report.title` and verify it really is
   admin/event noise (not real research).
2. Pick the minimal prefix that distinguishes it from real research
   (post-normalization). Prefer longer prefixes (`webinar invite:` over
   `webinar:`) to avoid false positives.
3. Append the prefix to the vendor's `EXCLUDED_TITLE_PREFIXES` tuple
   with a one-line comment that quotes a real example.
4. Add the example title to `playground/research/test_barclays_filter.py`
   (or the analogous test). The `test_every_excluded_prefix_has_at_least_one_real_sample`
   test enforces that every prefix has at least one real sample —
   speculative prefixes break that test, which is by design.
5. Run `python -m pytest playground/research/test_barclays_filter.py -v`.

### Cleaning up leaks

If the filter was too narrow and admin titles already made it into the
corpus, use `cleanup_filter_violations.py` with `--rule admin`:

```
python playground/research/cleanup_filter_violations.py --rule admin            # dry-run
python playground/research/cleanup_filter_violations.py --rule admin --commit   # destructive
```

It replays the current discovery filter against every persisted title
in `dim_report` and removes any rows the filter would now reject —
across the DB, Qdrant, and OneDrive in one transaction.

## Post-ingest `[FAIL]` modes

Per-report `[FAIL]` lines come from the writer in
[`playground/research/ingest/db.py`](../../../playground/research/ingest/db.py).
The vendor crawler and classifier already succeeded — the error is
inside the DB transaction that materialises the report row, chunk rows,
and tag-map rows.

| Failure | Trigger | Fix |
|---------|---------|-----|
| `IntegrityError: uq_research_map_report_tag` (duplicate `(report_id, tag_id)`) | The classifier emitted two `(category, value)` tag pairs that resolved to the **same** `research.dim_tag.id`. `dim_tag` is unique on the `tag` value alone (not on `(category, value)`), so two distinct input categories sharing a value — or two values whose 50-char truncation collides — return the same id. | Fixed in `_bulk_insert_report_tags` by deduping on resolved `tag_id` (not just on input `(category, value)`). If you see this re-emerge, audit the upsert path for any caller that bypasses the dedupe. |
| `FetchError: HTTP 404 (session likely expired ...)` on `marquee.gs.com/content/markets/...pdf` (Goldman) | The Goldman API populates `downloadPath` with `/content/markets/.../<uuid>.pdf` URLs for MarketView audio/video/blog assets that have no PDF rendition. The fast-path GET hits a hard 404 with `<title>404</title>`. The "session likely expired" hint in the message is misleading for this case — see `probe_goldman_markets_pdf.py`. | Fixed in `_derive_pdf_url` ([crawler_goldman.py](../../../playground/research/ingest/crawler_goldman.py)) by gating the `downloadPath` branch behind `_PDF_PATH_PREFIX = "/content/research/en/reports/"` so these dead URLs are dropped at discovery. |
| `FetchError: Couldn't extract a PDF URL from viewer page` on HSBC Podcast / Video titles | HSBC Reach lists podcast and video assets in the same feed as PDF research; their viewer URLs (`/R/10/<id>`) have no `.pdf` redirect. | Title-prefix filter at [`filters/hsbc.py`](../../../playground/research/ingest/filters/hsbc.py) excludes `"podcast:"` and `"video:"` at discovery. New non-PDF media types should be added there alongside the existing `invite:` / `webcast:` / `conference call:` / `expert access:` prefixes. |
| `FetchError: Couldn't extract a PDF URL ... Viewer URL was: about:blank` | Playwright finished navigation before the viewer page's redirect fired; the page object's URL is still `about:blank` when we read it. | Transient — re-runs usually pick it up. If a specific report fails repeatedly, raise the post-navigation settle wait in the affected crawler's viewer-redirect helper. |

## Per-vendor quirks

- **ANZ** — SingleTrack CMS's tile API returns `{"content":[], "total_count":0}` with a valid session cookie if the SPA hasn't been visited recently. The crawler runs `page.goto(/all_research)` first to warm the session; if it skips that step you get `empty_window` despite healthy auth. Diagnosed via `playground/research/probe_anz_status.py` on 2026-05-24.
- **Goldman** — per-PDF fetch may return HTTP 401 long after the listing API was happy. Those surface as `[FAIL] ... FetchError: GET ... returned HTTP 401` per-report — not as a category here. Same fix applies (re-run `explore_goldman.py`). A separate failure mode is the API populating `downloadPath` with dead `/content/markets/...pdf` URLs — see the post-ingest `[FAIL]` table above. Diagnostic harness: `playground/research/probe_goldman_markets_pdf.py` (tries fast-path GET + viewer-redirect against a sample of the failing URLs; both return `text/html` 404).
- **Barclays** — has its own re-login retry loop inside `_fetch_json_with_relogin` / `_download_pdf_with_relogin`. You'll see `[WARN] barclays.json_fetch:...: auth_expired ... — re-logging in` followed by either success or a final `[ERR]`. The retry is silent in the sense of "no operator action needed" but the diagnostic line is still printed.
- **HSBC** — uses `page.evaluate` (DOM JS) instead of direct HTTP. Failures surface as `navigation_timeout` or `listing_layout_changed`, not as HTTP status categories. If the vendor changes the JS function name (`rcRedisplayReportsTab`), the crawler can't paginate. The listing also mixes podcast/video assets in with PDF research; those are dropped at discovery via title-prefix filter — see [`filters/hsbc.py`](../../../playground/research/ingest/filters/hsbc.py).
- **MS** — frontmatter resolution is per-UUID. Per-UUID failures print one `[ERR] ms.frontmatter_uuid=...` line each but don't abort the whole vendor — that report is just skipped from the ingest queue. Watch the funnel `after_relevance_filter` count vs the original discovered to spot if too many were dropped at the frontmatter step.

## Files

| Where | What |
|-------|------|
| [`playground/research/ingest/diagnostics.py`](../../../playground/research/ingest/diagnostics.py) | Shared classifier + log-message helpers. The source of truth for the category list. |
| [`playground/research/test_diagnostics.py`](../../../playground/research/test_diagnostics.py) | Pins category mapping + message shape. |
| [`playground/research/ingest/crawler_*.py`](../../../playground/research/ingest/) | Each vendor crawler imports and uses `describe_response()` / `describe_exception()` / `describe_layout_change()` / `describe_navigation_timeout()` at every failure path. |
| [`playground/research/ingest_today.py`](../../../playground/research/ingest_today.py) | Orchestrator — emits the funnel line + named `DISCOVER_THREW / DISCOVER_ZERO / FILTER_DROPPED_ALL / LIMIT_ZERO` scenarios. |
| [`playground/research/probe_anz_status.py`](../../../playground/research/probe_anz_status.py) | Diagnostic harness for ANZ — hits the tile API with and without SPA bootstrap and prints status/content-type. |

## Adding a category

1. Decide whether the new failure is a HTTP-status category (extend `classify_status`) or a structural one (add a `describe_*` helper in `diagnostics.py`).
2. Add the hint string to `_HINT` so the message tells the operator what to do.
3. Add a parametrized test row to `test_diagnostics.py`.
4. Add a row to the **Categories** table above.

Never introduce a new error path without first deciding which category it falls under. If none of the existing ones fit, prefer adding a new category over reusing `bad_response` / `other` — that's the whole point of this module.
