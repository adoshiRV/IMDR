"""BI Indonesia SKDU macro-survey tables fetcher (T2/T5/T6).

Companion to bi_business_survey (T1). Pulls three macro-relevant SKDU tables:
T2 Capacity Utilization, T5 Selling Prices (SBT), T6 Inflation Expectations.
Quarterly. Cell mapping: 2.3 Domestic Costs + 2.2 Producer Prices.
"""

from __future__ import annotations

import datetime

from imdr.domains.econ.bi_survey import download_survey_zip, parse_survey_rows
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

_SECTORS: list[tuple[str, str]] = [
    ("AGRI",        "Agriculture, Forestry & Fishery"),
    ("MINING",      "Mining & Quarrying"),
    ("MFG",         "Manufacturing"),
    ("ELEC_GAS",    "Electricity & Gas"),
    ("WATER",       "Water Supply / Sewerage"),
    ("CONSTR",      "Construction"),
    ("TRADE",       "Wholesale & Retail Trade"),
    ("TRANSPORT",   "Transport & Storage"),
    ("ACCOM",       "Accommodation & Food Service"),
    ("INFO_COMM",   "Information & Communication"),
    ("FINANCE",     "Financial & Insurance Services"),
    ("REALESTATE",  "Real Estate"),
    ("BIZ_SVC",     "Business Services"),
    ("PUBADMIN",    "Public Administration & Defense"),
    ("EDUCATION",   "Education Services"),
    ("HEALTH",      "Health & Social Work"),
    ("OTHER_SVC",   "Other Services"),
]

_T2_ROWS: dict[str, int] = {
    "AGRI": 6, "MINING": 14, "MFG": 15, "ELEC_GAS": 30, "WATER": 31, "TOTAL": 32,
}
_T5_ROWS: dict[str, int] = {
    "AGRI": 6, "MINING": 14, "MFG": 15, "ELEC_GAS": 30, "WATER": 31,
    "CONSTR": 32, "TRADE": 33, "TRANSPORT": 36, "ACCOM": 37,
    "INFO_COMM": 40, "FINANCE": 41, "REALESTATE": 46, "BIZ_SVC": 47,
    "PUBADMIN": 48, "EDUCATION": 49, "HEALTH": 50, "OTHER_SVC": 51,
    "TOTAL": 52,
}
_T6_ROWS: dict[str, int] = {
    "AGRI": 7, "MINING": 8, "MFG": 9, "ELEC_GAS": 10, "WATER": 11,
    "CONSTR": 12, "TRADE": 13, "TRANSPORT": 14, "ACCOM": 15,
    "INFO_COMM": 16, "FINANCE": 17, "REALESTATE": 18, "BIZ_SVC": 19,
    "PUBADMIN": 20, "EDUCATION": 21, "HEALTH": 22, "OTHER_SVC": 23,
    "TOTAL": 24,
}

# Each tuple: (table_num, sheet, year_row, month_row, first_data_col, row_map,
#              prefix, suffix, unit, category, display_template)
_TABLES = [
    ("T2", "T2 Kapasitas Produksi",  4, 5, 4, _T2_ROWS, "BI.CAP_UTIL",    "LEVEL", "pct", "sentiment",
     "Indonesia capacity utilization — {label} (BI SKDU T2, %)"),
    ("T5", "T5 Harga Jual",          4, 5, 4, _T5_ROWS, "BI.SELL_PRICES", "SBT",   "pct", "sentiment",
     "Indonesia selling prices SBT — {label} (BI SKDU T5, Weighted Net Balance %)"),
    ("T6", "T6 Perkiraan Inflasi",   4, 5, 3, _T6_ROWS, "BI.INFL_EXP",    "LEVEL", "pct", "cpi",
     "Indonesia expected inflation — {label} (BI SKDU T6, % YoY)"),
]
_LABEL_OVERRIDES = {"TOTAL": "TOTAL (all sectors)"}


def run_fetch(since, until):
    since_dt = datetime.date.fromisoformat(since) if since else None
    until_dt = datetime.date.fromisoformat(until) if until else None
    now = datetime.datetime.now(UTC)

    print("  downloading SKDU.zip ...", end=" ", flush=True)
    path = download_survey_zip("SKDU")
    print(path.name)

    sector_label = dict(_SECTORS)
    sector_label.update(_LABEL_OVERRIDES)

    indicators: list[IndicatorRow] = []
    observations: list[ObservationRow] = []

    for tnum, sheet, yr_row, mo_row, first_col, row_map, prefix, suffix, unit, cat, tmpl in _TABLES:
        rows_data = parse_survey_rows(
            path, sheet,
            rows=list(row_map.values()),
            year_row=yr_row, month_row=mo_row, first_data_col=first_col,
        )
        for sector, row_idx in row_map.items():
            series = rows_data.get(row_idx) or []
            if not series:
                continue
            label = sector_label.get(sector, sector)
            imdr_code = f"{prefix}.{sector}.{suffix}.ID"
            indicator = IndicatorRow(
                imdr_code=imdr_code, vendor_name="BI",
                source_code=f"BI/SKDU/{sheet}/row={row_idx}",
                display_name=tmpl.format(label=label),
                unit=unit, frequency="QUARTERLY",
                country_iso="ID", category=cat,
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
            if obs_emitted == 0:
                continue
            indicators.append(indicator)
            print(f"    {imdr_code}: {obs_emitted} obs")
    return indicators, observations


def main() -> int:
    return run_main(vendor="bi", topic="skdu_macro",
                    fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "")

if __name__ == "__main__":
    import sys; sys.exit(main())
