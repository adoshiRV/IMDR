"""Deep-dive into RATES.VOL tag tree using taglisting (flat, fast).

The swaption vol cube is too deep for recursive tagbrowsing.
Instead, use taglisting to get all tags per currency in one call,
then parse the structure from the flat tag list.

Run:
    python -m scripts.explore.explore_rates_vol

Output: data/cache/rates/rates_vol_tree.json
"""
from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path

from imdr.config.settings import get_settings
from imdr.connectors.citi_velocity import CitiVelocityClient

OUTPUT = Path("data/cache/rates/rates_vol_tree.json")
SLEEP = 1.1


def parse_tag(tag: str) -> dict | None:
    """Parse a RATES.VOL tag into its components.

    Expected formats:
      RATES.VOL.{CCY}.{DATA_TYPE}.{QUOTE_TYPE}.{EXPIRY}.{SWAP_TENOR}
      (7 parts for full swaption vol)
    or shorter for leaf-less intermediate nodes.
    """
    parts = tag.split(".")
    if len(parts) < 3 or parts[0] != "RATES" or parts[1] != "VOL":
        return None

    result = {"tag": tag, "ccy": parts[2]}
    if len(parts) >= 4:
        result["data_type"] = parts[3]  # ATM, REALIZED, VOL_RATIO
    if len(parts) >= 5:
        result["quote_type"] = parts[4]  # BLACK, NORMAL, FWDPREMIUM, PREMIUM
    if len(parts) >= 6:
        result["option_expiry"] = parts[5]  # 1M, 3M, ..., 30Y
    if len(parts) >= 7:
        result["swap_tenor"] = parts[6]  # 3M, 1Y, ..., 30Y
    result["depth"] = len(parts)
    return result


def main() -> None:
    settings = get_settings()
    tree: dict = {}

    with CitiVelocityClient(settings) as client:
        # Step 1: Get all currencies
        print("=" * 60)
        print("RATES.VOL: Discovering currencies")
        print("=" * 60)
        resp = client.fetch_tagbrowsing("RATES.VOL")
        currencies = sorted(resp.get("fields", {}).keys())
        print(f"Currencies ({len(currencies)}): {currencies}")
        tree["currencies"] = currencies

        # Step 2: For each currency, do ONE tagbrowsing at level 2
        # to get data_types (ATM, REALIZED, VOL_RATIO, etc.)
        print(f"\n{'=' * 60}")
        print("Data types per currency (tagbrowsing level 2)")
        print(f"{'=' * 60}")
        ccy_data_types: dict[str, list[str]] = {}
        for ccy in currencies:
            time.sleep(SLEEP)
            resp = client.fetch_tagbrowsing(f"RATES.VOL.{ccy}")
            dtypes = sorted(resp.get("fields", {}).keys())
            ccy_data_types[ccy] = dtypes
            print(f"  {ccy}: {dtypes}")
        tree["data_types_by_ccy"] = ccy_data_types

        # Step 3: For each currency, do ONE tagbrowsing at level 3
        # to get quote_types under ATM (BLACK, NORMAL, etc.)
        print(f"\n{'=' * 60}")
        print("Quote types under ATM per currency (tagbrowsing level 3)")
        print(f"{'=' * 60}")
        ccy_quote_types: dict[str, dict[str, list[str]]] = {}
        for ccy in currencies:
            ccy_quote_types[ccy] = {}
            for dtype in ccy_data_types[ccy]:
                time.sleep(SLEEP)
                resp = client.fetch_tagbrowsing(f"RATES.VOL.{ccy}.{dtype}")
                qtypes = sorted(resp.get("fields", {}).keys())
                leaves = resp.get("leaves", [])
                ccy_quote_types[ccy][dtype] = qtypes
                extra = f" (leaves: {sorted(leaves)[:5]})" if leaves else ""
                print(f"  {ccy}.{dtype}: {qtypes}{extra}")
        tree["quote_types_by_ccy"] = ccy_quote_types

        # Step 4: For ONE representative currency (USD), browse one more
        # level to confirm expiry grid
        print(f"\n{'=' * 60}")
        print("Expiry grid sample: USD.ATM.BLACK")
        print(f"{'=' * 60}")
        time.sleep(SLEEP)
        resp = client.fetch_tagbrowsing("RATES.VOL.USD.ATM.BLACK")
        expiries = sorted(resp.get("fields", {}).keys())
        print(f"  Option expiries ({len(expiries)}): {expiries}")
        tree["sample_expiries_USD_ATM_BLACK"] = expiries

        # And swap tenors under first expiry
        time.sleep(SLEEP)
        first_exp = expiries[0] if expiries else "1Y"
        resp = client.fetch_tagbrowsing(f"RATES.VOL.USD.ATM.BLACK.{first_exp}")
        swap_tenors = sorted(resp.get("fields", {}).keys())
        swap_leaves = sorted(resp.get("leaves", []))
        print(f"  Swap tenors under {first_exp} ({len(swap_tenors)}): {swap_tenors}")
        if swap_leaves:
            print(f"  Leaves: {swap_leaves}")
        tree["sample_swap_tenors_USD_ATM_BLACK"] = swap_tenors

        # Also check REALIZED and VOL_RATIO structure (might be different)
        for dtype in ["REALIZED", "VOL_RATIO"]:
            time.sleep(SLEEP)
            resp = client.fetch_tagbrowsing(f"RATES.VOL.USD.{dtype}")
            children = sorted(resp.get("fields", {}).keys())
            leaves = sorted(resp.get("leaves", []))
            print(f"\n  USD.{dtype} children: {children}")
            if leaves:
                print(f"  USD.{dtype} leaves: {leaves[:10]}")
            tree[f"sample_USD_{dtype}"] = {
                "children": children,
                "leaves": leaves[:10],
            }
            # Go one more level if children exist
            if children:
                time.sleep(SLEEP)
                resp2 = client.fetch_tagbrowsing(
                    f"RATES.VOL.USD.{dtype}.{children[0]}"
                )
                sub_children = sorted(resp2.get("fields", {}).keys())
                sub_leaves = sorted(resp2.get("leaves", []))
                print(f"  USD.{dtype}.{children[0]} children: {sub_children}")
                if sub_leaves:
                    print(f"  USD.{dtype}.{children[0]} leaves: {sub_leaves[:10]}")
                tree[f"sample_USD_{dtype}"][f"_drill_{children[0]}"] = {
                    "children": sub_children,
                    "leaves": sub_leaves[:10],
                }

        # Step 5: Use taglisting to get COMPLETE flat tag list per currency
        # This is the authoritative count
        print(f"\n{'=' * 60}")
        print("TAG LISTINGS (complete flat inventories)")
        print(f"{'=' * 60}")

        tag_listings: dict[str, list[str]] = {}
        for ccy in currencies:
            prefix = f"RATES.VOL.{ccy}"
            print(f"\n  taglisting: {prefix}")
            time.sleep(SLEEP)
            tl = client.fetch_taglisting(prefix)
            if tl.get("status") == "OK":
                tags = sorted(tl.get("tags", []))
                tag_listings[ccy] = tags
                print(f"    {len(tags)} tags total")
                if tags:
                    print(f"    First 3: {tags[:3]}")
                    print(f"    Last  3: {tags[-3:]}")

                    # Parse structure from tags
                    depths = defaultdict(int)
                    data_types_seen = set()
                    quote_types_seen = set()
                    expiries_seen = set()
                    swap_tenors_seen = set()

                    for t in tags:
                        parsed = parse_tag(t)
                        if parsed:
                            depths[parsed["depth"]] += 1
                            if "data_type" in parsed:
                                data_types_seen.add(parsed["data_type"])
                            if "quote_type" in parsed:
                                quote_types_seen.add(parsed["quote_type"])
                            if "option_expiry" in parsed:
                                expiries_seen.add(parsed["option_expiry"])
                            if "swap_tenor" in parsed:
                                swap_tenors_seen.add(parsed["swap_tenor"])

                    print(f"    Depths: {dict(depths)}")
                    print(f"    Data types: {sorted(data_types_seen)}")
                    print(f"    Quote types: {sorted(quote_types_seen)}")
                    print(f"    Option expiries: {sorted(expiries_seen)}")
                    print(f"    Swap tenors: {sorted(swap_tenors_seen)}")
            else:
                print(f"    [ERROR]")
                tag_listings[ccy] = []

        tree["_tag_listings"] = tag_listings
        tree["_tag_counts"] = {
            ccy: len(tags) for ccy, tags in tag_listings.items()
        }
        tree["_total_tags"] = sum(len(t) for t in tag_listings.values())

        # Step 6: Summary
        print(f"\n{'=' * 60}")
        print("SUMMARY")
        print(f"{'=' * 60}")
        print(f"Currencies: {currencies}")
        print(f"\nTag counts by currency:")
        for ccy in currencies:
            count = len(tag_listings.get(ccy, []))
            print(f"  {ccy}: {count:>5} tags")
        print(f"  {'TOTAL':>3}: {tree['_total_tags']:>5} tags")

    # Save
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(tree, indent=2, default=str))
    print(f"\nSaved to {OUTPUT}")


if __name__ == "__main__":
    main()
