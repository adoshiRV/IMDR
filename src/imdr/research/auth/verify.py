"""Session-liveness checks for research portals.

:func:`verify` opens a short-lived :class:`BrowserContext` against the
vendor's persistent profile, navigates the healthcheck URL, and
returns a :class:`SessionStatus` based on the registry's predicate.
No login attempt is made here — :mod:`.refresh` is the place that
knows how to recover from EXPIRED.
"""
from __future__ import annotations

import contextlib
from dataclasses import dataclass
from enum import StrEnum

from ._paths import profile_dir
from .registry import AuthMode, VendorAuthSpec, get_spec


class SessionStatus(StrEnum):
    """Result of a session healthcheck."""

    #: Cookies / SSO still get us past the landing page.
    LIVE = "live"

    #: Landed on a login page or otherwise failed the predicate. For
    #: :data:`AuthMode.PROGRAMMATIC` vendors this is recoverable
    #: automatically; for others it means a human needs to re-auth.
    EXPIRED = "expired"

    #: Profile dir does not exist or is empty — never been seeded.
    NO_PROFILE = "no_profile"

    #: Healthcheck threw (network down, browser crash, etc.).
    UNREACHABLE = "unreachable"


@dataclass(slots=True, frozen=True)
class VerifyResult:
    vendor: str
    status: SessionStatus
    title: str = ""
    url: str = ""
    detail: str = ""


_HEALTHCHECK_NAV_TIMEOUT_MS = 30000
_HEALTHCHECK_SETTLE_TIMEOUT_MS = 10000


def _profile_is_seeded(vendor: str) -> bool:
    """Cheap check: a never-seeded profile dir has no ``Default/`` (Chrome
    creates this on first launch). We don't want to spend ~10s booting
    Chrome just to confirm it's empty.
    """
    p = profile_dir(vendor)
    # First-run Chrome populates Default/. If it's missing AND the dir
    # has no other children, treat as never-seeded.
    if (p / "Default").exists():
        return True
    try:
        return any(p.iterdir())
    except OSError:
        return False


async def _probe(spec: VendorAuthSpec) -> tuple[bool, str, str]:
    """Open a context, navigate the healthcheck URL, run the predicate.

    Returns ``(is_live, title, url)``. Does NOT swallow exceptions —
    the caller wraps to map errors to :data:`SessionStatus.UNREACHABLE`.
    Header-factory failures (e.g. missing JPM janus_user) propagate as
    real auth failures.
    """
    from playwright.async_api import async_playwright

    from .loginflows._base import silent_cleanup

    async with async_playwright() as pw:
        ctx = await pw.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir(spec.code)),
            channel="chrome",
            headless=spec.headless,
            accept_downloads=False,
        )
        try:
            if spec.extra_headers_factory is not None:
                # Note: extra_headers_factory raises propagate intentionally —
                # missing janus_user etc. is an auth failure, not a cleanup.
                headers = spec.extra_headers_factory()
                if headers:
                    await ctx.set_extra_http_headers(headers)

            page = await ctx.new_page()
            try:
                await page.goto(
                    spec.healthcheck_url,
                    wait_until="domcontentloaded",
                    timeout=_HEALTHCHECK_NAV_TIMEOUT_MS,
                )
                async with silent_cleanup("verify._probe.networkidle"):
                    await page.wait_for_load_state(
                        "networkidle",
                        timeout=_HEALTHCHECK_SETTLE_TIMEOUT_MS,
                    )
                title = ""
                async with silent_cleanup("verify._probe.title"):
                    title = (await page.title()) or ""
                url = ""
                with contextlib.suppress(Exception):
                    url = page.url or ""
                return bool(spec.healthcheck_predicate(title, url)), title, url
            finally:
                async with silent_cleanup("verify._probe.page.close"):
                    await page.close()
        finally:
            async with silent_cleanup("verify._probe.ctx.close"):
                await ctx.close()


async def verify(vendor: str) -> VerifyResult:
    """Run a healthcheck for ``vendor`` and return the result.

    Never raises — every error maps to a SessionStatus so callers can
    keep iterating over a vendor list without try/except per call.
    """
    spec = get_spec(vendor)

    if not _profile_is_seeded(vendor):
        return VerifyResult(
            vendor=vendor,
            status=SessionStatus.NO_PROFILE,
            detail=(
                f"no profile at {profile_dir(vendor)} — run "
                f"`python -m imdr.research.auth login --vendor {vendor}` "
                f"to seed via headed SSO."
                if spec.mode != AuthMode.PROGRAMMATIC
                else f"no profile at {profile_dir(vendor)} — first "
                     f"`refresh --vendor {vendor}` will create one."
            ),
        )

    try:
        live, title, url = await _probe(spec)
    except Exception as exc:
        return VerifyResult(
            vendor=vendor,
            status=SessionStatus.UNREACHABLE,
            detail=f"{type(exc).__name__}: {exc!s:.300}",
        )

    return VerifyResult(
        vendor=vendor,
        status=SessionStatus.LIVE if live else SessionStatus.EXPIRED,
        title=title,
        url=url,
    )


__all__ = ["SessionStatus", "VerifyResult", "verify"]
