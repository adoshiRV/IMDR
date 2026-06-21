# Outlook email — research acquisition channel

**Status: prototype (route-B), updated 2026-06-19. Migration 099 APPLIED; FULL `--load` pipeline IMPLEMENTED (classify → portal-twin dedup-merge → chunk → embed → upload `.html` to the SharePoint tree → MSSQL `source='email'` → Qdrant), one command. Validated by a 2-week Citi+DB backfill smoke: 41 loaded, fuzzy merge skipped 9 portal-dup re-forwards with 0 false positives, clean 36-row corpus. Artifacts land in `ResearchData1/IMDR/` identical to portal. NOT wired into any orchestrator; route-A (Graph) producer + per-vendor subject parsers are the next builds.**

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

> Folder-name lookup in the M365 search tool is unreliable for nested
> folders — read folders by **ID** via `read_resource mail:///folders/{id}`.
> The shared-mailbox REST search (`mailboxOwnerEmail`) currently 404s
> (`MailboxNotEnabledForRESTAPI`); the folders are reachable in the
> delegate's own mailbox instead.

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
data blasts, "thematics framework", **login/OTP/verification** (login codes,
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
5. Adapter-level (`decide_dedup`): pure notification wrapper (no substantive
   body) → skip; PDF whose hash exists → retry body-only.

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
| [`ingest/crawler_outlook.py`](../../../playground/research/ingest/crawler_outlook.py) | staging reader → `OutlookReportRef`; folder→vendor map; `EMAIL_VENDOR_HOLD`; `_derive_source_type`; `email_noise_reason`; `decide_dedup` |
| [`ingest/email_doc.py`](../../../playground/research/ingest/email_doc.py) | HTML sanitizer + synthetic-Document builder |
| [`ingest/classifiers/email_common.py`](../../../playground/research/ingest/classifiers/email_common.py) | keyword classifier (word-boundary scored) |
| [`ingest/classifiers/cba.py`](../../../playground/research/ingest/classifiers/cba.py) | CBA classifier (AU/MACRO default) |
| [`ingest/engine.py`](../../../playground/research/ingest/engine.py) | shared ODBC Driver 18 engine factory (used by `ingest_one.py` + `ingest_outlook.py`) |
| [`ingest/db.py`](../../../playground/research/ingest/db.py) | `write_report()` — gained `source`/`source_type`/`internet_message_id` params + the imi dedup gate |
| [`ingest/dedup_merge.py`](../../../playground/research/ingest/dedup_merge.py) | `find_portal_twin()` — fuzzy email→portal title match (Jaccard) so desk re-forwards of portal notes are skipped |
| [`ingest/email_pipeline.py`](../../../playground/research/ingest/email_pipeline.py) | `ingest_email_one()` — full per-message pipeline (portal-twin gate → chunk → embed → upload → DB → Qdrant); the ~10x-simpler analogue of `pipeline.ingest_one` |
| [`ingest_outlook.py`](../../../playground/research/ingest_outlook.py) | dry-run + full `--load` CLI (`--no-embed`, `--limit`, `--keep-portal-twins`); the `ingest_today.py` analogue |
| [`tests/unit/research/test_outlook_adapter.py`](../../../tests/unit/research/test_outlook_adapter.py) + [`test_dedup_merge.py`](../../../tests/unit/research/test_dedup_merge.py) | adapter sanitizer/synthesize/folder-map/source_type/decide_dedup (25) + dedup-merge jaccard/tokens (7) |
| [`tests/unit/research/test_email_common_classifier.py`](../../../tests/unit/research/test_email_common_classifier.py) | keyword classifier: per-class scoring, commodities-specificity guard, no-stem word-boundary, country/region scan, theme/author tags (15) |
| [`tests/unit/research/test_email_doc.py`](../../../tests/unit/research/test_email_doc.py) | adapter edges: earliest-cut boilerplate, `DESK_DISCLAIMER_RE`, `best_body_text` summary fallback, `build_email_document` synthetic/skip/pdf_missing, inline-attachment skip (11) |
| [`tests/unit/research/test_email_pipeline.py`](../../../tests/unit/research/test_email_pipeline.py) | `ingest_email_one` dedup short-circuits: imi-idempotency + portal-twin skip, fake Engine + monkeypatched twin (3) |

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

## Status — built vs pending

* ✅ 16-folder map (CBA/CACIB held), lenient noise gate, source_type
  (body-disclaimer → vendor-default → sender), email→Document adapter, CBA +
  keyword classifiers, dry-run + minimal `--load`, 61 unit tests
  (adapter 25, dedup-merge 7, keyword-classifier 15, email-doc edges 11,
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
* ⏳ per-vendor subject parsers (classification accuracy on net-new rows).
* ⏳ core-headline extraction (recall boost: catch differing-masthead twins).
* ⏳ route-A Graph API (unattended producer; `.eml` artifact + real PDF bytes).
* ⏳ `dim_vendor` rows for `cba` + `cacib`; orchestrator wiring (user-gated).
