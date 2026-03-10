"""Citi Velocity API client — all endpoint types via httpx.

Covers: OAuth2 token, historical data, metadata, tag listing, tag browsing.
Replaces RATES_data/src/client.py (stdlib http.client) with httpx + auto-refreshing token.
"""

from __future__ import annotations

import time
import urllib.parse
from datetime import datetime, timezone
from typing import Any

import httpx
import structlog

from imdr.config.settings import Settings


def _yyyymmdd(dt: datetime) -> int:
    return int(dt.astimezone(timezone.utc).strftime("%Y%m%d"))


def _hhmm(dt: datetime) -> int:
    return int(dt.astimezone(timezone.utc).strftime("%H%M"))


class CitiVelocityClient:
    """Full Citi Velocity API client with auto-refreshing OAuth2 token."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._log = structlog.get_logger("CitiVelocityClient")

        transport = httpx.HTTPTransport(retries=3)
        self._client = httpx.Client(
            base_url=f"https://{settings.citi_host}",
            timeout=settings.citi_timeout,
            transport=transport,
        )

        # Token cache
        self._token: str | None = None
        self._token_expiry: float = 0.0

    # ── 1. Authentication ────────────────────────────────────────

    def get_token(self) -> str:
        """OAuth2 client_credentials grant. Caches token, auto-refreshes on expiry."""
        now = time.monotonic()
        # Refresh 60s before actual expiry
        if self._token and now < (self._token_expiry - 60):
            return self._token

        self._log.info("citi_token_refresh")
        payload = urllib.parse.urlencode({
            "grant_type": "client_credentials",
            "client_id": self._settings.citi_client_id,
            "client_secret": self._settings.citi_client_secret,
            "scope": self._settings.citi_scope,
        })

        resp = self._client.post(
            self._settings.citi_token_path,
            content=payload,
            headers={
                "content-type": "application/x-www-form-urlencoded",
                "accept": "application/json",
            },
        )

        if resp.status_code >= 400:
            raise RuntimeError(
                f"Token fetch failed (status={resp.status_code}): {resp.text[:500]}"
            )

        try:
            data = resp.json()
        except Exception:
            raise RuntimeError(
                f"Token response not JSON (status={resp.status_code}): {resp.text[:500]}"
            )

        if "access_token" not in data:
            raise RuntimeError(f"Token response missing access_token: {data}")

        self._token = data["access_token"]
        ttl = int(data.get("expires_in", self._settings.citi_token_ttl))
        self._token_expiry = now + ttl
        self._log.info("citi_token_acquired", ttl=ttl)
        return self._token

    def _auth_headers(self) -> dict[str, str]:
        """Returns headers with current Bearer token (auto-refreshing if needed)."""
        return {
            "content-type": "application/json",
            "accept": "application/json",
            "authorization": f"Bearer {self.get_token()}",
        }

    # ── 2. Historical Data ───────────────────────────────────────

    def fetch_historical(
        self,
        tags: list[str],
        start: datetime,
        end: datetime,
        frequency: str = "DAILY",
    ) -> dict[str, Any]:
        """POST to data endpoint — time series by tag (1-100 tags per request).

        Returns {status, body: {tag: {x, c, type}}}.
        """
        payload: dict[str, Any] = {
            "startDate": _yyyymmdd(start),
            "endDate": _yyyymmdd(end),
            "startTime": _hhmm(start),
            "endTime": _hhmm(end),
            "tags": tags,
        }
        if frequency:
            payload["frequency"] = frequency

        self._log.info("citi_fetch_historical", n_tags=len(tags), start=str(start.date()), end=str(end.date()))
        return self._post_json(self._settings.citi_data_path, payload)

    # ── 3. Metadata ──────────────────────────────────────────────

    def fetch_metadata(self, tags: list[str]) -> dict[str, Any]:
        """POST to data endpoint with metadata request — series info (1-1000 tags)."""
        payload: dict[str, Any] = {
            "tags": tags,
            "metadata": True,
        }
        self._log.info("citi_fetch_metadata", n_tags=len(tags))
        return self._post_json(self._settings.citi_data_path, payload)

    # ── 4. Tag Listing ───────────────────────────────────────────

    def fetch_taglisting(
        self,
        prefix: str,
        regex: str | None = None,
    ) -> dict[str, Any]:
        """POST to taglisting endpoint — list tags by prefix + optional regex.

        Min 2-level prefix (e.g. 'RATES.OIS.').
        Returns {status, tags: [str]}.
        """
        payload: dict[str, Any] = {"prefix": prefix}
        if regex:
            payload["regex"] = regex

        self._log.info("citi_fetch_taglisting", prefix=prefix)
        return self._post_json(self._settings.citi_taglisting_path, payload)

    # ── 5. Tag Browsing ──────────────────────────────────────────

    def fetch_tagbrowsing(self, prefix: str = "") -> dict[str, Any]:
        """POST to tagbrowsing endpoint — explore tag tree one level at a time.

        Pass '' for root, or partial prefix to drill down.
        Returns {status, fields, leaves, header}.
        """
        payload: dict[str, Any] = {"prefix": prefix}

        self._log.info("citi_fetch_tagbrowsing", prefix=prefix)
        return self._post_json(self._settings.citi_tagbrowsing_path, payload)

    # ── Shared HTTP helper ───────────────────────────────────────

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Common POST with JSON body, auth headers, error handling.

        Appends ?client_id= to path for all non-token endpoints.
        """
        url = f"{path}?client_id={urllib.parse.quote(self._settings.citi_client_id)}"

        resp = self._client.post(url, json=payload, headers=self._auth_headers())

        if resp.status_code >= 400:
            raise RuntimeError(
                f"Citi API error (status={resp.status_code}, path={path}): {resp.text[:500]}"
            )

        try:
            return resp.json()
        except Exception:
            raise RuntimeError(
                f"Citi API response not JSON (status={resp.status_code}, path={path}): {resp.text[:500]}"
            )

    # ── Lifecycle ────────────────────────────────────────────────

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> CitiVelocityClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
