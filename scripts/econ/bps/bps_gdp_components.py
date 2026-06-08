"""BPS Indonesia GDP component decomposition fetcher.

Source: BPS Web API subject 11 (Industrial Origin) + subject 169 (Expenditure).
17 supply-side sectors (A-Q, var=104 YoY %) and 7 demand-side components
(PCE/NPISH/Govt/GFCF/Inventory/Exports/Imports, var=108 YoY %). Cells: 1.1-1.4.
"""

from __future__ import annotations

import datetime

from imdr.domains.econ.bps_http import all_th_ids, bps_fetch_data_chunked, make_session, turtahun_to_period
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

_INDUSTRIAL_SECTORS: dict[int, tuple[str, str]] = {
    11000: ("AGRI",        "Agriculture, Forestry & Fishing"),
    12000: ("MINING",      "Mining & Quarrying"),
    13000: ("MFG",         "Manufacturing"),
    14000: ("ELEC_GAS",    "Electricity & Gas"),
    15000: ("WATER",       "Water, Waste, Recycling"),
    16000: ("CONSTR",      "Construction"),
    17000: ("TRADE",       "Wholesale & Retail Trade"),
    18000: ("TRANSPORT",   "Transportation & Storage"),
    19000: ("ACCOM",       "Accommodation & Food Service"),
    20000: ("INFO_COMM",   "Information & Communication"),
    21000: ("FINANCE",     "Financial & Insurance Services"),
    22000: ("REALESTATE",  "Real Estate"),
    23000: ("BIZ_SVC",     "Business Services (M,N)"),
    24000: ("PUBADMIN",    "Public Administration & Defence"),
    25000: ("EDUCATION",   "Education Services"),
    26000: ("HEALTH",      "Health & Social Services"),
    27000: ("OTHER_SVC",   "Other Services (R,S,T,U)"),
}

_EXPENDITURE_COMPONENTS: dict[int, tuple[str, str]] = {
    100: ("PCE",       "Private Consumption (PCE)"),
    200: ("NPISH",     "NPISH Consumption"),
    300: ("GOV_C",     "Government Consumption"),
    400: ("GFCF",      "Gross Fixed Capital Formation"),
    500: ("INVENTORY", "Change in Inventories"),
    600: ("EXPORTS",   "Exports of Goods & Services"),
    700: ("IMPORTS",   "Imports of Goods & Services"),
}


def _build_targets() -> list[tuple[int, int, int, str, str, str]]:
    targets: list[tuple[int, int, int, str, str, str]] = []
    for vervar_id, (suffix, label) in _INDUSTRIAL_SECTORS.items():
        targets.append((
            104, vervar_id, 5,
            f"BPS.GDP.IND_{suffix}.YOY.ID",
            f"Indonesia GDP YoY growth — {label} (supply-side, BPS, %)",
            "pct",
        ))
    for vervar_id, (suffix, label) in _EXPENDITURE_COMPONENTS.items():
        targets.append((
            108, vervar_id, 5,
            f"BPS.GDP.EXP_{suffix}.YOY.ID",
            f"Indonesia GDP YoY growth — {label} (demand-side, BPS, %)",
            "pct",
        ))
    return targets


_TARGETS = _build_targets()


def run_fetch(
    since: str | None,
    until: str | None,
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    session = make_session()
    since_dt = datetime.date.fromisoformat(since) if since else None
    until_dt = datetime.date.fromisoformat(until) if until else None
    now = datetime.datetime.now(UTC)
    data_cache: dict[int, list[dict]] = {}
    indicators: list[IndicatorRow] = []
    observations: list[ObservationRow] = []

    for var_id, vervar_id, turvar_id, imdr_code, display, unit in _TARGETS:
        if var_id not in data_cache:
            print(f"  fetching var={var_id} ...", end=" ", flush=True)
            th_ids = all_th_ids(session, var_id)
            data_cache[var_id] = bps_fetch_data_chunked(
                session, var=var_id, th_ids=th_ids, domain="0000", lang="ind",
            )
            print(f"{len(data_cache[var_id])} rows cached")
        rows = data_cache[var_id]
        filtered = [r for r in rows
                    if r["vervar_id"] == vervar_id and r["turvar_id"] == turvar_id]
        if not filtered:
            print(f"    {imdr_code}: no rows after filter")
            continue

        indicator = IndicatorRow(
            imdr_code=imdr_code, vendor_name="BPS",
            source_code=f"BPS/var={var_id}/vervar={vervar_id}/turvar={turvar_id}",
            display_name=display, unit=unit, frequency="QUARTERLY",
            country_iso="ID", category="gdp",
            is_seasonally_adjusted=False, bbg_ticker=None,
        )
        obs_emitted = 0
        for r in filtered:
            period = turtahun_to_period(r["turtahun_id"])
            if period is None or period[1] != "QUARTERLY":
                continue
            month, _f = period
            try:
                year = int(r["tahun_label"].strip())
            except (TypeError, ValueError):
                continue
            obs_date = datetime.date(year, month, 1)
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
            continue
        indicators.append(indicator)
    return indicators, observations


def main() -> int:
    return run_main(vendor="bps", topic="gdp_components",
                    fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "")


if __name__ == "__main__":
    import sys; sys.exit(main())
