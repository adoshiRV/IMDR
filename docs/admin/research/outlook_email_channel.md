# Outlook email — research acquisition channel

**Status: prototype (route-B), updated 2026-06-22. Migration 099 APPLIED; FULL `--load` pipeline IMPLEMENTED (classify → portal-twin dedup-merge → chunk → embed → upload `.html` to the SharePoint tree → MSSQL `source='email'` → Qdrant), one command. First multi-vendor production load done 2026-06-22 (7-day desk-core, 8 vendors): 77 net-new rows loaded / 0 failed in 76s; gates skipped 17 portal-twins + 14 db-dedups + 4 hash-dups. Email corpus 112 rows (after retro-cleaning one teaser-pointer row caught by the new portal-pointer gate). Artifacts land in `ResearchData1/IMDR/` identical to portal. Still NOT wired into any orchestrator; route-A (Graph) producer + per-vendor subject parsers are the next builds. NB route-B's per-run cost is ~all the LLM spend (~9–13k tokens/article to stage each body); route-A eliminates it.**

A *second acquisition channel* for sell-side research, alongside the
per-vendor portal scrapers ([`scrapers/`](scrapers/)). Research that
arrives by **email** in the `research@rvcapital.com` mailbox — already
hand-filtered by the user's Outlook rules into per-bank folders — is read,
normalised, and pushed through the **same** parse → write pipeline as
portal PDFs, tagged with provenance so every row knows it came from email.

This is a *channel*, not a vendor: a Goldman note ingested here is still
`vendor_id=goldman`; what differs is `source='email'`.

> Build/staging contract (folder→vendor map, staging JSON shape, adapter
> internals): [`playground/research/outlook/README.md`](../../../playground/research/outlook/README.md).
> Per-folder email taxonomy (what each folder actually carries): memory
> `reference_outlook_folder_taxonomy`.

## Why a separate channel

| | Portal scrapers | Email channel |
|---|---|---|
| Source | vendor SPA listing APIs | `research@rvcapital.com` mailbox |
| Discovery | Playwright + persistent profile | read folders (route B: MCP; route A: Graph API) |
| Filtering | aggressive (single-name-equity drop, chart-pack gates) | **lenient** — folders are pre-curated; drop only noise |
| Provenance | `source='portal'` (default) | `source='email'` |
| Unique value | exhaustive firehose | **desk/sales commentary that never appears on portals** |

The real unlock is **desk commentary** (DB·Wong, Citi·Koh, SCB·Szto,
Nomura·Winkelmolen, BofA·Sidhva, MS JPY desk, HSBC "The Floor", JPM·Shah).
A dedup smoke against the live 8,291-row corpus (2026-06-18) confirmed it:
every sampled `research`/portal-digest item was **already in IMDR** from the
portal crawlers, while every `desk_commentary` item was **net-new**. So the
`source_type` split *is* the dedup signal.

## Mailbox + folders

`research@rvcapital.com` (shared/delegated). `Research/` has **16 per-bank
child folders** (confirmed via `read_resource mail:///folders/`). Two are
**held out** of ingestion pending separate onboarding.

| Folder | vendor_code | | Folder | vendor_code |
|---|---|---|---|---|
| GS   | `goldman`  | | Citi    | `citi`     |
| MS   | `ms`       | | HSBC    | `hsbc`     |
| DB   | `db`       | | Barc    | `barclays` |
| JPM  | `jpm`      | | BOFA    | `bofa`     |
| Nom  | `nomura`   | | Westpac | `westpac`  |
| ANZ  | `anz`      | | UBS     | `ubs`      |
| SCB  | `stanc` †  | | CBA     | `cba` ⚠ (held) |
| STANC| `stanc` †  | | CACIB   | `cacib` ⚠ (held) |

† **`SCB` and `STANC` are two folders for the same vendor** (Standard
Chartered = `stanc`) with opposite provenance: `SCB` = `John.Szto@sc.com`
**desk commentary**; `STANC` = `research.distribution@sc.com` **formal
research** (the SMS flagship arrives here). One `dim_vendor` row; the split
lives in `source_type`, resolved per message.

⚠ **`cba` and `cacib` have NO `dbo.dim_vendor` row and no portal crawler** —
email is their only channel. They are in `crawler_outlook.EMAIL_VENDOR_HOLD`
(skipped by `discover_reports` unless `--vendors` names them explicitly), per
user instruction 2026-06-18 ("do those two later"). Onboarding each needs a
`dim_vendor` row first.

> **M365 MCP access recipe (re-confirmed 2026-06-22 — read carefully, the
> `owner` rules are inconsistent across resource types):**
> * **List folders:** `read_resource mail:///folders/?owner=research@rvcapital.com`
>   returns the full tree (mailbox + the 16 `Research/` child folders) with IDs.
> * **List a folder's messages:** `read_resource mail:///folders/{id}?owner=…`
>   returns up to ~45 messages **newest-first** (no date filter, no paging) —
>   so a high-volume folder like GS (>45 msgs/3 days) won't reach a week back
>   in one call.
> * **Read one message:** `read_resource mail:///messages/{id}` **WITHOUT**
>   `?owner` (adding `?owner=` here 404s `NOT_FOUND`). Returns the full
>   `body.content` (HTML) **and `internetMessageId`** — the stable staging
>   dedup key, available without any extra call.
> * **Search (`outlook_email_search` with `mailboxOwnerEmail`) 404s**
>   (`MailboxNotEnabledForRESTAPI`) — do NOT rely on search; enumerate folders
>   by ID instead. Folder-name lookup is also unreliable for nested folders.

## Access model — route B now, route A later

The Microsoft 365 MCP is a **Claude-side** tool; the unattended Python
pipeline can't use it. So:

* **Route B (current):** Claude pulls emails via the M365 MCP and writes
  one JSON per message into `playground/research/outlook/staging/{vendor}/`.
  The Python crawler reads **only** that staging dir.
* **Route A (future, unattended):** an Azure AD app registration
  (`Mail.Read` on `research@rvcapital.com`, `msal`) populates the same
  staging shape on a cron. The crawler is identical either way. → needs
  `imdr-security` for the app reg.

> **PDF-byte limitation (confirmed 2026-06-18):** the M365 MCP `read_resource`
> returns an attachment's **extracted text only — never raw bytes**. So
> route B **cannot** capture a byte-accurate PDF; the 3 vendors that attach
> real PDFs (CBA, Nomura ~35%, DB desk-PM) need **route A** (`Graph
> /attachments/{id}/$value`) for the bytes. Body-only desk notes are
> unaffected — the body *is* the artifact.

## Delivery archetypes → extraction

| Archetype | Example senders | Real PDF? | Stored as |
|---|---|---|---|
| Attached-PDF research | `*.cba.com.au`, SCB `Eric.Robertsen` (SMS), `maki.hanawa@db.com` | ✅ attachment (route A only) | the PDF; body → `context` |
| Clean HTML note | `research@anz.com` (summary + portal docRef link) | ❌ | body text |
| Desk/sales commentary | `walter.wong@db.com`, `zeke.koh@citi.com`, `John.Szto@sc.com`, `remo.winkelmolen@nomura.com`, `jamshed.d.sidhva@bofa.com`, `ms.jpy.rates.daily@` | ❌ | body text |
| Portal digest / marketing | `*.alerts.publishing.gs.com`, `resweb@morganstanley.com`, `ubs_research@ubs.com`, Barc marketing | ❌ (inline charts only) | dedup vs portal; keep body only if unique |

> **Links are never fetchable.** Every portal link in these emails is
> auth-gated + expiring + often recipient-bound (BofA `rsch.baml.com?e=<the
> salesperson>`, UBS `neo.ubs.com/r/`, ANZ Singletrack `docRef`, GS
> `opentoken`, StreetContxt for Barc/JPM) and arrives Outlook-safelink
> wrapped. Rule: **PDFs come only from a real attachment or the portal
> crawler — never an email link.**

## email → Document + the pdf_path artifact

The pipeline operates on [`ingest/models.py:Document`](../../../playground/research/ingest/models.py).
The adapter [`ingest/email_doc.py`](../../../playground/research/ingest/email_doc.py)
builds it two ways:

* **Attached PDF** → `parse_pdf(bytes)` → normal `Document` (`content_hash`
  = SHA-256 of PDF bytes); sanitized body → `ReportMeta.context`.
* **Body-only** → sanitize `body_html` (strip CAUTION banner + legal/footer
  tails) → synthesize a `Document` (`content_hash` = SHA-256 of the **stable
  sanitized source**, `parser_version="email-html-v1"`).

**`pdf_path` stays `NOT NULL` — every email report keeps a stored artifact,
in the SAME date-first SharePoint tree as portal PDFs** (`build_sharepoint_path`
with the email's message-id hash as the uuid → `{YYYY}/{MM}/{DD}/{vendor}/
{slug}_{imi8}.{ext}`, uploaded via `upload.upload_bytes` into
`LOCAL_IMDR_ROOT` = the OneDrive sync of `ResearchData1/IMDR/`). No lossy
render step. Artifact format by archetype + access route:

* **Body-only, route B (now):** the raw body HTML → `.html` (browser-readable,
  `pdf_path` ends `.html`). Proven: id=10870 →
  `2026/06/10/nomura/Nomura_EUR_Rates_Strategy_France_..._aaac884b.html`.
* **Body-only, route A (Graph):** the canonical raw `.eml` (lossless MIME —
  headers + attachments + message-id). Same path, `.eml` extension → no schema
  change, just a different suffix in `pdf_path`.
* **Attached-PDF emails** (CBA / DB-desk / Nomura): the real attachment `.pdf`
  is `pdf_path`; keep the `.eml` alongside as provenance. (Needs route A for
  the bytes — MCP gives text only.)

`content_hash` (dedup) comes from the **stable sanitized body source**, NOT the
stored artifact bytes, so a later route-B→route-A swap (`.html`→`.eml`) never
creates a false duplicate.

## Relevance — lenient by design

The folders are already hand-filtered, so the email path does **NOT** run the
portal single-name-equity filter. Its only gate is
`crawler_outlook.email_noise_reason(subject)` — an admin/marketing/media/
digest drop-list. Patterns (each a labelled regex): summary-alert,
ratings/TP, World-Cup novelty, single-name "actionable ideas", webcast/
webinar/timetable, "Most Read"/"What Your Peers" digests, training, Extel
surveys, `Video:`/`Podcast:`/`Video Views`, economic/auction calendars, thin
data blasts, "thematics framework", **chart-packs** (`\bchart\s?packs?\b` —
Westpac "AUD Rates Morning Chartpacks"; link-only, substance in unreachable
chart PDFs; does NOT catch "Charts that Matter", which carries real captions),
**login/OTP/verification** (login codes,
`portal token`, account-verification, password-reset), **credentials** (JPM
`jpmm.notification` username/password mail), **marketing** ("WEBSITE – SIGN
UP"), **top-weekly-reads digests**. Deliberately OTP-specific — bare `token`
is NOT matched, so tokenisation/crypto research is never dropped.

## source_type — research vs desk_commentary

`crawler_outlook._derive_source_type` decides in this authority order:

1. explicit staging value
2. body **"NOT RESEARCH" disclaimer** → `desk_commentary` (authoritative)
3. **per-vendor folder default** (`_VENDOR_DEFAULT_SOURCE_TYPE`): `bofa`=desk;
   `cba`/`anz`/`westpac`/`cacib`=research — this BEATS the archetype below,
   because vendor identity is a stronger provenance signal than delivery
   shape (a formal economist note delivered body-only is still research)
4. archetype `desk_commentary`
5. **sender heuristic** — research aliases (`macro@alerts…`, `HSBC.Research@`,
   `ubs_research@`, **`research.distribution@sc.com`** for the STANC folder) →
   research; named-person@desk-domain or `[/]`-prefixed subjects → desk.
   `nomura.com` is deliberately NOT a desk-domain (one salesperson forwards
   the whole folder, mostly research; genuine desk products still match via
   the desk-subject regex)
6. default → `research`

## Classification

Email refs lack the structured facets portal classifiers depend on. So
`cba`/`cacib` (no portal classifier) and any vendor whose portal classifier
returns an empty `asset_class` fall back to the keyword classifier
[`classifiers/email_common.py`](../../../playground/research/ingest/classifiers/email_common.py).

**Known limitation:** subject-only classification is weak (the load smoke
mislabelled CBA Daily→COMMODITIES, STANC BoJ→FX, Barclays Fed→CREDIT);
**bodies improve it but per-vendor SUBJECT PARSERS are the real fix** —
CACIB `FX Daily`/`Interest Rates Daily`, STANC `The Morning Standard –
{country}`, DB `DB Asia: Korea`, Westpac mastheads encode asset+country
structurally. Net-new items need this; portal-overlap items inherit the
portal class on dedup-merge.

## Dedup rules

Gates in order, cheapest/most-certain first:

1. **`internet_message_id`** already in `dim_report` → skip (migration-099
   filtered-unique key; PRIMARY email gate; pre-checked in `ingest_email_one`
   before chunk/embed, and again inside `write_report`).
2. **Portal-twin fuzzy merge** ([`dedup_merge.find_portal_twin`](../../../playground/research/ingest/dedup_merge.py)) →
   skip if the report already exists from the portal crawler under a reworded
   title. See below.
3. `content_hash` already present → skip (in `write_report`).
4. `(vendor_id, publish_date, LOWER(title))` exact match → skip.
5. Adapter-level (`decide_dedup` on the `build_email_document` outcome): pure
   notification wrapper (no substantive body) → skip; **`skip(portal_pointer)`**
   (short body + report-download link — teaser cover-note) → skip; PDF whose
   hash exists → retry body-only.

### Portal-twin fuzzy merge

Desks re-forward portal research with a masthead prefix + a +1-day lag —
e.g. portal `Fed Notes: June FOMC recap…` (06-17) arrives as email
`[/] DB Fed Notes - June FOMC recap…` (06-18). Exact title/date/hash gates
all miss it, so without this the email would insert a duplicate report.

`find_portal_twin` normalizes both titles to significant-token sets (drop
vendor names, `RE:`/`FW:` markers, stopwords, generic cadence words
[week/ahead/weekly/daily/monthly/monitor/update], and pure-digit year/day
tokens), then scores **Jaccard `|A∩B|/|A∪B|`**; a match needs `≥0.70` AND
`≥3` shared tokens, both titles `≥3` tokens, same vendor, within `±3 days`.

**Precision-first by design** (the gate is destructive — it skips the
email): it catches verbatim-headline forwards (~1.0) but deliberately
MISSES differing-masthead twins (`DB Strategy: X` vs portal `FX Blog: X`
→ 0.5), leaving those as a dup row — far better than a false positive
dropping a net-new desk note. Jaccard (not overlap-coefficient) + the
digit-drop + the ≥3-shared guard prevent the degenerate single-shared-token
false match (a Citi `ASW Run … 2026` once matched a mojibake portal title
`2026年6月8日`). `--keep-portal-twins` disables the gate for investigation.
Future recall boost: core-headline extraction (after the masthead separator)
to catch the differing-masthead cases.

> **⏳ OPEN — revisit (logged 2026-06-22):** the gate filters
> `v.vendor_code = :vc AND r.source = 'portal'`, so for a vendor with **no
> portal crawler** (`cba`, `cacib`) there are zero portal rows to match and
> the portal-twin merge is a **silent no-op** — those vendors fall back to
> the `internet_message_id` + `content_hash` + `(vendor, date, title)` gates
> only. That is *probably* correct (email is their sole channel, so every
> item is genuinely net-new and there's nothing to twin against), but it has
> **not been confirmed** and warrants a deliberate decision before cba/cacib
> are un-held: is imi+hash dedup sufficient for an email-only vendor, or do
> we want an intra-email near-dup merge (same desk re-sending the same note)?
> Also unverified: the gate's recall on the **other live-portal vendors**
> (GS/MS/JPM/…) — the mechanism is vendor-agnostic but precision/recall was
> only smoke-validated on DB + Citi (the entire 36-row corpus). See the
> 2026-06-22 cross-vendor dry-run smoke note below.

## Schema — migration 099 (APPLIED 2026-06-18)

[`migrations/099_research_dim_report_email_channel.sql`](../../../migrations/099_research_dim_report_email_channel.sql)
added to `research.dim_report`:

| Column | Type | Notes |
|---|---|---|
| `source` | `varchar(16)` NOT NULL DEFAULT `'portal'` | `'portal'` \| `'email'` — all pre-existing rows back-labelled portal |
| `source_type` | `varchar(20)` NOT NULL DEFAULT `'research'` | `'research'` \| `'desk_commentary'` |
| `internet_message_id` | `varchar(255)` NULL | RFC-2822 Message-ID; filtered-UNIQUE index `ix_research_dim_report_imi WHERE NOT NULL` |

`pdf_path` untouched (stays NOT NULL). Verified post-apply: all portal rows
`source='portal'`/`source_type='research'`/`imi=NULL`; index `is_unique=1,
has_filter=1`. (The read-only DB MCP returns NULL for `object_definition`/
`filter_definition` — a system-fn quirk; verify via data + `sys.indexes.has_filter`.)

## Code map

| File | Purpose |
|---|---|
| [`ingest/crawler_outlook.py`](../../../playground/research/ingest/crawler_outlook.py) | staging reader → `OutlookReportRef`; folder→vendor map; `EMAIL_VENDOR_HOLD`; `_derive_source_type`; `email_noise_reason` (incl. `chartpack` drop); `decide_dedup` |
| [`ingest/email_doc.py`](../../../playground/research/ingest/email_doc.py) | HTML sanitizer (CAUTION + Westpac anti-phishing banner strip; `_TRAILING_CUTS` incl. ANZ/BofA/DB disclaimer footers) + synthetic-Document builder + `is_portal_pointer` (teaser-cover-note → `skip(portal_pointer)`) |
| [`ingest/classifiers/email_common.py`](../../../playground/research/ingest/classifiers/email_common.py) | keyword classifier (word-boundary scored) |
| [`ingest/classifiers/cba.py`](../../../playground/research/ingest/classifiers/cba.py) | CBA classifier (AU/MACRO default) |
| [`ingest/engine.py`](../../../playground/research/ingest/engine.py) | shared ODBC Driver 18 engine factory (used by `ingest_one.py` + `ingest_outlook.py`) |
| [`ingest/db.py`](../../../playground/research/ingest/db.py) | `write_report()` — gained `source`/`source_type`/`internet_message_id` params + the imi dedup gate |
| [`ingest/dedup_merge.py`](../../../playground/research/ingest/dedup_merge.py) | `find_portal_twin()` — fuzzy email→portal title match (Jaccard) so desk re-forwards of portal notes are skipped |
| [`ingest/email_pipeline.py`](../../../playground/research/ingest/email_pipeline.py) | `ingest_email_one()` — full per-message pipeline (portal-twin gate → chunk → embed → upload → DB → Qdrant); the ~10x-simpler analogue of `pipeline.ingest_one` |
| [`ingest_outlook.py`](../../../playground/research/ingest_outlook.py) | dry-run + full `--load` CLI (`--no-embed`, `--limit`, `--keep-portal-twins`); the `ingest_today.py` analogue |
| [`tests/unit/research/test_outlook_adapter.py`](../../../tests/unit/research/test_outlook_adapter.py) + [`test_dedup_merge.py`](../../../tests/unit/research/test_dedup_merge.py) | adapter sanitizer/synthesize/folder-map/source_type/decide_dedup (incl. `chartpack` + `skip(portal_pointer)`) (27) + dedup-merge jaccard/tokens (7) |
| [`tests/unit/research/test_email_common_classifier.py`](../../../tests/unit/research/test_email_common_classifier.py) | keyword classifier: per-class scoring, commodities-specificity guard, no-stem word-boundary, country/region scan, theme/author tags (15) |
| [`tests/unit/research/test_email_doc.py`](../../../tests/unit/research/test_email_doc.py) | adapter edges: earliest-cut boilerplate, ANZ/BofA/DB disclaimer + Westpac banner strips, `DESK_DISCLAIMER_RE`, `best_body_text`, `build_email_document` synthetic/skip/pdf_missing/link-only-skip, **portal-pointer gate** (`is_portal_pointer`), inline-attachment skip (19) |
| [`tests/unit/research/test_email_pipeline.py`](../../../tests/unit/research/test_email_pipeline.py) | `ingest_email_one` dedup short-circuits: imi-idempotency + portal-twin skip, fake Engine + monkeypatched twin (3) |

**71 email unit tests total** (adapter 27 · dedup-merge 7 · classifier 15 · email-doc 19 · pipeline 3).

## Running

```
python playground/research/ingest_outlook.py                          # dry-run, all staged
python playground/research/ingest_outlook.py --vendors citi            # dry-run, one vendor
# Full end-to-end (needs the imdr conda env for pyodbc/Driver18 + Voyage/Gemini + Qdrant):
C:/Users/adoshi/.conda/envs/imdr/python.exe playground/research/ingest_outlook.py --load
...ingest_outlook.py --load --vendors ms --limit 1                     # one note, full pipeline
...ingest_outlook.py --load --vendors citi --no-embed                  # DB row only (no embed/Qdrant)
```

`--load` runs the full pipeline (portal-twin gate → chunk → embed → upload
artifact to SharePoint → DB → Qdrant) per net-new email; embed + Qdrant are ON
by default (`--no-embed` for a DB-only row). Idempotent — re-runs DB-DEDUP on
`internet_message_id` and skip chunk/embed/upload.

**2-week backfill smoke (2026-06-19, Citi + DB, route-B MCP staging):**
staged 7 Citi + 35 DB → loaded 41, 0 failed, all SharePoint+chunks+Qdrant. The
portal-twin merge then removed **9 DB rows** that re-forward portal notes
(Fed Notes, FX Blog, Asia Macro Strategy Notes, Asia Chart Alert, Japan MPM
Watch); **0 false positives** (after the digit-drop fix). Clean corpus = **36
email rows** (db 25, citi 9, nomura 1, ms 1), 0 remaining twins. Net-new desk
content (JPY PM Summary ×N, Trading Comments, Citi ASW/Correlation Grid) all
preserved.

> **Bulk-loading status:** the portal-twin merge makes wider loads safe — it
> skips desk re-forwards of portal notes. It's precision-first, so a few
> differing-masthead twins still slip through as dup rows (acceptable). The
> route-B *producer* (MCP staging) is the practical limiter for a full backfill;
> the live variant (route A / Graph) is the unattended producer. CBA/CACIB
> remain held (no `dim_vendor` row).

### Cross-vendor dry-run smoke (2026-06-22, read-only)

`playground/research/outlook/_smoke_dedup_analysis.py` simulates the
`ingest_email_one` decision for **every** staged message against the live
corpus **without writing** (noise gate → build doc → imi-in-DB check →
`find_portal_twin` → in-run hash). Purpose: prove the gate behaves on the
vendors **beyond db/citi**, which the backfill never bulk-loaded. Result over
57 staged msgs / 15 vendors:

* **Portal-twin gate generalises — fired correctly for 7 distinct vendors**,
  not just db/citi: 13 twins caught, **all true positives, 0 false positives**.
  db Fed Notes/FX Blog/Chart Alert/MPM/CCS (1.00), goldman `US Daily: June FOMC
  Recap` → portal `June FOMC Recap` (0.92), hsbc `Bank of Japan :` (1.00, punct
  only), westpac/anz verbatim forwards (1.00), db Indonesia differing-masthead
  (`DB Asia:` vs portal `Asia Chart Alert:`) **caught at 0.83** — better recall
  than the documented worst case.
* **Closest call: stanc `The Morning Standard – BoJ – If not now, when?` →
  portal `BoJ – If not now, when?` at 0.71** — barely clears the 0.70 threshold.
  Little margin here; a slightly different masthead would miss it.
* **cba/cacib confirmed no-op:** `portal_rows = 0` → every staged item is
  INGEST (no twin possible). Empirically confirms the OPEN note above —
  email-only vendors get imi+hash dedup only.
* **Net-new INGEST items expose the classification gap on rows that DON'T have
  a portal twin to inherit a class from:** barclays `What if the Fed's next
  move is a hike?` → **CREDIT** (should be MACRO/RATES). NB the stanc BoJ note
  *was* mis-classed FX but it's a PORTAL-DUP, so it's skipped and the issue is
  moot — confirming portal-overlap items dodge the classifier weakness while
  **net-new items do not**. This is the strongest argument for the pending
  per-vendor subject parsers.

### Don't subject-drop the recurring dailies — read the bodies (2026-06-22)

A first pass proposed adding the high-volume recurring series (ANZ `Morning
Focus` / `What's Priced In`, Westpac `FinanceAM` / `Chartpacks`, BofA `Arvin
The: …Spot Views`) to the noise gate as "thin boilerplate". **Reading the actual
bodies overturned that** — most are substantive:

* ANZ **Morning Focus** — ~600 words (Highlights, FX/Rates commentary, Fed
  outlook). The body IS the note. KEEP.
* Westpac **FinanceAM** — full Overnight Market Wrap: levels, US/AU/NZ rate
  pricing, 1-day + 1-3mo AUD/NZD/swap views. KEEP.
* BofA **Arvin The: Spot Views** — real desk commentary (Warsh read, options-desk
  USDJPY regime call); self-labels "Sales/Trading Commentary; Not a Research
  Product" → correctly `desk_commentary`. KEEP.
* ANZ **What's Priced In**, Westpac **Chartpacks** — genuinely thin: link/chart
  pointers whose value is in unreachable auth-gated PDFs.

**The real fix was the sanitizer, not the noise gate.** ANZ + BofA legal
disclaimer footers were NOT in `email_doc._TRAILING_CUTS` (Westpac's "Things you
should know" *was*), so the disclaimer leaked into the body — which (a) inflated
link-only pointers past `MIN_BODY_CHARS`, defeating the wrapper-skip, and (b)
polluted substantive notes' stored text + embeddings. Added trailing-cuts for
`IMPORTANT NOTICE: This communication is issued by` / `By continuing to use our
services` / generic `This communication is (intended|confidential|not intended
for distribution)` / BofA `This marketing material was prepared by` / `This
message may contain information that is privileged`. Verified on the real bodies
(ANZ "What's Priced In" now sanitizes 637→131 chars → wrapper-skips; Morning
Focus / FinanceAM / Spot Views keep content, drop the tail). +3 regression tests
in `test_email_doc.py`. Lesson: tune the body-stage gates from real bodies, not
subjects.

**Dropping the genuinely-thin pointers (2026-06-22 / 23):**
* **ANZ `What's Priced In`** — body is link-only ("Open this report" + sign-off).
  After the footer fix it sanitizes to ~131 chars → already `wrapper-skip`s, no
  rule needed.
* **Westpac `Chartpacks`** — carries enough bullet text (chart-pack PDF links +
  one-line annotations) to dodge the wrapper-skip (681 chars), so it gets an
  explicit `chartpack` noise rule (`\bchart\s?packs?\b` in `email_noise_reason`)
  — the substance is in auth-gated chart PDFs we can't fetch, consistent with the
  portal pipeline's chart-pack de-prioritisation.
* **Teaser cover-note + report link** (2026-06-23) — e.g. DB `[/] … What a 'deal'
  means for Asia`: a 2-3 sentence cover note + a `research.db.com/TinyUrl` link to
  the real 13-page report. The title doesn't token-match the report (so the
  fuzzy portal-twin matcher misses it) and the body cleared the wrapper-skip
  (inflated by an uncut DB confidentiality footer). Fixed by (a) cutting the DB
  footer (`This e-mail may contain confidential` / `Privacy of communications`)
  so the teaser shrinks to its true ~657 chars, and (b) a **portal-pointer gate**
  in `build_email_document`: a sanitized body `< POINTER_MAX_CHARS` (700) that
  contains a report-download link (`/TinyUrl/`, `opentoken`,
  `SingletrackCMS__DownloadDocument`, `neo.ubs.com/r/`, `streetcontxt`) → returns
  `skip(portal_pointer)`. Keys on body STRUCTURE, not subject — so it catches
  differing-title cover-notes while leaving long desk notes alone (verified: 1
  flagged across 146 staged bodies, 0 false positives). One such row (11613) had
  already loaded on 2026-06-22 → retro-cleaned (corpus 113 → 112).
* Also strip the **Westpac anti-phishing banner** ("Westpac will never send you a
  link…View online") in the sanitizer — it prepends ~270 chars to *every* Westpac
  email (incl. substantive FinanceAM). +2 regression tests (`test_email_doc`,
  `test_outlook_adapter`). 66 email unit tests total.

## Status — built vs pending

* ✅ 16-folder map (CBA/CACIB held), lenient noise gate, source_type
  (body-disclaimer → vendor-default → sender), email→Document adapter, CBA +
  keyword classifiers, dry-run + minimal `--load`, 71 unit tests
  (adapter 27, dedup-merge 7, keyword-classifier 15, email-doc 19,
  pipeline dedup-branches 3).
* ✅ migration 099 applied + verified; `internet_message_id` dedup gate live.
* ✅ bank-by-bank link/artifact smoke + dedup smoke vs live corpus.
* ✅ **full `--load` pipeline** — `ingest_email_one()` (chunk → embed → upload
  → DB → Qdrant), one command, proven end-to-end (id=10870).
* ✅ **artifact in the SharePoint tree** — body `.html` under
  `ResearchData1/IMDR/{YYYY}/{MM}/{DD}/{vendor}/`, identical layout to portal
  (`upload.upload_bytes` + `build_sharepoint_path(ext=...)`).
* ✅ **fuzzy portal-twin dedup-merge** (`dedup_merge.find_portal_twin`,
  Jaccard, precision-first) — validated on the 2-week backfill: 9 DB dups
  skipped, 0 false positives.
* ✅ **2-week backfill smoke** (Citi + DB) — bulk-stage → load → merge,
  clean 36-row corpus.
* ✅ **review-stage hardening (2026-06-22)** — unit-test backfill (66 total);
  full 14-folder week estimate; **body-grounded sanitizer fixes** (ANZ/BofA
  disclaimer `_TRAILING_CUTS` + Westpac anti-phishing banner strip) so link-only
  pointers wrapper-skip + substantive dailies (Morning Focus/FinanceAM/Spot
  Views) are kept; `chartpack` noise rule for link-only chart packs.
* ✅ **first multi-vendor production load (2026-06-22)** — 7-day desk-core
  (db/citi/jpm/stanc[SCB+STANC]/ms/hsbc/bofa/nomura, 2026-06-15→22): route-B
  staged 108 in-window via parallel MCP agents (verbatim bodies), then `--load`
  wrote **77 net-new / 0 failed in 76s** (17 portal-twins + 14 db-dedups + 4
  hash-dups gated out). Email corpus 36 → **113 rows** (104 desk_commentary + 9
  research). BofA ~31 of the 77 (desk pings); high-signal slice ~46.
* ⏳ per-vendor subject parsers (classification accuracy on net-new rows).
* ⏳ core-headline extraction (recall boost: catch differing-masthead twins).
* ⏳ route-A Graph API (unattended producer; `.eml` artifact + real PDF bytes).
* ⏳ `dim_vendor` rows for `cba` + `cacib`; orchestrator wiring (user-gated).
