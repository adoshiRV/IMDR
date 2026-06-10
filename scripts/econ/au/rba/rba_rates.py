"""RBA F1 (money market rates) + F2 (govt bond yields) fetcher.

Source CSVs at ``data/econ/au/rba/samples/{f1,f2}-data.csv``,
captured via Playwright (Akamai blocks plain GET). Refresh those CSVs
by running ``rba_snapshot_refresh.py --daily-only``.

Series mapping (Series IDs from the CSV "Series ID" header row):

  F1:  FIRMMCRTD    Cash Rate Target (D)
       FIRMMBAB30D  1m BBSW (D)
       FIRMMBAB90D  3m BBSW (D)
       FIRMMBAB180D 6m BBSW (D)
       FIRMMOIS1D   1m OIS (D)
       FIRMMOIS3D   3m OIS (D)
       FIRMMOIS6D   6m OIS (D)

  F2:  FCMYGBAG2D    2-year Australian govt bond yield (D)
       FCMYGBAG3D    3-year (D)
       FCMYGBAG5D    5-year (D)
       FCMYGBAG10D   10-year (D)
       FCMYGBAGID    10-year Australian govt INDEXED bond yield (D)
                     -- real yield; breakeven inflation = GOVTBOND_10Y - GOVTBOND_INDEXED_10Y
"""
from __future__ import annotations

import sys

from imdr.domains.econ.rba_tables import RBASeries, fetch_specs
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main


_SERIES = [
    # F1 — money-market rates
    RBASeries("f1", "FIRMMCRTD",   "RBA.RATES.CASH_RATE_TARGET.AU",
              "RBA Cash Rate Target (daily)", "pct", "DAILY", "rates"),
    RBASeries("f1", "FIRMMBAB30D", "RBA.RATES.BBSW_1M.AU",
              "RBA 1-month BBSW (daily)", "pct", "DAILY", "rates"),
    RBASeries("f1", "FIRMMBAB90D", "RBA.RATES.BBSW_3M.AU",
              "RBA 3-month BBSW (daily)", "pct", "DAILY", "rates"),
    RBASeries("f1", "FIRMMBAB180D", "RBA.RATES.BBSW_6M.AU",
              "RBA 6-month BBSW (daily)", "pct", "DAILY", "rates"),
    RBASeries("f1", "FIRMMOIS1D",  "RBA.RATES.OIS_1M.AU",
              "RBA 1-month OIS (daily)", "pct", "DAILY", "rates"),
    RBASeries("f1", "FIRMMOIS3D",  "RBA.RATES.OIS_3M.AU",
              "RBA 3-month OIS (daily)", "pct", "DAILY", "rates"),
    RBASeries("f1", "FIRMMOIS6D",  "RBA.RATES.OIS_6M.AU",
              "RBA 6-month OIS (daily)", "pct", "DAILY", "rates"),
    # F2 — govt bond yields
    RBASeries("f2", "FCMYGBAG2D",  "RBA.RATES.GOVTBOND_2Y.AU",
              "RBA 2-year Australian government bond yield (daily)", "pct", "DAILY", "rates"),
    RBASeries("f2", "FCMYGBAG3D",  "RBA.RATES.GOVTBOND_3Y.AU",
              "RBA 3-year Australian government bond yield (daily)", "pct", "DAILY", "rates"),
    RBASeries("f2", "FCMYGBAG5D",  "RBA.RATES.GOVTBOND_5Y.AU",
              "RBA 5-year Australian government bond yield (daily)", "pct", "DAILY", "rates"),
    RBASeries("f2", "FCMYGBAG10D", "RBA.RATES.GOVTBOND_10Y.AU",
              "RBA 10-year Australian government bond yield (daily)", "pct", "DAILY", "rates"),
    RBASeries("f2", "FCMYGBAGID",  "RBA.RATES.GOVTBOND_INDEXED_10Y.AU",
              "RBA 10-year Australian government indexed bond (TIB) real yield (daily). "
              "Breakeven 10Y inflation = GOVTBOND_10Y − GOVTBOND_INDEXED_10Y.",
              "pct", "DAILY", "rates"),
]


def run_fetch(since: str | None, until: str | None) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    return fetch_specs(_SERIES, since, until)


def main() -> int:
    return run_main(vendor="rba", topic="rates", fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "",
                    country_code="AU")


if __name__ == "__main__":
    sys.exit(main())
