"""imdr.vendors — external data acquisition framework.

Architecture:

    scripts/run_vendor_feed.py  ──┐
                                   │   ┌──────── specs/ (one per feed; registers
                                   ▼   │           via register_feed() at import)
                              runner.run_vendor_feed_daily(name)
                                   │   │
                                   │   └─► registry.get_feed(name) -> VendorFeed
                                   │
                                   ▼
                           VendorFeed.acquirer.fetch() ─► FetchResult
                                   │
                                   ▼
                           VendorFeed.pipeline_builder(files) ─► BasePipeline.run()

Importing ``imdr.vendors`` auto-populates the registry (see specs/__init__).

Public API::

    from imdr.vendors import FetchResult, VendorFeed, run_vendor_feed_daily
    from imdr.vendors.registry import get_feed, list_feeds, VENDOR_FEEDS
    from imdr.vendors.exceptions import VendorError, NoEmailFound, SSOTimeout
"""
from __future__ import annotations

from imdr.vendors.base import Acquirer, FetchResult, PipelineBuilder, VendorFeed
from imdr.vendors.exceptions import (
    AcquirerMisconfigured,
    DownloadFailed,
    LinkExtractionFailed,
    ListingNotFound,
    NoEmailFound,
    SSOTimeout,
    VendorError,
)
from imdr.vendors.registry import VENDOR_FEEDS, get_feed, list_feeds, register_feed
from imdr.vendors.runner import run_vendor_feed_daily

# Side-effect: importing the specs package runs each feed's register_feed(...).
from imdr.vendors import specs  # noqa: E402, F401

__all__ = [
    "Acquirer",
    "AcquirerMisconfigured",
    "DownloadFailed",
    "FetchResult",
    "LinkExtractionFailed",
    "ListingNotFound",
    "NoEmailFound",
    "PipelineBuilder",
    "SSOTimeout",
    "VENDOR_FEEDS",
    "VendorError",
    "VendorFeed",
    "get_feed",
    "list_feeds",
    "register_feed",
    "run_vendor_feed_daily",
]
