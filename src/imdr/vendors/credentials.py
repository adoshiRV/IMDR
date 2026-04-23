"""Vendor credential accessor.

Keeps acquirers decoupled from specific settings fields — each spec
declares an ``IMDR_{PREFIX}_...`` prefix and the acquirer asks for the
credential bundle by prefix.  New vendors add settings fields and a
spec; no acquirer code changes.
"""
from __future__ import annotations

from dataclasses import dataclass

from imdr.config.settings import Settings, get_settings


@dataclass(frozen=True)
class VendorCredentials:
    """Credential triple common to SSO-style portals.

    Some vendors only populate a subset (e.g. API-key-only feeds leave
    username/password empty).  Callers check the fields they care about.
    """

    username: str
    password: str
    url: str


def get_vendor_credentials(
    prefix: str,
    settings: Settings | None = None,
) -> VendorCredentials:
    """Resolve credentials for a vendor by settings-field prefix.

    ``prefix`` is the lower-case field stem on the ``Settings`` object —
    e.g. ``"barclays"`` reads ``settings.barclays_username``,
    ``barclays_password``, ``barclays_url``.  Matches the existing
    ``IMDR_BARCLAYS_*`` env-var convention in ``.env``.
    """
    s = settings or get_settings()
    return VendorCredentials(
        username=getattr(s, f"{prefix}_username", ""),
        password=getattr(s, f"{prefix}_password", ""),
        url=getattr(s, f"{prefix}_url", ""),
    )
