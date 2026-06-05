"""KOSIS-mirror weekly apartment price index fetcher.

Same 4 indicators as ``scripts.econ.reb.reb_housing``, but pulled via
KOSIS's mirror of REB's R-ONE catalogue (orgId=408). Used for cross-check
against the REB-direct path and as a fallback if the REB key is unavailable.

Series — identical imdr_codes as the REB fetcher, different vendor:
  REB.HOUSING.APT_SALE.LEVEL.KR_NAT
  REB.HOUSING.APT_SALE.LEVEL.KR_SEOUL
  REB.HOUSING.APT_JEONSE.LEVEL.KR_NAT
  REB.HOUSING.APT_JEONSE.LEVEL.KR_SEOUL

KOSIS mirrors the same underlying REB tables under different tblIds with a
re-based index (KOSIS base 2025-03-31=100; REB base 2026-02-02=100). YoY %
change is identical between paths; absolute levels are offset.

KOSIS history coverage starts ~2021-07 (probed; earlier periods return
err=30 데이터가 존재하지 않습니다). For the full 2012-05-07 → present window
seen in the chart, use the REB-direct fetcher instead.

TLS 1.2 pinning + connection-reset retry are inherited from
`imdr.domains.econ.kosis_http.fetch_kosis_table` -- this fetcher does not
roll its own HTTP layer.

Usage:
    C:/Users/adoshi/.conda/envs/imdr/python.exe scripts/econ/kosis/kosis_reb_housing.py
    C:/Users/adoshi/.conda/envs/imdr/python.exe scripts/econ/kosis/kosis_reb_housing.py --no-parquet
    python -m scripts.econ.kosis.kosis_reb_housing
"""

from __future__ import annotations

import datetime

from imdr.domains.econ.kosis_http import fetch_kosis_table, make_session
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

# (kind, objL1) → (imdr_code, display_name, bbg)
_SERIES_META: dict[tuple[str, str], tuple[str, str, str | None]] = {
    ("sale", "a0"):   ("REB.HOUSING.APT_SALE.LEVEL.KR_NAT",
                       "Korea Nationwide Apartment Sale Price Index (REB via KOSIS, weekly)",
                       None),
    ("sale", "a7"):   ("REB.HOUSING.APT_SALE.LEVEL.KR_SEOUL",
                       "Korea Seoul Apartment Sale Price Index (REB via KOSIS, weekly)",
                       None),
    ("jeonse", "a0"): ("REB.HOUSING.APT_JEONSE.LEVEL.KR_NAT",
                       "Korea Nationwide Apartment Jeonse Price Index (REB via KOSIS, weekly)",
                       None),
    ("jeonse", "a7"): ("REB.HOUSING.APT_JEONSE.LEVEL.KR_SEOUL",
                       "Korea Seoul Apartment Jeonse Price Index (REB via KOSIS, weekly)",
                       None),
}

# KOSIS REB-mirror tables — level series (item code 매매가격지수 / 전세가격지수).
_TABLES: dict[str, str] = {
    "sale":   "DT_304004_WEEK_002_A",   # 주간 아파트 매매가격지수 (level)
    "jeonse": "DT_304004_WEEK_004_A",   # 주간 아파트 전세가격지수 (level)
}


def _parse_obs_date(row: dict) -> datetime.date | None:
    """PRD_DE is YYYYMMDD (week-end date for REB weekly series)."""
    raw = row.get("PRD_DE")
    if not raw or len(raw) != 8:
        return None
    try:
        return datetime.date(int(raw[:4]), int(raw[4:6]), int(raw[6:8]))
    except (TypeError, ValueError):
        return None


def _parse_value(row: dict) -> float | None:
    raw = row.get("DT")
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
    session = make_session()
    since_dt = datetime.date.fromisoformat(since) if since else None
    until_dt = datetime.date.fromisoformat(until) if until else None
    now = datetime.datetime.now(UTC)
    end = datetime.date.today().strftime("%Y%m%d")

    indicators: list[IndicatorRow] = []
    observations: list[ObservationRow] = []

    for kind, tbl_id in _TABLES.items():
        for obj_l1 in ("a0", "a7"):
            imdr_code, display_name, bbg = _SERIES_META[(kind, obj_l1)]
            print(f"  Fetching {imdr_code} ...", end=" ", flush=True)
            # KOSIS treats prdSe='M' as weekly for the REB-mirror tables --
            # PRD_DE comes back as YYYYMMDD week-anchored regardless.
            rows = fetch_kosis_table(
                session,
                org_id="408",
                tbl_id=tbl_id,
                obj_l1=obj_l1,
                itm_id="ALL",
                prd_se="M",
                start_prd_de="20200101",
                end_prd_de=end,
            )
            print(f"{len(rows)} rows")

            indicators.append(IndicatorRow(
                imdr_code=imdr_code,
                vendor_name="KOSIS",
                source_code=f"408/{tbl_id}/{obj_l1}",
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
        vendor="kosis",
        topic="reb_housing",
        fetch_fn=run_fetch,
        description=__doc__.splitlines()[0] if __doc__ else "",
    )


if __name__ == "__main__":
    import sys
    sys.exit(main())
