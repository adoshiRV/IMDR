"""verify(vendor) — status mapping under mocked Playwright."""
from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest

from imdr.research.auth import verify
from imdr.research.auth.verify import SessionStatus


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def _stub_profile_seeded(value: bool):
    return patch(
        "imdr.research.auth.verify._profile_is_seeded",
        return_value=value,
    )


def _stub_probe(*, live: bool = True, title: str = "", url: str = ""):
    async def fake(_spec):
        return live, title, url
    return patch("imdr.research.auth.verify._probe", side_effect=fake)


def _stub_probe_raises(exc: Exception):
    async def fake(_spec):
        raise exc
    return patch("imdr.research.auth.verify._probe", side_effect=fake)


def test_no_profile_returns_no_profile():
    with _stub_profile_seeded(False):
        r = _run(verify("anz"))
    assert r.status == SessionStatus.NO_PROFILE
    assert "login" in r.detail.lower() or "first" in r.detail.lower()


def test_live_predicate_maps_to_live():
    with _stub_profile_seeded(True), _stub_probe(
        live=True, title="ANZ Research",
        url="https://research.anz.com/all_research",
    ):
        r = _run(verify("anz"))
    assert r.status == SessionStatus.LIVE
    assert r.url.endswith("/all_research")


def test_failed_predicate_maps_to_expired():
    with _stub_profile_seeded(True), _stub_probe(
        live=False, title="Login",
        url="https://login.anz.com/sso",
    ):
        r = _run(verify("anz"))
    assert r.status == SessionStatus.EXPIRED


def test_probe_exception_maps_to_unreachable():
    with _stub_profile_seeded(True), _stub_probe_raises(
        RuntimeError("network down"),
    ):
        r = _run(verify("anz"))
    assert r.status == SessionStatus.UNREACHABLE
    assert "RuntimeError" in r.detail
    assert "network down" in r.detail


def test_unknown_vendor_raises_keyerror():
    with pytest.raises(KeyError, match="unknown research vendor"):
        _run(verify("does_not_exist"))
