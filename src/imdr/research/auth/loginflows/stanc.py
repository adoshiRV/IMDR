"""Programmatic Standard Chartered Research login.

Form-fill flow against ``research.sc.com``. Credentials from
``Settings.research_stanc_username`` / ``research_stanc_password``.

**⚠ Selectors unverified.** Best-guess selectors below — verify via
``python -m imdr.research.auth validate --vendor stanc``; on failure,
run a headed Playwright probe and update the selectors.

**MFA fallback policy.** If validate reports MFA gating, revert the
STANC registry entry to ``PROFILE_ONLY`` and drop this module's
import from ``loginflows/__init__.py``.
"""
from __future__ import annotations

from ._base import LoginFailedError, silent_cleanup

LOGIN_URL = "https://research.sc.com/research/"

# Best-guess selectors — verify via validate command.
_USER_INPUT = 'input[name="username"], input[name="userid"], #username'
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
        async with silent_cleanup("stanc.is_authenticated.networkidle"):
            await page.wait_for_load_state("networkidle", timeout=15000)
        url = page.url or ""
        title = ""
        async with silent_cleanup("stanc.is_authenticated.title"):
            title = (await page.title()) or ""
        return "research.sc.com" in url and not _on_login_page(url, title)
    except Exception:
        return False
    finally:
        async with silent_cleanup("stanc.is_authenticated.page.close"):
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
        async with silent_cleanup("stanc.login.networkidle.pre"):
            await page.wait_for_load_state("networkidle", timeout=15000)

        await page.locator(_USER_INPUT).first.fill(
            username, timeout=_FIELD_TIMEOUT_MS,
        )
        await page.wait_for_timeout(300)
        await page.locator(_PASSWORD_INPUT).first.fill(
            password, timeout=_FIELD_TIMEOUT_MS,
        )
        await page.wait_for_timeout(300)

        async with silent_cleanup("stanc.login.expect_navigation"), page.expect_navigation(
            timeout=_NAV_TIMEOUT_MS, wait_until="domcontentloaded",
        ):
            await page.locator(_SUBMIT_BUTTON).first.click(
                timeout=_FIELD_TIMEOUT_MS,
            )

        async with silent_cleanup("stanc.login.networkidle.post"):
            await page.wait_for_load_state("networkidle", timeout=15000)
        await page.wait_for_timeout(_POST_LOGIN_SETTLE_MS)

        cur = page.url or ""
        title = ""
        async with silent_cleanup("stanc.login.title"):
            title = (await page.title()) or ""
        if _on_login_page(cur, title):
            raise LoginFailedError(
                vendor="stanc",
                title=title,
                url=cur,
                hint=(
                    "still on login/verify page — likely MFA gate, "
                    "wrong creds, or selector mismatch. If MFA, revert "
                    "STANC to PROFILE_ONLY in the registry."
                ),
            )
    finally:
        async with silent_cleanup("stanc.login.page.close"):
            await page.close()
