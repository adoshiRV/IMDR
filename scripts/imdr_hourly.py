"""IMDR Hourly Orchestrator.

Runs all pipelines scheduled at hourly frequency via subprocess.
Each pipeline is isolated — one failure does not block others.

Schedule: Hourly (via Windows Task Scheduler or cron)

Usage:
    python -m scripts.imdr_hourly
"""

from __future__ import annotations

import subprocess
import sys
import time

# ============================================================================
# REGISTERED HOURLY PIPELINES
# Add new hourly pipelines here as [command, args...] lists.
# ============================================================================

PIPELINES: list[list[str]] = [
    ["python", "-m", "scripts.fx.bidfx.fx_bidfx_live"],
    ["python", "-m", "scripts.rates.citi.rates_citi_live_hourly"],
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
