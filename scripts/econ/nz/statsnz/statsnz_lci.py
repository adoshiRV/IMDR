"""Stats NZ — Labour Cost Index (LCI) fetcher, via Infoshare.

Cell 2.3 Domestic Costs — fixed-quality wage inflation. No release-page CSV.
Tables (Work income and spending > Labour Cost Index - LCI):
  - All Sectors Combined, All Salary and Wage Rates (Base: June 2017 = 1000) — headline

The by-industry / by-occupation cross-tab tables time out generating server-side
(deferred). IMDR code: STATSNZ.LCI.ALLSEC.{CATEGORY}.NZ
"""

from __future__ import annotations

import sys

from imdr.domains.econ.statsnz_infoshare import InfoshareClient, fetch_table_rows
from scripts.econ._runner import run_main


_CAT, _GROUP = "Work income and spending", "Labour Cost Index - LCI"
# NOTE: the "... and Industry Group"/"... and Occupation Group" cross-tab tables
# consistently time out generating (>120s, retried) — server-side slow table,
# not a 2-dim parser issue (QES 2-dim tables of similar size work fine). Deferred
# as a known-slow follow-up; the all-sectors headline below is the macro-relevant
# wage-inflation series and downloads reliably.
_TABLES = [
    ("ALLSEC", "All Sectors Combined, All Salary and Wage Rates (Base: June 2017 qtr (=1000))", "LCI all sectors - "),
]


def run_fetch(since: str | None = None, until: str | None = None):
    indicators, observations = [], []
    with InfoshareClient(headless=True) as client:
        for tag, leaf, disp in _TABLES:
            print(f"[*] LCI {tag}: {leaf!r}")
            ind, obs = fetch_table_rows(
                client, [_CAT, _GROUP, leaf],
                code_prefix=f"STATSNZ.LCI.{tag}",
                unit="index", frequency="QUARTERLY", category="labour", display_prefix=disp,
            )
            indicators += ind
            observations += obs
    return indicators, observations


def main() -> int:
    return run_main(
        vendor="statsnz",
        topic="lci",
        fetch_fn=run_fetch,
        description="Stats NZ LCI (Infoshare) - labour cost index, all-sectors headline + by-industry (cell 2.3)",
        country_code="NZ",
    )


if __name__ == "__main__":
    sys.exit(main())
