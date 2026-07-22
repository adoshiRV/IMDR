"""Per-vendor programmatic login flows.

A login flow exposes two coroutines::

    async def is_authenticated(ctx) -> bool: ...
    async def login(ctx, *, username: str, password: str) -> None: ...

Both share the contract defined in :mod:`.._base`. Only vendors with a
form-fill credential flow live here; SSO-only vendors are handled by
the generic profile-restore path in :mod:`..context`.

Currently registered:

* :mod:`.barclays` — Barclays Live (PingFederate, profile-wiped per run)
* :mod:`.ubs` — UBS Neo (two-step form, headed Chrome required)
* :mod:`.anz` — ANZ Research (best-guess selectors — verify via validate)
* :mod:`.nomura` — Nomura NomuraNow (best-guess selectors)
* :mod:`.stanc` — Standard Chartered Research (best-guess selectors)
* :mod:`.db` — DB Research (email-verification-code, selectors confirmed
  via live DOM probe)
"""
from __future__ import annotations

from . import anz, barclays, db, nomura, stanc, ubs

__all__ = ["anz", "barclays", "db", "nomura", "stanc", "ubs"]
