# Outlook email — research acquisition channel

**Status: prototype (route-B), updated 2026-06-18. Migration 099 APPLIED; minimal `--load` IMPLEMENTED (writes `source='email'` `dim_report` rows, no chunks/embeds/Qdrant/SharePoint yet); NOT wired into any orchestrator.**

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

**`pdf_path` stays `NOT NULL` — every email report keeps a stored artifact.**
*Current minimal `--load`:* body-only emails save the sanitized body as a
`.txt` under `playground/research/outlook/rendered/{vendor}/` and `pdf_path`
records that repo-relative path (prototype). *Production target:* render the
body (HTML + inline charts as base64) via playwright `set_content` →
`page.pdf()` and upload to the normal SharePoint path, so email research is a
first-class PDF uniform with the portal corpus. `content_hash` comes from the
stable sanitized source, **not** rendered bytes, so re-renders never dupe.

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

Email path (in `write_report`, primary→backstop order):

1. **`internet_message_id`** already in `dim_report` → skip (the migration-099
   filtered-unique key; the PRIMARY email gate).
2. `content_hash` already present → skip.
3. `(vendor_id, publish_date, LOWER(title))` match → skip (catches the same
   report under a different message-id / a portal copy with the same title).
4. Adapter-level (`decide_dedup`): pure notification wrapper (no substantive
   body) → skip; PDF whose hash exists → retry body-only.

> **TODO (dedup-merge):** exact title+date dedup catches portal-overlap only
> when titles match exactly (Westpac/ANZ did; GS/HSBC/Barclays teasers use a
> reworded title). A fuzzy title / `pdf_text`-similarity merge against
> `source='portal'` rows is needed before bulk-loading the Lane-3 (portal-
> overlap) vendors. The current minimal load targets net-new desk items where
> no portal collision is possible.

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
| [`ingest_outlook.py`](../../../playground/research/ingest_outlook.py) | dry-run + `--load` CLI (`--limit` safety cap) |
| [`tests/unit/research/test_outlook_adapter.py`](../../../tests/unit/research/test_outlook_adapter.py) | 25 unit tests |

## Running

```
python playground/research/ingest_outlook.py                          # dry-run, all staged
python playground/research/ingest_outlook.py --vendors citi            # dry-run, one vendor
# Actual write (uses the imdr conda env for pyodbc + ODBC Driver 18):
C:/Users/adoshi/.conda/envs/imdr/python.exe playground/research/ingest_outlook.py --load --vendors citi --limit 1
```

`--load` writes a minimal `source='email'` `dim_report` row per net-new
email and is idempotent (re-runs DB-DEDUP on `internet_message_id`). First
real load: 2 Citi desk notes (ids 10475/10476, `desk_commentary`/RATES).

## Status — built vs pending

* ✅ 16-folder map (CBA/CACIB held), lenient noise gate, source_type
  (body-disclaimer → vendor-default → sender), email→Document adapter, CBA +
  keyword classifiers, dry-run + minimal `--load`, 25 unit tests.
* ✅ migration 099 applied + verified; `internet_message_id` dedup gate live.
* ✅ bank-by-bank link/artifact smoke + dedup smoke vs live corpus.
* ⏳ chunk + embed + Qdrant for email rows (currently dim_report row only).
* ⏳ render-to-PDF artifact + SharePoint upload (currently a local `.txt`).
* ⏳ fuzzy dedup-merge vs portal rows (before loading Lane-3 vendors).
* ⏳ per-vendor subject parsers (classification accuracy).
* ⏳ route-A Graph API (unattended pulls + real PDF bytes).
* ⏳ `dim_vendor` rows for `cba` + `cacib`; orchestrator wiring (user-gated).
