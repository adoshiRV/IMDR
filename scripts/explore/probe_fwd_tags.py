"""Probe FWD / CURVES / BFLY multi-tenor tags on existing OIS & SWAP_LIBOR curves.

Uses taglisting API to discover what combos exist, then fetches sample data
for a few key curves to confirm data flows end-to-end.

Run:
    python -m scripts.explore.probe_fwd_tags
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from imdr.config.settings import get_settings
from imdr.connectors.citi_velocity import CitiVelocityClient

CACHE_DIR = Path("data/cache/rates")
OUTPUT_PATH = CACHE_DIR / "fwd_probe.json"
SLEEP = 1.2

# Key curves to probe (representative G10 + 1 EM)
PROBE_CURVES = [
    ("RATES.OIS.USD_SOFR", "USD SOFR"),
    ("RATES.OIS.EUR_EUROSTR", "EUR EUROSTR"),
    ("RATES.OIS.GBP_SONIA", "GBP SONIA"),
    ("RATES.OIS.JPY_TONAR", "JPY TONAR"),
    ("RATES.SWAP_LIBOR.USD", "USD LIBOR"),
    ("RATES.SWAP_LIBOR.EUR", "EUR EURIBOR"),
]

# Multi-tenor quote types to probe
QUOTE_TYPES = ["FWD", "CURVES", "BFLY"]


def main() -> None:
    settings = get_settings()
    results: dict = {"tag_listings": {}, "sample_data": {}, "summary": {}}

    with CitiVelocityClient(settings) as client:
        # ── Step 1: Tag listing for each curve x quote type ──
        print("=" * 60)
        print("Step 1: Discover available tags via taglisting")
        print("=" * 60)
        for prefix, label in PROBE_CURVES:
            results["tag_listings"][prefix] = {}
            for qt in QUOTE_TYPES:
                listing_prefix = f"{prefix}.{qt}."
                print(f"  {listing_prefix} ...", end=" ", flush=True)
                time.sleep(SLEEP)
                try:
                    resp = client.fetch_taglisting(listing_prefix)
                    tags = resp.get("tags", [])
                    results["tag_listings"][prefix][qt] = {
                        "count": len(tags),
                        "sample": tags[:30],
                    }
                    print(f"{len(tags)} tags")
                    if tags:
                        for t in tags[:5]:
                            print(f"    {t}")
                except Exception as e:
                    print(f"ERROR: {e}")
                    results["tag_listings"][prefix][qt] = {"count": 0, "error": str(e)}

        # ── Step 2: Fetch sample data for FWD tags ──
        print()
        print("=" * 60)
        print("Step 2: Fetch sample historical data (last 5 days)")
        print("=" * 60)
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=5)

        # Collect sample tags from step 1
        sample_tags: list[str] = []
        for prefix, label in PROBE_CURVES[:3]:  # Just first 3 curves
            for qt in QUOTE_TYPES:
                listing = results["tag_listings"].get(prefix, {}).get(qt, {})
                sample = listing.get("sample", [])
                sample_tags.extend(sample[:5])  # 5 per qt per curve

        if sample_tags:
            print(f"  Fetching {len(sample_tags)} sample tags...")
            # Batch in groups of 100
            for i in range(0, len(sample_tags), 100):
                batch = sample_tags[i:i + 100]
                time.sleep(SLEEP)
                data_resp = client.fetch_historical(batch, start, end)
                body = data_resp.get("body", {})
                for tag in batch:
                    tag_data = body.get(tag, {})
                    values = tag_data.get("c", [])
                    dates = tag_data.get("x", [])
                    if values:
                        print(f"  OK  {tag}: {len(values)} pts, latest={values[-1]}")
                        results["sample_data"][tag] = {
                            "dates": dates[-5:],
                            "values": values[-5:],
                            "count": len(values),
                        }
                    else:
                        print(f"  --  {tag}: NO DATA")
                        results["sample_data"][tag] = {"count": 0}
        else:
            print("  No tags found to probe!")

        # ── Summary ──
        print()
        print("=" * 60)
        print("Summary")
        print("=" * 60)
        for prefix, label in PROBE_CURVES:
            for qt in QUOTE_TYPES:
                listing = results["tag_listings"].get(prefix, {}).get(qt, {})
                count = listing.get("count", 0)
                data_count = sum(
                    1 for tag, d in results["sample_data"].items()
                    if tag.startswith(f"{prefix}.{qt}.") and d.get("count", 0) > 0
                )
                status = f"{data_count}/{min(5, count)} returned data" if count > 0 else "no tags"
                print(f"  {label:20s} {qt:8s} {count:4d} tags  ({status})")
                results["summary"][f"{prefix}.{qt}"] = {
                    "label": label,
                    "quote_type": qt,
                    "tag_count": count,
                    "data_confirmed": data_count,
                }

    # ── Save ──
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(results, indent=2))
    print(f"\nSaved to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
