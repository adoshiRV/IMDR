"""ABS Producer Price Index — Final Demand (PPI_FD) playground fetch.

Dataflow: PPI_FD. Key shape: {MEASURE}.{INDEX}.{SOURCE}.{DESTINATION}.{FREQ}.

MEASURE: 1 = Index Number, 2 = % Chg prev period, 3 = % Chg YoY,
         4 = Points contribution to total index.
INDEX: TOT = Total All Industries (the headline).
SOURCE: TOT = Total, DOM = Domestic, IMP = Import.
DESTINATION: TOTXE = Total (excl. exports — the headline, only quarterly cut
             with MEASURE=1/2/3 published), TOTIE = Total (incl. exports —
             404s in the SDMX API as of 2026-06-09), CON = Consumer,
             KAP = Capital, EXP = Exports.
FREQ: Q (quarterly).

The PPI_FD is the RBA-quoted "Final Demand" PPI — the cleanest pipeline-
inflation signal at producer level. Sub-bullets here cover the
SOURCE × DESTINATION breakdown to decompose imported vs domestic pressure.
"""

from __future__ import annotations

import sys

from imdr.domains.econ.abs_sdmx import ABSClient, SDMXSeries, fetch_series
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main


def _build_series() -> list[SDMXSeries]:
    out: list[SDMXSeries] = []
    # Headline — TOTXE final demand
    for measure, code, label, unit in [
        ("1", "TOTAL_INDEX",        "PPI Final Demand Total (Index, NSA)",          "index"),
        ("2", "TOTAL_QOQ",          "PPI Final Demand Total (QoQ %, NSA)",          "pct_qoq"),
        ("3", "TOTAL_YOY",          "PPI Final Demand Total (YoY %, NSA)",          "pct_yoy"),
    ]:
        out.append(SDMXSeries(
            dataflow="PPI_FD", key=f"{measure}.TOT.TOT.TOTXE.Q",
            imdr_code=f"ABS.PPI_FD.{code}.AU",
            display_name=label,
            unit=unit, frequency="QUARTERLY", category="other", is_sa=False,
        ))
    # Source decomposition — domestic vs import
    for source, source_label in [("DOM", "DOMESTIC"), ("IMP", "IMPORT")]:
        out.append(SDMXSeries(
            dataflow="PPI_FD", key=f"3.TOT.{source}.TOTXE.Q",
            imdr_code=f"ABS.PPI_FD.{source_label}_YOY.AU",
            display_name=f"PPI Final Demand {source_label.title()} source (YoY %, NSA)",
            unit="pct_yoy", frequency="QUARTERLY", category="other", is_sa=False,
        ))
    # NOTE: Destination=CON / KAP / EXP only exist in MEASURE=4 (Points
    # contribution to total index) per the wildcard probe — no quarterly YoY
    # cut at DESTINATION level. The TOTXE total already captures the
    # ex-exports headline. Decomposition skipped.
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
    return run_main(vendor="abs", topic="ppi_fd", fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "",
                    country_code="AU")


if __name__ == "__main__":
    sys.exit(main())
