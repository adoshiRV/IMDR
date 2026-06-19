"""Stats NZ — Electronic Card Transactions (ECT) fetcher, via Infoshare.

Cell 1.1 Private Demand — monthly card-spend (leading consumer indicator).
No release-page CSV. Tables (Economic indicators > Electronic Card
Transactions (ANZSIC06) - ECT):
  - Total values - Electronic card transactions A/S/T by division (Monthly)
  - Values - Electronic card transactions A/S/T by industry group (Monthly)

A/S/T = Actual / Seasonally adjusted / Trend (kept as a category level).
IMDR code: STATSNZ.ECT.{TOTALVAL_DIV|VAL_IND}.{CATEGORY}.NZ
"""

from __future__ import annotations

import sys

from imdr.domains.econ.statsnz_infoshare import InfoshareClient, fetch_table_rows
from scripts.econ._runner import run_main


_CAT, _GROUP = "Economic indicators", "Electronic Card Transactions (ANZSIC06) - ECT"
_TABLES = [
    ("TOTALVAL_DIV", "Total values - Electronic card transactions A/S/T by division (Monthly)", "ECT total values - "),
    ("VAL_IND", "Values - Electronic card transactions A/S/T by industry group (Monthly)", "ECT values - "),
]


def run_fetch(since: str | None = None, until: str | None = None):
    indicators, observations = [], []
    with InfoshareClient(headless=True) as client:
        for tag, leaf, disp in _TABLES:
            print(f"[*] ECT {tag}: {leaf!r}")
            ind, obs = fetch_table_rows(
                client, [_CAT, _GROUP, leaf],
                code_prefix=f"STATSNZ.ECT.{tag}",
                unit="nzd_mn", frequency="MONTHLY", category="other", display_prefix=disp,
            )
            indicators += ind
            observations += obs
    return indicators, observations


def main() -> int:
    return run_main(
        vendor="statsnz",
        topic="ect",
        fetch_fn=run_fetch,
        description="Stats NZ ECT (Infoshare) - electronic card transaction values, monthly by division + industry (cell 1.1)",
        country_code="NZ",
    )


if __name__ == "__main__":
    sys.exit(main())
