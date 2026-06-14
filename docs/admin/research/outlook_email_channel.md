# Outlook email — research acquisition channel

**Status: prototype (route-B), 2026-06-15. Code-complete + dry-run-validated; NOT wired into any orchestrator; migration 099 NOT applied; `--load` not yet implemented.**

A *second acquisition channel* for sell-side research, alongside the
per-vendor portal scrapers ([`scrapers/`](scrapers/)). Research that
arrives by **email** in the `research@rvcapital.com` mailbox — already
hand-filtered by the user's Outlook rules into per-bank folders — is read,
normalised, and pushed through the **same** parse → chunk → embed → write
pipeline as portal PDFs, tagged with provenance so every row knows it came
from email.

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
Nomura·Winkelmolen, BofA·Sidhva, HSBC "The Floor") — body-only,
EM-rates/FX-rich, and not published on any portal we scrape.

## Mailbox + folders

`research@rvcapital.com` (shared/delegated). `Research/` has **13 per-bank
child folders** mirroring the SharePoint tree. 1-month volumes (last 30
days, 2026-06-15) and folder→vendor map:

| Folder | vendor_code | ~30-day | Folder | vendor_code | ~30-day |
|---|---|--:|---|---|--:|
| GS   | `goldman` | 622 | JPM  | `jpm`      | 19 |
| ANZ  | `anz`     | 190 | Citi | `citi`     | 13 |
| BOFA | `bofa`    | 72  | Barc | `barclays` | 11 |
| HSBC | `hsbc`    | 68  | SCB  | `stanc`    | ~50 |
| MS   | `ms`      | 60  | UBS  | `ubs`      | ~12 |
| DB   | `db`      | 59  | Nom  | `nomura`   | 21 |
| CBA  | `cba` ⚠   | 56  |      |            |    |

**≈ 1,250 research emails/month; GS alone is ~50%.** ⚠ `cba` has no portal
scraper — email is its only channel (new `classifiers/cba.py` + dim_vendor
row needed).

> Folder-name lookup in the M365 search tool caps out before the
> alphabetically-last folders (SCB/UBS) — read those by folder **ID** via
> `read_resource mail:///folders/{id}`.

## Access model — route B now, route A later

The Microsoft 365 MCP is a **Claude-side** tool; the unattended Python
pipeline can't use it. So:

* **Route B (current):** Claude pulls emails via the M365 MCP and writes
  one JSON per message (+ non-inline attachment bytes) into
  `playground/research/outlook/staging/{vendor}/`. The Python crawler reads
  **only** that staging dir. Validates classification + dedup on live mail
  with zero Azure work.
* **Route A (future, unattended):** an Azure AD app registration
  (`Mail.Read` on `research@rvcapital.com`, `msal`) lets a Python job
  populate the same staging shape on a cron. The crawler is identical
  either way — only the producer changes. → needs `imdr-security` for the
  app reg.

## Delivery archetypes → extraction

| Archetype | Example senders | Real PDF? | Stored as |
|---|---|---|---|
| Attached-PDF research | `*.cba.com.au`, `HSBC.Research@hsbcib.com`, SCB `Eric.Robertsen` (SMS) | ✅ attachment | the PDF; body → `context` |
| Clean HTML note | `research@anz.com` (summary + portal docRef link) | ❌ | rendered PDF |
| Desk/sales commentary | `walter.wong@db.com`, `zeke.koh@citi.com`, `John.Szto@sc.com`, `remo.winkelmolen@nomura.com`, `jamshed.d.sidhva@bofa.com`, HSBC "The Floor" | ❌ | rendered PDF |
| Portal digest / marketing | `*.alerts.publishing.gs.com`, `resweb@morganstanley.com`, `ubs_research@ubs.com`, Barc marketing | ❌ (inline charts only) | body summary text; portal crawler owns the PDF |

## email → Document + the pdf_path artifact

The pipeline operates on [`ingest/models.py:Document`](../../../playground/research/ingest/models.py).
The adapter [`ingest/email_doc.py`](../../../playground/research/ingest/email_doc.py)
builds it two ways:

* **Attached PDF** → `parse_pdf(bytes)` → normal `Document` (`content_hash`
  = SHA-256 of PDF bytes); sanitized body → `ReportMeta.context`.
* **Body-only** → sanitize `body_html` (strip CAUTION banner + legal/footer
  tails) → synthesize a `Document` for chunk/embed (`content_hash` =
  SHA-256 of the **stable sanitized source**, `parser_version="email-html-v1"`).

**`pdf_path` stays `NOT NULL` — every email report keeps a stored artifact.**
Body-only emails have no vendor PDF, so the pipeline **renders one**:
sanitized body HTML + inline chart images embedded as base64 data URIs →
playwright `set_content` → `page.pdf()` (the same mechanism as Goldman
`render_mode="html"` in [`ingest/fetch.py`](../../../playground/research/ingest/fetch.py)).
The rendered PDF is written under the normal SharePoint path convention and
`pdf_path` records it — so email research is a first-class PDF, uniform with
the portal corpus. `content_hash` (dedup) comes from the stable sanitized
source, **not** the rendered bytes, so re-renders never create false dupes.

## Relevance — lenient by design

The folders are already hand-filtered by the user's Outlook rules, so the
email path does **NOT** run the portal single-name-equity filter
([`relevance.py`](../../../playground/research/ingest/relevance.py)). Its
only gate is `crawler_outlook.email_noise_reason(subject)` — a small
admin/marketing/media/digest drop-list (webcasts, calendars, "Most Read"
digests, ratings recaps, Extel surveys, podcasts/videos, thin data blasts).

Validated on an 87-subject month sample (2026-06-15): **19/87 (22%)
flagged, all correct**; UBS folder kept 0 (pure portal-digest, drop-all).

## source_type — research vs desk_commentary

`crawler_outlook._derive_source_type` decides, in priority order: explicit
staging value → archetype → body "NOT RESEARCH" disclaimer → **sender
heuristic** (research aliases like `macro@alerts…`/`HSBC.Research@`/
`ubs_research@` → `research`; named-person@desk-domain or `[/]`-prefixed
subjects → `desk_commentary`). The sender heuristic means provenance is
correct even before any body is parsed.

## Classification

Email refs lack the structured facets portal classifiers depend on
(`girAssetTypes`, `companies[]`, …). So:

* `cba` (no portal classifier) → keyword classifier
  [`classifiers/email_common.py`](../../../playground/research/ingest/classifiers/email_common.py)
  (registered in `classifiers/__init__.py`).
* Other vendors → try the portal classifier; if it returns an empty
  `asset_class`, fall back to the email keyword classifier.

**Known limitation:** subject-only classification is weak (~50% asset_class
unknown on the month sample); **bodies are required** for good results
(full-body fixtures classify correctly). Phase-2 cheap win: per-vendor
**subject parsers** — SCB `(KRW Rates)`/`(India Macros)`, DB `DB Asia:
Korea/Singapore`, Nomura `EUR Rates Strategy` encode asset class + country
structurally in the subject.

## Dedup rules

1. PDF already in `dim_report` (by `content_hash`) → don't re-store the
   PDF; if the email body has unique commentary, store the body instead.
2. Pure notification wrapper (no substantive body) → skip.
3. Any HTML body that IS a proper research note → store.
4. Email-level dedup on `internet_message_id` (skip already-ingested).

## Schema — migration 099 (additive; NOT applied)

[`migrations/099_research_dim_report_email_channel.sql`](../../../migrations/099_research_dim_report_email_channel.sql)
adds to `research.dim_report`:

| Column | Type | Notes |
|---|---|---|
| `source` | `varchar(16)` NOT NULL DEFAULT `'portal'` | `'portal'` \| `'email'` — back-labels all existing rows as portal |
| `source_type` | `varchar(20)` NOT NULL DEFAULT `'research'` | `'research'` \| `'desk_commentary'` |
| `internet_message_id` | `varchar(255)` NULL | RFC-2822 Message-ID; filtered-UNIQUE index `ix_research_dim_report_imi WHERE NOT NULL` |

**`pdf_path` is NOT touched — stays NOT NULL** (every email report saves a
rendered-PDF artifact). Purely additive: no drops, no data loss, no row
rewrite. Verified against the live schema by `imdr-dbm`. **Not applied —
DDL on IMDR awaits explicit user OK.**

## Code map

| File | Purpose |
|---|---|
| [`ingest/crawler_outlook.py`](../../../playground/research/ingest/crawler_outlook.py) | staging reader → `OutlookReportRef`; folder→vendor map; `_derive_source_type`; `email_noise_reason`; `decide_dedup` |
| [`ingest/email_doc.py`](../../../playground/research/ingest/email_doc.py) | HTML sanitizer + synthetic-Document builder + artifact selection |
| [`ingest/classifiers/email_common.py`](../../../playground/research/ingest/classifiers/email_common.py) | keyword classifier (word-boundary scored) |
| [`ingest/classifiers/cba.py`](../../../playground/research/ingest/classifiers/cba.py) | CBA classifier (AU/MACRO default) |
| [`ingest_outlook.py`](../../../playground/research/ingest_outlook.py) | dry-run CLI (`--no-load` default; `--load` reserved) |
| [`tests/unit/research/test_outlook_adapter.py`](../../../tests/unit/research/test_outlook_adapter.py) | 16 unit tests (sanitizer, synth-Document, folder map, cba, noise gate, source_type, dedup) |

## Running the dry-run

```
python playground/research/ingest_outlook.py            # all staged vendors
python playground/research/ingest_outlook.py --vendors cba,citi
```

Prints a per-message table (vendor, archetype, source_type, asset_class,
country, doc_path, decision). Writes nothing to DB/SharePoint/Qdrant;
`--load` is reserved until migration 099 is applied + the render-to-PDF
writer is built.

## Status — built vs pending

* ✅ crawler, lenient noise gate, sender-based `source_type`, email→Document
  adapter, CBA + email keyword classifiers, dry-run CLI, 16 unit tests,
  month-scale validation (volumes + drop-list + classification).
* ✅ migration 099 written (provenance only), **not applied**.
* ⏳ render-to-PDF artifact writer + `--load` (gated on migration 099).
* ⏳ route-A Graph API for unattended pulls + bodies/attachments at scale.
* ⏳ orchestrator wiring (per hard rule: not until user flips the switch).
