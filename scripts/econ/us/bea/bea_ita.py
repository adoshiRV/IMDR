"""BEA ITA (International Transactions Accounts) fetcher — cells 3.2/3.3.

Current account decomposition (QNSA): headline CA balance, goods, services,
primary income, secondary income. Financial account (QNSA): net lending/
borrowing, net US acquisition of assets, net US incurrence of liabilities.

Usage:
    python -m scripts.econ.us.bea.bea_ita
    python -m scripts.econ.us.bea.bea_ita --since 2000-01-01 --no-load
    python -m scripts.econ.us.bea.bea_ita --no-parquet
"""

from __future__ import annotations

import datetime

from imdr.domains.econ.bea_http import BeaClient, bea_period_to_date, parse_data_value
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

# (Indicator, imdr_code, display_name)
_TARGETS: list[tuple[str, str, str]] = [
    # Current account — cell 3.2
    ("BalCurrAcct",          "BEA.BOP.CA_TOTAL.US",         "Current Account Balance (USD mn)"),
    ("BalGds",               "BEA.BOP.CA_GOODS.US",          "Goods Balance (USD mn)"),
    ("BalGdsServ",           "BEA.BOP.CA_GOODS_SVCS.US",     "Goods & Services Balance (USD mn)"),
    ("BalServ",              "BEA.BOP.CA_SERVICES.US",        "Services Balance (USD mn)"),
    ("BalPrimInc",           "BEA.BOP.CA_PRIM_INCOME.US",    "Primary Income Balance (USD mn)"),
    ("BalSecInc",            "BEA.BOP.CA_SEC_INCOME.US",     "Secondary Income Balance (USD mn)"),
    # Financial account — cell 3.3
    ("NetLendBorrFinAcct",   "BEA.BOP.FA_NET_LEND_BORR.US", "FA Net Lending(+)/Borrowing(-) (USD mn)"),
    ("FinAssetsExclFinDeriv","BEA.BOP.FA_US_ASSETS.US",      "FA Net US Acquisition of Assets (USD mn)"),
    ("FinLiabsExclFinDeriv", "BEA.BOP.FA_US_LIABS.US",      "FA Net US Incurrence of Liabilities (USD mn)"),
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

    target_map = {ind: (imdr, name) for (ind, imdr, name) in _TARGETS}

    with BeaClient() as client:
        for indicator, (imdr_code, display_name) in target_map.items():
            results = client.get_data(
                "ITA",
                Indicator=indicator,
                AreaOrCountry="AllCountries",
                Frequency="QNSA",
                Year="ALL",
            )
            data = results.get("Data", [])
            if not data:
                print(f"  WARN ITA/{indicator}: 0 rows")
                continue
            indicators.append(IndicatorRow(
                imdr_code=imdr_code,
                vendor_name="BEA",
                source_code=f"ITA.{indicator}",
                display_name=display_name,
                unit="usd_mn",
                frequency="QUARTERLY",
                country_iso="US",
                category="bop",
                is_seasonally_adjusted=False,
            ))
            n = 0
            for obs in data:
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
            print(f"  ITA/{indicator:<28} {imdr_code:<40} {n} obs")
            if n == 0:
                indicators.pop()

    return indicators, observations


def main() -> int:
    return run_main(
        vendor="bea",
        topic="ita",
        fetch_fn=run_fetch,
        description=__doc__.splitlines()[0] if __doc__ else "",
        country_code="US",
    )


if __name__ == "__main__":
    import sys
    sys.exit(main())
