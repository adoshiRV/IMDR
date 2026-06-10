"""ABS Residential Property Price Index (RPPI) playground fetch.

Dataflow: RPPI. Key shape: {MEASURE}.{PROPERTY_TYPE}.{REGION}.{FREQ}.

MEASURE (CL_RPPI_MEASURES):
  1 = Index Number, 2 = % Chg prev period, 3 = % Chg YoY.
PROPERTY_TYPE (CL_RPPI_PROP_TYPE):
  3 = Residential property (the headline), 2 = Established houses, 1 = Attached dwellings.
REGION (CL_GCCSA): 100 = Weighted average of 8 capital cities (national headline);
  1GSYD / 2GMEL / 3GBRI / 4GADE / 5GPER / 6GHOB / 7GDAR / 8ACTE = individual cities.
FREQ: Q (quarterly).

Note: probe (2026-06-09) showed RPPI sample data only through 2021-Q4 — this
dataflow may be partially stale relative to the latest ABS publication.
"""
from __future__ import annotations

import sys

from imdr.domains.econ.abs_sdmx import ABSClient, SDMXSeries, fetch_series
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main


_CAPITAL_CITIES = [
    ("1GSYD", "SYDNEY"),
    ("2GMEL", "MELBOURNE"),
    ("3GBRI", "BRISBANE"),
    ("4GADE", "ADELAIDE"),
    ("5GPER", "PERTH"),
    ("6GHOB", "HOBART"),
    ("7GDAR", "DARWIN"),
    ("8ACTE", "CANBERRA"),
]


def _build_series() -> list[SDMXSeries]:
    out: list[SDMXSeries] = []
    # National headline — Index + QoQ + YoY for all 3 property types
    for prop_id, prop_code, prop_label in [("3", "RESIDENTIAL", "Residential property"),
                                            ("2", "ESTABLISHED_HOUSES", "Established houses"),
                                            ("1", "ATTACHED_DWELLINGS", "Attached dwellings")]:
        for measure, suffix, unit, label_suffix in [
            ("1", "INDEX", "index",  "(Index)"),
            ("2", "QOQ",   "pct_qoq", "(QoQ %)"),
            ("3", "YOY",   "pct_yoy", "(YoY %)"),
        ]:
            out.append(SDMXSeries(
                dataflow="RPPI", key=f"{measure}.{prop_id}.100.Q",
                imdr_code=f"ABS.RPPI.{prop_code}_{suffix}.AU",
                display_name=f"ABS RPPI {prop_label}, weighted avg 8 capital cities {label_suffix}",
                unit=unit, frequency="QUARTERLY", category="housing", is_sa=False,
            ))
    # Capital cities — residential property only, Index
    for region, name in _CAPITAL_CITIES:
        out.append(SDMXSeries(
            dataflow="RPPI", key=f"1.3.{region}.Q",
            imdr_code=f"ABS.RPPI.RESIDENTIAL_{name}.AU",
            display_name=f"ABS RPPI Residential property, {name.title()} (Index)",
            unit="index", frequency="QUARTERLY", category="housing", is_sa=False,
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
    return run_main(vendor="abs", topic="rppi", fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "",
                    country_code="AU")


if __name__ == "__main__":
    sys.exit(main())
