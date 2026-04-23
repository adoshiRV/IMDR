from __future__ import annotations

from unittest.mock import MagicMock

from imdr.vendors.credentials import VendorCredentials, get_vendor_credentials


def test_reads_credentials_by_prefix() -> None:
    settings = MagicMock()
    settings.barclays_username = "alice"
    settings.barclays_password = "hunter2"
    settings.barclays_url = "https://live.barcap.com"

    creds = get_vendor_credentials("barclays", settings=settings)
    assert isinstance(creds, VendorCredentials)
    assert creds.username == "alice"
    assert creds.password == "hunter2"
    assert creds.url == "https://live.barcap.com"


def test_missing_fields_default_to_empty() -> None:
    settings = MagicMock(spec=[])  # no attributes
    creds = get_vendor_credentials("nonexistent", settings=settings)
    assert creds.username == ""
    assert creds.password == ""
    assert creds.url == ""
