"""Session abstractions — Outlook scanner, Playwright browser.

Each session is a thin Protocol + one production implementation.  Tests
substitute fake implementations by type.
"""
from __future__ import annotations

from imdr.vendors.sessions.browser import BrowserSession
from imdr.vendors.sessions.outlook import EmailRef, OutlookClient, Win32OutlookClient

__all__ = [
    "BrowserSession",
    "EmailRef",
    "OutlookClient",
    "Win32OutlookClient",
]
