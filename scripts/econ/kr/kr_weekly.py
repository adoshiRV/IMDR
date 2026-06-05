"""Korea econ — WEEKLY-cadence orchestrator.

Runs every prod fetcher that publishes WEEKLY-frequency series:
  - scripts.econ.reb.reb_housing               REB R-ONE direct (4 series)
  - scripts.econ.kosis.kosis_reb_housing       KOSIS mirror of REB (4 series)

Each fetcher is a subprocess so one failure doesn't block the others. Each
also invokes the loader at the end (see scripts.econ._runner.invoke_loader),
so a successful run leaves the DB updated.

Wired into scripts/imdr_weekly.py:PIPELINES — runs on the weekly schedule.

Usage:
    python -m scripts.econ.kr.kr_weekly
"""

from __future__ import annotations

import subprocess
import sys
import time


PIPELINES: list[list[str]] = [
    [sys.executable, "-m", "scripts.econ.reb.reb_housing"],
    [sys.executable, "-m", "scripts.econ.kosis.kosis_reb_housing"],
]


def main() -> int:
    failed: list[str] = []
    for cmd in PIPELINES:
        name = cmd[-1]
        t0 = time.perf_counter()
        rc = subprocess.call(cmd)
        elapsed = time.perf_counter() - t0
        if rc != 0:
            print(f"FAIL  {name}  rc={rc}  ({elapsed:.1f}s)")
            failed.append(name)
        else:
            print(f"OK    {name}  ({elapsed:.1f}s)")

    if failed:
        print(f"\n{len(failed)} pipeline(s) failed: {', '.join(failed)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
