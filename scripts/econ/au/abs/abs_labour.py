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

Age-group breakdown lives in the sibling ``LF_AGES`` dataflow, NOT ``LF``
(the LF dataflow 404s on any non-1599 AGE code — verified 2026-07-14). Its
dimension shape is identical to LF: {MEASURE}.{SEX}.{AGE}.{TSEST}.{REGION}.{FREQ}.
State/territory breakdown DOES live in ``LF`` itself via the REGION dimension
(CL_STATE codelist), crossed with AGE=1599 (total) only -- AGE and REGION are
not jointly published (age-by-state key combos 404).

AGE codelist (CL_LF_AGE, verified via /rest/datastructure/ABS/LF_AGES):
  1524 = 15-24, 2534 = 25-34, 3544 = 35-44, 4554 = 45-54, 5564 = 55-64,
  6599 = 65+, 1564 = 15-64. Seasonally Adjusted (TSEST=20) is only published
  for 1524 and 1564; all other bands are Original (TSEST=10) only.

REGION/state codelist (CL_STATE, verified via /rest/datastructure/ABS/LF):
  1=NSW, 2=VIC, 3=QLD, 4=SA, 5=WA, 6=TAS, 7=NT, 8=ACT. SA (TSEST=20) is
  published for NSW/VIC/QLD/SA/WA/TAS; NT and ACT are Original only.
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
# 404 against /rest/data/LF/{Mxx}.3.1599.20.AUS.M. They live in the sibling
# LF_UNDER dataflow (see abs_lf_under.py).
_MEASURES = [
    ("M13", "UNEMPLOYMENT_RATE",    "Unemployment rate",              "pct",     "labour"),
    ("M12", "PARTICIPATION_RATE",   "Participation rate",             "pct",     "labour"),
    ("M3",  "EMPLOYED",             "Employed persons",               "persons", "labour"),
    ("M6",  "UNEMPLOYED",           "Unemployed persons",             "persons", "labour"),
    ("M9",  "LABOUR_FORCE",         "Labour Force",                   "persons", "labour"),
    ("M16", "EMPLOYMENT_POP_RATIO", "Employment-to-population ratio", "pct",     "labour"),
]

# Age/state breakdowns are limited to the three desk-screen rate/level
# measures (unemployment rate, participation rate, employed persons).
_BREAKDOWN_MEASURES = [
    ("M13", "UNEMPLOYMENT_RATE",  "Unemployment rate",    "pct"),
    ("M12", "PARTICIPATION_RATE", "Participation rate",   "pct"),
    ("M3",  "EMPLOYED",           "Employed persons",     "persons"),
]

# (AGE code, label suffix, TSEST code) -- TSEST picked per band per the SA
# availability verified above (SA where published, else Original).
_AGE_BANDS = [
    ("1524", "15_24",  "20"),
    ("2534", "25_34",  "10"),
    ("3544", "35_44",  "10"),
    ("4554", "45_54",  "10"),
    ("5564", "55_64",  "10"),
    ("6599", "65_PLUS", "10"),
    ("1564", "15_64",  "20"),
]

# (REGION code, label suffix, TSEST code) -- SA for the 6 states, Original
# for the 2 territories (verified above).
_STATES = [
    ("1", "NSW", "20"),
    ("2", "VIC", "20"),
    ("3", "QLD", "20"),
    ("4", "SA",  "20"),
    ("5", "WA",  "20"),
    ("6", "TAS", "20"),
    ("7", "NT",  "10"),
    ("8", "ACT", "10"),
]


def _tsest_label(tsest: str) -> str:
    return "SA" if tsest == "20" else "ORIG"


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


def _build_age_series() -> list[SDMXSeries]:
    out: list[SDMXSeries] = []
    for meas, code_suffix, label, unit in _BREAKDOWN_MEASURES:
        for age_code, age_label, tsest in _AGE_BANDS:
            tsest_label = _tsest_label(tsest)
            out.append(SDMXSeries(
                dataflow="LF_AGES",
                key=f"{meas}.3.{age_code}.{tsest}.AUS.M",
                imdr_code=f"ABS.LF.{code_suffix}_AGE_{age_label}_{tsest_label}.AU",
                display_name=f"ABS Labour Force — {label} (age {age_label.replace('_', '-')}, {tsest_label})",
                unit=unit,
                frequency="MONTHLY",
                category="labour",
                is_sa=(tsest == "20"),
            ))
    return out


def _build_state_series() -> list[SDMXSeries]:
    out: list[SDMXSeries] = []
    for meas, code_suffix, label, unit in _BREAKDOWN_MEASURES:
        for region_code, state_label, tsest in _STATES:
            tsest_label = _tsest_label(tsest)
            out.append(SDMXSeries(
                dataflow="LF",
                key=f"{meas}.3.1599.{tsest}.{region_code}.M",
                imdr_code=f"ABS.LF.{code_suffix}_STATE_{state_label}_{tsest_label}.AU",
                display_name=f"ABS Labour Force — {label} ({state_label}, {tsest_label})",
                unit=unit,
                frequency="MONTHLY",
                category="labour",
                is_sa=(tsest == "20"),
            ))
    return out


def run_fetch(since: str | None, until: str | None) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    indicators: list[IndicatorRow] = []
    observations: list[ObservationRow] = []
    specs = _build_series() + _build_age_series() + _build_state_series()
    with ABSClient() as client:
        for spec in specs:
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
