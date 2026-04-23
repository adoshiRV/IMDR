"""Exception hierarchy for the vendors framework.

All acquirer failures raise a subclass of ``VendorError`` so the runner
can translate them into a single failure-email path regardless of the
underlying transport (Outlook, browser, SFTP, HTTP, ...).
"""
from __future__ import annotations


class VendorError(Exception):
    """Base class for all vendor-acquisition failures."""


class AcquirerMisconfigured(VendorError):
    """Registry or spec wiring is wrong (duplicate name, missing feed, ...)."""


class NoEmailFound(VendorError):
    """Outlook scan found no matching emails in the requested window."""


class LinkExtractionFailed(VendorError):
    """An email matched the sender/subject filter but contained no usable link."""


class SSOTimeout(VendorError):
    """Browser waited past ``sso_timeout_s`` without reaching the authenticated page."""


class ListingNotFound(VendorError):
    """Authenticated page loaded but the expected listing anchors never appeared."""


class DownloadFailed(VendorError):
    """One or more file downloads returned a non-OK HTTP status."""
