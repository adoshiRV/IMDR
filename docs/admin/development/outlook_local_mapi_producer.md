# Outlook email ingest — local MAPI/COM producer (cost overhaul)

**Status: PLANNED (2026-06-23).** Design + rationale below; not yet built. File a
Linear project ("Build local Outlook MAPI producer for the email channel",
label `research`) per [README](README.md) before starting.

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
```python
import win32com.client
ns = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
rcpt = ns.CreateRecipient("research@rvcapital.com"); rcpt.Resolve()
research = ns.GetSharedDefaultFolder(rcpt, 6).Parent.Folders["Research"]  # parent of Inbox
for vfolder in research.Folders:                 # GS, MS, DB, Citi, SCB, STANC, ...
    items = vfolder.Items
    items.Sort("[ReceivedTime]", True)
    items = items.Restrict("[ReceivedTime] >= '06/15/2026' AND [ReceivedTime] < '06/23/2026'")
    for m in items:
        ...  # build staging JSON
```
`Restrict` date strings are **locale-sensitive** — format as the host's short-date
(`m/d/yyyy`); detect/format defensively.

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
| `received` | `m.ReceivedTime` → ISO-8601 Z (it's a pywintypes datetime; convert to UTC) |
| `body_content_type` | `"html"` |
| `body_html` | `m.HTMLBody` (full verbatim HTML — **must be byte/sanitiser-equivalent to the MCP `body.content`**, see §5 parity) |
| `attachments` | iterate `m.Attachments` → `{name, content_type, size, is_inline}`; for real (non-inline) PDFs **`att.SaveAsFile(staging/<vendor>/attachments/<sha8>.pdf)`** and set `file` to that relative path |

### 4.4 Attachments → real PDF artifacts
COM exposes attachment bytes locally. For `att.Type` real-file PDFs, `SaveAsFile`
into `attachments/`; the existing `email_doc.build_email_document` already prefers a
staged PDF (`parse_pdf`) over the synthetic body — so CBA/Nomura/DB-PM become
first-class `.pdf` rows with **no pipeline change**. (Inline images: record
metadata, don't save — same as today.)

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
- **Parity check (the cutover-critical one):** stage the same messages via MAPI and
  via the existing MCP path; assert the **sanitised body + `content_hash` match**.
  `content_hash` derives from the stable sanitised source (not raw bytes), so if
  `HTMLBody` sanitises to the same text as `body.content`, **cutover creates zero
  false-duplicates** (re-runs imi/hash-dedup cleanly). If `HTMLBody` differs
  materially (e.g. Outlook re-encodes), document the delta and confirm the sanitiser
  normalises it.
- **Integration:** MAPI-staged → `ingest_outlook.py --dry-run` parity vs the
  06-15→22 desk-core; then a `--no-embed` load smoke on 1–2 vendors.

## 6. Build phases (checklist)

- [ ] **P0 spike** — confirm COM reaches `Research/*` subfolders of the shared
  mailbox, reads `HTMLBody` + PR_INTERNET_MESSAGE_ID + recipients + attachments for
  one folder/one day. (De-risks the whole thing in ~30 min.)
- [ ] **P1 producer** — `outlook_mapi_pull.py` writing the staging contract for a
  `--since/--until` window across the folder→vendor map (reuse `FOLDER_TO_VENDOR`,
  honour `EMAIL_VENDOR_HOLD`). Dry-run parity vs MCP-staged JSON.
- [ ] **P2 attachments** — `SaveAsFile` real PDFs; verify CBA/Nomura/DB-PM now load
  as `.pdf` (route-A PDF gap closed).
- [ ] **P3 incremental** — per-folder HWM; idempotent reruns (imi-dedup confirms).
- [ ] **P4 parity + cutover** — content_hash parity test green; make MAPI the
  default producer in the runbook; retire the route-B MCP-agent staging procedure;
  update docs.
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
- A 7-day desk-core ingest runs at **~0 LLM tokens** (producer is pure Python COM).
- **No Azure app registration** required.
- CBA/Nomura/DB-PM attach **real `.pdf`** artifacts (not `pdf_missing`).
- Reruns are incremental (HWM) and idempotent (imi-dedup).
- content_hash parity with the prior producer → clean cutover, zero false-dups.

## 9. Relationship to route A (Graph)
Route A (Graph + app-reg) was the previously-planned "unattended producer." Route C
supersedes it for the **interactive/local** case (no admin, captures PDFs, free).
Graph remains the right choice **only** if the ingest must ever run on a host
*without* an Outlook profile (true headless server/cron). Keep route A documented as
the headless option; build route C now.
