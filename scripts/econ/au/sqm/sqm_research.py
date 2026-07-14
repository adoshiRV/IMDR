"""SQM Research — Weekly Asking Rents + Residential Vacancy Rates — prod fetcher.

One run pulls the full free/public history for both series families in a
single pass (see src/imdr/domains/econ/sqm_research.py module docstring for
the investigation notes and source URL / field details):

  Weekly Asking Rents (WEEKLY, 2009-08 -> present, 8 capitals, 3 series each):
    SQM.RENT.{CITY}.AU        combined (houses + units)
    SQM.RENT.{CITY}_HOUSE.AU  all houses
    SQM.RENT.{CITY}_UNIT.AU   all units

  Residential Vacancy Rates (MONTHLY, 2005-01 -> present, 8 capitals + National):
    SQM.VACANCY.{CITY}.AU
    SQM.VACANCY.NATIONAL.AU

CITY in {SYDNEY, MELBOURNE, BRISBANE, ADELAIDE, PERTH, HOBART, DARWIN, CANBERRA}.
"""
from __future__ import annotations

import sys

from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from imdr.domains.econ.sqm_research import build_rent_rows, build_vacancy_rows
from scripts.econ._runner import run_main


def run_fetch(
    since: str | None,
    until: str | None,
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    rent_ind, rent_obs = build_rent_rows(since, until)
    vac_ind, vac_obs = build_vacancy_rows(since, until)
    return rent_ind + vac_ind, rent_obs + vac_obs


def main() -> int:
    return run_main(vendor="sqm", topic="rents_vacancy", fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "",
                    country_code="AU")


if __name__ == "__main__":
    sys.exit(main())
