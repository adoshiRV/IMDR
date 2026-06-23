"""BEA NIPA Personal Income fetcher — cell 1.1 Private Demand.

Pulls from three NIPA tables at monthly frequency:
  T20600 — Personal Income and Its Disposition (levels, USD bn current $)
  T20804 — PCE Price Index (index, 2017=100, headline + core)
  T20806 — Real PCE by major type, chained (2017) dollars (headline level)

Usage:
    python -m scripts.econ.us.bea.bea_personal_income
    python -m scripts.econ.us.bea.bea_personal_income --since 2015-01-01 --no-load
    python -m scripts.econ.us.bea.bea_personal_income --no-parquet
"""

from __future__ import annotations

import datetime

from imdr.domains.econ.bea_http import BeaClient, bea_period_to_date, parse_data_value
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

# (TableName, SeriesCode, imdr_code, display_name, unit, category, is_sa)
_TARGETS: list[tuple[str, str, str, str, str, str, bool]] = [
    # T20600 — Personal Income disposition
    ("T20600", "A065RC", "BEA.INCOME.PI_USD_BN.US",       "Personal Income (USD bn)",                           "usd_bn", "gdp", True),
    ("T20600", "A067RC", "BEA.INCOME.DPI_USD_BN.US",      "Disposable Personal Income (USD bn)",                "usd_bn", "gdp", True),
    ("T20600", "A072RC", "BEA.INCOME.SAVING_RATE.US",     "Personal Saving Rate (% of DPI)",                   "pct",    "gdp", True),
    ("T20600", "A067RX", "BEA.INCOME.REAL_DPI_USD_BN.US", "Real DPI Chained 2017 USD bn",                      "usd_bn", "gdp", True),
    # T20804 — PCE Price Index
    ("T20804", "DPCERG", "BEA.CPI.PCE_PRICE_IDX.US",      "PCE Chain Price Index (2017=100)",                  "index",  "cpi", True),
    ("T20804", "DPCCRG", "BEA.CPI.PCE_CORE_PRICE_IDX.US", "Core PCE Chain Price Index (ex F&E, 2017=100)",     "index",  "cpi", True),
    # T20806 — Real PCE by major type, chained (2017) dollars. NB: this table is
    # in MILLIONS of chained dollars (unlike T20600's billions) → unit usd_mn.
    ("T20806", "DPCERX", "BEA.INCOME.REAL_PCE.US",        "US Real Personal Consumption Expenditures (chained 2017 $mn, SAAR)", "usd_mn", "gdp", True),
]


def run_fetch(
    since: str | None,
    until: str | None,
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    since_dt = datetime.date.fromisoformat(since) if since else None
    until_dt = datetime.date.fromisoformat(until) if until else None
    now = datetime.datetime.now(UTC)

    indicators: list[IndicatorRow] = []
    observations: list[ObservationRow] = []

    tables: dict[str, list] = {}
    for t in _TARGETS:
        tables.setdefault(t[0], []).append(t)

    with BeaClient() as client:
        for table_name, target_list in tables.items():
            results = client.get_data(
                "NIPA",
                TableName=table_name,
                Frequency="M",
                Year="ALL",
            )
            data = results.get("Data", [])

            target_map = {
                sc: (imdr, name, unit, cat, is_sa)
                for (_, sc, imdr, name, unit, cat, is_sa) in target_list
            }
            by_series: dict[str, list] = {sc: [] for sc in target_map}
            for row in data:
                sc = row.get("SeriesCode", "")
                if sc in by_series:
                    by_series[sc].append(row)

            for sc, rows in by_series.items():
                imdr_code, display_name, unit, category, is_sa = target_map[sc]
                if not rows:
                    print(f"  WARN {table_name}/{sc}: 0 rows")
                    continue
                indicators.append(IndicatorRow(
                    imdr_code=imdr_code,
                    vendor_name="BEA",
                    source_code=f"{table_name}.{sc}",
                    display_name=display_name,
                    unit=unit,
                    frequency="MONTHLY",
                    country_iso="US",
                    category=category,
                    is_seasonally_adjusted=is_sa,
                ))
                n = 0
                for obs in rows:
                    obs_date = bea_period_to_date(obs.get("TimePeriod", ""))
                    if obs_date is None:
                        continue
                    if since_dt and obs_date < since_dt:
                        continue
                    if until_dt and obs_date > until_dt:
                        continue
                    value = parse_data_value(obs.get("DataValue"))
                    observations.append(ObservationRow(
                        imdr_code=imdr_code,
                        obs_date=obs_date,
                        vintage=0,
                        release_date=now,
                        value=value,
                        ingested_at=now,
                    ))
                    n += 1
                print(f"  {table_name}/{sc:<12} {imdr_code:<42} {n} obs")
                if n == 0:
                    indicators.pop()

    return indicators, observations


def main() -> int:
    return run_main(
        vendor="bea",
        topic="personal_income",
        fetch_fn=run_fetch,
        description=__doc__.splitlines()[0] if __doc__ else "",
        country_code="US",
    )


if __name__ == "__main__":
    import sys
    sys.exit(main())
