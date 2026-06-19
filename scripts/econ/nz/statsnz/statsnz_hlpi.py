"""Stats NZ — Household Living-costs Price Indexes (HLPI) fetcher, via Infoshare.

Cell 2.4 CPI Pressure (cost-of-living view; complements CPI). No release CSV.
Tables (Economic indicators > Household living-costs price Indexes - HPI):
  - HLPI All groups (Qrtly)   — all-groups index per household type (13 groups)
  - HLPI Groups (Qrtly)       — household type x expenditure group (2-dim firehose)

IMDR code: STATSNZ.HLPI.{ALLGROUPS|GROUP}.{CATEGORY}.NZ
"""

from __future__ import annotations

import sys

from imdr.domains.econ.statsnz_infoshare import InfoshareClient, fetch_table_rows
from scripts.econ._runner import run_main


_CAT, _GROUP = "Economic indicators", "Household living-costs price Indexes - HPI"
_TABLES = [
    ("ALLGROUPS", "HLPI All groups (Qrtly-Mar/Jun/Sep/Dec)", "HLPI all-groups - "),
    ("GROUP", "HLPI Groups (Qrtly-Mar/Jun/Sep/Dec)", "HLPI - "),
]


def run_fetch(since: str | None = None, until: str | None = None):
    indicators, observations = [], []
    with InfoshareClient(headless=True) as client:
        for tag, leaf, disp in _TABLES:
            print(f"[*] HLPI {tag}: {leaf!r}")
            ind, obs = fetch_table_rows(
                client, [_CAT, _GROUP, leaf],
                code_prefix=f"STATSNZ.HLPI.{tag}",
                unit="index", frequency="QUARTERLY", category="cpi", display_prefix=disp,
            )
            indicators += ind
            observations += obs
    return indicators, observations


def main() -> int:
    return run_main(
        vendor="statsnz",
        topic="hlpi",
        fetch_fn=run_fetch,
        description="Stats NZ HLPI (Infoshare) - household living-costs price indexes by household type + expenditure group (cell 2.4)",
        country_code="NZ",
    )


if __name__ == "__main__":
    sys.exit(main())
