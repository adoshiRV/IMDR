"""Stats NZ — Retail Trade Survey (RTS) fetcher, via Infoshare.

Cell 1.1 Private Demand — quarterly retail sales (core consumer-demand read).
No release-page CSV. Tables (Industry sectors > Retail Trade (ANZSIC06) - RTT):
  - Sales and stocks by industry, in current and constant prices (SAFC) (Qrtly)
  - Sales by region in current prices (SAFC) (Qrtly)

SAFC = Seasonally Adjusted / Actual + current/constant price levels (kept as
category levels). IMDR code: STATSNZ.RTS.{SALES_IND|SALES_REGION}.{CATEGORY}.NZ
"""

from __future__ import annotations

import sys

from imdr.domains.econ.statsnz_infoshare import InfoshareClient, fetch_table_rows
from scripts.econ._runner import run_main


_CAT, _GROUP = "Industry sectors", "Retail Trade (ANZSIC06) - RTT"
_TABLES = [
    ("SALES_IND", "Sales and stocks by industry, in current and constant prices (SAFC) (Qrtly-Mar/Jun/Sep/Dec)", "RTS sales/stocks - "),
    ("SALES_REGION", "Sales by region in current prices (SAFC) (Qrtly-Mar/Jun/Sep/Dec)", "RTS sales by region - "),
]


def run_fetch(since: str | None = None, until: str | None = None):
    indicators, observations = [], []
    with InfoshareClient(headless=True) as client:
        for tag, leaf, disp in _TABLES:
            print(f"[*] RTS {tag}: {leaf!r}")
            ind, obs = fetch_table_rows(
                client, [_CAT, _GROUP, leaf],
                code_prefix=f"STATSNZ.RTS.{tag}",
                unit="nzd_mn", frequency="QUARTERLY", category="other", display_prefix=disp,
            )
            indicators += ind
            observations += obs
    return indicators, observations


def main() -> int:
    return run_main(
        vendor="statsnz",
        topic="rts",
        fetch_fn=run_fetch,
        description="Stats NZ RTS (Infoshare) - retail sales/stocks by industry + region, quarterly (cell 1.1)",
        country_code="NZ",
    )


if __name__ == "__main__":
    sys.exit(main())
