"""BI Indonesia Retail Sales Survey fetcher (SPE — spe.zip, Tabel 1).

Real Sales Index (Indeks Penjualan Riil) — INDEKS TOTAL + 8 category breakdowns.
Monthly, 2012-01 onward. Base 2010=100. Cell mapping: 1.1 Private Demand.
"""

from __future__ import annotations

import datetime

from imdr.domains.econ.bi_survey import download_survey_zip, parse_survey_rows
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

_TARGETS: list[tuple[int, str, str]] = [
    (13, "BI.RETAIL_SALES.TOTAL.LEVEL.ID",
     "Indonesia Real Retail Sales Index — INDEKS TOTAL (BI SPE, index)"),
    (5,  "BI.RETAIL_SALES.AUTO_PARTS.LEVEL.ID",
     "Indonesia Real Retail Sales — Spare Parts & Accessories (BI SPE, index)"),
    (6,  "BI.RETAIL_SALES.FOOD_BEV_TOB.LEVEL.ID",
     "Indonesia Real Retail Sales — Food, Beverages & Tobacco (BI SPE, index)"),
    (7,  "BI.RETAIL_SALES.FUEL.LEVEL.ID",
     "Indonesia Real Retail Sales — Vehicle Fuel (BI SPE, index)"),
    (8,  "BI.RETAIL_SALES.INFO_COMM.LEVEL.ID",
     "Indonesia Real Retail Sales — Info-Comm Equipment (BI SPE, index)"),
    (9,  "BI.RETAIL_SALES.HOUSEHOLD.LEVEL.ID",
     "Indonesia Real Retail Sales — Other Household Equipment (BI SPE, index)"),
    (10, "BI.RETAIL_SALES.CULT_REC.LEVEL.ID",
     "Indonesia Real Retail Sales — Culture & Recreation (BI SPE, index)"),
    (11, "BI.RETAIL_SALES.OTHER.LEVEL.ID",
     "Indonesia Real Retail Sales — Other Goods (BI SPE, index)"),
    (12, "BI.RETAIL_SALES.CLOTHING.LEVEL.ID",
     "Indonesia Real Retail Sales — Clothing/Sandang (BI SPE, index)"),
]


def run_fetch(since, until):
    since_dt = datetime.date.fromisoformat(since) if since else None
    until_dt = datetime.date.fromisoformat(until) if until else None
    now = datetime.datetime.now(UTC)

    print("  downloading spe.zip ...", end=" ", flush=True)
    path = download_survey_zip("spe")
    print(path.name)
    rows_data = parse_survey_rows(
        path, "Tabel 1",
        rows=[r for r, _, _ in _TARGETS],
        year_row=3, month_row=4, first_data_col=1,
    )

    indicators: list[IndicatorRow] = []
    observations: list[ObservationRow] = []
    for row_idx, imdr_code, display in _TARGETS:
        series = rows_data.get(row_idx) or []
        if not series:
            print(f"    {imdr_code}: row {row_idx} empty — skipping")
            continue
        indicator = IndicatorRow(
            imdr_code=imdr_code, vendor_name="BI",
            source_code=f"BI/SPE/Tabel 1/row={row_idx}",
            display_name=display, unit="index", frequency="MONTHLY",
            country_iso="ID", category="other",
            is_seasonally_adjusted=False, bbg_ticker=None,
        )
        obs_emitted = 0
        for obs_date, value in series:
            if value is None:
                continue
            if since_dt and obs_date < since_dt:
                continue
            if until_dt and obs_date > until_dt:
                continue
            observations.append(ObservationRow(
                imdr_code=imdr_code, obs_date=obs_date, vintage=0,
                release_date=now, value=value, ingested_at=now,
            ))
            obs_emitted += 1
        indicators.append(indicator)
        print(f"    {imdr_code}: {obs_emitted} obs")
    return indicators, observations


def main() -> int:
    return run_main(vendor="bi", topic="retail_sales",
                    fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "")

if __name__ == "__main__":
    import sys; sys.exit(main())
