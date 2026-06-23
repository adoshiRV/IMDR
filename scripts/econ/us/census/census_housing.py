"""Census New Residential Construction fetcher — cell 1.1 housing leg.

Pulls housing starts and building permits (total + single-family) from the
Census EITS resconst program (New Residential Construction / C20 release).
Filters to geo_level_code='US' (national) and seasonally_adj='yes'. Values
are in seasonally adjusted annual rate (thousands of units).

Series produced:
  CENSUS.HOUSING.STARTS_TOTAL_SA.US   — total starts, SAAR (thousands)
  CENSUS.HOUSING.STARTS_SF_SA.US      — single-family starts, SAAR (thousands)
  CENSUS.HOUSING.PERMITS_TOTAL_SA.US  — total permits, SAAR (thousands)
  CENSUS.HOUSING.PERMITS_SF_SA.US     — single-family permits, SAAR (thousands)

Usage:
    python -m scripts.econ.us.census.census_housing
    python -m scripts.econ.us.census.census_housing --since 2020-01-01 --no-parquet
    python -m scripts.econ.us.census.census_housing --no-load
"""

from __future__ import annotations

import datetime

from imdr.domains.econ.census_http import CensusClient, eits_time_to_date
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

# (category_code, data_type_code, imdr_code, display_name)
# All are seasonally_adj='yes', geo_level_code='US'
_TARGETS: list[tuple[str, str, str, str]] = [
    ("ASTARTS",  "TOTAL",  "CENSUS.HOUSING.STARTS_TOTAL_SA.US",  "US Housing Starts, Total SAAR (thousands)"),
    ("ASTARTS",  "SINGLE", "CENSUS.HOUSING.STARTS_SF_SA.US",     "US Housing Starts, Single-Family SAAR (thousands)"),
    ("APERMITS", "TOTAL",  "CENSUS.HOUSING.PERMITS_TOTAL_SA.US", "US Building Permits, Total SAAR (thousands)"),
    ("APERMITS", "SINGLE", "CENSUS.HOUSING.PERMITS_SF_SA.US",    "US Building Permits, Single-Family SAAR (thousands)"),
]

_DEFAULT_START_YEAR = 2015


def run_fetch(
    since: str | None,
    until: str | None,
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    since_dt = datetime.date.fromisoformat(since) if since else None
    until_dt = datetime.date.fromisoformat(until) if until else None
    start_year = since_dt.year if since_dt else _DEFAULT_START_YEAR
    now = datetime.datetime.now(UTC)

    indicators: list[IndicatorRow] = []
    observations: list[ObservationRow] = []

    with CensusClient() as client:
        # The API does not accept geo_level_code as a filter param; it is
        # a dimension in the response that we must filter post-download.
        rows = client.get_eits(
            "resconst",
            {
                "get": "data_type_code,time_slot_id,seasonally_adj,category_code,cell_value,error_data,geo_level_code",
                "time": f"from+{start_year}",
            },
        )

    if not rows:
        print("  WARN resconst: 0 rows returned")
        return indicators, observations

    key_to_val: dict[tuple, str] = {}
    for row in rows:
        if row.get("geo_level_code") != "US":
            continue
        if row.get("seasonally_adj") != "yes":
            continue
        if row.get("error_data") == "yes":
            continue
        key = (row["category_code"], row["data_type_code"], row["time"])
        key_to_val[key] = row["cell_value"]

    for cat_code, dtype_code, imdr_code, display_name in _TARGETS:
        matching = {
            t: v
            for (c, d, t), v in key_to_val.items()
            if c == cat_code and d == dtype_code
        }
        if not matching:
            print(f"  WARN {imdr_code}: 0 rows after filter")
            continue

        indicators.append(IndicatorRow(
            imdr_code=imdr_code,
            vendor_name="CENSUS",
            source_code=f"resconst|{cat_code}|{dtype_code}|SA|US",
            display_name=display_name,
            unit="units_th",
            frequency="MONTHLY",
            country_iso="US",
            category="housing",
            is_seasonally_adjusted=True,
        ))

        n = 0
        for t, val_s in sorted(matching.items()):
            obs_date = eits_time_to_date(t)
            if obs_date is None:
                continue
            if since_dt and obs_date < since_dt:
                continue
            if until_dt and obs_date > until_dt:
                continue
            try:
                value = float(val_s)
            except (ValueError, TypeError):
                value = None
            observations.append(ObservationRow(
                imdr_code=imdr_code,
                obs_date=obs_date,
                vintage=0,
                release_date=now,
                value=value,
                ingested_at=now,
            ))
            n += 1
        print(f"  {imdr_code:<44} {n} obs")

    return indicators, observations


def main() -> int:
    return run_main(
        vendor="census",
        topic="housing",
        fetch_fn=run_fetch,
        description=__doc__.splitlines()[0] if __doc__ else "",
        country_code="US",
    )


if __name__ == "__main__":
    import sys
    sys.exit(main())
