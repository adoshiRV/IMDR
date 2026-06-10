"""ABS National Accounts Key Aggregates playground fetch.

Dataflow: ANA_AGG. Key shape: {MEASURE}.{DATA_ITEM}.{TSEST}.{REGION}.{FREQ}.

MEASURE:    M1 = Chain volume measures (real),
            M2 = Chain volume measures, percentage change,
            M3 = Current prices (nominal),
            M4 = Current prices, percentage change,
            M5 = Price deflator (index),
            M6 = Price deflator, percentage change.
DATA_ITEM:  GPM = Gross domestic product (headline),
            GNI = Gross national income,
            GPM_PCA = GDP per capita,
            GVA_MKT = Gross value added market sector,
            NDP = Net domestic product,
            NNDI = Real net national disposable income,
            RDI = Real gross domestic income.
TSEST:      10 = Original, 20 = SA, 30 = Trend.
REGION:     AUS = Australia (national).
FREQ:       Q (quarterly).

Verified live (2026-06-09): MEASURE x DATA_ITEM x TSEST x AUS x Q.
"""

from __future__ import annotations

import sys

from imdr.domains.econ.abs_sdmx import ABSClient, SDMXSeries, fetch_series
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main


def _build_series() -> list[SDMXSeries]:
    return [
        # Real (chain volume) — Seasonally Adjusted
        SDMXSeries(
            dataflow="ANA_AGG", key="M1.GPM.20.AUS.Q",
            imdr_code="ABS.GDP.REAL_SA.AU",
            display_name="ABS GDP Australia, chain volume measure (Real, SA, $m)",
            unit="aud_mn", frequency="QUARTERLY", category="gdp", is_sa=True,
        ),
        SDMXSeries(
            dataflow="ANA_AGG", key="M2.GPM.20.AUS.Q",
            imdr_code="ABS.GDP.REAL_QOQ_SA.AU",
            display_name="ABS GDP Australia, chain volume measure QoQ % (SA)",
            unit="pct_qoq", frequency="QUARTERLY", category="gdp", is_sa=True,
        ),
        # Nominal — SA
        SDMXSeries(
            dataflow="ANA_AGG", key="M3.GPM.20.AUS.Q",
            imdr_code="ABS.GDP.NOMINAL_SA.AU",
            display_name="ABS GDP Australia, current prices (Nominal, SA, $m)",
            unit="aud_mn", frequency="QUARTERLY", category="gdp", is_sa=True,
        ),
        # GDP deflator
        SDMXSeries(
            dataflow="ANA_AGG", key="M5.GPM.20.AUS.Q",
            imdr_code="ABS.GDP.DEFLATOR_SA.AU",
            display_name="ABS GDP Australia, price deflator (index, SA)",
            unit="index", frequency="QUARTERLY", category="gdp", is_sa=True,
        ),
        # GDP per capita — real, SA
        SDMXSeries(
            dataflow="ANA_AGG", key="M1.GPM_PCA.20.AUS.Q",
            imdr_code="ABS.GDP.PER_CAPITA_REAL_SA.AU",
            display_name="ABS GDP per capita Australia, chain volume (Real, SA)",
            unit="aud", frequency="QUARTERLY", category="gdp", is_sa=True,
        ),
        # Gross National Income — real SA + QoQ
        SDMXSeries(
            dataflow="ANA_AGG", key="M1.GNI.20.AUS.Q",
            imdr_code="ABS.GDP.GNI_REAL_SA.AU",
            display_name="ABS Gross National Income Australia, chain volume (Real, SA, $m)",
            unit="aud_mn", frequency="QUARTERLY", category="gdp", is_sa=True,
        ),
        SDMXSeries(
            dataflow="ANA_AGG", key="M1.NNDI.20.AUS.Q",
            imdr_code="ABS.GDP.NNDI_REAL_SA.AU",
            display_name="ABS Real Net National Disposable Income Australia (Real, SA, $m)",
            unit="aud_mn", frequency="QUARTERLY", category="gdp", is_sa=True,
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
    return run_main(vendor="abs", topic="gdp", fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "",
                    country_code="AU")


if __name__ == "__main__":
    sys.exit(main())
