"""Vendor feed registry.

Mirrors the ``PIPELINE_REGISTRY`` pattern in ``scripts/run_pipeline.py``
— a plain dict keyed by feed name, populated at import time by each
module under ``imdr.vendors.specs``.  Imports of ``imdr.vendors`` walk
the specs package so the runner sees every feed without manual wiring.
"""
from __future__ import annotations

from imdr.vendors.base import VendorFeed
from imdr.vendors.exceptions import AcquirerMisconfigured

VENDOR_FEEDS: dict[str, VendorFeed] = {}


def register_feed(feed: VendorFeed) -> None:
    """Add a feed to the registry.  Duplicate names are a configuration bug."""
    if feed.name in VENDOR_FEEDS:
        raise AcquirerMisconfigured(
            f"Feed already registered: {feed.name!r} "
            f"(from {VENDOR_FEEDS[feed.name].__class__.__name__})"
        )
    VENDOR_FEEDS[feed.name] = feed


def get_feed(name: str) -> VendorFeed:
    """Look up a registered feed by name."""
    try:
        return VENDOR_FEEDS[name]
    except KeyError as exc:
        known = ", ".join(sorted(VENDOR_FEEDS)) or "(none)"
        raise AcquirerMisconfigured(
            f"Unknown vendor feed: {name!r}. Registered: {known}"
        ) from exc


def list_feeds() -> list[str]:
    """All registered feed names, sorted."""
    return sorted(VENDOR_FEEDS)
