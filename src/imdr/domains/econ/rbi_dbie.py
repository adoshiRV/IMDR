"""RBI DBIE (Database on Indian Economy) gateway client.

DBIE is a SPA at https://data.rbi.org.in/DBIE/ backed by a JSON gateway at
    https://data.rbi.org.in/CIMS_Gateway_DBIE/GATEWAY/SERVICES/

Auth bootstrap (verified 2026-06-10):
  1. POST to ``security_generateSessionToken`` with ``{"body": {}}`` and the
     standard channel headers (``datatype``, ``channelkey``) but NO
     ``authorization`` header.
  2. The new session token comes back in the HTTP **response header**
     ``authorization`` (a value like ``y2ntg01781036792680197`` — prefix
     rotates per session, suffix is epoch-microseconds).
  3. Use that token as the ``authorization`` request header on subsequent
     DBIE service calls.

Response payloads are HTML-escaped JSON (e.g. ``\\xa0`` non-breaking space
characters appear inside string values) — every response goes through
``html.unescape()`` before ``json.loads``.

Endpoints exercised:
  ``dbie_foreignExchangeReserves``      FX reserves (5 components)
  ``dbie_menuMappingList``               Full taxonomy
  ``dbie_getPublicationDataImpala``      Generic publication-table fetcher
"""

from __future__ import annotations

import html
import json
import time
from dataclasses import dataclass, field
from typing import Any

import httpx


_BASE_DBIE = "https://data.rbi.org.in/CIMS_Gateway_DBIE/GATEWAY/SERVICES"
_BASE_LOGIN = "https://data.rbi.org.in/CIMS_Gateway_LOGIN/GATEWAY/SERVICES"

_BASE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "Origin": "https://data.rbi.org.in",
    "Referer": "https://data.rbi.org.in/DBIE/",
    "datatype": "application/json",
    "channelkey": "key2",
}

_THROTTLE_S = 0.5  # polite spacing between calls; DBIE has no published rate limit


class DBIEError(RuntimeError):
    """Raised when a DBIE service call returns ``status=error``."""


@dataclass
class DBIEClient:
    """Stateful client that holds a session token across calls.

    Use as a context manager or call ``bootstrap()`` explicitly before the
    first service call.  If a service call returns a 4xx/5xx error code from
    the JSON envelope (DBIE returns HTTP 200 with ``header.status="error"``
    on auth failure), the client re-runs ``bootstrap()`` once and retries.
    """

    timeout: int = 30
    _http: httpx.Client = field(init=False, repr=False)
    _token: str | None = field(init=False, default=None, repr=False)

    def __post_init__(self) -> None:
        self._http = httpx.Client(
            headers=_BASE_HEADERS, timeout=self.timeout, follow_redirects=True
        )

    def __enter__(self) -> "DBIEClient":
        self.bootstrap()
        return self

    def __exit__(self, *exc: Any) -> None:
        self._http.close()

    # ------------------------------------------------------------------
    # Bootstrap / token
    # ------------------------------------------------------------------

    def bootstrap(self) -> str:
        """Fetch a fresh session token; cache it on ``self._token``."""
        url = f"{_BASE_DBIE}/security_generateSessionToken"
        # NB: do NOT send our cached authorization on this call.
        r = self._http.post(url, json={"body": {}})
        r.raise_for_status()
        tok = r.headers.get("authorization")
        if not tok:
            raise DBIEError(
                "security_generateSessionToken did not return an "
                "authorization response header"
            )
        self._token = tok
        return tok

    # ------------------------------------------------------------------
    # Generic call
    # ------------------------------------------------------------------

    def call(self, endpoint: str, body: dict) -> dict:
        """POST to a DBIE service endpoint with the cached session token.

        Returns the unescaped JSON body. Raises ``DBIEError`` if the envelope
        reports ``status="error"`` after one auto-retry (which re-runs the
        bootstrap to refresh the token).
        """
        if self._token is None:
            self.bootstrap()

        url = f"{_BASE_DBIE}/{endpoint}"
        payload = {"body": body}

        last_err: dict | None = None
        for attempt in (1, 2):
            time.sleep(_THROTTLE_S)
            headers = {"authorization": self._token or ""}
            r = self._http.post(url, json=payload, headers=headers)
            r.raise_for_status()
            try:
                data = json.loads(html.unescape(r.text))
            except json.JSONDecodeError as exc:
                raise DBIEError(
                    f"{endpoint}: invalid JSON in response: {exc}"
                ) from exc
            hdr = (data.get("header") or {})
            if hdr.get("status") == "success":
                return data
            last_err = hdr
            if attempt == 1:
                # Auth probably expired (DBIE returns errorCode 4302 for that
                # but it's not strictly documented). Re-bootstrap and retry.
                self.bootstrap()
                continue
            break

        raise DBIEError(
            f"{endpoint}: {last_err.get('errorCode')} "
            f"{last_err.get('errorMessage', '')[:200]}" if last_err else
            f"{endpoint}: unknown error"
        )

    # ------------------------------------------------------------------
    # Convenience wrappers — add more as endpoints are decoded.
    # ------------------------------------------------------------------

    def fx_reserves(
        self,
        reserve_code: str,
        from_date: str,
        to_date: str,
        currency_code: str = "USD",
        frequency: str = "Weekly",
    ) -> list[dict]:
        """``dbie_foreignExchangeReserves`` — 5 reserve codes: TR / FCA /
        GOLD / SDR / IMF.

        Dates are passed as ``YYYY-MM-DD HH:MM:SS``. Returns the
        ``resultList`` array directly (caller picks ``timeDate`` /
        ``amount`` / etc.).
        """
        data = self.call(
            "dbie_foreignExchangeReserves",
            {
                "currencyCode": currency_code,
                "reserveCode": reserve_code,
                "fromDate": from_date,
                "toDate": to_date,
                "frequency": frequency,
            },
        )
        return (data.get("body") or {}).get("resultList") or []
