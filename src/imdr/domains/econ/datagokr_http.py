"""Shared HTTP helper for data.go.kr public-data REST APIs
(``apis.data.go.kr/{org}/{service}/{operation}``).

These are plain GET endpoints keyed by a per-account ``serviceKey``, returning
a standard envelope: ``response.header.resultCode`` (``"00"`` = NORMAL) +
``response.body.items.item`` (a list, or a single dict when there is exactly
one row) + ``response.body.totalCount`` for pagination.

CRITICAL GOTCHA — the serviceKey stored in ``.env`` (``IMDR_KSD_API_KEY`` and
friends) is the URL-ENCODED ("Encoding") variant data.go.kr issues, ending in
``%3D%3D``. It must be placed RAW into the query string. Passing it through
``requests(params=...)`` re-encodes the literal ``%`` characters (``%``→``%25``)
and silently breaks auth (data.go.kr returns a SERVICE_KEY_IS_NOT_REGISTERED
error even though the key is valid) — so every other query param is
urlencoded normally and the whole string is concatenated by hand.

Also: use ``https`` — ``http``/port-80 times out from this host. TLS
verification is disabled to match the other Korean-government transports in
this codebase (``bi_srbi.py``); these are corporate-proxied hosts.
"""

from __future__ import annotations

import time
import urllib.parse
from typing import Any

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_RETRIES = 5
_RETRY_SLEEP_S = 2.0


def _get(session: requests.Session, url: str, timeout: int) -> dict:
    last_err: Exception | None = None
    for attempt in range(1, _RETRIES + 1):
        try:
            resp = session.get(url, timeout=timeout, verify=False)
            resp.raise_for_status()
            return resp.json()
        except (requests.exceptions.ConnectionError,
                requests.exceptions.ChunkedEncodingError,
                requests.exceptions.Timeout) as e:  # Timeout covers Connect+Read
            last_err = e
            if attempt == _RETRIES:
                break
            time.sleep(_RETRY_SLEEP_S)
    raise RuntimeError(f"data.go.kr GET failed after {_RETRIES} attempts "
                       f"({url}): {last_err}")


def _build_url(service_url: str, key: str, params: dict[str, Any]) -> str:
    """Build the request URL with ``key`` raw and every other param encoded."""
    query = "&".join(
        f"{k}={urllib.parse.quote(str(v), safe='')}" for k, v in params.items()
    )
    return f"{service_url}?serviceKey={key}&{query}"


def _extract_items(payload: dict) -> tuple[list[dict], int]:
    """Return (items, totalCount) from one data.go.kr response page."""
    response = payload.get("response") or {}
    header = response.get("header") or {}
    result_code = header.get("resultCode")
    if result_code != "00":
        raise RuntimeError(
            f"data.go.kr resultCode={result_code!r}: {header.get('resultMsg')}"
        )
    body = response.get("body") or {}
    items = (body.get("items") or {}).get("item")
    if items is None:
        items = []
    elif isinstance(items, dict):
        items = [items]
    total_count = int(body.get("totalCount") or 0)
    return items, total_count


def fetch_datagokr_rows(
    session: requests.Session,
    service_url: str,
    key: str,
    params: dict[str, Any],
    *,
    page_size: int = 1000,
    timeout: int = 40,
    sleep_s: float = 0.2,
    max_pages: int | None = None,
) -> list[dict]:
    """Page a data.go.kr operation to exhaustion; returns all `item` rows.

    ``service_url`` is the full endpoint, e.g.
    ``https://apis.data.go.kr/1160100/GetShorTermSecuIssuInfoService_V2/getCdIssuBasiInfo_V2``.
    ``key`` is the raw (already URL-encoded) serviceKey from `.env` — see the
    module docstring; do NOT pre-decode it.
    ``params`` are the operation's own filters (e.g. ``basDt``); ``pageNo`` /
    ``numOfRows`` / ``resultType`` are added automatically.
    """
    rows: list[dict] = []
    page_no = 1
    while True:
        page_params = {
            **params,
            "pageNo": page_no,
            "numOfRows": page_size,
            "resultType": "json",
        }
        url = _build_url(service_url, key, page_params)
        payload = _get(session, url, timeout)
        items, total_count = _extract_items(payload)
        rows.extend(items)
        if not items:
            break
        if len(rows) >= total_count:
            break
        if max_pages is not None and page_no >= max_pages:
            break
        page_no += 1
        time.sleep(sleep_s)
    return rows


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": "Mozilla/5.0 IMDR-datagokr"})
    return s
