"""US FRED — MONTHLY + QUARTERLY + ANNUAL series.

Pulls the slow-moving slice of the curated US FRED set (seed_us.yml): the
FRED-unique US series that the source agencies don't cover — GDPNow nowcast,
INDPRO, capacity utilisation, durable/cap-goods orders, sticky CPI, U6,
emp-pop ratio, Case-Shiller, mortgage rates, Z.1 balance-sheet family, money
aggregates, regional-Fed surveys (Empire/Philly/Dallas), CFNAI, leading index,
recession probabilities, market-based PCE, fiscal aggregates, etc.

The cross-country OECD mirror stays in playground/econ/fred/; the 26 source-
agency duplicates deactivated by migration 106 are absent from the seed.

Part of the us_monthly orchestrator.
"""

from __future__ import annotations

from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main
from scripts.econ.us.fred._fred_seed import fetch_seed

_FREQS = {"MONTHLY", "QUARTERLY", "ANNUAL"}


def run_fetch(since: str | None, until: str | None) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    return fetch_seed(_FREQS, since, until)


def main() -> int:
    return run_main(
        vendor="fred",
        topic="series_monthly",
        fetch_fn=run_fetch,
        description=__doc__.splitlines()[0] if __doc__ else "",
        country_code="US",
    )


if __name__ == "__main__":
    import sys
    sys.exit(main())
