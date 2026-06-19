"""IMDR Monthly Orchestrator.

Runs all pipelines scheduled at monthly frequency via subprocess.
Each pipeline is isolated — one failure does not block others.

Schedule: Monthly (e.g. 1st of month, via Windows Task Scheduler or cron)

Usage:
    python -m scripts.imdr_monthly
"""

from __future__ import annotations

import subprocess
import sys
import time

# ============================================================================
# REGISTERED MONTHLY PIPELINES
# Add new monthly pipelines here as [command, args...] lists.
# Examples:
#     ["python", "-m", "scripts.rates.citi.rates_monthly_report"],
#     ["python", "-m", "scripts.fx.citi.fx_monthly_aggregates"],
# ============================================================================

PIPELINES: list[list[str]] = [
    ["python", "-m", "scripts.econ.kr.kr_monthly"],
    ["python", "-m", "scripts.econ.id.id_monthly"],
    ["python", "-m", "scripts.econ.au.au_monthly"],
    ["python", "-m", "scripts.econ.nz.nz_monthly"],
    ["python", "-m", "scripts.econ.in.in_monthly"],
]

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
