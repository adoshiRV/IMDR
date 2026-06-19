"""Stats NZ — Capital Goods Price Index (CGPI) fetcher, via Infoshare.

Cell 2.2 Producer Prices (capital-goods side). No release-page CSV.
Tables (Economic indicators > Capital Goods Price Index - CEP):
  - Price Index all groups of capital goods (Base: Sept 2022 = 1000)
  - Price Index asset types of capital goods (Base: Sept 2022 = 1000)

IMDR code: STATSNZ.CGPI.{ALLGROUPS|ASSET}.{CATEGORY}.NZ
"""

from __future__ import annotations

import sys

from imdr.domains.econ.statsnz_infoshare import InfoshareClient, fetch_table_rows
from scripts.econ._runner import run_main


_CAT, _GROUP = "Economic indicators", "Capital Goods Price Index - CEP"
_TABLES = [
    ("ALLGROUPS", "Price Index all groups of capital goods (Base: September quarter 2022 = 1000)", "CGPI all groups - "),
    ("ASSET", "Price Index asset types of capital goods (Base: September quarter 2022 = 1000)", "CGPI asset type - "),
]


def run_fetch(since: str | None = None, until: str | None = None):
    indicators, observations = [], []
    with InfoshareClient(headless=True) as client:
        for tag, leaf, disp in _TABLES:
            print(f"[*] CGPI {tag}: {leaf!r}")
            ind, obs = fetch_table_rows(
                client, [_CAT, _GROUP, leaf],
                code_prefix=f"STATSNZ.CGPI.{tag}",
                unit="index", frequency="QUARTERLY", category="other", display_prefix=disp,
            )
            indicators += ind
            observations += obs
    return indicators, observations


def main() -> int:
    return run_main(
        vendor="statsnz",
        topic="cgpi",
        fetch_fn=run_fetch,
        description="Stats NZ CGPI (Infoshare) - capital goods price index, all-groups + asset types (cell 2.2)",
        country_code="NZ",
    )


if __name__ == "__main__":
    sys.exit(main())
