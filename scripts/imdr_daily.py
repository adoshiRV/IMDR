"""IMDR Daily Orchestrator.

Runs all pipelines scheduled at daily frequency via subprocess.
Each pipeline is isolated — one failure does not block others.

Reads the shared tag quota tracker before each pipeline to log
remaining budget. Skips pipelines that can't fit within remaining quota.

Schedule: 08:00 SGT daily (via Windows Task Scheduler).
  - Summer (EDT): 08:00 SGT = 20:00 previous-day NY — 4h after market close,
    2h after Citi EOD publish.
  - Winter (EST): 08:00 SGT = 19:00 previous-day NY — 3h after close, ~1h
    after Citi publishes. Chosen over 07:00 SGT to eliminate the winter
    edge case where Citi occasionally hadn't finished publishing at 18:00 NY.
  - Retry cron (imdr_retry.py) runs 12:00 / 18:00 SGT to catch tag-quota
    or transient failures.

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
    {"cmd": ["python", "-m", "scripts.fx.citi.fx_rate_citi_live"], "estimated_tags": 800},
    {"cmd": ["python", "-m", "scripts.commodities.citi.cmdty_spot_citi_live"], "estimated_tags": 5},
    {"cmd": ["python", "-m", "scripts.commodities.citi.cmdty_vol_citi_live"], "estimated_tags": 1_200},
    {"cmd": ["python", "-m", "scripts.equity.citi.equity_index_citi_live"], "estimated_tags": 24},
    {"cmd": ["python", "-m", "scripts.equity.citi.equity_vix_citi_live"], "estimated_tags": 5},
    {"cmd": ["python", "-m", "scripts.rates.citi.rates_bench_citi_live"], "estimated_tags": 10},
    {"cmd": ["python", "-m", "scripts.rates.citi.rates_basis_swaps_citi_live"], "estimated_tags": 100},
    # Non-Citi vendor feeds (no tag quota).
    {"cmd": ["python", "-m", "scripts.econ.bis.bis_indonesia"], "estimated_tags": 0},
    {"cmd": ["python", "-m", "scripts.prediction.polymarket.streaming", "cleanup"], "estimated_tags": 0},
    # {"cmd": ["python", "-m", "scripts.prediction.polymarket.teams_post", "--slot", "AM"], "estimated_tags": 0},
    {"cmd": ["python", "-m", "scripts.run_vendor_feed", "barclays_skew"], "estimated_tags": 0},
    {"cmd": ["python", "-m", "scripts.run_vendor_feed", "bbg_fx_daily"], "estimated_tags": 0},
    {"cmd": ["python", "-m", "scripts.run_vendor_feed", "bbg_rates_daily"], "estimated_tags": 0},
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

    # ── Post-batch staleness check ─────────────────────────────────
    # Runs after all pipelines complete to catch silent upstream drops.
    print("\n── Staleness check ──")
    staleness_result = subprocess.run(["python", "-m", "scripts.imdr_staleness_check"])
    if staleness_result.returncode != 0:
        print("WARN  staleness check found stale keys (see email)")

    # ── Polymarket watchlist hygiene (auto-apply) ──────────────────
    # Flips `pruned: true` on DEAD/MISSING slugs in watchlist.yml. .bak written
    # first for rollback. ERROR slugs are kept (transient API failures shouldn't
    # delete real entries). Idempotent — already-pruned entries are skipped.
    print("\n── Polymarket watchlist prune (--apply) ──")
    subprocess.run(["python", "-m", "scripts.prediction.polymarket.streaming",
                    "prune", "--apply"])

    if failed or skipped:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
