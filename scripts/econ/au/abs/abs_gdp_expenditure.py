"""ABS GDP Expenditure decomposition (ANA_EXP) playground fetch.

Dataflow: ANA_EXP. Key shape: {MEASURE}.{DATA_ITEM}.{SECTOR}.{TSEST}.{REGION}.{FREQ}.

Note: ANA_EXP has a SECTOR dimension that ANA_AGG doesn't.

MEASURE (CL_ANA_MEASURE):
  VCH     = Chain volume measures (real $),
  PCT_VCH = Chain volume % change,
  C       = Current prices (nominal $),
  PCT_C   = Current prices % change,
  TCH     = Contributions to growth (chain volume),
  TC      = Contributions to growth.
DATA_ITEM (CL_ANA_EXP_ITEMS) — desk-relevant headlines:
  FCE     = Final consumption expenditure (combines household + govt depending on sector)
  GFC     = Gross fixed capital formation (total)
  GFC_PBI = Total private business investment
  GFC_DWL = Dwellings (housing investment)
  GFC_EQP = Machinery and equipment
  GFC_IPP = Intellectual property products
  GFC_NDC = Non-dwelling construction
  IST     = Changes in inventories
  DFD     = Domestic final demand (FCE + GFC + IST)
  GNE     = Gross national expenditure
  XGS     = Exports of goods and services
  MGS     = Imports of goods and services
  GPM     = Gross domestic product (verify cross-check vs ANA_AGG)
  SDE     = Statistical discrepancy
SECTOR (CL_ANA_SECTOR) — pick:
  SSS     = All sectors (the headline)
  PHS     = Households
  GGS     = General government
  PSS     = Private
TSEST: 10 = Original, 20 = SA, 30 = Trend.
REGION: AUS = Australia.
FREQ: Q (quarterly).
"""

from __future__ import annotations

import sys

from imdr.domains.econ.abs_sdmx import ABSClient, SDMXSeries, fetch_series
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main


# Headline expenditure items — all SECTOR=SSS (all sectors), chain volume + SA
_EXPENDITURE_ITEMS = [
    ("FCE",     "FCE_TOTAL",         "Final consumption expenditure"),
    ("GFC",     "GFC_TOTAL",         "Gross fixed capital formation"),
    ("GFC_PBI", "GFC_PRIVATE_BUS",   "Gross fixed capital formation — total private business investment"),
    ("GFC_DWL", "GFC_DWELLINGS",     "Gross fixed capital formation — dwellings (housing)"),
    ("GFC_EQP", "GFC_EQUIPMENT",     "Gross fixed capital formation — machinery and equipment"),
    ("GFC_IPP", "GFC_IPP",           "Gross fixed capital formation — intellectual property products"),
    ("GFC_NDC", "GFC_NON_DWELL_CON", "Gross fixed capital formation — non-dwelling construction"),
    ("IST",     "INVENTORY_CHG",     "Changes in inventories"),
    ("DFD",     "DFD",               "Domestic final demand"),
    ("GNE",     "GNE",               "Gross national expenditure"),
    ("XGS",     "EXPORTS",           "Exports of goods and services"),
    ("MGS",     "IMPORTS",           "Imports of goods and services"),
    ("GPM",     "GDP_VCH",           "GDP (expenditure measure, ANA_EXP)"),
]

# Sector-specific consumption (household vs general government)
_SECTOR_FCE = [
    ("PHS", "HOUSEHOLD",   "Household final consumption"),
    ("GGS", "GOVERNMENT",  "General government final consumption"),
]


def _build_series() -> list[SDMXSeries]:
    out: list[SDMXSeries] = []
    # Chain volume SA Q — all-sectors aggregate items
    for item, code, label in _EXPENDITURE_ITEMS:
        out.append(SDMXSeries(
            dataflow="ANA_EXP", key=f"VCH.{item}.SSS.20.AUS.Q",
            imdr_code=f"ABS.GDPE.{code}_REAL_SA.AU",
            display_name=f"ABS GDP-E {label} (Real, SA, $m)",
            unit="aud_mn", frequency="QUARTERLY", category="gdp", is_sa=True,
        ))
    # FCE by sector — household + government
    for sector, code, label in _SECTOR_FCE:
        out.append(SDMXSeries(
            dataflow="ANA_EXP", key=f"VCH.FCE.{sector}.20.AUS.Q",
            imdr_code=f"ABS.GDPE.FCE_{code}_REAL_SA.AU",
            display_name=f"ABS GDP-E {label} (Real, SA, $m)",
            unit="aud_mn", frequency="QUARTERLY", category="gdp", is_sa=True,
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
            print(f"  {spec.imdr_code:<48s} {len(obs):>5} obs")
    return indicators, observations


def main() -> int:
    return run_main(vendor="abs", topic="gdp_expenditure", fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "",
                    country_code="AU")


if __name__ == "__main__":
    sys.exit(main())
