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

Window mode — fill an explicit interior gap (e.g. an outage) across all active
slugs rather than only warming up new ones:
    python -m scripts.prediction.polymarket.backfill \
        --start 2026-06-13T18:00 --end 2026-06-15T00:00

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


def _parse_ts(value: str) -> int:
    """Parse epoch-seconds or an ISO8601 date/datetime into an int epoch.

    Naive datetimes are assumed UTC (the snapshot_ts convention).
    """
    value = value.strip()
    if value.isdigit():
        return int(value)
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


def _global_max_cap(conn: sqlite3.Connection) -> int:
    """End-ts ceiling that keeps backfill points from overtaking live polls.

    Capping strictly below the global MAX(snapshot_ts) preserves the
    macro_snapshot invariant: a backfilled point must never become the newest
    observation, or macro_snapshot looks up rows at that instant and surfaces
    dozens of false-missing entries.
    """
    cap = int(time.time()) - 60
    global_max = conn.execute(
        "SELECT MAX(snapshot_ts) FROM market_observation"
    ).fetchone()[0]
    if global_max:
        max_dt = datetime.fromisoformat(global_max.replace("Z", "+00:00"))
        cap = min(cap, int(max_dt.timestamp()) - 1)
    return cap


def _collect_rows(
    ev: dict, *, start_ts: int, end_ts: int, fidelity: int, slug: str
) -> tuple[int, list[tuple]]:
    """Fetch CLOB price-history for each live market in ``ev`` within the window.

    Returns ``(n_live_markets, rows)`` ready for ``_insert_rows``.
    """
    ev_id = ev.get("id")
    ev_slug = ev.get("slug")
    ev_title = ev.get("title")
    markets = ev.get("markets") or []

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
        # CLOB /prices-history does NOT honor endTs — it always appends a
        # trailing near-current point (observed ~2h past a requested end). Left
        # unfiltered, that point lands at ~now with a handful of rows and
        # becomes the global MAX(snapshot_ts), breaking macro_snapshot (which
        # reads only rows at the MAX). Clamp to the requested window here.
        hist = [
            pt for pt in hist
            if pt.get("t") is not None and start_ts <= int(pt["t"]) <= end_ts
        ]
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
    return n_live_markets, rows


def _insert_rows(conn: sqlite3.Connection, rows: list[tuple]) -> None:
    conn.executemany(
        """INSERT OR IGNORE INTO market_observation (
            snapshot_ts, condition_id, event_id, event_slug, event_title,
            question, yes_price, no_price, best_bid, best_ask, spread,
            last_trade_price, volume_total, volume_24h, liquidity, updated_at_src
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        rows,
    )
    conn.commit()


def backfill_slug(
    conn: sqlite3.Connection, slug: str, *, hours: int, fidelity: int
) -> tuple[int, int, str]:
    """Warm-up mode: backfill the N hours *before* the slug's earliest row.

    Returns (n_markets, n_rows, status_msg).
    """
    ev = fetch_event(slug)
    if not ev:
        return 0, 0, "no event returned"
    ev_slug = ev.get("slug")

    # Cap end_ts strictly below BOTH this slug's earliest existing row and the
    # global MAX — see _global_max_cap. A genuinely-new slug (no existing rows)
    # backfills right up to the global-max ceiling.
    end_ts = _global_max_cap(conn)
    existing_min = conn.execute(
        "SELECT MIN(snapshot_ts) FROM market_observation WHERE event_slug=?",
        [ev_slug],
    ).fetchone()[0]
    if existing_min:
        cap_dt = datetime.fromisoformat(existing_min.replace("Z", "+00:00"))
        end_ts = min(end_ts, int(cap_dt.timestamp()) - 1)
    start_ts = end_ts - hours * 3600
    if end_ts <= start_ts:
        return 0, 0, "no window to backfill"

    n_live_markets, rows = _collect_rows(
        ev, start_ts=start_ts, end_ts=end_ts, fidelity=fidelity, slug=slug
    )
    if not rows:
        return n_live_markets, 0, "no history points"
    _insert_rows(conn, rows)
    return n_live_markets, len(rows), "ok"


def backfill_slug_window(
    conn: sqlite3.Connection, slug: str, *, start_ts: int, end_ts: int, fidelity: int
) -> tuple[int, int, str]:
    """Window mode: backfill an explicit [start_ts, end_ts] (e.g. fill an outage gap).

    Unlike warm-up mode this does NOT cap to the slug's earliest row, so it can
    fill an *interior* hole; INSERT OR IGNORE keeps it from clobbering live rows.
    end_ts is still capped below the global MAX to protect macro_snapshot.
    Returns (n_markets, n_rows, status_msg).
    """
    ev = fetch_event(slug)
    if not ev:
        return 0, 0, "no event returned"
    end_ts = min(end_ts, _global_max_cap(conn))
    if end_ts <= start_ts:
        return 0, 0, "window collapsed after global-max cap"

    n_live_markets, rows = _collect_rows(
        ev, start_ts=start_ts, end_ts=end_ts, fidelity=fidelity, slug=slug
    )
    if not rows:
        return n_live_markets, 0, "no history points"
    _insert_rows(conn, rows)
    return n_live_markets, len(rows), "ok"


def _process(targets: list[str], per_slug) -> None:
    """Run ``per_slug(conn, slug)`` over each target, printing a per-slug line."""
    conn = sqlite3.connect(str(DB_FILE), timeout=5)
    conn.execute("PRAGMA journal_mode=WAL")
    total_rows = 0
    total_markets = 0
    try:
        for slug in targets:
            try:
                n_mkts, n_rows, msg = per_slug(conn, slug)
                print(f"  {slug:<60s}  markets={n_mkts:<3d}  rows={n_rows:<5d}  {msg}")
                total_rows += n_rows
                total_markets += n_mkts
            except Exception as e:
                print(f"  {slug:<60s}  FAILED: {e!r}")
    finally:
        conn.close()
    print(f"[backfill] done — {len(targets)} slugs, {total_markets} live markets, "
          f"{total_rows} rows inserted (INSERT OR IGNORE).")


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

    _process(targets, lambda conn, slug: backfill_slug(
        conn, slug, hours=args.hours, fidelity=args.fidelity))


def cmd_window(args: argparse.Namespace) -> None:
    if not DB_FILE.exists():
        print(f"[backfill] no DB at {DB_FILE} — run streaming poll first.")
        return
    start_ts = _parse_ts(args.start)
    end_ts = _parse_ts(args.end)
    if end_ts <= start_ts:
        print("[backfill] --end must be after --start.")
        return

    if args.slugs:
        targets = args.slugs
    else:
        wl = load_watchlist(WATCHLIST_FILE)
        targets = [s for s in active_slugs(wl) if not s.endswith("*")]
    s_iso = datetime.fromtimestamp(start_ts, tz=timezone.utc).isoformat(timespec="seconds")
    e_iso = datetime.fromtimestamp(end_ts, tz=timezone.utc).isoformat(timespec="seconds")
    print(f"[backfill] window mode {s_iso} .. {e_iso} over {len(targets)} active slugs "
          f"(fidelity={args.fidelity}m)")

    _process(targets, lambda conn, slug: backfill_slug_window(
        conn, slug, start_ts=start_ts, end_ts=end_ts, fidelity=args.fidelity))


def main() -> None:
    p = argparse.ArgumentParser(prog="polymarket_backfill")
    p.add_argument("--hours", type=int, default=48,
                   help="Warm-up mode: hours of history to fetch before a slug's "
                        "earliest row (default 48)")
    p.add_argument("--fidelity", type=int, default=15,
                   help="Minutes between price points (default 15, matches streamer cadence)")
    p.add_argument("--slugs", nargs="+",
                   help="Specific slugs (default warm-up: active slugs with zero rows; "
                        "default window: all active slugs)")
    p.add_argument("--start",
                   help="Window mode: ISO8601 or epoch start (UTC if naive). Requires --end. "
                        "Fills an explicit interior gap across active slugs.")
    p.add_argument("--end",
                   help="Window mode: ISO8601 or epoch end. Requires --start.")
    args = p.parse_args()
    if args.start or args.end:
        if not (args.start and args.end):
            p.error("window mode needs BOTH --start and --end")
        cmd_window(args)
    else:
        cmd_run(args)


if __name__ == "__main__":
    main()
