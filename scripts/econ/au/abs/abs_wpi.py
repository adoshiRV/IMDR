"""ABS Wage Price Index (WPI) playground fetch.

Dataflow: WPI. Key shape: {MEASURE}.{INDEX}.{SECTOR}.{INDUSTRY}.{TSEST}.{REGION}.{FREQ}.

MEASURE: 1 = Quarterly Index, 2 = QoQ %, 3 = YoY % (the RBA's headline cut).
INDEX (CL_WPI_PCI):
  OHRPEB = Ordinary time hourly rates of pay, excluding bonuses (the headline)
  OHRPIB = Ordinary time hourly rates of pay, including bonuses
  THRPEB = Total hourly rates of pay, excluding bonuses
  THRPIB = Total hourly rates of pay, including bonuses
SECTOR: 7 = Private and Public (the headline); 1 = Private; 2 = Public.
INDUSTRY: TOT = All industries.
TSEST: 10 = Original (NNSA), 20 = Seasonally Adjusted, 30 = Trend.
REGION: AUS = Australia (national).
FREQ: Q (quarterly).
"""

from __future__ import annotations

import sys

from imdr.domains.econ.abs_sdmx import ABSClient, SDMXSeries, fetch_series
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main


def _build_series() -> list[SDMXSeries]:
    out: list[SDMXSeries] = []
    # Ordinary time hourly rates, excl. bonuses — the RBA-quoted wage metric
    for measure, code, label, unit in [
        ("1", "OHRPEB_INDEX_NSA",  "WPI ordinary time hourly rates ex-bonus (Index, NSA)",      "index"),
        ("2", "OHRPEB_QOQ_NSA",    "WPI ordinary time hourly rates ex-bonus (QoQ %, NSA)",      "pct_qoq"),
        ("3", "OHRPEB_YOY_NSA",    "WPI ordinary time hourly rates ex-bonus (YoY %, NSA)",      "pct_yoy"),
    ]:
        out.append(SDMXSeries(
            dataflow="WPI", key=f"{measure}.OHRPEB.7.TOT.10.AUS.Q",
            imdr_code=f"ABS.WPI.{code}.AU",
            display_name=label,
            unit=unit, frequency="QUARTERLY", category="labour", is_sa=False,
        ))
    # Total hourly rates incl bonuses (broader wage measure)
    out.append(SDMXSeries(
        dataflow="WPI", key="3.THRPIB.7.TOT.10.AUS.Q",
        imdr_code="ABS.WPI.THRPIB_YOY_NSA.AU",
        display_name="WPI total hourly rates incl bonuses (YoY %, NSA)",
        unit="pct_yoy", frequency="QUARTERLY", category="labour", is_sa=False,
    ))
    # Private vs Public sector — YoY %, SA
    out.append(SDMXSeries(
        dataflow="WPI", key="3.OHRPEB.1.TOT.10.AUS.Q",
        imdr_code="ABS.WPI.OHRPEB_YOY_PRIVATE_NSA.AU",
        display_name="WPI ordinary time hourly rates ex-bonus, Private sector (YoY %, NSA)",
        unit="pct_yoy", frequency="QUARTERLY", category="labour", is_sa=False,
    ))
    out.append(SDMXSeries(
        dataflow="WPI", key="3.OHRPEB.2.TOT.10.AUS.Q",
        imdr_code="ABS.WPI.OHRPEB_YOY_PUBLIC_NSA.AU",
        display_name="WPI ordinary time hourly rates ex-bonus, Public sector (YoY %, NSA)",
        unit="pct_yoy", frequency="QUARTERLY", category="labour", is_sa=False,
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
            print(f"  {spec.imdr_code:<50s} {len(obs):>5} obs")
    return indicators, observations


def main() -> int:
    return run_main(vendor="abs", topic="wpi", fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "",
                    country_code="AU")


if __name__ == "__main__":
    sys.exit(main())
