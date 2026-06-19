"""Stats NZ — Overseas Trade Indexes (OTI) fetcher, via Infoshare.

Cell 3.1 Terms of Trade. OTI has no release-page CSV; Infoshare is the only
path. We pull the quarterly analytical export + import price indexes (full
commodity breakdown). Merchandise terms of trade = export price index /
import price index, derivable downstream.

Tables (Imports and exports > Overseas Trade Indexes - Prices - OTP):
  - Export price indexes - analytical (Qrtly-Mar/Jun/Sep/Dec)
  - Import price indexes - analytical (Qrtly-Mar/Jun/Sep/Dec)

Keeps all commodity categories (firehose). Cell 3.1.
IMDR code: STATSNZ.OTI.{EXPRICE|IMPRICE}.{COMMODITY}.NZ
"""

from __future__ import annotations

import sys

from imdr.domains.econ.statsnz_infoshare import InfoshareClient, fetch_table_rows
from scripts.econ._runner import run_main


_CAT = "Imports and exports"
_GROUP = "Overseas Trade Indexes - Prices - OTP"

_TABLES = [
    ("EXPRICE", "Export price indexes - analytical (Qrtly-Mar/Jun/Sep/Dec)", "Export price index - "),
    ("IMPRICE", "Import price indexes - analytical (Qrtly-Mar/Jun/Sep/Dec)", "Import price index - "),
]


def run_fetch(since: str | None = None, until: str | None = None):
    indicators, observations = [], []
    with InfoshareClient(headless=True) as client:
        for tag, leaf, disp in _TABLES:
            print(f"[*] OTI {tag}: {leaf!r}")
            ind, obs = fetch_table_rows(
                client, [_CAT, _GROUP, leaf],
                code_prefix=f"STATSNZ.OTI.{tag}",
                unit="index", frequency="QUARTERLY", category="other",
                display_prefix=disp,
            )
            indicators += ind
            observations += obs
    return indicators, observations


def main() -> int:
    return run_main(
        vendor="statsnz",
        topic="oti",
        fetch_fn=run_fetch,
        description="Stats NZ OTI (Infoshare) - export + import analytical price indexes; terms of trade (cell 3.1)",
        country_code="NZ",
    )


if __name__ == "__main__":
    sys.exit(main())
