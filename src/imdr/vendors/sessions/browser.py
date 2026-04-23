"""Browser session — persistent Chrome profile for SSO-gated portals.

Wraps Playwright's ``launch_persistent_context`` so every email-linked
download (and future web-scrape acquirers) share one implementation of
the SSO / stale-lock / iframe / safe-filename plumbing.

Moved out of ``scripts/rates/barclays/rates_skew_download.py`` with no
behavioural changes.  Playwright import is deferred into
``__enter__`` so module import works in environments without it.
"""
from __future__ import annotations

import re
import time
from datetime import datetime
from pathlib import Path
from types import TracebackType
from typing import Literal

import structlog

log = structlog.get_logger(__name__)

# Chrome leaves these behind if killed ungracefully and refuses to reopen the
# profile until they're removed.
_CHROME_SINGLETON_LOCKS = (
    "SingletonLock",
    "SingletonCookie",
    "SingletonSocket",
    "lockfile",
)

# Invalid Windows filename chars plus whitespace collapsed to underscore.
_FILENAME_BAD_CHARS = re.compile(r'[<>:"|?*\\/\s]+')


FilenameRule = Literal["anchor", "server"]


def _safe_filename(name: str, fallback: str = "download") -> str:
    cleaned = _FILENAME_BAD_CHARS.sub("_", name.strip()).strip("_")
    return cleaned or fallback


def _clean_stale_chrome_locks(profile_dir: Path) -> None:
    for name in _CHROME_SINGLETON_LOCKS:
        lock = profile_dir / name
        if not lock.exists():
            continue
        try:
            lock.unlink()
            log.info("removed_stale_chrome_lock", path=str(lock))
        except OSError as exc:
            log.warning("chrome_lock_unlink_failed", path=str(lock), error=str(exc))


class BrowserSession:
    """Persistent-profile Chrome session as a context manager.

    On ``__enter__`` it cleans stale singleton locks and launches a
    persistent context.  Downloads reuse the same cookie jar as the
    browsing session (``ctx.request.get``).

    Usage::

        with BrowserSession(profile_dir, headless=True) as session:
            files, nbytes = session.download_anchors(
                listing_url=..., selector=..., output_dir=..., ...
            )
    """

    def __init__(self, profile_dir: Path, *, headless: bool) -> None:
        self._profile_dir = profile_dir
        self._headless = headless
        self._pw = None  # playwright manager
        self._ctx = None  # browser context

    def __enter__(self) -> "BrowserSession":
        from playwright.sync_api import sync_playwright

        self._profile_dir.mkdir(parents=True, exist_ok=True)
        _clean_stale_chrome_locks(self._profile_dir)

        self._pw = sync_playwright().start()
        self._ctx = self._pw.chromium.launch_persistent_context(
            user_data_dir=str(self._profile_dir),
            channel="chrome",
            headless=self._headless,
            accept_downloads=True,
        )
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        try:
            if self._ctx is not None:
                self._ctx.close()
        finally:
            if self._pw is not None:
                self._pw.stop()

    def download_anchors(
        self,
        *,
        listing_url: str,
        selector: str,
        output_dir: Path,
        filename_rule: FilenameRule = "anchor",
        sso_timeout_s: float = 300.0,
    ) -> tuple[list[Path], int]:
        """Open ``listing_url``, find anchors matching ``selector`` (searching all
        frames — listings often live in same-origin iframes), and save each file
        via the session's authenticated request context.

        Returns ``(saved_paths, total_bytes)``.  Raises ``SSOTimeout`` if the
        listing anchors never appear within ``sso_timeout_s``.  Raises
        ``DownloadFailed`` if every anchor download fails; partial-failure
        collects a warning per bad URL and continues.
        """
        # Imported here to keep the top-level module import lightweight.
        from imdr.vendors.exceptions import DownloadFailed, ListingNotFound, SSOTimeout

        if self._ctx is None:
            raise RuntimeError("BrowserSession used outside its context manager")

        output_dir.mkdir(parents=True, exist_ok=True)
        page = self._ctx.new_page()
        log.info("browser_goto", url=listing_url)
        page.goto(listing_url, wait_until="domcontentloaded")

        frame = self._wait_for_listing_frame(page, selector, sso_timeout_s)
        if frame is None:
            # We can't distinguish "SSO never completed" from "portal returned
            # an empty page" reliably — both surface as missing anchors.  Use
            # the timeout hint to pick the more common case.
            if sso_timeout_s >= 60:
                raise SSOTimeout(
                    f"No anchors matching {selector!r} after {int(sso_timeout_s)}s at {page.url!r}"
                )
            raise ListingNotFound(
                f"No anchors matching {selector!r} at {page.url!r}"
            )

        anchors: list[tuple[str, str]] = []
        seen: set[str] = set()
        for anchor in frame.locator(selector).all():
            href = anchor.get_attribute("href") or ""
            if not href or href in seen:
                continue
            seen.add(href)
            text = (anchor.text_content() or "").strip() or "download"
            anchors.append((href, text))

        if not anchors:
            raise ListingNotFound("Listing frame had no unique anchors")

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        saved: list[Path] = []
        total_bytes = 0
        errors: list[str] = []

        for href, label in anchors:
            response = self._ctx.request.get(href)
            if not response.ok:
                errors.append(f"{label}: HTTP {response.status}")
                log.error("download_http_error", label=label, status=response.status)
                continue

            body = response.body()
            if filename_rule == "anchor":
                target = output_dir / f"{_safe_filename(label)}_{stamp}.xlsx"
            else:
                # Fall back to server-supplied filename when available.
                header = response.headers.get("content-disposition", "")
                server_name = _parse_content_disposition_filename(header) or f"download_{stamp}.bin"
                target = output_dir / _safe_filename(server_name)

            target.write_bytes(body)
            total_bytes += len(body)
            saved.append(target)
            log.info("downloaded", label=label, path=str(target), bytes=len(body))

        if not saved:
            raise DownloadFailed(f"All {len(anchors)} downloads failed: {errors}")

        return saved, total_bytes

    def _wait_for_listing_frame(self, page, selector: str, timeout_s: float):
        """Poll every frame until one contains the target anchors, or timeout."""
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            for frame in page.frames:
                try:
                    if frame.locator(selector).count() > 0:
                        return frame
                except Exception:  # noqa: BLE001 — frame may still be loading
                    continue
            time.sleep(2)
        return None


def _parse_content_disposition_filename(header: str) -> str | None:
    """Extract ``filename="..."`` from a Content-Disposition header."""
    if not header:
        return None
    match = re.search(r'filename\s*=\s*"?([^"\s;]+)"?', header)
    return match.group(1) if match else None
