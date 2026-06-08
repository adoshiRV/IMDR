"""Korea econ — WEEKLY-cadence orchestrator.

Runs every prod fetcher that publishes WEEKLY-frequency series:
  - scripts.econ.reb.reb_housing               REB R-ONE direct (4 series)
  - scripts.econ.kosis.kosis_reb_housing       KOSIS mirror of REB (4 series)

Each fetcher is a subprocess so one failure doesn't block the others. After
all fetchers finish, the shared country runner queries econ.fact_indicator for
WEEKLY-frequency KR rows touched in this run and emails a consolidated
report (one email per orchestrator run -- see
``imdr.notifications.formatters.country_econ_ingest``).

Wired into scripts/imdr_weekly.py:PIPELINES.

Usage:
    python -m scripts.econ.kr.kr_weekly
"""

from __future__ import annotations

import sys

from scripts.econ._country_runner import run


PIPELINES: list[list[str]] = [
    [sys.executable, "-m", "scripts.econ.reb.reb_housing"],
    [sys.executable, "-m", "scripts.econ.kosis.kosis_reb_housing"],
]


def main() -> int:
    return run(
        run_name="Weekly",
        country_code="KR",
        country_label="KR",
        country_name="Korea",
        orchestrator_path="scripts.econ.kr.kr_weekly",
        pipelines=PIPELINES,
        frequency_scope=["WEEKLY"],
    )


if __name__ == "__main__":
    sys.exit(main())
