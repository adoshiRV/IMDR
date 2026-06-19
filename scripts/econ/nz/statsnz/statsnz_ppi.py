"""Stats NZ — Producers Price Index (PPI) fetcher, via Infoshare.

PPI has NO release-page CSV (the Business Price Indexes release ships only
presentation XLSX). Infoshare is the only path. We pull the NZSIOC level-1
Outputs + Inputs index tables (quarterly, base Dec-2010 = 1000, history to
1977-Q4), keeping ALL 20 industry aggregates per side (firehose).

Coverage: cell 2.2 Producer Prices. ~40 indicators x ~195 quarters.
PPI Output = prices producers receive; PPI Input = prices producers pay
(a margin/cost-pressure read that leads CPI).

IMDR code: STATSNZ.PPI.{OUTPUT|INPUT}.{CATEGORY}.NZ
"""

from __future__ import annotations

import sys

from imdr.domains.econ.statsnz_infoshare import InfoshareClient, fetch_table_rows
from scripts.econ._runner import run_main


_CAT, _GROUP = "Economic indicators", "Producers Price Index - PPI"

# (side, leaf-table fragment) — keep ALL industries (firehose).
_TABLES = [
    ("OUTPUT", "Outputs (ANZSIC06) - NZSIOC level 1, Base", "PPI output - "),
    ("INPUT", "Inputs (ANZSIC06) - NZSIOC level 1, Base", "PPI input - "),
]


def run_fetch(since: str | None = None, until: str | None = None):
    indicators, observations = [], []
    with InfoshareClient(headless=True) as client:
        for side, leaf, disp in _TABLES:
            print(f"[*] PPI {side}: {leaf!r}")
            ind, obs = fetch_table_rows(
                client, [_CAT, _GROUP, leaf],
                code_prefix=f"STATSNZ.PPI.{side}",
                unit="index", frequency="QUARTERLY", category="other", display_prefix=disp,
            )
            indicators += ind
            observations += obs
    return indicators, observations


def main() -> int:
    return run_main(
        vendor="statsnz",
        topic="ppi",
        fetch_fn=run_fetch,
        description="Stats NZ PPI (Infoshare) - Outputs + Inputs NZSIOC L1, all industries, quarterly 1977-Q4 ->",
        country_code="NZ",
    )


if __name__ == "__main__":
    sys.exit(main())
