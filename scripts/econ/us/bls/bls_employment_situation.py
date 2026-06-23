"""BLS Employment Situation fetcher — cell 1.4 labour leg.

Pulls core Employment Situation release series from BLS v2:
nonfarm payrolls, unemployment rate, LFPR, average hourly earnings,
employment level, and unemployment level.

Usage:
    python -m scripts.econ.us.bls.bls_employment_situation
    python -m scripts.econ.us.bls.bls_employment_situation --since 2024-01-01 --no-load
"""

from __future__ import annotations

import datetime

from imdr.domains.econ.bls_http import BlsClient, bls_period_to_date
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

# (source_code, imdr_code, display_name, unit, is_SA)
_TARGETS: list[tuple[str, str, str, str, bool]] = [
    ("CES0000000001", "BLS.LABOUR.PAYROLLS_SA.US",    "Nonfarm Payrolls Total (SA)",                  "th_persons", True),
    ("LNS14000000",   "BLS.LABOUR.UNEMP_RATE_SA.US",  "Unemployment Rate (SA)",                       "pct",        True),
    ("LNS11300000",   "BLS.LABOUR.LFPR_SA.US",        "Labour Force Participation Rate (SA)",         "pct",        True),
    ("CES0500000003", "BLS.LABOUR.AHE_PRIV_SA.US",    "Avg Hourly Earnings Total Private (SA)",       "usd",        True),
    ("LNS12000000",   "BLS.LABOUR.EMP_LEVEL_SA.US",   "Employment Level Civilian (SA)",               "th_persons", True),
    ("LNS13000000",   "BLS.LABOUR.UNEMP_LEVEL_SA.US", "Unemployment Level Civilian (SA)",             "th_persons", True),
]


def run_fetch(
    since: str | None,
    until: str | None,
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    since_dt = datetime.date.fromisoformat(since) if since else None
    until_dt = datetime.date.fromisoformat(until) if until else None
    now = datetime.datetime.now(UTC)

    start_year = since_dt.year if since_dt else 2010
    end_year = until_dt.year if until_dt else datetime.date.today().year

    series_ids = [t[0] for t in _TARGETS]
    with BlsClient() as client:
        raw = client.fetch_series(series_ids, start_year, end_year)

    indicators: list[IndicatorRow] = []
    observations: list[ObservationRow] = []

    by_source = {t[0]: t for t in _TARGETS}
    for sid, target in by_source.items():
        _, imdr_code, display_name, unit, is_sa = target
        rows = raw.get(sid, [])
        if not rows:
            print(f"  WARN {sid}: 0 rows")
            continue
        indicators.append(IndicatorRow(
            imdr_code=imdr_code,
            vendor_name="BLS",
            source_code=sid,
            display_name=display_name,
            unit=unit,
            frequency="MONTHLY",
            country_iso="US",
            category="labour",
            is_seasonally_adjusted=is_sa,
            bbg_ticker=None,
        ))
        n = 0
        for obs in rows:
            obs_date = bls_period_to_date(obs.get("year"), obs.get("period"))
            if obs_date is None:
                continue
            if since_dt and obs_date < since_dt:
                continue
            if until_dt and obs_date > until_dt:
                continue
            val_s = obs.get("value")
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
        print(f"  {sid:<18} {imdr_code:<40} {n} obs")
        if n == 0:
            indicators.pop()

    return indicators, observations


def main() -> int:
    return run_main(
        vendor="bls",
        topic="employment_situation",
        fetch_fn=run_fetch,
        description=__doc__.splitlines()[0] if __doc__ else "",
        country_code="US",
    )


if __name__ == "__main__":
    import sys
    sys.exit(main())
