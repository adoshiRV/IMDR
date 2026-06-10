"""ABS International Investment Position (IIP) playground fetch.

Dataflow: IIP. Key shape:
  {MEASURE}.{DATA_ITEM}.{SECTOR}.{MATURITY}.{INDUSTRY}.{CURRENCY}.{TSEST}.{FREQ}

We pin everything except DATA_ITEM:
  MEASURE  = 6   (Position at end of period — the stock)
  SECTOR   = TOT (sectoral breakdown is not published at this dim level)
  MATURITY = TOT
  INDUSTRY = T
  CURRENCY = 700 (AUD — only currency code with data at the headline cuts)
  TSEST    = 10  (Original / NSA)
  FREQ     = Q

Functional sub-decomposition lives inside DATA_ITEM, not in the sector or
maturity axes (probed 2026-06-10 — see `discovery/iip_findings.md`).

Sign convention: ABS records Foreign Assets with **negative sign** in MEASURE=6,
preserving the BoP debit convention into the stock view. Net IIP = FA + FL in
raw ABS units; positive Net IIP reads as net liability (debtor) position. Raw
values stored as published; analytics layer flips signs for reader-facing
display.

Fills wiring-map cell 3.3 stock-side (replaces the dropped BOP_FACTOR attempt).
"""

from __future__ import annotations

import sys

from imdr.domains.econ.abs_sdmx import ABSClient, SDMXSeries, fetch_series
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main


# Each tuple: (DATA_ITEM, suffix, display label). Grouped visually below.
_IIP_SERIES: list[tuple[str, str, str]] = [
    # ----- Headline (9) -----
    ("1300A", "NET_IIP",                       "Net International Investment Position"),
    ("1100A", "NET_FOREIGN_EQUITY",            "Net Foreign Equity"),
    ("1100B", "NET_FOREIGN_DEBT",              "Net Foreign Debt"),
    ("1200A", "FA_TOTAL",                      "Total Foreign Assets (gross)"),
    ("1250A", "FL_TOTAL",                      "Total Foreign Liabilities (gross)"),
    ("900A",  "FA_TOTAL_EQUITY",               "Foreign Assets, Total Equity"),
    ("902A",  "FL_TOTAL_EQUITY",               "Foreign Liabilities, Total Equity"),
    ("903A",  "FL_TOTAL_DEBT",                 "Foreign Liabilities, Total foreign debt"),
    ("904A",  "FL_GROSS_EXTERNAL_DEBT",        "Foreign Liabilities, Gross External Debt"),
    # ----- Direct investment (6) -----
    ("800A",  "FA_DIRECT_INV",                 "Foreign Assets, Direct Investment"),
    ("601A",  "FA_DIRECT_INV_EQUITY",          "Foreign Assets, Direct Investment, Equity"),
    ("601C",  "FA_DIRECT_INV_DEBT",            "Foreign Assets, Direct Investment, Debt"),
    ("850A",  "FL_DIRECT_INV",                 "Foreign Liabilities, Direct Investment"),
    ("650A",  "FL_DIRECT_INV_EQUITY",          "Foreign Liabilities, Direct Investment, Equity"),
    ("652A",  "FL_DIRECT_INV_DEBT",            "Foreign Liabilities, Direct Investment, Debt"),
    # ----- Portfolio investment (6) -----
    ("801A",  "FA_PORTFOLIO_INV",              "Foreign Assets, Portfolio Investment"),
    ("602A",  "FA_PORTFOLIO_INV_EQUITY",       "Foreign Assets, Portfolio Investment, Equity"),
    ("602C",  "FA_PORTFOLIO_INV_DEBT",         "Foreign Assets, Portfolio Investment, Debt securities"),
    ("851A",  "FL_PORTFOLIO_INV",              "Foreign Liabilities, Portfolio Investment"),
    ("555A",  "FL_PORTFOLIO_INV_EQUITY",       "Foreign Liabilities, Portfolio Investment, Equity"),
    ("653B",  "FL_PORTFOLIO_INV_DEBT",         "Foreign Liabilities, Portfolio Investment, Debt securities"),
    # ----- Other investment (2) -----
    ("802A",  "FA_OTHER_INV",                  "Foreign Assets, Other Investment"),
    ("852A",  "FL_OTHER_INV",                  "Foreign Liabilities, Other Investment"),
    # ----- Financial derivatives (2) -----
    ("509A",  "FA_FIN_DERIV",                  "Foreign Assets, Financial Derivatives"),
    ("558A",  "FL_FIN_DERIV",                  "Foreign Liabilities, Financial Derivatives"),
    # ----- Reserve assets (8) -----
    ("820A",  "FA_RESERVE_ASSETS",             "Foreign Assets, Reserve Assets"),
    ("420A",  "FA_RESERVE_CURR_DEPOSITS",      "Foreign Assets, Reserve Assets, Currency and Deposits"),
    ("220F",  "FA_RESERVE_DEBT_SECURITIES",    "Foreign Assets, Reserve Assets, Debt Securities"),
    ("220S",  "FA_RESERVE_DEBT_SHORT",         "Foreign Assets, Reserve Assets, Debt Securities, Short term"),
    ("220M",  "FA_RESERVE_DEBT_LONG",          "Foreign Assets, Reserve Assets, Debt Securities, Long term"),
    ("520A",  "FA_RESERVE_MONETARY_GOLD",      "Foreign Assets, Reserve Assets, Monetary Gold"),
    ("520B",  "FA_RESERVE_SDR",                "Foreign Assets, Reserve Assets, SDRs"),
    ("520D",  "FA_RESERVE_OTHER",              "Foreign Assets, Reserve Assets, Other Reserve Assets"),
]


def _build_series() -> list[SDMXSeries]:
    out: list[SDMXSeries] = []
    for data_item, suffix, label in _IIP_SERIES:
        out.append(SDMXSeries(
            dataflow="IIP",
            key=f"6.{data_item}.TOT.TOT.T.700.10.Q",
            imdr_code=f"ABS.IIP.{suffix}.AU",
            display_name=f"ABS IIP — {label} (Q stock, AUD m, NSA)",
            unit="aud_mn",
            frequency="QUARTERLY",
            category="instr_outstand",
            is_sa=False,
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
    return run_main(vendor="abs", topic="iip", fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "",
                    country_code="AU")


if __name__ == "__main__":
    sys.exit(main())
