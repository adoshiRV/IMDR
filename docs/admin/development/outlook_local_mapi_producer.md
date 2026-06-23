# Outlook email ingest — local MAPI/COM producer (cost overhaul)

**Status: BUILT — P0–P3 done, P4 measured (2026-06-23).** The producer
(`playground/research/outlook/outlook_mapi_pull.py`) works end-to-end: dry-run +
real staging across the folder→vendor map, real PDF capture, per-folder HWM, and
the crawler consumes its JSON unchanged. Parity measured (see §5/P4): cutover is
imi-gated, not hash-gated. **Remaining before cutover (needs user OK — touches the
prod corpus): a `--no-embed` live load smoke, then default-producer switch +
retire route-B.** (Linear filing skipped per user.)

**Goal:** replace the route-B (Claude + M365 MCP) email *producer* with a local
Python Outlook **MAPI/COM** producer so a 7-day (or daily) ingest costs **~0 LLM
tokens** instead of ~1M, needs **no Azure app registration**, and additionally
captures **real PDF attachment bytes**. The crawler + `--load` pipeline are
unchanged — only the thing that writes `staging/` changes.

---

## 1. Problem / motivation

The email channel splits into **capture** (get the body onto disk) and **process**
(sanitize → chunk → embed → dedup → DB/Qdrant). Process is already pure Python and
cheap (`ingest_outlook.py --load` did 77 articles in 76s). **All the cost is
capture**, and only because route-B captures via an LLM:

- The M365 MCP `read_resource` returns each email body **into the model's context**,
  then the staging agent **re-emits** that body into the Write tool. Every byte of
  every email passes through the LLM **twice** (input + the more-expensive output).
- **Measured (2026-06-22 desk-core week):** ~1.0M LLM tokens to stage ~108 articles
  ≈ **9–13k tokens per net-new article**, and it **recurs every run**.
- Secondary route-B limits: the MCP folder listing **caps ~45 msgs, no date filter,
  no paging** (GS firehose can't reach a week back); `read_resource` returns
  attachment **text only, never bytes** (the 3 PDF-attaching vendors — CBA, Nomura
  ~35%, DB-PM — degrade to `synthetic_body(pdf_missing)`).

This is unsustainable for a recurring feed. See the cost analysis in
[`../research/outlook_email_channel.md`](../research/outlook_email_channel.md).

## 2. Key realisation

The mail is **already local.** Outlook caches the whole `research@rvcapital.com`
shared mailbox in an **`.ost`** (`%LOCALAPPDATA%\Microsoft\Outlook\*.ost`), synced
and authenticated by the running Outlook. There is no reason to round-trip to the
cloud (MCP/Graph) or through an LLM at all — a local process can read the bodies
straight off disk via Outlook's MAPI interface.

## 3. Options analysed

| producer | LLM tokens | admin / new auth | PDF attachment bytes | folder cap / paging |
|---|---|---|---|---|
| **B — M365 MCP (today)** | ~9–13k/article | none | ❌ text only | capped ~45, no date filter |
| **A — Microsoft Graph** | ~0 | **Azure app registration** (`Mail.Read`, client secret) | ✅ `/$value` | ✅ |
| **Playwright vs OWA** | ~0 | none (reuses login) | hard | ✅ |
| **C — local MAPI/COM** ✅ | **~0** | **none** (uses live Outlook profile) | **✅ `SaveAsFile()`** | **✅ `.Restrict()`** |

**Decision: route C (local MAPI/COM).** It dominates: zero tokens like Graph, but
**no app registration** (uses the already-logged-in profile — arguably *more*
secure, no external secret created), **captures real PDF bytes locally** (closes
the route-A-only gap), and **fixes the cap/paging** via server-side `Restrict`. It
runs in the same place the rest of the pipeline already does (the user's Windows
box, imdr conda env, beside the OneDrive SharePoint sync) — no cloud hop.
Trade-off: Windows + Outlook-desktop only, and Outlook must be running with the
shared mailbox mounted (true today). A `pypff`/`libpff` reader against the `.ost`
is the headless fallback if Outlook-closed operation is ever needed.

## 4. Design

### 4.1 Producer script
`playground/research/outlook/outlook_mapi_pull.py` (prototype lives in the
gitignored playground beside the rest of the channel; promote to `scripts/` when the
channel graduates to prod). Pure `pywin32` COM; **no change to
`crawler_outlook.py` / `email_doc.py` / `ingest_outlook.py`** — it just writes the
same `staging/{vendor}/{slug}.json` contract.

### 4.2 COM access pattern
**P0-confirmed (2026-06-23):** the vendor folders live under the user's **own
mailbox store** (`adoshi@rvcapital.com/Research/<vendor>`), NOT a separate shared
store. `GetSharedDefaultFolder("research@rvcapital.com", …)` raises *"the server
mailbox cannot be opened because this address book entry is not a mail user"* —
the `research@` mail is delivered into the user's own store and filed under
`Research/`. So navigate the store by display name:
```python
import win32com.client
ns = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
store = next(f for f in ns.Folders if f.Name == "adoshi@rvcapital.com")
research = store.Folders["Research"]
for vfolder in research.Folders:                 # GS, MS, DB, Citi, SCB, STANC, ...
    items = vfolder.Items
    items.Sort("[ReceivedTime]", True)
    items = items.Restrict("[ReceivedTime] >= '06/15/2026'")  # locale short-date
    for m in items:
        if m.Class != 43:        # olMail — skip meeting/report items
            continue
        ...  # build staging JSON
```
`Restrict` date strings are **locale-sensitive** — `%m/%d/%Y` worked on this host;
format as the host's short-date defensively. Make `--mailbox` default to the own-
mailbox store name, not `research@`. (Spike: `playground/research/outlook/_p0_com_spike.py`.)

### 4.3 Field mapping → staging contract
| staging key | COM source |
|---|---|
| `internet_message_id` | `m.PropertyAccessor.GetProperty("http://schemas.microsoft.com/mapi/proptag/0x1035001F")` (PR_INTERNET_MESSAGE_ID) |
| `graph_id` | `m.EntryID` (MAPI entry id; rename field or keep `graph_id` for contract parity) |
| `folder` | `vfolder.Name` |
| `vendor_code` | folder→vendor map (reuse `crawler_outlook.FOLDER_TO_VENDOR`) |
| `subject` | `m.Subject` |
| `sender` | `{name: m.SenderName, address: m.SenderEmailAddress}` (resolve EX→SMTP via `PropertyAccessor` PR_SMTP_ADDRESS when `SenderEmailType=='EX'`) |
| `to` / `cc` | iterate `m.Recipients` → `{name: r.Name, address: r.Address}` (resolve EX→SMTP); split on `r.Type` (1=To, 2=Cc) |
| `received` | **⚠ see P0 finding** — `m.ReceivedTime` returns host-**local** wall-clock but pywin32 mislabels its tzinfo as `+00:00`; trusting it records times `host_offset` late (8h on this UTC+8 box). Fix: `rt.replace(tzinfo=host_local_tz).astimezone(timezone.utc)` (verified == `PR_MESSAGE_DELIVERY_TIME 0x0E060040`, the true-UTC cross-check). Then `.strftime('%Y-%m-%dT%H:%M:%SZ')`. |
| `body_content_type` | `"html"` |
| `body_html` | `m.HTMLBody` (full verbatim HTML — **must be byte/sanitiser-equivalent to the MCP `body.content`**, see §5 parity) |
| `attachments` | iterate `m.Attachments` → `{name, content_type, size, is_inline}`; for real (non-inline) PDFs **`att.SaveAsFile(staging/<vendor>/attachments/<sha8>.pdf)`** and set `file` to that relative path |

### 4.4 Attachments → real PDF artifacts
COM exposes attachment bytes locally. For `att.Type == 1` (olByValue) real-file
PDFs, `SaveAsFile` into `attachments/`; the existing
`email_doc.build_email_document` already prefers a staged PDF (`parse_pdf`) over the
synthetic body — so CBA/Nomura/DB-PM become first-class `.pdf` rows with **no
pipeline change**.

**⚠ P0 finding (2026-06-23):** do NOT gate PDF-saving on the inline flag. DB's PM
Summary attaches the **real PDF with a content-id set** (`PR_ATTACH_CONTENT_ID`
non-empty → my naïve "inline" probe returned `True` for a 97 KB `.pdf`). The right
discriminator is **`Type == 1` AND filename ends `.pdf` AND size > a few KB**, not
the CID/inline flag. Inline *images* (`image001.gif`, `image_*.png` — the GS chart
PNGs) are also `Type == 1` with a CID, so the `.pdf`-extension + size test is what
separates a real report attachment from rendered chart images. The staging
contract still records `is_inline` as metadata for all of them.

### 4.5 Incremental high-water-mark
Persist per-folder last-ingested `ReceivedTime` (e.g. `outlook/.hwm.json`). Default
run fetches only messages newer than the mark (`--since` overrides for backfill).
Turns "108 bodies/run" into "~10–15/day". `internet_message_id` dedup at load is the
safety net, so the HWM is a fetch optimisation, not a correctness dependency.

### 4.6 CLI
`--since / --until` (window, default = HWM→now), `--vendors`, `--folders-root`
(default `Research`), `--mailbox` (default `research@rvcapital.com`),
`--no-attachments`, `--dry-run` (list what it *would* stage, write nothing).

## 5. Testing & parity

- **Unit (tracked, `tests/unit/research/`):** field mapping (EX→SMTP resolution,
  recipient split, ISO received), `Restrict` date-string builder (locale), slug
  scheme, attachment metadata + save-path logic. Mock the COM objects (duck-typed
  `SimpleNamespace`) — no live Outlook in unit tests.
- **Parity check (`_p4_parity_check.py`, RUN 2026-06-23):** staged the same DB
  messages via both producers and compared sanitised-body `content_hash`.
  **Result: 0/4 match — and that's expected/benign.** The route-B (Claude relay)
  bodies were **truncated** (re-emit was lossy); the MAPI `HTMLBody` is the full
  verbatim body (PM Summary 5680c vs MCP 2566c, *same text* + the missing tail).
  So:
    - **content_hash parity is NOT the cutover gate** (it can't hold — MAPI is more
      complete). The cutover-safety basis is the **`internet_message_id` gate**
      (dedup gate #1): every loaded email row has a distinct populated imi, so a
      MAPI re-run of already-loaded mail skips on imi regardless of hash. Verified:
      2 of the 4 overlaps already in `dim_report` → would skip.
    - MAPI bodies are a **fidelity win** over route-B (no relay truncation).
  Genuine "Outlook re-encodes" deltas (if any beyond truncation) wash out in the
  sanitiser's `_collapse_ws`; none seen.
- **Integration:** MAPI-staged → `ingest_outlook.py --dry-run` parity vs the
  06-15→22 desk-core; then a `--no-embed` load smoke on 1–2 vendors.

## 6. Build phases (checklist)

- [x] **P0 spike** — DONE 2026-06-23 (`_p0_com_spike.py`). COM reaches all **16**
  `Research/*` folders (matches `FOLDER_TO_VENDOR` exactly; GS=5088 items, DB=470,
  SCB=815; Barc/STANC/BOFA/CACIB/Westpac currently empty) via the **own-mailbox
  store** (see §4.2 correction). Read every contract field for DB/GS: `Subject`,
  `ReceivedTime` (tz-aware), `PR_INTERNET_MESSAGE_ID` (clean `<…@…>`), `SenderName`
  + SMTP (external vendors already `SenderEmailType=='SMTP'` → EX-resolution mostly
  moot for vendor folders), `Recipients` To/Cc split, full `HTMLBody` (17k–135k
  chars), and `Attachments` (name/type/size/inline). Two findings folded in: §4.2
  (store nav, not `GetSharedDefaultFolder`) + §4.4 (real PDFs flagged inline →
  discriminate by `.pdf`+size) + the `received` row in §4.3 (**`ReceivedTime` is
  host-local mislabeled `+00:00` — reinterpret as host-local → UTC; verified ==
  `PR_MESSAGE_DELIVERY_TIME`**). All open P0 items resolved.
- [x] **P1 producer** — DONE 2026-06-23. `outlook_mapi_pull.py` writes the staging
  contract for a `--since/--until` window across the folder→vendor map (imports
  `FOLDER_TO_VENDOR`/`EMAIL_VENDOR_HOLD` from `crawler_outlook`; per-message
  `build_record`). Dry-run across all 14 active folders = 23 staged (CBA/CACIB
  held); a real `--vendors db` run wrote 7 contract-valid JSON files that
  `discover_reports` + `ingest_outlook.py --dry-run` consume identically (7
  ingestable, correct `desk_commentary`/asset-class/country). CLI: `--mailbox
  --folders-root --staging-dir --since --until --vendors --no-attachments
  --dry-run --limit`.
- [x] **P2 attachments** — DONE 2026-06-23. `SaveAsFile` (absolute native path —
  it rejects relative/forward-slash) saved the 3 DB PM-Summary PDFs as real
  `%PDF-1.4` bytes (~96 KB). Two small fixes in `email_doc.py` made them load as
  `pdf` not `synthetic_body(pdf_missing)`: (a) `_first_pdf_attachment` now accepts
  a saved-`file` PDF even when inline-flagged (DB's CID case); (b)
  `build_email_document` resolves the vendor-relative `file` against the JSON's own
  dir (`ref._staging_file`'s parent), fixing a latent path bug that route-B never
  hit (it never staged bytes). DB-PM now → `pdf`; body-only notes stay
  `synthetic_body`. (Nomura/CBA not exercised — no in-window mail; same code path.)
- [x] **P3 incremental** — DONE 2026-06-23. Per-folder HWM at `outlook/.hwm.json`
  (`{"DB": "2026-06-22"}` after the run); default `since = --since or HWM[folder]
  or 7d-ago`. imi-dedup is the correctness net, HWM is the fetch optimisation.
- [~] **P4 parity + cutover** — parity MEASURED 2026-06-23 (`_p4_parity_check.py`):
  **content_hash does NOT match** on the 4 overlapping DB messages — but because
  route-B (Claude relay) **truncated** bodies (PM Summary 2566c MCP vs **5680c**
  MAPI; same text, MAPI has the full tail), not because MAPI is wrong. **So the
  cutover-safety basis is the `internet_message_id` gate, not hash parity** — all
  112 loaded email rows have distinct populated imis, and 2 of the 4 overlaps are
  already in `dim_report` (→ skipped on re-load via gate #1). MAPI bodies are
  strictly **higher-fidelity** (route-B was lossy). ⇒ §5 revised: parity is an
  imi-gate guarantee + a "MAPI ≥ MCP completeness" quality win, NOT a hash equality.
  Remaining for cutover: a `--no-embed` live load smoke on 1–2 vendors, then make
  MAPI the default producer + retire the route-B staging procedure (**needs user OK
  — touches the prod corpus**).
- [ ] **P5 (optional)** — `pypff`/`libpff` headless `.ost` reader fallback for
  Outlook-closed/cron operation.

## 7. Risks / caveats

- **Windows + Outlook-desktop only**, Outlook running with `research@` mounted (true
  today; the ingest already runs on this box).
- **COM is single-threaded** against the Outlook process → slower than Graph's bulk
  API, but it's *local + token-free*, so wall-clock is irrelevant for a daily job.
- **EX vs SMTP addresses** — internal senders surface as X.500 EX addresses; resolve
  to SMTP via `PropertyAccessor` (PR_SMTP_ADDRESS `0x39FE001F`) so `_derive_source_type`
  sender heuristics keep working.
- **Locale date strings** in `Restrict` — format to host short-date; add a guard.
- **`HTMLBody` ≠ `body.content`?** Outlook may re-encode HTML on cache; the §5 parity
  test gates cutover precisely to avoid false-dups.
- **Security**: no new credential/scope; reads the local authenticated profile only.
  Lower attack surface than a Graph app secret. (Still: only reads, never writes/moves
  mail — assert no `Move`/`Delete`/`Save` COM calls, mirroring the BBG read-only rule.)

## 8. Success criteria
- A 7-day desk-core ingest runs at **~0 LLM tokens** (producer is pure Python COM). ✅ (P1)
- **No Azure app registration** required. ✅ (P0 — own-profile COM)
- CBA/Nomura/DB-PM attach **real `.pdf`** artifacts (not `pdf_missing`). ✅ DB-PM (P2)
- Reruns are incremental (HWM) and idempotent (imi-dedup). ✅ (P3)
- ~~content_hash parity~~ → **clean cutover via the imi gate** (parity can't hold:
  MAPI bodies are more complete than route-B's truncated relay — a fidelity win). ✅ (P4)

## 9. Relationship to route A (Graph)
Route A (Graph + app-reg) was the previously-planned "unattended producer." Route C
supersedes it for the **interactive/local** case (no admin, captures PDFs, free).
Graph remains the right choice **only** if the ingest must ever run on a host
*without* an Outlook profile (true headless server/cron). Keep route A documented as
the headless option; build route C now.

---

## 10. Current layout reference (what exists today)

> The whole email channel is **prototype code under `playground/research/`, which is
> gitignored** (`.gitignore:43 playground/*`) — it lives on disk only, NOT in version
> control. The **tracked** parts are the unit tests (`tests/unit/research/`) and the
> docs. The new producer is a drop-in: it only needs to write §10.3's contract; it
> touches none of the pipeline below.

### 10.1 Pipeline code map — `playground/research/ingest/` (gitignored)
| file | key symbols / role |
|---|---|
| `crawler_outlook.py` | `discover_reports(staging_dir, *, since, until, vendors)` → `list[OutlookReportRef]`; `OutlookReportRef` (dataclass); `FOLDER_TO_VENDOR`; `EMAIL_VENDOR_HOLD`; `_VENDOR_DEFAULT_SOURCE_TYPE`; `_derive_source_type(rec, archetype, vendor=)`; `email_noise_reason(subject)`; `decide_dedup(ref, doc_path, hash, *, seen, known)`; `_ref_from_record` (staging JSON → ref); `_DESK_SUBJECT_RE`, `_RESEARCH_SENDER_MARKERS` |
| `email_doc.py` | `sanitize_email_html` (strips `_CAUTION_BANNER`, `_WESTPAC_BANNER`, then earliest of `_TRAILING_CUTS`); `build_email_document(ref, *, staging_dir=None)` → `(Document|None, path, body_text)` where path ∈ `pdf` / `synthetic_body` / `skip` / `skip(portal_pointer)` / `synthetic_body(pdf_missing)`; `is_portal_pointer`; `best_body_text`; `_first_pdf_attachment`; `synthesize_document`; `MIN_BODY_CHARS=200`; `POINTER_MAX_CHARS=700`; `DESK_DISCLAIMER_RE`; `EMAIL_PARSER_VERSION="email-html-v1"` |
| `classifiers/email_common.py` | `classify_email(ref, *, vendor_code)` → `ClassifyResult` (keyword asset-class scoring + country/region scan + theme/author tags) |
| `classifiers/cba.py` | thin CBA classifier (AU/MACRO default) |
| `email_pipeline.py` | `async ingest_email_one(*, ref, classify_result, doc, body_text, engine, api_keys, do_embed, embed_model, qdrant_writer, store_pdf_text, skip_portal_twins)` → `EmailIngestResult`. Flow: imi-in-DB precheck → `find_portal_twin` → `chunk_doc` → `embed_chunks` → `upload_bytes` (SharePoint) → `write_report` → Qdrant upsert |
| `dedup_merge.py` | `find_portal_twin(engine, *, vendor_code, publish_date, title)`; `jaccard`; `title_tokens`; `THRESHOLD=0.70`; `PortalTwin` |
| `db.py` | `write_report(conn, meta, doc, chunks, embeddings, tag_ids, model_id, store_pdf_text, source, source_type, internet_message_id)`; `resolve_tag_ids`; `ensure_model_id`. imi dedup gate ahead of content_hash |
| `engine.py` | `research_engine(settings)` — shared SQLAlchemy engine (ODBC Driver 18) |
| `paths.py` | `build_sharepoint_path(*, vendor_code, publish_date, uuid, title="", ext="pdf")` → IMDR-relative path |
| `upload.py` | `upload_bytes(*, data, relative_path)` — writes into the OneDrive-synced IMDR root; `upload_pdf` delegates |
| `qdrant_writer.py` | `QdrantWriter.from_env()`; `.collection_for(model_name, dimensions)`; `.upsert_chunks(...)`; client attr is **`_client`** (delete via `_client.delete(collection, FilterSelector(...))`); `ChunkPoint` |
| `chunk.py` / `embed.py` | `chunk_doc(doc)`; `embed_chunks(chunks, model_name, api_keys)`; `get_spec(model)`; `DEFAULT_MODEL_NAME="gemini-embedding-2"` |
| `models.py` | `Document`, `ReportMeta`, `ClassifyResult`, `Tag` |
| `ingest_outlook.py` (CLI, repo-root of `playground/research/`) | dry-run (default) + `--load`; flags `--staging-dir --vendors --since --until --load --no-embed --embed-model --limit --keep-portal-twins`; `DEFAULT_STAGING = outlook/staging` |

### 10.2 Staging dir — `playground/research/outlook/staging/`
`{vendor}/{slug}.json` per message; real attachments go in `{vendor}/attachments/`.
Exploratory helpers also here (gitignored): `_week_estimate.py`, `_smoke_dedup_analysis.py`,
and per-vendor MCP-staged JSON from the 2026-06-22 backfill. **The MAPI producer
writes into this same tree** (the planned per-folder high-water-mark → `outlook/.hwm.json`).

### 10.3 Staging JSON contract (the producer's output target — keep byte-identical)
```jsonc
{
  "internet_message_id": "<...@...>",   // PRIMARY dedup key → dim_report.internet_message_id
  "graph_id": "AAMk... | <MAPI EntryID>",
  "folder": "DB",                        // Outlook display name (see map below)
  "vendor_code": "db",
  "subject": "...",
  "sender": { "name": "...", "address": "..." },   // address must be SMTP, not EX
  "to":  [ { "name": "...", "address": "..." } ],  // ARRAY OF OBJECTS (not strings)
  "cc":  [ ... ],
  "received": "2026-06-19T05:04:11Z",    // ISO-8601 UTC Z
  "body_content_type": "html",
  "body_html": "...",                    // full verbatim HTML
  "attachments": [
    { "name": "x.pdf", "content_type": "application/pdf",
      "size": 2296681, "is_inline": false, "file": "attachments/<sha8>.pdf" }
  ]
}
```
`_ref_from_record` skips any file missing `internet_message_id` / `subject` / `received`.

### 10.4 Folder→vendor map (exact display-name keys — gotchas)
`FOLDER_TO_VENDOR` = `GS→goldman, MS→ms, CBA→cba, DB→db, SCB→stanc, STANC→stanc,
JPM→jpm, Nom→nomura, ANZ→anz, UBS→ubs, Citi→citi, HSBC→hsbc, Barc→barclays,
BOFA→bofa, Westpac→westpac, CACIB→cacib`. **Watch the abbreviations** —
`Nom` (not Nomura), `Barc` (not Barclays), `BOFA` (caps), `Citi`/`Westpac` (mixed).
**`SCB` and `STANC` are two folders → one vendor `stanc`** (SCB=desk, STANC=formal
research; source_type resolved per message). `EMAIL_VENDOR_HOLD = {cba, cacib}` — the
producer should skip these unless explicitly named (they have no `dim_vendor` row /
portal crawler). `_VENDOR_DEFAULT_SOURCE_TYPE = {bofa:desk_commentary, cba:research,
anz:research, westpac:research, cacib:research}`. The 16 folders sit under
`Research/` in the shared mailbox; the MAPI producer navigates by these **names**.

### 10.5 The `--load` decision flow (what consumes staging — DO NOT change)
`discover_reports` → per ref: `_classify` (portal classifier if it yields a class,
else `classify_email`) → `email_noise_reason(title)` (drop) → `build_email_document`
(skip variants) → `decide_dedup` (in-run seen imi/hash) → `ingest_email_one`
(imi-in-DB → portal-twin → chunk/embed/upload/write/qdrant). Per-run counters:
`ingestable / dropped / skipped / loaded / db_dedup / portal_dup / failed`.

### 10.6 Body-stage gates (in `build_email_document`/sanitizer — recently hardened)
- **Sanitizer cuts**: CAUTION banner; Westpac anti-phishing banner; `_TRAILING_CUTS`
  trailing legal blocks incl. ANZ (`IMPORTANT NOTICE: This communication is issued by`,
  `By continuing to use our services`), BofA (`This marketing material was prepared by`,
  `…privileged`), DB (`This e-mail may contain confidential`, `Privacy of communications`).
- **`skip` (wrapper)**: sanitized body `< MIN_BODY_CHARS (200)`.
- **`skip(portal_pointer)`**: sanitized body `< POINTER_MAX_CHARS (700)` AND raw body
  has a report-download link (`/TinyUrl/|opentoken|SingletrackCMS__DownloadDocument|
  neo.ubs.com/r/|streetcontxt`).
- **`chartpack`** noise rule (`\bchart\s?packs?\b`) in `email_noise_reason`.

### 10.7 `source_type` derivation (authority order) + noise gate
`_derive_source_type`: 1) explicit staging value → 2) body "NOT RESEARCH" disclaimer
→ 3) per-vendor folder default (`_VENDOR_DEFAULT_SOURCE_TYPE`) → 4) archetype → 5)
sender heuristic (research aliases / `research.distribution@sc.com` → research;
person@desk-domain or `[/]`-prefixed → desk) → 6) default research. `email_noise_reason`
labels: summary_alert, ratings_tp, novelty(World Cup), single_name_ideas,
webcast, most_read_digest, training, survey(Extel), media(Video/Podcast), calendar,
data_blast, framework_promo, **chartpack**, login_code/otp/portal_token/
account_verification/password_reset/credentials/portal_admin/marketing.

### 10.8 Dedup gates (cheapest-first)
1. `internet_message_id` already in `research.dim_report` (migration-099 filtered-unique
   idx `ix_research_dim_report_imi`) → skip. 2. `find_portal_twin` (Jaccard ≥0.70, ≥3
   shared tokens, same vendor, ±3 days, vs `source='portal'`) → skip. 3. `content_hash`
   present → skip. 4. `(vendor_id, publish_date, LOWER(title))` → skip.
   **`content_hash` = SHA-256 of the stable SANITIZED body** (not raw bytes / not the
   stored artifact) → producer-agnostic → §5 parity cutover is safe.

### 10.9 DB schema (`research` schema, MSSQL `IMDR`)
- `research.dim_report` (id, vendor_id→`dbo.dim_vendor`, title, publish_date, authors,
  **pdf_path NOT NULL**, source `varchar(16)` def 'portal', source_type `varchar(20)`
  def 'research', internet_message_id `varchar(255)` null + filtered-unique idx,
  content_hash binary(32), pdf_text, asset_class, region, country_id, context,
  parser_version). Migration **099** (applied) added source/source_type/imi.
- Dependents (delete children-first on cleanup): `research.fact_chunk` (report_id),
  `research.fact_chunk_embedding` (chunk_id), `research.map_report_tag` (report_id),
  `research.map_report_market` (report_id), plus `research.dim_tag`,
  `research.dim_embedding_model`.
- `dbo.dim_vendor` vendor_code→id: goldman=9, ms=12, db=18, citi=46, nomura=11,
  stanc=20, hsbc=13, anz=10, ubs=45, barclays=2, bofa=42, westpac=17. **cba/cacib
  have NO row** (held).
- **Read-only access** via the `imdr-db` MCP (`mcp__imdr-db__query`, SELECT only;
  rejects `;`/comments). Writes/deletes go via `research_engine` with a `source='email'`
  safety guard.

### 10.10 Artifact storage
`upload_bytes(data, relative_path=build_sharepoint_path(vendor_code, publish_date,
uuid=imi8, title, ext))` where `imi8 = sha256(internet_message_id)[:8]`. Path =
`{YYYY}/{MM}/{DD}/{vendor}/{slug}_{imi8}.{ext}` under the OneDrive-synced IMDR library
(observed local root: `C:\Users\adoshi\OneDrive - RV Capital Management Private
Ltd\Trade Knowledge Core - IMDR\`). `ext`: body-only → `html` (route B today); route
A → `eml`; **attachment PDF → `pdf`** (what route C enables). Upload happens BEFORE the
DB write so `pdf_path` always points at an existing file.

### 10.11 Embedding / Qdrant
Default model `gemini-embedding-2` (3072-dim); Qdrant collection
`research_gemini_embedding_2_3072d`; remote at `http://127.0.0.1:6333`. `--no-embed`
writes the DB row only (no embed/Qdrant). Keys (Voyage/Gemini) from `Settings`.

### 10.12 Environment
Run with the imdr conda env: `C:/Users/adoshi/.conda/envs/imdr/python.exe` (has pyodbc
+ ODBC Driver 18 + tiktoken + qdrant + voyage/gemini). The base interpreter lacks
tiktoken (dry-run still works — embed/engine imports are lazy). **No `pytest-asyncio`**
— async tests drive with `asyncio.run`. `pywin32` (for COM) must be added to the env.

### 10.13 Tests (tracked) + current corpus state
`tests/unit/research/`: `test_outlook_adapter.py` (27), `test_dedup_merge.py` (7),
`test_email_common_classifier.py` (15), `test_email_doc.py` (21),
`test_email_pipeline.py` (3), `test_outlook_mapi_pull.py` (8, NEW — slug/imi8,
content-type, real-PDF discriminator, EX→SMTP, ReceivedTime UTC fix, `build_record`
with mocked COM) = part of **94 email unit tests** (also dedup-merge 18 incl. the
masthead/serial/email-twin paths). Email corpus in `dim_report` = **110 rows**
(after the 2026-06-22 desk-core load, the portal-pointer cleanup, and the
2026-06-23 email-to-email dup cleanup) — the route-C build itself wrote nothing
(dry-runs / staging only). Spike + smoke helpers: `_p0_com_spike.py`,
`_p4_parity_check.py`, `_smoke_netnew_sim.py`, `_cleanup_email_dups.py`.
