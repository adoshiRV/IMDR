"""Plain-httpx session + raw-snapshot helper for US govt fetchers.

federalreserve.gov is plain-GET friendly (confirmed 2026-06-22: HTTP 200,
no Akamai gate, no TLS reset from RV's network for HTML, RSS, JSON, and
PDF endpoints). No Playwright needed for any Federal Reserve Tier-1 stream
— unlike RBA (Akamai) or the KR govt edges (TLS-1.3 reset).

This module deliberately does NOT add anti-detection / stealth flags
(per [[feedback-no-anti-detection-research]]). A standard desktop
User-Agent is all federalreserve.gov needs.
"""
from __future__ import annotations

import time
from pathlib import Path

import httpx

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/127.0 Safari/537.36"
)

RAW_DIR = Path(__file__).parent / "raw"


def make_session(timeout: float = 30.0) -> httpx.Client:
    """Standard httpx client for federalreserve.gov (and other US edges)."""
    return httpx.Client(
        follow_redirects=True,
        timeout=timeout,
        headers={
            "User-Agent": _UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.8",
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
    """GET with linear backoff on connect / read timeout.

    US Fed edges are stable; 4 attempts is plenty. Raises RuntimeError
    after attempts exhausted.
    """
    last: Exception | None = None
    for i in range(1, attempts + 1):
        try:
            r = client.get(url, headers=headers)
            if r.status_code == 200 and len(r.content) >= min_bytes:
                return r
            last = RuntimeError(f"HTTP {r.status_code} / {len(r.content)} bytes")
        except (httpx.ConnectError, httpx.ReadError, httpx.ReadTimeout) as exc:
            last = exc
        time.sleep(base_sleep + i * 0.3)
    raise RuntimeError(f"patient_get exhausted ({attempts} attempts) for {url}: {last}")


def save_raw(stream: str, name: str, content: bytes | str) -> Path:
    """Persist a raw listing response under raw/{stream}/{name} for debugging.

    Discovery-only convenience — keeps the byte-for-byte fetch so parser
    regressions can be reproduced offline. NOT a document store; only
    listing-page artifacts land here, never resolved document bodies.
    """
    out_dir = RAW_DIR / stream
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / name
    if isinstance(content, str):
        path.write_text(content, encoding="utf-8")
    else:
        path.write_bytes(content)
    return path
