"""Stats NZ — Household Labour Force Survey (HLFS), full history via Infoshare.

Cell 1.4 Macro Core (labour). The release-page XLSX carries only ~9 recent
quarters; Infoshare carries the full series. We pull the seasonally-adjusted
+ trend employed full/part-time series back to 1986.

Table (Work income and spending > Household Labour Force Survey - HLF):
  - Employed Full & Part-Time: Seas Adj & Trend Series (Qrtly)

The Labour-Force-Status-by-age-by-region tables are 3-dimensional and time out
server-side — deferred. Unemployment-rate / participation-rate SA series can be
added from their own HLF tables once a reliably-fast one is identified.

IMDR code: STATSNZ.HLFS.EMPLOYED.{CATEGORY}.NZ
"""

from __future__ import annotations

import sys

from imdr.domains.econ.statsnz_infoshare import InfoshareClient, fetch_table_rows
from scripts.econ._runner import run_main


_CAT, _GROUP = "Work income and spending", "Household Labour Force Survey - HLF"
_TABLES = [
    ("EMPLOYED", "Employed Full & Part-Time: Seas Adj & Trend Series (Qrtly-Mar/Jun/Sep/Dec)", "HLFS employed - "),
]


def run_fetch(since: str | None = None, until: str | None = None):
    indicators, observations = [], []
    with InfoshareClient(headless=True) as client:
        for tag, leaf, disp in _TABLES:
            print(f"[*] HLFS {tag}: {leaf!r}")
            ind, obs = fetch_table_rows(
                client, [_CAT, _GROUP, leaf],
                code_prefix=f"STATSNZ.HLFS.{tag}",
                unit="th_persons", frequency="QUARTERLY", category="labour",
                is_sa=True, display_prefix=disp,
            )
            indicators += ind
            observations += obs
    return indicators, observations


def main() -> int:
    return run_main(
        vendor="statsnz",
        topic="hlf",
        fetch_fn=run_fetch,
        description="Stats NZ HLFS (Infoshare) - SA + trend employed full/part-time, full history (cell 1.4)",
        country_code="NZ",
    )


if __name__ == "__main__":
    sys.exit(main())
