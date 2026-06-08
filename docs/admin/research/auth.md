# Research-portal auth — operator runbook

A single module at [`src/imdr/research/auth/`](../../../src/imdr/research/auth/)
owns every research vendor's browser-session lifecycle: predicate-based
healthchecks, persistent-profile session reuse, programmatic auto-login
for vendors that support it, JSON `storage_state` snapshots for
portability, and a 5-step end-to-end smoke (`validate`).

This doc is the operator-facing reference. Module docstrings + the CLI
`--help` are the day-to-day source; this file is the bigger picture.

The canonical vendor list and per-vendor configuration lives in
[`registry.py`](../../../src/imdr/research/auth/registry.py)
(`VENDOR_AUTH_REGISTRY`). The table below tracks it manually; if they
diverge, the registry wins.

---

## Per-vendor auth mode

| Vendor | Mode | Headless | Fetch in-session | Healthcheck URL | Env vars consumed |
|---|---|---|---|---|---|
| **anz** | `PROGRAMMATIC` | True | — | `research.anz.com/all_research` | `IMDR_RESEARCH_ANZ_USERNAME` / `_PASSWORD` |
| **barclays** | `PROGRAMMATIC` (wipe per run) | True | yes (PingFederate) | `live.barcap.com` | `IMDR_BARCLAYS_USERNAME` / `_PASSWORD` |
| **bnp** | `PROFILE_ONLY` | True | — | `markets360.bnpparibas.com/` | — |
| **db** | `PROFILE_ONLY` | True | — | `research.db.com/research/Research/Latest` | — |
| **goldman** | `PROFILE_ONLY` *(deferred — MFA push)* | True | — | `marquee.gs.com/s/` | — |
| **hsbc** | `PROFILE_ONLY` *(deferred — hardware token)* | True | — | `research.hsbc.com/.../Reach?productid=5` | — |
| **jpm** | `HEADER_INJECTION` | True | — | `markets.jpmorgan.com/jpmm/research` | `IMDR_RESEARCH_JPM_USERNAME` (header only) |
| **ms** | `PROFILE_ONLY` *(deferred — dual cred)* | True | — | `ny.matrix.ms.com/eqr/research/portal/home/global` | — |
| **nomura** | `PROGRAMMATIC` | True | — | `www.nomuranow.com/portal/site/nnpub/research/` | `IMDR_RESEARCH_NOMURA_USERNAME` / `_PASSWORD` |
| **socgen** | `PROFILE_ONLY` *(deferred — biometric)* | True | yes (OIDC) | `insight.sgmarkets.com/` | — |
| **stanc** | `PROGRAMMATIC` | True | — | `research.sc.com/research/api/application/static/` | `IMDR_RESEARCH_STANC_USERNAME` / `_PASSWORD` |
| **ubs** | `PROGRAMMATIC` | **False** | — | `neo.ubs.com/home` | `IMDR_RESEARCH_UBS_USERNAME` / `_PASSWORD` |
| **westpac** | `PROFILE_ONLY` *(deferred — device trust)* | True | — | `www.westpaciq.com.au/economics` | — |

**Mode semantics:**

- **`PROFILE_ONLY`** — SSO cookies live in the persistent Chrome profile.
  Recovery requires a human in headed Chrome (`auth login --vendor X`).
- **`PROGRAMMATIC`** — A `loginflows/{vendor}.py` module owns a form-fill
  flow. The auth context manager calls it automatically when the session
  is stale. Re-login is silent and ~5s.
- **`HEADER_INJECTION`** — Persistent SSO cookies plus a custom HTTP
  header injected on every request (today: JPM's `janus_user`).

**`fetch_in_session`** — True for vendors whose PDF fetch must happen
in the same Playwright context as discovery (cookies are session-scoped
and don't survive `ctx.close()`). The validate command's step 4 picks
the right fetch branch based on this flag.

---

## Settings reference

Every env var the auth flow reads, declared in
[`src/imdr/config/settings.py`](../../../src/imdr/config/settings.py).

| Env var | What it does |
|---|---|
| `IMDR_BARCLAYS_USERNAME` / `_PASSWORD` | Barclays Live programmatic login. |
| `IMDR_RESEARCH_UBS_USERNAME` / `_PASSWORD` | UBS Neo two-step form login. |
| `IMDR_RESEARCH_ANZ_USERNAME` / `_PASSWORD` | ANZ Research form login. |
| `IMDR_RESEARCH_NOMURA_USERNAME` / `_PASSWORD` | NomuraNow form login. |
| `IMDR_RESEARCH_STANC_USERNAME` / `_PASSWORD` | Standard Chartered form login. |
| `IMDR_RESEARCH_JPM_USERNAME` | JPM Janus `janus_user` GraphQL header value. |
| `IMDR_EMAIL_ENABLED` | Master switch for all email dispatch. False = silent. |
| `IMDR_EMAIL_TO` | Default operator recipient (semicolon-separated). |
| `IMDR_EMAIL_ANOMALY_TO` | Preferred recipient for auth-failure alerts; falls back to `IMDR_EMAIL_TO`. |
| `IMDR_RESEARCH_AUTH_EMAIL_ON_AUTH_FAILURE` | (default `true`) Whether `get_authed_context` emits a `login_failed` email on auth failures. The `validate` CLI sets this to `false` internally so it doesn't double-email on top of its own summary email. |

---

## CLI reference — `python -m imdr.research.auth`

### `check` — read-only session healthcheck

```
python -m imdr.research.auth check --vendor all
```

Navigates each vendor's healthcheck URL, runs the registry predicate,
prints `LIVE` / `EXPIRED` / `NO_PROFILE` / `UNREACHABLE`. Never logs
in, never wipes profiles, never emails. Exit code 0 = all live, 1 = at
least one not live.

### `refresh` — verify + auto-relog where possible

```
python -m imdr.research.auth refresh --vendor barclays
python -m imdr.research.auth refresh --vendor all
```

Calls `check` per vendor. For `EXPIRED` + `PROGRAMMATIC`, attempts a
fresh login via the loginflow module. For other modes, emits a
`needs_human` flag in the output. Exit code 0 = all live or auto-
recovered, 2 = one or more need human re-auth.

### `login` — headed SSO seed (one vendor)

```
python -m imdr.research.auth login --vendor anz
```

Opens **headed** Chrome on the vendor's healthcheck URL. Operator
completes SSO interactively. CLI polls the predicate every 2 seconds;
writes a `storage_state.json` snapshot once LIVE. 10-minute timeout.
This is the canonical re-auth ritual for SSO-only vendors.

### `status` — last storage_state snapshot timestamp

```
python -m imdr.research.auth status
```

Prints when each vendor's `data/cache/research_auth/{vendor}/storage_state.json`
was last written and its size. Useful for confirming that a recent
`login` actually persisted.

### `validate` — full 5-step end-to-end smoke

```
python -m imdr.research.auth validate --vendor ubs
python -m imdr.research.auth validate --vendor all              # 8-15 min
python -m imdr.research.auth validate --vendor all --no-email   # suppress email
python -m imdr.research.auth validate --vendor all --email-dry-run
```

Per vendor:

1. **current auth status** — calls `verify()`
2. **credential availability** — reads `Settings`, prints `current` /
   `could_be` / `gap`
3. **login + persist session** — opens `get_authed_context()`, snapshots
   `storage_state.json`
4. **download one PDF** — `discover(limit=1)` + fetch the first ref
   (via `fetch_pdf` or the crawler's `fetch_pdfs` generator depending
   on `fetch_in_session`); writes to a temp file, validates with
   `pypdf`, then `os.unlink`s
5. **SUCCESS / BLOCKED** with structured reason

When `--vendor all` finishes, dispatches one **summary email**
(formatter: `research_auth_validate.html`). Suppress with `--no-email`
or preview with `--email-dry-run`.

---

## Error catalogue

All exceptions inherit from
[`AuthError`](../../../src/imdr/research/auth/errors.py).

| Exception | Raised by | Recoverable | Operator action |
|---|---|---|---|
| `UnknownVendor` | `get_spec` | no | typo'd vendor code; check `auth check --help` for valid list |
| `CredentialMissing` | `context._run_programmatic_login` | no | set the env vars listed in `exc.env_var_prefix` |
| `SessionExpired` | (status enum today; reserved for future raise sites) | yes for `PROGRAMMATIC` | `auth refresh --vendor X` (programmatic) or `auth login --vendor X` (SSO) |
| `LoginFailedError` | `loginflows/{vendor}.py` | no | check creds; consider MFA fallback (revert to PROFILE_ONLY in registry) |
| `MFARequired` | (subclass of `LoginFailedError`) | no | revert vendor to `PROFILE_ONLY` and document MFA mode in `notes` |
| `PDFValidationError` | `cli._validate_pdf_bytes` | no | session likely returned an HTML error page; re-auth and retry |

All carry `.vendor`. `CredentialMissing` adds `.env_var_prefix`.
`LoginFailedError` adds `.title`, `.url`, `.hint`. `MFARequired` adds
`.mfa_kind`. `PDFValidationError` adds `.n_bytes` and `.reason`
(`"empty"` / `"bad_magic"` / `"too_small"` / `"pypdf_parse_failed"` /
`"zero_pages"`).

---

## Email triggers + recipient routing

Three event kinds, each backed by a Jinja2 template under
[`src/imdr/notifications/templates/`](../../../src/imdr/notifications/templates/).

| Kind | Trigger | Template | When |
|---|---|---|---|
| `validate_summary` | end of `validate --vendor all` | `research_auth_validate.html` | every successful run unless `--no-email` |
| `login_failed` | `context.get_authed_context` on `AuthError` | `research_auth_login_failed.html` | gated by `IMDR_RESEARCH_AUTH_EMAIL_ON_AUTH_FAILURE` (default true) |
| `needs_human` | `imdr_session_heartbeat` when any vendor returned EXPIRED + can't self-recover | `research_auth_needs_human.html` | every run that finds at least one needs-human vendor |

**Recipient resolution** (in `notify._resolve_recipient`):

1. `IMDR_EMAIL_ANOMALY_TO` if non-empty
2. else `IMDR_EMAIL_TO`
3. else no recipient → email silently skipped

**Importance flag**: `login_failed` and `needs_human` ship as
Outlook *high importance* (red badge); `validate_summary` as normal.

**Master switch**: nothing emails when `IMDR_EMAIL_ENABLED=false`.
`send_auth_email` returns `False` and logs at debug level.

`send_auth_email` never raises — broken Outlook installs, missing
recipients, render failures all degrade silently. The original auth
flow always wins.

---

## Heartbeat operator notes

Script:
[`scripts/imdr_session_heartbeat.py`](../../../scripts/imdr_session_heartbeat.py)

```
python -m scripts.imdr_session_heartbeat                   # all vendors
python -m scripts.imdr_session_heartbeat --vendor jpm
python -m scripts.imdr_session_heartbeat --no-email        # suppress email
```

Calls `refresh_all()`, prints a single-line summary, emits a
`needs_human` email when any vendor needs operator action.

**Exit codes**: 0 (all live or auto-recovered), 2 (one or more need
human), 1 (unexpected error).

**Not wired into a scheduler yet** — per the project's
*no-prod-wiring-without-permission* rule. To opt in, add to the
`PIPELINES` list in `scripts/imdr_hourly.py`:

```python
["python", "-m", "scripts.imdr_session_heartbeat"]
```

Suggested cadence: hourly during business hours, optional every-6h
overnight. The script is cheap (~30s for 13 vendors) and silent when
nothing's wrong.

---

## Troubleshooting

### `validate` step 3 fails with `CredentialMissing`

The vendor is `PROGRAMMATIC` but the corresponding `Settings` field is
empty. The exception message names the env-var prefix
(e.g. `IMDR_RESEARCH_UBS`). Populate `_USERNAME` + `_PASSWORD` in
`.env` and re-run.

### `validate` step 4 returns `bad_pdf:bad_magic`

The session lost discovery rights (cookies returned an HTML error
page instead of PDF bytes). Run `auth check --vendor X` — if EXPIRED,
re-auth via `refresh` (programmatic) or `login` (SSO-only).

### Cookies LIVE but `discover` returns `[]`

`auth check` says LIVE but no reports come back. Possible causes:

- Date window has no publications (try a wider `since`)
- Vendor outage (most surface this as 500s in the crawler logs)
- IP-bound session — the cookies are LIVE for healthcheck navigation
  but the listing API rejects from a different egress IP. Rare.

### MFA prompt appeared on a previously-working PROGRAMMATIC vendor

The vendor flipped on device-trust MFA. Fallback policy:

1. Revert the registry entry for that vendor back to `PROFILE_ONLY`
   in [`registry.py`](../../../src/imdr/research/auth/registry.py)
2. Remove the corresponding import line from
   [`loginflows/__init__.py`](../../../src/imdr/research/auth/loginflows/__init__.py)
3. Note the MFA kind in the spec's `notes` so the next operator knows
4. Use `auth login --vendor X` for ongoing re-auth (headed SSO)

### Headed Chrome rejected (UBS-style)

UBS's `headless=False` is intentional — the portal sniffs the
`HeadlessChrome` User-Agent and refuses content. If another vendor
starts doing this, flip `headless: False` on its registry spec.

### `state.restore_into` — what is it for?

Documented future hook for booting a fresh non-persistent context
from a snapshot. Not used by the current code; persistent contexts
read their state from the `user_data_dir` directly. Kept as ~20 lines
to signal design intent.

---

## Adding a new vendor

See the broader [onboarding doc](onboarding_new_vendor.md) for the
crawler half. The auth-specific checklist:

1. **Pick a healthcheck URL + predicate.** The URL should require auth
   to render real content (don't pick a public landing page).
   Predicate is `(title, url) -> bool`; lift the body from a
   one-shot Playwright headed probe.
2. **Decide the mode.**
   - SSO-only vendor → `PROFILE_ONLY`
   - Form-fill credentials available + no MFA → `PROGRAMMATIC`
   - SSO + custom header (rare) → `HEADER_INJECTION`
3. **Add the spec** to `VENDOR_AUTH_REGISTRY` in
   [`registry.py`](../../../src/imdr/research/auth/registry.py).
4. **(PROGRAMMATIC only)** write
   `src/imdr/research/auth/loginflows/{vendor}.py` following the
   contract in [`_base.py`](../../../src/imdr/research/auth/loginflows/_base.py):
   `is_authenticated(ctx) -> bool` + `login(ctx, *, username, password)`.
   Use `silent_cleanup` around all Playwright teardown calls.
5. **Add the credential-map entry** to `_CRED_FIELDS` in
   [`context.py`](../../../src/imdr/research/auth/context.py).
6. **Add `Settings` fields** + document the env vars in `.env.example`.
7. **Extend tests**: add the vendor code to `_EXPECTED_VENDORS` and
   predicate parametrize cases in
   [`tests/unit/test_research_auth_registry.py`](../../../tests/unit/test_research_auth_registry.py).
8. **Verify with `validate --vendor X`** — if MFA fires unexpectedly,
   revert to `PROFILE_ONLY` per the fallback policy above.
