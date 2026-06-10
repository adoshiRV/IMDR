"""Patient TLS-1.2-pinned HTTP session for Korea govt edges.

Same shape as the KOSIS-pattern adapter (TLS 1.3 from RV's network gets
reset by KR govt origins); the patient variant adds extended retry for
intermittently-flaky edges like FSC, KCS, MOTIR, BoK confirmed
2026-06-10. See memory: feedback_kr_govt_flaky_tls_patient_retry.md.

Defense-in-depth (added 2026-06-10): every URL passed through
``patient_get`` / ``patient_post`` is validated against an allowlist
of acceptable Korea-govt hostname suffixes + an ``https://`` scheme
requirement. Closes the theoretical SSRF path of a compromised
listing-endpoint redirecting us to a corp-internal address.
"""
from __future__ import annotations

import ssl
import time
from typing import Any
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/127.0 Safari/537.36"
)

# Hostname-suffix allowlist for outbound HTTP. We only hit Korea govt /
# quasi-govt origins from these fetchers. Block any URL outside this set
# (including http://, file://, javascript:, internal RV IPs) — protects
# against a compromised listing endpoint returning a redirect to corp
# infrastructure. Add new agencies' suffixes here when onboarding.
_ALLOWED_HOST_SUFFIXES = (
    ".go.kr",       # govt: moef, motir, customs, kostat, etc.
    ".or.kr",       # quasi-govt: bok, fss, kosis, kofia, etc.
    ".re.kr",       # research institutes: kdi, kiep, kif, etc.
)


def _validate_url(url: str) -> None:
    """Reject non-https URLs and hosts outside the KR-govt allowlist."""
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError(f"URL must use https scheme, got {parsed.scheme!r}: {url}")
    host = (parsed.hostname or "").lower()
    if not host:
        raise ValueError(f"URL has no host: {url}")
    if not any(host.endswith(s) for s in _ALLOWED_HOST_SUFFIXES):
        raise ValueError(
            f"host {host!r} not in KR-govt allowlist {_ALLOWED_HOST_SUFFIXES}: {url}"
        )


class _Tls12Adapter(HTTPAdapter):
    """Pin TLS 1.2 — KR govt edges reset TLS 1.3 from corp networks."""

    def init_poolmanager(self, *args: Any, **kwargs: Any):  # type: ignore[override]
        ctx = ssl.create_default_context()
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.maximum_version = ssl.TLSVersion.TLSv1_2
        kwargs["ssl_context"] = ctx
        return super().init_poolmanager(*args, **kwargs)


def make_session() -> requests.Session:
    s = requests.Session()
    s.mount("https://", _Tls12Adapter())
    s.headers["User-Agent"] = _UA
    s.headers["Accept"] = "*/*"
    s.headers["Accept-Language"] = "en-US,en;q=0.8,ko;q=0.5"
    return s


def patient_get(
    session: requests.Session,
    url: str,
    *,
    attempts: int = 10,
    base_sleep: float = 2.5,
    timeout: float = 45,
    headers: dict[str, str] | None = None,
) -> requests.Response:
    """GET with linear backoff on ConnectionReset/SSLError/Timeout.

    Raises RuntimeError after all attempts exhausted. Raises ValueError
    immediately if the URL is non-https or its host is outside the
    KR-govt allowlist. The default 10 attempts × ~2.5s base sleep
    covers the worst-observed FSC/KCS edge behaviour (typically
    succeeds within 5 tries).
    """
    _validate_url(url)
    last: Exception | None = None
    for i in range(1, attempts + 1):
        try:
            r = session.get(url, timeout=timeout, allow_redirects=True, headers=headers)
            if r.status_code == 200 and len(r.content) > 200:
                return r
            last = RuntimeError(f"HTTP {r.status_code} / {len(r.content)} bytes")
        except (requests.exceptions.ConnectionError, requests.exceptions.SSLError, requests.exceptions.Timeout) as exc:
            last = exc
        time.sleep(base_sleep + i * 0.4)
    raise RuntimeError(f"patient_get exhausted ({attempts} attempts) for {url}: {last}")


def patient_post(
    session: requests.Session,
    url: str,
    *,
    data: dict[str, str],
    headers: dict[str, str] | None = None,
    attempts: int = 10,
    base_sleep: float = 2.5,
    timeout: float = 45,
) -> requests.Response:
    _validate_url(url)
    last: Exception | None = None
    for i in range(1, attempts + 1):
        try:
            r = session.post(url, data=data, timeout=timeout, headers=headers)
            if r.status_code == 200 and len(r.content) > 200:
                return r
            last = RuntimeError(f"HTTP {r.status_code} / {len(r.content)} bytes")
        except (requests.exceptions.ConnectionError, requests.exceptions.SSLError, requests.exceptions.Timeout) as exc:
            last = exc
        time.sleep(base_sleep + i * 0.4)
    raise RuntimeError(f"patient_post exhausted ({attempts} attempts) for {url}: {last}")
