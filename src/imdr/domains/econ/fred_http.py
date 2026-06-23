"""FRED REST connector (production).

Reads IMDR_ECON_FRED_KEY (+ optional numbered siblings IMDR_ECON_FRED_KEY2..)
from the environment via the loaded .env. Wraps the FRED observations /
release / updates / search endpoints with retry + structured logging, and
rotates keys per request to spread the 120 req/min/key quota.

Promoted from playground/econ/fred/connector.py 2026-06-23 (US Track-A
completeness). Country-agnostic, vendor-keyed — the US-specific series live in
the seed at scripts/econ/us/fred/seed_us.yml; the cross-country OECD mirror
stays in playground.

Usage:
    from imdr.domains.econ.fred_http import FredClient
    with FredClient() as client:
        obs = client.fetch_series("CPIAUCSL", start="2020-01-01")

FRED API docs: https://fred.stlouisfed.org/docs/api/fred/
"""

from __future__ import annotations

import os
from typing import Any

import structlog

from imdr.config.settings import get_settings
from imdr.connectors.http import HTTPClient

_FRED_BASE = "https://api.stlouisfed.org/fred"

logger = structlog.get_logger("econ.fred_http")


def _api_keys() -> list[str]:
    """Return all FRED API keys in round-robin order.

    Primary key via ``get_settings().econ_fred_key`` (consistent with the
    bls/bea/census/eia connectors); optional numbered siblings
    ``IMDR_ECON_FRED_KEY2..9`` from the env (Settings has only the single
    field, so the rotation pool reads the extras directly). Multiple keys split
    traffic and survive a single key's 429 window (FRED is 120 req/min/key).
    """
    keys: list[str] = []
    primary = (get_settings().econ_fred_key or "").strip()
    if primary:
        keys.append(primary)
    for i in range(2, 10):
        extra = os.environ.get(f"IMDR_ECON_FRED_KEY{i}", "").strip()
        if extra and extra not in keys:
            keys.append(extra)
    if not keys:
        raise EnvironmentError(
            "FRED API key not found. Set IMDR_ECON_FRED_KEY in .env "
            "(optional IMDR_ECON_FRED_KEY2 for a second key). "
            "Register free keys at https://fred.stlouisfed.org/docs/api/api_key.html"
        )
    return keys


class FredClient:
    """Thin, multi-key-aware wrapper over the FRED REST API.

    Rotates through every ``IMDR_ECON_FRED_KEY*`` env var per request to spread
    load. Context-manager compatible — closes the HTTP session on exit.
    """

    def __init__(self, api_key: str | None = None, api_keys: list[str] | None = None) -> None:
        if api_keys is not None:
            self._keys = list(api_keys)
        elif api_key is not None:
            self._keys = [api_key]
        else:
            self._keys = _api_keys()
        self._key_idx = 0
        self._http = HTTPClient(base_url=_FRED_BASE, timeout=30, retries=3)

    def _next_key(self) -> str:
        key = self._keys[self._key_idx % len(self._keys)]
        self._key_idx += 1
        return key

    def series_info(self, series_id: str) -> dict[str, Any]:
        """Return metadata dict for a single FRED series (raises if not found)."""
        data = self._http.get_json(
            "/series",
            params={"series_id": series_id, "api_key": self._next_key(), "file_type": "json"},
        )
        series_list = data.get("seriess", [])
        if not series_list:
            raise ValueError(f"FRED series not found: {series_id!r}")
        return series_list[0]

    def fetch_series(
        self,
        series_id: str,
        start: str | None = None,
        end: str | None = None,
        vintage_dates: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return list of observation dicts for ``series_id`` ('.' → None)."""
        params: dict[str, Any] = {
            "series_id": series_id,
            "api_key": self._next_key(),
            "file_type": "json",
        }
        if start:
            params["observation_start"] = start
        if end:
            params["observation_end"] = end
        if vintage_dates:
            params["vintage_dates"] = vintage_dates

        logger.info("fred_fetch", series_id=series_id, start=start, end=end)
        data = self._http.get_json("/series/observations", params=params)
        obs = data.get("observations", [])
        for row in obs:
            if row.get("value") == ".":
                row["value"] = None
        return obs

    def fetch_release_calendar(
        self,
        realtime_start: str,
        realtime_end: str,
        include_release_dates_with_no_data: bool = True,
    ) -> list[dict[str, Any]]:
        """Return release-calendar entries within a realtime window."""
        params: dict[str, Any] = {
            "api_key": self._next_key(),
            "file_type": "json",
            "realtime_start": realtime_start,
            "realtime_end": realtime_end,
            "include_release_dates_with_no_data": (
                "true" if include_release_dates_with_no_data else "false"
            ),
        }
        logger.info("fred_release_calendar", realtime_start=realtime_start, realtime_end=realtime_end)
        data = self._http.get_json("/releases/dates", params=params)
        return data.get("release_dates", [])

    def fetch_recent_updates(
        self,
        start_time: str,
        end_time: str | None = None,
        filter_value: str = "all",
    ) -> list[dict[str, Any]]:
        """Return series updated within a time window (incremental-ingest helper)."""
        params: dict[str, Any] = {
            "api_key": self._next_key(),
            "file_type": "json",
            "start_time": start_time,
            "filter_value": filter_value,
        }
        if end_time is not None:
            params["end_time"] = end_time
        logger.info("fred_recent_updates", start_time=start_time, end_time=end_time)
        data = self._http.get_json("/series/updates", params=params)
        return data.get("seriess", [])

    def search_series(
        self,
        query: str | None = None,
        search_type: str = "full_text",
        tag_names: list[str] | None = None,
        limit: int = 50,
        order_by: str = "popularity",
    ) -> list[dict[str, Any]]:
        """Search the FRED series catalog (query and/or tag_names required)."""
        if not query and not tag_names:
            raise ValueError("search_series requires at least one of 'query' or 'tag_names'")
        params: dict[str, Any] = {
            "api_key": self._next_key(),
            "file_type": "json",
            "search_type": search_type,
            "limit": limit,
            "order_by": order_by,
        }
        if query:
            params["search_text"] = query
        if tag_names:
            params["tag_names"] = ";".join(tag_names)
        logger.info("fred_search", query=query, tag_names=tag_names, limit=limit)
        data = self._http.get_json("/series/search", params=params)
        return data.get("seriess", [])

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "FredClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
