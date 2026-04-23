"""Deep-dive into FX.FORWARD tag tree — replace BidFX outrights with Citi.

Goals:
  1. Enumerate FULL base-ccy list for FWD_OUTRIGHT, FWD_POINT, FWD_POINT_PIP
     (previous tree crawl truncated at 20 children).
  2. For a representative set (G10, EM deliverable, EM NDF, HKD, metals),
     drill down to quote ccys and tenors.
  3. Probe data availability for NDF ccys (KRW, IDR, PHP, TWD, THB, INR):
     - Can we get FWD_POINT.{CCY}.USD.{TENOR}? (Doc claim: empty)
     - What about vs JPY? vs EUR? Cross-pair fallback.
  4. Confirm SPOT + FORWARD historical data returns for a sample batch.

Run:
    python -m scripts.explore.explore_fx_forward

Output: data/cache/fx/fwd_exploration.json
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from imdr.config.settings import get_settings
from imdr.connectors.citi_velocity import CitiVelocityClient

OUTPUT = Path("data/cache/fx/fwd_exploration.json")
SLEEP = 1.1

FWD_TYPES = ["FWD_OUTRIGHT", "FWD_POINT", "FWD_POINT_PIP"]

# Representative currencies to drill down on — covers G10, EM deliverable,
# EM NDF, HKD (pegged), and metals
DRILLDOWN_CCYS = [
    # G10
    "EUR", "GBP", "JPY", "CHF", "AUD", "NZD", "CAD", "NOK", "SEK", "CNH", "USD",
    # EM deliverable
    "SGD", "CZK", "PLN", "HUF", "ILS", "MXN", "ZAR", "TRY", "BRL", "CLP",
    # EM NDF
    "KRW", "TWD", "THB", "IDR", "PHP", "INR",
    # Pegged / special
    "HKD", "CNY",
    # Metals
    "XAU", "XAG", "XPT", "XPD",
]

NDF_CCYS = ["KRW", "TWD", "THB", "IDR", "PHP", "INR"]

# Quote legs to try for NDF fallback
NDF_QUOTE_PROBE = ["USD", "JPY", "EUR"]

# Standard FX tenor grid (matches VOL pipeline)
STANDARD_TENORS = ["ON", "1W", "2W", "1M", "2M", "3M", "6M", "9M", "1Y", "2Y", "3Y", "5Y", "7Y", "10Y"]


def browse(client: CitiVelocityClient, prefix: str) -> list[str]:
    """Return sorted child keys at a given prefix."""
    time.sleep(SLEEP)
    try:
        resp = client.fetch_tagbrowsing(prefix)
        return sorted(resp.get("fields", {}).keys())
    except Exception as e:
        print(f"  ERROR browse {prefix}: {e}")
        return []


def taglist(client: CitiVelocityClient, prefix: str) -> list[str]:
    """Return full leaf tag list under a prefix."""
    time.sleep(SLEEP)
    try:
        resp = client.fetch_taglisting(prefix)
        return resp.get("tags", [])
    except Exception as e:
        print(f"  ERROR taglist {prefix}: {e}")
        return []


def main() -> None:
    settings = get_settings()
    result: dict = {"generated_at": datetime.now(timezone.utc).isoformat()}

    with CitiVelocityClient(settings) as client:
        # ── 1. Full base-ccy list per FWD type ─────────────────────
        print("=" * 70)
        print("STEP 1: Full base-ccy list per FWD type")
        print("=" * 70)
        result["base_ccys"] = {}
        for fwd_type in FWD_TYPES:
            prefix = f"FX.FORWARD.{fwd_type}"
            ccys = browse(client, prefix)
            result["base_ccys"][fwd_type] = ccys
            print(f"  {prefix}: {len(ccys)} base ccys")
            print(f"    {ccys}")

        # ── 2. Drill into each representative ccy → quote ccys ────
        print()
        print("=" * 70)
        print("STEP 2: Quote ccys per base (FWD_OUTRIGHT)")
        print("=" * 70)
        result["quotes_per_base"] = {}
        for base in DRILLDOWN_CCYS:
            prefix = f"FX.FORWARD.FWD_OUTRIGHT.{base}"
            quotes = browse(client, prefix)
            if quotes:
                result["quotes_per_base"][base] = quotes
                print(f"  {base}: {len(quotes)} quotes -> {quotes[:15]}{'...' if len(quotes) > 15 else ''}")
            else:
                print(f"  {base}: (none)")

        # ── 3. Tenor grid — probe one representative pair ──────────
        print()
        print("=" * 70)
        print("STEP 3: Tenor grid (FWD_OUTRIGHT.EUR.USD)")
        print("=" * 70)
        tenors_eurusd = browse(client, "FX.FORWARD.FWD_OUTRIGHT.EUR.USD")
        result["tenors_eurusd"] = tenors_eurusd
        print(f"  EUR.USD tenors ({len(tenors_eurusd)}): {tenors_eurusd}")

        # Also check JPY pair
        tenors_usdjpy = browse(client, "FX.FORWARD.FWD_OUTRIGHT.USD.JPY")
        result["tenors_usdjpy"] = tenors_usdjpy
        print(f"  USD.JPY tenors ({len(tenors_usdjpy)}): {tenors_usdjpy}")

        # ── 4. NDF ccys: check what quote legs exist ───────────────
        print()
        print("=" * 70)
        print("STEP 4: NDF ccy quote legs (FWD_OUTRIGHT and FWD_POINT)")
        print("=" * 70)
        result["ndf_legs"] = {}
        for ccy in NDF_CCYS:
            ccy_data = {}
            for fwd_type in ["FWD_OUTRIGHT", "FWD_POINT"]:
                prefix = f"FX.FORWARD.{fwd_type}.{ccy}"
                quotes = browse(client, prefix)
                ccy_data[fwd_type] = quotes
                print(f"  {ccy} [{fwd_type}]: {quotes}")
            result["ndf_legs"][ccy] = ccy_data

        # ── 5. Historical fetch test — confirm data returns ────────
        print()
        print("=" * 70)
        print("STEP 5: Historical fetch test (DAILY, last 10 days)")
        print("=" * 70)
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=10)

        # Build test batch — mix of SPOT, FWD G10, FWD HKD, FWD NDF vs USD, FWD NDF vs JPY
        test_tags = [
            # Spot sanity
            "FX.SPOT.EUR.USD.SPOT.CITI",
            "FX.SPOT.USD.JPY.SPOT.CITI",
            "FX.SPOT.USD.HKD.SPOT.CITI",
            "FX.SPOT.USD.KRW.SPOT.CITI",
            # G10 outrights
            "FX.FORWARD.FWD_OUTRIGHT.EUR.USD.1M.CITI",
            "FX.FORWARD.FWD_OUTRIGHT.EUR.USD.3M.CITI",
            "FX.FORWARD.FWD_OUTRIGHT.EUR.USD.1Y.CITI",
            "FX.FORWARD.FWD_OUTRIGHT.USD.JPY.1M.CITI",
            "FX.FORWARD.FWD_OUTRIGHT.USD.JPY.1Y.CITI",
            # HKD outrights
            "FX.FORWARD.FWD_OUTRIGHT.USD.HKD.1M.CITI",
            "FX.FORWARD.FWD_OUTRIGHT.USD.HKD.1Y.CITI",
            # NDF-USD (expected: empty per doc)
            "FX.FORWARD.FWD_OUTRIGHT.USD.KRW.1M.CITI",
            "FX.FORWARD.FWD_POINT.USD.KRW.1M.CITI",
            "FX.FORWARD.FWD_OUTRIGHT.KRW.USD.1M.CITI",
            "FX.FORWARD.FWD_POINT.KRW.USD.1M.CITI",
            # NDF-JPY fallback
            "FX.FORWARD.FWD_POINT.KRW.JPY.1M.CITI",
            "FX.FORWARD.FWD_OUTRIGHT.KRW.JPY.1M.CITI",
            "FX.FORWARD.FWD_POINT.INR.JPY.1M.CITI",
            # Forward point for comparison
            "FX.FORWARD.FWD_POINT.EUR.USD.1M.CITI",
            "FX.FORWARD.FWD_POINT_PIP.EUR.USD.1M.CITI",
        ]

        print(f"  Fetching {len(test_tags)} tags, {start.date()} -> {end.date()}...")
        time.sleep(SLEEP)
        try:
            resp = client.fetch_historical(test_tags, start, end)
            body = resp.get("body", {})
            samples = {}
            for tag in test_tags:
                td = body.get(tag, {}) or {}
                values = td.get("c", [])
                dates = td.get("x", [])
                samples[tag] = {
                    "n_points": len(values),
                    "latest_date": dates[-1] if dates else None,
                    "latest_value": values[-1] if values else None,
                    "first_date": dates[0] if dates else None,
                }
                status = "OK " if values else "-- "
                latest = f"last={values[-1]}" if values else "NO DATA"
                print(f"  {status}{tag:60s} {td.get('type','?'):8s} pts={len(values):3d}  {latest}")
            result["historical_samples"] = samples
        except Exception as e:
            print(f"  ERROR: {e}")
            result["historical_samples_error"] = str(e)

        # ── 6. Taglisting — count tags under FWD_OUTRIGHT.EUR.USD ──
        print()
        print("=" * 70)
        print("STEP 6: Taglisting count for EUR.USD forward curve")
        print("=" * 70)
        tags = taglist(client, "FX.FORWARD.FWD_OUTRIGHT.EUR.USD.")
        result["tags_eurusd_outright"] = {"count": len(tags), "sample": tags[:30]}
        print(f"  Count: {len(tags)}")
        for t in tags[:15]:
            print(f"    {t}")

        # Rate limit snapshot
        print()
        print(f"Rate limit remaining: {client.rate_limit_remaining}")
        result["rate_limit_remaining"] = client.rate_limit_remaining
        result["rate_limit_info"] = client.rate_limit_info

    # ── Save ──
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2))
    print()
    print(f"Saved to {OUTPUT}")


if __name__ == "__main__":
    main()
