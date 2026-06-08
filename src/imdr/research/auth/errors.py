"""Typed exception hierarchy for ``imdr.research.auth``.

Every exception the auth module raises is a subclass of :class:`AuthError`.
Each subclass carries structured context (vendor, healthcheck URL, MFA
kind, etc.) so the email formatter and the CLI's BLOCKED line can
render rich payloads without ``str(exc)`` parsing.

Design rules:

* Exceptions are about **what** went wrong, never **who** observed it.
  Don't leak "ingest" / "heartbeat" / "validate" into the class itself —
  that's the caller's context, conveyed via formatter kwargs.
* ``recoverable`` is a class-level hint, not a runtime promise. It says
  "a programmatic retry has a reasonable chance" — typically True for
  :class:`SessionExpired` against a ``PROGRAMMATIC`` vendor, False for
  :class:`MFARequired` or :class:`CredentialMissing`.
* The hierarchy is wide and shallow: every concrete error inherits
  directly from :class:`AuthError` (or :class:`LoginFailedError`, which
  is a thin specialisation). Avoid deep inheritance chains.
"""
from __future__ import annotations


class AuthError(Exception):
    """Base for everything :mod:`imdr.research.auth` raises.

    Subclasses set instance attributes — ``vendor`` is always present,
    other fields are subclass-specific. The default ``__str__`` is the
    bare message; ``__repr__`` includes the vendor for log readability.
    """

    #: Class-level default — overridden by SessionExpired et al.
    recoverable: bool = False

    def __init__(self, message: str, *, vendor: str = "") -> None:
        super().__init__(message)
        self.vendor: str = vendor

    def __repr__(self) -> str:
        return f"{type(self).__name__}(vendor={self.vendor!r}, msg={self.args[0]!r})"


class UnknownVendor(AuthError, KeyError):  # noqa: N818 — semantic name reads better
    """Vendor code not in :data:`VENDOR_AUTH_REGISTRY`.

    Inherits from :class:`KeyError` too so existing ``except KeyError``
    blocks (e.g. in unit tests written against the previous behaviour)
    keep working during the migration window.
    """


class CredentialMissing(AuthError):  # noqa: N818 — semantic name reads better
    """Programmatic-login credentials not set in :class:`Settings`.

    Carries ``env_var_prefix`` so the email payload can tell the
    operator the exact env vars to populate.
    """

    def __init__(
        self,
        message: str,
        *,
        vendor: str,
        env_var_prefix: str,
    ) -> None:
        super().__init__(message, vendor=vendor)
        self.env_var_prefix: str = env_var_prefix


class SessionExpired(AuthError):  # noqa: N818 — semantic name reads better
    """:func:`verify` returned EXPIRED.

    Recoverable iff the vendor's mode is ``PROGRAMMATIC`` (the auth
    context manager will attempt a fresh login). For PROFILE_ONLY /
    HEADER_INJECTION vendors this means a human must re-SSO.
    """

    def __init__(
        self,
        message: str,
        *,
        vendor: str,
        recoverable: bool = False,
    ) -> None:
        super().__init__(message, vendor=vendor)
        self.recoverable = recoverable


class LoginFailedError(AuthError):
    """A programmatic login flow landed back on the login page.

    Carries the post-submit ``title`` + ``url`` so the email payload
    and the BLOCKED line can tell the operator what they're looking
    at — typically "wrong creds", "MFA gate", or "selector mismatch".
    """

    def __init__(
        self,
        *,
        vendor: str,
        title: str = "",
        url: str = "",
        hint: str = "",
    ) -> None:
        suffix = f"  ({hint})" if hint else ""
        super().__init__(
            f"{vendor} login failed: still on '{title}' / {url}{suffix}",
            vendor=vendor,
        )
        self.title: str = title
        self.url: str = url
        self.hint: str = hint


class MFARequired(LoginFailedError):  # noqa: N818 — semantic name reads better
    """Login was gated by MFA we can't satisfy programmatically.

    Subclass of :class:`LoginFailedError` so existing handlers that
    catch ``LoginFailedError`` still see this case. The ``mfa_kind``
    discriminator lets the email formatter render a clear "biometric
    push expected" / "hardware token required" etc. badge.
    """

    def __init__(
        self,
        *,
        vendor: str,
        title: str = "",
        url: str = "",
        mfa_kind: str = "unknown",
        hint: str = "",
    ) -> None:
        super().__init__(
            vendor=vendor, title=title, url=url,
            hint=hint or f"MFA gate ({mfa_kind})",
        )
        self.mfa_kind: str = mfa_kind


class PDFValidationError(AuthError):
    """``validate`` step 4: bytes don't look like a real PDF.

    ``reason`` is one of: ``"bad_magic"``, ``"too_small"``,
    ``"pypdf_parse_failed"``, ``"zero_pages"``, ``"empty"``.
    """

    def __init__(
        self,
        message: str,
        *,
        vendor: str,
        n_bytes: int,
        reason: str,
    ) -> None:
        super().__init__(message, vendor=vendor)
        self.n_bytes: int = n_bytes
        self.reason: str = reason


__all__ = [
    "AuthError",
    "CredentialMissing",
    "LoginFailedError",
    "MFARequired",
    "PDFValidationError",
    "SessionExpired",
    "UnknownVendor",
]
