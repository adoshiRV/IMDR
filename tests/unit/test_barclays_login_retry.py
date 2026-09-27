"""Retry behaviour of imdr.research.auth.loginflows.barclays.login.

The Barclays login is flaky at the OneTrust cookie step (the banner paints
late and the submit gets intercepted). login() absorbs that by running up to
``_MAX_LOGIN_ATTEMPTS`` independent attempts and only raising if all fail.
These tests pin that contract by monkeypatching the two async collaborators
(is_authenticated + _attempt_login) — no browser required.
"""
from __future__ import annotations

import asyncio

import pytest

from imdr.research.auth.loginflows import barclays
from imdr.research.auth.loginflows._base import LoginFailedError


def _run(coro):
    return asyncio.run(coro)


def test_short_circuits_when_already_authenticated(monkeypatch):
    calls = {"attempt": 0}

    async def fake_is_auth(ctx):
        return True

    async def fake_attempt(ctx, *, username, password):
        calls["attempt"] += 1
        return True, "Home", "https://live.barcap.com/BU/"

    monkeypatch.setattr(barclays, "is_authenticated", fake_is_auth)
    monkeypatch.setattr(barclays, "_attempt_login", fake_attempt)

    _run(barclays.login(object(), username="u", password="p"))
    assert calls["attempt"] == 0, "should not attempt a fresh login when already authed"


def test_succeeds_on_first_attempt(monkeypatch):
    calls = {"attempt": 0}

    async def fake_is_auth(ctx):
        return False

    async def fake_attempt(ctx, *, username, password):
        calls["attempt"] += 1
        return True, "Home", "https://live.barcap.com/BU/"

    monkeypatch.setattr(barclays, "is_authenticated", fake_is_auth)
    monkeypatch.setattr(barclays, "_attempt_login", fake_attempt)

    _run(barclays.login(object(), username="u", password="p"))
    assert calls["attempt"] == 1


def test_retries_then_succeeds(monkeypatch):
    """First attempt stuck on login page, second reaches /BU/ — no raise."""
    calls = {"attempt": 0}

    async def fake_is_auth(ctx):
        return False

    async def fake_attempt(ctx, *, username, password):
        calls["attempt"] += 1
        if calls["attempt"] == 1:
            return False, "Barclays Live - Login", "https://live.barcap.com/UAB/ct_logon_basic"
        return True, "Home", "https://live.barcap.com/BU/"

    monkeypatch.setattr(barclays, "is_authenticated", fake_is_auth)
    monkeypatch.setattr(barclays, "_attempt_login", fake_attempt)

    _run(barclays.login(object(), username="u", password="p"))
    assert calls["attempt"] == 2, "should retry once and stop after success"


def test_raises_after_all_attempts_fail(monkeypatch):
    calls = {"attempt": 0}

    async def fake_is_auth(ctx):
        return False

    async def fake_attempt(ctx, *, username, password):
        calls["attempt"] += 1
        return False, "Barclays Live - Login", "https://live.barcap.com/UAB/ct_logon_basic"

    monkeypatch.setattr(barclays, "is_authenticated", fake_is_auth)
    monkeypatch.setattr(barclays, "_attempt_login", fake_attempt)

    with pytest.raises(LoginFailedError):
        _run(barclays.login(object(), username="u", password="p"))
    assert calls["attempt"] == barclays._MAX_LOGIN_ATTEMPTS, (
        "should exhaust exactly _MAX_LOGIN_ATTEMPTS before raising"
    )
