"""India econ — DAILY orchestrator.

IMD All-India rainfall snapshot, fetched daily during the Jun–Sep monsoon
window. The fetcher is idempotent (MERGE on PK) so off-season daily runs
are harmless — they simply find no new data and exit cleanly.

Wired into scripts/imdr_daily.py.
"""

from __future__ import annotations

import sys

from scripts.econ._country_runner import run


PIPELINES: list[list[str]] = [
    [sys.executable, "-m", "scripts.econ.in.imd.imd_rainfall"],
]


def main() -> int:
    return run(
        run_name="Daily",
        country_code="IN",
        country_label="IN",
        country_name="India",
        orchestrator_path="scripts.econ.in.in_daily",
        pipelines=PIPELINES,
        frequency_scope=["DAILY"],
    )


if __name__ == "__main__":
    sys.exit(main())
