"""Deep-dive into COMMODITIES tag tree — full catalog + sample data.

Explores all 5 subcategories (SPOT, EIA, IMPLIED_VOL, INDEX, FORECAST)
using tagbrowsing + taglisting, then fetches sample historical data
to understand values, timestamps, and update frequency.

Run:
    python -m scripts.explore.explore_commodities

Output: data/cache/commodities/commodities_deep.json
"""
from __future__ import annotations

import json
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from imdr.config.settings import get_settings
from imdr.connectors.citi_velocity import CitiVelocityClient

OUTPUT = Path("data/cache/commodities/commodities_deep.json")
SLEEP = 1.1
ROOT = "COMMODITIES"


def _summarize_series(series: dict | list) -> dict:
    """Summarize a single tag's response (dict with x/c arrays)."""
    if isinstance(series, dict) and "x" in series:
        xs = series["x"]
        cs = series["c"]
        return {
            "row_count": len(xs),
            "first_date": xs[0] if xs else None,
            "last_date": xs[-1] if xs else None,
            "first_val": cs[0] if cs else None,
            "last_val": cs[-1] if cs else None,
            "sample_dates": xs[:5],
            "sample_vals": cs[:5],
        }
    return {"row_count": 0}


def drill_recursive(
    client: CitiVelocityClient,
    prefix: str,
    max_depth: int = 5,
    current_depth: int = 0,
) -> dict:
    """Recursively browse the tag tree under a prefix."""
    time.sleep(SLEEP)
    resp = client.fetch_tagbrowsing(prefix)
    if resp.get("status") != "OK":
        print(f"{'  ' * current_depth}  [ERROR] {resp.get('message', 'unknown')}")
        return {"error": resp.get("message", "unknown")}

    children = sorted(resp.get("fields", {}).keys())
    leaves = sorted(resp.get("leaves", []))

    node: dict = {
        "children": children,
        "child_count": len(children),
        "leaves": leaves,
        "leaf_count": len(leaves),
    }

    indent = "  " * (current_depth + 1)
    if children:
        print(f"{indent}Children ({len(children)}): {children[:20]}")
    if leaves:
        print(f"{indent}Leaves ({len(leaves)}): {leaves[:10]}")

    if current_depth < max_depth and children:
        for child in children:
            child_prefix = f"{prefix}.{child}"
            print(f"{indent}  Drilling: {child_prefix}")
            node[child] = drill_recursive(
                client, child_prefix, max_depth, current_depth + 1
            )

    return node


def main() -> None:
    settings = get_settings()
    tree: dict = {}

    with CitiVelocityClient(settings) as client:
        # ================================================================
        # PART 1: Full tag tree discovery
        # ================================================================
        print("=" * 70)
        print("PART 1: DEEP TAG TREE DISCOVERY")
        print("=" * 70)

        # Get top-level subcategories
        resp = client.fetch_tagbrowsing(ROOT)
        subcats = sorted(resp.get("fields", {}).keys())
        print(f"\nSubcategories ({len(subcats)}): {subcats}")
        tree["subcategories"] = subcats

        # --- SPOT (simple — only 3 leaf tags) ---
        print(f"\n{'=' * 60}")
        print("  COMMODITIES.SPOT")
        print(f"{'=' * 60}")
        tree["SPOT"] = drill_recursive(client, f"{ROOT}.SPOT", max_depth=3)

        # --- EIA (16 series x regions) ---
        print(f"\n{'=' * 60}")
        print("  COMMODITIES.EIA")
        print(f"{'=' * 60}")
        tree["EIA"] = drill_recursive(client, f"{ROOT}.EIA", max_depth=4)

        # --- IMPLIED_VOL (5 products x tenors) ---
        print(f"\n{'=' * 60}")
        print("  COMMODITIES.IMPLIED_VOL")
        print(f"{'=' * 60}")
        tree["IMPLIED_VOL"] = drill_recursive(client, f"{ROOT}.IMPLIED_VOL", max_depth=5)

        # --- INDEX (6 indices) ---
        print(f"\n{'=' * 60}")
        print("  COMMODITIES.INDEX")
        print(f"{'=' * 60}")
        tree["INDEX"] = drill_recursive(client, f"{ROOT}.INDEX", max_depth=3)

        # --- FORECAST (6 sectors x products x freq) ---
        print(f"\n{'=' * 60}")
        print("  COMMODITIES.FORECAST")
        print(f"{'=' * 60}")
        tree["FORECAST"] = drill_recursive(client, f"{ROOT}.FORECAST", max_depth=5)

        # ================================================================
        # PART 2: Flat tag listings per subcategory (authoritative counts)
        # ================================================================
        print(f"\n{'=' * 70}")
        print("PART 2: FLAT TAG LISTINGS")
        print(f"{'=' * 70}")

        tag_listings: dict[str, list[str]] = {}
        for subcat in subcats:
            prefix = f"{ROOT}.{subcat}"
            print(f"\n  taglisting: {prefix}")
            time.sleep(SLEEP)
            tl = client.fetch_taglisting(prefix)
            if tl.get("status") == "OK":
                tags = sorted(tl.get("tags", []))
                tag_listings[subcat] = tags
                print(f"    {len(tags)} tags total")
                if tags:
                    print(f"    First 5: {tags[:5]}")
                    print(f"    Last  5: {tags[-5:]}")
            else:
                print(f"    [ERROR] {tl.get('message', 'unknown')}")
                tag_listings[subcat] = []

        tree["_tag_listings"] = tag_listings
        tree["_tag_counts"] = {s: len(t) for s, t in tag_listings.items()}
        tree["_total_tags"] = sum(len(t) for t in tag_listings.values())

        # ================================================================
        # PART 3: Sample data probes
        # ================================================================
        print(f"\n{'=' * 70}")
        print("PART 3: SAMPLE DATA PROBES")
        print(f"{'=' * 70}")

        end = datetime.now(timezone.utc)
        start_30d = end - timedelta(days=30)
        start_1y = end - timedelta(days=365)

        sample_data: dict = {}

        # --- SPOT: all 3 tags, 30 days ---
        spot_tags = tag_listings.get("SPOT", [])
        if spot_tags:
            print(f"\n  Probing SPOT ({len(spot_tags)} tags, last 30 days)")
            time.sleep(SLEEP)
            resp = client.fetch_historical(spot_tags, start_30d, end)
            if resp.get("status") == "OK":
                body = resp.get("body", {})
                for tag, series in body.items():
                    xs = series.get("x", []) if isinstance(series, dict) else []
                    cs = series.get("c", []) if isinstance(series, dict) else []
                    print(f"    {tag}: {len(xs)} points")
                    if xs:
                        print(f"      Range: [{xs[0]}..{xs[-1]}]")
                        print(f"      Values: [{cs[0]}..{cs[-1]}]")
                sample_data["SPOT"] = {
                    tag: _summarize_series(series)
                    for tag, series in body.items()
                }
            else:
                print(f"    [ERROR] {resp.get('message', 'unknown')}")

        # --- EIA: pick a few representative tags, 1 year ---
        eia_tags = tag_listings.get("EIA", [])
        eia_sample_tags = [
            t for t in eia_tags
            if any(k in t for k in ["CRUDE_STOCKS.EIA_TOTAL_US",
                                     "CRUDE_IMPORTS.EIA_TOTAL_US",
                                     "GASOLINE_STOCKS.EIA_TOTAL_US"])
        ][:5]
        if eia_sample_tags:
            print(f"\n  Probing EIA ({len(eia_sample_tags)} sample tags, last 1 year)")
            time.sleep(SLEEP)
            resp = client.fetch_historical(eia_sample_tags, start_1y, end)
            if resp.get("status") == "OK":
                body = resp.get("body", {})
                for tag, series in body.items():
                    xs = series.get("x", []) if isinstance(series, dict) else []
                    cs = series.get("c", []) if isinstance(series, dict) else []
                    print(f"    {tag}: {len(xs)} points")
                    if xs:
                        print(f"      Range: [{xs[0]}..{xs[-1]}], Values: [{cs[0]}..{cs[-1]}]")
                sample_data["EIA"] = {
                    tag: _summarize_series(series)
                    for tag, series in body.items()
                }
            else:
                print(f"    [ERROR] {resp.get('message', 'unknown')}")

        # --- IMPLIED_VOL: pick gold ATM + WTI ATM (first few tenors) ---
        vol_tags = tag_listings.get("IMPLIED_VOL", [])
        vol_sample_tags = [
            t for t in vol_tags
            if ("XAU" in t or "CR_NYM_CL" in t) and "ATM" in t
        ][:10]
        if vol_sample_tags:
            print(f"\n  Probing IMPLIED_VOL ({len(vol_sample_tags)} sample tags, last 30 days)")
            time.sleep(SLEEP)
            resp = client.fetch_historical(vol_sample_tags, start_30d, end)
            if resp.get("status") == "OK":
                body = resp.get("body", {})
                for tag, series in body.items():
                    xs = series.get("x", []) if isinstance(series, dict) else []
                    cs = series.get("c", []) if isinstance(series, dict) else []
                    print(f"    {tag}: {len(xs)} points")
                    if xs:
                        print(f"      Range: [{xs[0]}..{xs[-1]}], Values: [{cs[0]}..{cs[-1]}]")
                sample_data["IMPLIED_VOL"] = {
                    tag: _summarize_series(series)
                    for tag, series in body.items()
                }
            else:
                print(f"    [ERROR] {resp.get('message', 'unknown')}")

        # --- INDEX: all 6, last 30 days ---
        idx_tags = tag_listings.get("INDEX", [])
        if idx_tags:
            print(f"\n  Probing INDEX ({len(idx_tags)} tags, last 30 days)")
            time.sleep(SLEEP)
            resp = client.fetch_historical(idx_tags, start_30d, end)
            if resp.get("status") == "OK":
                body = resp.get("body", {})
                for tag, series in body.items():
                    xs = series.get("x", []) if isinstance(series, dict) else []
                    cs = series.get("c", []) if isinstance(series, dict) else []
                    print(f"    {tag}: {len(xs)} points")
                    if xs:
                        print(f"      Range: [{xs[0]}..{xs[-1]}], Values: [{cs[0]}..{cs[-1]}]")
                sample_data["INDEX"] = {
                    tag: _summarize_series(series)
                    for tag, series in body.items()
                }
            else:
                print(f"    [ERROR] {resp.get('message', 'unknown')}")

        # --- FORECAST: pick energy + precious metals samples ---
        fcast_tags = tag_listings.get("FORECAST", [])
        fcast_sample_tags = [
            t for t in fcast_tags
            if any(k in t for k in ["ENERGY", "P_METALS"])
        ][:10]
        if fcast_sample_tags:
            print(f"\n  Probing FORECAST ({len(fcast_sample_tags)} sample tags, last 1 year)")
            time.sleep(SLEEP)
            resp = client.fetch_historical(fcast_sample_tags, start_1y, end)
            if resp.get("status") == "OK":
                body = resp.get("body", {})
                for tag, series in body.items():
                    xs = series.get("x", []) if isinstance(series, dict) else []
                    cs = series.get("c", []) if isinstance(series, dict) else []
                    print(f"    {tag}: {len(xs)} points")
                    if xs:
                        print(f"      Range: [{xs[0]}..{xs[-1]}], Values: [{cs[0]}..{cs[-1]}]")
                sample_data["FORECAST"] = {
                    tag: _summarize_series(series)
                    for tag, series in body.items()
                }
            else:
                print(f"    [ERROR] {resp.get('message', 'unknown')}")

        tree["_sample_data"] = sample_data

        # ================================================================
        # SUMMARY
        # ================================================================
        print(f"\n{'=' * 70}")
        print("SUMMARY")
        print(f"{'=' * 70}")
        print(f"\nTag counts by subcategory:")
        for subcat in subcats:
            count = len(tag_listings.get(subcat, []))
            print(f"  {subcat:>15}: {count:>5} tags")
        print(f"  {'TOTAL':>15}: {tree['_total_tags']:>5} tags")

        print(f"\nSample data probes:")
        for subcat, data in sample_data.items():
            tags_with_data = sum(1 for v in data.values() if v.get("row_count", 0) > 0)
            total_rows = sum(v.get("row_count", 0) for v in data.values())
            print(f"  {subcat:>15}: {tags_with_data} tags returned data, {total_rows} total rows")

        print(f"\nRate limit remaining: {client.rate_limit_remaining}")

    # Save
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(tree, indent=2, default=str))
    print(f"\nSaved to {OUTPUT}")


if __name__ == "__main__":
    main()
