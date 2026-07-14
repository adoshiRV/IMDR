"""Cotality Home Value Index — Monthly Values — prod fetcher.

Extends cotality_hvi.py (daily, 5 capitals + agg) with the "Monthly values"
tab of https://www.cotality.com/au/our-data/indices, which additionally
covers Darwin, Canberra, Hobart, and a second Brisbane metro definition
(ABS GCCSA boundary, excluding Gold Coast).

Rent/gross-rental-yield indices and national/combined-regional aggregates
are NOT available here -- confirmed (2026-07-14) against Cotality's own
"Home Value Hedonic Indices FAQs" (Oct 2023) as subscriber-only ("CoreLogic
Indices - Research Pack" / "Full Research Indices suite"); nothing in the
public page's rendered DOM exposes them. See cotality_hvi.py module
docstring for the full investigation notes.

One run = one monthly snapshot (the latest published month-end value per
region). Idempotent MERGE means re-running mid-month is harmless. Series
(10, all-dwellings only):

  COTALITY.HVI_MONTHLY.SYDNEY.AU
  COTALITY.HVI_MONTHLY.MELBOURNE.AU
  COTALITY.HVI_MONTHLY.BRISBANE.AU          (incl. Gold Coast)
  COTALITY.HVI_MONTHLY.BRISBANE_GCCSA.AU    (excl. Gold Coast)
  COTALITY.HVI_MONTHLY.ADELAIDE.AU
  COTALITY.HVI_MONTHLY.PERTH.AU
  COTALITY.HVI_MONTHLY.FIVE_CAPITAL_AGG.AU
  COTALITY.HVI_MONTHLY.DARWIN.AU
  COTALITY.HVI_MONTHLY.CANBERRA.AU
  COTALITY.HVI_MONTHLY.HOBART.AU
"""
from __future__ import annotations

import sys

from imdr.domains.econ.cotality_hvi import build_monthly_rows
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main


def run_fetch(
    since: str | None,
    until: str | None,
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    # Cotality Monthly Values is a today-only snapshot of the latest
    # published month-end -- since/until are accepted by the runner
    # interface but ignored here.
    return build_monthly_rows()


def main() -> int:
    return run_main(vendor="cotality", topic="hvi_monthly", fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "",
                    country_code="AU")


if __name__ == "__main__":
    sys.exit(main())
