"""ABS Labour Force underemployment / underutilisation (LF_UNDER) playground fetch.

Dataflow: LF_UNDER. Key shape: {PARM_ITEM}.{SEX}.{AGE}.{TSEST}.{REGION}.{FREQ}.

This is the sibling dataflow to LF that carries the underemployment,
underutilisation, and hours-worked measures we skipped in ``fetch_labour.py``.

PARM_ITEM (verified live 2026-06-09): the measure dimension.
  Codes follow LF's M-numbering but LF_UNDER only carries subset M1..M9, M21..M31.
  Headline desk-screen pulls:
    M23 = Underemployment rate (% of labour force)
    M24 = Underutilisation rate (% of labour force)
    M21 = Underemployed total (persons)
    M18 = Employed persons - monthly hours worked
SEX: 3 = Persons (both sexes), 1 = Males, 2 = Females.
AGE: 1599 = Total (15+).
TSEST: 10 = Original, 20 = SA, 30 = Trend.
REGION: AUS = Australia.
FREQ: M (monthly).
"""
from __future__ import annotations

import sys

from imdr.domains.econ.abs_sdmx import ABSClient, SDMXSeries, fetch_series
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main


_MEASURES = [
    ("M23", "UNDEREMPLOYMENT_RATE",   "Underemployment rate",                     "pct"),
    ("M24", "UNDERUTILISATION_RATE",  "Underutilisation rate",                    "pct"),
    ("M21", "UNDEREMPLOYED",          "Underemployed total persons",              "persons"),
    ("M18", "HOURS_WORKED_TOTAL",     "Employed persons monthly hours worked",    "hours"),
]


def _build_series() -> list[SDMXSeries]:
    return [
        SDMXSeries(
            dataflow="LF_UNDER",
            key=f"{meas}.3.1599.20.AUS.M",
            imdr_code=f"ABS.LF_UNDER.{code}_SA.AU",
            display_name=f"ABS Labour Force underutilisation — {label} (persons total, 15+, SA)",
            unit=unit, frequency="MONTHLY", category="labour", is_sa=True,
        )
        for meas, code, label, unit in _MEASURES
    ]


def run_fetch(since: str | None, until: str | None) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    indicators: list[IndicatorRow] = []
    observations: list[ObservationRow] = []
    with ABSClient() as client:
        for spec in _build_series():
            try:
                ind, obs = fetch_series(client, spec, since, until)
            except Exception as exc:
                print(f"  ERROR {spec.imdr_code}: {exc}")
                continue
            indicators.append(ind)
            observations.extend(obs)
            print(f"  {spec.imdr_code:<48s} {len(obs):>5} obs")
    return indicators, observations


def main() -> int:
    return run_main(vendor="abs", topic="lf_under", fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "",
                    country_code="AU")


if __name__ == "__main__":
    sys.exit(main())
