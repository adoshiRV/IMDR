"""Acquirers — concrete implementations of the ``Acquirer`` Protocol.

One module per transport.  Adding a new transport means adding a module
here and a spec under ``imdr.vendors.specs`` — no framework surgery.
"""
from __future__ import annotations

from imdr.vendors.acquirers.email_linked import (
    EmailLinkedDownloadAcquirer,
    EmailLinkedDownloadSpec,
)

__all__ = [
    "EmailLinkedDownloadAcquirer",
    "EmailLinkedDownloadSpec",
]
