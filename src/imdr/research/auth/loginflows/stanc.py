"""Programmatic Standard Chartered Global Research login.

The login page (``research.sc.com/research/api/application/static/login``)
defaults to an **email activation-link** flow (submit email → SC emails a
device-activation link). But it also offers a password path behind an
**"Already have a password?"** link — that's what we use, with
``Settings.research_stanc_username`` (email) + ``research_stanc_password``.
No MFA. "Keep me logged in" is ticked so the session persists (the flow is
a refresh-only fallback — ``is_authenticated`` short-circuits otherwise).

Selectors verified via a live DOM probe 2026-07-22.

**Prior bug (fixed 2026-07-22):** the old flow pointed at
``research.sc.com/research/`` (302s to an error page), never clicked
"Already have a password?", and used best-guess username/password
selectors that don't exist on the default (activation-link) form — so it
never authenticated and the ``newSearch`` API returned a session error.
"""
from __future__ import annotations

import re

from ..registry import _live_stanc
from ._base import LoginFailedError, silent_cleanup

LOGIN_URL = "https://research.sc.com/research/api/application/static/login"
HEALTHCHECK_URL = "https://research.sc.com/research/api/application/static/"

# Verified via live DOM probe 2026-07-22 (after clicking "Already have a
# password?" to switch off the default activation-link form).
_PW_TOGGLE = re.compile(r"already have a password", re.IGNORECASE)
_EMAIL_INPUT = "#txtemail"
_PASSWORD_INPUT = "#txtpwd"
_LOGIN_BUTTON = "#btnlogin"
# "Keep me logged in" = a visible <span class="LoginPage-kmli"> label that
# is itself the toggle (there is no adjacent standard checkbox input —
# #chkbox-id on this page is an unrelated category filter). Clicking the
# span extends session persistence.
_KEEP_LABEL = "span.LoginPage-kmli"
_COOKIE_ACCEPT = "#accept-recommended-btn-handler"

_NAV_TIMEOUT_MS = 45000
_FIELD_TIMEOUT_MS = 15000
_POST_LOGIN_SETTLE_MS = 5000


async def is_authenticated(ctx) -> bool:
    """Navigate the portal home; True iff authenticated (reuses the registry
    ``_live_stanc`` predicate — authed stays on ``…/static/``, logged out
    redirects to ``…/static/login``). Never raises."""
    page = await ctx.new_page()
    try:
        await page.goto(
            HEALTHCHECK_URL, wait_until="domcontentloaded", timeout=_NAV_TIMEOUT_MS,
        )
        async with silent_cleanup("stanc.is_authenticated.networkidle"):
            await page.wait_for_load_state("networkidle", timeout=4000)
        title = ""
        async with silent_cleanup("stanc.is_authenticated.title"):
            title = (await page.title()) or ""
        return _live_stanc(title, page.url or "")
    except Exception:  # noqa: BLE001
        return False
    finally:
        async with silent_cleanup("stanc.is_authenticated.page.close"):
            await page.close()


async def _dismiss_cookie_banner(page) -> None:
    async with silent_cleanup("stanc.cookie"):
        btn = page.locator(_COOKIE_ACCEPT)
        if await btn.count() > 0 and await btn.is_visible():
            await btn.click(timeout=5000)
            await page.wait_for_timeout(400)


async def login(ctx, *, username: str, password: str) -> None:
    """Idempotent email+password login via the "Already have a password?"
    path. Raises :class:`LoginFailedError` if still unauthenticated after."""
    if await is_authenticated(ctx):
        return

    page = await ctx.new_page()
    try:
        await page.goto(
            LOGIN_URL, wait_until="domcontentloaded", timeout=_NAV_TIMEOUT_MS,
        )
        async with silent_cleanup("stanc.login.networkidle.pre"):
            await page.wait_for_load_state("networkidle", timeout=4000)
        await _dismiss_cookie_banner(page)

        # Switch off the default activation-link form to the password form.
        await page.get_by_text(_PW_TOGGLE).first.click(timeout=_FIELD_TIMEOUT_MS)
        await page.wait_for_timeout(1500)

        await page.locator(_EMAIL_INPUT).fill(username, timeout=_FIELD_TIMEOUT_MS)
        await page.wait_for_timeout(200)
        await page.locator(_PASSWORD_INPUT).fill(password, timeout=_FIELD_TIMEOUT_MS)
        await page.wait_for_timeout(200)

        # Tick "Keep me logged in" (the visible <span> label is the toggle;
        # there is no adjacent standard checkbox input). Best-effort,
        # non-fatal.
        async with silent_cleanup("stanc.login.keep_logged_in"):
            label = page.locator(_KEEP_LABEL)
            if await label.count() > 0:
                await label.first.click(timeout=5000)

        async with silent_cleanup("stanc.login.expect_navigation"), page.expect_navigation(
            timeout=_NAV_TIMEOUT_MS, wait_until="domcontentloaded",
        ):
            await page.locator(_LOGIN_BUTTON).click(timeout=_FIELD_TIMEOUT_MS)

        async with silent_cleanup("stanc.login.networkidle.post"):
            await page.wait_for_load_state("networkidle", timeout=4000)
        await page.wait_for_timeout(_POST_LOGIN_SETTLE_MS)
    finally:
        async with silent_cleanup("stanc.login.page.close"):
            await page.close()

    if not await is_authenticated(ctx):
        raise LoginFailedError(
            vendor="stanc",
            url=LOGIN_URL,
            hint=(
                "clicked 'Already have a password?' and submitted but the "
                "portal is still not authenticated — check creds "
                "(adoshi@rvcapital.com) or selector drift on the login form"
            ),
        )
