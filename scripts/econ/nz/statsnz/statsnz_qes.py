"""Stats NZ — Quarterly Employment Survey (QES) fetcher, via Infoshare.

Cells 1.4 / 2.3 — earnings + hours (employer-side). No release-page CSV.
Tables (Work income and spending > Quarterly Employment Survey - QEM):
  - Average Weekly Earnings (Employees) Total All Ind. & Both Sexes - Seasonally Adj
  - Average Weekly Earnings (Employees) by Industry (ANZSIC06) and Sex  (firehose)
  - Average Hourly Earnings by Industry (ANZSIC06) and Sex              (firehose)
  - Average Weekly Paid Hours (Employees) Total All Ind & Both Sexes - Seasonal Adj

IMDR code: STATSNZ.QES.{TAG}.{CATEGORY}.NZ
"""

from __future__ import annotations

import sys

from imdr.domains.econ.statsnz_infoshare import InfoshareClient, fetch_table_rows
from scripts.econ._runner import run_main


_CAT, _GROUP = "Work income and spending", "Quarterly Employment Survey - QEM"
# (tag, leaf, unit, display_prefix)
_TABLES = [
    ("AWE_TOTAL_SA", "Average Weekly Earnings (Employees) Total All Ind. & Both Sexes - Seasonally Adj (Qrtly-Mar/Jun/Sep/Dec)", "nzd", "QES avg weekly earnings (SA) - "),
    ("AWE_IND", "Average Weekly Earnings (Employees) by Industry (ANZSIC06) and Sex (Qrtly-Mar/Jun/Sep/Dec)", "nzd", "QES avg weekly earnings - "),
    ("AHE_IND", "Average Hourly Earnings by Industry (ANZSIC06) and Sex (Qrtly-Mar/Jun/Sep/Dec)", "nzd", "QES avg hourly earnings - "),
    ("AWPH_TOTAL_SA", "Average Weekly Paid Hours (Employees) Total All Ind & Both Sexes - Seasonal Adj (Qrtly-Mar/Jun/Sep/Dec)", "hours", "QES avg weekly paid hours (SA) - "),
]


def run_fetch(since: str | None = None, until: str | None = None):
    indicators, observations = [], []
    with InfoshareClient(headless=True) as client:
        for tag, leaf, unit, disp in _TABLES:
            print(f"[*] QES {tag}: {leaf!r}")
            ind, obs = fetch_table_rows(
                client, [_CAT, _GROUP, leaf],
                code_prefix=f"STATSNZ.QES.{tag}",
                unit=unit, frequency="QUARTERLY", category="labour",
                is_sa=("SA" in tag), display_prefix=disp,
            )
            indicators += ind
            observations += obs
    return indicators, observations


def main() -> int:
    return run_main(
        vendor="statsnz",
        topic="qes",
        fetch_fn=run_fetch,
        description="Stats NZ QES (Infoshare) - weekly/hourly earnings + paid hours, totals + by-industry (cells 1.4/2.3)",
        country_code="NZ",
    )


if __name__ == "__main__":
    sys.exit(main())
