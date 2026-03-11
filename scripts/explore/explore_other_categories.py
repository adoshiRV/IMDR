"""Explore Citi Velocity tag tree for FX, EQUITY, and COMMODITIES categories.

Run:
    python -m scripts.explore.explore_other_categories

Output: saves to data/cache/{category}_tree.json
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from imdr.config.settings import get_settings
from imdr.connectors.citi_velocity import CitiVelocityClient

CACHE_DIR = Path("data/cache")
SLEEP_SEC = 1.1
CATEGORIES = ["FX", "EQUITY", "COMMODITIES"]


def explore_category(client: CitiVelocityClient, category: str) -> dict:
    """Browse a top-level category 2-3 levels deep."""
    print(f"\n{'=' * 60}")
    print(f"  {category}")
    print(f"{'=' * 60}")

    resp = client.fetch_tagbrowsing(category)
    if resp.get("status") != "OK":
        print(f"  [ERROR] {resp.get('message', 'unknown')}")
        return {"error": resp.get("message", "unknown")}

    subcats = sorted(resp.get("fields", {}).keys())
    leaves = resp.get("leaves", [])
    print(f"  Subcategories ({len(subcats)}): {subcats}")
    if leaves:
        print(f"  Leaves: {leaves[:10]}")

    tree: dict = {}

    for subcat in subcats:
        prefix = f"{category}.{subcat}"
        print(f"\n  --- {prefix} ---")
        time.sleep(SLEEP_SEC)

        sub_resp = client.fetch_tagbrowsing(prefix)
        if sub_resp.get("status") != "OK":
            print(f"    [ERROR] {sub_resp.get('message', 'unknown')}")
            tree[subcat] = {"error": True}
            continue

        children = sorted(sub_resp.get("fields", {}).keys())
        sub_leaves = sub_resp.get("leaves", [])
        print(f"    Children ({len(children)}): {children[:30]}")
        if sub_leaves:
            print(f"    Leaves ({len(sub_leaves)}): {sub_leaves[:10]}")

        tree[subcat] = {
            "children": children,
            "child_count": len(children),
            "leaf_sample": sub_leaves[:5] if sub_leaves else [],
        }

        # Drill one more level into first 3 children to understand structure
        for child in children[:3]:
            child_prefix = f"{prefix}.{child}"
            print(f"      Drilling: {child_prefix}")
            time.sleep(SLEEP_SEC)
            child_resp = client.fetch_tagbrowsing(child_prefix)
            if child_resp.get("status") == "OK":
                grandchildren = sorted(child_resp.get("fields", {}).keys())
                gc_leaves = child_resp.get("leaves", [])
                print(f"        Children: {grandchildren[:20]}")
                if gc_leaves:
                    print(f"        Leaves: {gc_leaves[:5]}")
                tree[subcat][f"_sample_{child}"] = {
                    "children": grandchildren[:20],
                    "leaves_sample": gc_leaves[:5],
                }
            else:
                print(f"        [ERROR] {child_resp.get('message', 'unknown')}")

    return tree


def main() -> None:
    settings = get_settings()

    with CitiVelocityClient(settings) as client:
        all_trees: dict[str, dict] = {}

        for category in CATEGORIES:
            tree = explore_category(client, category)
            all_trees[category] = tree

            # Save each category individually
            out_path = CACHE_DIR / category.lower() / f"{category.lower()}_tree.json"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(tree, indent=2, default=str))
            print(f"\n  Saved to {out_path}")

        # Summary
        print(f"\n{'=' * 60}")
        print("SUMMARY")
        print(f"{'=' * 60}")
        for cat, tree in all_trees.items():
            subcats = [k for k in tree.keys() if not k.startswith("_") and k != "error"]
            print(f"\n{cat}: {len(subcats)} subcategories")
            for s in sorted(subcats):
                info = tree[s]
                if isinstance(info, dict) and "children" in info:
                    print(f"  {s}: {info.get('child_count', '?')} children — {info.get('children', [])[:10]}")


if __name__ == "__main__":
    main()
