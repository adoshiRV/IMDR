"""KOSIS / KOSTAT Retail Sales Index fetcher (DT_1K41013).

Source: Statistics Korea (KOSTAT, orgId=101), 소매업태별 판매액지수 —
Retail Sales Index by type, base 2020=100, monthly.

The table covers 19 retail cuts (7 top-level + 12 sub-categories). We pull
the 7 top-level types × 2 indices (Value index + Seasonally Adjusted index)
= 14 indicators. Sub-categories (A41/A42 supermarket split, A61/A62 car/
fuel split, A71-A74 specialised stores) are skipped — extensible later.

Top-level cuts:
  A1  Department Stores
  A2  Large discount stores
  A3  Duty-free shops
  A4  Supermarkets and other non-specialised retail
  A5  Convenience stores
  A6  Passenger cars ＆ Fuel stores
  A7  Specialised stores

Indices kept (2020=100 base):
  T1  Value index (nominal)
  T3  Seasonally-adjusted index
  (T2 Volume index dropped — Value + SA cover the headline analysis case)

Cell mapping: 1.1 Private Demand (consumption-side) → ⚠ → ✅.

Usage:
    C:/Users/adoshi/.conda/envs/imdr/python.exe scripts/econ/kosis/kosis_retail.py
    python -m scripts.econ.kosis.kosis_retail
"""

from __future__ import annotations

import datetime

from imdr.domains.econ.kosis_http import fetch_kosis_table, make_session, parse_kosis_period
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

# C1 → (suffix, display)
_CUTS: dict[str, tuple[str, str]] = {
    "A1": ("DEPT_STORES",     "Department Stores"),
    "A2": ("DISCOUNT",        "Large discount stores"),
    "A3": ("DUTY_FREE",       "Duty-free shops"),
    "A4": ("SUPERMARKET",     "Supermarkets and other non-specialised retail"),
    "A5": ("CONVENIENCE",     "Convenience stores"),
    "A6": ("CARS_FUEL",       "Passenger cars and fuel stores"),
    "A7": ("SPECIALISED",     "Specialised stores"),
}

# ITM_ID → (suffix, display)
_ITEMS: dict[str, tuple[str, str]] = {
    "T1": ("VALUE",  "Value index, 2020=100"),
    "T3": ("SA",     "Seasonally-adjusted index, 2020=100"),
}


def run_fetch(
    since: str | None,
    until: str | None,
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    session = make_session()
    since_dt = datetime.date.fromisoformat(since) if since else None
    until_dt = datetime.date.fromisoformat(until) if until else None
    now = datetime.datetime.now(UTC)

    print("  Fetching Retail Sales: DT_1K41013 (KOSTAT, orgId=101) ...", end=" ", flush=True)
    rows = fetch_kosis_table(
        session,
        org_id="101",
        tbl_id="DT_1K41013",
        obj_l1="ALL",
        itm_id="ALL",
        prd_se="M",
        start_prd_de="200001",
        end_prd_de=datetime.date.today().strftime("%Y%m"),
    )
    print(f"{len(rows)} rows")

    indicators: list[IndicatorRow] = []
    observations: list[ObservationRow] = []

    for c1_code, (cut_suffix, cut_display) in _CUTS.items():
        for itm_id, (item_suffix, item_display) in _ITEMS.items():
            sub = [r for r in rows if r.get("C1") == c1_code and r.get("ITM_ID") == itm_id]
            if not sub:
                continue
            imdr_code = f"KOSTAT.RETAIL.{cut_suffix}.{item_suffix}.KR"
            indicators.append(IndicatorRow(
                imdr_code=imdr_code,
                vendor_name="KOSIS",
                source_code=f"101/DT_1K41013/C1={c1_code}/ITM_ID={itm_id}",
                display_name=f"Korea Retail Sales — {cut_display}, {item_display} (KOSTAT)",
                unit="index",
                frequency="MONTHLY",
                country_iso="KR",
                category="gdp",
                is_seasonally_adjusted=(item_suffix == "SA"),
                bbg_ticker=None,
            ))
            for r in sub:
                ymd = parse_kosis_period(r.get("PRD_DE"), "M")
                if ymd is None:
                    continue
                obs_date = datetime.date(*ymd)
                if since_dt and obs_date < since_dt:
                    continue
                if until_dt and obs_date > until_dt:
                    continue
                try:
                    value = float(r["DT"]) if r.get("DT") not in (None, "") else None
                except (TypeError, ValueError):
                    value = None
                observations.append(ObservationRow(
                    imdr_code=imdr_code,
                    obs_date=obs_date,
                    vintage=0,
                    release_date=now,
                    value=value,
                    ingested_at=now,
                ))

    return indicators, observations


def main() -> int:
    return run_main(
        vendor="kosis",
        topic="retail",
        fetch_fn=run_fetch,
        description=__doc__.splitlines()[0] if __doc__ else "",
    )


if __name__ == "__main__":
    import sys
    sys.exit(main())
