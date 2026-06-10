"""Australia econ — FULL runner (daily + monthly back-to-back). Manual only.

Runs ``au_daily`` then ``au_monthly`` in sequence. Skips weekly because AU
has no genuinely-weekly fetchers. NOT registered in any cron — use this
for first-time setup, post-downtime catch-up, or an ad-hoc full refresh.

Each child orchestrator runs its own pipelines and writes its own email
unless ``--no-email`` is passed (in which case both children are silenced
and this script writes a single consolidated end-of-run line to stdout).

Usage:
    python -m scripts.econ.au.au_full
    python -m scripts.econ.au.au_full --no-email
"""
from __future__ import annotations

import argparse
import datetime
import io
import subprocess
import sys
import time


sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


PIPELINES: list[list[str]] = [
    [sys.executable, "-m", "scripts.econ.au.au_daily"],
    [sys.executable, "-m", "scripts.econ.au.au_monthly"],
]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--no-email", action="store_true",
        help="propagate --no-email to each child orchestrator",
    )
    args = ap.parse_args(argv)

    started_at = datetime.datetime.now(datetime.timezone.utc)
    t0 = time.perf_counter()

    failed: list[str] = []
    for cmd in PIPELINES:
        name = cmd[-1]
        child_cmd = list(cmd)
        if args.no_email:
            child_cmd.append("--no-email")
        print(f"\n>>> {name}")
        p_start = time.perf_counter()
        rc = subprocess.call(child_cmd)
        elapsed = time.perf_counter() - p_start
        if rc != 0:
            print(f"FAIL  {name}  rc={rc}  ({elapsed/60:.1f} min)")
            failed.append(name)
        else:
            print(f"OK    {name}  ({elapsed/60:.1f} min)")

    duration_s = time.perf_counter() - t0
    completed_at = datetime.datetime.now(datetime.timezone.utc)
    print(
        f"\n=== au_full done. started {started_at:%H:%M UTC} → "
        f"finished {completed_at:%H:%M UTC} ({duration_s/60:.1f} min) === "
        f"{len(failed)} child orchestrator(s) failed"
    )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
