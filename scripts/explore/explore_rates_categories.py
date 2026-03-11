"""Explore the Citi Velocity RATES tag tree to discover all subcategories.

Uses the tagbrowsing API to drill down the RATES hierarchy and find
instrument types beyond OIS and SWAP_LIBOR.

Run:
    python -m scripts.explore.explore_rates_categories

Output: prints the tree and saves to data/cache/rates/rates_tree.json
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from imdr.config.settings import get_settings
from imdr.connectors.citi_velocity import CitiVelocityClient

CACHE_DIR = Path("data/cache/rates")
OUTPUT_PATH = CACHE_DIR / "rates_tree.json"

# How many levels deep to explore (RATES.X.Y.Z = 3 levels below RATES)
MAX_DEPTH = 3

# Rate limit between API calls
SLEEP_SEC = 1.1


def browse_tree(client: CitiVelocityClient, prefix: str, depth: int = 0) -> dict:
    """Recursively browse the tag tree, returning structure at each level."""
    resp = client.fetch_tagbrowsing(prefix)

    if resp.get("status") != "OK":
        print(f"  {'  ' * depth}[ERROR] {prefix}: {resp.get('message', 'unknown error')}")
        return {"error": resp.get("message", "unknown")}

    fields = resp.get("fields", {})
    leaves = resp.get("leaves", [])

    node: dict = {}

    if leaves:
        node["_leaves"] = leaves[:20]  # sample, not all
        node["_leaf_count"] = len(leaves)

    if fields and depth < MAX_DEPTH:
        for child_name in sorted(fields.keys()):
            child_prefix = f"{prefix}.{child_name}" if prefix else child_name
            indent = "  " * (depth + 1)
            print(f"{indent}{child_prefix}")
            time.sleep(SLEEP_SEC)
            node[child_name] = browse_tree(client, child_prefix, depth + 1)
    elif fields:
        # At max depth, just list field names without drilling deeper
        node["_children"] = sorted(fields.keys())
        node["_child_count"] = len(fields)

    return node


def main() -> None:
    settings = get_settings()

    with CitiVelocityClient(settings) as client:
        # Step 1: Browse the root to see all top-level categories
        print("=" * 60)
        print("Step 1: Root-level categories")
        print("=" * 60)
        root_resp = client.fetch_tagbrowsing("")
        root_fields = root_resp.get("fields", {})
        print(f"Root categories: {sorted(root_fields.keys())}")
        print()

        # Step 2: Browse RATES to find all instrument types
        print("=" * 60)
        print("Step 2: RATES subcategories")
        print("=" * 60)
        time.sleep(SLEEP_SEC)
        rates_resp = client.fetch_tagbrowsing("RATES")
        rates_fields = rates_resp.get("fields", {})
        rates_leaves = rates_resp.get("leaves", [])
        print(f"RATES subcategories: {sorted(rates_fields.keys())}")
        if rates_leaves:
            print(f"RATES leaves (direct tags): {rates_leaves[:10]}")
        print()

        # Step 3: For each subcategory under RATES, explore one level deeper
        print("=" * 60)
        print("Step 3: Drilling into each RATES subcategory")
        print("=" * 60)
        tree: dict = {}

        for subcat in sorted(rates_fields.keys()):
            prefix = f"RATES.{subcat}"
            print(f"\n--- {prefix} ---")
            time.sleep(SLEEP_SEC)
            resp = client.fetch_tagbrowsing(prefix)

            if resp.get("status") != "OK":
                print(f"  [ERROR] {resp.get('message', 'unknown')}")
                tree[subcat] = {"error": True}
                continue

            children = sorted(resp.get("fields", {}).keys())
            child_leaves = resp.get("leaves", [])
            print(f"  Children ({len(children)}): {children[:30]}")
            if child_leaves:
                print(f"  Leaves ({len(child_leaves)}): {child_leaves[:10]}")

            tree[subcat] = {
                "children": children,
                "child_count": len(children),
                "leaf_sample": child_leaves[:5] if child_leaves else [],
            }

            # For new (non-OIS, non-SWAP_LIBOR) subcategories, go one level deeper
            if subcat not in ("OIS", "SWAP_LIBOR") and children:
                # Sample first 3 children to understand the structure
                for child in children[:3]:
                    child_prefix = f"{prefix}.{child}"
                    print(f"    Drilling: {child_prefix}")
                    time.sleep(SLEEP_SEC)
                    child_resp = client.fetch_tagbrowsing(child_prefix)
                    if child_resp.get("status") == "OK":
                        grandchildren = sorted(child_resp.get("fields", {}).keys())
                        gc_leaves = child_resp.get("leaves", [])
                        print(f"      Children: {grandchildren[:20]}")
                        if gc_leaves:
                            print(f"      Leaves: {gc_leaves[:5]}")
                        tree[subcat][f"_sample_{child}"] = {
                            "children": grandchildren,
                            "leaves_sample": gc_leaves[:5],
                        }
                    else:
                        print(f"      [ERROR] {child_resp.get('message', 'unknown')}")

        # Step 4: Summary
        print("\n" + "=" * 60)
        print("SUMMARY: All RATES subcategories")
        print("=" * 60)
        known = {"OIS", "SWAP_LIBOR"}
        new_subcats = set(tree.keys()) - known
        print(f"\nAlready tracked: {sorted(known & set(tree.keys()))}")
        print(f"NEW subcategories: {sorted(new_subcats)}")
        for s in sorted(new_subcats):
            info = tree[s]
            print(f"  {s}: {info.get('child_count', '?')} children — {info.get('children', [])[:10]}")

        # Save
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(json.dumps(tree, indent=2, default=str))
        print(f"\nTree saved to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
