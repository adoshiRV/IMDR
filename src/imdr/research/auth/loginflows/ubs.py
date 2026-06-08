"""Programmatic UBS Neo login.

Two-step form (email page → password page) against ``neo.ubs.com``.
Credentials from ``Settings.research_ubs_username`` /
``research_ubs_password``.

Two operational quirks captured during selector discovery
(2026-06-05, see playground/research/ubs_explore/):

1. **Headless rejection** — UBS rejects the ``HeadlessChrome/N`` User-
   Agent. The auth context manager picks up ``headless=False`` from the
   UBS registry spec; do not override.

2. **rememberMe1fa is opt-OUT** — the suffix "1fa" means "after first-
   factor auth". Ticking the checkbox DISABLES remember-me. We never
   touch it; the unchecked default keeps remember-me ON, which is what
   we want for cookie persistence across ``ctx.close()``.

Session persistence — verified 2026-06-05: ``UBS_NEO_USER`` is durable
(2027 expiry); the SAML-bearing cookies are nominally session-scoped
but Playwright's persistent-profile user-data-dir preserves them
across launches. Days-to-weeks of cookie life in practice.

Stale-cookie bootstrap — empirically a profile with EXPIRED ``UBS_NEO_*``
cookies renders the login page with an invisible #email_input (covered
by a "checking session" overlay). We clear ``*.ubs.com`` cookies before
navigating so the form renders from a known cookieless state, then
restore non-UBS cookies (Adobe analytics etc) so we don't destroy
unrelated profile state.

Moved from ``playground/research/ingest/login_ubs.py`` as part of the
2026-06-08 UBS-into-registry change; the old path keeps a re-export
shim for ``crawler_ubs.py`` mid-fetch re-login calls.
"""
from __future__ import annotations

from ._base import LoginFailedError, silent_cleanup

LOGIN_URL = "https://neo.ubs.com/home"           # SSO bounces to /static/login.html
POST_LOGIN_URL_FRAGMENT = "neo.ubs.com/home"
LOGIN_PAGE_URL_FRAGMENT = "/static/login.html"

_EMAIL_INPUT = "#email_input"
_PASSWORD_INPUT = 'input[name="password_input"]'

_NAV_TIMEOUT_MS = 45000
_FIELD_TIMEOUT_MS = 15000
_STEP_SETTLE_MS = 4000
_POST_LOGIN_SETTLE_MS = 6000


async def is_authenticated(ctx) -> bool:
    """Navigate /home; return True if it lands on /home, False if SSO
    bounces us to /static/login.html. Never raises — returns False on
    any error so callers can fall through to a full login.
    """
    page = await ctx.new_page()
    try:
        await page.goto(
            LOGIN_URL, wait_until="domcontentloaded", timeout=_NAV_TIMEOUT_MS,
        )
        async with silent_cleanup("ubs.is_authenticated.networkidle"):
            await page.wait_for_load_state("networkidle", timeout=15000)
        url = page.url or ""
        return POST_LOGIN_URL_FRAGMENT in url and LOGIN_PAGE_URL_FRAGMENT not in url
    except Exception:
        return False
    finally:
        async with silent_cleanup("ubs.is_authenticated.page.close"):
            await page.close()


async def _clear_ubs_cookies(ctx) -> None:
    """Clear stale UBS cookies; preserve everything else.

    See module docstring "Stale-cookie bootstrap" for why this matters.
    """
    try:
        all_cookies = await ctx.cookies()
    except Exception:
        return
    ubs_names = [
        c["name"] for c in all_cookies
        if "ubs.com" in (c.get("domain") or "").lower()
    ]
    if not ubs_names:
        return
    try:
        await ctx.clear_cookies()
    except Exception:
        return
    non_ubs = [
        c for c in all_cookies
        if "ubs.com" not in (c.get("domain") or "").lower()
    ]
    if non_ubs:
        async with silent_cleanup("ubs._clear_ubs_cookies.restore"):
            await ctx.add_cookies(non_ubs)


async def login(ctx, *, username: str, password: str) -> None:
    """Full programmatic login. Idempotent — :func:`is_authenticated`
    short-circuits when cookies are still LIVE.

    Raises :class:`LoginFailedError` if post-submit URL still has the
    login-page fragment (wrong creds, MFA prompt, etc).
    """
    if await is_authenticated(ctx):
        return

    await _clear_ubs_cookies(ctx)

    page = await ctx.new_page()
    try:
        await page.goto(
            LOGIN_URL, wait_until="domcontentloaded", timeout=_NAV_TIMEOUT_MS,
        )
        async with silent_cleanup("ubs.login.networkidle.pre"):
            await page.wait_for_load_state("networkidle", timeout=20000)

        # Step 1: email + Next
        await page.locator(_EMAIL_INPUT).fill(username, timeout=_FIELD_TIMEOUT_MS)
        await page.wait_for_timeout(300)
        await page.get_by_role("button", name="Next").click(timeout=_FIELD_TIMEOUT_MS)

        async with silent_cleanup("ubs.login.networkidle.step1"):
            await page.wait_for_load_state("networkidle", timeout=15000)
        await page.wait_for_timeout(_STEP_SETTLE_MS)
        await page.wait_for_selector(
            _PASSWORD_INPUT, state="visible", timeout=_FIELD_TIMEOUT_MS,
        )

        # Step 2: password + Next. ``rememberMe1fa`` is opt-OUT; do NOT touch it.
        await page.locator(_PASSWORD_INPUT).fill(password, timeout=_FIELD_TIMEOUT_MS)
        await page.wait_for_timeout(300)
        # SSO often does multi-step nav; the first listener may miss.
        # Swallow expect_navigation failures and fall back to settle + verify.
        async with silent_cleanup("ubs.login.expect_navigation"), page.expect_navigation(
            timeout=_NAV_TIMEOUT_MS, wait_until="domcontentloaded",
        ):
            await page.get_by_role("button", name="Next").click(
                timeout=_FIELD_TIMEOUT_MS,
            )

        async with silent_cleanup("ubs.login.networkidle.post"):
            await page.wait_for_load_state("networkidle", timeout=20000)
        await page.wait_for_timeout(_POST_LOGIN_SETTLE_MS)

        cur = page.url or ""
        title = ""
        async with silent_cleanup("ubs.login.title"):
            title = (await page.title()) or ""
        if LOGIN_PAGE_URL_FRAGMENT in cur:
            raise LoginFailedError(
                vendor="ubs",
                title=title,
                url=cur,
                hint=(
                    "if MFA is now required, extend "
                    "imdr.research.auth.loginflows.ubs with the "
                    "Outlook-poll pattern sketched in loginflows.barclays."
                ),
            )
        if POST_LOGIN_URL_FRAGMENT not in cur:
            raise LoginFailedError(
                vendor="ubs",
                title=title,
                url=cur,
                hint="landed at unexpected URL; expected /home",
            )
    finally:
        async with silent_cleanup("ubs.login.page.close"):
            await page.close()
