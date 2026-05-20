"""Polymarket event snapshot — scheduled 2x/day capture of macro events.

Each run captures a structured panel of every macro-relevant Polymarket event:
full probability distribution across the event's markets, best bid/ask, 24h
volume, last trade info, plus derived metrics (modal outcome, runner-up,
implied probability sum, HHI concentration).

Pure HTTP — no WebSocket, no state machine. One JSONL file per snapshot under
`data/cache/polymarket/snapshots/{YYYY-MM-DD}/snapshot_{HHMM}Z.jsonl` plus a
per-date `manifest.json` index.

Run:
    python -m scripts.explore.polymarket_event_snapshot
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from imdr.connectors.http import HTTPClient

from scripts.explore.polymarket_macro_stream import (
    EXCLUDE_RE,
    GAMMA_BASE,
    MIN_VOLUME,
    _parse_json_field,
    _to_float,
    _volume,
    fetch_events_for_tag,
    fetch_macro_tags,
)

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

CACHE_ROOT = Path("data/cache/polymarket/snapshots")
ILLIQUID_SPREAD = 0.20


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _snapshot_label(ts: datetime) -> str:
    """Coarse AM/PM bucket aligned with the 12:00Z / 20:00Z default schedule."""
    return "AM" if ts.hour < 16 else "PM"


def _extract_market(market: dict) -> dict | None:
    prices = _parse_json_field(market.get("outcomePrices"))
    tokens = _parse_json_field(market.get("clobTokenIds"))
    if not tokens or len(tokens) < 2:
        return None
    try:
        yes = float(prices[0]) if prices else None
        no = float(prices[1]) if prices and len(prices) > 1 else None
    except (TypeError, ValueError):
        yes, no = None, None
    best_bid = _to_float(market.get("bestBid"))
    best_ask = _to_float(market.get("bestAsk"))
    spread = best_ask - best_bid if (best_bid is not None and best_ask is not None) else None
    return {
        "condition_id": market.get("conditionId"),
        "question": market.get("question"),
        "outcomes": _parse_json_field(market.get("outcomes")),
        "yes_token": str(tokens[0]),
        "no_token": str(tokens[1]),
        "yes": yes,
        "no": no,
        "best_bid": best_bid,
        "best_ask": best_ask,
        "spread": spread,
        "last_trade_price": _to_float(market.get("lastTradePrice")),
        "volume": _volume(market),
        "volume_24h": _to_float(market.get("volume24hr")),
        "liquidity": _to_float(market.get("liquidityNum") or market.get("liquidity")),
        "updated_at": market.get("updatedAt"),
        "end_date": market.get("endDate"),
        "closed": market.get("closed"),
    }


def _event_derived(markets: list[dict]) -> dict:
    """Modal outcome, runner-up, implied probability sum, HHI, illiquid flag."""
    priced = [(m["question"], m["yes"], m) for m in markets if m.get("yes") is not None]
    priced.sort(key=lambda t: t[1], reverse=True)
    modal = priced[0] if priced else None
    runner_up = priced[1] if len(priced) > 1 else None
    yes_sum = sum(p[1] for p in priced) if priced else None
    hhi = sum(p[1] ** 2 for p in priced) if priced else None
    modal_spread = modal[2].get("spread") if modal else None
    return {
        "modal_question": modal[0] if modal else None,
        "modal_yes": modal[1] if modal else None,
        "runner_up_question": runner_up[0] if runner_up else None,
        "runner_up_yes": runner_up[1] if runner_up else None,
        "implied_prob_sum": yes_sum,
        "hhi": hhi,
        "illiquid_flag": modal_spread is not None and modal_spread > ILLIQUID_SPREAD,
    }


def build_event_snapshot(client: HTTPClient) -> list[dict]:
    """Walk macro tags, assemble events keyed by event_id (first-matching-tag wins).

    Same discovery as Step 1 but keeps the event grouping instead of flattening.
    """
    macro_tags = fetch_macro_tags(client)
    print(f"  Matched {len(macro_tags)} macro tags.")

    events_by_id: dict[int, dict] = {}
    for tag in macro_tags:
        slug = tag["slug"]
        label = tag["label"] or slug
        events = fetch_events_for_tag(client, slug)
        new_for_tag = 0
        for event in events:
            eid = event.get("id")
            if eid is None or eid in events_by_id:
                continue
            raw_markets = event.get("markets") or []
            if not isinstance(raw_markets, list):
                continue
            extracted: list[dict] = []
            for m in raw_markets:
                if m.get("closed"):
                    continue
                q = str(m.get("question") or "")
                if EXCLUDE_RE.search(q):
                    continue
                if _volume(m) < MIN_VOLUME:
                    continue
                row = _extract_market(m)
                if row is not None:
                    extracted.append(row)
            if not extracted:
                continue
            extracted.sort(key=lambda r: str(r.get("condition_id") or ""))
            events_by_id[eid] = {
                "event_id": eid,
                "slug": event.get("slug"),
                "title": event.get("title"),
                "theme": label,
                "end_date": event.get("endDate"),
                "total_volume": sum(r["volume"] for r in extracted),
                "total_liquidity": sum((r.get("liquidity") or 0.0) for r in extracted),
                "event_volume_24h": sum((r.get("volume_24h") or 0.0) for r in extracted),
                "market_count": len(extracted),
                "markets": extracted,
                "derived": _event_derived(extracted),
            }
            new_for_tag += 1
        print(f"    [{slug:35s}]  events_fetched={len(events):>3}  new={new_for_tag}")

    return sorted(events_by_id.values(), key=lambda e: e["event_id"])


def write_snapshot(rows: list[dict], snapshot_ts: datetime) -> Path:
    date_str = snapshot_ts.strftime("%Y-%m-%d")
    hhmm = snapshot_ts.strftime("%H%M")
    out_dir = CACHE_ROOT / date_str
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"snapshot_{hhmm}Z.jsonl"

    label = _snapshot_label(snapshot_ts)
    with out_file.open("w", encoding="utf-8") as f:
        for r in rows:
            rec = {
                "snapshot_ts": snapshot_ts.isoformat(),
                "snapshot_label": label,
                **r,
            }
            f.write(json.dumps(rec, default=str) + "\n")

    manifest_file = out_dir / "manifest.json"
    manifest: dict[str, Any]
    if manifest_file.exists():
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    else:
        manifest = {"date": date_str, "snapshots": []}
    # Upsert: replace existing entry with same hhmm, else append
    manifest["snapshots"] = [s for s in manifest["snapshots"] if s.get("hhmm") != hhmm]
    manifest["snapshots"].append({
        "label": label,
        "hhmm": hhmm,
        "snapshot_ts": snapshot_ts.isoformat(),
        "event_count": len(rows),
        "file": out_file.name,
    })
    manifest["snapshots"].sort(key=lambda s: s["hhmm"])
    manifest_file.write_text(
        json.dumps(manifest, indent=2, default=str), encoding="utf-8"
    )
    return out_file


def print_summary(rows: list[dict], out_file: Path) -> None:
    themes = Counter(e["theme"] for e in rows)
    total_volume = sum(e["total_volume"] for e in rows)
    print(f"\n  Snapshot:   {out_file}")
    print(f"  Events:     {len(rows)}")
    print(f"  Themes:     {len(themes)}")
    print(f"  Volume Σ:   ${total_volume:,.0f}")

    print(f"\n  Themes (by event count):")
    for theme, count in themes.most_common():
        theme_vol = sum(e["total_volume"] for e in rows if e["theme"] == theme)
        print(f"    {theme[:30]:30s}  events={count:>3}  vol=${theme_vol:>14,.0f}")

    top_events = sorted(rows, key=lambda e: e["total_volume"], reverse=True)[:8]
    print(f"\n  Top events by volume:")
    for e in top_events:
        d = e["derived"]
        modal_yes = d.get("modal_yes")
        modal_str = f"{modal_yes:.3f}" if modal_yes is not None else "  -  "
        illiq = " [ILLIQ]" if d.get("illiquid_flag") else ""
        title = (e["title"] or "")[:55]
        modal_q = (d.get("modal_question") or "")[:40]
        print(f"    vol=${e['total_volume']:>12,.0f}  n={e['market_count']:>2}  "
              f"modal={modal_str}{illiq}  [{title}]")
        print(f"       modal_q = {modal_q}")

    # Sanity check: implied_prob_sum distribution
    sums = [e["derived"].get("implied_prob_sum") for e in rows
            if e["market_count"] > 1 and e["derived"].get("implied_prob_sum") is not None]
    if sums:
        sums_sorted = sorted(sums)
        mid = sums_sorted[len(sums_sorted) // 2]
        print(f"\n  implied_prob_sum (multi-market events, n={len(sums)}): "
              f"min={min(sums):.3f} median={mid:.3f} max={max(sums):.3f}")


def main() -> None:
    ts = _now_utc()
    print("=" * 70)
    print(f"Polymarket event snapshot  —  {ts.isoformat(timespec='seconds')}  ({_snapshot_label(ts)})")
    print("=" * 70)
    with HTTPClient(base_url=GAMMA_BASE, timeout=30) as client:
        rows = build_event_snapshot(client)
    if not rows:
        print("  No events matched — nothing to write.")
        return
    out_file = write_snapshot(rows, ts)
    print_summary(rows, out_file)


if __name__ == "__main__":
    main()
