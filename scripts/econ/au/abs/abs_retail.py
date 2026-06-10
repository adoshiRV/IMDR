"""ABS Retail Trade (RT) playground fetch.

Dataflow: RT. Key shape: {MEASURE}.{INDUSTRY}.{TSEST}.{REGION}.{FREQ}.

MEASURE: M1 = Current prices ($), M2 = QoQ %,
         M3 = Chain volume measures (real $), M4 = Chain volume QoQ %.
INDUSTRY: 20 = Total; 41 = Food retailing; 42 = Household goods;
          43 = Clothing/footwear; 44 = Department stores; 45 = Other retailing;
          46 = Cafes/restaurants.
TSEST: 10 = Original, 20 = Seasonally Adjusted, 30 = Trend.
REGION: AUS = Australia.
FREQ: M (monthly) for current prices; Q for chain volume.
"""

from __future__ import annotations

import sys

from imdr.domains.econ.abs_sdmx import ABSClient, SDMXSeries, fetch_series
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main


_CATEGORIES = [
    ("20", "TOTAL",            "Total retail"),
    ("41", "FOOD",             "Food retailing"),
    ("42", "HOUSEHOLD_GOODS",  "Household goods retailing"),
    ("43", "CLOTHING",         "Clothing, footwear and personal accessory retailing"),
    ("44", "DEPARTMENT",       "Department stores"),
    ("45", "OTHER",            "Other retailing"),
    ("46", "CAFES_RESTAURANTS", "Cafes, restaurants and takeaway food services"),
]


def _build_series() -> list[SDMXSeries]:
    out: list[SDMXSeries] = []
    # Headline = total nominal monthly, SA
    out.append(SDMXSeries(
        dataflow="RT", key="M1.20.20.AUS.M",
        imdr_code="ABS.RT.TOTAL_NOMINAL_SA.AU",
        display_name="ABS Retail Trade Total current prices (SA, monthly, $m)",
        unit="aud_mn", frequency="MONTHLY", category="other", is_sa=True,
    ))
    out.append(SDMXSeries(
        dataflow="RT", key="M2.20.20.AUS.M",
        imdr_code="ABS.RT.TOTAL_MOM_SA.AU",
        display_name="ABS Retail Trade Total current prices MoM % (SA)",
        unit="pct_mom", frequency="MONTHLY", category="other", is_sa=True,
    ))
    # Total chain volume (real) — quarterly
    out.append(SDMXSeries(
        dataflow="RT", key="M3.20.20.AUS.Q",
        imdr_code="ABS.RT.TOTAL_REAL_SA.AU",
        display_name="ABS Retail Trade Total chain volume (Real, SA, quarterly, $m)",
        unit="aud_mn", frequency="QUARTERLY", category="other", is_sa=True,
    ))
    out.append(SDMXSeries(
        dataflow="RT", key="M4.20.20.AUS.Q",
        imdr_code="ABS.RT.TOTAL_REAL_QOQ_SA.AU",
        display_name="ABS Retail Trade Total chain volume QoQ % (Real, SA)",
        unit="pct_qoq", frequency="QUARTERLY", category="other", is_sa=True,
    ))
    # Category-level nominals, SA monthly
    for ind_id, code, label in _CATEGORIES[1:]:
        out.append(SDMXSeries(
            dataflow="RT", key=f"M1.{ind_id}.20.AUS.M",
            imdr_code=f"ABS.RT.{code}_NOMINAL_SA.AU",
            display_name=f"ABS Retail Trade {label} current prices (SA, monthly, $m)",
            unit="aud_mn", frequency="MONTHLY", category="other", is_sa=True,
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
    return run_main(vendor="abs", topic="retail", fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "",
                    country_code="AU")


if __name__ == "__main__":
    sys.exit(main())
