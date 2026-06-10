"""Cotality Daily Home Value Index — prod fetcher.

One run = one daily snapshot (today's value for 5 capitals + 5-cap aggregate).
Idempotent MERGE means re-running on the same day is harmless. Series:

  COTALITY.HVI.SYDNEY.AU
  COTALITY.HVI.MELBOURNE.AU
  COTALITY.HVI.BRISBANE.AU
  COTALITY.HVI.ADELAIDE.AU
  COTALITY.HVI.PERTH.AU
  COTALITY.HVI.FIVE_CAPITAL_AGG.AU
"""
from __future__ import annotations

import sys

from imdr.domains.econ.cotality_hvi import build_rows
from imdr.domains.econ.schema import IndicatorRow, ObservationRow
from scripts.econ._runner import run_main


def run_fetch(
    since: str | None,
    until: str | None,
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    # Cotality is a today-only snapshot — since/until are accepted by the runner
    # interface but ignored here. Each run captures today's value per series.
    return build_rows()


def main() -> int:
    return run_main(vendor="cotality", topic="hvi", fetch_fn=run_fetch,
                    description=__doc__.splitlines()[0] if __doc__ else "",
                    country_code="AU")


if __name__ == "__main__":
    sys.exit(main())
