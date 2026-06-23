"""US FRED — DAILY + WEEKLY series (financial conditions + high-frequency).

Pulls the daily/weekly slice of the curated US FRED set (seed_us.yml): UST
curve, SOFR/EFFR/IORB, IG/HY/BAA OAS spreads, VIX, the broad USD index, WTI/
Brent/gold, plus the weekly H.4.1 / H.8 / jobless-claims / NFCI financial-stress
series. Feeds wiring-map cells 4.3 (Financial Conditions), 4.4 (Policy), 2.1,
3.4, and the high-frequency leading indicators.

The cross-country OECD mirror stays in playground/econ/fred/; the 26 source-
agency duplicates deactivated by migration 106 are absent from the seed.

Part of the us_daily orchestrator.
"""

from __future__ import annotations

from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main
from scripts.econ.us.fred._fred_seed import fetch_seed

_FREQS = {"DAILY", "WEEKLY"}


def run_fetch(since: str | None, until: str | None) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    return fetch_seed(_FREQS, since, until)


def main() -> int:
    return run_main(
        vendor="fred",
        topic="series_daily",
        fetch_fn=run_fetch,
        description=__doc__.splitlines()[0] if __doc__ else "",
        country_code="US",
    )


if __name__ == "__main__":
    import sys
    sys.exit(main())
