"""Probe Citi Velocity for the USD tags currently silently returning empty.

Covers both open incidents (as of 2026-04-23):
  1. USD swaption vol — USD has returned n_obs=0 on 4 of last 6 daily runs.
  2. US bench rates — FED_FUNDS / US_FED_CP_* / US_FED_PRIME dropped out of
     daily responses (last DB obs 2026-04-14 / 2026-04-17).

Asks Citi Historical for the last 10 days, DAILY frequency. Reports per tag:
  - HTTP status
  - whether the tag appears in the response body
  - number of data points
  - first/last x + sample value (if any)
  - response "type" or error field (if any)

Small quota footprint (~15 tags × 1 batch).

Run:
    python -m scripts.explore.probe_usd_stale_tags
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from imdr.config.settings import get_settings
from imdr.connectors.citi_velocity import CitiVelocityClient
from imdr.universe.rates import get_rates_universe

STALE_BENCH_TAGS = [
    "RATES.BENCH_RATES.FED_FUNDS",
    "RATES.BENCH_RATES.US_FED_CP_1M",
    "RATES.BENCH_RATES.US_FED_CP_2M",
    "RATES.BENCH_RATES.US_FED_CP_3M",
    "RATES.BENCH_RATES.US_FED_PRIME",
]
HEALTHY_BENCH_TAGS = [
    "RATES.BENCH_RATES.US_FED_FUNDS_TARGET",  # control — known to work
]


def pick_usd_vol_sample() -> list[str]:
    """Pick a handful of representative USD vol tags from the cached tree."""
    universe = get_rates_universe()
    all_usd = universe.build_vol_tags("USD")
    if not all_usd:
        return []

    # Prefer diverse coverage: one ATM_RFR, one REALIZED_RFR, one VOL_RATIO_RFR
    wanted_types = {"ATM_RFR", "REALIZED_RFR", "VOL_RATIO_RFR"}
    picks: dict[str, str] = {}
    for tag in all_usd:
        parts = tag.split(".")
        if len(parts) < 4:
            continue
        dt = parts[3]
        if dt in wanted_types and dt not in picks:
            picks[dt] = tag
        if len(picks) == len(wanted_types):
            break
    return list(picks.values())


def summarize(tag: str, body: dict) -> dict:
    entry = body.get(tag)
    if entry is None:
        return {"tag": tag, "present": False, "n_points": 0}
    xs = entry.get("x") or []
    cs = entry.get("c") or []
    return {
        "tag": tag,
        "present": True,
        "type": entry.get("type"),
        "error": entry.get("error"),
        "n_points": len(xs),
        "first_x": xs[0] if xs else None,
        "last_x": xs[-1] if xs else None,
        "sample_value": cs[-1] if cs else None,
    }


def main() -> None:
    settings = get_settings()
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=10)

    usd_vol = pick_usd_vol_sample()
    tags = STALE_BENCH_TAGS + HEALTHY_BENCH_TAGS + usd_vol

    print(f"Probing {len(tags)} tags  ({start.date()} -> {end.date()} DAILY)")
    for t in tags:
        print(f"  - {t}")
    print()

    with CitiVelocityClient(settings) as client:
        resp = client.fetch_historical(tags, start, end, frequency="DAILY")

    body = resp.get("body") or {}
    print(f"HTTP status: {resp.get('status')}")
    print(f"Tags in response body: {len(body)} / {len(tags)}\n")

    print(f"{'tag':<55} {'present':<8} {'n':<5} {'last_x':<20} value")
    print("-" * 105)
    results = []
    for t in tags:
        s = summarize(t, body)
        results.append(s)
        last_x = s.get("last_x") or ""
        val = s.get("sample_value")
        val_str = "" if val is None else f"{val}"
        print(f"{t:<55} {str(s['present']):<8} {s['n_points']:<5} {str(last_x):<20} {val_str}")

    # Dump full response for post-mortem
    out_path = "data/cache/rates/probe_usd_stale.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"tags": tags, "response": resp, "summary": results}, f, indent=2, default=str)
    print(f"\nFull response saved to {out_path}")


if __name__ == "__main__":
    main()
