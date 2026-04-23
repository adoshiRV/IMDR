"""Outlook session — scan the default Inbox for vendor emails.

``OutlookClient`` is a Protocol so tests can substitute a fake without
touching ``win32com``.  Production uses ``Win32OutlookClient``, which is
Windows-only; import of ``win32com`` is deferred into ``find_matching()``
so module import works on any platform.

Moved out of ``scripts/rates/barclays/rates_skew_download.py`` with no
behavioural changes — same Defender-safelinks unwrap, same sender/subject
filter, same newest-first sort.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol
from urllib.parse import parse_qs, unquote, urlparse

import structlog
from bs4 import BeautifulSoup

log = structlog.get_logger(__name__)

_OL_CLASS_MAIL = 43      # olMail
_OL_FOLDER_INBOX = 6     # olFolderInbox


@dataclass(frozen=True)
class EmailRef:
    """A vendor email that matched the sender + subject filter."""

    received: datetime
    subject: str
    link_url: str


class OutlookClient(Protocol):
    """Port for Outlook scanning.  Real impl uses win32com; tests use a fake."""

    def find_matching(
        self,
        *,
        sender: str,
        subject_contains: str,
        days_back: int,
        link_label: str,
    ) -> list[EmailRef]: ...


def _unwrap_safelinks(url: str) -> str:
    """Return the real URL hidden behind a Microsoft Defender safelinks wrapper."""
    parsed = urlparse(url)
    if "safelinks.protection.outlook.com" not in parsed.netloc:
        return url
    inner = parse_qs(parsed.query).get("url", [""])[0]
    return unquote(inner) if inner else url


def _extract_labelled_link(html_body: str, label: str) -> str | None:
    """Find the first <a> whose bold-labelled row matches ``label`` (e.g. 'View Excel')."""
    soup = BeautifulSoup(html_body, "html.parser")
    for tag in soup.find_all("b"):
        if tag.get_text(strip=True).rstrip(":").strip() != label:
            continue
        anchor = tag.parent.find("a", href=True) if tag.parent else None
        if anchor:
            return _unwrap_safelinks(anchor["href"])
    return None


class Win32OutlookClient:
    """Production Outlook client using win32com COM automation (Windows only)."""

    def find_matching(
        self,
        *,
        sender: str,
        subject_contains: str,
        days_back: int,
        link_label: str,
    ) -> list[EmailRef]:
        import win32com.client  # type: ignore[import-untyped]

        outlook = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
        inbox = outlook.GetDefaultFolder(_OL_FOLDER_INBOX)
        items = inbox.Items
        items.Sort("[ReceivedTime]", True)  # newest first

        cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
        sender_lc = sender.lower()
        subject_upper = subject_contains.upper()
        results: list[EmailRef] = []

        for item in items:
            if getattr(item, "Class", None) != _OL_CLASS_MAIL:
                continue
            received = getattr(item, "ReceivedTime", None)
            if received is None:
                continue
            received_utc = received.astimezone(timezone.utc)
            if received_utc < cutoff:
                break  # items are sorted newest-first; we're past the window

            subject = item.Subject or ""
            item_sender = (item.SenderEmailAddress or "").lower()
            if subject_upper not in subject.upper() or sender_lc not in item_sender:
                continue

            url = _extract_labelled_link(item.HTMLBody or "", label=link_label)
            if not url:
                log.warning(
                    "vendor_email_no_link",
                    subject=subject,
                    label=link_label,
                )
                continue

            results.append(EmailRef(received=received_utc, subject=subject, link_url=url))

        return results
