"""Plain-httpx session for AU govt fetchers that don't need Playwright.

Used by Treasury / APRA / ABS-commentary fetchers (probed 2026-06-10: all
reachable over plain HTTPS, no Akamai gate). The 4 RBA fetchers do NOT
use this module — they use `_playwright.py` because `rba.gov.au` is
Akamai-gated.

Unlike Korea (KR govt edges reset TLS 1.3 from RV's network), AU edges
that are reachable at all behave normally — no TLS pinning needed. The
two gating stories that DO matter live elsewhere:

  - **RBA** (Akamai-gated): plain GET returns 403. Use the Playwright
    persistent-profile pattern from `playground/econ/rba/fetch_d2_e_tables.py`.
    Per-fetcher; this module is not involved.
  - **AOFM / Treasury / APRA** (corp TLS-inspection on `*.gov.au/sites/default/files/*`):
    Plain HTTPS to the HTML index page typically works; XLSX/PDF downloads
    on `*.gov.au/sites/default/files/*` get HTTP/2 reset. Discovery-only
    fetchers can use this module; download steps need manual Edge.
"""
from __future__ import annotations

import time

import httpx

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/127.0 Safari/537.36"
)


def make_session(timeout: float = 30.0) -> httpx.Client:
    """Standard httpx client for non-gated AU sources (ABS HTML, etc.)."""
    return httpx.Client(
        follow_redirects=True,
        timeout=timeout,
        headers={
            "User-Agent": _UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-AU,en;q=0.8",
        },
    )


def patient_get(
    client: httpx.Client,
    url: str,
    *,
    attempts: int = 4,
    base_sleep: float = 1.5,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    """GET with linear backoff on connect / read timeout.

    AU edges don't have KR's TLS-1.3 reset issue, so 4 attempts is enough.
    Raises RuntimeError after attempts exhausted.
    """
    last: Exception | None = None
    for i in range(1, attempts + 1):
        try:
            r = client.get(url, headers=headers)
            if r.status_code == 200 and len(r.content) > 200:
                return r
            last = RuntimeError(f"HTTP {r.status_code} / {len(r.content)} bytes")
        except (httpx.ConnectError, httpx.ReadError, httpx.ReadTimeout) as exc:
            last = exc
        time.sleep(base_sleep + i * 0.3)
    raise RuntimeError(f"patient_get exhausted ({attempts} attempts) for {url}: {last}")
