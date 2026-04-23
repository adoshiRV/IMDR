"""WebScrapeAcquirer — SCAFFOLD.

Intended for vendors with no email trigger: login page → navigate →
download.  Will share ``BrowserSession`` with EmailLinkedDownloadAcquirer
(same persistent-profile SSO model, just without the Outlook pre-step).

Not implemented yet.  See ``docs/admin/vendors/web_scraping.md`` for the
design sketch.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WebScrapeSpec:
    """Placeholder — fields will be finalised when the first web-scrape feed lands."""

    name: str
    vendor_code: str
    login_url: str
    target_url: str
    output_dir: Path
    profile_name: str


class WebScrapeAcquirer:
    """Placeholder class so the public API shape is visible to readers.

    Raises ``NotImplementedError`` on ``fetch()``.  When the first web-scrape
    vendor arrives, implement ``fetch()`` using ``BrowserSession`` from
    ``imdr.vendors.sessions`` and register a concrete feed.
    """

    def __init__(self, spec: WebScrapeSpec) -> None:
        self.spec = spec
        self.name = spec.name

    def fetch(self, *, headless: bool = True, report=None):  # type: ignore[no-untyped-def]
        raise NotImplementedError(
            "WebScrapeAcquirer is scaffolded but not implemented. "
            "See docs/admin/vendors/web_scraping.md."
        )
