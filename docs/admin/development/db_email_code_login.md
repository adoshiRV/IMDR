# DB (Deutsche Bank Research) email-code login — design plan

**Status:** DONE — implemented + live-validated 2026-07-22 (wiped profile →
auto-read the emailed code → logged in → discovered 270 reports → downloaded a
PDF, `smoke=PASS`). Freshness uses **baseline-diff** (wait for an email strictly
newer than the newest present before Submit) — skew-proof and immune to leftover
codes; supersedes the original `received_after − 30s` skew idea.
**Author:** 2026-07-22
**Related:** [credit_bofa.md](credit_bofa.md) (the working model), [../research/auth.md](../research/auth.md) (auth runbook)

---

## 1. Problem

Deutsche Bank Research (`research.db.com`) is **not SSO**. When the
persistent profile's session lapses, the portal drops to
`research.db.com/research/Register` — a 3-step **email verification-code**
login:

1. **Enter email** (`adoshi@rvcapital.com`) → Submit.
2. DB emails a **6-character alphanumeric code** (e.g. `6BA0EC`) from
   `DoNotReply@markit.esp.db.com` (subject varies: "instant access to
   research" / "Verify device"; body contains `Code: 6BA0EC` and a
   "Verify device" button). Code expires in 30 min.
3. **Paste code** → Submit → tick + **accept Terms & Conditions**.

Today `db` is `PROFILE_ONLY` — there is no code-reader, so when the
session lapses the ingest silently gets HTTP 403 `auth_missing` and
returns zero reports (seen 2026-07-22). A human currently has to do the
email-code dance by hand.

**Goal:** on the occasional refresh, read the code out of the Outlook
Inbox and complete the login automatically — the same capability BofA
already has.

### Persistence note (important — sets the cadence)
Unlike BofA (whose Premia auth ticket lives in non-persistent JS storage,
so it needs a fresh token **every run**), **DB persists its session in the
profile.** So `is_authenticated()` returns True on normal runs and the
email-code path never fires. The inbox read is a **refresh-only fallback**
— it triggers only when the saved session has actually lapsed, so it does
**not** generate a login email every crawl.

---

## 2. The working model we copy — `login_bofa.py`

`playground/research/ingest/login_bofa.py` is the reference. Reuse its
four hard-won patterns **verbatim** (each fixed a real bug — see
`credit_bofa.md` changelog):

| Pattern | Why it matters |
|---|---|
| **Idempotent `login()`** — calls `is_authenticated()` first, short-circuits if already authed | This is what makes DB "store & save, re-auth only on refresh". |
| **Freshness gate** — stamp `token_since = now(UTC)` at the moment of Submit; only accept a code email received at/after `token_since − 30s` skew | A stale/leftover code from a prior login can't be consumed. |
| **`asyncio.to_thread(...)`** around the blocking win32com poll | The Outlook poll must not freeze the shared event loop (other vendors). |
| **Poll-continues-on-parse-miss** until a deadline (~120s) | The email lands a few seconds late; don't abort on the first empty read. |

---

## 3. Design

### 3.1 Auth-mode change
Flip `db` in `registry.py` from `PROFILE_ONLY` → **`PROGRAMMATIC`**, with
`login_module="imdr.research.auth.loginflows.db"`. This is cleaner than
BofA's standalone approach — it plugs into the existing
`get_authed_context()` → `_run_programmatic_login()` path, so both the
ingest and `auth refresh`/`validate` recover db automatically.

### 3.2 New module — `src/imdr/research/auth/loginflows/db.py`
Implements the `_base.py` contract:

- **`async def is_authenticated(ctx) -> bool`** — navigate the healthcheck
  URL; True iff we land on authenticated content (reuse the `_live_db`
  predicate, already fixed 2026-07-22 to reject the Register/signin
  funnel). Must not raise.
- **`async def login(ctx, *, username, password) -> None`** — idempotent.
  `username` = the DB login email; `password` is **unused** (the "secret"
  is the emailed code). The 3-step flow:
  1. Goto `research.db.com/research/Register`; fill the **Email Address**
     field with `username`; click **Submit**.
  2. Stamp `code_since = now(UTC)`; `await asyncio.to_thread(read_db_code,
     code_since)`; fill the **Verification Code** field; click **Submit**.
  3. Tick the **T&C** checkbox if present; accept/continue.
  4. Verify we positively landed on authenticated content (reuse
     `_live_db`); else raise `LoginFailedError`.

**Selectors** — to be captured from a live DOM probe of the Register page
(none exist yet). Expected shape from the screenshots:
- Email: `input[type="email"]` / `input[name*="email" i]` + a Submit button.
- Code: `input[name*="code" i]` / the "Verification Code" input + Submit.
- T&C: a checkbox near "Accept Terms & Conditions" + accept/continue.

### 3.3 Inbox code reader — extend `Win32OutlookClient`
Add a `find_code()` method to `src/imdr/vendors/sessions/outlook.py`
(reuse its existing default-Inbox walk + newest-first sort + sender/subject
filter — DB mail lands in the **Inbox**, confirmed 2026-07-22). Signature:

```python
def find_code(self, *, sender: str, subject_contains: str = "",
              received_after: datetime, code_regex: re.Pattern,
              max_wait_s: int = 120, poll_s: int = 5) -> str | None
```

- Filter: `SenderEmailAddress` contains `DoNotReply@markit.esp.db.com`
  (sender-based — more robust than subject, which varies).
- **Freshness:** ignore any email received before `received_after`
  (minus 30s skew).
- **Code regex — the critical delta from BofA:** DB codes are **6
  alphanumeric** chars, so `re.compile(r"Code:?\s*([A-Z0-9]{6})\b")`
  (anchor on the `Code:` label to avoid matching stray body text).
  Exact anchor to be confirmed against a real email body. **NOT** BofA's
  digits-only `\d{6,10}`.
- Poll every `poll_s` until `max_wait_s`; return `None` on timeout with a
  stashed `last_err` for diagnostics.

Keeping this on `Win32OutlookClient` (behind the `OutlookClient` Protocol)
means tests substitute a fake — no `win32com` needed in CI.

### 3.4 Config / credentials
- **Reuse the existing env var** `IMDR_RESEARCH_DB_USERNAME=adoshi@rvcapital.com`
  (already in `.env`). Add the matching `Settings.research_db_username: str = ""`
  field (currently undeclared, so pydantic ignores it) alongside the other
  `research_*_username` fields.
- No password — the "secret" is the emailed code.
- Add `db` to `context._CRED_FIELDS`: `("research_db_username", "", "IMDR_RESEARCH_DB")`
  (email as username, empty password slot).

### 3.5 Predicate (already done)
`_live_db` was tightened 2026-07-22 to exclude `login/register/signin/logon`
so `verify()`/`auth login` stop treating the Register page as LIVE.
Regression test added in `test_research_auth_registry.py`.

---

## 4. Tests
- **Code regex** unit test: `6BA0EC` matches; stray 6-char words in body
  don't; digits-only BofA-style codes still parse if present.
- **`find_code` with a fake `OutlookClient`**: returns the fresh code;
  ignores a pre-`received_after` email; returns None on timeout.
- **Predicate regression** (done): Register URL → False.
- **`is_authenticated` smoke**: monkeypatch page to Register vs content.

## 5. Rollout / validation
1. Live selector probe of the Register page (playground, headed) → capture
   exact selectors.
2. Implement + unit tests green.
3. `python -m imdr.research.auth validate --vendor db` — should log in via
   the email code and download one PDF (`smoke=PASS`).
4. Confirm the ingest recovers db unattended after a forced logout.

## 6. Risks & open questions
- **Alphanumeric regex false-positives** — mitigated by anchoring on the
  `Code:` label; confirm against a real email body before shipping.
- **T&C step** may only appear on first registration per device; handle
  its presence/absence gracefully (like BofA's two-path resolver).
- **Headless vs headed** — probe whether the Register flow completes
  headless; DB was `PROFILE_ONLY headless=True`, but the code flow may
  need headed once. Decide during the probe.
- **Every-refresh email** is acceptable because refreshes are rare (session
  persists); no unattended-spam concern.

## 7. Related follow-up — predicate looseness is systemic
The same too-loose `"<domain>" in url and "login" not in url` pattern that
broke `_live_db` also mis-fires elsewhere. Confirmed 2026-07-22:
- **jpm** — `auth login` flipped LIVE on a security-**redirect** landing
  (`markets.jpmorgan.com/home?URI=…&securityLevel=0`), never reaching
  `/jpmm/research`. Needs the predicate to require the research path.

Audit all `_live_*` predicates for register/redirect/interstitial pages as
a separate task; this doc covers db only.
