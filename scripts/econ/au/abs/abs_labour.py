"""ABS Labour Force playground fetch.

Dataflow: LF. Key shape: {MEASURE}.{SEX}.{AGE}.{TSEST}.{REGION}.{FREQ}.

MEASURE: M3  = Employed persons,
         M6  = Unemployed persons,
         M9  = Labour Force (M3 + M6),
         M11 = Civilian population (15+),
         M12 = Participation rate (%),
         M13 = Unemployment rate (%),
         M16 = Employment to population ratio (%),
         M18 = Employed persons monthly hours worked,
         M23 = Underemployment rate (%),
         M24 = Underutilisation rate (%).
SEX:     3 = Persons (both sexes), 1 = Males, 2 = Females.
AGE:     1599 = Total (age 15+).
TSEST:   10 = Original, 20 = Seasonally Adjusted, 30 = Trend.
REGION:  AUS = Australia (national).
FREQ:    M (monthly).

Headline desk-screen: M13 (unemployment rate), M12 (participation rate),
M23 (underemployment rate), M24 (underutilisation rate), M3 (employed persons).
"""

from __future__ import annotations

import sys

from imdr.domains.econ.abs_sdmx import ABSClient, SDMXSeries, fetch_series
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main

# Headline measure code -> (imdr_code suffix, display label, unit, category)
#
# Underemployment (M23) + underutilisation (M24) + hours worked (M18) are NOT
# in the LF dataflow at the persons-total / 15+ / national / SA cut — they
# 404 against /rest/data/LF/{Mxx}.3.1599.20.AUS.M. They likely live in the
# sibling LF_UNDER dataflow.
# TODO: verify LF_UNDER dataflow before promoting these measures.
_MEASURES = [
    ("M13", "UNEMPLOYMENT_RATE",    "Unemployment rate",              "pct",     "labour"),
    ("M12", "PARTICIPATION_RATE",   "Participation rate",             "pct",     "labour"),
    ("M3",  "EMPLOYED",             "Employed persons",               "persons", "labour"),
    ("M6",  "UNEMPLOYED",           "Unemployed persons",             "persons", "labour"),
    ("M9",  "LABOUR_FORCE",         "Labour Force",                   "persons", "labour"),
    ("M16", "EMPLOYMENT_POP_RATIO", "Employment-to-population ratio", "pct",     "labour"),
]


def _build_series() -> list[SDMXSeries]:
    out: list[SDMXSeries] = []
    for meas, code_suffix, label, unit, category in _MEASURES:
        # National, persons total, 15+, Seasonally Adjusted, monthly
        out.append(SDMXSeries(
            dataflow="LF",
            key=f"{meas}.3.1599.20.AUS.M",
            imdr_code=f"ABS.LF.{code_suffix}_SA.AU",
            display_name=f"ABS Labour Force — {label} (persons total, 15+, SA)",
            unit=unit,
            frequency="MONTHLY",
            category=category,
            is_sa=True,
        ))
    return out


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
    return run_main(vendor="abs", topic="labour", fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "",
                    country_code="AU")


if __name__ == "__main__":
    sys.exit(main())
