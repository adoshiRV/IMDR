"""IMDR Quarterly Orchestrator.

Runs all pipelines scheduled at quarterly frequency via subprocess.
Each pipeline is isolated — one failure does not block others.
Intended for data cleaning, quality audits, and periodic maintenance.

Schedule: Quarterly (e.g. 1st of Jan/Apr/Jul/Oct, via Windows Task Scheduler or cron)

Usage:
    python -m scripts.imdr_quarterly
"""

from __future__ import annotations

import subprocess
import sys
import time

# ============================================================================
# REGISTERED QUARTERLY PIPELINES
# Add new quarterly pipelines here as [command, args...] lists.
# Examples:
#     ["python", "-m", "scripts.rates_quarterly_cleaning"],
#     ["python", "-m", "scripts.fx_quarterly_quality_audit"],
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
