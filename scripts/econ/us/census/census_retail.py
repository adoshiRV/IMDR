"""Census MARTS retail-sales fetcher — cell 1.1 Private Demand.

Pulls Monthly Advance Retail Trade and Food Services (MARTS) headline totals
from the Census EITS time-series API. Three series: total SA, total NSA, and
ex-auto SA. Category 44000 = Total Retail & Food Services; 44X72 = ex-Motor
Vehicles. data_type_code SM = Sales ($mn).

Usage:
    python -m scripts.econ.us.census.census_retail
    python -m scripts.econ.us.census.census_retail --since 2020-01-01 --no-parquet
    python -m scripts.econ.us.census.census_retail --no-load
"""

from __future__ import annotations

import datetime

from imdr.domains.econ.census_http import CensusClient, eits_time_to_date
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

# (category_code, seasonally_adj, imdr_code, display_name, is_sa)
_TARGETS: list[tuple[str, str, str, str, bool]] = [
    ("44000", "yes", "CENSUS.RETAIL.TOTAL_SA.US",   "US Retail & Food Services Sales, Total (SA)",   True),
    ("44000", "no",  "CENSUS.RETAIL.TOTAL_NSA.US",  "US Retail & Food Services Sales, Total (NSA)",  False),
    ("44X72", "yes", "CENSUS.RETAIL.EX_AUTO_SA.US", "US Retail & Food Services Sales, Ex-Auto (SA)", True),
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
        for cat_code, sa, imdr_code, display_name, is_sa in _TARGETS:
            rows = client.get_eits(
                "marts",
                {
                    "get": "data_type_code,seasonally_adj,category_code,cell_value,error_data",
                    "time": f"from+{start_year}",
                    "data_type_code": "SM",
                    "category_code": cat_code,
                    "seasonally_adj": sa,
                },
            )
            if not rows:
                print(f"  WARN {imdr_code}: 0 rows returned")
                continue

            indicators.append(IndicatorRow(
                imdr_code=imdr_code,
                vendor_name="CENSUS",
                source_code=f"marts|{cat_code}|SM|{sa}",
                display_name=display_name,
                unit="usd_mn",
                frequency="MONTHLY",
                country_iso="US",
                category="other",
                is_seasonally_adjusted=is_sa,
            ))

            n = 0
            for row in rows:
                if row.get("error_data", "no") == "yes":
                    continue
                obs_date = eits_time_to_date(row.get("time", ""))
                if obs_date is None:
                    continue
                if since_dt and obs_date < since_dt:
                    continue
                if until_dt and obs_date > until_dt:
                    continue
                val_s = row.get("cell_value")
                try:
                    value = float(val_s) if val_s not in (None, "") else None
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
            print(f"  {imdr_code:<38} {n} obs")

    return indicators, observations


def main() -> int:
    return run_main(
        vendor="census",
        topic="retail",
        fetch_fn=run_fetch,
        description=__doc__.splitlines()[0] if __doc__ else "",
        country_code="US",
    )


if __name__ == "__main__":
    import sys
    sys.exit(main())
