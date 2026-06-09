"""IMDR BBG Snapshots Orchestrator.

Runs Bloomberg-sourced intraday pipelines that read the BBG R-pipeline
outputs (live CSVs at ``Z:\\...\\BBG\\FX\\{CCY}\\FX_{CCY}.csv``).

Scheduling design — half-hourly polling 09:45-20:45 SGT
-------------------------------------------------------
The R pipeline fires at 09:30, 11:00, 13:00, 16:00, 18:00, 19:00 SGT
and overwrites each pair's CSV in place. We poll every 30 minutes
through the active window — each BBG batch is captured at least 2-6
times before the next batch overwrites the file. Idempotency means
the redundant fires are MERGE no-ops on the
``(pair, vendor, freq, obs_ts, tenor)`` unique key.

See ``docs/admin/bbg_intraday_schedule.md`` for the full fire grid.

Time-window guard
-----------------
This script enforces the active window itself: outside 09:45-20:45 SGT
it exits silently with code 0 — no fire, no email, no error. This
means any Task Scheduler entry registered for an out-of-window time
is harmless (silent no-op). Pass ``--force`` to bypass the window
check for ad-hoc runs.

Usage:
    python -m scripts.imdr_snapshots_bbg            # window-guarded fire
    python -m scripts.imdr_snapshots_bbg --force    # always fire
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from datetime import datetime, time as dtime, timedelta, timezone

# ── Active window (SGT) ──────────────────────────────────────────────
# Outside this window the orchestrator no-ops silently.
SGT = timezone(timedelta(hours=8))
WINDOW_START = dtime(9, 45)
WINDOW_END = dtime(20, 45)

# ── Registered BBG snapshot pipelines ────────────────────────────────
# Add entries as the BBG integration expands (FX is P0; rates / vol later).
PIPELINES: list[list[str]] = [
    ["python", "-m", "scripts.run_vendor_feed", "bbg_fx_snapshot"],
    ["python", "-m", "scripts.run_vendor_feed", "bbg_rates_snapshot"],
    # ["python", "-m", "scripts.run_vendor_feed", "bbg_vol_snapshot"],
]


def _within_window(now_sgt: datetime) -> bool:
    t = now_sgt.time()
    return WINDOW_START <= t <= WINDOW_END


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--force", action="store_true",
                        help="Bypass the SGT active-window guard.")
    args = parser.parse_args()

    now_sgt = datetime.now(SGT)
    if not args.force and not _within_window(now_sgt):
        # Silent no-op outside the window — exit clean so Task Scheduler
        # records "success", and no email is sent.
        return 0

    if not PIPELINES:
        print("No BBG snapshot pipelines registered — exiting.")
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
