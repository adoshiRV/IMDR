"""ABS Balance of Payments — Goods (BOP_GOODS) playground fetch.

Dataflow: BOP_GOODS. Key shape: {MEASURE}.{DATA_ITEM}.{EXP_IMP}.{TSEST}.{FREQ}.

MEASURE: 1 = Current Prices ($), 2 = Chain Volume, 3 = Implicit Price Index,
         4 = Terms of Trade.
DATA_ITEM (CL_BOP_TRADE) headlines:
  1000 = Total goods credits (exports total)
  1050 = Total general merchandise (exports)
  1100 = Total rural goods (exports)
  1350 = Total non-rural goods (exports)
  2000 = Total goods debits (imports total)
  2050 = Total general merchandise (imports)
  2100 = Total consumption goods (imports)
EXP_IMP: EXP or IMP — paired with DATA_ITEM (exports use credit codes, imports debit).
TSEST: 10 = Original, 20 = SA.
FREQ: Q (quarterly).
"""

from __future__ import annotations

import sys

from imdr.domains.econ.abs_sdmx import ABSClient, SDMXSeries, fetch_series
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main


def _build_series() -> list[SDMXSeries]:
    out: list[SDMXSeries] = []
    # Exports — current prices SA Q
    for item, code, label in [
        ("1000", "EXPORTS_TOTAL",          "Total goods exports"),
        ("1050", "EXPORTS_GENERAL_MERCH",  "Total general merchandise exports"),
        ("1100", "EXPORTS_RURAL",          "Total rural goods exports"),
        ("1350", "EXPORTS_NON_RURAL",      "Total non-rural goods exports"),
    ]:
        out.append(SDMXSeries(
            dataflow="BOP_GOODS", key=f"2.{item}.EXP.10.Q",
            imdr_code=f"ABS.BOP_GOODS.{code}_REAL.AU",
            display_name=f"ABS BoP Goods — {label} (Chain Volume, NSA, AUD m)",
            unit="aud_mn", frequency="QUARTERLY", category="bop", is_sa=False,
        ))
    # Imports — chain volume NSA Q (MEASURE=2 TSEST=10 is the live cut)
    for item, code, label in [
        ("2000", "IMPORTS_TOTAL",         "Total goods imports"),
        ("2050", "IMPORTS_GENERAL_MERCH", "Total general merchandise imports"),
        ("2100", "IMPORTS_CONSUMPTION",   "Total consumption-goods imports"),
    ]:
        out.append(SDMXSeries(
            dataflow="BOP_GOODS", key=f"2.{item}.IMP.10.Q",
            imdr_code=f"ABS.BOP_GOODS.{code}_REAL.AU",
            display_name=f"ABS BoP Goods — {label} (Chain Volume, NSA, AUD m)",
            unit="aud_mn", frequency="QUARTERLY", category="bop", is_sa=False,
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
    return run_main(vendor="abs", topic="bop_goods", fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "",
                    country_code="AU")


if __name__ == "__main__":
    sys.exit(main())
