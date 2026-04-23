"""Probe FX.SPOT tag formats — all attempted patterns errored in the forward probe.

Run:
    python -m scripts.explore.probe_fx_spot
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from imdr.config.settings import get_settings
from imdr.connectors.citi_velocity import CitiVelocityClient

OUTPUT = Path("data/cache/fx/spot_probe.json")
SLEEP = 1.1


def main() -> None:
    settings = get_settings()
    result: dict = {}

    with CitiVelocityClient(settings) as client:
        # ── 1. What children does FX.SPOT.EUR.USD have? ───────────
        print("=" * 70)
        print("STEP 1: FX.SPOT.EUR.USD tree browse")
        print("=" * 70)
        for prefix in [
            "FX.SPOT",
            "FX.SPOT.EUR",
            "FX.SPOT.EUR.USD",
            "FX.SPOT.USD",
            "FX.SPOT.USD.JPY",
        ]:
            time.sleep(SLEEP)
            try:
                resp = client.fetch_tagbrowsing(prefix)
                fields = list(resp.get("fields", {}).keys())
                leaves = resp.get("leaves", []) or resp.get("header", [])
                print(f"  {prefix}: fields={fields}  leaves_sample={str(leaves)[:200]}")
                result[f"browse_{prefix}"] = {"fields": fields, "raw": resp}
            except Exception as e:
                print(f"  ERROR {prefix}: {e}")

        # ── 2. Taglisting under FX.SPOT.EUR.USD. ───────────────────
        print()
        print("=" * 70)
        print("STEP 2: Taglisting")
        print("=" * 70)
        for prefix in ["FX.SPOT.EUR.USD.", "FX.SPOT.EUR.USD", "FX.SPOT.USD.JPY."]:
            time.sleep(SLEEP)
            try:
                resp = client.fetch_taglisting(prefix)
                tags = resp.get("tags", [])
                print(f"  {prefix}: {len(tags)} tags")
                for t in tags[:20]:
                    print(f"    {t}")
                result[f"taglist_{prefix}"] = tags
            except Exception as e:
                print(f"  ERROR {prefix}: {e}")

        # ── 3. Try variants of SPOT historical fetch ──────────────
        print()
        print("=" * 70)
        print("STEP 3: Historical fetch — SPOT tag variants")
        print("=" * 70)
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=10)

        variants = [
            "FX.SPOT.EUR.USD.CITI",
            "FX.SPOT.EUR.USD",
            "FX.SPOT.EUR.USD.SPOT",
            "FX.SPOT.EUR.USD.REUTERS",
            "FX.SPOT.EUR.USD.CITI_REUTERS",
            "FX.SPOT.EUR.USD.LEVEL.CITI",
            "FX.SPOT.EUR.USD.MID.CITI",
            "FX.SPOT.EUR.USD.CLOSE.CITI",
            "FX.SPOT.EUR.USD.BID.CITI",
            "FX.SPOT.EUR.USD.ASK.CITI",
            "FX.SPOT.EUR.USD.CITI.MID",
            # Try with both orderings for USD pairs
            "FX.SPOT.USD.JPY.CITI",
            "FX.SPOT.USD.HKD.CITI",
            "FX.SPOT.USD.KRW.CITI",
        ]

        time.sleep(SLEEP)
        try:
            resp = client.fetch_historical(variants, start, end)
            body = resp.get("body", {})
            samples = {}
            for tag in variants:
                td = body.get(tag, {}) or {}
                values = td.get("c", [])
                dates = td.get("x", [])
                err = td.get("errorMessage") or td.get("error")
                status_code = td.get("status") or td.get("statusCode")
                samples[tag] = {
                    "n_points": len(values),
                    "latest": values[-1] if values else None,
                    "type": td.get("type"),
                    "error": err,
                    "status": status_code,
                }
                marker = "OK" if values else "--"
                extra = f" err={err}" if err else ""
                print(f"  {marker} {tag:45s} type={td.get('type','?'):8s} pts={len(values):3d}{extra}")
            result["variants"] = samples
        except Exception as e:
            print(f"  ERROR: {e}")
            result["variants_error"] = str(e)

        print()
        print(f"Rate limit remaining: {client.rate_limit_remaining}")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2, default=str))
    print(f"Saved to {OUTPUT}")


if __name__ == "__main__":
    main()
