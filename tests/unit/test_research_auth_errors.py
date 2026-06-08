"""Typed exception hierarchy for imdr.research.auth."""
from __future__ import annotations

import pytest

from imdr.research.auth.errors import (
    AuthError,
    CredentialMissing,
    LoginFailedError,
    MFARequired,
    PDFValidationError,
    SessionExpired,
    UnknownVendor,
)


# ---------------------------------------------------------------------
# Hierarchy
# ---------------------------------------------------------------------

@pytest.mark.parametrize("cls", [
    UnknownVendor,
    CredentialMissing,
    SessionExpired,
    LoginFailedError,
    MFARequired,
    PDFValidationError,
])
def test_every_concrete_error_inherits_authError(cls):
    assert issubclass(cls, AuthError)


def test_unknown_vendor_is_also_keyerror():
    """KeyError backcompat — existing `except KeyError` blocks still match."""
    assert issubclass(UnknownVendor, KeyError)


def test_mfa_required_is_loginfailederror_subclass():
    """Handlers that catch LoginFailedError must also see MFARequired."""
    assert issubclass(MFARequired, LoginFailedError)


# ---------------------------------------------------------------------
# Recoverable flag
# ---------------------------------------------------------------------

def test_authError_recoverable_default_false():
    assert AuthError.recoverable is False


def test_credential_missing_not_recoverable():
    exc = CredentialMissing(
        "creds missing", vendor="ubs", env_var_prefix="IMDR_RESEARCH_UBS",
    )
    assert exc.recoverable is False


def test_session_expired_recoverable_for_programmatic():
    exc = SessionExpired("expired", vendor="barclays", recoverable=True)
    assert exc.recoverable is True


def test_session_expired_not_recoverable_for_profile_only():
    exc = SessionExpired("expired", vendor="bnp", recoverable=False)
    assert exc.recoverable is False


# ---------------------------------------------------------------------
# Field shape
# ---------------------------------------------------------------------

def test_unknown_vendor_carries_vendor_code():
    exc = UnknownVendor("unknown vendor 'bofa'", vendor="bofa")
    assert exc.vendor == "bofa"
    assert "bofa" in str(exc)


def test_credential_missing_carries_env_prefix():
    exc = CredentialMissing(
        "UBS credentials missing — set IMDR_RESEARCH_UBS_USERNAME / _PASSWORD",
        vendor="ubs",
        env_var_prefix="IMDR_RESEARCH_UBS",
    )
    assert exc.vendor == "ubs"
    assert exc.env_var_prefix == "IMDR_RESEARCH_UBS"
    assert "IMDR_RESEARCH_UBS" in str(exc)


def test_login_failed_carries_title_url_hint():
    exc = LoginFailedError(
        vendor="barclays",
        title="Login - Barclays Live",
        url="https://live.barcap.com/ct_logon_basic.do",
        hint="check IMDR_BARCLAYS_PASSWORD",
    )
    assert exc.vendor == "barclays"
    assert exc.title == "Login - Barclays Live"
    assert exc.url == "https://live.barcap.com/ct_logon_basic.do"
    assert exc.hint == "check IMDR_BARCLAYS_PASSWORD"
    msg = str(exc)
    assert "barclays" in msg
    assert "Login - Barclays Live" in msg
    assert "check IMDR_BARCLAYS_PASSWORD" in msg


def test_login_failed_renders_cleanly_without_hint():
    exc = LoginFailedError(vendor="ubs", title="", url="")
    # Empty fields shouldn't crash str() and shouldn't dangle "(...)" suffix.
    msg = str(exc)
    assert "ubs" in msg
    # No trailing parenthesised hint when hint is empty.
    assert "(" not in msg.rstrip()


def test_mfa_required_carries_kind():
    exc = MFARequired(
        vendor="goldman",
        title="Verify your identity",
        url="https://marquee.gs.com/mfa",
        mfa_kind="mobile push",
    )
    assert exc.mfa_kind == "mobile push"
    assert exc.vendor == "goldman"
    assert "mobile push" in str(exc)


def test_mfa_required_default_kind_unknown():
    exc = MFARequired(vendor="goldman", title="", url="")
    assert exc.mfa_kind == "unknown"


def test_pdf_validation_error_carries_reason_and_size():
    exc = PDFValidationError(
        "too small (200 bytes)", vendor="anz", n_bytes=200, reason="too_small",
    )
    assert exc.vendor == "anz"
    assert exc.n_bytes == 200
    assert exc.reason == "too_small"


# ---------------------------------------------------------------------
# repr() includes vendor — useful for logs
# ---------------------------------------------------------------------

def test_repr_includes_vendor():
    exc = CredentialMissing(
        "creds missing", vendor="ubs", env_var_prefix="IMDR_RESEARCH_UBS",
    )
    r = repr(exc)
    assert "CredentialMissing" in r
    assert "ubs" in r


def test_raises_and_catches_correctly():
    """Sanity — using these in real try/except blocks behaves as expected."""
    with pytest.raises(AuthError):
        raise CredentialMissing(
            "x", vendor="ubs", env_var_prefix="IMDR_RESEARCH_UBS",
        )

    with pytest.raises(LoginFailedError):
        raise MFARequired(vendor="goldman", title="", url="")
