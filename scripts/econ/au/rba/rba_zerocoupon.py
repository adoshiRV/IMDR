"""RBA F17 — Zero-coupon Interest Rates (Analytical Series).

CSV snapshots at:
  - ``data/econ/au/rba/samples/f17-yields-data.csv``
  - ``data/econ/au/rba/samples/f17-forward-rates-data.csv``
  - (f17-discount-factors-data.csv also pulled but not loaded — derivable
     from yields)

Captured via Playwright by ``rba_snapshot_refresh.py`` (Akamai gate).

F17 publishes the full zero-coupon AGB curve at quarter-year tenors
from 0Y to 10Y (41 tenors × 3 measures = 123 series). For a macro desk
we ship only the integer-year + short-end tenors most analytics actually
look at: 0.25Y / 0.5Y / 1Y / 2Y / 3Y / 5Y / 7Y / 10Y across yields and
forward rates = 16 indicators.

Series IDs follow:
  FZCY{tenor*100}D   = zero-coupon yield  (e.g. FZCY100D = 1.00Y yield)
  FZCF{tenor*100}D   = zero-coupon forward rate
  FZCD{tenor*100}D   = zero-coupon discount factor (NOT loaded)
"""
from __future__ import annotations

import sys

from imdr.domains.econ.rba_tables import RBASeries, fetch_specs
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main


# Desk-relevant tenor set. List of (raw_tenor_label, code_suffix, display_label).
# code_suffix is the trailing token in the IMDR code (e.g. "1Y", "0_5Y").
_TENORS = [
    ("25",   "0_25Y",  "0.25Y (3M)"),
    ("50",   "0_5Y",   "0.5Y (6M)"),
    ("100",  "1Y",     "1Y"),
    ("200",  "2Y",     "2Y"),
    ("300",  "3Y",     "3Y"),
    ("500",  "5Y",     "5Y"),
    ("700",  "7Y",     "7Y"),
    ("1000", "10Y",    "10Y"),
]


_SERIES = []
for raw, suffix, label in _TENORS:
    _SERIES.append(RBASeries(
        "f17-yields",
        f"FZCY{raw}D",
        f"RBA.ZCY.YIELD_{suffix}.AU",
        f"RBA F17 — Zero-coupon AGB yield, {label} (daily, % p.a.)",
        "pct", "DAILY", "rates",
    ))
for raw, suffix, label in _TENORS:
    _SERIES.append(RBASeries(
        "f17-forward-rates",
        f"FZCF{raw}D",
        f"RBA.ZCY.FORWARD_{suffix}.AU",
        f"RBA F17 — Zero-coupon AGB forward rate, {label} (daily, % p.a.)",
        "pct", "DAILY", "rates",
    ))


def run_fetch(since: str | None, until: str | None) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    return fetch_specs(_SERIES, since, until)


def main() -> int:
    return run_main(vendor="rba", topic="zerocoupon", fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "",
                    country_code="AU")


if __name__ == "__main__":
    sys.exit(main())
