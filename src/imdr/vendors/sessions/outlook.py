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

import re
import time
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

    def find_code(
        self,
        *,
        sender: str,
        received_after: datetime,
        code_pattern: str,
        subject_contains: str = "",
        max_wait_s: int = 120,
        poll_s: int = 5,
    ) -> str | None: ...

    def latest_received(
        self, *, sender: str, subject_contains: str = "",
    ) -> datetime | None: ...


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

    def find_code(
        self,
        *,
        sender: str,
        received_after: datetime,
        code_pattern: str,
        subject_contains: str = "",
        max_wait_s: int = 120,
        poll_s: int = 5,
    ) -> str | None:
        """Poll the default Inbox for a one-time verification-code email.

        Blocking (win32com + ``time.sleep``) — call via
        ``asyncio.to_thread`` so it never freezes the shared event loop.
        Only accepts an email received at/after ``received_after`` (minus
        a small skew grace) so a leftover code from a prior/overlapping
        login can't be consumed. Keeps polling on a parse miss until the
        deadline — the code email can land a few seconds late. Returns
        ``None`` on timeout and stashes ``self.last_err`` for diagnostics.
        """
        import win32com.client  # type: ignore[import-untyped]

        # STRICT freshness floor. ``received_after`` must be the timestamp of
        # the newest matching email that existed BEFORE the code was
        # requested (a "baseline" — see ``latest_received``). We only accept
        # an email received strictly AFTER it. Because that floor is itself a
        # real email's ReceivedTime (same clock as the new one), the
        # comparison is clock-skew-proof and can't consume a leftover code
        # from a prior/overlapping login — critical for DB, whose every new
        # code invalidates the previous one.
        deadline = time.time() + max_wait_s
        sender_lc = sender.lower()
        subject_upper = subject_contains.upper()
        pattern = re.compile(code_pattern)
        last_err = f"no matching email from {sender!r} newer than {received_after.isoformat()}"

        while time.time() < deadline:
            try:
                outlook = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
                inbox = outlook.GetDefaultFolder(_OL_FOLDER_INBOX)
                items = inbox.Items
                items.Sort("[ReceivedTime]", True)  # newest first

                for item in items:
                    if getattr(item, "Class", None) != _OL_CLASS_MAIL:
                        continue
                    received = getattr(item, "ReceivedTime", None)
                    if received is None:
                        continue
                    received_utc = received.astimezone(timezone.utc)
                    if received_utc <= received_after:
                        break  # newest-first — nothing strictly newer remains

                    item_sender = (item.SenderEmailAddress or "").lower()
                    if sender_lc not in item_sender:
                        continue
                    if subject_upper and subject_upper not in (item.Subject or "").upper():
                        continue

                    m = pattern.search(item.Body or "")
                    if m:
                        return m.group(1)
                    last_err = "matching email found but body didn't match code_pattern"
            except Exception as exc:  # noqa: BLE001
                last_err = f"{type(exc).__name__}: {exc!s:.120}"
            time.sleep(poll_s)

        self.last_err = last_err
        return None

    def latest_received(
        self, *, sender: str, subject_contains: str = "",
    ) -> datetime | None:
        """Return the ReceivedTime (UTC) of the newest Inbox email matching
        ``sender`` (+ optional subject), or ``None`` if none. Used to snapshot
        a freshness baseline right before requesting a one-time code, so
        :meth:`find_code` can wait for an email strictly newer than it."""
        import win32com.client  # type: ignore[import-untyped]

        sender_lc = sender.lower()
        subject_upper = subject_contains.upper()
        outlook = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
        inbox = outlook.GetDefaultFolder(_OL_FOLDER_INBOX)
        items = inbox.Items
        items.Sort("[ReceivedTime]", True)  # newest first
        for item in items:
            if getattr(item, "Class", None) != _OL_CLASS_MAIL:
                continue
            received = getattr(item, "ReceivedTime", None)
            if received is None:
                continue
            if sender_lc not in (item.SenderEmailAddress or "").lower():
                continue
            if subject_upper and subject_upper not in (item.Subject or "").upper():
                continue
            return received.astimezone(timezone.utc)
        return None
