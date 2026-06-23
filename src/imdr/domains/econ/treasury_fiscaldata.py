"""Treasury Fiscal Data API client.

Keyless REST API at https://api.fiscaldata.treasury.gov/
GET /services/api/fiscal_service/{path}?fields=...&filter=...&sort=...&page[size]=...&page[number]=...

Auto-paginates by following meta.total-pages until all pages are consumed.
No authentication required.

Uses requests.Session — httpx dropped connections intermittently against the
Treasury server; the synchronous session avoids that instability.
"""

from __future__ import annotations

import time

import requests

_BASE = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service"
_DEFAULT_PAGE_SIZE = 10_000
_THROTTLE_SEC = 0.25


class TreasuryClient:
    """Minimal Treasury Fiscal Data REST client with auto-pagination."""

    def __init__(self, timeout: int = 30) -> None:
        self._timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({"Accept": "application/json"})

    def __enter__(self) -> "TreasuryClient":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def close(self) -> None:
        self._session.close()

    def get_all(
        self,
        path: str,
        *,
        fields: str | None = None,
        filter_: str | None = None,
        sort: str = "-record_date",
        page_size: int = _DEFAULT_PAGE_SIZE,
    ) -> list[dict]:
        """Fetch all pages for a given endpoint + query, returns flat list of dicts.

        Drives pagination via page[number] increments, terminating when the
        current page number reaches meta.total-pages.
        """
        params: dict[str, str | int] = {
            "sort": sort,
            "page[size]": page_size,
            "page[number]": 1,
        }
        if fields:
            params["fields"] = fields
        if filter_:
            params["filter"] = filter_

        url = f"{_BASE}/{path.lstrip('/')}"
        all_data: list[dict] = []
        page = 1

        while True:
            params["page[number]"] = page
            resp = self._session.get(url, params=params, timeout=self._timeout)
            resp.raise_for_status()
            body = resp.json()

            rows = body.get("data", [])
            all_data.extend(rows)

            meta = body.get("meta", {})
            total_pages = int(meta.get("total-pages", 1))
            if page >= total_pages:
                break

            page += 1
            time.sleep(_THROTTLE_SEC)

        return all_data
