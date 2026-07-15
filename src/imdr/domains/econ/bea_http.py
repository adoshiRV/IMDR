"""BEA (Bureau of Economic Analysis) JSON API client.

Wraps GET https://apps.bea.gov/api/data with UserID from settings.econ_bea_key.

BEA quirk: errors come back HTTP 200 with an Error object inside
BEAAPI.Results (key "Error") or BEAAPI.Error — both are checked.
"""

from __future__ import annotations

import datetime
import time
from typing import Any

import httpx

from imdr.config.settings import get_settings

_BASE = "https://apps.bea.gov/api/data"


class BeaClient:
    """Minimal BEA GET JSON client."""

    def __init__(self, timeout: int = 30) -> None:
        key = get_settings().econ_bea_key.strip()
        if not key:
            raise RuntimeError("IMDR_ECON_BEA_KEY not set")
        self._key = key
        # Connection-level retries (parity with fred_http's HTTPClient).
        self._client = httpx.Client(
            timeout=timeout,
            transport=httpx.HTTPTransport(retries=3),
        )

    def __enter__(self) -> "BeaClient":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def get_data(
        self,
        datasetname: str,
        *,
        throttle_sec: float = 0.5,
        **params: Any,
    ) -> dict:
        """GET BEA data endpoint; returns the Results dict.

        Raises RuntimeError on both HTTP errors and BEA application errors
        (which come back as HTTP 200 with an Error object in the body).
        """
        query: dict[str, Any] = {
            "UserID": self._key,
            "method": "GetData",
            "datasetname": datasetname,
            "ResultFormat": "JSON",
            **params,
        }
        r = self._client.get(_BASE, params=query)
        r.raise_for_status()
        body = r.json()
        time.sleep(throttle_sec)

        bea = body.get("BEAAPI", {})
        if "Error" in bea:
            err = bea["Error"]
            raise RuntimeError(
                f"BEA API error: {err.get('APIErrorCode')} — {err.get('APIErrorDescription')}"
            )
        results = bea.get("Results", {})
        if "Error" in results:
            err = results["Error"]
            raise RuntimeError(
                f"BEA API error: {err.get('APIErrorCode')} — {err.get('APIErrorDescription')}"
            )
        return results


def bea_period_to_date(period: str) -> datetime.date | None:
    """Map a BEA TimePeriod string to obs_date (period START).

    Quarterly  "2025Q1"  -> 2025-01-01
    Monthly    "2025M05" -> 2025-05-01
    Annual     "2025"    -> 2025-01-01
    """
    p = (period or "").strip()
    try:
        if "Q" in p:
            year_s, q_s = p.split("Q", 1)
            q = int(q_s)
            if 1 <= q <= 4:
                return datetime.date(int(year_s), (q - 1) * 3 + 1, 1)
            return None
        if "M" in p:
            year_s, m_s = p.split("M", 1)
            m = int(m_s)
            if 1 <= m <= 12:
                return datetime.date(int(year_s), m, 1)
            return None
        if len(p) == 4 and p.isdigit():
            return datetime.date(int(p), 1, 1)
    except (TypeError, ValueError):
        return None
    return None


def parse_data_value(raw: str | None) -> float | None:
    """Parse a BEA DataValue string to float.

    BEA emits commas in large numbers ("1,234,567"), "(NA)" for missing,
    and "(D)" for suppressed. All non-numeric values -> None.
    """
    if raw is None:
        return None
    s = raw.strip()
    if not s or s in ("(NA)", "(D)", "--"):
        return None
    try:
        return float(s.replace(",", ""))
    except ValueError:
        return None
