"""RBA D2 + E1 + E2 + A2 fetcher.

Three wiring-map cells filled from this one module:

  - 4.1 Demand Transmission  -> D2 credit aggregates (owner-occupier /
        investor housing / business credit / total credit)
  - 4.2 Balance Sheets       -> E1 household + business balance sheets,
        E2 household-ratio series (debt/income, debt/assets)
  - 4.4 Policy Reaction      -> A2 cash-rate event log (extends RBA D3
        monetary aggregates already in DB)

All four CSVs are Playwright-captured snapshots in
``data/econ/au/rba/samples/{d2,e1,e2,a2}-data.csv``. Refresh
via ``rba_snapshot_refresh.py``.
"""
from __future__ import annotations

import sys

from imdr.domains.econ.rba_tables import RBASeries, fetch_specs
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main


_SERIES = [
    # ------------------------------------------------------------------
    # D2 — Lending and Credit Aggregates (cell 4.1)
    # ------------------------------------------------------------------
    RBASeries("d2", "DLCACN",       "RBA.CREDIT.TOTAL.AU",
              "RBA D2 Credit total (monthly, AUD m)", "aud_mn", "MONTHLY", "credit"),
    RBASeries("d2", "DLCACS",       "RBA.CREDIT.TOTAL_SA.AU",
              "RBA D2 Credit total (SA, monthly, AUD m)", "aud_mn", "MONTHLY", "credit", True),
    RBASeries("d2", "DLCACFN",      "RBA.CREDIT.TOTAL_EX_FIN.AU",
              "RBA D2 Credit total excluding financial businesses (monthly, AUD m)", "aud_mn", "MONTHLY", "credit"),
    RBASeries("d2", "DLCACFS",      "RBA.CREDIT.TOTAL_EX_FIN_SA.AU",
              "RBA D2 Credit total excluding financial businesses (SA, monthly, AUD m)", "aud_mn", "MONTHLY", "credit", True),
    RBASeries("d2", "DLCACOHN",     "RBA.CREDIT.OWNER_OCC_HOUSING.AU",
              "RBA D2 Credit; Owner-occupier housing (monthly, AUD m)", "aud_mn", "MONTHLY", "credit"),
    RBASeries("d2", "DLCACOHS",     "RBA.CREDIT.OWNER_OCC_HOUSING_SA.AU",
              "RBA D2 Credit; Owner-occupier housing (SA, monthly, AUD m)", "aud_mn", "MONTHLY", "credit", True),
    RBASeries("d2", "DLCACIHN",     "RBA.CREDIT.INVESTOR_HOUSING.AU",
              "RBA D2 Credit; Investor housing (monthly, AUD m)", "aud_mn", "MONTHLY", "credit"),
    RBASeries("d2", "DLCACIHS",     "RBA.CREDIT.INVESTOR_HOUSING_SA.AU",
              "RBA D2 Credit; Investor housing (SA, monthly, AUD m)", "aud_mn", "MONTHLY", "credit", True),
    RBASeries("d2", "DLCACOPN",     "RBA.CREDIT.OTHER_PERSONAL.AU",
              "RBA D2 Credit; Other personal (monthly, AUD m)", "aud_mn", "MONTHLY", "credit"),
    RBASeries("d2", "DLCACOPS",     "RBA.CREDIT.OTHER_PERSONAL_SA.AU",
              "RBA D2 Credit; Other personal (SA, monthly, AUD m)", "aud_mn", "MONTHLY", "credit", True),
    RBASeries("d2", "DLCACBN",      "RBA.CREDIT.BUSINESS.AU",
              "RBA D2 Credit; Business (monthly, AUD m)", "aud_mn", "MONTHLY", "credit"),
    RBASeries("d2", "DLCACBS",      "RBA.CREDIT.BUSINESS_SA.AU",
              "RBA D2 Credit; Business (SA, monthly, AUD m)", "aud_mn", "MONTHLY", "credit", True),
    RBASeries("d2", "DLCANCN",      "RBA.CREDIT.NARROW.AU",
              "RBA D2 Narrow credit (monthly, AUD m)", "aud_mn", "MONTHLY", "credit"),
    RBASeries("d2", "DLCANCS",      "RBA.CREDIT.NARROW_SA.AU",
              "RBA D2 Narrow credit (SA, monthly, AUD m)", "aud_mn", "MONTHLY", "credit", True),

    # ------------------------------------------------------------------
    # E1 — Household + business balance sheets (cell 4.2)
    # ------------------------------------------------------------------
    RBASeries("e1", "BSPNSHUA",     "RBA.HH_BS.TOTAL_ASSETS.AU",
              "RBA E1 Household total assets (AUD bn)", "aud_bn", "QUARTERLY", "balance_sheet"),
    RBASeries("e1", "BSPNSHUL",     "RBA.HH_BS.TOTAL_LIABILITIES.AU",
              "RBA E1 Household total liabilities (AUD bn)", "aud_bn", "QUARTERLY", "balance_sheet"),
    RBASeries("e1", "BSPNSHUNW",    "RBA.HH_BS.NET_WORTH.AU",
              "RBA E1 Household net worth (AUD bn)", "aud_bn", "QUARTERLY", "balance_sheet"),
    RBASeries("e1", "BSPNSHNFT",    "RBA.HH_BS.NONFIN_ASSETS.AU",
              "RBA E1 Household total non-financial assets (AUD bn)", "aud_bn", "QUARTERLY", "balance_sheet"),
    RBASeries("e1", "BSPNSHUFAT",   "RBA.HH_BS.FIN_ASSETS.AU",
              "RBA E1 Household total financial assets (AUD bn)", "aud_bn", "QUARTERLY", "balance_sheet"),
    RBASeries("e1", "BSPNSHNFD",    "RBA.HH_BS.DWELLINGS.AU",
              "RBA E1 Household dwellings (AUD bn)", "aud_bn", "QUARTERLY", "balance_sheet"),
    RBASeries("e1", "BSPNSPNLL",    "RBA.BIZ_BS.LOANS.AU",
              "RBA E1 Business loans (AUD bn)", "aud_bn", "QUARTERLY", "balance_sheet"),
    RBASeries("e1", "BSPNSPNLT",    "RBA.BIZ_BS.TOTAL_LIABILITIES.AU",
              "RBA E1 Business total liabilities (AUD bn)", "aud_bn", "QUARTERLY", "balance_sheet"),

    # ------------------------------------------------------------------
    # E2 — Household finances selected ratios (cell 4.2)
    # ------------------------------------------------------------------
    RBASeries("e2", "BHFDDIT",      "RBA.HH_RATIOS.DEBT_TO_INCOME.AU",
              "RBA E2 Household debt to income (ratio)", "ratio", "QUARTERLY", "balance_sheet"),
    RBASeries("e2", "BHFDDIH",      "RBA.HH_RATIOS.HOUSING_DEBT_TO_INCOME.AU",
              "RBA E2 Housing debt to income (ratio)", "ratio", "QUARTERLY", "balance_sheet"),
    RBASeries("e2", "BHFDDIO",      "RBA.HH_RATIOS.OO_HOUSING_DEBT_TO_INCOME.AU",
              "RBA E2 Owner-occupier housing debt to income (ratio)", "ratio", "QUARTERLY", "balance_sheet"),
    RBASeries("e2", "BHFDA",        "RBA.HH_RATIOS.DEBT_TO_ASSETS.AU",
              "RBA E2 Household debt to assets (ratio)", "ratio", "QUARTERLY", "balance_sheet"),
    RBASeries("e2", "BHFHDHA",      "RBA.HH_RATIOS.HOUSING_DEBT_TO_HOUSING_ASSETS.AU",
              "RBA E2 Housing debt to housing assets (ratio)", "ratio", "QUARTERLY", "balance_sheet"),
    RBASeries("e2", "BHFADIT",      "RBA.HH_RATIOS.ASSETS_TO_INCOME.AU",
              "RBA E2 Household assets to income (ratio)", "ratio", "QUARTERLY", "balance_sheet"),
    RBASeries("e2", "BHFHDI",       "RBA.HH_RATIOS.HOUSING_ASSETS_TO_INCOME.AU",
              "RBA E2 Housing assets to income (ratio)", "ratio", "QUARTERLY", "balance_sheet"),
    RBASeries("e2", "BHFADIFA",     "RBA.HH_RATIOS.FIN_ASSETS_TO_INCOME.AU",
              "RBA E2 Household financial assets to income (ratio)", "ratio", "QUARTERLY", "balance_sheet"),

    # ------------------------------------------------------------------
    # A2 — Monetary policy event log (cell 4.4 — supplements RBA D3)
    # ------------------------------------------------------------------
    RBASeries("a2", "ARBAMPCNCRT",  "RBA.POLICY.CASH_RATE_TARGET.AU",
              "RBA A2 New Cash Rate Target (event-driven, %)", "pct", "EVENT", "rates"),
    RBASeries("a2", "ARBAMPCCCR",   "RBA.POLICY.CASH_RATE_CHANGE.AU",
              "RBA A2 Change in Cash Rate Target (event-driven, bp)", "pct", "EVENT", "rates"),
    RBASeries("a2", "ARBAMPNRPESB", "RBA.POLICY.ES_RATE.AU",
              "RBA A2 New Exchange Settlement Rate (event-driven, %)", "pct", "EVENT", "rates"),
    RBASeries("a2", "ARBAMPNORR",   "RBA.POLICY.OVERNIGHT_REPO_RATE.AU",
              "RBA A2 New Overnight Repo Rate (event-driven, %)", "pct", "EVENT", "rates"),
]


def run_fetch(since: str | None, until: str | None) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    return fetch_specs(_SERIES, since, until)


def main() -> int:
    return run_main(vendor="rba", topic="credit_balsheet", fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "",
                    country_code="AU")


if __name__ == "__main__":
    sys.exit(main())
