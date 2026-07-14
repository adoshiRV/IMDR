"""ANZ-Indeed Australian Job Ads — prod fetcher.

One run scrapes https://www.anz.com.au/newsroom/media/release-dates/ for the
current "Download data" XLSX link and pulls the full published workbook (see
src/imdr/domains/econ/anz_indeed_jobads.py module docstring for investigation
notes and source details):

  ANZ-Indeed Australian Job Ads (MONTHLY, 1975-01 -> present, national only):
    ANZ.JOBADS.INDEX.NATIONAL.AU        seasonally adjusted
    ANZ.JOBADS.INDEX_TREND.NATIONAL.AU  trend
    ANZ.JOBADS.INDEX_ORIG.NATIONAL.AU   original (not seasonally adjusted)

No state or industry/occupation breakdown is published in this workbook.
"""
from __future__ import annotations

import sys

from imdr.domains.econ.anz_indeed_jobads import build_rows
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main


def run_fetch(
    since: str | None,
    until: str | None,
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    return build_rows(since, until)


def main() -> int:
    return run_main(vendor="anz", topic="jobads", fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "",
                    country_code="AU")


if __name__ == "__main__":
    sys.exit(main())
