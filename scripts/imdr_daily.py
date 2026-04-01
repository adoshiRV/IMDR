"""IMDR Daily Orchestrator.

Runs all pipelines scheduled at daily frequency via subprocess.
Each pipeline is isolated — one failure does not block others.

Reads the shared tag quota tracker before each pipeline to log
remaining budget. Skips pipelines that can't fit within remaining quota.

Schedule: Daily EOD (via Windows Task Scheduler or cron)

Usage:
    python -m scripts.imdr_daily
"""

from __future__ import annotations

import subprocess
import sys
import time

from imdr.connectors.citi_quota import TagQuotaTracker
from imdr.config.settings import get_settings

# ============================================================================
# REGISTERED DAILY PIPELINES
# Add new daily pipelines here as [command, args...] lists.
# Estimated tag counts (conservative) for pre-flight budget check.
# ============================================================================

PIPELINES: list[dict] = [
    {"cmd": ["python", "-m", "scripts.rates.citi.rates_citi_live"], "estimated_tags": 20_000},
    {"cmd": ["python", "-m", "scripts.rates.citi.rates_vol_citi_live"], "estimated_tags": 40_000},
    {"cmd": ["python", "-m", "scripts.fx.citi.fx_vol_citi_live"], "estimated_tags": 2_000},
    {"cmd": ["python", "-m", "scripts.commodities.citi.cmdty_spot_citi_live"], "estimated_tags": 5},
    {"cmd": ["python", "-m", "scripts.commodities.citi.cmdty_vol_citi_live"], "estimated_tags": 1_200},
]

# ============================================================================


def main() -> int:
    if not PIPELINES:
        return 0

    settings = get_settings()
    tracker = TagQuotaTracker(
        quota_limit=settings.citi_tag_quota_limit,
        tracker_path=settings.citi_tag_quota_file or None,
    )

    failed: list[str] = []
    skipped: list[str] = []

    print(f"Quota: {tracker.current_usage():,} used / {tracker.remaining():,} remaining "
          f"(limit={settings.citi_tag_quota_limit:,})\n")

    for entry in PIPELINES:
        cmd = entry["cmd"]
        estimated = entry["estimated_tags"]
        name = cmd[-1]

        remaining = tracker.remaining()
        if remaining < estimated:
            print(f"SKIP  {name}  (need ~{estimated:,} tags, only {remaining:,} remain)")
            skipped.append(name)
            continue

        print(f"RUN   {name}  (quota: {remaining:,} remaining, need ~{estimated:,})")
        t0 = time.perf_counter()
        result = subprocess.run(cmd)
        elapsed = time.perf_counter() - t0

        # Re-read tracker after subprocess (it wrote its usage)
        new_remaining = tracker.remaining()

        if result.returncode != 0:
            print(f"FAIL  {name}  rc={result.returncode}  ({elapsed:.1f}s)  quota={new_remaining:,}")
            failed.append(name)
        else:
            print(f"OK    {name}  ({elapsed:.1f}s)  quota={new_remaining:,}")

    if skipped:
        print(f"\n{len(skipped)} pipeline(s) skipped (quota): {', '.join(skipped)}")
    if failed:
        print(f"{len(failed)} pipeline(s) failed: {', '.join(failed)}")
        return 1
    if skipped:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
