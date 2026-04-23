"""Probe RATES.FORWARD on Citi Velocity — discover full tag structure and sample data.

Browses the FORWARD subtree deeper than the original exploration,
then fetches sample historical data for key countries.

Run:
    python -m scripts.explore.probe_forward_rates
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

from imdr.config.settings import get_settings
from imdr.connectors.citi_velocity import CitiVelocityClient

CACHE_DIR = Path("data/cache/rates")
OUTPUT_PATH = CACHE_DIR / "forward_probe.json"
SLEEP = 1.2

# Countries to probe deeply
PRIORITY_COUNTRIES = ["USA", "DEU", "GBR", "JPN", "AUS"]
# Also list all countries but just one level
ALL_COUNTRIES = [
    "AUS", "AUT", "BEL", "CAN", "CYP", "DEU", "DNK", "ESP", "FIN", "FRA",
    "GBR", "GRC", "IRL", "ITA", "JPN", "LUX", "NLD", "NOR", "NZL", "PRT",
    "SVK", "SVN", "SWE", "USA",
]


def browse_level(client: CitiVelocityClient, prefix: str) -> dict:
    """Browse one level and return fields/leaves."""
    resp = client.fetch_tagbrowsing(prefix)
    if resp.get("status") != "OK":
        return {"error": resp.get("message", "unknown")}
    return {
        "fields": sorted(resp.get("fields", {}).keys()),
        "leaves": resp.get("leaves", [])[:30],
        "leaf_count": len(resp.get("leaves", [])),
    }


def main() -> None:
    settings = get_settings()
    results: dict = {"countries": {}, "sample_data": {}}

    with CitiVelocityClient(settings) as client:
        # ── Step 1: Browse each country's start tenors ──
        print("=" * 60)
        print("Step 1: Browse FORWARD.{COUNTRY} for all 24 countries")
        print("=" * 60)
        for country in ALL_COUNTRIES:
            prefix = f"RATES.FORWARD.{country}"
            print(f"  {prefix} ...", end=" ")
            time.sleep(SLEEP)
            level = browse_level(client, prefix)
            results["countries"][country] = {"starts": level}
            print(f"fields={level.get('fields', [])}")

        # ── Step 2: For priority countries, drill one more level ──
        print()
        print("=" * 60)
        print("Step 2: Drill FORWARD.{COUNTRY}.{START} for priority countries")
        print("=" * 60)
        for country in PRIORITY_COUNTRIES:
            starts = results["countries"][country]["starts"].get("fields", [])
            results["countries"][country]["detail"] = {}
            for start in starts:
                prefix = f"RATES.FORWARD.{country}.{start}"
                print(f"  {prefix} ...", end=" ")
                time.sleep(SLEEP)
                level = browse_level(client, prefix)
                results["countries"][country]["detail"][start] = level
                print(f"fields={level.get('fields', [])} leaves={level.get('leaves', [])[:5]}")

        # ── Step 3: Drill one more level to find the actual tag leaves ──
        print()
        print("=" * 60)
        print("Step 3: Find leaf tags for USA")
        print("=" * 60)
        usa_detail = results["countries"]["USA"].get("detail", {})
        results["usa_leaves"] = {}
        for start, info in usa_detail.items():
            for tenor_or_field in info.get("fields", [])[:3]:  # first 3
                prefix = f"RATES.FORWARD.USA.{start}.{tenor_or_field}"
                print(f"  {prefix} ...", end=" ")
                time.sleep(SLEEP)
                level = browse_level(client, prefix)
                results["usa_leaves"][f"{start}.{tenor_or_field}"] = level
                print(f"fields={level.get('fields', [])} leaves={level.get('leaves', [])[:5]}")

        # ── Step 4: Fetch taglisting for USA FORWARD ──
        print()
        print("=" * 60)
        print("Step 4: Tag listing for USA FORWARD")
        print("=" * 60)
        time.sleep(SLEEP)
        listing_resp = client.fetch_taglisting("RATES.FORWARD.USA.")
        tags = listing_resp.get("tags", [])
        results["usa_taglisting"] = tags[:100]
        results["usa_tag_count"] = len(tags)
        print(f"  Total tags: {len(tags)}")
        for t in tags[:20]:
            print(f"    {t}")

        # ── Step 5: Fetch sample data for a few tags ──
        print()
        print("=" * 60)
        print("Step 5: Sample historical data (last 5 days)")
        print("=" * 60)
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=5)

        # Build sample tags — try the documented format
        sample_tags = [
            "RATES.FORWARD.USA.5Y.5Y.CITI",
            "RATES.FORWARD.USA.2Y.10Y.CITI",
            "RATES.FORWARD.USA.1Y.1Y.CITI",
            "RATES.FORWARD.DEU.5Y.5Y.CITI",
            "RATES.FORWARD.GBR.5Y.5Y.CITI",
            "RATES.FORWARD.JPN.5Y.5Y.CITI",
            "RATES.FORWARD.AUS.5Y.5Y.CITI",
        ]

        # Also try tags from taglisting if we got any
        if tags:
            for t in tags[:5]:
                if t not in sample_tags:
                    sample_tags.append(t)

        print(f"  Fetching {len(sample_tags)} tags...")
        time.sleep(SLEEP)
        data_resp = client.fetch_historical(sample_tags, start, end)
        body = data_resp.get("body", {})
        for tag in sample_tags:
            tag_data = body.get(tag, {})
            values = tag_data.get("c", [])
            dates = tag_data.get("x", [])
            if values:
                print(f"  {tag}: {len(values)} pts, latest={values[-1]}")
                results["sample_data"][tag] = {
                    "dates": dates[-5:],
                    "values": values[-5:],
                    "count": len(values),
                }
            else:
                print(f"  {tag}: NO DATA")
                results["sample_data"][tag] = {"count": 0}

    # ── Save ──
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(results, indent=2))
    print(f"\nSaved to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
