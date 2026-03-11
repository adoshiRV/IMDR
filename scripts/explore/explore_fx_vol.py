"""Deep-dive into FX.VOL tag tree to map the full vol surface structure.

Explores: FX.VOL → CCY1 → CCY2 → surface type → tenors/strikes

Run:
    python -m scripts.explore.explore_fx_vol

Output: data/cache/fx/fx_vol_tree.json
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from imdr.config.settings import get_settings
from imdr.connectors.citi_velocity import CitiVelocityClient

OUTPUT = Path("data/cache/fx/fx_vol_tree.json")
SLEEP = 1.1


def main() -> None:
    settings = get_settings()

    with CitiVelocityClient(settings) as client:
        # Level 1: FX.VOL → all base currencies
        print("=== FX.VOL: base currencies ===")
        resp = client.fetch_tagbrowsing("FX.VOL")
        base_ccys = sorted(resp.get("fields", {}).keys())
        print(f"Base currencies ({len(base_ccys)}): {base_ccys}")

        tree: dict = {"base_currencies": base_ccys}

        # Level 2: Pick key pairs to explore deeply
        # USD is the main quote ccy, so explore EUR.USD, GBP.USD, USD.JPY, AUD.USD
        # Also explore a couple of EM: USD.MXN, USD.CNH
        key_pairs = [
            ("EUR", "USD"), ("GBP", "USD"), ("USD", "JPY"), ("AUD", "USD"),
            ("USD", "MXN"), ("USD", "CNH"), ("USD", "KRW"),
        ]

        # First, get all quote ccys for USD (most common base)
        print("\n=== FX.VOL.USD: all quote currencies ===")
        time.sleep(SLEEP)
        resp = client.fetch_tagbrowsing("FX.VOL.USD")
        usd_quotes = sorted(resp.get("fields", {}).keys())
        print(f"USD quote ccys ({len(usd_quotes)}): {usd_quotes}")
        tree["USD_quotes"] = usd_quotes

        # Also get EUR quotes
        print("\n=== FX.VOL.EUR: all quote currencies ===")
        time.sleep(SLEEP)
        resp = client.fetch_tagbrowsing("FX.VOL.EUR")
        eur_quotes = sorted(resp.get("fields", {}).keys())
        print(f"EUR quote ccys ({len(eur_quotes)}): {eur_quotes}")
        tree["EUR_quotes"] = eur_quotes

        # Level 3+: Deep drill into key pairs
        for ccy1, ccy2 in key_pairs:
            prefix = f"FX.VOL.{ccy1}.{ccy2}"
            print(f"\n=== {prefix} ===")
            time.sleep(SLEEP)
            resp = client.fetch_tagbrowsing(prefix)
            if resp.get("status") != "OK":
                print(f"  [ERROR]")
                continue

            surface_types = sorted(resp.get("fields", {}).keys())
            leaves = resp.get("leaves", [])
            print(f"  Surface types ({len(surface_types)}): {surface_types}")
            if leaves:
                print(f"  Leaves: {leaves[:5]}")

            pair_data: dict = {"surface_types": surface_types}

            # Drill into each surface type
            for stype in surface_types:
                stype_prefix = f"{prefix}.{stype}"
                print(f"  --- {stype} ---")
                time.sleep(SLEEP)
                resp2 = client.fetch_tagbrowsing(stype_prefix)
                if resp2.get("status") != "OK":
                    print(f"    [ERROR]")
                    continue

                children = sorted(resp2.get("fields", {}).keys())
                sleaves = resp2.get("leaves", [])
                print(f"    Children ({len(children)}): {children[:30]}")
                if sleaves:
                    print(f"    Leaves ({len(sleaves)}): {sleaves[:10]}")

                stype_data: dict = {
                    "children": children,
                    "child_count": len(children),
                    "leaf_sample": sleaves[:10],
                }

                # One more level for first 3 children (to see tenors/strikes)
                for child in children[:3]:
                    child_prefix = f"{stype_prefix}.{child}"
                    print(f"      Drilling: {child_prefix}")
                    time.sleep(SLEEP)
                    resp3 = client.fetch_tagbrowsing(child_prefix)
                    if resp3.get("status") == "OK":
                        gchildren = sorted(resp3.get("fields", {}).keys())
                        gleaves = resp3.get("leaves", [])
                        print(f"        Children: {gchildren[:20]}")
                        if gleaves:
                            print(f"        Leaves: {gleaves[:10]}")
                        stype_data[f"_sample_{child}"] = {
                            "children": gchildren[:20],
                            "leaves_sample": gleaves[:10],
                        }
                    else:
                        print(f"        [ERROR]")

                pair_data[stype] = stype_data

            tree[f"{ccy1}_{ccy2}"] = pair_data

        # Also use taglisting to get actual full tags for EUR.USD ATM
        print("\n=== TAGLISTING: FX.VOL.EUR.USD (sample) ===")
        time.sleep(SLEEP)
        tl_resp = client.fetch_taglisting("FX.VOL.EUR.USD")
        if tl_resp.get("status") == "OK":
            all_tags = sorted(tl_resp.get("tags", []))
            print(f"Total tags for EUR/USD vol: {len(all_tags)}")
            print(f"Sample: {all_tags[:20]}")
            tree["EUR_USD_all_tags"] = all_tags
            tree["EUR_USD_tag_count"] = len(all_tags)

        # Save
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(json.dumps(tree, indent=2, default=str))
        print(f"\nSaved to {OUTPUT}")


if __name__ == "__main__":
    main()
