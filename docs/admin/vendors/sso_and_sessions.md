# SSO and Persistent Browser Sessions

`BrowserSession` in `src/imdr/vendors/sessions/browser.py` wraps Playwright's persistent-context launcher. Every feed using a browser transport (email-linked today, web scrape tomorrow) shares this session so SSO bootstrap, cookie persistence, and lock recovery are handled in exactly one place.

## Profile location

`settings.browser_profile_root` (default `<repo>/data/browser_profiles/`). Each feed declares `profile_name` in its spec; the session opens `{root}/{profile_name}/`.

Override via `IMDR_BROWSER_PROFILE_ROOT` in `.env` if profiles need to live elsewhere (e.g. on a shared UNC path — works, but ensure Chrome can write to it).

## Bootstrap (first-time SSO)

1. Start the feed **headed**:
   ```
   python -m scripts.run_vendor_feed <feed> --headed
   ```
2. Chrome opens. Complete SSO interactively — credentials, MFA, whatever the portal asks.
3. Let the run finish. Cookies and local storage persist in the profile directory.
4. Subsequent runs are headless and silent until the SSO cookies expire.

## Re-bootstrap (SSO expired)

Symptoms: feed starts failing with `SSOTimeout` after previously succeeding. Fix:

1. Re-run headed as above. If Chrome remembers the portal, SSO just re-prompts; complete it.
2. If the profile is fully broken, delete `data/browser_profiles/{profile_name}/` and re-bootstrap from scratch.

Never share a profile dir between two feeds — Chrome can only hold one `launch_persistent_context` per dir at a time, and Playwright's stale-lock detection is imperfect.

## Stale lock recovery

Chrome leaves these files in the profile when killed uncleanly:

- `SingletonLock`
- `SingletonCookie`
- `SingletonSocket`
- `lockfile`

`BrowserSession.__enter__` unlinks them on every start. If you still see a `browser_lock` error, it usually means another Chrome instance is actively running against the same profile — close it, or the next run will.

## Headless rules

Headless mode is fine after bootstrap. It does NOT work for bootstrap itself — Playwright can't drive interactive SSO in headless. The `imdr_daily.py` batch uses headless by default (`run_vendor_feed_daily(name, headless=True)`).

## What the session does NOT do

- **Auto-login.** The framework does not currently submit credentials programmatically. Rationale: every vendor's SSO flow differs (Ping, Okta, AzureAD, custom SAML, sometimes MFA). Keep the bootstrap manual and simple until a second vendor confirms a shared pattern is worth abstracting.
- **Credential rotation.** If `IMDR_MYVENDOR_PASSWORD` rotates, the persisted session keeps working until cookies expire. Re-bootstrap at that point.
- **Session health checks.** The acquirer doesn't probe the session before opening the real URL — it just opens it and waits up to `sso_timeout_s` for the expected anchors. If you need earlier detection, add a health-probe step to the specific acquirer.

## Related

- [email_linked_downloads.md](email_linked_downloads.md) — how acquirers compose the session
- [troubleshooting.md](troubleshooting.md) — full failure-mode catalogue
