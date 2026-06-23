"""Census intltrade FT-900 headline fetcher — cell 1.3 External Demand.

Pulls monthly headline goods exports and imports from the Census intltrade
end-use API, filtering to the total-world, total-end-use aggregates. Trade
balance is derived as exports minus imports. API values are in actual USD;
this fetcher converts to $mn.

Series produced:
  CENSUS.TRADE.EXPORTS_GOODS.US — total goods exports
  CENSUS.TRADE.IMPORTS_GOODS.US — total goods imports
  CENSUS.TRADE.BALANCE_GOODS.US — trade balance (exports minus imports)

Usage:
    python -m scripts.econ.us.census.census_trade
    python -m scripts.econ.us.census.census_trade --since 2020-01-01 --no-parquet
    python -m scripts.econ.us.census.census_trade --no-load
"""

from __future__ import annotations

import datetime

from imdr.domains.econ.census_http import CensusClient, eits_time_to_date
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

_DEFAULT_START_YEAR = 2015
_USD_TO_MN = 1e-6  # API values are in actual USD; convert to $mn


def _fetch_exports(client: CensusClient, start_year: int) -> dict[str, float]:
    rows = client.get_intltrade(
        "exports/enduse",
        {
            "get": "ALL_VAL_MO,E_ENDUSE,E_ENDUSE_SDESC,CTY_NAME",
            "time": f"from+{start_year}",
        },
    )
    result: dict[str, float] = {}
    for row in rows:
        if row.get("E_ENDUSE") != "-":
            continue
        if row.get("CTY_NAME") != "TOTAL FOR ALL COUNTRIES":
            continue
        t = row.get("time", "")
        val_s = row.get("ALL_VAL_MO")
        try:
            result[t] = float(val_s) * _USD_TO_MN
        except (ValueError, TypeError):
            pass
    return result


def _fetch_imports(client: CensusClient, start_year: int) -> dict[str, float]:
    rows = client.get_intltrade(
        "imports/enduse",
        {
            "get": "GEN_VAL_MO,I_ENDUSE,I_ENDUSE_SDESC,CTY_NAME",
            "time": f"from+{start_year}",
        },
    )
    result: dict[str, float] = {}
    for row in rows:
        if row.get("I_ENDUSE") != "-":
            continue
        if row.get("CTY_NAME") != "TOTAL FOR ALL COUNTRIES":
            continue
        t = row.get("time", "")
        val_s = row.get("GEN_VAL_MO")
        try:
            result[t] = float(val_s) * _USD_TO_MN
        except (ValueError, TypeError):
            pass
    return result


def run_fetch(
    since: str | None,
    until: str | None,
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    since_dt = datetime.date.fromisoformat(since) if since else None
    until_dt = datetime.date.fromisoformat(until) if until else None
    start_year = since_dt.year if since_dt else _DEFAULT_START_YEAR
    now = datetime.datetime.now(UTC)

    with CensusClient() as client:
        exports_by_t = _fetch_exports(client, start_year)
        imports_by_t = _fetch_imports(client, start_year)

    print(f"  Exports raw periods: {len(exports_by_t)}, Imports raw periods: {len(imports_by_t)}")

    indicators: list[IndicatorRow] = []
    observations: list[ObservationRow] = []

    for imdr_code, source_code, display_name in [
        ("CENSUS.TRADE.EXPORTS_GOODS.US", "intltrade/exports/enduse|E_ENDUSE=-|ALL_VAL_MO", "US Goods Exports, Total (Census FT-900)"),
        ("CENSUS.TRADE.IMPORTS_GOODS.US", "intltrade/imports/enduse|I_ENDUSE=-|GEN_VAL_MO", "US Goods Imports, Total (Census FT-900)"),
        ("CENSUS.TRADE.BALANCE_GOODS.US", "intltrade/derived|exports-imports",              "US Goods Trade Balance (Census FT-900)"),
    ]:
        indicators.append(IndicatorRow(
            imdr_code=imdr_code,
            vendor_name="CENSUS",
            source_code=source_code,
            display_name=display_name,
            unit="usd_mn",
            frequency="MONTHLY",
            country_iso="US",
            category="bop",
            is_seasonally_adjusted=False,
        ))

    all_periods = sorted(set(exports_by_t) | set(imports_by_t))
    exp_n = imp_n = bal_n = 0
    for t in all_periods:
        obs_date = eits_time_to_date(t)
        if obs_date is None:
            continue
        if since_dt and obs_date < since_dt:
            continue
        if until_dt and obs_date > until_dt:
            continue

        if t in exports_by_t:
            observations.append(ObservationRow(
                imdr_code="CENSUS.TRADE.EXPORTS_GOODS.US",
                obs_date=obs_date,
                vintage=0,
                release_date=now,
                value=exports_by_t[t],
                ingested_at=now,
            ))
            exp_n += 1

        if t in imports_by_t:
            observations.append(ObservationRow(
                imdr_code="CENSUS.TRADE.IMPORTS_GOODS.US",
                obs_date=obs_date,
                vintage=0,
                release_date=now,
                value=imports_by_t[t],
                ingested_at=now,
            ))
            imp_n += 1

        if t in exports_by_t and t in imports_by_t:
            observations.append(ObservationRow(
                imdr_code="CENSUS.TRADE.BALANCE_GOODS.US",
                obs_date=obs_date,
                vintage=0,
                release_date=now,
                value=exports_by_t[t] - imports_by_t[t],
                ingested_at=now,
            ))
            bal_n += 1

    print(f"  CENSUS.TRADE.EXPORTS_GOODS.US         {exp_n} obs")
    print(f"  CENSUS.TRADE.IMPORTS_GOODS.US         {imp_n} obs")
    print(f"  CENSUS.TRADE.BALANCE_GOODS.US         {bal_n} obs")
    return indicators, observations


def main() -> int:
    return run_main(
        vendor="census",
        topic="trade",
        fetch_fn=run_fetch,
        description=__doc__.splitlines()[0] if __doc__ else "",
        country_code="US",
    )


if __name__ == "__main__":
    import sys
    sys.exit(main())
