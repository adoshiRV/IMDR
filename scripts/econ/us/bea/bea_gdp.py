"""BEA NIPA GDP fetcher — cell 1.4 Macro Core.

Pulls real GDP % change (T10101, quarterly SAAR) and GDP levels (T10105,
quarterly) for the headline + 5 expenditure components: PCE, Gross private
domestic investment, Exports, Imports, Government.

Usage:
    python -m scripts.econ.us.bea.bea_gdp
    python -m scripts.econ.us.bea.bea_gdp --since 2015-01-01 --no-load
    python -m scripts.econ.us.bea.bea_gdp --no-parquet
"""

from __future__ import annotations

import datetime

from imdr.domains.econ.bea_http import BeaClient, bea_period_to_date, parse_data_value
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

# (SeriesCode, imdr_code, display_name, is_sa)
# T10101 — percent change from preceding period (SAAR).
_T10101_TARGETS: list[tuple[str, str, str, bool]] = [
    ("A191RL", "BEA.GDP.REAL_PCHG_SAAR.US",     "Real GDP % Chg (SAAR)",                     True),
    ("DPCERL", "BEA.GDP.PCE_REAL_PCHG_SAAR.US",  "Real PCE % Chg (SAAR)",                     True),
    ("A006RL", "BEA.GDP.GPDI_REAL_PCHG_SAAR.US", "Real Gross Private Dom. Inv. % Chg (SAAR)", True),
    ("A020RL", "BEA.GDP.EXP_REAL_PCHG_SAAR.US",  "Real Exports % Chg (SAAR)",                 True),
    ("A021RL", "BEA.GDP.IMP_REAL_PCHG_SAAR.US",  "Real Imports % Chg (SAAR)",                 True),
    ("A822RL", "BEA.GDP.GOVT_REAL_PCHG_SAAR.US", "Real Govt C&I % Chg (SAAR)",                True),
]

# T10105 — levels, billions of current dollars.
_T10105_TARGETS: list[tuple[str, str, str, bool]] = [
    ("A191RC", "BEA.GDP.LEVEL_USD_BN.US",         "GDP Level (USD bn, current $)",             True),
    ("DPCERC", "BEA.GDP.PCE_LEVEL_USD_BN.US",     "PCE Level (USD bn, current $)",             True),
    ("A006RC", "BEA.GDP.GPDI_LEVEL_USD_BN.US",    "Gross Private Dom. Inv. (USD bn)",          True),
    ("A019RC", "BEA.GDP.NETEXP_LEVEL_USD_BN.US",  "Net Exports (USD bn)",                      True),
    ("B020RC", "BEA.GDP.EXP_LEVEL_USD_BN.US",     "Exports (USD bn)",                          True),
    ("B021RC", "BEA.GDP.IMP_LEVEL_USD_BN.US",     "Imports (USD bn)",                          True),
    ("A822RC", "BEA.GDP.GOVT_LEVEL_USD_BN.US",    "Govt C&I (USD bn)",                         True),
]


def _fetch_table(
    client: BeaClient,
    table_name: str,
    targets: list[tuple[str, str, str, bool]],
    unit: str,
    now: datetime.datetime,
    since_dt: datetime.date | None,
    until_dt: datetime.date | None,
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    results = client.get_data(
        "NIPA",
        TableName=table_name,
        Frequency="Q",
        Year="ALL",
    )
    data = results.get("Data", [])

    target_map = {sc: (imdr, name, sa) for sc, imdr, name, sa in targets}
    by_series: dict[str, list] = {sc: [] for sc in target_map}
    for row in data:
        sc = row.get("SeriesCode", "")
        if sc in by_series:
            by_series[sc].append(row)

    indicators: list[IndicatorRow] = []
    observations: list[ObservationRow] = []

    for sc, rows in by_series.items():
        imdr_code, display_name, is_sa = target_map[sc]
        if not rows:
            print(f"  WARN {table_name}/{sc}: 0 rows")
            continue
        indicators.append(IndicatorRow(
            imdr_code=imdr_code,
            vendor_name="BEA",
            source_code=f"{table_name}.{sc}",
            display_name=display_name,
            unit=unit,
            frequency="QUARTERLY",
            country_iso="US",
            category="gdp",
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
        print(f"  {table_name}/{sc:<10} {imdr_code:<40} {n} obs")
        if n == 0:
            indicators.pop()

    return indicators, observations


def run_fetch(
    since: str | None,
    until: str | None,
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    since_dt = datetime.date.fromisoformat(since) if since else None
    until_dt = datetime.date.fromisoformat(until) if until else None
    now = datetime.datetime.now(UTC)

    indicators: list[IndicatorRow] = []
    observations: list[ObservationRow] = []

    with BeaClient() as client:
        ind1, obs1 = _fetch_table(client, "T10101", _T10101_TARGETS, "pct_saar", now, since_dt, until_dt)
        ind2, obs2 = _fetch_table(client, "T10105", _T10105_TARGETS, "usd_bn",   now, since_dt, until_dt)

    indicators = ind1 + ind2
    observations = obs1 + obs2
    return indicators, observations


def main() -> int:
    return run_main(
        vendor="bea",
        topic="gdp",
        fetch_fn=run_fetch,
        description=__doc__.splitlines()[0] if __doc__ else "",
        country_code="US",
    )


if __name__ == "__main__":
    import sys
    sys.exit(main())
