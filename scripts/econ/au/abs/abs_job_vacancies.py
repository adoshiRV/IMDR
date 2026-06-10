"""ABS Job Vacancies (JV) playground fetch.

Dataflow: JV. Key shape: {MEASURE}.{SECTOR}.{INDUSTRY}.{TSEST}.{REGION}.{FREQ}.

MEASURE: M1 = Job Vacancies, M2 = Standard Error of Job Vacancies.
SECTOR: 7 = Private and Public (headline), 1 = Private, 2 = Public.
INDUSTRY: TOT = All industries; A..S = ANZSIC divisions.
TSEST: 10 = Original, 20 = SA, 30 = Trend.
REGION: AUS = Australia.
FREQ: Q (quarterly).
"""

from __future__ import annotations

import sys

from imdr.domains.econ.abs_sdmx import ABSClient, SDMXSeries, fetch_series
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main


def _build_series() -> list[SDMXSeries]:
    return [
        # Headline — total private+public, all industries, SA
        SDMXSeries(
            dataflow="JV", key="M1.7.TOT.20.AUS.Q",
            imdr_code="ABS.JV.TOTAL_SA.AU",
            display_name="ABS Job Vacancies — Total (Private+Public, all industries, SA)",
            unit="persons", frequency="QUARTERLY", category="labour", is_sa=True,
            source_code_suffix="thousands",
        ),
        SDMXSeries(
            dataflow="JV", key="M1.1.TOT.20.AUS.Q",
            imdr_code="ABS.JV.PRIVATE_SA.AU",
            display_name="ABS Job Vacancies — Private sector (all industries, SA)",
            unit="persons", frequency="QUARTERLY", category="labour", is_sa=True,
            source_code_suffix="thousands",
        ),
        SDMXSeries(
            dataflow="JV", key="M1.2.TOT.20.AUS.Q",
            imdr_code="ABS.JV.PUBLIC_SA.AU",
            display_name="ABS Job Vacancies — Public sector (all industries, SA)",
            unit="persons", frequency="QUARTERLY", category="labour", is_sa=True,
            source_code_suffix="thousands",
        ),
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
            print(f"  {spec.imdr_code:<45s} {len(obs):>5} obs")
    return indicators, observations


def main() -> int:
    return run_main(vendor="abs", topic="job_vacancies", fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "",
                    country_code="AU")


if __name__ == "__main__":
    sys.exit(main())
