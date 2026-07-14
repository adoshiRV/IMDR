"""BEA IIP (International Investment Position) fetcher — cell 3.3.

End-of-period position (Component=Pos, QNSA) for net IIP, total assets/
liabilities, and direct/portfolio investment split.

Usage:
    python -m scripts.econ.us.bea.bea_iip
    python -m scripts.econ.us.bea.bea_iip --since 2000-01-01 --no-load
    python -m scripts.econ.us.bea.bea_iip --no-parquet
"""

from __future__ import annotations

import datetime

from imdr.domains.econ.bea_http import BeaClient, bea_period_to_date, parse_data_value
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

# (TypeOfInvestment, imdr_code, display_name)
_TARGETS: list[tuple[str, str, str]] = [
    ("Net",             "BEA.IIP.NET.US",             "Net International Investment Position (USD mn)"),
    ("NetExclFinDeriv", "BEA.IIP.NET_EXCL_DERIV.US",  "Net IIP Excl. Financial Derivatives (USD mn)"),
    ("FinAssets",       "BEA.IIP.TOTAL_ASSETS.US",    "Total US Foreign Assets (USD mn)"),
    ("FinLiabs",        "BEA.IIP.TOTAL_LIABS.US",     "Total US Foreign Liabilities (USD mn)"),
    ("DiInvAssets",     "BEA.IIP.DI_ASSETS.US",       "Direct Investment Assets at Market Value (USD mn)"),
    ("DiInvLiabs",      "BEA.IIP.DI_LIABS.US",        "Direct Investment Liabilities at Market Value (USD mn)"),
    ("PfInvAssets",     "BEA.IIP.PF_ASSETS.US",       "Portfolio Investment Assets (USD mn)"),
    ("PfInvLiabs",      "BEA.IIP.PF_LIABS.US",        "Portfolio Investment Liabilities (USD mn)"),
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

    target_map = {toi: (imdr, name) for (toi, imdr, name) in _TARGETS}

    with BeaClient() as client:
        for toi, (imdr_code, display_name) in target_map.items():
            results = client.get_data(
                "IIP",
                TypeOfInvestment=toi,
                Component="Pos",
                Frequency="QNSA",
                Year="ALL",
            )
            data = results.get("Data", [])
            if not data:
                print(f"  WARN IIP/{toi}: 0 rows")
                continue
            indicators.append(IndicatorRow(
                imdr_code=imdr_code,
                vendor_name="BEA",
                source_code=f"IIP.{toi}",
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
            print(f"  IIP/{toi:<22} {imdr_code:<38} {n} obs")
            if n == 0:
                indicators.pop()

    return indicators, observations


def main() -> int:
    return run_main(
        vendor="bea",
        topic="iip",
        fetch_fn=run_fetch,
        description=__doc__.splitlines()[0] if __doc__ else "",
        country_code="US",
    )


if __name__ == "__main__":
    import sys
    sys.exit(main())
