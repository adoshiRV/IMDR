"""IMDR Citi Snapshots Orchestrator.

Runs Citi-Velocity-sourced intraday pipelines that share the hourly OAuth
client's per-tag rate budget.

Citi enforces a **10 calls/tag/24h rolling window** per OAuth client (separate
from the 100K aggregate tag quota). The hourly cadence used previously
(24 runs/day) blew this limit at hour ~10 every day, producing zero-row runs
for the rest of the day. This orchestrator runs at a fixed 3-hour interval
(8 snapshots/day) so each tag stays well under Citi's 10/24h bucket with
2 retry slots of headroom — sustainable indefinitely with a single
recurring Windows Task Scheduler trigger.

Schedule (every 3 hours, 8 snapshots/day — single WTS "repeat every 3h" trigger):

    UTC      SGT        Coverage
    -----    ---------  -------------------------------------------
    00:00    08:00      Asia pre-open
    03:00    11:00      Asia mid-morning
    06:00    14:00      Asia afternoon
    09:00    17:00      SGT close, LDN pre-open
    12:00    20:00      LDN afternoon, NY pre-open
    15:00    23:00      NY mid-session
    18:00    02:00 +1d  NY close (post FED H.15 release)
    21:00    05:00 +1d  Sydney/Tokyo overnight

Tag-call math: 8 calls/tag/day vs Citi's 10/tag/24h limit = 2 retry slots
of slack.

Usage:
    python -m scripts.imdr_snapshots_citi
"""

from __future__ import annotations

import subprocess
import sys
import time

# ============================================================================
# REGISTERED CITI SNAPSHOT PIPELINES
# Migrated from imdr_hourly.py to honor Citi's 10/tag/24h hourly OAuth budget.
# ============================================================================

PIPELINES: list[list[str]] = [
    ["python", "-m", "scripts.rates.citi.rates_citi_live_hourly"],
    ["python", "-m", "scripts.fx.citi.fx_rate_citi_live_hourly"],
    # Daily rates EOD pull, region-aware. Defaults to --region auto, which
    # maps each 3h fire to ASIA / EUROPE / AMERICAS via UTC_FIRE_WINDOWS.
    # Two of the eight 3h slots (06 + 15 UTC) fall in window gaps and
    # no-op silently — the remaining 6 cover all three regions with
    # idempotent MERGE-based retries that absorb Citi publish lag.
    ["python", "-m", "scripts.rates.citi.rates_citi_live"],
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
