"""Programmatic Nomura NomuraNow login.

Form-fill against the real login page
``https://www.nomuranow.com/research/m/public/login`` — email + password,
**no MFA**. Credentials from ``Settings.research_nomura_username`` /
``research_nomura_password`` (research@rvcapital.com). Selectors verified
via a live DOM probe 2026-07-22.

**Prior bug (fixed 2026-07-22):** ``LOGIN_URL`` used to point at the
research *portal* (``…/portal/site/nnpub/research/``). Logged out, that
serves a 'Not Found' SPA shell with **no login form**, so the fill did
nothing and ``is_authenticated`` was fooled by the shell → the flow
returned an empty session (0 KB storage_state) and the search API 401'd.
Now the flow hits the actual login page and verifies auth via the
registry's ``_live_nomura`` predicate (which rejects the 'Not Found'
shell) against the portal.
"""
from __future__ import annotations

from ..registry import _live_nomura
from ._base import LoginFailedError, silent_cleanup

LOGIN_URL = "https://www.nomuranow.com/research/m/public/login"
# Authenticated landing (title 'Nomura Research'); the old desktop portal
# path rendered 'Not Found' even when authed, so it could never verify.
HEALTHCHECK_URL = "https://www.nomuranow.com/research/m/Home"

# Verified via live DOM probe 2026-07-22.
_USER_INPUT = 'input[name="username"]'
_PASSWORD_INPUT = 'input[name="password"]'
_LOGIN_BUTTON = "#login-button"  # NOT #magicLink-button (passwordless email link)

_NAV_TIMEOUT_MS = 45000
_FIELD_TIMEOUT_MS = 15000
_POST_LOGIN_SETTLE_MS = 5000


async def is_authenticated(ctx) -> bool:
    """Navigate the research portal; True iff it renders authenticated
    content. Reuses the registry ``_live_nomura`` predicate, which rejects
    the logged-out 'Not Found' shell. Never raises."""
    page = await ctx.new_page()
    try:
        await page.goto(
            HEALTHCHECK_URL, wait_until="domcontentloaded", timeout=_NAV_TIMEOUT_MS,
        )
        async with silent_cleanup("nomura.is_authenticated.networkidle"):
            await page.wait_for_load_state("networkidle", timeout=15000)
        title = ""
        async with silent_cleanup("nomura.is_authenticated.title"):
            title = (await page.title()) or ""
        return _live_nomura(title, page.url or "")
    except Exception:  # noqa: BLE001
        return False
    finally:
        async with silent_cleanup("nomura.is_authenticated.page.close"):
            await page.close()


async def login(ctx, *, username: str, password: str) -> None:
    """Idempotent email+password form login. Raises :class:`LoginFailedError`
    if the portal is still unauthenticated afterwards."""
    if await is_authenticated(ctx):
        return

    page = await ctx.new_page()
    try:
        await page.goto(
            LOGIN_URL, wait_until="domcontentloaded", timeout=_NAV_TIMEOUT_MS,
        )
        async with silent_cleanup("nomura.login.networkidle.pre"):
            await page.wait_for_load_state("networkidle", timeout=15000)

        await page.locator(_USER_INPUT).fill(username, timeout=_FIELD_TIMEOUT_MS)
        await page.wait_for_timeout(300)
        await page.locator(_PASSWORD_INPUT).fill(password, timeout=_FIELD_TIMEOUT_MS)
        await page.wait_for_timeout(300)

        # Click Log In. It may navigate to the portal or resolve via AJAX +
        # redirect; either way we re-verify against the portal below rather
        # than trusting the post-submit page, so a missed nav event is fine.
        async with silent_cleanup("nomura.login.expect_navigation"), page.expect_navigation(
            timeout=_NAV_TIMEOUT_MS, wait_until="domcontentloaded",
        ):
            await page.locator(_LOGIN_BUTTON).click(timeout=_FIELD_TIMEOUT_MS)

        async with silent_cleanup("nomura.login.networkidle.post"):
            await page.wait_for_load_state("networkidle", timeout=15000)
        await page.wait_for_timeout(_POST_LOGIN_SETTLE_MS)
    finally:
        async with silent_cleanup("nomura.login.page.close"):
            await page.close()

    # Verify against the research portal (fresh page in the same context).
    if not await is_authenticated(ctx):
        raise LoginFailedError(
            vendor="nomura",
            url=LOGIN_URL,
            hint=(
                "login submitted but the research portal is still not "
                "authenticated — check creds (research@rvcapital.com) or "
                "selector drift on the login form"
            ),
        )
