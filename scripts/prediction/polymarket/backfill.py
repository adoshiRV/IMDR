"""Polymarket history backfill — warm up observations.db for newly-tracked slugs.

When a slug is added to ``watchlist.yml``, the streaming poller starts capturing
forward observations but polywatch's DRIFT / VOL_BURST checks need prior context
to fire. This script backfills the last N hours of YES-price history from the
Polymarket CLOB ``/prices-history`` endpoint for any active watchlist slug that
has no rows yet in ``market_observation``.

Run:
    python -m scripts.prediction.polymarket.backfill              # missing slugs, 48h
    python -m scripts.prediction.polymarket.backfill --hours 72
    python -m scripts.prediction.polymarket.backfill --slugs slug1 slug2 ...

Notes:
- Backfilled rows have NULL for spread / bid / ask / volume / liquidity —
  CLOB price-history only returns (t, p). Polywatch's SPIKE, MODAL_FLIP, DRIFT
  checks all work on yes_price alone; VOL_BURST is naturally skipped on rows
  with NULL volume.
- Uses ``INSERT OR IGNORE`` so re-running is idempotent and never overwrites a
  live streaming observation.
- Fidelity is in minutes; default 15 matches the streamer's default cadence.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from scripts.prediction.polymarket.watchlist import (
    WATCHLIST_FILE,
    active_slugs,
    load_watchlist,
)

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

POLY_DIR = Path(r"C:\IMDR_LOCAL\polymarket")
DB_FILE = POLY_DIR / "observations.db"
GAMMA_BASE = "https://gamma-api.polymarket.com"
CLOB_BASE = "https://clob.polymarket.com"
HTTP_TIMEOUT = 20


def slugs_needing_backfill(
    conn: sqlite3.Connection, slugs: list[str], hours: int
) -> list[str]:
    """Slug needs backfill if its earliest observation is newer than now-hours.

    A slug freshly added to the watchlist might already have 1-2 forward
    observations from the streamer; we still want to fetch the prior 48h of
    history so polywatch DRIFT has context.
    """
    if not slugs:
        return []
    cutoff = datetime.now(timezone.utc).timestamp() - hours * 3600
    cutoff_iso = datetime.fromtimestamp(cutoff, tz=timezone.utc).isoformat(
        timespec="microseconds"
    )
    qmarks = ",".join("?" for _ in slugs)
    rows = conn.execute(
        f"SELECT event_slug, MIN(snapshot_ts) FROM market_observation "
        f"WHERE event_slug IN ({qmarks}) GROUP BY event_slug",
        slugs,
    ).fetchall()
    earliest = {r[0]: r[1] for r in rows}
    out: list[str] = []
    for s in slugs:
        first = earliest.get(s)
        if first is None or first > cutoff_iso:
            out.append(s)
    return out


def fetch_event(slug: str) -> dict | None:
    r = requests.get(
        f"{GAMMA_BASE}/events",
        params={"slug": slug, "closed": "false"},
        timeout=HTTP_TIMEOUT,
    )
    r.raise_for_status()
    payload = r.json()
    if isinstance(payload, list) and payload:
        return payload[0]
    return None


def fetch_history(token_id: str, start_ts: int, end_ts: int, fidelity: int) -> list[dict]:
    r = requests.get(
        f"{CLOB_BASE}/prices-history",
        params={
            "market": token_id,
            "startTs": start_ts,
            "endTs": end_ts,
            "fidelity": fidelity,
        },
        timeout=HTTP_TIMEOUT,
    )
    r.raise_for_status()
    payload = r.json()
    if isinstance(payload, dict):
        return payload.get("history") or []
    return payload or []


def backfill_slug(
    conn: sqlite3.Connection, slug: str, *, hours: int, fidelity: int
) -> tuple[int, int, str]:
    """Returns (n_markets, n_rows, status_msg)."""
    ev = fetch_event(slug)
    if not ev:
        return 0, 0, "no event returned"
    ev_id = ev.get("id")
    ev_slug = ev.get("slug")
    ev_title = ev.get("title")
    markets = ev.get("markets") or []

    # Don't let backfill points overtake live polled observations. If a slug
    # has any live rows, cap backfill strictly before its earliest one — else
    # the new global MAX(snapshot_ts) becomes a backfill row, which breaks
    # macro_snapshot's latest-timestamp lookup. For genuinely-new slugs, cap
    # at now-60s for the same reason.
    existing_min = conn.execute(
        "SELECT MIN(snapshot_ts) FROM market_observation WHERE event_slug=?",
        [ev_slug],
    ).fetchone()[0]
    now_ts = int(time.time())
    if existing_min:
        cap_dt = datetime.fromisoformat(existing_min.replace("Z", "+00:00"))
        end_ts = min(now_ts - 60, int(cap_dt.timestamp()) - 1)
    else:
        end_ts = now_ts - 60
    start_ts = end_ts - hours * 3600
    if end_ts <= start_ts:
        return 0, 0, "no window to backfill"

    rows: list[tuple] = []
    n_live_markets = 0
    for m in markets:
        cond_id = m.get("conditionId")
        if not cond_id:
            continue
        if m.get("closed") or m.get("archived"):
            continue
        toks_raw = m.get("clobTokenIds")
        if isinstance(toks_raw, str):
            try:
                toks = json.loads(toks_raw)
            except (ValueError, json.JSONDecodeError):
                toks = []
        else:
            toks = toks_raw or []
        if not toks:
            continue
        yes_token = toks[0]
        try:
            hist = fetch_history(yes_token, start_ts, end_ts, fidelity)
        except requests.HTTPError as e:
            print(f"  [{slug}] cond={cond_id[:10]} history fetch failed: {e}")
            continue
        if not hist:
            continue
        n_live_markets += 1
        question = m.get("question")
        for pt in hist:
            t = pt.get("t")
            p = pt.get("p")
            if t is None or p is None:
                continue
            try:
                p = float(p)
            except (TypeError, ValueError):
                continue
            snap_iso = datetime.fromtimestamp(int(t), tz=timezone.utc).isoformat(
                timespec="microseconds"
            )
            rows.append(
                (
                    snap_iso,
                    cond_id,
                    ev_id,
                    ev_slug,
                    ev_title,
                    question,
                    p,            # yes_price
                    1.0 - p,      # no_price (CLOB is binary)
                    None, None, None,  # best_bid, best_ask, spread
                    None, None, None, None,  # last_trade, vol_total, vol_24h, liquidity
                    None,         # updated_at_src
                )
            )

    if not rows:
        return n_live_markets, 0, "no history points"

    conn.executemany(
        """INSERT OR IGNORE INTO market_observation (
            snapshot_ts, condition_id, event_id, event_slug, event_title,
            question, yes_price, no_price, best_bid, best_ask, spread,
            last_trade_price, volume_total, volume_24h, liquidity, updated_at_src
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        rows,
    )
    n_inserted = conn.total_changes
    conn.commit()
    return n_live_markets, len(rows), "ok"


def cmd_run(args: argparse.Namespace) -> None:
    if not DB_FILE.exists():
        print(f"[backfill] no DB at {DB_FILE} — run streaming poll first.")
        return

    if args.slugs:
        targets = args.slugs
    else:
        wl = load_watchlist(WATCHLIST_FILE)
        all_active = [s for s in active_slugs(wl) if not s.endswith("*")]
        conn = sqlite3.connect(str(DB_FILE), timeout=2)
        try:
            targets = slugs_needing_backfill(conn, all_active, args.hours)
        finally:
            conn.close()
        if not targets:
            print(f"[backfill] all active watchlist slugs have >={args.hours}h of history.")
            return
        print(f"[backfill] {len(targets)} watchlist slugs lack {args.hours}h of history")

    conn = sqlite3.connect(str(DB_FILE), timeout=5)
    conn.execute("PRAGMA journal_mode=WAL")
    total_rows = 0
    total_markets = 0
    try:
        for slug in targets:
            try:
                n_mkts, n_rows, msg = backfill_slug(
                    conn, slug, hours=args.hours, fidelity=args.fidelity
                )
                print(f"  {slug:<60s}  markets={n_mkts:<3d}  rows={n_rows:<5d}  {msg}")
                total_rows += n_rows
                total_markets += n_mkts
            except Exception as e:
                print(f"  {slug:<60s}  FAILED: {e!r}")
    finally:
        conn.close()
    print(f"[backfill] done — {len(targets)} slugs, {total_markets} live markets, "
          f"{total_rows} rows inserted (INSERT OR IGNORE).")


def main() -> None:
    p = argparse.ArgumentParser(prog="polymarket_backfill")
    p.add_argument("--hours", type=int, default=48,
                   help="Hours of history to fetch (default 48)")
    p.add_argument("--fidelity", type=int, default=15,
                   help="Minutes between price points (default 15, matches streamer cadence)")
    p.add_argument("--slugs", nargs="+",
                   help="Specific slugs to backfill (default: any active watchlist slug "
                        "with zero rows in observations.db)")
    cmd_run(p.parse_args())


if __name__ == "__main__":
    main()
