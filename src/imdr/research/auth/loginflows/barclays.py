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
# How long to wait for the OneTrust cookie banner to actually render before
# clicking it. An immediate is_visible() check is flaky — the banner paints a
# beat late, the click is skipped, and the banner then intercepts the submit
# so login lands back on ct_logon_basic (matrix 2026-07-21: 1/2). Waiting for
# it to be visible is reliable (2/2, headed and headless).
_COOKIE_APPEAR_TIMEOUT_MS = 15000
# Independent full login attempts before giving up. Each attempt re-navigates,
# re-dismisses the banner, and re-submits; a retry catches the occasional late-
# banner / slow-portal miss that a single attempt hits.
_MAX_LOGIN_ATTEMPTS = 3


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


async def _attempt_login(ctx, *, username: str, password: str) -> tuple[bool, str, str]:
    """One full nav → dismiss-banner → fill → submit → verify cycle.

    Returns ``(ok, title, url)`` — ``ok`` is True iff we landed past the
    login page. Raises nothing for a stuck login (the caller decides
    whether to retry or raise); genuine navigation errors propagate.
    """
    page = await ctx.new_page()
    try:
        await page.goto(LOGIN_URL, wait_until="commit", timeout=_NAV_TIMEOUT_MS)
        async with silent_cleanup("barclays.login.networkidle.pre"):
            await page.wait_for_load_state("networkidle", timeout=15000)

        # 1. Cookie banner — WAIT for it to render, then click. An immediate
        #    is_visible() check is flaky (see _COOKIE_APPEAR_TIMEOUT_MS); an
        #    undismissed banner intercepts the submit and login fails. If the
        #    banner never appears (already accepted this session), the
        #    wait_for times out and we proceed — that's fine.
        async with silent_cleanup("barclays.login.cookie_banner"):
            cookie_btn = page.locator(_COOKIE_ACCEPT).first
            try:
                await cookie_btn.wait_for(
                    state="visible", timeout=_COOKIE_APPEAR_TIMEOUT_MS
                )
                await cookie_btn.click(timeout=_COOKIE_TIMEOUT_MS)
                await page.wait_for_timeout(800)
            except Exception:  # noqa: BLE001
                pass  # banner genuinely absent — proceed to the form

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
        ok = "Login" not in title and "ct_logon_basic" not in cur
        return ok, title, cur
    finally:
        async with silent_cleanup("barclays.login.page.close"):
            await page.close()


async def login(ctx, *, username: str, password: str) -> None:
    """Full programmatic login — idempotent, with retry.

    Calls :func:`is_authenticated` first and short-circuits if the
    persistent cookie still works. Otherwise runs up to
    :data:`_MAX_LOGIN_ATTEMPTS` independent login cycles (each
    re-navigates + re-dismisses the cookie banner + re-submits) — a
    retry absorbs the occasional late-banner / slow-portal miss that
    makes a single attempt flaky. Raises :class:`LoginFailedError` only
    if every attempt lands back on the login page (genuine cause:
    wrong creds, or Barclays flipped on MFA for this device).
    """
    if await is_authenticated(ctx):
        return

    last_title, last_url = "", ""
    for _attempt in range(1, _MAX_LOGIN_ATTEMPTS + 1):
        ok, last_title, last_url = await _attempt_login(
            ctx, username=username, password=password
        )
        if ok:
            return
        # Stuck on the login page — likely the cookie banner intercepted the
        # submit on this cycle. Retry with a fresh page; the banner is usually
        # accepted by now, so the next attempt sails through.

    raise LoginFailedError(
        vendor="barclays",
        title=last_title,
        url=last_url,
        hint=(
            f"login still on the sign-in page after {_MAX_LOGIN_ATTEMPTS} "
            "attempts. If MFA is now required, extend "
            "imdr.research.auth.loginflows.barclays with the Outlook-poll "
            "pattern sketched below."
        ),
    )


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
