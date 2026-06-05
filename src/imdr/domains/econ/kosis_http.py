"""Shared TLS-1.2-pinned HTTP helper for KOSIS OpenAPI fetchers.

KOSIS's edge resets TLS 1.3 handshakes from our corporate network and is
also intermittently flaky on TLS 1.2 (Recv failure: Connection was reset).
This helper wraps both pins:
  - Force TLS 1.2 via a custom HTTPAdapter
  - Retry connection-reset errors up to N times with linear backoff

All prod KOSIS fetchers under `scripts/econ/kosis/` should import
``fetch_kosis_table`` rather than rolling their own ``requests`` calls.
"""

from __future__ import annotations

import os
import ssl
import time
from pathlib import Path
from typing import Any

import requests
from requests.adapters import HTTPAdapter


_KOSIS_URL = "https://kosis.kr/openapi/Param/statisticsParameterData.do"
# src/imdr/domains/econ/kosis_http.py -> parents[4] is the repo root.
_REPO_ROOT = Path(__file__).resolve().parents[4]

_RETRIES = 6
_RETRY_SLEEP_S = 1.5


class _Tls12Adapter(HTTPAdapter):
    """Pin TLS 1.2 -- KOSIS resets TLS 1.3 from corp networks."""

    def init_poolmanager(self, *args: Any, **kwargs: Any):  # type: ignore[override]
        ctx = ssl.create_default_context()
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.maximum_version = ssl.TLSVersion.TLSv1_2
        kwargs["ssl_context"] = ctx
        return super().init_poolmanager(*args, **kwargs)


def make_session() -> requests.Session:
    """Return a requests.Session with TLS 1.2 pinned and a browser UA."""
    s = requests.Session()
    s.mount("https://", _Tls12Adapter())
    s.headers["User-Agent"] = "Mozilla/5.0 IMDR-kosis"
    return s


def load_kosis_key() -> str:
    """Read IMDR_KOSIS_API_KEY from env or fall back to .env file."""
    key = os.environ.get("IMDR_KOSIS_API_KEY")
    if key:
        return key
    env_path = _REPO_ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("IMDR_KOSIS_API_KEY="):
                return line.split("=", 1)[1].strip()
    raise RuntimeError("IMDR_KOSIS_API_KEY not set in env or .env")


def fetch_kosis_table(
    session: requests.Session,
    *,
    org_id: str,
    tbl_id: str,
    obj_l1: str = "ALL",
    itm_id: str = "ALL",
    prd_se: str = "M",
    start_prd_de: str | None = None,
    end_prd_de: str | None = None,
    new_est_prd_cnt: int | None = None,
    extra_params: dict[str, str] | None = None,
    timeout: int = 30,
) -> list[dict]:
    """Fetch one KOSIS table cut, with TLS-reset retry.

    Returns the parsed JSON list. Raises RuntimeError on KOSIS-level errors
    (err code in payload) or exhausted retries.

    Use either ``start_prd_de`` + ``end_prd_de`` for an explicit window, or
    ``new_est_prd_cnt`` for "last N periods". Pass one or the other.
    """
    if (start_prd_de or end_prd_de) and new_est_prd_cnt:
        raise ValueError("Use either start/end date OR newEstPrdCnt, not both")

    params: dict[str, Any] = {
        "method": "getList",
        "apiKey": load_kosis_key(),
        "orgId": org_id,
        "tblId": tbl_id,
        "itmId": itm_id,
        "objL1": obj_l1,
        "prdSe": prd_se,
        "format": "json",
        "jsonVD": "Y",
    }
    if new_est_prd_cnt is not None:
        params["newEstPrdCnt"] = new_est_prd_cnt
    if start_prd_de:
        params["startPrdDe"] = start_prd_de
    if end_prd_de:
        params["endPrdDe"] = end_prd_de
    if extra_params:
        params.update(extra_params)

    last_err: Exception | None = None
    for attempt in range(1, _RETRIES + 1):
        try:
            resp = session.get(_KOSIS_URL, params=params, timeout=timeout)
            resp.raise_for_status()
            payload = resp.json()
            if isinstance(payload, dict) and payload.get("err"):
                raise RuntimeError(
                    f"KOSIS API error {payload['err']} on {tbl_id}/{obj_l1}: "
                    f"{payload.get('errMsg')}"
                )
            if isinstance(payload, list):
                return payload
            raise RuntimeError(
                f"Unexpected payload shape for {tbl_id}: {type(payload).__name__}"
            )
        except (requests.exceptions.ConnectionError,
                requests.exceptions.ChunkedEncodingError) as e:
            last_err = e
            if attempt == _RETRIES:
                break
            time.sleep(_RETRY_SLEEP_S)
    raise RuntimeError(
        f"KOSIS connection failed after {_RETRIES} attempts for "
        f"{tbl_id}/{obj_l1}: {last_err}"
    )


def parse_kosis_period(raw: str | None, prd_se: str) -> tuple[int, int, int] | None:
    """Parse a KOSIS PRD_DE field into (year, month, day) tuple.

    PRD_DE format depends on cadence:
      - M (monthly): 6 chars YYYYMM
      - Q (quarterly): 6 chars YYYYQ (e.g. 20261)
      - A (annual): 4 chars YYYY
      - W (weekly, via REB mirror): 8 chars YYYYMMDD
      - D (daily): 8 chars YYYYMMDD

    Returns (year, month, day) anchored to the period START. Returns None
    on parse error.
    """
    if not raw:
        return None
    try:
        if prd_se in ("M",) and len(raw) == 6:
            return int(raw[:4]), int(raw[4:6]), 1
        if prd_se in ("Q",) and len(raw) == 6:
            year = int(raw[:4])
            quarter = int(raw[4:6])
            if 1 <= quarter <= 4:
                return year, (quarter - 1) * 3 + 1, 1
            return None
        if prd_se in ("A",) and len(raw) == 4:
            return int(raw), 1, 1
        if prd_se in ("W", "D") and len(raw) == 8:
            return int(raw[:4]), int(raw[4:6]), int(raw[6:8])
    except (TypeError, ValueError):
        pass
    return None
