"""Contract + shared helpers for per-vendor programmatic login flows.

Each vendor module under :mod:`imdr.research.auth.loginflows` must
expose two coroutines:

.. code-block:: python

    async def is_authenticated(ctx) -> bool:
        '''Quick session probe — navigate the home/landing URL and
        decide whether persistent cookies still get us past SSO.
        Must NOT raise — return False on any error.'''

    async def login(ctx, *, username: str, password: str) -> None:
        '''Full form-fill login. Must be idempotent — call
        :func:`is_authenticated` first and short-circuit when already
        signed in. Raises :class:`LoginFailedError` if the flow lands
        back on the login page (wrong creds, MFA prompt, etc).'''

The :mod:`..context` and :mod:`..refresh` modules dispatch via
``getattr(loginflow_module, "is_authenticated" | "login")``; the
``Protocol`` below is documentation, not runtime-checked.

This module also exposes :func:`silent_cleanup`, the async context
manager loginflows use around Playwright teardown calls (``page.close``,
``ctx.close``, ``page.title``) that can spuriously raise on a
torn-down execution context. Centralised so the swallow-pattern is
visible at one site, and so we can route to structured logging later
without touching every loginflow.
"""
from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator
from typing import Any, Protocol

import structlog

# Re-export the canonical exception classes so existing
# ``from ._base import LoginFailedError`` imports keep working.
from ..errors import (
    AuthError,
    LoginFailedError,
    MFARequired,
)

_log = structlog.get_logger(__name__)


class LoginFlow(Protocol):
    """Static-typing-only contract; runtime dispatch uses ``getattr``."""

    async def is_authenticated(self, ctx: Any) -> bool: ...
    async def login(
        self, ctx: Any, *, username: str, password: str,
    ) -> None: ...


@contextlib.asynccontextmanager
async def silent_cleanup(label: str = "cleanup") -> AsyncIterator[None]:
    """Swallow exceptions in Playwright teardown blocks.

    Playwright's ``page.close()`` / ``page.title()`` / ``page.url``
    can raise when the underlying execution context was torn down by
    a redirect mid-call (e.g. PingFederate SSO chains). These failures
    are not actionable in cleanup paths — the caller already has its
    result. We log at debug for forensics; never propagate.

    Usage::

        async with silent_cleanup("page.close"):
            await page.close()
    """
    try:
        yield
    except Exception as exc:
        _log.debug(
            "silent_cleanup_swallowed",
            label=label,
            error_type=type(exc).__name__,
            error=str(exc)[:200],
        )


__all__ = [
    "AuthError",
    "LoginFailedError",
    "LoginFlow",
    "MFARequired",
    "silent_cleanup",
]
