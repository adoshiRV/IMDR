"""Stats NZ — Overseas Merchandise Trade (OMT) fetcher, via Infoshare.

Cell 1.3 External Demand — monthly goods exports/imports/balance. No release
CSV. We pull the headline seasonally-adjusted totals + trade balance (the
country x commodity detail tables are intentionally skipped — high-cardinality
noise per the "relevant firehose" call).

Tables (Imports and exports > Overseas Trade Statistics - OTT):
  - Overseas Trade Statistics - Seasonally Adjusted (Monthly)
  - Overseas Trade Statistics - Trade Balance ($millions) (Monthly)

IMDR code: STATSNZ.OMT.{SA|BALANCE}.{CATEGORY}.NZ
"""

from __future__ import annotations

import sys

from imdr.domains.econ.statsnz_infoshare import InfoshareClient, fetch_table_rows
from scripts.econ._runner import run_main


_CAT, _GROUP = "Imports and exports", "Overseas Trade Statistics - OTT"
_TABLES = [
    ("SA", "Overseas Trade Statistics - Seasonally Adjusted (Monthly)", "OMT SA - "),
    ("BALANCE", "Overseas Trade Statistics - Trade Balance ($millions) (Monthly)", "OMT trade balance - "),
]


def run_fetch(since: str | None = None, until: str | None = None):
    indicators, observations = [], []
    with InfoshareClient(headless=True) as client:
        for tag, leaf, disp in _TABLES:
            print(f"[*] OMT {tag}: {leaf!r}")
            ind, obs = fetch_table_rows(
                client, [_CAT, _GROUP, leaf],
                code_prefix=f"STATSNZ.OMT.{tag}",
                unit="nzd_mn", frequency="MONTHLY", category="bop",
                is_sa=(tag == "SA"), display_prefix=disp,
            )
            indicators += ind
            observations += obs
    return indicators, observations


def main() -> int:
    return run_main(
        vendor="statsnz",
        topic="omt",
        fetch_fn=run_fetch,
        description="Stats NZ OMT (Infoshare) - merchandise trade SA totals + trade balance, monthly (cell 1.3)",
        country_code="NZ",
    )


if __name__ == "__main__":
    sys.exit(main())
