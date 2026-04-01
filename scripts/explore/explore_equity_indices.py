"""Probe EQUITY tag prefixes visible in the Citi Velocity UI but not
returned by tagbrowsing("EQUITY").

The UI shows subcategories: Citi indices, Convertible Bonds, ETF,
Forecast, indices, Prime, Stocks, Variance Swap, Vol Swap, Volatility.

The tag preview shows: EQUITY.EQUITY_INDEX..SPX.LEVEL.REUTERS
This suggests prefixes like EQUITY_INDEX, EQUITY_ETF, etc. that may
sit at the *root* level, not nested under EQUITY.

Run:
    python -m scripts.explore.explore_equity_indices

Output: data/cache/equity/equity_indices_deep.json
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from imdr.config.settings import get_settings
from imdr.connectors.citi_velocity import CitiVelocityClient

OUTPUT = Path("data/cache/equity/equity_indices_deep.json")
SLEEP = 1.1


def _summarize_series(series: dict | list) -> dict:
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


def browse(client: CitiVelocityClient, prefix: str, label: str = "") -> dict | None:
    """Fetch tagbrowsing for a prefix, print summary, return result."""
    time.sleep(SLEEP)
    resp = client.fetch_tagbrowsing(prefix)
    status = resp.get("status")
    children = sorted(resp.get("fields", {}).keys())
    leaves = sorted(resp.get("leaves", []))
    if status != "OK":
        print(f"  {label or prefix}: [ERROR] {resp.get('message', 'unknown')}")
        return None
    print(f"  {label or prefix}: {len(children)} children, {len(leaves)} leaves")
    if children:
        print(f"    Children: {children[:30]}{'...' if len(children)>30 else ''}")
    if leaves:
        print(f"    Leaves: {leaves[:10]}{'...' if len(leaves)>10 else ''}")
    return {"children": children, "leaves": leaves,
            "child_count": len(children), "leaf_count": len(leaves)}


def drill(client: CitiVelocityClient, prefix: str,
          max_depth: int = 4, depth: int = 0) -> dict:
    """Recursively browse a prefix."""
    time.sleep(SLEEP)
    resp = client.fetch_tagbrowsing(prefix)
    if resp.get("status") != "OK":
        return {"error": resp.get("message", "unknown")}
    children = sorted(resp.get("fields", {}).keys())
    leaves = sorted(resp.get("leaves", []))
    indent = "  " * (depth + 2)
    node = {"children": children, "child_count": len(children),
            "leaves": leaves, "leaf_count": len(leaves)}
    if children:
        print(f"{indent}Children ({len(children)}): {children[:15]}")
    if leaves:
        print(f"{indent}Leaves ({len(leaves)}): {leaves[:8]}")
    if depth < max_depth and children:
        for child in children:
            cp = f"{prefix}.{child}"
            print(f"{indent}  -> {cp}")
            node[child] = drill(client, cp, max_depth, depth + 1)
    return node


def main() -> None:
    settings = get_settings()
    results: dict = {}

    with CitiVelocityClient(settings) as client:
        # ================================================================
        # STEP 1: Probe candidate root prefixes
        # ================================================================
        print("=" * 70)
        print("STEP 1: PROBE ROOT PREFIXES")
        print("=" * 70)

        # From the UI tag: EQUITY.EQUITY_INDEX..SPX.LEVEL.REUTERS
        # Try various prefix guesses
        candidates = [
            "EQUITY.EQUITY_INDEX",
            "EQUITY.EQUITY_ETF",
            "EQUITY.STOCKS",
            "EQUITY.ETF",
            "EQUITY.INDICES",
            "EQUITY.INDEX",
            "EQUITY.CONVERTIBLE_BONDS",
            "EQUITY.VOLATILITY",
            "EQUITY.VOL",
            # Maybe root-level?
            "EQUITY_INDEX",
            "EQUITY_ETF",
            "EQ_INDEX",
            "EQ",
        ]

        found_prefixes = {}
        for prefix in candidates:
            result = browse(client, prefix, prefix)
            if result and (result["child_count"] > 0 or result["leaf_count"] > 0):
                found_prefixes[prefix] = result

        results["_probed_prefixes"] = {
            "candidates_tried": candidates,
            "found": list(found_prefixes.keys()),
        }
        results["_prefix_results"] = found_prefixes

        # ================================================================
        # STEP 2: For each found prefix, drill deeper
        # ================================================================
        print(f"\n{'=' * 70}")
        print("STEP 2: DRILL FOUND PREFIXES")
        print(f"{'=' * 70}")

        for prefix, info in found_prefixes.items():
            print(f"\n  === {prefix} ({info['child_count']} children) ===")
            # Drill children but limit to avoid quota burn
            children = info["children"]
            # For large lists, only sample first 5
            sample = children[:5] if len(children) > 10 else children
            results[prefix] = {"_overview": info}
            for child in sample:
                cp = f"{prefix}.{child}"
                print(f"\n    Drilling: {cp}")
                results[prefix][child] = drill(client, cp, max_depth=3, depth=0)

        # ================================================================
        # STEP 3: Tag listings for found prefixes
        # ================================================================
        print(f"\n{'=' * 70}")
        print("STEP 3: TAG LISTINGS")
        print(f"{'=' * 70}")

        tag_listings: dict[str, list[str]] = {}
        for prefix in found_prefixes:
            print(f"\n  taglisting: {prefix}")
            time.sleep(SLEEP)
            tl = client.fetch_taglisting(prefix)
            if tl.get("status") == "OK":
                tags = sorted(tl.get("tags", []))
                tag_listings[prefix] = tags
                print(f"    {len(tags)} tags")
                if tags:
                    print(f"    First 5: {tags[:5]}")
                    print(f"    Last  5: {tags[-5:]}")
            else:
                print(f"    [ERROR] {tl.get('message', 'unknown')}")
                tag_listings[prefix] = []

        results["_tag_listings"] = tag_listings
        results["_tag_counts"] = {p: len(t) for p, t in tag_listings.items()}

        # ================================================================
        # STEP 4: Try constructing tags manually based on UI pattern
        # ================================================================
        print(f"\n{'=' * 70}")
        print("STEP 4: MANUAL TAG PROBES (based on UI pattern)")
        print(f"{'=' * 70}")

        # The UI shows: EQUITY.EQUITY_INDEX..SPX.LEVEL.REUTERS
        # Try fetching data for tags that match the UI pattern
        end = datetime.now(timezone.utc)
        start_30d = end - timedelta(days=30)

        manual_tags = [
            "EQUITY.EQUITY_INDEX..SPX.LEVEL.REUTERS",
            "EQUITY.EQUITY_INDEX.SPX.LEVEL.REUTERS",
            "EQUITY.EQUITY_INDEX.SPX.LEVEL.CITI",
            "EQUITY.EQUITY_INDEX..NDX.LEVEL.REUTERS",
            "EQUITY.EQUITY_INDEX..FTSE.LEVEL.REUTERS",
            # ETF patterns
            "EQUITY.EQUITY_ETF..SPY.LEVEL.REUTERS",
            "EQUITY.EQUITY_ETF.SPY.LEVEL.REUTERS",
            "EQUITY.ETF..SPY.LEVEL.REUTERS",
        ]

        print(f"\n  Trying {len(manual_tags)} manual tag patterns...")
        time.sleep(SLEEP)
        resp = client.fetch_historical(manual_tags, start_30d, end)
        manual_results = {}
        if resp.get("status") == "OK":
            body = resp.get("body", {})
            for tag, series in body.items():
                xs = series.get("x", []) if isinstance(series, dict) else []
                cs = series.get("c", []) if isinstance(series, dict) else []
                print(f"    {tag}: {len(xs)} points")
                if xs:
                    print(f"      Range: [{xs[0]}..{xs[-1]}], Vals: [{cs[0]}..{cs[-1]}]")
                manual_results[tag] = _summarize_series(series)
        else:
            print(f"    [ERROR] {resp.get('message', 'unknown')}")

        results["_manual_probes"] = manual_results

        # Also try metadata on these tags
        print(f"\n  Fetching metadata for manual tags...")
        time.sleep(SLEEP)
        meta = client.fetch_metadata(manual_tags)
        results["_manual_metadata"] = meta
        if meta.get("status") == "OK":
            for tag, info in meta.get("body", {}).items():
                print(f"    {tag}: {info}")

        # ================================================================
        # STEP 5: Also try tagbrowsing with the double-dot pattern
        # ================================================================
        print(f"\n{'=' * 70}")
        print("STEP 5: DOUBLE-DOT PREFIX PROBES")
        print(f"{'=' * 70}")

        # The tag has EQUITY.EQUITY_INDEX..SPX — maybe the empty segment
        # means we should browse EQUITY.EQUITY_INDEX.
        # Let's also try the exact ticker lookup
        dd_prefixes = [
            "EQUITY.EQUITY_INDEX.",  # trailing dot
            "EQUITY.EQUITY_INDEX..SPX",
        ]
        for prefix in dd_prefixes:
            result = browse(client, prefix, prefix)
            if result:
                results[f"_dd_{prefix}"] = result

        # ================================================================
        # SUMMARY
        # ================================================================
        print(f"\n{'=' * 70}")
        print("SUMMARY")
        print(f"{'=' * 70}")
        print(f"\nPrefixes found: {list(found_prefixes.keys())}")
        for prefix, tags in tag_listings.items():
            print(f"  {prefix}: {len(tags)} tags")
        print(f"\nManual probes with data: "
              f"{sum(1 for v in manual_results.values() if v.get('row_count',0)>0)}"
              f"/{len(manual_tags)}")
        print(f"\nRate limit remaining: {client.rate_limit_remaining}")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(results, indent=2, default=str))
    print(f"\nSaved to {OUTPUT}")


if __name__ == "__main__":
    main()
