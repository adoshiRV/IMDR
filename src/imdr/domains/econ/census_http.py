"""Census Bureau EITS time-series API client.

GET wrapper for https://api.census.gov/data/timeseries/eits/{program} and
the intltrade sub-endpoints. Returns list-of-dicts by zipping the header row.

Key read via get_settings().econ_census_key (IMDR_ECON_CENSUS_KEY in .env).
"""

from __future__ import annotations

import datetime
import time
from typing import Any
from urllib.parse import urlencode

import httpx

from imdr.config.settings import get_settings

_BASE = "https://api.census.gov/data"
_DEFAULT_TIMEOUT = 60


def eits_time_to_date(t: str) -> datetime.date | None:
    """Parse a Census EITS / intltrade ``time`` value (``YYYY-MM``) to a date.

    Returns the first of the month, or None on a malformed value. Shared by
    the census_{retail,trade,housing} fetchers.
    """
    try:
        parts = t.split("-")
        return datetime.date(int(parts[0]), int(parts[1]), 1)
    except (IndexError, ValueError, TypeError):
        return None


class CensusClient:
    """Minimal Census EITS / intltrade client.

    All GET calls return list[dict] — header row zipped with each data row.
    The raw Census response is a 2-D array where row[0] is the header.
    """

    def __init__(self, api_key: str | None = None, timeout: int = _DEFAULT_TIMEOUT) -> None:
        key = api_key if api_key is not None else get_settings().econ_census_key
        self._key = key.strip()
        if not self._key:
            raise RuntimeError(
                "Census API key is empty. Set IMDR_ECON_CENSUS_KEY in .env."
            )
        # Connection-level retries (parity with fred_http's HTTPClient).
        self._client = httpx.Client(
            timeout=timeout,
            transport=httpx.HTTPTransport(retries=3),
        )

    def __enter__(self) -> "CensusClient":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def get_eits(
        self,
        program: str,
        params: dict[str, Any],
        *,
        throttle_sec: float = 0.3,
    ) -> list[dict]:
        """GET timeseries/eits/{program}; return list-of-dicts.

        ``params`` should include ``get``, ``time``, and any filter params.
        The API key is injected automatically.
        """
        url = f"{_BASE}/timeseries/eits/{program}"
        return self._get(url, params, throttle_sec=throttle_sec)

    def get_intltrade(
        self,
        sub_path: str,
        params: dict[str, Any],
        *,
        throttle_sec: float = 0.3,
    ) -> list[dict]:
        """GET timeseries/intltrade/{sub_path}; return list-of-dicts.

        ``sub_path`` is e.g. ``exports/enduse`` or ``imports/enduse``.
        """
        url = f"{_BASE}/timeseries/intltrade/{sub_path}"
        return self._get(url, params, throttle_sec=throttle_sec)

    def _get(
        self,
        url: str,
        params: dict[str, Any],
        *,
        throttle_sec: float = 0.3,
    ) -> list[dict]:
        merged = dict(params)
        merged["key"] = self._key

        # The Census EITS API uses 'time=from+YYYY' as a range operator.
        # Standard URL encoding turns '+' into '%2B', breaking the range
        # syntax. Build the query string manually so '+' is preserved as a
        # literal character in the final URL.
        qs = urlencode(
            {k: v for k, v in merged.items()},
            quote_via=lambda s, *_: s.replace(" ", "+"),
        )
        final_url = f"{url}?{qs}"
        r = self._client.get(final_url)

        if r.status_code == 204:
            return []
        r.raise_for_status()
        raw: list[list[str]] = r.json()
        if not raw:
            return []
        header = raw[0]
        time.sleep(throttle_sec)
        return [dict(zip(header, row)) for row in raw[1:]]
