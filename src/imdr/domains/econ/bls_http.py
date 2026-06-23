"""BLS Public Data API v2 client.

POST JSON wrapper around https://api.bls.gov/publicAPI/v2/timeseries/data/.
Single registration key (IMDR_ECON_BLS_KEY). Registered v2 limits:
500 queries/day, 50 series/query, 20 years/query.
"""

from __future__ import annotations

import datetime
import time

import httpx

from imdr.config.settings import get_settings

_BASE = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
_MAX_SERIES_PER_CALL = 50
_MAX_YEARS_PER_CALL = 20


class BlsClient:
    """Minimal BLS v2 timeseries client."""

    def __init__(self, timeout: int = 30) -> None:
        self._key = get_settings().econ_bls_key.strip()
        if not self._key:
            raise RuntimeError("IMDR_ECON_BLS_KEY not set")
        self._client = httpx.Client(timeout=timeout)

    def __enter__(self) -> "BlsClient":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def fetch_series(
        self,
        series_ids: list[str],
        start_year: int,
        end_year: int,
        *,
        catalog: bool = False,
        throttle_sec: float = 0.5,
    ) -> dict[str, list[dict]]:
        """Fetch one or more BLS series, chunking by 50-series / 20-year limits.

        Returns {series_id: [obs, ...]} where each obs is BLS's raw dict
        (year, period, periodName, value, footnotes). Newest-first per BLS.
        """
        results: dict[str, list[dict]] = {sid: [] for sid in series_ids}
        year_spans: list[tuple[int, int]] = []
        lo = start_year
        while lo <= end_year:
            hi = min(lo + _MAX_YEARS_PER_CALL - 1, end_year)
            year_spans.append((lo, hi))
            lo = hi + 1

        for i in range(0, len(series_ids), _MAX_SERIES_PER_CALL):
            chunk = series_ids[i : i + _MAX_SERIES_PER_CALL]
            for span_lo, span_hi in year_spans:
                payload = {
                    "seriesid": chunk,
                    "startyear": str(span_lo),
                    "endyear": str(span_hi),
                    "registrationkey": self._key,
                    "catalog": catalog,
                }
                r = self._client.post(_BASE, json=payload)
                r.raise_for_status()
                body = r.json()
                status = body.get("status")
                if status != "REQUEST_SUCCEEDED":
                    raise RuntimeError(
                        f"BLS request failed: status={status} messages={body.get('message')}"
                    )
                for series in body["Results"]["series"]:
                    sid = series["seriesID"]
                    results.setdefault(sid, []).extend(series.get("data", []))
                time.sleep(throttle_sec)
        return results


def bls_period_to_date(year: str, period: str) -> datetime.date | None:
    """Map a BLS (year, period) pair to obs_date (period START).

    Monthly  M01..M12 -> first of month.
    Quarterly Q01..Q04 -> first of quarter; Q05 (annual avg) -> skip (None).
    Annual   A01 -> Jan 1.
    Semiannual S01/S02 -> Jan 1 / Jul 1.
    """
    try:
        y = int(year)
    except (TypeError, ValueError):
        return None
    p = (period or "").strip().upper()
    if p.startswith("M"):
        m = int(p[1:])
        if 1 <= m <= 12:
            return datetime.date(y, m, 1)
        return None  # M13 = annual avg
    if p.startswith("Q"):
        q = int(p[1:])
        if 1 <= q <= 4:
            return datetime.date(y, (q - 1) * 3 + 1, 1)
        return None  # Q05 = annual avg
    if p.startswith("S"):
        s = int(p[1:])
        return datetime.date(y, 1 if s == 1 else 7, 1)
    if p.startswith("A"):
        return datetime.date(y, 1, 1)
    return None
