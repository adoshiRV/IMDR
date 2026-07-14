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

Unlike LF, LF_UNDER natively carries both the AGE and REGION dimensions
(verified 2026-07-14 via /rest/datastructure/ABS/LF_UNDER + live data probes
against M23/M24) -- no sibling dataflow needed for the breakdowns.

AGE codelist (CL_LF_AGE, shared with LF/LF_AGES): 1524=15-24, 2534=25-34,
3544=35-44, 4554=45-54, 5564=55-64, 6599=65+, 1564=15-64. For M23/M24, SA
(TSEST=20) is published for 1524/2534/3544/4554/1564; 5564 and 6599 are
Original only.

REGION/state codelist (CL_STATE, shared with LF): 1=NSW, 2=VIC, 3=QLD, 4=SA,
5=WA, 6=TAS, 7=NT, 8=ACT. SA is published for the 6 states; NT/ACT are
Original only (same pattern as LF).
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

# Breakdowns are limited to the two headline rate measures.
_BREAKDOWN_MEASURES = [
    ("M23", "UNDEREMPLOYMENT_RATE",  "Underemployment rate",  "pct"),
    ("M24", "UNDERUTILISATION_RATE", "Underutilisation rate", "pct"),
]

# (AGE code, label suffix, TSEST code) -- SA where published else Original,
# per the M23/M24 availability verified above.
_AGE_BANDS = [
    ("1524", "15_24",  "20"),
    ("2534", "25_34",  "20"),
    ("3544", "35_44",  "20"),
    ("4554", "45_54",  "20"),
    ("5564", "55_64",  "10"),
    ("6599", "65_PLUS", "10"),
    ("1564", "15_64",  "20"),
]

# (REGION code, label suffix, TSEST code) -- SA for the 6 states, Original
# for the 2 territories.
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


def _build_age_series() -> list[SDMXSeries]:
    out: list[SDMXSeries] = []
    for meas, code_suffix, label, unit in _BREAKDOWN_MEASURES:
        for age_code, age_label, tsest in _AGE_BANDS:
            tsest_label = _tsest_label(tsest)
            out.append(SDMXSeries(
                dataflow="LF_UNDER",
                key=f"{meas}.3.{age_code}.{tsest}.AUS.M",
                imdr_code=f"ABS.LF_UNDER.{code_suffix}_AGE_{age_label}_{tsest_label}.AU",
                display_name=f"ABS Labour Force underutilisation — {label} (age {age_label.replace('_', '-')}, {tsest_label})",
                unit=unit, frequency="MONTHLY", category="labour",
                is_sa=(tsest == "20"),
            ))
    return out


def _build_state_series() -> list[SDMXSeries]:
    out: list[SDMXSeries] = []
    for meas, code_suffix, label, unit in _BREAKDOWN_MEASURES:
        for region_code, state_label, tsest in _STATES:
            tsest_label = _tsest_label(tsest)
            out.append(SDMXSeries(
                dataflow="LF_UNDER",
                key=f"{meas}.3.1599.{tsest}.{region_code}.M",
                imdr_code=f"ABS.LF_UNDER.{code_suffix}_STATE_{state_label}_{tsest_label}.AU",
                display_name=f"ABS Labour Force underutilisation — {label} ({state_label}, {tsest_label})",
                unit=unit, frequency="MONTHLY", category="labour",
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
            print(f"  {spec.imdr_code:<48s} {len(obs):>5} obs")
    return indicators, observations


def main() -> int:
    return run_main(vendor="abs", topic="lf_under", fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "",
                    country_code="AU")


if __name__ == "__main__":
    sys.exit(main())
