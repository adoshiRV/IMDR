"""``Win32OutlookClient.find_code`` — DB email-verification-code reader.

win32com is real in this environment (pywin32 installed), so we patch
``win32com.client.Dispatch`` to substitute a fake MAPI object graph
rather than touching a real Outlook install.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from imdr.research.auth.loginflows.db import _CODE_PATTERN
from imdr.vendors.sessions.outlook import Win32OutlookClient

_OL_CLASS_MAIL = 43

# Fast-poll knobs so timeout tests don't slow the suite down.
_FAST_MAX_WAIT_S = 0.2
_FAST_POLL_S = 0.05


class _FakeItem:
    def __init__(
        self, *, received: datetime, sender: str, subject: str, body: str,
        cls: int = _OL_CLASS_MAIL,
    ) -> None:
        self.Class = cls
        self.ReceivedTime = received
        self.SenderEmailAddress = sender
        self.Subject = subject
        self.Body = body


class _FakeItems(list):
    """Stands in for Outlook's ``Items`` COM collection — already
    constructed newest-first by the tests, ``Sort`` is a no-op."""

    def Sort(self, *args, **kwargs) -> None:
        pass


def _patch_inbox(items: list[_FakeItem]):
    inbox = MagicMock()
    inbox.Items = _FakeItems(items)
    namespace = MagicMock()
    namespace.GetDefaultFolder.return_value = inbox
    app = MagicMock()
    app.GetNamespace.return_value = namespace
    return patch("win32com.client.Dispatch", return_value=app)


def test_find_code_returns_matching_code() -> None:
    now = datetime.now(timezone.utc)
    item = _FakeItem(
        received=now,
        sender="DoNotReply@markit.esp.db.com",
        subject="Verify device",
        body="Please use the following Code: 6BA0EC to continue.",
    )
    with _patch_inbox([item]):
        code = Win32OutlookClient().find_code(
            sender="DoNotReply@markit.esp.db.com",
            received_after=now - timedelta(seconds=5),
            code_pattern=_CODE_PATTERN,
            max_wait_s=_FAST_MAX_WAIT_S,
            poll_s=_FAST_POLL_S,
        )
    assert code == "6BA0EC"


def test_find_code_ignores_pre_received_after_email() -> None:
    """A code email from a prior, unrelated login must not be consumed —
    freshness gate is STRICTLY newer than ``received_after`` (the baseline)."""
    login_time = datetime.now(timezone.utc)
    stale_item = _FakeItem(
        received=login_time - timedelta(minutes=10),
        sender="DoNotReply@markit.esp.db.com",
        subject="Verify device",
        body="Code: 6BA0EC",
    )
    with _patch_inbox([stale_item]):
        code = Win32OutlookClient().find_code(
            sender="DoNotReply@markit.esp.db.com",
            received_after=login_time,
            code_pattern=_CODE_PATTERN,
            max_wait_s=_FAST_MAX_WAIT_S,
            poll_s=_FAST_POLL_S,
        )
    assert code is None


def test_find_code_is_strict_and_takes_newest() -> None:
    """The bug that motivated baseline-diff: a code email received a few
    seconds BEFORE the baseline (an earlier attempt's, now invalidated) must
    NOT be returned; only one strictly newer than the baseline. When both a
    stale and a fresh email are present, return the fresh (newest) one."""
    baseline = datetime.now(timezone.utc)
    stale = _FakeItem(
        received=baseline - timedelta(seconds=8),   # within the old 30s skew
        sender="DoNotReply@markit.esp.db.com",
        subject="Verification Code", body="Code: STALE1",
    )
    fresh = _FakeItem(
        received=baseline + timedelta(seconds=6),
        sender="DoNotReply@markit.esp.db.com",
        subject="Verification Code", body="Code: 5BDF0D",
    )
    # newest-first order
    with _patch_inbox([fresh, stale]):
        code = Win32OutlookClient().find_code(
            sender="DoNotReply@markit.esp.db.com",
            received_after=baseline,
            code_pattern=_CODE_PATTERN,
            max_wait_s=_FAST_MAX_WAIT_S, poll_s=_FAST_POLL_S,
        )
    assert code == "5BDF0D"

    # Only the stale one present → nothing strictly newer → None (would have
    # been wrongly consumed under the old ``received_after - 30s`` gate).
    with _patch_inbox([stale]):
        code = Win32OutlookClient().find_code(
            sender="DoNotReply@markit.esp.db.com",
            received_after=baseline,
            code_pattern=_CODE_PATTERN,
            max_wait_s=_FAST_MAX_WAIT_S, poll_s=_FAST_POLL_S,
        )
    assert code is None


def test_find_code_returns_none_on_timeout() -> None:
    now = datetime.now(timezone.utc)
    with _patch_inbox([]):
        client = Win32OutlookClient()
        code = client.find_code(
            sender="DoNotReply@markit.esp.db.com",
            received_after=now,
            code_pattern=_CODE_PATTERN,
            max_wait_s=_FAST_MAX_WAIT_S,
            poll_s=_FAST_POLL_S,
        )
    assert code is None
    assert "no matching email" in client.last_err


def test_find_code_ignores_wrong_sender() -> None:
    now = datetime.now(timezone.utc)
    item = _FakeItem(
        received=now,
        sender="someoneelse@example.com",
        subject="Verify device",
        body="Code: 6BA0EC",
    )
    with _patch_inbox([item]):
        code = Win32OutlookClient().find_code(
            sender="DoNotReply@markit.esp.db.com",
            received_after=now - timedelta(seconds=5),
            code_pattern=_CODE_PATTERN,
            max_wait_s=_FAST_MAX_WAIT_S,
            poll_s=_FAST_POLL_S,
        )
    assert code is None


def test_latest_received_returns_newest_matching() -> None:
    now = datetime.now(timezone.utc)
    older = _FakeItem(
        received=now - timedelta(minutes=5),
        sender="DoNotReply@markit.esp.db.com",
        subject="Verification Code", body="Code: OLD123",
    )
    newer = _FakeItem(
        received=now,
        sender="DoNotReply@markit.esp.db.com",
        subject="Verification Code", body="Code: NEW456",
    )
    with _patch_inbox([newer, older]):  # newest-first
        ts = Win32OutlookClient().latest_received(
            sender="DoNotReply@markit.esp.db.com",
        )
    assert ts == now


def test_latest_received_none_when_absent() -> None:
    with _patch_inbox([]):
        ts = Win32OutlookClient().latest_received(
            sender="DoNotReply@markit.esp.db.com",
        )
    assert ts is None


class TestCodePattern:
    """The DB code regex — 6 alphanumeric chars anchored on 'Code:'."""

    def test_matches_labelled_code(self) -> None:
        m = re.search(_CODE_PATTERN, "Please use Code: 6BA0EC to verify.")
        assert m is not None
        assert m.group(1) == "6BA0EC"

    def test_matches_without_colon(self) -> None:
        m = re.search(_CODE_PATTERN, "Your Code 6BA0EC expires in 30 minutes.")
        assert m is not None
        assert m.group(1) == "6BA0EC"

    def test_does_not_match_unlabelled_stray_word(self) -> None:
        assert re.search(_CODE_PATTERN, "Please review ABCDEF for details.") is None

    def test_does_not_match_lowercase_noise(self) -> None:
        assert re.search(_CODE_PATTERN, "Code: 6ba0ec") is None
