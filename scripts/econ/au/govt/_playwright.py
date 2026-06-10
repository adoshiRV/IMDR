"""Shared Playwright helper for RBA fetchers (all Akamai-gated).

All four RBA streams (Governor's Statement, Board Minutes, SMP, FSR) share
the same Akamai-bypass recipe: fresh persistent profile per run, headed
Chrome channel, ``domcontentloaded`` then wait for a stream-specific anchor
selector so we don't capture a JS-challenge page as a legitimate
zero-items result.

`fetch_rba_html()` is the single entry point. Each fetcher passes its
target URL, a profile directory, and an anchor selector that must be
present in the real listing HTML.
"""
from __future__ import annotations

import re
import shutil
from datetime import date
from pathlib import Path


def fetch_rba_html(
    url: str,
    profile: Path,
    *,
    anchor_selector: str,
    selector_timeout_ms: int = 15_000,
    goto_timeout_ms: int = 60_000,
) -> str:
    """Launch headed Chrome with a fresh persistent profile, navigate to
    ``url``, wait until ``anchor_selector`` is present in the DOM, return
    the rendered HTML.

    Raises ``RuntimeError`` if the selector never appears — that
    distinguishes a real empty listing from an Akamai JS-challenge page.
    """
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError

    if profile.exists():
        shutil.rmtree(profile, ignore_errors=True)
    profile.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            user_data_dir=str(profile),
            channel="chrome",
            headless=False,
            ignore_https_errors=True,
            viewport={"width": 1400, "height": 900},
            locale="en-AU",
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=goto_timeout_ms)
            try:
                page.wait_for_selector(anchor_selector, timeout=selector_timeout_ms)
            except PWTimeoutError as exc:
                raise RuntimeError(
                    f"anchor selector {anchor_selector!r} not found within "
                    f"{selector_timeout_ms}ms — likely Akamai JS challenge page"
                ) from exc
            return page.content()
        finally:
            ctx.close()


# ---------------------------------------------------------------------------
# Shared date-parsing helpers (used by Governor's Statement / Board Minutes)
# ---------------------------------------------------------------------------

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def extract_date(text: str) -> date | None:
    """Parse a `"D Mon YYYY"` / `"DD Month YYYY"` date out of free-form text."""
    if not text:
        return None
    m = re.search(r"\b(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})\b", text)
    if not m:
        return None
    day = int(m.group(1))
    mon = _MONTHS.get(m.group(2)[:3].lower())
    year = int(m.group(3))
    if mon is None:
        return None
    try:
        return date(year, mon, day)
    except ValueError:
        return None
