"""Macro-filtered Polymarket watchlist + live WebSocket stream.

Phase 1 (HTTP):
    - GET gamma /tags, filter to macro-relevant slugs (Fed, rates, oil,
      geopolitics, elections, central banks, etc.)
    - GET /events?tag_slug=<slug> for each match; flatten to binary markets
    - Apply a hard exclude list (sports/entertainment noise) and a minimum
      24h volume floor
    - Persist watchlist to data/cache/polymarket/watchlist.json

Phase 2 (WebSocket):
    - Connect to wss://ws-subscriptions-clob.polymarket.com/ws/market
    - Subscribe to the YES token IDs from the watchlist (NO price = 1 - YES)
    - Print a clean one-liner per trade / price-change event and append the
      raw payload to data/cache/polymarket/stream.jsonl

Run:
    python -m scripts.explore.polymarket_macro_stream

Stop with Ctrl+C — watchlist and stream log remain on disk.
"""
from __future__ import annotations

import json
import re
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from websockets.sync.client import connect as ws_connect

from imdr.connectors.http import HTTPClient

# Windows consoles default to cp1252; Polymarket questions contain ≥, ≤, ’, $, €
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

GAMMA_BASE = "https://gamma-api.polymarket.com"
WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
CACHE_DIR = Path("data/cache/polymarket")

MIN_VOLUME = 1_000.0
PING_INTERVAL_SEC = 10
RECV_TIMEOUT_SEC = 5

MACRO_TAG_PATTERNS = [
    # Macro / activity
    r"macro", r"econom", r"\bgdp\b", r"recession", r"slowdown", r"growth",
    # Labor
    r"jobs?\b", r"unemploy", r"payroll", r"nonfarm", r"\bnfp\b", r"jolts?\b",
    r"jobless", r"\bwage", r"hiring", r"layoff",
    # Inflation / prices
    r"inflation", r"\bcpi\b", r"\bpce\b", r"\bppi\b", r"core.?cpi", r"core.?pce",
    r"deflation", r"price.?index",
    # Activity indicators
    r"\bism\b", r"\bpmi\b", r"retail.?sales?", r"housing", r"home.?sales?",
    r"mortgage", r"building.?permits?", r"consumer.?(?:confidence|sentiment|spending)",
    r"durable.?goods", r"factory.?orders?", r"industrial.?production",
    r"capacity.?utilization", r"trade.?balance", r"current.?account",
    # Rates / Fed / central banks
    r"\bfed\b", r"fomc", r"\brate", r"interest", r"powell", r"warsh", r"bessent",
    r"waller", r"bowman", r"kashkari", r"goolsbee", r"williams",
    r"central.bank", r"\becb\b", r"\bboe\b", r"\bboj\b", r"pboc", r"\brba\b", r"rbnz",
    r"bank.?of.?(?:canada|england|japan|korea|mexico|india)",
    # Bonds / FX
    r"yield.?curve", r"treasury", r"treasuries", r"\bdxy\b", r"dollar.?index",
    r"bond.?yield", r"\b(?:2|5|10|30).?year\b",
    # Energy / commodities (event-resolution only — price binaries gated by CURATION_EXCLUDE)
    r"\boil\b", r"crude", r"energy", r"\bgas\b(?!\s*tax)", r"\bwti\b", r"brent", r"opec",
    r"natural.?gas", r"refinery", r"pipeline", r"production",
    # Trade
    r"tariff", r"trade.?war", r"\btrade\b", r"export", r"import", r"sanction",
    # Geopolitics (oil-driver)
    r"china", r"russia", r"ukraine", r"iran", r"middle.east", r"israel", r"hormuz",
    r"taiwan", r"geopolit",
    # Politics (national-level only — state/local gated by CURATION_EXCLUDE)
    r"president", r"congress", r"\bsenate\b", r"\bhouse\b", r"midterm",
    r"\b(?:democrat|republican)s?\b",
    # Fiscal / debt
    r"debt.ceiling", r"budget", r"shutdown", r"fiscal", r"deficit", r"stimulus",
    # Leaders
    r"starmer", r"macron", r"merz", r"scholz", r"trump",
    r"\bxi\b", r"putin", r"zelensky",
]
MACRO_RE = re.compile("|".join(MACRO_TAG_PATTERNS), re.I)

EXCLUDE_PATTERNS = [
    r"fifa", r"world.cup", r"olympics?", r"\bnba\b", r"\bnfl\b", r"\bmlb\b", r"\bnhl\b",
    r"super.?bowl", r"oscar", r"grammy", r"tony award", r"bachelor",
    r"\bgta\b", r"song of the year", r"album of", r"heisman",
    r"espys?", r"\bemmy", r"netflix", r"spotify", r"golden globe",
    r"formula.?1", r"\bf1\b", r"eurovision", r"love island",
]
EXCLUDE_RE = re.compile("|".join(EXCLUDE_PATTERNS), re.I)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_json_field(raw: Any) -> Any:
    if raw is None:
        return None
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (ValueError, json.JSONDecodeError):
            return None
    return raw


def _volume(market: dict) -> float:
    for key in ("volumeNum", "volume", "volume24hr"):
        v = market.get(key)
        if v is None:
            continue
        try:
            return float(v)
        except (TypeError, ValueError):
            continue
    return 0.0


def _market_row(market: dict, theme: str) -> dict | None:
    prices = _parse_json_field(market.get("outcomePrices"))
    tokens = _parse_json_field(market.get("clobTokenIds"))
    outcomes = _parse_json_field(market.get("outcomes"))
    if not tokens or len(tokens) < 2:
        return None
    try:
        yes_price = float(prices[0]) if prices else None
        no_price = float(prices[1]) if prices and len(prices) > 1 else None
    except (TypeError, ValueError):
        yes_price, no_price = None, None
    return {
        "id": market.get("id"),
        "conditionId": market.get("conditionId"),
        "slug": market.get("slug"),
        "question": market.get("question"),
        "outcomes": outcomes,
        "yes_token": str(tokens[0]),
        "no_token": str(tokens[1]),
        "yes_price": yes_price,
        "no_price": no_price,
        "lastTradePrice": market.get("lastTradePrice"),
        "volume": _volume(market),
        "volume24hr": market.get("volume24hr"),
        "liquidity": market.get("liquidityNum") or market.get("liquidity"),
        "endDate": market.get("endDate"),
        "theme": theme,
    }


# ---------------------------------------------------------------------------
# Phase 1 — watchlist build
# ---------------------------------------------------------------------------

def _harvest_tags_from_events(client: HTTPClient) -> list[dict]:
    """Fallback: scan /events response for tags if /tags is unavailable."""
    try:
        events = client.get_json("/events", params={"closed": "false", "limit": 500})
    except Exception as e:
        print(f"  [WARN] /events harvest failed: {e}")
        return []
    if isinstance(events, dict) and "data" in events:
        events = events["data"]
    seen: dict[str, dict] = {}
    for e in events if isinstance(events, list) else []:
        for t in e.get("tags") or []:
            slug = t.get("slug")
            label = t.get("label") or slug or ""
            if not slug or slug in seen:
                continue
            if EXCLUDE_RE.search(label) or EXCLUDE_RE.search(slug):
                continue
            if MACRO_RE.search(label) or MACRO_RE.search(slug):
                seen[slug] = {"label": label, "slug": slug, "id": t.get("id")}
    return list(seen.values())


def fetch_macro_tags(client: HTTPClient) -> list[dict]:
    try:
        tags = client.get_json("/tags", params={"limit": 1000})
    except Exception as e:
        print(f"  [WARN] /tags failed ({e}); harvesting from /events instead.")
        return _harvest_tags_from_events(client)
    if isinstance(tags, dict) and "data" in tags:
        tags = tags["data"]
    if not isinstance(tags, list):
        return _harvest_tags_from_events(client)

    out: list[dict] = []
    seen = set()
    for t in tags:
        label = str(t.get("label") or "")
        slug = str(t.get("slug") or "")
        if not slug or slug in seen:
            continue
        if EXCLUDE_RE.search(label) or EXCLUDE_RE.search(slug):
            continue
        if MACRO_RE.search(label) or MACRO_RE.search(slug):
            out.append({"label": label, "slug": slug, "id": t.get("id")})
            seen.add(slug)
    return out


def fetch_events_for_tag(client: HTTPClient, slug: str) -> list[dict]:
    try:
        events = client.get_json(
            "/events",
            params={"tag_slug": slug, "closed": "false", "limit": 200},
        )
    except Exception as e:
        print(f"    [WARN] tag_slug={slug}: {e}")
        return []
    if isinstance(events, dict) and "data" in events:
        events = events["data"]
    return events if isinstance(events, list) else []


def build_watchlist(client: HTTPClient) -> list[dict]:
    print("\n" + "=" * 70)
    print("Phase 1: Building macro watchlist")
    print("=" * 70)

    print("  Fetching /tags ...")
    macro_tags = fetch_macro_tags(client)
    print(f"  Matched {len(macro_tags)} macro-relevant tags:")
    for t in macro_tags:
        print(f"    - {t['label']!r:30s}  slug={t['slug']!r}")
    if not macro_tags:
        return []

    watchlist: dict[str, dict] = {}   # conditionId -> row
    print()
    for tag in macro_tags:
        slug, label = tag["slug"], tag["label"] or tag["slug"]
        events = fetch_events_for_tag(client, slug)
        added = 0
        for event in events:
            markets = event.get("markets") or []
            if not isinstance(markets, list):
                continue
            for m in markets:
                if m.get("closed"):
                    continue
                q = str(m.get("question") or "")
                if EXCLUDE_RE.search(q):
                    continue
                if _volume(m) < MIN_VOLUME:
                    continue
                cid = m.get("conditionId")
                if not cid or cid in watchlist:
                    continue
                row = _market_row(m, label)
                if row is None:
                    continue
                watchlist[cid] = row
                added += 1
        print(f"    [{slug:35s}]  events={len(events):>3}  new_markets={added}")
        time.sleep(0.15)

    return sorted(watchlist.values(), key=lambda r: r["volume"], reverse=True)


def print_watchlist_summary(rows: list[dict]) -> None:
    print(f"\n  Watchlist: {len(rows)} markets")
    by_theme: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_theme[r["theme"]].append(r)
    for theme, items in sorted(
        by_theme.items(), key=lambda x: -sum(r["volume"] for r in x[1])
    ):
        total = sum(r["volume"] for r in items)
        print(f"\n  [{theme}]  {len(items)} markets  total_vol=${total:,.0f}")
        for r in items[:6]:
            y = r["yes_price"]
            ystr = f"{y:.3f}" if y is not None else "  -  "
            q = (r["question"] or "")[:72]
            print(f"    YES={ystr}  vol=${r['volume']:>12,.0f}  {q}")
        if len(items) > 6:
            print(f"    ... and {len(items) - 6} more")


# ---------------------------------------------------------------------------
# Phase 2 — WebSocket stream
# ---------------------------------------------------------------------------

class _StreamState:
    """Per-run state for clean, deduplicated event printing."""

    def __init__(self) -> None:
        self.last_price: dict[str, float] = {}    # asset_id -> last YES trade price
        self.best_bid: dict[str, float | None] = {}
        self.best_ask: dict[str, float | None] = {}
        self.book_seen: set[str] = set()
        self.initial_books = 0
        self.quote_count = 0
        self.trade_count = 0


def _to_float(x: Any) -> float | None:
    if x is None or x == "":
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _print_event(ev: dict, meta: dict, state: _StreamState) -> None:
    """Route an event through the right formatter. Only YES-side tokens are kept."""
    etype = ev.get("event_type")
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")

    if etype == "book":
        aid = str(ev.get("asset_id") or "")
        m = meta.get(aid)
        if not m:
            return   # NO-side or foreign token; ignore
        bids = ev.get("bids") or []
        asks = ev.get("asks") or []
        bid = _to_float(bids[-1].get("price")) if bids else None
        ask = _to_float(asks[0].get("price")) if asks else None
        state.best_bid[aid] = bid
        state.best_ask[aid] = ask
        if aid not in state.book_seen:
            state.book_seen.add(aid)
            state.initial_books += 1
        return

    if etype == "last_trade_price":
        aid = str(ev.get("asset_id") or "")
        m = meta.get(aid)
        if not m:
            return   # trade on a NO-side or unsubscribed token
        price = _to_float(ev.get("price"))
        size = ev.get("size")
        side = str(ev.get("side", ""))
        prev = state.last_price.get(aid)
        if price is not None:
            state.last_price[aid] = price
        if prev is not None and price is not None:
            arrow = f"{prev:.3f} -> {price:.3f} ({price - prev:+.3f})"
        else:
            arrow = f"YES={price}"
        theme = (m["theme"] or "?")[:18]
        q = (m["question"] or "")[:55]
        state.trade_count += 1
        print(f"  {ts}  [{theme:18s}]  TRADE  {arrow:30s}  {side:4s} size={size:>8}  {q}")
        return

    if etype == "price_change":
        # Nested changes — filter to YES-token changes that actually move top of book.
        for ch in ev.get("price_changes") or []:
            aid = str(ch.get("asset_id") or "")
            m = meta.get(aid)
            if not m:
                continue   # NO-side token; skip
            new_bid = _to_float(ch.get("best_bid"))
            new_ask = _to_float(ch.get("best_ask"))
            prev_bid = state.best_bid.get(aid)
            prev_ask = state.best_ask.get(aid)
            if new_bid == prev_bid and new_ask == prev_ask:
                continue   # inside-the-book churn; top unchanged
            state.best_bid[aid] = new_bid
            state.best_ask[aid] = new_ask
            mid = (new_bid + new_ask) / 2 if (new_bid is not None and new_ask is not None) else None
            mid_s = f"{mid:.3f}" if mid is not None else "  -  "
            bid_s = f"{new_bid:.3f}" if new_bid is not None else "  -  "
            ask_s = f"{new_ask:.3f}" if new_ask is not None else "  -  "
            theme = (m["theme"] or "?")[:18]
            q = (m["question"] or "")[:55]
            state.quote_count += 1
            print(f"  {ts}  [{theme:18s}]  QUOTE  mid={mid_s}  bid={bid_s}/ask={ask_s}         {q}")
        return

    if etype == "market_resolved":
        aid = str(ev.get("asset_id") or "")
        m = meta.get(aid)
        if m:
            print(f"  {ts}  [{(m['theme'] or '?')[:18]:18s}]  RESOLVED  {(m['question'] or '')[:60]}")
        return

    # tick_size_change, new_market, and unknown types are intentionally ignored.


def stream_websocket(rows: list[dict], stream_log: Path) -> None:
    print("\n" + "=" * 70)
    print("Phase 2: Live WebSocket stream")
    print("=" * 70)

    meta = {r["yes_token"]: r for r in rows if r.get("yes_token")}
    token_ids = list(meta.keys())
    if not token_ids:
        print("  No token IDs to subscribe — skipping stream.")
        return

    state = _StreamState()
    for t, r in meta.items():
        if r.get("yes_price") is not None:
            state.last_price[t] = r["yes_price"]

    sub = {
        "assets_ids": token_ids,
        "type": "market",
        "initial_dump": True,
    }
    print(f"  URL:        {WS_URL}")
    print(f"  Subscribe:  {len(token_ids)} YES tokens")
    print(f"  Log file:   {stream_log}")
    print(f"  Filter:     TRADE + top-of-book QUOTE changes only (YES side)")
    print(f"  Ctrl+C to stop.\n")

    event_count = 0
    initial_summary_printed = False
    last_activity = time.monotonic()
    with ws_connect(WS_URL, max_size=None, ping_interval=None) as ws, \
            stream_log.open("a", encoding="utf-8") as log:
        ws.send(json.dumps(sub))
        last_ping = time.monotonic()
        try:
            while True:
                if time.monotonic() - last_ping > PING_INTERVAL_SEC:
                    try:
                        ws.send("PING")
                    except Exception:
                        pass
                    last_ping = time.monotonic()

                try:
                    msg = ws.recv(timeout=RECV_TIMEOUT_SEC)
                except TimeoutError:
                    if not initial_summary_printed and state.initial_books:
                        print(f"  [initial dump] received {state.initial_books} book snapshots "
                              f"for {len(token_ids)} subscribed tokens")
                        print(f"  [streaming]    waiting for trades / top-of-book moves...\n")
                        initial_summary_printed = True
                    if time.monotonic() - last_activity > 60:
                        print(f"  [heartbeat] {datetime.now(timezone.utc).strftime('%H:%M:%S')}  "
                              f"trades={state.trade_count}  quotes={state.quote_count}  "
                              f"(silent {int(time.monotonic() - last_activity)}s)")
                        last_activity = time.monotonic()
                    continue
                except Exception as e:
                    print(f"  [WS ERROR] {e}")
                    break

                if not msg or msg == "PONG":
                    continue
                try:
                    payload = json.loads(msg)
                except (ValueError, json.JSONDecodeError):
                    continue

                events = payload if isinstance(payload, list) else [payload]
                for ev in events:
                    if not isinstance(ev, dict):
                        continue
                    event_count += 1
                    log.write(json.dumps({
                        "recv_ts": datetime.now(timezone.utc).isoformat(),
                        "event": ev,
                    }) + "\n")
                    _print_event(ev, meta, state)
                last_activity = time.monotonic()

                if not initial_summary_printed and state.initial_books >= len(token_ids) * 0.8:
                    print(f"  [initial dump] received {state.initial_books} book snapshots "
                          f"for {len(token_ids)} subscribed tokens")
                    print(f"  [streaming]    waiting for trades / top-of-book moves...\n")
                    initial_summary_printed = True
        except KeyboardInterrupt:
            print(f"\n  Stopped. raw_events={event_count}  trades={state.trade_count}  "
                  f"quotes={state.quote_count}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    print("=" * 70)
    print(f"Polymarket macro stream  —  {datetime.now().isoformat(timespec='seconds')}")
    print("=" * 70)

    with HTTPClient(base_url=GAMMA_BASE, timeout=30) as client:
        rows = build_watchlist(client)
        if not rows:
            print("  Watchlist is empty — stopping.")
            return
        (CACHE_DIR / "watchlist.json").write_text(
            json.dumps(rows, indent=2, default=str)
        )
        print(f"\n  Saved watchlist to {CACHE_DIR / 'watchlist.json'}")
        print_watchlist_summary(rows)

    stream_websocket(rows, CACHE_DIR / "stream.jsonl")


if __name__ == "__main__":
    main()
