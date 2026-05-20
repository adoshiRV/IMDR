"""First-touch exploration of the Polymarket Gamma API.

Goal: see what's available, what fields exist, how probabilities are expressed,
and how often the data ticks. No DB writes. Results cached as JSON for later
design work.

Run:
    python -m scripts.explore.explore_polymarket_gamma

Outputs (under data/cache/polymarket/):
    - markets_sample.json     first page of /markets (active only)
    - events_sample.json      first page of /events  (active only)
    - macro_hits.json         macro-keyword filtered subset of markets
    - frequency_probe.json    6 polls x top macro contracts, ~60s window
"""
from __future__ import annotations

import json
import statistics
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from imdr.connectors.http import HTTPClient

BASE_URL = "https://gamma-api.polymarket.com"
CACHE_DIR = Path("data/cache/polymarket")
SLEEP_LIST = 1.0
PROBE_ROUNDS = 6
PROBE_SLEEP = 10
PROBE_TARGETS = 5
MARKET_LIMIT = 500
EVENT_LIMIT = 200

MACRO_KEYWORDS = [
    "fed", "rate cut", "rate hike", "fomc", "cpi", "inflation",
    "oil", "wti", "brent", "opec", "hormuz",
    "iran", "ukraine", "russia", "china", "tariff",
    "recession", "gdp", "unemployment", "jobs report",
]


def _keywords_hit(market: dict) -> list[str]:
    haystack = " ".join([
        str(market.get("question", "")),
        str(market.get("description", "")),
        str(market.get("slug", "")),
        json.dumps(market.get("tags", []), default=str),
    ]).lower()
    return [kw for kw in MACRO_KEYWORDS if kw in haystack]


def _get_volume(market: dict) -> float:
    for key in ("volumeNum", "volume", "volume24hr", "volumeUsd"):
        val = market.get(key)
        if val is None:
            continue
        try:
            return float(val)
        except (ValueError, TypeError):
            continue
    return 0.0


def _summarize_markets(markets: list[dict]) -> None:
    print(f"\n  Total markets returned: {len(markets)}")
    if not markets:
        return
    first = markets[0]
    print(f"  Example keys on first market object ({len(first)} fields):")
    for k in sorted(first.keys()):
        print(f"    - {k}")
    volumes = sorted([_get_volume(m) for m in markets], reverse=True)
    if volumes:
        print(f"  Volume distribution:")
        print(f"    max    = {volumes[0]:>15,.0f}")
        print(f"    median = {statistics.median(volumes):>15,.0f}")
        print(f"    min    = {volumes[-1]:>15,.0f}")
    end_dates = [m.get("endDate") for m in markets if m.get("endDate")]
    if end_dates:
        print(f"  End-date range: {min(end_dates)}  ..  {max(end_dates)}")
    closed_dist = Counter(m.get("closed") for m in markets)
    active_dist = Counter(m.get("active") for m in markets)
    print(f"  'closed' field: {dict(closed_dist)}")
    print(f"  'active' field: {dict(active_dist)}")
    op_samples = [m.get("outcomePrices") for m in markets[:5]]
    print(f"  First 5 outcomePrices samples: {op_samples}")


def _probe_round(client: HTTPClient, targets: list[dict], round_idx: int) -> list[dict]:
    rows = []
    for t in targets:
        mid = t.get("id") or t.get("conditionId") or t.get("slug")
        if not mid:
            continue
        try:
            detail = client.get_json(f"/markets/{mid}")
        except Exception as e:
            print(f"    [poll {round_idx}] {mid}: ERROR {e}")
            continue
        if isinstance(detail, list):
            detail = detail[0] if detail else {}
        rows.append({
            "round": round_idx,
            "poll_ts": datetime.now(timezone.utc).isoformat(),
            "id": str(mid),
            "question": detail.get("question"),
            "outcomePrices": detail.get("outcomePrices"),
            "lastTradePrice": detail.get("lastTradePrice"),
            "bestBid": detail.get("bestBid"),
            "bestAsk": detail.get("bestAsk"),
            "updatedAt": detail.get("updatedAt"),
            "volume24hr": detail.get("volume24hr") or detail.get("volumeNum"),
        })
    return rows


def main() -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with HTTPClient(base_url=BASE_URL, timeout=30) as client:
        # ============================================================
        # PART 1: /markets
        # ============================================================
        print("=" * 70)
        print("PART 1: GET /markets  (first page, active only)")
        print("=" * 70)
        markets = client.get_json("/markets", params={"limit": MARKET_LIMIT, "closed": "false"})
        if isinstance(markets, dict) and "data" in markets:
            markets = markets["data"]
        if not isinstance(markets, list):
            markets = []
        (CACHE_DIR / "markets_sample.json").write_text(
            json.dumps(markets, indent=2, default=str)
        )
        _summarize_markets(markets)

        time.sleep(SLEEP_LIST)

        # ============================================================
        # PART 2: /events
        # ============================================================
        print("\n" + "=" * 70)
        print("PART 2: GET /events  (first page, active only)")
        print("=" * 70)
        events = client.get_json("/events", params={"limit": EVENT_LIMIT, "closed": "false"})
        if isinstance(events, dict) and "data" in events:
            events = events["data"]
        if not isinstance(events, list):
            events = []
        (CACHE_DIR / "events_sample.json").write_text(
            json.dumps(events, indent=2, default=str)
        )
        print(f"\n  Total events returned: {len(events)}")
        if events:
            first = events[0]
            print(f"  Example keys on first event object ({len(first)} fields):")
            for k in sorted(first.keys()):
                print(f"    - {k}")
            markets_per_event = [len(e.get("markets", [])) for e in events if isinstance(e.get("markets"), list)]
            if markets_per_event:
                print(f"  Markets-per-event: min={min(markets_per_event)}  median={statistics.median(markets_per_event)}  max={max(markets_per_event)}")

        # ============================================================
        # PART 3: macro-keyword filter
        # ============================================================
        print("\n" + "=" * 70)
        print("PART 3: Macro-keyword filter")
        print("=" * 70)
        macro_hits: list[dict] = []
        for m in markets:
            hits = _keywords_hit(m)
            if hits:
                macro_hits.append({
                    "id": m.get("id"),
                    "conditionId": m.get("conditionId"),
                    "slug": m.get("slug"),
                    "question": m.get("question"),
                    "endDate": m.get("endDate"),
                    "volume": _get_volume(m),
                    "outcomePrices": m.get("outcomePrices"),
                    "keywords_matched": hits,
                })
        macro_hits.sort(key=lambda x: x["volume"], reverse=True)
        (CACHE_DIR / "macro_hits.json").write_text(
            json.dumps(macro_hits, indent=2, default=str)
        )
        print(f"\n  Found {len(macro_hits)} macro-relevant contracts (out of {len(markets)})")
        print(f"  Top 10 by volume:")
        for h in macro_hits[:10]:
            print(f"    vol={h['volume']:>12,.0f}  kw={h['keywords_matched']}")
            print(f"       Q: {h['question']}")

        # ============================================================
        # PART 4: frequency probe
        # ============================================================
        print("\n" + "=" * 70)
        print(f"PART 4: Frequency probe — top {PROBE_TARGETS} macro contracts x {PROBE_ROUNDS} polls, {PROBE_SLEEP}s apart")
        print("=" * 70)
        probe_targets = macro_hits[:PROBE_TARGETS]
        snapshots: list[dict] = []
        if not probe_targets:
            print("  No macro hits to probe — skipping.")
        else:
            print(f"\n  Probe targets:")
            for t in probe_targets:
                print(f"    - id={t['id']}  vol={t['volume']:,.0f}")
                print(f"         Q: {t['question']}")
            for i in range(PROBE_ROUNDS):
                print(f"\n  Poll {i+1}/{PROBE_ROUNDS}")
                rows = _probe_round(client, probe_targets, i)
                for r in rows:
                    print(f"    id={r['id']}  prices={r['outcomePrices']}  last={r['lastTradePrice']}  updatedAt={r['updatedAt']}")
                snapshots.extend(rows)
                if i < PROBE_ROUNDS - 1:
                    time.sleep(PROBE_SLEEP)
        (CACHE_DIR / "frequency_probe.json").write_text(
            json.dumps(snapshots, indent=2, default=str)
        )

        # ============================================================
        # PART 5: probe summary
        # ============================================================
        print("\n" + "=" * 70)
        print("PART 5: Frequency probe summary (distinct values across polls)")
        print("=" * 70)
        if snapshots:
            by_id: dict[str, list[dict]] = {}
            for s in snapshots:
                by_id.setdefault(s["id"], []).append(s)
            for mid, series in by_id.items():
                distinct_prices = len({json.dumps(s["outcomePrices"], default=str) for s in series})
                distinct_updated = len({str(s["updatedAt"]) for s in series})
                distinct_last = len({str(s["lastTradePrice"]) for s in series})
                print(f"  id={mid}: distinct_outcomePrices={distinct_prices}  distinct_updatedAt={distinct_updated}  distinct_lastTradePrice={distinct_last}")
        else:
            print("  (no snapshots)")

    print(f"\nAll outputs cached in: {CACHE_DIR}")


if __name__ == "__main__":
    main()
