"""SEEK — Advertised Job Index (job-ad volumes) + Advertised Salary Index — prod fetcher.

One run scrapes https://au.seek.com/about/news/article/seek-employment-data
for the current month's download links and pulls both published workbooks
(see src/imdr/domains/econ/seek_jobads.py module docstring for investigation
notes and source details):

  SEEK Job Ad Index (MONTHLY, 2001-07 -> present, national + 8 states):
    SEEK.JOBADS.INDEX.{NATIONAL|STATE_XXX}.AU        seasonally adjusted
    SEEK.JOBADS.INDEX_TREND.{NATIONAL|STATE_XXX}.AU  trend

  SEEK Advertised Salary Index (MONTHLY, 2015-11 -> present, national + 8
  states + 27 industries):
    SEEK.SALARY.INDEX.{NATIONAL|STATE_XXX|IND_XXX}.AU        seasonally adjusted
    SEEK.SALARY.INDEX_TREND.{NATIONAL|STATE_XXX|IND_XXX}.AU  trend

STATE_XXX in {STATE_ACT, STATE_NSW, STATE_NT, STATE_QLD, STATE_SA,
STATE_TAS, STATE_VIC, STATE_WA}.
"""
from __future__ import annotations

import sys

from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from imdr.domains.econ.seek_jobads import build_rows
from scripts.econ._runner import run_main


def run_fetch(
    since: str | None,
    until: str | None,
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    return build_rows(since, until)


def main() -> int:
    return run_main(vendor="seek", topic="jobads", fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "",
                    country_code="AU")


if __name__ == "__main__":
    sys.exit(main())
