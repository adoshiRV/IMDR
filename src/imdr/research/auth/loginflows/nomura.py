"""Programmatic Nomura NomuraNow login.

Form-fill flow against ``www.nomuranow.com``. Credentials from
``Settings.research_nomura_username`` / ``research_nomura_password``.

**⚠ Selectors unverified.** This module ships with best-guess
selectors. Verify via ``python -m imdr.research.auth validate --vendor
nomura``; on failure, run a headed Playwright probe against the live
login form, update the selectors below, and retry.

**MFA fallback policy.** If validate reports MFA gating, revert the
Nomura registry entry to ``PROFILE_ONLY`` and drop this module's
import from ``loginflows/__init__.py``.
"""
from __future__ import annotations

from ._base import LoginFailedError, silent_cleanup

LOGIN_URL = "https://www.nomuranow.com/portal/site/nnpub/research/"

# Best-guess selectors — verify via validate command.
_USER_INPUT = 'input[name="userid"], input[name="username"], #userid, #username'
_PASSWORD_INPUT = 'input[name="password"], input[type="password"]'
_SUBMIT_BUTTON = 'button[type="submit"], input[type="submit"]'

_NAV_TIMEOUT_MS = 45000
_FIELD_TIMEOUT_MS = 15000
_POST_LOGIN_SETTLE_MS = 5000


def _on_login_page(url: str, title: str) -> bool:
    return (
        "login" in url.lower()
        or "signon" in url.lower()
        or "Sign" in title
        or "Login" in title
    )


async def is_authenticated(ctx) -> bool:
    page = await ctx.new_page()
    try:
        await page.goto(
            LOGIN_URL, wait_until="domcontentloaded", timeout=_NAV_TIMEOUT_MS,
        )
        async with silent_cleanup("nomura.is_authenticated.networkidle"):
            await page.wait_for_load_state("networkidle", timeout=15000)
        url = page.url or ""
        title = ""
        async with silent_cleanup("nomura.is_authenticated.title"):
            title = (await page.title()) or ""
        return "nomuranow.com" in url and not _on_login_page(url, title)
    except Exception:
        return False
    finally:
        async with silent_cleanup("nomura.is_authenticated.page.close"):
            await page.close()


async def login(ctx, *, username: str, password: str) -> None:
    """Idempotent form-fill login. Raises :class:`LoginFailedError` on
    failure (wrong creds, MFA gate, selector miss).
    """
    if await is_authenticated(ctx):
        return

    page = await ctx.new_page()
    try:
        await page.goto(
            LOGIN_URL, wait_until="domcontentloaded", timeout=_NAV_TIMEOUT_MS,
        )
        async with silent_cleanup("nomura.login.networkidle.pre"):
            await page.wait_for_load_state("networkidle", timeout=15000)

        await page.locator(_USER_INPUT).first.fill(
            username, timeout=_FIELD_TIMEOUT_MS,
        )
        await page.wait_for_timeout(300)
        await page.locator(_PASSWORD_INPUT).first.fill(
            password, timeout=_FIELD_TIMEOUT_MS,
        )
        await page.wait_for_timeout(300)

        async with silent_cleanup("nomura.login.expect_navigation"), page.expect_navigation(
            timeout=_NAV_TIMEOUT_MS, wait_until="domcontentloaded",
        ):
            await page.locator(_SUBMIT_BUTTON).first.click(
                timeout=_FIELD_TIMEOUT_MS,
            )

        async with silent_cleanup("nomura.login.networkidle.post"):
            await page.wait_for_load_state("networkidle", timeout=15000)
        await page.wait_for_timeout(_POST_LOGIN_SETTLE_MS)

        cur = page.url or ""
        title = ""
        async with silent_cleanup("nomura.login.title"):
            title = (await page.title()) or ""
        if _on_login_page(cur, title):
            raise LoginFailedError(
                vendor="nomura",
                title=title,
                url=cur,
                hint=(
                    "still on login/verify page — likely MFA gate, "
                    "wrong creds, or selector mismatch. If MFA, revert "
                    "Nomura to PROFILE_ONLY in the registry."
                ),
            )
    finally:
        async with silent_cleanup("nomura.login.page.close"):
            await page.close()
