"""Playwright ``storage_state`` snapshot helpers.

A persistent ``user_data_dir`` is the *primary* session store — cookies,
IndexedDB, the full Chrome profile. ``storage_state`` is a *secondary*
JSON export of cookies + per-origin localStorage/sessionStorage that we
write on every context exit. Two reasons:

1. **Portability.** A profile dir is local Chrome state, not movable
   between machines or even diff-able. The JSON is.
2. **Crash insurance.** If a profile dir gets corrupted (Chrome crash
   mid-write, antivirus quarantine, disk-full mid-IndexedDB-commit),
   the snapshot is a recoverable copy of the cookies + localStorage
   captured at the end of the last healthy run.

Restore is not used in the persistent-context path (the user_data_dir
already carries state); :func:`restore_into` exists for the future
case where we boot a fresh non-persistent context from a snapshot
(e.g. a separate verification context that doesn't lock the profile).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ._paths import snapshot_path


async def snapshot(ctx: Any, vendor: str) -> Path:
    """Write ``ctx``'s cookies + origins to ``storage_state.json``.

    Returns the snapshot path. Best-effort — Playwright surfaces a
    ``TargetClosedError`` if the context was torn down by a navigation
    crash mid-finally; we catch and return the path anyway so the
    caller's cleanup is unaffected.
    """
    path = snapshot_path(vendor)
    try:
        await ctx.storage_state(path=str(path))
    except Exception as exc:
        # Surface to stderr but never raise — snapshot is a "nice to
        # have", not a correctness requirement. Crawlers that fail to
        # snapshot still have their live profile dir as primary state.
        import sys
        print(f"[auth.state] snapshot({vendor}) failed: {exc!s:.200}",
              file=sys.stderr)
    return path


async def restore_into(ctx: Any, vendor: str) -> bool:
    """Replay a snapshot's cookies into ``ctx``.

    Intentionally narrow: only cookies are re-added (the most common
    auth carrier). Origin-bound localStorage cannot be replayed via
    :meth:`BrowserContext.add_cookies`; that requires navigating to the
    origin then calling :func:`page.evaluate('localStorage.setItem(...)')`,
    which is fragile across SPA boots. Persistent contexts don't need
    this anyway — the profile dir carries it.

    Returns True if at least one cookie was restored.
    """
    import json

    path = snapshot_path(vendor)
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    cookies = data.get("cookies") or []
    if not cookies:
        return False
    try:
        await ctx.add_cookies(cookies)
    except Exception:
        return False
    return True
