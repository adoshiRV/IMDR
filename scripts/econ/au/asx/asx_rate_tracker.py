"""ASX RBA Rate Tracker — prod fetcher.

One run captures today's implied cash-rate curve (derived to fixed 1/3/6/12M
horizons) + the ~15-day next-meeting change-probability backfill. Idempotent
MERGE means re-running on the same day is harmless; running daily builds the
implied-path time series forward one settlement at a time.

Replaces the dead RBA F1 OIS series (FIRMMOIS*, discontinued 2022-12-01).

Series:
  ASX.CASHRATE.IMPLIED_1M.AU
  ASX.CASHRATE.IMPLIED_3M.AU
  ASX.CASHRATE.IMPLIED_6M.AU
  ASX.CASHRATE.IMPLIED_12M.AU
  ASX.RATETRACKER.PROB_CHANGE_NEXT_MEETING.AU

Usage:
    python -m scripts.econ.au.asx.asx_rate_tracker            # fetch + load
    python -m scripts.econ.au.asx.asx_rate_tracker --no-load  # smoke only
"""
from __future__ import annotations

import sys

from imdr.domains.econ.asx_rate_tracker import build_rows
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main


def run_fetch(
    since: str | None,
    until: str | None,
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    # ASX serves a today-only curve + a rolling ~15-day probability window;
    # since/until are accepted by the runner interface but ignored here.
    return build_rows()


def main() -> int:
    return run_main(vendor="asx", topic="rate_tracker", fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "",
                    country_code="AU")


if __name__ == "__main__":
    sys.exit(main())
