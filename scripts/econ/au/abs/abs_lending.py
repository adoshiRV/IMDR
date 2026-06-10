"""ABS Lending Indicators (LEND_HOUSING + LEND_BUSINESS + LEND_PERSONAL).

Three sibling dataflows; combined into one fetcher to keep credit-cycle
indicators together.

LEND_HOUSING key shape:
  {MEASURE}.{DATA_ITEM}.{LOAN_TYPE}.{LOAN_PURPOSE}.{LENDER_TYPE}.{HOUSING_PURPOSE}.{TSEST}.{REGION}.{FREQ}

LEND_BUSINESS key shape:
  {MEASURE}.{DATA_ITEM}.{LOAN_TYPE}.{LOAN_PURPOSE}.{LENDER_TYPE}.{BUSINESS_SIZE}.{TSEST}.{REGION}.{FREQ}

LEND_PERSONAL key shape:
  {MEASURE}.{DATA_ITEM}.{LOAN_TYPE}.{LOAN_PURPOSE}.{LENDER_TYPE}.{TSEST}.{REGION}.{FREQ}

Common codes (verified live 2026-06-09):
  MEASURE: FIN_VAL = Value (dollars), FIN_NUM = Number of commitments.
  DATA_ITEM: NEWCOMMITS = New loan commitments (the headline).
  LOAN_TYPE: DV8270 = Fixed term loans, DV8368 = Fixed term + revolving credit,
             DV8575 = Total (fixed term + revolving + other finance).
  LOAN_PURPOSE: DV8348 = Total housing, DV8344 = Refinancing, DV8349 = Other.
  LENDER_TYPE: TOT = Total lender type.
  HOUSING_PURPOSE: DV5167 = Owner occupier, DV5168 = Investor, TOT_FHB = First-home buyers.
  BUSINESS_SIZE: DV8604 / DV8605 / DV8606 (sizes); TOT = Total.
  TSEST: 10 = Original, 20 = SA, 30 = Trend.
  REGION: AUS = national.
  FREQ: M (monthly).
"""
from __future__ import annotations

import sys

from imdr.domains.econ.abs_sdmx import ABSClient, SDMXSeries, fetch_series
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main


def _build_series() -> list[SDMXSeries]:
    out: list[SDMXSeries] = []

    # ------------------------------------------------------------------
    # LEND_HOUSING — new commitments, total + owner-occupier + investor, SA
    # ------------------------------------------------------------------
    for purpose, code, label in [
        ("DV5167", "OWNER_OCC",   "Owner occupier"),
        ("DV5168", "INVESTOR",    "Investor"),
        ("TOT_FHB", "FIRST_HOME", "First-home buyers (total)"),
    ]:
        out.append(SDMXSeries(
            dataflow="LEND_HOUSING",
            key=f"FIN_VAL.NEWCOMMITS.DV8368.DV8348.TOT.{purpose}.20.AUS.Q",
            imdr_code=f"ABS.LEND.HOUSING_{code}_VALUE_SA.AU",
            display_name=f"ABS Lending Indicators — Housing, {label}, new loan commitments value (SA, AUD m)",
            unit="aud_mn", frequency="QUARTERLY", category="credit", is_sa=True,
        ))
        out.append(SDMXSeries(
            dataflow="LEND_HOUSING",
            key=f"FIN_NUM.NEWCOMMITS.DV8368.DV8348.TOT.{purpose}.20.AUS.Q",
            imdr_code=f"ABS.LEND.HOUSING_{code}_NUM_SA.AU",
            display_name=f"ABS Lending Indicators — Housing, {label}, new loan commitments count (SA)",
            unit="count", frequency="QUARTERLY", category="credit", is_sa=True,
        ))

    # ------------------------------------------------------------------
    # LEND_BUSINESS — new commitments by purpose, SA national
    # ------------------------------------------------------------------
    for purpose, code, label in [
        ("DV4969", "CONSTRUCTION", "Business — construction"),
        ("DV4970", "PURCHASE_PROPERTY", "Business — property purchase"),
    ]:
        out.append(SDMXSeries(
            dataflow="LEND_BUSINESS",
            key=f"FIN_VAL.NEWCOMMITS.DV8270.{purpose}.TOT.TOT.20.AUS.Q",
            imdr_code=f"ABS.LEND.BUSINESS_{code}_VALUE_SA.AU",
            display_name=f"ABS Lending Indicators — {label}, new loan commitments value (SA, AUD m)",
            unit="aud_mn", frequency="QUARTERLY", category="credit", is_sa=True,
        ))

    # ------------------------------------------------------------------
    # LEND_PERSONAL — new commitments, total + by purpose, SA national
    # ------------------------------------------------------------------
    for purpose, code, label in [
        ("TOTLOANPURP_EXCLREFIN", "TOTAL_EXCL_REFI", "Personal total ex-refinance"),
        ("DV8344",                "REFINANCE",       "Personal refinancing"),
        ("DV8348",                "PROPERTY",        "Personal — for property purchase"),
        ("DV8349",                "VEHICLE",         "Personal — for vehicle"),
        ("PERSONALOTH",           "OTHER",           "Personal — other purpose"),
    ]:
        out.append(SDMXSeries(
            dataflow="LEND_PERSONAL",
            key=f"FIN_VAL.NEWCOMMITS.DV8270.{purpose}.TOT.20.AUS.Q",
            imdr_code=f"ABS.LEND.PERSONAL_{code}_VALUE_SA.AU",
            display_name=f"ABS Lending Indicators — {label}, new loan commitments value (SA, AUD m)",
            unit="aud_mn", frequency="QUARTERLY", category="credit", is_sa=True,
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
            print(f"  {spec.imdr_code:<55s} {len(obs):>5} obs")
    return indicators, observations


def main() -> int:
    return run_main(vendor="abs", topic="lending", fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "",
                    country_code="AU")


if __name__ == "__main__":
    sys.exit(main())
