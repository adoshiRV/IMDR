"""Deep-dive into EQUITY tag tree — full catalog + sample data.

Explores all 6 subcategories (CITI_EQ_INDICES, EQIVOL, FORECAST,
PRIME, VARSWAP, VOLSWAP) using tagbrowsing + taglisting, then fetches
sample historical data to understand values, timestamps, and update
frequency.

Run:
    python -m scripts.explore.explore_equity

Output: data/cache/equity/equity_deep.json
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from imdr.config.settings import get_settings
from imdr.connectors.citi_velocity import CitiVelocityClient

OUTPUT = Path("data/cache/equity/equity_deep.json")
SLEEP = 1.1
ROOT = "EQUITY"


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

        # --- CITI_EQ_INDICES (CIS_INDEX, DELTAONE) ---
        # DELTAONE has hundreds of proprietary indices per region — only
        # enumerate one level deep, then sample a few tickers to get leaf
        # structure without burning thousands of API calls.
        print(f"\n{'=' * 60}")
        print("  EQUITY.CITI_EQ_INDICES")
        print(f"{'=' * 60}")
        tree["CITI_EQ_INDICES"] = drill_recursive(
            client, f"{ROOT}.CITI_EQ_INDICES", max_depth=2
        )
        # Deep-drill a handful of representative DELTAONE tickers
        for region in ["ALL", "NAM"]:
            prefix = f"{ROOT}.CITI_EQ_INDICES.DELTAONE.{region}"
            time.sleep(SLEEP)
            resp = client.fetch_tagbrowsing(prefix)
            if resp.get("status") == "OK":
                kids = sorted(resp.get("fields", {}).keys())
                tree["CITI_EQ_INDICES"][f"_deltaone_{region}_children"] = kids
                tree["CITI_EQ_INDICES"][f"_deltaone_{region}_count"] = len(kids)
                print(f"  DELTAONE.{region}: {len(kids)} tickers")
                # Drill first 3 to understand leaf structure
                for ticker in kids[:3]:
                    tp = f"{prefix}.{ticker}"
                    print(f"    Drilling sample: {tp}")
                    tree["CITI_EQ_INDICES"][f"_drill_{region}_{ticker}"] = (
                        drill_recursive(client, tp, max_depth=3, current_depth=2)
                    )

        # --- EQIVOL (INDEX_CORR — 11 indices) ---
        print(f"\n{'=' * 60}")
        print("  EQUITY.EQIVOL")
        print(f"{'=' * 60}")
        tree["EQIVOL"] = drill_recursive(client, f"{ROOT}.EQIVOL", max_depth=3)
        # Deep-drill SPX to understand full leaf structure
        for idx in ["SPX", "SX5E"]:
            prefix = f"{ROOT}.EQIVOL.INDEX_CORR.{idx}"
            print(f"    Drilling sample: {prefix}")
            tree["EQIVOL"][f"_drill_{idx}"] = drill_recursive(
                client, prefix, max_depth=4, current_depth=2
            )

        # --- FORECAST (15 countries/regions) ---
        # Drill 2 levels to get country → index list, then drill a few
        print(f"\n{'=' * 60}")
        print("  EQUITY.FORECAST")
        print(f"{'=' * 60}")
        tree["FORECAST"] = drill_recursive(client, f"{ROOT}.FORECAST", max_depth=3)
        # Deep-drill USA + GBR to understand leaf structure
        for country in ["USA", "GBR", "JPN"]:
            prefix = f"{ROOT}.FORECAST.{country}"
            print(f"    Drilling sample: {prefix}")
            tree["FORECAST"][f"_drill_{country}"] = drill_recursive(
                client, prefix, max_depth=5, current_depth=1
            )

        # --- PRIME (empty in shallow cache) ---
        print(f"\n{'=' * 60}")
        print("  EQUITY.PRIME")
        print(f"{'=' * 60}")
        tree["PRIME"] = drill_recursive(client, f"{ROOT}.PRIME", max_depth=3)

        # --- VARSWAP (CONSTANT_EXPIRY, FIXED_EXPIRY — 20+ indices each) ---
        # Enumerate 2 levels deep (type → index list), then drill a few
        # representative indices to get the full leaf structure.
        print(f"\n{'=' * 60}")
        print("  EQUITY.VARSWAP")
        print(f"{'=' * 60}")
        tree["VARSWAP"] = drill_recursive(client, f"{ROOT}.VARSWAP", max_depth=2)
        # Deep-drill SPX + NDX in each expiry type
        for etype in ["CONSTANT_EXPIRY", "FIXED_EXPIRY"]:
            for idx in ["SPX", "NDX"]:
                prefix = f"{ROOT}.VARSWAP.{etype}.{idx}"
                print(f"    Drilling sample: {prefix}")
                tree["VARSWAP"][f"_drill_{etype}_{idx}"] = drill_recursive(
                    client, prefix, max_depth=4, current_depth=2
                )

        # --- VOLSWAP (197 tickers — drill first 5 to understand structure, skip rest) ---
        print(f"\n{'=' * 60}")
        print("  EQUITY.VOLSWAP")
        print(f"{'=' * 60}")
        # Only drill a few representative tickers to understand the structure
        # (197 tickers x deep drill would burn too many API calls)
        time.sleep(SLEEP)
        vs_resp = client.fetch_tagbrowsing(f"{ROOT}.VOLSWAP")
        vs_children = sorted(vs_resp.get("fields", {}).keys())
        vs_leaves = sorted(vs_resp.get("leaves", []))
        tree["VOLSWAP"] = {
            "children": vs_children,
            "child_count": len(vs_children),
            "leaves": vs_leaves,
            "leaf_count": len(vs_leaves),
        }
        print(f"  VOLSWAP: {len(vs_children)} tickers")

        # Drill a few representative tickers (US large-cap, EU, index)
        sample_tickers = ["SPX", "AAPL_O", "NVDA_O", "GDAXI", "FTSE"]
        sample_tickers = [t for t in sample_tickers if t in vs_children]
        for ticker in sample_tickers:
            prefix = f"{ROOT}.VOLSWAP.{ticker}"
            print(f"    Drilling sample: {prefix}")
            tree["VOLSWAP"][f"_drill_{ticker}"] = drill_recursive(
                client, prefix, max_depth=4, current_depth=1
            )

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

        # --- CITI_EQ_INDICES: pick a few tags ---
        idx_tags = tag_listings.get("CITI_EQ_INDICES", [])
        idx_sample = idx_tags[:10]
        if idx_sample:
            print(f"\n  Probing CITI_EQ_INDICES ({len(idx_sample)} sample tags, last 30 days)")
            time.sleep(SLEEP)
            resp = client.fetch_historical(idx_sample, start_30d, end)
            if resp.get("status") == "OK":
                body = resp.get("body", {})
                for tag, series in body.items():
                    xs = series.get("x", []) if isinstance(series, dict) else []
                    cs = series.get("c", []) if isinstance(series, dict) else []
                    print(f"    {tag}: {len(xs)} points")
                    if xs:
                        print(f"      Range: [{xs[0]}..{xs[-1]}], Values: [{cs[0]}..{cs[-1]}]")
                sample_data["CITI_EQ_INDICES"] = {
                    tag: _summarize_series(series)
                    for tag, series in body.items()
                }
            else:
                print(f"    [ERROR] {resp.get('message', 'unknown')}")

        # --- EQIVOL: pick SPX + a couple others ---
        eqivol_tags = tag_listings.get("EQIVOL", [])
        eqivol_sample = [t for t in eqivol_tags if "SPX" in t or "SX5E" in t or "NKY" in t][:10]
        if eqivol_sample:
            print(f"\n  Probing EQIVOL ({len(eqivol_sample)} sample tags, last 30 days)")
            time.sleep(SLEEP)
            resp = client.fetch_historical(eqivol_sample, start_30d, end)
            if resp.get("status") == "OK":
                body = resp.get("body", {})
                for tag, series in body.items():
                    xs = series.get("x", []) if isinstance(series, dict) else []
                    cs = series.get("c", []) if isinstance(series, dict) else []
                    print(f"    {tag}: {len(xs)} points")
                    if xs:
                        print(f"      Range: [{xs[0]}..{xs[-1]}], Values: [{cs[0]}..{cs[-1]}]")
                sample_data["EQIVOL"] = {
                    tag: _summarize_series(series)
                    for tag, series in body.items()
                }
            else:
                print(f"    [ERROR] {resp.get('message', 'unknown')}")

        # --- FORECAST: pick a few countries ---
        fcast_tags = tag_listings.get("FORECAST", [])
        fcast_sample = [t for t in fcast_tags if "USA" in t or "GBR" in t or "JPN" in t][:10]
        if fcast_sample:
            print(f"\n  Probing FORECAST ({len(fcast_sample)} sample tags, last 1 year)")
            time.sleep(SLEEP)
            resp = client.fetch_historical(fcast_sample, start_1y, end)
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

        # --- VARSWAP: pick SPX constant + fixed expiry ---
        var_tags = tag_listings.get("VARSWAP", [])
        var_sample = [t for t in var_tags if "SPX" in t or "NDX" in t][:10]
        if var_sample:
            print(f"\n  Probing VARSWAP ({len(var_sample)} sample tags, last 30 days)")
            time.sleep(SLEEP)
            resp = client.fetch_historical(var_sample, start_30d, end)
            if resp.get("status") == "OK":
                body = resp.get("body", {})
                for tag, series in body.items():
                    xs = series.get("x", []) if isinstance(series, dict) else []
                    cs = series.get("c", []) if isinstance(series, dict) else []
                    print(f"    {tag}: {len(xs)} points")
                    if xs:
                        print(f"      Range: [{xs[0]}..{xs[-1]}], Values: [{cs[0]}..{cs[-1]}]")
                sample_data["VARSWAP"] = {
                    tag: _summarize_series(series)
                    for tag, series in body.items()
                }
            else:
                print(f"    [ERROR] {resp.get('message', 'unknown')}")

        # --- VOLSWAP: pick SPX + AAPL + NVDA ---
        vol_tags = tag_listings.get("VOLSWAP", [])
        vol_sample = [t for t in vol_tags if "SPX" in t or "AAPL" in t or "NVDA" in t][:10]
        if vol_sample:
            print(f"\n  Probing VOLSWAP ({len(vol_sample)} sample tags, last 30 days)")
            time.sleep(SLEEP)
            resp = client.fetch_historical(vol_sample, start_30d, end)
            if resp.get("status") == "OK":
                body = resp.get("body", {})
                for tag, series in body.items():
                    xs = series.get("x", []) if isinstance(series, dict) else []
                    cs = series.get("c", []) if isinstance(series, dict) else []
                    print(f"    {tag}: {len(xs)} points")
                    if xs:
                        print(f"      Range: [{xs[0]}..{xs[-1]}], Values: [{cs[0]}..{cs[-1]}]")
                sample_data["VOLSWAP"] = {
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
            print(f"  {subcat:>20}: {count:>5} tags")
        print(f"  {'TOTAL':>20}: {tree['_total_tags']:>5} tags")

        print(f"\nSample data probes:")
        for subcat, data in sample_data.items():
            tags_with_data = sum(1 for v in data.values() if v.get("row_count", 0) > 0)
            total_rows = sum(v.get("row_count", 0) for v in data.values())
            print(f"  {subcat:>20}: {tags_with_data} tags returned data, {total_rows} total rows")

        print(f"\nRate limit remaining: {client.rate_limit_remaining}")

    # Save
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(tree, indent=2, default=str))
    print(f"\nSaved to {OUTPUT}")


if __name__ == "__main__":
    main()
