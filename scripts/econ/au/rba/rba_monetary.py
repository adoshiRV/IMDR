"""RBA D3 (monetary aggregates) fetcher.

Source CSV at ``data/econ/au/rba/samples/d3-data.csv``,
captured via Playwright. Refresh by running ``rba_snapshot_refresh.py``.

Series mapping (Series IDs reconciled against the live D3 CSV 2026-06-09):
  DMACN / DMACS         Currency NSA / SA
  DMATD                 Transaction Deposits with ADIs
  DMANTD                Non-Transaction Deposits with ADIs
  DMAODCD               Certificates of Deposit issued by ADIs
  DMAM1N / DMAM1S       M1 NSA / SA
  DMAM3N / DMAM3S       M3 NSA / SA
  DMABMN / DMABMS       Broad Money NSA / SA
  DMAMMB                Money Base
  DMANBPA               Other borrowings from private sector by AFIs
  DMAMOAFI              Offshore borrowings by AFIs

NSA codes carry the `N` suffix; SA codes carry `S`. Earlier RBA documentation
referencing `DMAM1` / `DMAM3` / `DMABM` (no suffix) does NOT match the live
CSV — those keys return zero rows.
"""
from __future__ import annotations

import sys

from imdr.domains.econ.rba_tables import RBASeries, fetch_specs
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main


_SERIES = [
    RBASeries("d3", "DMACN",     "RBA.MA.CURRENCY.AU",        "RBA Currency (monthly, AUD m)",            "aud_mn", "MONTHLY", "other"),
    RBASeries("d3", "DMACS",     "RBA.MA.CURRENCY_SA.AU",     "RBA Currency seasonally adjusted (monthly, AUD m)", "aud_mn", "MONTHLY", "other", True),
    RBASeries("d3", "DMATD",     "RBA.MA.TXN_DEPOSITS.AU",    "RBA Transaction deposits ADIs (monthly, AUD m)",     "aud_mn", "MONTHLY", "other"),
    RBASeries("d3", "DMANTD",    "RBA.MA.NONTXN_DEPOSITS.AU", "RBA Non-transaction deposits ADIs (monthly, AUD m)", "aud_mn", "MONTHLY", "other"),
    RBASeries("d3", "DMAODCD",   "RBA.MA.ADI_CDS.AU",         "RBA Certificates of deposit issued by ADIs (monthly, AUD m)", "aud_mn", "MONTHLY", "other"),
    RBASeries("d3", "DMAM1N",    "RBA.MA.M1.AU",              "RBA M1 (monthly, AUD m)",                   "aud_mn", "MONTHLY", "other"),
    RBASeries("d3", "DMAM1S",    "RBA.MA.M1_SA.AU",           "RBA M1 (seasonally adjusted, monthly, AUD m)", "aud_mn", "MONTHLY", "other", True),
    RBASeries("d3", "DMAM3N",    "RBA.MA.M3.AU",              "RBA M3 (monthly, AUD m)",                   "aud_mn", "MONTHLY", "other"),
    RBASeries("d3", "DMAM3S",    "RBA.MA.M3_SA.AU",           "RBA M3 (seasonally adjusted, monthly, AUD m)", "aud_mn", "MONTHLY", "other", True),
    RBASeries("d3", "DMABMN",    "RBA.MA.BROAD_MONEY.AU",     "RBA Broad money (monthly, AUD m)",          "aud_mn", "MONTHLY", "other"),
    RBASeries("d3", "DMABMS",    "RBA.MA.BROAD_MONEY_SA.AU",  "RBA Broad money (seasonally adjusted, monthly, AUD m)", "aud_mn", "MONTHLY", "other", True),
    RBASeries("d3", "DMAMMB",    "RBA.MA.MONEY_BASE.AU",      "RBA Money base (monthly, AUD m)",           "aud_mn", "MONTHLY", "other"),
    RBASeries("d3", "DMANBPA",   "RBA.MA.AFI_PRIVATE_BORR.AU", "RBA Other borrowings from private sector by AFIs (monthly, AUD m)", "aud_mn", "MONTHLY", "other"),
    RBASeries("d3", "DMAMOAFI",  "RBA.MA.AFI_OFFSHORE_BORR.AU", "RBA Offshore borrowings by AFIs (monthly, AUD m)", "aud_mn", "MONTHLY", "other"),
]


def run_fetch(since: str | None, until: str | None) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    return fetch_specs(_SERIES, since, until)


def main() -> int:
    return run_main(vendor="rba", topic="monetary", fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "",
                    country_code="AU")


if __name__ == "__main__":
    sys.exit(main())
