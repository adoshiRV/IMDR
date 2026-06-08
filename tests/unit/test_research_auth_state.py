"""storage_state snapshot + restore — round-trip on a fake context."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import patch

from imdr.research.auth import state as state_mod


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class _FakeCtx:
    """Minimal stand-in for Playwright's BrowserContext."""

    def __init__(self, *, payload: dict | None = None,
                 raise_on_snapshot: Exception | None = None,
                 raise_on_add_cookies: Exception | None = None):
        self._payload = payload or {"cookies": [], "origins": []}
        self._raise_on_snapshot = raise_on_snapshot
        self._raise_on_add_cookies = raise_on_add_cookies
        self.added_cookies: list = []

    async def storage_state(self, *, path: str):
        if self._raise_on_snapshot is not None:
            raise self._raise_on_snapshot
        Path(path).write_text(json.dumps(self._payload), encoding="utf-8")

    async def add_cookies(self, cookies):
        if self._raise_on_add_cookies is not None:
            raise self._raise_on_add_cookies
        self.added_cookies.extend(cookies)


def _stub_snapshot_path(tmp_path: Path):
    out = tmp_path / "snap.json"
    return patch("imdr.research.auth.state.snapshot_path", return_value=out), out


def test_snapshot_writes_json(tmp_path: Path):
    ctx = _FakeCtx(payload={"cookies": [{"name": "sid", "value": "abc"}], "origins": []})
    stub, out_path = _stub_snapshot_path(tmp_path)
    with stub:
        result = _run(state_mod.snapshot(ctx, "vendor_x"))
    assert result == out_path
    assert out_path.exists()
    written = json.loads(out_path.read_text(encoding="utf-8"))
    assert written["cookies"][0]["name"] == "sid"


def test_snapshot_swallows_errors(tmp_path: Path):
    ctx = _FakeCtx(raise_on_snapshot=RuntimeError("ctx closed"))
    stub, out_path = _stub_snapshot_path(tmp_path)
    with stub:
        # Must not raise — snapshot is best-effort.
        result = _run(state_mod.snapshot(ctx, "vendor_x"))
    assert result == out_path  # path returned even though write failed


def test_restore_into_returns_false_when_no_snapshot(tmp_path: Path):
    ctx = _FakeCtx()
    stub, _ = _stub_snapshot_path(tmp_path)
    with stub:
        ok = _run(state_mod.restore_into(ctx, "vendor_x"))
    assert ok is False


def test_restore_into_replays_cookies(tmp_path: Path):
    cookies = [{"name": "sid", "value": "abc", "domain": ".x.com", "path": "/"}]
    ctx = _FakeCtx()
    stub, out_path = _stub_snapshot_path(tmp_path)
    out_path.write_text(
        json.dumps({"cookies": cookies, "origins": []}),
        encoding="utf-8",
    )
    with stub:
        ok = _run(state_mod.restore_into(ctx, "vendor_x"))
    assert ok is True
    assert ctx.added_cookies == cookies


def test_restore_into_handles_add_cookies_error(tmp_path: Path):
    cookies = [{"name": "sid", "value": "abc"}]
    ctx = _FakeCtx(raise_on_add_cookies=RuntimeError("ctx closed"))
    stub, out_path = _stub_snapshot_path(tmp_path)
    out_path.write_text(
        json.dumps({"cookies": cookies, "origins": []}),
        encoding="utf-8",
    )
    with stub:
        ok = _run(state_mod.restore_into(ctx, "vendor_x"))
    assert ok is False


def test_restore_into_empty_cookies_returns_false(tmp_path: Path):
    ctx = _FakeCtx()
    stub, out_path = _stub_snapshot_path(tmp_path)
    out_path.write_text(
        json.dumps({"cookies": [], "origins": []}),
        encoding="utf-8",
    )
    with stub:
        ok = _run(state_mod.restore_into(ctx, "vendor_x"))
    assert ok is False


def test_restore_into_handles_corrupt_json(tmp_path: Path):
    ctx = _FakeCtx()
    stub, out_path = _stub_snapshot_path(tmp_path)
    out_path.write_text("{not json", encoding="utf-8")
    with stub:
        ok = _run(state_mod.restore_into(ctx, "vendor_x"))
    assert ok is False
