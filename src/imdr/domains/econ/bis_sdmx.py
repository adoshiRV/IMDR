"""SDMX-JSON helper for BIS Data Portal fetches.

BIS publishes data via SDMX 2.1 at:
    https://stats.bis.org/api/v2/data/dataflow/BIS/{flow_id}/{version}/{key}

Public, no auth, polite throttle. Response is SDMX-JSON (vendor mime
type ``application/vnd.sdmx.data+json;version=1.0.0``).

Useful BIS dataflows for cross-country coverage:
  WS_EER         Effective Exchange Rates (NEER + REER)
  WS_DSR         Debt Service Ratios (Households / NFC / Private)
  WS_CREDIT_GAP  Credit-to-GDP ratio / trend / gap
  WS_CBPOL       Central Bank Policy Rates
"""

from __future__ import annotations

import datetime
import json
import time
import urllib.request

_BASE = "https://stats.bis.org/api/v2/data/dataflow/BIS"
_HEADERS = {
    "Accept": "application/vnd.sdmx.data+json;version=1.0.0",
    "User-Agent": "Mozilla/5.0 IMDR-bis",
}
_THROTTLE_S = 1.0


def bis_fetch_series(
    flow_id: str,
    version: str,
    key: str,
    *,
    timeout: int = 60,
) -> list[tuple[str, float | None]]:
    """Fetch a single BIS series and return [(period_str, value), ...].

    Period string formats by frequency:
      D → 'YYYY-MM-DD'
      M → 'YYYY-MM'
      Q → 'YYYY-Qn'
      A → 'YYYY'

    Returns empty list if the response has no series. Raises RuntimeError
    on HTTP error or unparseable payload.
    """
    url = f"{_BASE}/{flow_id}/{version}/{key}"
    time.sleep(_THROTTLE_S)
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read())

    datasets = payload.get("data", {}).get("dataSets") or []
    if not datasets:
        return []
    series = datasets[0].get("series") or {}
    if not series:
        return []
    _series_key, ser = next(iter(series.items()))
    observations = ser.get("observations") or {}
    if not observations:
        return []

    obs_dims = (
        payload.get("data", {})
        .get("structure", {})
        .get("dimensions", {})
        .get("observation")
        or []
    )
    if not obs_dims:
        raise RuntimeError(f"BIS {flow_id} {key}: missing observation dimensions")
    time_values = obs_dims[0].get("values") or []

    out: list[tuple[str, float | None]] = []
    for obs_pos_str, obs_arr in observations.items():
        obs_pos = int(obs_pos_str)
        if obs_pos >= len(time_values):
            continue
        period = time_values[obs_pos].get("id", "")
        val = obs_arr[0] if obs_arr else None
        try:
            val_f = float(val) if val is not None else None
        except (TypeError, ValueError):
            val_f = None
        out.append((period, val_f))
    return sorted(out, key=lambda r: r[0])


def parse_bis_period(period: str) -> datetime.date | None:
    """Parse a BIS period string ('2026-Q1', '2026-04', '2026-04-30') to date.

    Returns the period-START date (Q1 → Jan 1, Q2 → Apr 1, etc.). Returns
    None on unrecognised format.
    """
    if not period:
        return None
    p = period.strip()
    try:
        if "-Q" in p:
            year_s, q_s = p.split("-Q", 1)
            year = int(year_s)
            q = int(q_s)
            if 1 <= q <= 4:
                return datetime.date(year, (q - 1) * 3 + 1, 1)
            return None
        parts = p.split("-")
        if len(parts) == 3:
            return datetime.date(int(parts[0]), int(parts[1]), int(parts[2]))
        if len(parts) == 2:
            return datetime.date(int(parts[0]), int(parts[1]), 1)
        if len(parts) == 1:
            return datetime.date(int(parts[0]), 1, 1)
    except (TypeError, ValueError):
        return None
    return None
