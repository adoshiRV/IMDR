"""refresh(vendor) — auto-relog dispatch under mocked verify + context."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from unittest.mock import patch

from imdr.research.auth import refresh
from imdr.research.auth.verify import SessionStatus, VerifyResult


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def _stub_verify_sequence(*results: VerifyResult):
    """Patch verify() so each call returns the next result in sequence."""
    iterator = iter(results)

    async def fake(vendor: str):
        try:
            return next(iterator)
        except StopIteration:
            # Repeat the last result if exhausted; refresh() calls it 1-2x.
            return results[-1]

    return patch("imdr.research.auth.refresh.verify", side_effect=fake)


def _stub_context_noop():
    """Make get_authed_context a no-op so refresh()'s login attempt
    succeeds without touching Playwright."""
    @asynccontextmanager
    async def fake(_vendor: str, **_kw):
        yield object()

    return patch("imdr.research.auth.refresh.get_authed_context", new=fake)


def _stub_context_raises(exc: Exception):
    @asynccontextmanager
    async def fake(_vendor: str, **_kw):
        raise exc
        yield  # pragma: no cover

    return patch("imdr.research.auth.refresh.get_authed_context", new=fake)


def test_live_session_no_action():
    live = VerifyResult(vendor="anz", status=SessionStatus.LIVE,
                        url="https://research.anz.com/all_research")
    with _stub_verify_sequence(live):
        out = _run(refresh("anz"))
    assert out.before == SessionStatus.LIVE
    assert out.after == SessionStatus.LIVE
    assert out.needs_human is False
    assert out.recovered is False


def test_expired_profile_only_needs_human():
    # Use BNP — still PROFILE_ONLY after the 2026-06-08 ANZ/Nomura/STANC
    # upgrade. (ANZ moved to PROGRAMMATIC; refresh on EXPIRED + PROGRAMMATIC
    # takes a different branch.)
    expired = VerifyResult(vendor="bnp", status=SessionStatus.EXPIRED)
    with _stub_verify_sequence(expired):
        out = _run(refresh("bnp"))
    assert out.before == SessionStatus.EXPIRED
    assert out.after == SessionStatus.EXPIRED
    assert out.needs_human is True
    assert out.healthcheck_url == "https://markets360.bnpparibas.com/"
    assert "login" in out.detail.lower()


def test_expired_programmatic_auto_recovers():
    expired = VerifyResult(vendor="barclays", status=SessionStatus.EXPIRED)
    live = VerifyResult(vendor="barclays", status=SessionStatus.LIVE,
                        url="https://live.barcap.com/BU/")
    # First verify → EXPIRED, then context_open succeeds (no-op),
    # then post-recovery verify → LIVE.
    with _stub_verify_sequence(expired, live), _stub_context_noop():
        out = _run(refresh("barclays"))
    assert out.before == SessionStatus.EXPIRED
    assert out.after == SessionStatus.LIVE
    assert out.recovered is True
    assert out.needs_human is False


def test_expired_programmatic_login_fails():
    expired = VerifyResult(vendor="barclays", status=SessionStatus.EXPIRED)
    with _stub_verify_sequence(expired), _stub_context_raises(
        RuntimeError("bad creds"),
    ):
        out = _run(refresh("barclays"))
    assert out.before == SessionStatus.EXPIRED
    assert out.after == SessionStatus.EXPIRED
    assert out.needs_human is True
    assert "bad creds" in out.detail


def test_expired_header_injection_needs_human():
    """JPM (HEADER_INJECTION) cannot self-recover — cookies require SSO."""
    expired = VerifyResult(vendor="jpm", status=SessionStatus.EXPIRED)
    with _stub_verify_sequence(expired):
        out = _run(refresh("jpm"))
    assert out.after == SessionStatus.EXPIRED
    assert out.needs_human is True
