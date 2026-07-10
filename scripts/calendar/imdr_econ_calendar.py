"""IMDR Economic-Calendar Orchestrator.

Runs the two canonical `calendar.cb_events` feeds back-to-back:

  1. **TradingEconomics** (`scripts.calendar.te_calendar_refresh`) — vendor lane 73.
  2. **Bloomberg BQL** (`scripts.calendar.bql_calendar_refresh`) — vendor lane 4 (BBG).

Both are idempotent upserts keyed on `(vendor_id, event_date, country_id,
event_name)`, so re-runs only insert new events and fill in actuals/revisions.
Each feed runs in its own subprocess and is **isolated** — one feed failing
does not block the other (mirrors `scripts.imdr_daily`).

Purpose: give the calendar refresh its own schedulable entrypoint instead of
being buried as a single step inside `imdr_daily`. The work is cheap and
idempotent, so this is safe to schedule frequently (e.g. every 15-30 min) —
which keeps `cb_events` tracking the upstream feeds (the BQL SQLite on the
STIRT share refreshes ~every 15 min; TE is a polite once-per-run GET).

NOTE: this builds the orchestrator only. Registering the Windows scheduled
task is a separate, manual step (owner-run) — this script is not wired into
any other orchestrator.

Usage
-----
    python -m scripts.calendar.imdr_econ_calendar             # both feeds, live
    python -m scripts.calendar.imdr_econ_calendar --dry-run   # both, no DB writes
    python -m scripts.calendar.imdr_econ_calendar --te-only   # TradingEconomics only
    python -m scripts.calendar.imdr_econ_calendar --bql-only  # Bloomberg BQL only
    python -m scripts.calendar.imdr_econ_calendar --bql-all   # BQL full-history backfill
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time

# The two canonical event feeds, run in this order (TE first — a network GET;
# then BQL — a local SQLite read off the STIRT share).
FEEDS: list[dict] = [
    {"name": "tradingeconomics", "module": "scripts.calendar.te_calendar_refresh"},
    {"name": "bloomberg_bql", "module": "scripts.calendar.bql_calendar_refresh"},
]


def main() -> int:
    ap = argparse.ArgumentParser(description="Refresh calendar.cb_events from TE + Bloomberg BQL.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Pass --dry-run to each feed — read + classify, write nothing.")
    ap.add_argument("--te-only", action="store_true", help="Run only the TradingEconomics feed.")
    ap.add_argument("--bql-only", action="store_true", help="Run only the Bloomberg BQL feed.")
    ap.add_argument("--bql-all", action="store_true",
                    help="BQL full-history backfill (passes --all to the BQL feed).")
    args = ap.parse_args()

    if args.te_only and args.bql_only:
        print("ERROR: --te-only and --bql-only are mutually exclusive.", file=sys.stderr)
        return 2

    feeds = FEEDS
    if args.te_only:
        feeds = [f for f in FEEDS if f["name"] == "tradingeconomics"]
    elif args.bql_only:
        feeds = [f for f in FEEDS if f["name"] == "bloomberg_bql"]

    mode = "DRY RUN" if args.dry_run else "LIVE"
    print(f"=== imdr_econ_calendar ({mode}) — {len(feeds)} feed(s) ===\n")

    failed: list[str] = []
    t_all = time.perf_counter()
    for feed in feeds:
        # Bind to the same interpreter/env as the orchestrator (consistent with imdr_daily).
        cmd = [sys.executable, "-m", feed["module"]]
        if args.dry_run:
            cmd.append("--dry-run")
        if feed["name"] == "bloomberg_bql" and args.bql_all:
            cmd.append("--all")

        print(f"RUN   {feed['name']}  ({' '.join(cmd[2:])})")
        t0 = time.perf_counter()
        rc = subprocess.run(cmd).returncode
        elapsed = time.perf_counter() - t0
        if rc != 0:
            print(f"FAIL  {feed['name']}  rc={rc}  ({elapsed:.1f}s)\n")
            failed.append(feed["name"])
        else:
            print(f"OK    {feed['name']}  ({elapsed:.1f}s)\n")

    print(f"=== done in {time.perf_counter() - t_all:.1f}s ===")
    if failed:
        print(f"{len(failed)} feed(s) failed: {', '.join(failed)}")
        return 1
    print("all feeds OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
