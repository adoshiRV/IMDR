"""EIA v2 API client.

GET wrapper around https://api.eia.gov/v2/{route}/data/ with auto-pagination
via offset/length. Single API key IMDR_ECON_EIA_KEY (free registration at
https://www.eia.gov/opendata/register.php).

Route-to-series mapping for energy spot prices:
  petroleum/pri/spt   — WTI (RWTC), Brent (RBRTE)
  natural-gas/pri/fut — Henry Hub spot (RNGWHHD)
"""

from __future__ import annotations

import time
from typing import Any

import httpx

from imdr.config.settings import get_settings

_BASE = "https://api.eia.gov/v2"
_PAGE_SIZE = 5000  # EIA max per request


class EiaClient:
    """Minimal EIA v2 GET client with auto-pagination."""

    def __init__(self, timeout: int = 60) -> None:
        self._key = get_settings().econ_eia_key.strip()
        if not self._key:
            raise RuntimeError("IMDR_ECON_EIA_KEY not set")
        self._client = httpx.Client(timeout=timeout)

    def __enter__(self) -> "EiaClient":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def fetch_series(
        self,
        route: str,
        *,
        frequency: str,
        facets: dict[str, str | list[str]] | None = None,
        start_period: str | None = None,
        throttle_sec: float = 0.3,
    ) -> list[dict[str, Any]]:
        """Fetch all rows for a route/frequency/facet combination.

        Paginates automatically using offset until no more rows are returned.
        Returns a flat list of EIA row dicts (period, value, series, units, ...).

        ``facets`` maps facet id to a single value or list of values.
        ``start_period`` is an ISO date string (YYYY-MM-DD); rows before it are
        filtered client-side (EIA v2 has no formal start param for all routes).
        """
        url = f"{_BASE}/{route.strip('/')}/data/"
        all_rows: list[dict] = []
        offset = 0

        while True:
            # A list of (key, value) pairs, not a dict, so list-valued facets
            # (e.g. {"series": ["RWTC", "RBRTE"]}) emit a repeated
            # facets[series][]=... param per value instead of clobbering one key.
            params: list[tuple[str, Any]] = [
                ("api_key", self._key),
                ("frequency", frequency),
                ("data[0]", "value"),
                ("sort[0][column]", "period"),
                ("sort[0][direction]", "asc"),
                ("length", _PAGE_SIZE),
                ("offset", offset),
            ]
            if facets:
                for fid, fval in facets.items():
                    values = fval if isinstance(fval, list) else [fval]
                    for v in values:
                        params.append((f"facets[{fid}][]", v))

            r = self._client.get(url, params=params)
            r.raise_for_status()
            body = r.json()

            err = body.get("error") or body.get("response", {}).get("error")
            if err:
                raise RuntimeError(f"EIA API error on {route}: {err}")

            rows = body.get("response", {}).get("data", [])
            if not rows:
                break
            all_rows.extend(rows)
            if len(rows) < _PAGE_SIZE:
                break
            offset += _PAGE_SIZE
            time.sleep(throttle_sec)

        if start_period:
            all_rows = [r for r in all_rows if r.get("period", "") >= start_period]

        return all_rows
