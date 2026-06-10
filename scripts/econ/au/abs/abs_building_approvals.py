"""ABS Building Approvals (BA_GCCSA) playground fetch.

Dataflow: BA_GCCSA. Key shape:
  {MEASURE}.{VALUE}.{SECTOR}.{WORK_TYPE}.{BUILDING_TYPE}.{TSEST}.{REGION}.{FREQ}

We pin national headline (REGION=AUS, FREQ=M, VALUE=1 Total, SECTOR=9
Total Sectors, WORK_TYPE=TOT) and vary the housing-type split.

MEASURE (CL_BA_MEASURE):
  1 = Number of dwelling units (the headline count)
  2 = Value of building jobs (AUD thousands)
BUILDING_TYPE (CL_BLD_TYPE — only component totals exist):
  100 = Total Residential (HEADLINE — dwellings approved)
  110 = Houses (single-housing leading indicator)
  130 = Apartments — Total
  150 = Total Other Residential
  200 = Commercial Buildings — Total
TSEST: 10 Original, 20 SA, 30 Trend

Loads the dwellings-by-headline-split + total-residential value + Trend
view. Classical leading indicator for AU construction + private demand.
"""
from __future__ import annotations

import sys

from imdr.domains.econ.abs_sdmx import ABSClient, SDMXSeries, fetch_series
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main


def _build_series() -> list[SDMXSeries]:
    """Returns the 4 NSA national-headline building-approvals series:
    2 dwelling-count series + 2 value-of-jobs series.

    Probed 2026-06-10: SA (TSEST=20) returns 404 at the building-type
    headline level; only NSA (TSEST=10) is published. Apartments (130)
    and Other Residential (150 post-2001) also 404 — Total Residential
    and Houses cover what desk uses.

    Value-of-jobs series enabled 2026-06-10 after migration 091 seeded
    `aud_th` (Thousand Australian dollars, scale=1000) into dim_unit.
    ABS reports BA values with UNIT_MULT=3 = thousands of AUD.
    """
    return [
        SDMXSeries(
            dataflow="BA_GCCSA",
            key="1.1.9.TOT.100.10.AUS.M",
            imdr_code="ABS.BA.TOTAL_RES_UNITS_NSA.AU",
            display_name="ABS Building Approvals — Total Residential dwellings (number, NSA, monthly)",
            unit="count", frequency="MONTHLY", category="housing", is_sa=False,
        ),
        SDMXSeries(
            dataflow="BA_GCCSA",
            key="1.1.9.TOT.110.10.AUS.M",
            imdr_code="ABS.BA.HOUSES_UNITS_NSA.AU",
            display_name="ABS Building Approvals — Houses dwellings (number, NSA, monthly)",
            unit="count", frequency="MONTHLY", category="housing", is_sa=False,
        ),
        SDMXSeries(
            dataflow="BA_GCCSA",
            key="2.1.9.TOT.100.10.AUS.M",
            imdr_code="ABS.BA.TOTAL_RES_VALUE_NSA.AU",
            display_name="ABS Building Approvals — Total Residential value of jobs (NSA, AUD thousands, monthly)",
            unit="aud_th", frequency="MONTHLY", category="housing", is_sa=False,
        ),
        SDMXSeries(
            dataflow="BA_GCCSA",
            key="2.1.9.TOT.200.10.AUS.M",
            imdr_code="ABS.BA.COMMERCIAL_VALUE_NSA.AU",
            display_name="ABS Building Approvals — Commercial Buildings value of jobs (NSA, AUD thousands, monthly)",
            unit="aud_th", frequency="MONTHLY", category="housing", is_sa=False,
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
            print(f"  {spec.imdr_code:<48s} {len(obs):>5} obs")
    return indicators, observations


def main() -> int:
    return run_main(vendor="abs", topic="building_approvals", fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "",
                    country_code="AU")


if __name__ == "__main__":
    sys.exit(main())
