"""Headed-Chrome download primitives for `rbidocs.rbi.org.in` (Akamai TSPD).

Every RBI document host -- the Bulletin XLSX tables, the monthly
Sectoral-Deployment press-release statements -- sits behind Akamai TSPD
bot protection. Plain httpx and headless Playwright both get the
challenge page (an HTML body served with an `.xlsx` extension); HEADED
Chrome with live JS clears it naturally and the file arrives as an
ordinary browser download. Verified 2026-06-11 (Bulletin) and re-verified
2026-09-15 (Sectoral Deployment).

The *index* pages on `rbi.org.in` are NOT walled -- only the documents on
`rbidocs.rbi.org.in`. Discover URLs over plain httpx and spend the
browser only on the downloads.

**The profile must be FRESH, and it must be this fetcher's own.**
`launch_persistent_context` takes an exclusive lock on `user_data_dir`,
so two fetchers sharing one dir kill each other -- observed 2026-09-15
against a live research-profile Chrome session. Worse, a profile that
has been used before (or left behind by a killed run) makes Chrome tear
the browser down on the FIRST download with `TargetClosedError`, after
which every later download in the batch times out waiting for an event
from a dead browser; a brand-new dir downloads the same URL fine. So
`download_all` recreates its working profile on every run. Nothing is
lost by that: TSPD is cleared by live JS execution in the session, not
by anything persisted, which is exactly why a first-run profile works.
"""
from __future__ import annotations

import shutil
import time
from pathlib import Path

_XLSX_MAGIC = b"PK\x03\x04"


def fresh_profile(profile_dir: Path) -> Path:
    """Delete and recreate `profile_dir`. See the module docstring."""
    shutil.rmtree(profile_dir, ignore_errors=True)
    profile_dir.mkdir(parents=True, exist_ok=True)
    return profile_dir


def launch_download_context(pw, profile_dir: Path, *, headless: bool = False):
    """Headed persistent Chrome with downloads accepted.

    `headless=True` is offered only so a probe can demonstrate that TSPD
    blocks it; production callers must leave it False.
    """
    profile_dir.mkdir(parents=True, exist_ok=True)
    return pw.chromium.launch_persistent_context(
        user_data_dir=str(profile_dir),
        channel="chrome",
        headless=headless,
        accept_downloads=True,
        viewport={"width": 1280, "height": 900},
    )


def download_xlsx(page, url: str, dest: Path, *, timeout_ms: int = 60000) -> Path | None:
    """Download `url` to `dest`; return it only if the bytes are a real XLSX.

    A TSPD challenge arrives as an HTML body under the `.xlsx` name, so
    the magic-number check is the only thing that separates a download
    from a block. A blocked file is deleted rather than left on disk for
    a parser to choke on later.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        with page.expect_download(timeout=timeout_ms) as info:
            try:
                page.goto(url, timeout=30000)
            except Exception:
                # Navigating to a download target always raises; the
                # download event is the real signal.
                pass
        info.value.save_as(str(dest))
    except Exception as e:
        print(f"    FAIL: {type(e).__name__}: {str(e)[:110]}")
        return None

    head = dest.read_bytes()[:4]
    if head.startswith(_XLSX_MAGIC):
        print(f"    OK  {dest.stat().st_size:,}B")
        return dest
    if head.startswith(b"<!DO") or head.startswith(b"<htm"):
        print("    BLOCKED: TSPD challenge")
    else:
        print(f"    UNKNOWN format head={head!r}")
    dest.unlink(missing_ok=True)
    return None


def download_all(
    pw,
    profile_dir: Path,
    items: list[tuple[str, str]],
    dest_dir: Path,
    *,
    pause_s: float = 2.0,
) -> dict[str, Path]:
    """`[(label, url)]` -> `{label: path}`, one headed session for the lot.

    Labels already present in `dest_dir` as a valid XLSX are skipped, so a
    re-run after a partial failure costs only the missing files.
    """
    out: dict[str, Path] = {}
    dest_dir.mkdir(parents=True, exist_ok=True)
    pending = []
    for label, url in items:
        cached = dest_dir / f"{label}.xlsx"
        if cached.exists() and cached.read_bytes()[:4].startswith(_XLSX_MAGIC):
            out[label] = cached
        else:
            pending.append((label, url))
    if out:
        print(f"  {len(out)} already cached")
    if not pending:
        return out

    print(f"  launching headed Chrome for {len(pending)} download(s)")
    ctx = launch_download_context(pw, fresh_profile(profile_dir))
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    try:
        for i, (label, url) in enumerate(pending, 1):
            print(f"  [{i}/{len(pending)}] {label}")
            got = download_xlsx(page, url, dest_dir / f"{label}.xlsx")
            if got is None and is_context_dead(ctx):
                # A dead browser fails every remaining item on a 60s
                # timeout each, which turns one fault into a half-hour
                # stall. Relaunch once and retry this item.
                print("    browser died — relaunching")
                try:
                    ctx.close()
                except Exception:
                    pass
                ctx = launch_download_context(pw, fresh_profile(profile_dir))
                page = ctx.pages[0] if ctx.pages else ctx.new_page()
                got = download_xlsx(page, url, dest_dir / f"{label}.xlsx")
            if got:
                out[label] = got
            time.sleep(pause_s)
    finally:
        try:
            ctx.close()
        except Exception:
            pass
    return out


def is_context_dead(ctx) -> bool:
    """True once Chrome has torn itself down mid-batch.

    Public because a caller that does its own in-browser discovery (the
    Bulletin fetcher) runs its own download loop and needs the same
    relaunch trigger.
    """
    try:
        return len(ctx.pages) == 0
    except Exception:
        return True
