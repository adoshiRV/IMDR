"""IMDR Weekly Orchestrator.

Runs all pipelines scheduled at weekly frequency via subprocess.
Each pipeline is isolated — one failure does not block others.

Schedule: Weekly (e.g. Monday morning, via Windows Task Scheduler or cron)

Usage:
    python -m scripts.imdr_weekly
"""

from __future__ import annotations

import subprocess
import sys
import time

# ============================================================================
# REGISTERED WEEKLY PIPELINES
# Add new weekly pipelines here as [command, args...] lists.
# Examples:
#     ["python", "-m", "scripts.rates_weekly_validation"],
#     ["python", "-m", "scripts.fx_weekly_gap_fill"],
# ============================================================================

PIPELINES: list[list[str]] = []

# ============================================================================


def main() -> int:
    if not PIPELINES:
        return 0

    failed: list[str] = []
    for cmd in PIPELINES:
        name = cmd[-1]
        t0 = time.perf_counter()
        result = subprocess.run(cmd)
        elapsed = time.perf_counter() - t0

        if result.returncode != 0:
            print(f"FAIL  {name}  rc={result.returncode}  ({elapsed:.1f}s)")
            failed.append(name)
        else:
            print(f"OK    {name}  ({elapsed:.1f}s)")

    if failed:
        print(f"\n{len(failed)} pipeline(s) failed: {', '.join(failed)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
