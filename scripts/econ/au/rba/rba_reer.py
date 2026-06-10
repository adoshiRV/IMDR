"""RBA F15 — Real Exchange Rate Measures (REER).

CSV snapshot at ``data/econ/au/rba/samples/f15-data.csv``,
captured via Playwright by ``rba_snapshot_refresh.py``. Quarterly since
1970, indexed to March 1995 = 100.

Closes the wiring-map cell 3.4 sub-bullet for REER (previously
addressed only via the BIS WS_EER mirror).

Series IDs:
  FRERTWI  Real trade-weighted index
  FRERIWI  Real import-weighted index
  FREREWI  Real export-weighted index
"""
from __future__ import annotations

import sys

from imdr.domains.econ.rba_tables import RBASeries, fetch_specs
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main


_SERIES = [
    RBASeries("f15", "FRERTWI", "RBA.REER.TWI.AU",
              "RBA F15 — Real trade-weighted AUD index (quarterly, Index Mar-1995=100)",
              "index", "QUARTERLY", "fx"),
    RBASeries("f15", "FRERIWI", "RBA.REER.IMPORT_WEIGHTED.AU",
              "RBA F15 — Real import-weighted AUD index (quarterly, Index Mar-1995=100)",
              "index", "QUARTERLY", "fx"),
    RBASeries("f15", "FREREWI", "RBA.REER.EXPORT_WEIGHTED.AU",
              "RBA F15 — Real export-weighted AUD index (quarterly, Index Mar-1995=100)",
              "index", "QUARTERLY", "fx"),
]


def run_fetch(since: str | None, until: str | None) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    return fetch_specs(_SERIES, since, until)


def main() -> int:
    return run_main(vendor="rba", topic="reer", fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "",
                    country_code="AU")


if __name__ == "__main__":
    sys.exit(main())
