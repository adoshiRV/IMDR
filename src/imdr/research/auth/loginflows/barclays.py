"""Programmatic Barclays Live login.

Form-fill flow against ``live.barcap.com``. Reads credentials from
``Settings.barclays_username`` / ``Settings.barclays_password``,
dismisses the OneTrust cookie banner if present, fills user + password,
clicks submit, and waits for the post-SSO landing page.

**Profile lifecycle: fresh-per-run.** Empirically Barclays' persistent
profile state poisons subsequent runs — PingFederate sets per-session
tokens that, once stale, redirect every navigation back to the login
page even though cookies look valid. The auth context manager
(:func:`imdr.research.auth.context.get_authed_context`) wipes
``profile_dir`` before launch for any vendor with
``wipe_profile_per_run=True`` in :data:`VENDOR_AUTH_REGISTRY`.

Empirically (2026-05-08) Barclays Live uses **risk-based auth** for
this device — username + password is sufficient, no MFA email step.
If MFA reappears later (Barclays revokes the trust, or we move to a
new device), the flow needs an Outlook poll for the OTP code; that
extension is sketched at the bottom of this module.

Moved from ``playground/research/ingest/login_barclays.py`` on
2026-06-06 as part of the research-auth productionalisation; the old
path keeps a thin re-export for one cycle so any helper scripts still
import cleanly.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from ._base import LoginFailedError, silent_cleanup

LOGIN_URL = "https://live.barcap.com"
HOME_URL_FRAGMENT = "/BU/"

_COOKIE_ACCEPT = "#onetrust-accept-btn-handler"
_USER_INPUT = 'input[name="user"]'
_PASSWORD_INPUT = 'input[name="password"]'
_SUBMIT_BUTTON = "button#submit"

_NAV_TIMEOUT_MS = 30000
_COOKIE_TIMEOUT_MS = 5000
_FIELD_TIMEOUT_MS = 10000


async def _safe_title(page) -> str:
    """``page.title()`` that tolerates a torn-down execution context.

    PingFederate's redirect chain can destroy the JS context mid-call,
    surfacing as "Execution context was destroyed, most likely because
    of a navigation". Retry once after a settle; return "" if still
    gone.
    """
    for _ in range(2):
        try:
            return (await page.title()) or ""
        except Exception:
            async with silent_cleanup("barclays._safe_title.settle"):
                await page.wait_for_load_state("domcontentloaded", timeout=5000)
    return ""


def _safe_url(page) -> str:
    try:
        return page.url or ""
    except Exception:
        return ""


def ensure_clean_profile(profile_dir: Path) -> None:
    """Wipe the profile dir so Chrome boots from a clean slate.

    Required for Barclays — see module docstring. The auth context
    manager calls this for any vendor with
    ``wipe_profile_per_run=True`` in the registry.
    """
    if profile_dir.exists():
        shutil.rmtree(profile_dir, ignore_errors=True)
    profile_dir.mkdir(parents=True, exist_ok=True)


async def is_authenticated(ctx) -> bool:
    """Navigate :data:`LOGIN_URL` and decide if we landed past SSO.

    Returns True if persistent cookies still get us past the login
    page. False on any error so callers can fall through to a full
    :func:`login`.
    """
    page = await ctx.new_page()
    try:
        await page.goto(LOGIN_URL, wait_until="commit", timeout=_NAV_TIMEOUT_MS)
        async with silent_cleanup("barclays.is_authenticated.networkidle"):
            await page.wait_for_load_state("networkidle", timeout=10000)
        title = await _safe_title(page)
        url = _safe_url(page)
        if not title and not url:
            return False
        return "Login" not in title and "ct_logon_basic" not in url
    except Exception:
        return False
    finally:
        async with silent_cleanup("barclays.is_authenticated.page.close"):
            await page.close()


async def login(ctx, *, username: str, password: str) -> None:
    """Full programmatic login — idempotent.

    Calls :func:`is_authenticated` first and short-circuits if the
    persistent cookie still works. Raises :class:`LoginFailedError`
    if we land back on the login page after submit (typically: wrong
    creds, or Barclays flipped on MFA for this device).
    """
    if await is_authenticated(ctx):
        return

    page = await ctx.new_page()
    try:
        await page.goto(LOGIN_URL, wait_until="commit", timeout=_NAV_TIMEOUT_MS)
        async with silent_cleanup("barclays.login.networkidle.pre"):
            await page.wait_for_load_state("networkidle", timeout=15000)

        # 1. Cookie banner — must be dismissed before form is interactive.
        async with silent_cleanup("barclays.login.cookie_banner"):
            cookie_btn = page.locator(_COOKIE_ACCEPT).first
            if await cookie_btn.count() > 0 and await cookie_btn.is_visible():
                await cookie_btn.click(timeout=_COOKIE_TIMEOUT_MS)
                await page.wait_for_timeout(500)

        # 2. Fill credentials.
        await page.locator(_USER_INPUT).fill(username, timeout=_FIELD_TIMEOUT_MS)
        await page.wait_for_timeout(200)
        await page.locator(_PASSWORD_INPUT).fill(password, timeout=_FIELD_TIMEOUT_MS)
        await page.wait_for_timeout(200)

        # 3. Submit and wait for navigation away from the login URL.
        # PingFederate sometimes redirects through multiple intermediate
        # pages; the first navigation may complete before we register
        # the listener, so swallow expect_navigation failures and fall
        # back to a URL/title check after a settle.
        async with silent_cleanup("barclays.login.expect_navigation"), page.expect_navigation(
            timeout=_NAV_TIMEOUT_MS,
            wait_until="domcontentloaded",
        ):
            await page.locator(_SUBMIT_BUTTON).click(timeout=_FIELD_TIMEOUT_MS)

        # 4. Settle, then verify we're past the login page.
        async with silent_cleanup("barclays.login.networkidle.post"):
            await page.wait_for_load_state("networkidle", timeout=15000)
        await page.wait_for_timeout(2000)

        title = await _safe_title(page)
        cur = _safe_url(page)
        if "Login" in title or "ct_logon_basic" in cur:
            raise LoginFailedError(
                vendor="barclays",
                title=title,
                url=cur,
                hint=(
                    "if MFA is now required, extend "
                    "imdr.research.auth.loginflows.barclays with the "
                    "Outlook-poll pattern sketched below."
                ),
            )
    finally:
        async with silent_cleanup("barclays.login.page.close"):
            await page.close()


# ---------------------------------------------------------------------
# Future MFA extension (not currently active)
# ---------------------------------------------------------------------
# If Barclays starts requiring MFA, the login() flow above will land on
# a "Verify your identity" page. The expected extension:
#
#   1. After clicking submit, detect MFA page by URL or by presence of
#      a code-input field.
#   2. Poll Outlook via Win32OutlookClient.find_matching(
#          sender="...@barclays.com",
#          subject_contains="Login Code",  # or whatever Barclays uses
#          days_back=1,
#          link_label=None,                # extract code from body, not link
#      )
#   3. Parse the 6-digit code from email body via regex.
#   4. Fill code into the MFA input field, submit, wait for navigation.
#
# Keep this stub here so the caller knows where to extend.
