"""REB R-ONE weekly apartment price index fetcher.

Source: Korea Real Estate Board (REB / 한국부동산원) R-ONE Open API, listed on
data.go.kr as service id 15134761 (Real Estate Statistics Inquiry Service).

Required env: ``IMDR_REB_API_KEY`` (free, registered through data.go.kr).

Series pulled — 4 indicators, all weekly, base 2026-02-02 = 100.0:
  REB.HOUSING.APT_SALE.LEVEL.KR_NAT     Nationwide apartment sale price index
  REB.HOUSING.APT_SALE.LEVEL.KR_SEOUL   Seoul apartment sale price index
  REB.HOUSING.APT_JEONSE.LEVEL.KR_NAT   Nationwide apartment jeonse price index
  REB.HOUSING.APT_JEONSE.LEVEL.KR_SEOUL Seoul apartment jeonse price index

History: 2012-05-07 → present (pilot survey from 2012-05-07; series transferred
from KB Kookmin Bank to REB on 2013-01-01).

The REB endpoint requires ``STATBL_ID``, ``DTACYCLE_CD``, and the two
``WRTTIME_IDTFR_*`` date params, but in practice the date filter is ignored
server-side. ``CLS_ID`` filtering DOES work — passing the region code returns
just the nationwide / Seoul series (~732 rows each), so one paged call per
(STATBL_ID, CLS_ID) is enough for full history. We pin ``pSize=2000`` to fit
a 14-year × weekly series in a single page.

Usage:
    C:/Users/adoshi/.conda/envs/imdr/python.exe scripts/econ/reb/reb_housing.py
    C:/Users/adoshi/.conda/envs/imdr/python.exe scripts/econ/reb/reb_housing.py --no-parquet
    C:/Users/adoshi/.conda/envs/imdr/python.exe scripts/econ/reb/reb_housing.py --since 2020-01-01
    python -m scripts.econ.reb.reb_housing
"""

from __future__ import annotations

import datetime
import os
from pathlib import Path

import requests

from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc
_REB_DATA_URL = "https://www.reb.or.kr/r-one/openapi/SttsApiTblData.do"

# Repo root: scripts/econ/reb/reb_housing.py -> parents[3]
_REPO_ROOT = Path(__file__).resolve().parents[3]

# (STATBL_ID, series_kind, item_id_filter_or_None)
_TABLES: dict[str, tuple[str, int]] = {
    "sale":   ("T244183132827305", 10001),   # (주) 매매가격지수, ITM_ID=10001 (지수)
    "jeonse": ("T247713133046872", 10001),   # (주) 전세가격지수, ITM_ID=10001 (지수)
}

# CLS_ID (REB region classification) → (region_suffix, display_suffix)
_REGIONS: dict[int, tuple[str, str]] = {
    50001: ("KR_NAT",   "Nationwide"),
    50008: ("KR_SEOUL", "Seoul"),
}

# (kind, region_id) → (imdr_code, display_name, bbg_ticker | None)
#
# Suffix ``.REB_DIRECT`` distinguishes these from the KOSIS-mirror rows of
# the same underlying series. KOSIS only goes back to 2021-07; REB-direct
# goes back to 2012-05-07. Both load into econ.dim_indicator, with
# coexistence enforced via the suffix (UNIQUE constraint on imdr_code).
_SERIES_META: dict[tuple[str, int], tuple[str, str, str | None]] = {
    ("sale", 50001):   ("REB.HOUSING.APT_SALE.LEVEL.KR_NAT.REB_DIRECT",
                        "Korea Nationwide Apartment Sale Price Index (REB-direct R-ONE OpenAPI, weekly, 2026-02-02=100)",
                        None),
    ("sale", 50008):   ("REB.HOUSING.APT_SALE.LEVEL.KR_SEOUL.REB_DIRECT",
                        "Korea Seoul Apartment Sale Price Index (REB-direct R-ONE OpenAPI, weekly, 2026-02-02=100)",
                        None),
    ("jeonse", 50001): ("REB.HOUSING.APT_JEONSE.LEVEL.KR_NAT.REB_DIRECT",
                        "Korea Nationwide Apartment Jeonse Price Index (REB-direct R-ONE OpenAPI, weekly, 2026-02-02=100)",
                        None),
    ("jeonse", 50008): ("REB.HOUSING.APT_JEONSE.LEVEL.KR_SEOUL.REB_DIRECT",
                        "Korea Seoul Apartment Jeonse Price Index (REB-direct R-ONE OpenAPI, weekly, 2026-02-02=100)",
                        None),
}

_PAGE_SIZE = 1000  # REB hard cap (ERROR-336 if exceeded); 14yr × 52wk ≈ 730 rows fits


def _load_key() -> str:
    """Read IMDR_REB_API_KEY from os env or fall back to .env file."""
    key = os.environ.get("IMDR_REB_API_KEY")
    if key:
        return key
    env_path = _REPO_ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("IMDR_REB_API_KEY="):
                return line.split("=", 1)[1].strip()
    raise RuntimeError(
        "IMDR_REB_API_KEY not set. Add it to .env or export it."
    )


def _fetch_series(
    key: str,
    statbl_id: str,
    cls_id: int,
    itm_id: int,
    *,
    timeout: int = 60,
) -> list[dict]:
    """Fetch one (statbl_id, cls_id) page from REB and return its rows.

    The date filter is honoured by the API only for required-param validation;
    the server ignores its value and always returns the full series for the
    given region. We still send the dates so the endpoint doesn't 400.
    """
    params = {
        "KEY": key,
        "STATBL_ID": statbl_id,
        "DTACYCLE_CD": "WK",
        "WRTTIME_IDTFR_STARTDT": "20120101",
        "WRTTIME_IDTFR_ENDDT": datetime.date.today().strftime("%Y%m%d"),
        "CLS_ID": cls_id,
        "Type": "json",
        "pIndex": 1,
        "pSize": _PAGE_SIZE,
    }
    resp = requests.get(_REB_DATA_URL, params=params, timeout=timeout)
    resp.raise_for_status()
    payload = resp.json()
    if "SttsApiTblData" not in payload:
        # API returns flat {RESULT: {CODE, MESSAGE}} on error
        result = payload.get("RESULT", {})
        raise RuntimeError(
            f"REB API error for {statbl_id}/{cls_id}: "
            f"{result.get('CODE')} {result.get('MESSAGE')}"
        )
    blocks = payload["SttsApiTblData"]
    head = blocks[0]["head"]
    total = head[0]["list_total_count"]
    code = head[1]["RESULT"]["CODE"]
    if code != "INFO-000":
        raise RuntimeError(
            f"REB API non-OK code for {statbl_id}/{cls_id}: "
            f"{code} {head[1]['RESULT']['MESSAGE']}"
        )
    rows = blocks[1].get("row", []) if len(blocks) > 1 else []
    if itm_id is not None:
        rows = [r for r in rows if r.get("ITM_ID") == itm_id]
    if len(rows) >= _PAGE_SIZE:
        # Hit the per-call cap — would need pagination across pIndex pages.
        # For the 4-series-per-region cuts we expect <750 rows; flag loudly.
        raise RuntimeError(
            f"REB returned {len(rows)} rows for {statbl_id}/{cls_id} — "
            f"hit pSize={_PAGE_SIZE} cap (declared total={total}). "
            f"Add pIndex paging."
        )
    return rows


def _parse_obs_date(row: dict) -> datetime.date | None:
    """Parse WRTTIME_DESC ('YYYY-MM-DD') into a date object."""
    raw = row.get("WRTTIME_DESC")
    if not raw:
        return None
    try:
        return datetime.date.fromisoformat(raw)
    except (TypeError, ValueError):
        return None


def _parse_value(row: dict) -> float | None:
    raw = row.get("DTA_VAL")
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def run_fetch(
    since: str | None,
    until: str | None,
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    """Pull all 4 series and return indicator + observation rows."""
    key = _load_key()
    since_dt = datetime.date.fromisoformat(since) if since else None
    until_dt = datetime.date.fromisoformat(until) if until else None
    now = datetime.datetime.now(UTC)

    indicators: list[IndicatorRow] = []
    observations: list[ObservationRow] = []

    for kind, (statbl_id, itm_id) in _TABLES.items():
        for cls_id in _REGIONS:
            imdr_code, display_name, bbg = _SERIES_META[(kind, cls_id)]
            print(f"  Fetching {imdr_code} ...", end=" ", flush=True)
            rows = _fetch_series(key, statbl_id, cls_id, itm_id)
            print(f"{len(rows)} rows")

            indicators.append(IndicatorRow(
                imdr_code=imdr_code,
                vendor_name="REB",
                source_code=f"{statbl_id}/CLS_ID={cls_id}/ITM_ID={itm_id}",
                display_name=display_name,
                unit="index",
                frequency="WEEKLY",
                country_iso="KR",
                category="housing",
                is_seasonally_adjusted=False,
                bbg_ticker=bbg,
            ))

            for r in rows:
                obs_date = _parse_obs_date(r)
                if obs_date is None:
                    continue
                if since_dt and obs_date < since_dt:
                    continue
                if until_dt and obs_date > until_dt:
                    continue
                observations.append(ObservationRow(
                    imdr_code=imdr_code,
                    obs_date=obs_date,
                    vintage=0,
                    release_date=now,
                    value=_parse_value(r),
                    ingested_at=now,
                ))

    return indicators, observations


def main() -> int:
    return run_main(
        vendor="reb",
        topic="housing",
        fetch_fn=run_fetch,
        description=__doc__.splitlines()[0] if __doc__ else "",
    )


if __name__ == "__main__":
    import sys
    sys.exit(main())
