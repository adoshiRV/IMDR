"""ABS Balance of Payments (BOP) playground fetch.

Dataflow: BOP. Key shape: {MEASURE}.{DATA_ITEM}.{TSEST}.{FREQ}.

MEASURE: 1 = Current Prices ($), 2 = Chain Volume, 3 = Implicit Price Index,
         4 = Terms of Trade, 5 = Chain Laspeyres Price Indexes.
DATA_ITEM (CL_BOP_ITEM) — desk-relevant headlines:
  100  = Current account
  8700 = Primary income
  8100 = Secondary income
  8305 = Capital account
  8800 = Financial account
  8805 = Financial account, Direct investment
  8820 = Financial account, Portfolio investment
  8835 = Financial account, Financial derivatives
  8850 = Financial account, Other investment
  8865 = Financial account, Reserve assets
  8900 = Net errors and omissions
TSEST: 10 = Original, 20 = SA.
FREQ: Q (quarterly).
"""

from __future__ import annotations

import sys

from imdr.domains.econ.abs_sdmx import ABSClient, SDMXSeries, fetch_series
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main


_BOP_HEADLINES = [
    ("100",  "CA_TOTAL",         "Current account"),
    ("8700", "PRIMARY_INCOME",   "Primary income (net)"),
    ("8100", "SECONDARY_INCOME", "Secondary income (net)"),
    ("8305", "CAPITAL_ACCT",     "Capital account"),
    ("8800", "FA_TOTAL",         "Financial account (net)"),
    ("8805", "FA_DIRECT_INV",    "Financial account, Direct investment (net)"),
    ("8820", "FA_PORTFOLIO_INV", "Financial account, Portfolio investment (net)"),
    ("8835", "FA_DERIVATIVES",   "Financial account, Financial derivatives (net)"),
    ("8850", "FA_OTHER_INV",     "Financial account, Other investment (net)"),
    ("8865", "FA_RESERVES",      "Financial account, Reserve assets (net)"),
    ("8900", "NET_ERR_OMIS",     "Net errors and omissions"),
]


def _build_series() -> list[SDMXSeries]:
    out: list[SDMXSeries] = []
    # CA/Primary/Secondary headlines have both SA + NSA cuts (TSEST=20).
    # Capital, Financial-account, and Net Err & Omis only have NSA (TSEST=10).
    _SA_AVAIL = {"100", "8700", "8100"}
    for item, code, label in _BOP_HEADLINES:
        if item in _SA_AVAIL:
            out.append(SDMXSeries(
                dataflow="BOP", key=f"1.{item}.20.Q",
                imdr_code=f"ABS.BOP.{code}_SA.AU",
                display_name=f"ABS Balance of Payments — {label} (SA, current prices, AUD m)",
                unit="aud_mn", frequency="QUARTERLY", category="bop", is_sa=True,
            ))
        out.append(SDMXSeries(
            dataflow="BOP", key=f"1.{item}.10.Q",
            imdr_code=f"ABS.BOP.{code}_NSA.AU",
            display_name=f"ABS Balance of Payments — {label} (NSA, current prices, AUD m)",
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
            print(f"  {spec.imdr_code:<45s} {len(obs):>5} obs")
    return indicators, observations


def main() -> int:
    return run_main(vendor="abs", topic="bop", fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "",
                    country_code="AU")


if __name__ == "__main__":
    sys.exit(main())
