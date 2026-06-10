"""ABS Private New Capital Expenditure (CAPEX) playground fetch.

Dataflow: CAPEX. Key shape:
  {MEASURE}.{PRICE_ADJUSTMENT}.{ASSET}.{INDUSTRY}.{TSEST}.{STATE}.{FREQ}.

MEASURE (CL_CAPEX_MEASURE):
  M1 = Actual Expenditure (the headline — what was actually spent),
  M2 = Short Term Expected Expenditure (next quarter survey response),
  M3 = Long Term Expected Expenditure (full FY ahead survey response).
PRICE_ADJUSTMENT (CL_PRICE_ADJUSTMENT):
  CUR = Current Price, CVM = Chain Volume (Real), IPD = Implicit Price Deflator.
ASSET (CL_CAPEX_ASSET):
  TOT = Total, 1 = Buildings and Structures, 2 = Equipment, Plant and Machinery.
INDUSTRY: TOT for all industries; otherwise ANZSIC code.
TSEST: 10 = Original, 20 = SA, 30 = Trend.
STATE: AUS = Australia, 1..8 = states.
FREQ: Q (quarterly).
"""
from __future__ import annotations

import sys

from imdr.domains.econ.abs_sdmx import ABSClient, SDMXSeries, fetch_series
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main


def _build_series() -> list[SDMXSeries]:
    out: list[SDMXSeries] = []
    # Actual expenditure — Total assets, Total industry, SA, national
    out.append(SDMXSeries(
        dataflow="CAPEX", key="M1.CVM.TOT.TOT.20.AUS.Q",
        imdr_code="ABS.CAPEX.ACTUAL_TOTAL_REAL_SA.AU",
        display_name="ABS CAPEX Actual Expenditure — Total assets / Total industry (Real, SA, AUD m)",
        unit="aud_mn", frequency="QUARTERLY", category="gdp", is_sa=True,
    ))
    out.append(SDMXSeries(
        dataflow="CAPEX", key="M1.CUR.TOT.TOT.20.AUS.Q",
        imdr_code="ABS.CAPEX.ACTUAL_TOTAL_NOMINAL_SA.AU",
        display_name="ABS CAPEX Actual Expenditure — Total assets / Total industry (Nominal, SA, AUD m)",
        unit="aud_mn", frequency="QUARTERLY", category="gdp", is_sa=True,
    ))
    # Buildings & Structures vs Equipment Plant & Machinery — chain volume SA
    for asset, code, label in [("1", "BUILDINGS", "Buildings and Structures"),
                                ("2", "EQUIPMENT", "Equipment, Plant and Machinery")]:
        out.append(SDMXSeries(
            dataflow="CAPEX", key=f"M1.CVM.{asset}.TOT.20.AUS.Q",
            imdr_code=f"ABS.CAPEX.ACTUAL_{code}_REAL_SA.AU",
            display_name=f"ABS CAPEX Actual Expenditure — {label} (Real, SA, AUD m)",
            unit="aud_mn", frequency="QUARTERLY", category="gdp", is_sa=True,
        ))
    # Expected expenditure — short-term + long-term forecasts (Total/Total, SA)
    for meas, code, label in [("M2", "EXPECTED_ST", "Short-term expected expenditure"),
                               ("M3", "EXPECTED_LT", "Long-term expected expenditure")]:
        out.append(SDMXSeries(
            dataflow="CAPEX", key=f"{meas}.CUR.TOT.TOT.20.AUS.Q",
            imdr_code=f"ABS.CAPEX.{code}_NOMINAL_SA.AU",
            display_name=f"ABS CAPEX {label} — Total assets / Total industry (Nominal, SA, AUD m)",
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
    return run_main(vendor="abs", topic="capex", fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "",
                    country_code="AU")


if __name__ == "__main__":
    sys.exit(main())
