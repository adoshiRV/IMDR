"""Global authenticator for research portals.

Single entry point :func:`get_authed_context` replaces the open-coded
``launch_persistent_context`` block that used to live in every vendor
crawler. Verifies the session before yielding the context and snapshots
``storage_state`` on exit so the cookies + localStorage survive a
corrupted profile dir.

Public surface::

    from imdr.research.auth import (
        get_authed_context,        # async ctx mgr — used by crawlers
        verify, refresh_all,       # session health
        SessionStatus, AuthMode,
        VENDOR_AUTH_REGISTRY,
    )

CLI::

    python -m imdr.research.auth check   [--vendor X|all]
    python -m imdr.research.auth refresh [--vendor X|all]
    python -m imdr.research.auth login    --vendor X
    python -m imdr.research.auth status

See ``docs/admin/research/auth.md`` (when written) for the full
operator runbook; until then, the module docstrings are the source.
"""
from __future__ import annotations

from .context import get_authed_context
from .errors import (
    AuthError,
    CredentialMissing,
    LoginFailedError,
    MFARequired,
    PDFValidationError,
    SessionExpired,
    UnknownVendor,
)
from .notify import send_auth_email
from .refresh import RefreshOutcome, refresh, refresh_all
from .registry import VENDOR_AUTH_REGISTRY, AuthMode, VendorAuthSpec
from .verify import SessionStatus, verify

__all__ = [
    "VENDOR_AUTH_REGISTRY",
    "AuthError",
    "AuthMode",
    "CredentialMissing",
    "LoginFailedError",
    "MFARequired",
    "PDFValidationError",
    "RefreshOutcome",
    "SessionExpired",
    "SessionStatus",
    "UnknownVendor",
    "VendorAuthSpec",
    "get_authed_context",
    "refresh",
    "refresh_all",
    "send_auth_email",
    "verify",
]
