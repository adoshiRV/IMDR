"""Programmatic DB (Deutsche Bank) Research email-verification-code login.

Unlike the other ``PROGRAMMATIC`` vendors, DB has no password — the
"secret" is a 6-character alphanumeric code DB emails on Submit
(``DoNotReply@markit.esp.db.com``, subject varies: "instant access to
research" / "Verify device"; body contains ``Code: 6BA0EC``). DB's
session **persists in the profile**, so this flow is a refresh-only
fallback: ``is_authenticated`` short-circuits on almost every run and
the login email only fires when the saved session has actually lapsed.
See ``docs/admin/development/db_email_code_login.md`` for the full design.

Selectors captured from a live DOM probe of
``https://research.db.com/research/Register`` (2026-07-22) — all exist
in the DOM up front, hidden until their step is revealed:

* Step 1 (email): ``#input-email`` + the currently-**visible**
  ``button[type="submit"]`` (there are two on the page, one per hidden
  panel — always click whichever is visible).
* Step 2 (code): ``#input-verification-code`` (revealed after step 1) +
  the now-visible ``button[type="submit"]``.
* Step 3 (T&C): ``#checkbox-accept-terms-conditions`` (check if present
  and unchecked) then ``#button-accept-terms-conditions``. MiFID
  radios / country dropdowns are first-registration-only — adoshi is
  already registered, so they should not appear; handled gracefully if
  a step is simply absent.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from ..registry import _live_db
from ._base import LoginFailedError, silent_cleanup

REGISTER_URL = "https://research.db.com/research/Register"
HEALTHCHECK_URL = "https://research.db.com/research/Research/Latest"

# Selectors — see module docstring for the live-probe provenance.
_EMAIL_INPUT = "#input-email"
_CODE_INPUT = "#input-verification-code"
_SUBMIT_BUTTON = 'button[type="submit"]'  # two exist; click the visible one
_TC_CHECKBOX = "#checkbox-accept-terms-conditions"
_TC_ACCEPT_BUTTON = "#button-accept-terms-conditions"

# Code-request email — sender-based filter (more robust than subject,
# which varies). 6 alphanumeric chars, anchored on the "Code:" label to
# avoid matching stray body text (NOT BofA's digits-only pattern).
_CODE_SENDER = "DoNotReply@markit.esp.db.com"
_CODE_PATTERN = r"Code:?\s*([A-Z0-9]{6})\b"
_CODE_WAIT_S = 120  # DB codes expire in 30 min; this is just the poll window

_NAV_TIMEOUT_MS = 45000
_FIELD_TIMEOUT_MS = 15000
_POST_LOGIN_SETTLE_MS = 5000


async def is_authenticated(ctx) -> bool:
    """Navigate the healthcheck URL; True iff we land on authenticated
    DB Research content (reuses the registry's ``_live_db`` predicate,
    already tightened to reject the Register/signin funnel). Never raises.
    """
    page = await ctx.new_page()
    try:
        await page.goto(
            HEALTHCHECK_URL, wait_until="domcontentloaded", timeout=_NAV_TIMEOUT_MS,
        )
        async with silent_cleanup("db.is_authenticated.networkidle"):
            await page.wait_for_load_state("networkidle", timeout=15000)
        title = ""
        async with silent_cleanup("db.is_authenticated.title"):
            title = (await page.title()) or ""
        return _live_db(title, page.url or "")
    except Exception:  # noqa: BLE001
        return False
    finally:
        async with silent_cleanup("db.is_authenticated.page.close"):
            await page.close()


async def _click_visible_submit(page) -> None:
    """The Register page carries two ``button[type="submit"]`` (one per
    hidden step panel) — only the currently-revealed one is clickable."""
    buttons = page.locator(_SUBMIT_BUTTON)
    count = await buttons.count()
    for i in range(count):
        btn = buttons.nth(i)
        try:
            if await btn.is_visible():
                await btn.click(timeout=_FIELD_TIMEOUT_MS)
                return
        except Exception:  # noqa: BLE001
            continue
    raise LoginFailedError(
        vendor="db", hint="no visible Submit button found on Register page",
    )


async def _accept_terms(page) -> None:
    """Step 3 — tick T&C if present, then Accept. MiFID radios / country
    dropdowns are first-registration-only and are skipped entirely
    (adoshi is already registered); this step itself is also handled
    gracefully if it never appears.
    """
    checkbox = page.locator(_TC_CHECKBOX)
    try:
        if await checkbox.count() > 0 and not await checkbox.is_checked():
            await checkbox.check(timeout=_FIELD_TIMEOUT_MS)
    except Exception:  # noqa: BLE001
        pass
    accept = page.locator(_TC_ACCEPT_BUTTON)
    try:
        if await accept.count() > 0 and await accept.is_visible():
            await accept.click(timeout=_FIELD_TIMEOUT_MS)
    except Exception:  # noqa: BLE001
        pass


async def login(ctx, *, username: str, password: str) -> None:
    """Idempotent email-code login. ``password`` is unused — the DB
    "secret" is a code emailed to ``username``'s inbox on Submit.

    Raises :class:`LoginFailedError` if no code email arrives, or if the
    final landing isn't authenticated DB Research content.
    """
    if await is_authenticated(ctx):
        return

    page = await ctx.new_page()
    try:
        await page.goto(
            REGISTER_URL, wait_until="domcontentloaded", timeout=_NAV_TIMEOUT_MS,
        )
        async with silent_cleanup("db.login.networkidle.email"):
            await page.wait_for_load_state("networkidle", timeout=15000)

        # Step 1 — email.
        await page.locator(_EMAIL_INPUT).fill(username, timeout=_FIELD_TIMEOUT_MS)
        await page.wait_for_timeout(300)

        # Freshness baseline: snapshot the newest EXISTING code email BEFORE
        # requesting a new one, so find_code waits for one strictly newer.
        # This is skew-proof (compares two real email timestamps) and can't
        # consume a leftover/older code — DB invalidates the previous code on
        # every new request, so grabbing a stale one gets rejected.
        from imdr.vendors.sessions.outlook import Win32OutlookClient

        outlook = Win32OutlookClient()
        baseline = await asyncio.to_thread(
            outlook.latest_received, sender=_CODE_SENDER,
        )
        floor = baseline if baseline is not None else (
            datetime.now(timezone.utc) - timedelta(minutes=5)
        )

        await _click_visible_submit(page)

        async with silent_cleanup("db.login.networkidle.code"):
            await page.wait_for_load_state("networkidle", timeout=15000)
        await page.wait_for_timeout(1000)

        # Step 2 — read the code off-loop (win32com + time.sleep is blocking;
        # must not freeze other vendors sharing the event loop). Only an
        # email strictly newer than the baseline counts as THIS attempt's.
        code = await asyncio.to_thread(
            outlook.find_code,
            sender=_CODE_SENDER,
            received_after=floor,
            code_pattern=_CODE_PATTERN,
            max_wait_s=_CODE_WAIT_S,
        )
        if not code:
            raise LoginFailedError(
                vendor="db",
                hint=(
                    f"no verification-code email from {_CODE_SENDER} "
                    f"within {_CODE_WAIT_S}s of Submit"
                ),
            )

        await page.locator(_CODE_INPUT).fill(code, timeout=_FIELD_TIMEOUT_MS)
        await page.wait_for_timeout(300)
        await _click_visible_submit(page)

        async with silent_cleanup("db.login.networkidle.terms"):
            await page.wait_for_load_state("networkidle", timeout=15000)
        await page.wait_for_timeout(1000)

        # Step 3 — Terms & Conditions.
        await _accept_terms(page)

        async with silent_cleanup("db.login.networkidle.post"):
            await page.wait_for_load_state("networkidle", timeout=15000)
        await page.wait_for_timeout(_POST_LOGIN_SETTLE_MS)

        title = ""
        async with silent_cleanup("db.login.title"):
            title = (await page.title()) or ""
        cur = page.url or ""
        if not _live_db(title, cur):
            raise LoginFailedError(
                vendor="db",
                title=title,
                url=cur,
                hint="still not on authenticated DB Research content after the code flow",
            )
    finally:
        async with silent_cleanup("db.login.page.close"):
            await page.close()
