from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from imdr.vendors.base import FetchResult
from imdr.vendors.exceptions import (
    DownloadFailed,
    ListingNotFound,
    NoEmailFound,
    SSOTimeout,
    VendorError,
)


class TestFetchResult:
    def _now(self) -> datetime:
        return datetime(2026, 4, 23, 12, 0, tzinfo=timezone.utc)

    def test_ok_true_when_files_saved(self) -> None:
        r = FetchResult(
            vendor="v", feed="f",
            saved_files=[Path("a.xlsx")],
            started_at=self._now(), finished_at=self._now(),
        )
        assert r.ok is True

    def test_ok_false_when_no_files(self) -> None:
        r = FetchResult(
            vendor="v", feed="f",
            saved_files=[],
            started_at=self._now(), finished_at=self._now(),
        )
        assert r.ok is False

    def test_elapsed_s_computed(self) -> None:
        start = self._now()
        end = start + timedelta(seconds=12.5)
        r = FetchResult(vendor="v", feed="f", started_at=start, finished_at=end)
        assert r.elapsed_s == pytest.approx(12.5)


class TestExceptionHierarchy:
    @pytest.mark.parametrize("cls", [
        NoEmailFound,
        SSOTimeout,
        ListingNotFound,
        DownloadFailed,
    ])
    def test_subclass_of_vendor_error(self, cls: type) -> None:
        assert issubclass(cls, VendorError)
        # Each subclass must be catchable via the base.
        with pytest.raises(VendorError):
            raise cls("boom")
