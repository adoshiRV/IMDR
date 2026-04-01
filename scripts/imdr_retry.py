"""IMDR Retry — re-run pipelines that failed due to tag quota exhaustion.

Scans today's JSONL run logs for tag_quota errors, checks if the 24h
rolling window has freed enough budget, then re-runs failed pipelines.

Schedule: Separate from imdr_daily — e.g. 12pm and 6pm SGT.
          Register as Windows Task Scheduler entries.

Usage:
    python -m scripts.imdr_retry
    python -m scripts.imdr_retry --date 2026-03-25
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

import structlog

from imdr.config.settings import get_settings
from imdr.connectors.citi_quota import TagQuotaTracker

log = structlog.get_logger("imdr_retry")

# Pipeline name → (command, estimated tags, run log subdir, JSONL prefix)
PIPELINE_REGISTRY: dict[str, dict] = {
    "rates.citi_live": {
        "cmd": ["python", "-m", "scripts.rates.citi.rates_citi_live"],
        "estimated_tags": 20_000,
        "log_dir": "rates/fact_observation",
        "log_prefix": "rates_citi_live",
    },
    "rates.vol_citi_live": {
        "cmd": ["python", "-m", "scripts.rates.citi.rates_vol_citi_live"],
        "estimated_tags": 40_000,
        "log_dir": "rates/swaption_vol",
        "log_prefix": "rates_vol_citi_live",
    },
    "fx.vol_citi_live": {
        "cmd": ["python", "-m", "scripts.fx.citi.fx_vol_citi_live"],
        "estimated_tags": 2_000,
        "log_dir": "fx/fact_vol",
        "log_prefix": "fx_vol_citi_live",
    },
    "commodities.spot_citi_live": {
        "cmd": ["python", "-m", "scripts.commodities.citi.cmdty_spot_citi_live"],
        "estimated_tags": 5,
        "log_dir": "commodities/fact_spot",
        "log_prefix": "cmdty_spot_citi_live",
    },
    "commodities.vol_citi_live": {
        "cmd": ["python", "-m", "scripts.commodities.citi.cmdty_vol_citi_live"],
        "estimated_tags": 1_200,
        "log_dir": "commodities/fact_implied_vol",
        "log_prefix": "cmdty_vol_citi_live",
    },
    "commodities.eia_citi_live": {
        "cmd": ["python", "-m", "scripts.commodities.citi.cmdty_eia_citi_live"],
        "estimated_tags": 70,
        "log_dir": "commodities/fact_eia",
        "log_prefix": "cmdty_eia_citi_live",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="IMDR Retry — re-run quota-failed pipelines")
    parser.add_argument(
        "--date", type=str, default=None,
        help="Override date to check/retry (YYYY-MM-DD). Default: today.",
    )
    return parser.parse_args()


def _find_quota_failures(run_log_dir: str, target_date: date) -> list[dict]:
    """Scan JSONL run logs for today and find pipelines with tag_quota errors.

    Returns list of {pipeline_name, target_date_str, log_path}.
    """
    failures: list[dict] = []
    date_str = target_date.strftime("%Y%m%d")

    for name, info in PIPELINE_REGISTRY.items():
        log_path = Path(run_log_dir) / info["log_dir"] / f"{info['log_prefix']}_{date_str}.jsonl"
        if not log_path.exists():
            continue

        has_quota_error = False
        target_date_from_log: str | None = None

        for line in log_path.read_text(encoding="utf-8").splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            # Extract target date from pipeline details
            if event.get("category") == "pipeline" and event.get("details", {}).get("date"):
                target_date_from_log = event["details"]["date"]

            # Check for quota errors
            if event.get("category") == "tag_quota" and event.get("level") == "error":
                has_quota_error = True

        if has_quota_error:
            failures.append({
                "pipeline_name": name,
                "target_date_str": target_date_from_log or str(target_date),
                "log_path": str(log_path),
            })

    return failures


def main() -> int:
    args = parse_args()
    settings = get_settings()

    if args.date:
        target_date = datetime.strptime(args.date, "%Y-%m-%d").date()
    else:
        target_date = date.today()

    if not settings.run_log_dir:
        print("IMDR_RUN_LOG_DIR not set — cannot scan for failures")
        return 1

    tracker = TagQuotaTracker(
        quota_limit=settings.citi_tag_quota_limit,
        tracker_path=settings.citi_tag_quota_file or None,
    )

    print(f"IMDR Retry — scanning logs for {target_date}")
    print(f"Quota: {tracker.current_usage():,} used / {tracker.remaining():,} remaining\n")

    failures = _find_quota_failures(settings.run_log_dir, target_date)

    if not failures:
        print("No quota failures found — nothing to retry.")
        return 0

    print(f"Found {len(failures)} quota-failed pipeline(s):\n")
    for f in failures:
        print(f"  - {f['pipeline_name']} (target: {f['target_date_str']})")

    retried: list[str] = []
    still_blocked: list[str] = []

    for failure in failures:
        name = failure["pipeline_name"]
        info = PIPELINE_REGISTRY[name]
        estimated = info["estimated_tags"]
        remaining = tracker.remaining()

        if remaining < estimated:
            print(f"\nSKIP  {name}  (need ~{estimated:,}, only {remaining:,} remain)")
            still_blocked.append(name)
            continue

        # Build command with --date override
        cmd = info["cmd"] + ["--date", failure["target_date_str"]]
        print(f"\nRETRY {name}  --date {failure['target_date_str']}  "
              f"(quota: {remaining:,} remaining)")

        t0 = time.perf_counter()
        result = subprocess.run(cmd)
        elapsed = time.perf_counter() - t0

        if result.returncode == 0:
            print(f"OK    {name}  ({elapsed:.1f}s)")
            retried.append(name)
        else:
            print(f"FAIL  {name}  rc={result.returncode}  ({elapsed:.1f}s)")

    print(f"\n--- Retry Summary ---")
    if retried:
        print(f"Retried successfully: {', '.join(retried)}")
    if still_blocked:
        print(f"Still blocked (quota): {', '.join(still_blocked)}")
    if not retried and still_blocked:
        print("All pipelines still blocked — quota has not freed up yet.")

    return 0 if not still_blocked else 1


if __name__ == "__main__":
    sys.exit(main())
