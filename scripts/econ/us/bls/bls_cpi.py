"""BLS CPI-U fetcher — cell 2.4 CPI Pressure.

Pulls CPI-U headline + core + major-group component tree from BLS v2.
Release-day primary source for US CPI (FRED mirrors this with a lag).

Usage:
    python -m scripts.econ.us.bls.bls_cpi
    python -m scripts.econ.us.bls.bls_cpi --since 2024-01-01 --no-load
"""

from __future__ import annotations

import datetime

from imdr.domains.econ.bls_http import BlsClient, bls_period_to_date
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

UTC = datetime.timezone.utc

# (source_code, imdr_code, display_name, is_SA)
_TARGETS: list[tuple[str, str, str, bool]] = [
    ("CUSR0000SA0",    "BLS.CPI.HEADLINE_SA.US",   "CPI-U All Items (SA)",                                          True),
    ("CUUR0000SA0",    "BLS.CPI.HEADLINE_NSA.US",  "CPI-U All Items (NSA)",                                         False),
    ("CUSR0000SA0L1E", "BLS.CPI.CORE_SA.US",       "CPI-U Less Food & Energy / Core (SA)",                          True),
    ("CUUR0000SA0L1E", "BLS.CPI.CORE_NSA.US",      "CPI-U Less Food & Energy / Core (NSA)",                         False),
    ("CUSR0000SAF1",   "BLS.CPI.FOOD_SA.US",       "CPI-U Food (SA)",                                               True),
    ("CUSR0000SA0E",   "BLS.CPI.ENERGY_SA.US",     "CPI-U Energy (SA)",                                             True),
    ("CUSR0000SAH1",   "BLS.CPI.SHELTER_SA.US",    "CPI-U Shelter (SA)",                                            True),
    ("CUSR0000SAS",    "BLS.CPI.SERVICES_SA.US",   "CPI-U Services (SA)",                                           True),
    ("CUSR0000SACL1E", "BLS.CPI.CORE_GOODS_SA.US", "CPI-U Commodities Less Food & Energy / Core Goods (SA)",        True),
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
        _, imdr_code, display_name, is_sa = target
        rows = raw.get(sid, [])
        if not rows:
            print(f"  WARN {sid}: 0 rows")
            continue
        indicators.append(IndicatorRow(
            imdr_code=imdr_code,
            vendor_name="BLS",
            source_code=sid,
            display_name=display_name,
            unit="index",
            frequency="MONTHLY",
            country_iso="US",
            category="cpi",
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
        print(f"  {sid:<18} {imdr_code:<32} {n} obs")
        if n == 0:
            indicators.pop()

    return indicators, observations


def main() -> int:
    return run_main(
        vendor="bls",
        topic="cpi",
        fetch_fn=run_fetch,
        description=__doc__.splitlines()[0] if __doc__ else "",
        country_code="US",
    )


if __name__ == "__main__":
    import sys
    sys.exit(main())
