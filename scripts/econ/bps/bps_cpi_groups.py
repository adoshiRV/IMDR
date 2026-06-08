"""BPS Indonesia CPI 11-group decomposition fetcher.

Source: BPS Web API subject 3 (Consumer Prices Indices). Headline national-aggregate
inflation YoY by 11 COICOP-aligned kelompok (2022=100 base, post-2024 series) at the
INDONESIA aggregate level (vervar_id=151). Cell: 2.4 CPI Pressure (group decomposition).
"""

from __future__ import annotations

import datetime

from imdr.domains.econ.bps_http import all_th_ids, bps_fetch_data_chunked, make_session
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc
_NATIONAL_VERVAR_LABEL = "INDONESIA"
_MONTHS_TURTAHUN = set(range(1, 13))

# (var_id, kelompok_total_turvar_id, imdr_code, display)
_TARGETS: list[tuple[int, int, str, str]] = [
    (2250, 1551, "BPS.CPI.GROUP01_FOOD.YOY.ID",
     "Indonesia CPI YoY — Food, Beverages & Tobacco (2022=100) (BPS)"),
    (2251, 1555, "BPS.CPI.GROUP02_CLOTHING.YOY.ID",
     "Indonesia CPI YoY — Clothing & Footwear (2022=100) (BPS)"),
    (2252, 1558, "BPS.CPI.GROUP03_HOUSING.YOY.ID",
     "Indonesia CPI YoY — Housing, Water, Electricity & Fuel (2022=100) (BPS)"),
    (2253, 1563, "BPS.CPI.GROUP04_HOUSEHOLD.YOY.ID",
     "Indonesia CPI YoY — Furnishings, Equipment & Routine Maintenance (2022=100) (BPS)"),
    (2254, 1570, "BPS.CPI.GROUP05_HEALTH.YOY.ID",
     "Indonesia CPI YoY — Health (2022=100) (BPS)"),
    (2255, 1575, "BPS.CPI.GROUP06_TRANSPORT.YOY.ID",
     "Indonesia CPI YoY — Transportation (2022=100) (BPS)"),
    (2256, 1580, "BPS.CPI.GROUP07_INFOCOMM.YOY.ID",
     "Indonesia CPI YoY — Information, Communication & Financial Services (2022=100) (BPS)"),
    (2257, 1585, "BPS.CPI.GROUP08_RECREATION.YOY.ID",
     "Indonesia CPI YoY — Recreation, Sport & Culture (2022=100) (BPS)"),
    (2258, 1592, "BPS.CPI.GROUP09_EDUCATION.YOY.ID",
     "Indonesia CPI YoY — Education (2022=100) (BPS)"),
    (2259, 1597, "BPS.CPI.GROUP10_RESTAURANTS.YOY.ID",
     "Indonesia CPI YoY — Restaurants & Food Service (2022=100) (BPS)"),
    (2260, 1599, "BPS.CPI.GROUP11_PERSONAL.YOY.ID",
     "Indonesia CPI YoY — Personal Care & Other Services (2022=100) (BPS)"),
]


def run_fetch(
    since: str | None,
    until: str | None,
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    session = make_session()
    since_dt = datetime.date.fromisoformat(since) if since else None
    until_dt = datetime.date.fromisoformat(until) if until else None
    now = datetime.datetime.now(UTC)
    indicators: list[IndicatorRow] = []
    observations: list[ObservationRow] = []

    for var_id, turvar_id, imdr_code, display in _TARGETS:
        print(f"  var={var_id} turvar={turvar_id} {imdr_code} ...", end=" ", flush=True)
        th_ids = all_th_ids(session, var_id)
        rows = bps_fetch_data_chunked(
            session, var=var_id, th_ids=th_ids, domain="0000", lang="ind",
        )
        national = [r for r in rows
                    if r["vervar_label"].strip().upper() == _NATIONAL_VERVAR_LABEL
                    and r["turvar_id"] == turvar_id
                    and r["turtahun_id"] in _MONTHS_TURTAHUN]
        if not national:
            print("no national rows — skipping")
            continue

        indicator = IndicatorRow(
            imdr_code=imdr_code, vendor_name="BPS",
            source_code=f"BPS/subject=3/var={var_id}/vervar=INDONESIA/turvar={turvar_id}",
            display_name=display, unit="pct", frequency="MONTHLY",
            country_iso="ID", category="cpi",
            is_seasonally_adjusted=False, bbg_ticker=None,
        )
        obs_emitted = 0
        for r in national:
            try:
                year = int(r["tahun_label"].strip())
            except (TypeError, ValueError):
                continue
            obs_date = datetime.date(year, r["turtahun_id"], 1)
            if since_dt and obs_date < since_dt:
                continue
            if until_dt and obs_date > until_dt:
                continue
            try:
                value = float(r["value"]) if r["value"] is not None else None
            except (TypeError, ValueError):
                value = None
            observations.append(ObservationRow(
                imdr_code=imdr_code, obs_date=obs_date, vintage=0,
                release_date=now, value=value, ingested_at=now,
            ))
            obs_emitted += 1
        if obs_emitted == 0:
            print("no obs")
            continue
        indicators.append(indicator)
        print(f"{obs_emitted} obs")
    return indicators, observations


def main() -> int:
    return run_main(vendor="bps", topic="cpi_groups",
                    fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "")


if __name__ == "__main__":
    import sys; sys.exit(main())
