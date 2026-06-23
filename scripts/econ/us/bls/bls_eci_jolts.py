"""BLS ECI + JOLTS + Productivity fetcher — cell 2.3 Domestic Costs.

Quarterly: ECI Total Compensation, ECI Wages & Salaries, Nonfarm Business
Productivity. Monthly: JOLTS Quits Rate, Job Openings Level, Hires Rate.

Usage:
    python -m scripts.econ.us.bls.bls_eci_jolts
    python -m scripts.econ.us.bls.bls_eci_jolts --since 2024-01-01 --no-load
"""

from __future__ import annotations

import datetime

from imdr.domains.econ.bls_http import BlsClient, bls_period_to_date
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

# (source_code, imdr_code, display_name, unit, frequency, is_SA)
_TARGETS: list[tuple[str, str, str, str, str, bool]] = [
    ("CIU1010000000000A",    "BLS.ECI.TOTAL_COMP.US",       "ECI Total Compensation Civilian Workers",       "index",      "QUARTERLY", True),
    ("CIU2020000000000A",    "BLS.ECI.WAGES_SALARIES.US",   "ECI Wages & Salaries Civilian Workers",         "index",      "QUARTERLY", True),
    ("PRS85006092",          "BLS.PRODUCTIVITY.NONFARM.US", "Nonfarm Business Productivity Output per Hour", "index",      "QUARTERLY", True),
    ("JTS000000000000000QUR","BLS.JOLTS.QUITS_RATE.US",     "JOLTS Total Nonfarm Quits Rate",                "pct",        "MONTHLY",   True),
    ("JTS000000000000000JOL","BLS.JOLTS.JOB_OPENINGS.US",   "JOLTS Total Nonfarm Job Openings Level",        "th_persons", "MONTHLY",   True),
    ("JTS000000000000000HIR","BLS.JOLTS.HIRES_RATE.US",     "JOLTS Total Nonfarm Hires Rate",                "pct",        "MONTHLY",   True),
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
        _, imdr_code, display_name, unit, frequency, is_sa = target
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
            frequency=frequency,
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
        print(f"  {sid:<26} {imdr_code:<38} [{frequency:9s}] {n} obs")
        if n == 0:
            indicators.pop()

    return indicators, observations


def main() -> int:
    return run_main(
        vendor="bls",
        topic="eci_jolts",
        fetch_fn=run_fetch,
        description=__doc__.splitlines()[0] if __doc__ else "",
        country_code="US",
    )


if __name__ == "__main__":
    import sys
    sys.exit(main())
