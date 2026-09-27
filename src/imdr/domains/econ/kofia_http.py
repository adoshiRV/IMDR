"""Shared HTTP helper for KOFIA freeSIS 2.0 statistics (Korea Financial
Investment Association capital-market statistics portal).

freeSIS is a WebSquare SPA, but every statistics page is backed by plain
JSON POSTs — no auth, no browser. Three endpoints matter:

  POST /meta/getMenuData.do      -> full catalogue of SERVICE_IDs (discovery)
  POST /meta/getSrvData.do       -> per-service param spec + grid metadata
  POST /meta/getMetaDataList.do  -> the actual data rows (ds1: TMPV1..TMPVn)

Prod fetchers under ``scripts/econ/kr/kofia/`` import ``fetch_freesis_rows``
rather than rolling their own ``requests`` calls. A session must be primed
with one GET on the portal (done inside ``make_session``) so the backend
issues the cookies its POST handlers expect.

Values in freeSIS are denominated in 억원 (100 million KRW) unless the
service's dsGridInfo says otherwise; convert to krw_bn with ``EOK_TO_KRW_BN``.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import requests

# src/imdr/domains/econ/kofia_http.py -> parents[4] is the repo root.
_REPO_ROOT = Path(__file__).resolve().parents[4]

_BASE = "https://freesis.kofia.or.kr"
_PORTAL = f"{_BASE}/stat/FreeSIS.do"
_DATA_URL = f"{_BASE}/meta/getMetaDataList.do"
_SRV_URL = f"{_BASE}/meta/getSrvData.do"

_RETRIES = 5
_RETRY_SLEEP_S = 2.0

# 1 억원 (100 million KRW) = 0.1 billion KRW. Multiply raw freeSIS values
# (which come in 억원) by this to store as krw_bn.
EOK_TO_KRW_BN = 0.1

# All top-level division ids — required verbatim by getSrvData/getMenuData.
_ALL_DIV = (
    "MSIS10000000000000,MSIS20000000000000,MSIS30000000000000,"
    "MSIS35000000000000,MSIS40000000000000,MSIS60000000000000,"
    "MSIS70000000000000,MSIS50000000000000,MSIS80000000000000,"
    "MSIS90000000000000,MSIS02000000000000,MSIS04000000000000,"
    "MSIS06000000000000,MSIS95000000000000,MSIS07000000000000"
)

_HEADERS = {
    "Content-Type": "application/json; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
    "User-Agent": "Mozilla/5.0 IMDR-kofia",
    "Referer": _PORTAL,
}


def make_session() -> requests.Session:
    """Return a requests.Session primed with freeSIS portal cookies."""
    s = requests.Session()
    s.headers.update(_HEADERS)
    # Prime cookies — the POST data handlers 500 without a portal session.
    s.get(_PORTAL, headers={"User-Agent": _HEADERS["User-Agent"]}, timeout=30)
    return s


def _post(session: requests.Session, url: str, body: dict, timeout: int) -> dict:
    last_err: Exception | None = None
    for attempt in range(1, _RETRIES + 1):
        try:
            resp = session.post(url, json=body, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except (requests.exceptions.ConnectionError,
                requests.exceptions.ChunkedEncodingError,
                requests.exceptions.Timeout) as e:  # Timeout covers Connect+Read
            last_err = e
            if attempt == _RETRIES:
                break
            time.sleep(_RETRY_SLEEP_S)
    raise RuntimeError(f"freeSIS POST failed after {_RETRIES} attempts "
                       f"({url}): {last_err}")


def fetch_freesis_rows(
    session: requests.Session,
    service_id: str,
    params: dict[str, Any],
    *,
    timeout: int = 40,
) -> list[dict]:
    """Fetch the data rows (ds1) for one freeSIS service.

    ``params`` are the service-specific dmSearch fields (date range, unit,
    fund-type, etc.) — ``OBJ_NM`` is added automatically as ``{service_id}BO``.
    Returns the ds1 list (each row a dict of TMPV1..TMPVn); [] if none.
    """
    body = {"dmSearch": {**params, "OBJ_NM": f"{service_id}BO"}}
    payload = _post(session, _DATA_URL, body, timeout)
    rows = payload.get("ds1")
    return rows if isinstance(rows, list) else []


def fetch_srv_meta(
    session: requests.Session,
    service_id: str,
    *,
    timeout: int = 30,
) -> dict:
    """Fetch a service's metadata (param code lists + grid headers).

    Discovery/diagnostics only — prod fetchers hard-code the params they need.
    """
    body = {"dmSearchData": {
        "strSvrId": service_id, "strDivId": _ALL_DIV,
        "app_peron_yn": "Y", "language_gb": "KOR", "strGetCode": "Y"}}
    return _post(session, _SRV_URL, body, timeout)
