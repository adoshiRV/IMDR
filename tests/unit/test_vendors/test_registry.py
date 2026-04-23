from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from imdr.notifications.formatters.rates_skew_ingest import RatesSkewIngestFormatter
from imdr.vendors.base import VendorFeed
from imdr.vendors.exceptions import AcquirerMisconfigured
from imdr.vendors.registry import VENDOR_FEEDS, get_feed, list_feeds, register_feed


def _make_feed(name: str) -> VendorFeed:
    return VendorFeed(
        name=name,
        vendor_code="test",
        acquirer=MagicMock(name="acquirer", spec_set=("name", "fetch")),
        pipeline_builder=MagicMock(name="builder"),
        success_formatter=RatesSkewIngestFormatter(),
        staleness_pipeline_name=f"test.{name}",
    )


class TestRegistry:
    def test_import_populates_barclays_skew(self) -> None:
        """Importing the package has the side-effect of registering every spec."""
        import imdr.vendors  # noqa: F401  (registration side-effect)

        assert "barclays_skew" in VENDOR_FEEDS
        assert "barclays_skew" in list_feeds()

    def test_get_feed_returns_registered(self) -> None:
        import imdr.vendors  # noqa: F401

        feed = get_feed("barclays_skew")
        assert feed.name == "barclays_skew"
        assert feed.vendor_code == "barclays"

    def test_get_feed_unknown_raises(self) -> None:
        with pytest.raises(AcquirerMisconfigured) as excinfo:
            get_feed("not_a_real_feed")
        assert "not_a_real_feed" in str(excinfo.value)

    def test_register_feed_duplicate_raises(self) -> None:
        feed = _make_feed("dup_test_feed")
        try:
            register_feed(feed)
            with pytest.raises(AcquirerMisconfigured):
                register_feed(feed)
        finally:
            VENDOR_FEEDS.pop("dup_test_feed", None)
