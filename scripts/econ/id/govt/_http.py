"""Plain-httpx session for the Indonesia govt-filings discovery layer.

Network reality (probed 2026-09-21 from RV's network):

  - **bi.go.id** — plain HTTPS, fast (~0.6s), no gate. SharePoint 2013-era
    `.aspx` with ASP.NET UpdatePanel pagination. No Playwright needed.
  - **webapi.bps.go.id** — the BPS WebAPI. Plain HTTPS + free key. This is
    the ONLY viable BPS path: the HTML portal at `www.bps.go.id` sits behind
    a Cloudflare interactive challenge (`cf-mitigated: challenge`, HTTP 403
    to any plain GET). The API is not challenged, and it carries the press
    releases (BRS) and publications we want — so we never touch the portal.
  - **djppr.kemenkeu.go.id** — SPA shell (5 KB) + JSON API on
    `api-djppr.kemenkeu.go.id`. NOTE: `www.djppr.kemenkeu.go.id` fails TLS
    hostname verification — always use the apex host, no `www.`.
  - **kemenkeu.go.id** — Angular SPA, no API host in the JS bundles. See
    `fetch_kemenkeu.py` for how its listing is actually reached.
  - **ojk.go.id** — plain HTTPS, server-rendered. No gate.

None of these need the Korea-style 10-retry TLS patience; 4 attempts is
ample. Kept configurable in case an edge degrades.
"""
from __future__ import annotations

import time

import httpx

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/127.0 Safari/537.36"
)


def make_session(timeout: float = 45.0) -> httpx.Client:
    """Standard httpx client for Indonesian govt/CB hosts."""
    return httpx.Client(
        follow_redirects=True,
        timeout=timeout,
        headers={
            "User-Agent": _UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            # id first: BI/DJPPR/Kemenkeu serve richer Indonesian-language
            # listings than their English mirrors.
            "Accept-Language": "id-ID,id;q=0.9,en;q=0.8",
        },
    )


def patient_get(
    client: httpx.Client,
    url: str,
    *,
    attempts: int = 4,
    base_sleep: float = 1.5,
    headers: dict[str, str] | None = None,
    min_bytes: int = 200,
) -> httpx.Response:
    """GET with linear backoff on connect/read failure.

    Raises RuntimeError once attempts are exhausted so the caller can turn
    it into a `FetchResult(ok=False)` rather than crashing the daily pull.
    """
    last: Exception | None = None
    for i in range(1, attempts + 1):
        try:
            r = client.get(url, headers=headers)
            if r.status_code == 200 and len(r.content) >= min_bytes:
                return r
            last = RuntimeError(f"HTTP {r.status_code} / {len(r.content)} bytes")
        except (httpx.ConnectError, httpx.ReadError, httpx.ReadTimeout,
                httpx.RemoteProtocolError) as exc:
            last = exc
        time.sleep(base_sleep + i * 0.3)
    raise RuntimeError(f"patient_get exhausted ({attempts}) for {url}: {last}")


def throttle(seconds: float = 1.0) -> None:
    """Politeness pause between requests to the same host."""
    time.sleep(seconds)
