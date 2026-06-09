"""IMDR Evening Orchestrator.

Runs the PM-slot tasks that aren't tied to the daily ingest cycle. The
canonical use case today is the Polymarket macro-snapshot post to the
Teams channel — the AM post happens inside `imdr_daily.py` at 08:00 SGT;
this runs ~12h later so the desk has a late-day refresh covering NY's
session.

Schedule: 20:00 SGT daily (via Windows Task Scheduler).
  - 20:00 SGT = 08:00 NY (winter) / 07:00 NY (summer) — pre-NY-open, after
    Europe morning has digested overnight Asia. Aligns with the desk's
    expected morning-of-NY-day check-in for prediction-market consensus.

Add new evening tasks here as `[command, args...]` lists.

Usage:
    python -m scripts.imdr_evening
"""

from __future__ import annotations

import subprocess
import sys
import time

TASKS: list[list[str]] = [
    ["python", "-m", "scripts.prediction.polymarket.teams_post", "--slot", "PM"],
]


def main() -> int:
    failed: list[str] = []
    for cmd in TASKS:
        name = cmd[-1] if cmd[-1] not in ("AM", "PM") else cmd[-3]
        print(f"RUN   {name}")
        t0 = time.perf_counter()
        result = subprocess.run(cmd)
        elapsed = time.perf_counter() - t0
        if result.returncode != 0:
            print(f"FAIL  {name}  rc={result.returncode}  ({elapsed:.1f}s)")
            failed.append(name)
        else:
            print(f"OK    {name}  ({elapsed:.1f}s)")

    if failed:
        print(f"\n{len(failed)} task(s) failed: {', '.join(failed)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
