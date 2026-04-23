from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from imdr.vendors.acquirers.email_linked import (
    EmailLinkedDownloadAcquirer,
    EmailLinkedDownloadSpec,
)
from imdr.vendors.exceptions import NoEmailFound, SSOTimeout
from imdr.vendors.sessions.outlook import EmailRef


def _spec(tmp_path: Path) -> EmailLinkedDownloadSpec:
    return EmailLinkedDownloadSpec(
        name="test_feed",
        vendor_code="test_vendor",
        sender="test@example.com",
        subject_contains="TEST REPORT",
        link_label="View Excel",
        listing_anchor_selector="a",
        output_dir=tmp_path / "drop",
        profile_name="test",
    )


class _FakeOutlook:
    def __init__(self, emails: list[EmailRef]) -> None:
        self._emails = emails
        self.calls: list[dict[str, Any]] = []

    def find_matching(self, **kwargs: Any) -> list[EmailRef]:
        self.calls.append(kwargs)
        return self._emails


class _FakeBrowserSession:
    """Substitutes for BrowserSession — records download_anchors calls."""

    instances: list["_FakeBrowserSession"] = []

    def __init__(self, profile_dir: Path, *, headless: bool) -> None:
        self.profile_dir = profile_dir
        self.headless = headless
        self.calls: list[dict[str, Any]] = []
        self.raise_on_fetch: BaseException | None = None
        self.returns: list[tuple[list[Path], int]] = []
        _FakeBrowserSession.instances.append(self)

    def __enter__(self) -> "_FakeBrowserSession":
        return self

    def __exit__(self, *exc: Any) -> None:
        return None

    def download_anchors(self, **kwargs: Any) -> tuple[list[Path], int]:
        self.calls.append(kwargs)
        if self.raise_on_fetch is not None:
            raise self.raise_on_fetch
        return self.returns.pop(0) if self.returns else ([], 0)


@pytest.fixture(autouse=True)
def _clear_fake_instances() -> None:
    _FakeBrowserSession.instances.clear()


@pytest.fixture
def _settings() -> Any:
    s = MagicMock()
    s.browser_profile_root = Path("/tmp/profiles")
    return s


class TestEmailLinkedAcquirer:
    def test_no_email_found_raises(self, tmp_path: Path, _settings: Any) -> None:
        spec = _spec(tmp_path)
        acq = EmailLinkedDownloadAcquirer(spec, outlook=_FakeOutlook([]), settings=_settings)

        with pytest.raises(NoEmailFound) as excinfo:
            acq.fetch(headless=True)
        assert "TEST REPORT" in str(excinfo.value)

    def test_fetch_downloads_and_returns_result(self, tmp_path: Path, _settings: Any) -> None:
        spec = _spec(tmp_path)
        email = EmailRef(
            received=datetime(2026, 4, 23, tzinfo=timezone.utc),
            subject="TEST REPORT daily",
            link_url="https://portal.example.com/report",
        )
        outlook = _FakeOutlook([email])
        acq = EmailLinkedDownloadAcquirer(spec, outlook=outlook, settings=_settings)

        out = tmp_path / "drop"
        saved = [out / "a.xlsx", out / "b.xlsx"]

        with patch("imdr.vendors.acquirers.email_linked.BrowserSession", _FakeBrowserSession):
            _FakeBrowserSession.instances.clear()

            def make_session(*args: Any, **kwargs: Any) -> _FakeBrowserSession:
                s = _FakeBrowserSession(*args, **kwargs)
                s.returns = [(saved, 1234)]
                return s

            with patch(
                "imdr.vendors.acquirers.email_linked.BrowserSession",
                side_effect=make_session,
            ):
                result = acq.fetch(headless=True)

        assert result.ok is True
        assert result.saved_files == saved
        assert result.bytes_downloaded == 1234
        assert result.vendor == "test_vendor"
        assert result.feed == "test_feed"

    def test_sso_timeout_bubbles_up(self, tmp_path: Path, _settings: Any) -> None:
        spec = _spec(tmp_path)
        email = EmailRef(
            received=datetime(2026, 4, 23, tzinfo=timezone.utc),
            subject="TEST REPORT daily",
            link_url="https://portal.example.com/report",
        )
        acq = EmailLinkedDownloadAcquirer(
            spec, outlook=_FakeOutlook([email]), settings=_settings
        )

        def make_session(*args: Any, **kwargs: Any) -> _FakeBrowserSession:
            s = _FakeBrowserSession(*args, **kwargs)
            s.raise_on_fetch = SSOTimeout("timed out waiting")
            return s

        with patch(
            "imdr.vendors.acquirers.email_linked.BrowserSession",
            side_effect=make_session,
        ):
            with pytest.raises(SSOTimeout):
                acq.fetch(headless=True)

    def test_newest_only_limits_to_first_email(self, tmp_path: Path, _settings: Any) -> None:
        spec = _spec(tmp_path)
        emails = [
            EmailRef(datetime(2026, 4, 23, tzinfo=timezone.utc), "TEST REPORT newest", "u1"),
            EmailRef(datetime(2026, 4, 22, tzinfo=timezone.utc), "TEST REPORT older", "u2"),
        ]
        acq = EmailLinkedDownloadAcquirer(
            spec, outlook=_FakeOutlook(emails), settings=_settings
        )

        def make_session(*args: Any, **kwargs: Any) -> _FakeBrowserSession:
            s = _FakeBrowserSession(*args, **kwargs)
            s.returns = [([tmp_path / "a.xlsx"], 1)]
            return s

        with patch(
            "imdr.vendors.acquirers.email_linked.BrowserSession",
            side_effect=make_session,
        ):
            acq.fetch(headless=True)

        # Only one email processed when newest_only=True (default).
        assert len(_FakeBrowserSession.instances) == 1
        assert len(_FakeBrowserSession.instances[0].calls) == 1
