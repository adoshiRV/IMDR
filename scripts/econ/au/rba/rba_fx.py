"""RBA F11.1 (FX rates) fetcher.

Source CSV at ``data/econ/au/rba/samples/f11.1-data.csv``,
captured via Playwright. Refresh by running
``rba_snapshot_refresh.py --daily-only``.

Series mapping:
  FXRUSD     AUD/USD
  FXRTWI     AUD trade-weighted index (May 1970 = 100)
  FXRCR      AUD/CNY
  FXRJY      AUD/JPY
  FXREUR     AUD/EUR
  FXRSKW     AUD/KRW
  FXRUKPS    AUD/GBP
  FXRSD      AUD/SGD
  FXRIRE     AUD/INR
  FXRTB      AUD/THB
  FXRNZD     AUD/NZD
  FXRNTD     AUD/TWD
  FXRMR      AUD/MYR
  FXRIR      AUD/IDR
  FXRVD      AUD/VND
  FXRHKD     AUD/HKD
  FXRCD      AUD/CAD
  FXRSF      AUD/CHF
  FXRPHP     AUD/PHP
"""
from __future__ import annotations

import sys

from imdr.domains.econ.rba_tables import RBASeries, fetch_specs
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main


_SERIES = [
    RBASeries("f11.1", "FXRUSD",   "RBA.FX.AUDUSD.AU",   "RBA AUD/USD exchange rate (daily)",  "ratio", "DAILY", "fx"),
    RBASeries("f11.1", "FXRTWI",   "RBA.FX.TWI.AU",      "RBA AUD trade-weighted index (May 1970 = 100, daily)", "index",   "DAILY", "fx"),
    RBASeries("f11.1", "FXRCR",    "RBA.FX.AUDCNY.AU",   "RBA AUD/CNY (daily)",  "ratio", "DAILY", "fx"),
    RBASeries("f11.1", "FXRJY",    "RBA.FX.AUDJPY.AU",   "RBA AUD/JPY (daily)",  "ratio", "DAILY", "fx"),
    RBASeries("f11.1", "FXREUR",   "RBA.FX.AUDEUR.AU",   "RBA AUD/EUR (daily)",  "ratio", "DAILY", "fx"),
    RBASeries("f11.1", "FXRSKW",   "RBA.FX.AUDKRW.AU",   "RBA AUD/KRW (daily)",  "ratio", "DAILY", "fx"),
    RBASeries("f11.1", "FXRUKPS",  "RBA.FX.AUDGBP.AU",   "RBA AUD/GBP (daily)",  "ratio", "DAILY", "fx"),
    RBASeries("f11.1", "FXRSD",    "RBA.FX.AUDSGD.AU",   "RBA AUD/SGD (daily)",  "ratio", "DAILY", "fx"),
    RBASeries("f11.1", "FXRIRE",   "RBA.FX.AUDINR.AU",   "RBA AUD/INR (daily)",  "ratio", "DAILY", "fx"),
    RBASeries("f11.1", "FXRTB",    "RBA.FX.AUDTHB.AU",   "RBA AUD/THB (daily)",  "ratio", "DAILY", "fx"),
    RBASeries("f11.1", "FXRNZD",   "RBA.FX.AUDNZD.AU",   "RBA AUD/NZD (daily)",  "ratio", "DAILY", "fx"),
    RBASeries("f11.1", "FXRNTD",   "RBA.FX.AUDTWD.AU",   "RBA AUD/TWD (daily)",  "ratio", "DAILY", "fx"),
    RBASeries("f11.1", "FXRMR",    "RBA.FX.AUDMYR.AU",   "RBA AUD/MYR (daily)",  "ratio", "DAILY", "fx"),
    RBASeries("f11.1", "FXRIR",    "RBA.FX.AUDIDR.AU",   "RBA AUD/IDR (daily)",  "ratio", "DAILY", "fx"),
    RBASeries("f11.1", "FXRVD",    "RBA.FX.AUDVND.AU",   "RBA AUD/VND (daily)",  "ratio", "DAILY", "fx"),
    RBASeries("f11.1", "FXRHKD",   "RBA.FX.AUDHKD.AU",   "RBA AUD/HKD (daily)",  "ratio", "DAILY", "fx"),
    RBASeries("f11.1", "FXRCD",    "RBA.FX.AUDCAD.AU",   "RBA AUD/CAD (daily)",  "ratio", "DAILY", "fx"),
    RBASeries("f11.1", "FXRSF",    "RBA.FX.AUDCHF.AU",   "RBA AUD/CHF (daily)",  "ratio", "DAILY", "fx"),
    RBASeries("f11.1", "FXRPHP",   "RBA.FX.AUDPHP.AU",   "RBA AUD/PHP (daily)",  "ratio", "DAILY", "fx"),
]


def run_fetch(since: str | None, until: str | None) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    return fetch_specs(_SERIES, since, until)


def main() -> int:
    return run_main(vendor="rba", topic="fx", fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "",
                    country_code="AU")


if __name__ == "__main__":
    sys.exit(main())
