"""APRA Monthly ADI Statistics (MADIS) — big-4 housing loan book — prod fetcher.

Downloads the current back-series XLSX linked off
https://www.apra.gov.au/monthly-authorised-deposit-taking-institution-statistics
(discovered by anchor text, not a hardcoded filename -- the file is renamed
every month with the new end date) and extracts owner-occupied vs investment
housing loan balances for the big-4 ADIs. See
src/imdr/domains/econ/apra_madis.py module docstring for the full source
investigation (sheet/column names, legacy-file exclusion, auth).

Series (8, monthly, AUD million, category=credit):
  APRA.ADI.ANZ.HOUSING_OWNER_OCC.AU   APRA.ADI.ANZ.HOUSING_INVESTOR.AU
  APRA.ADI.CBA.HOUSING_OWNER_OCC.AU   APRA.ADI.CBA.HOUSING_INVESTOR.AU
  APRA.ADI.NAB.HOUSING_OWNER_OCC.AU   APRA.ADI.NAB.HOUSING_INVESTOR.AU
  APRA.ADI.WBC.HOUSING_OWNER_OCC.AU   APRA.ADI.WBC.HOUSING_INVESTOR.AU
"""
from __future__ import annotations

import datetime
import sys

from imdr.domains.econ.apra_madis import (
    build_rows,
    discover_backseries_url,
    fetch_backseries_xlsx,
    fetch_page_html,
    parse_backseries_xlsx,
)
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main


def run_fetch(since: str | None, until: str | None) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    since_d = datetime.date.fromisoformat(since) if since else None
    until_d = datetime.date.fromisoformat(until) if until else None

    html = fetch_page_html()
    url = discover_backseries_url(html)
    if url is None:
        print("  ERROR: could not find MADIS back-series XLSX link on the publication page")
        return [], []
    print(f"  back-series URL: {url}")

    xlsx_bytes = fetch_backseries_xlsx(url)
    parsed = parse_backseries_xlsx(xlsx_bytes)
    print(f"  parsed {len(parsed)} big-4 rows from Table 1")

    return build_rows(parsed, since=since_d, until=until_d)


def main() -> int:
    return run_main(vendor="apra", topic="madis", fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "",
                    country_code="AU")


if __name__ == "__main__":
    sys.exit(main())
