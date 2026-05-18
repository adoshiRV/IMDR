"""Polymarket streaming watcher — URL-driven, SQLite-backed.

A small local utility that polls Polymarket's Gamma API for a hand-curated set
of events and stores observations in a SQLite database under
``C:\\IMDR_LOCAL\\polymarket\\``. Lives outside IMDR's MSSQL footprint per
the user's directive ("we don't need to make a whole table on IMDR for this").

Four subcommands:

    poll      one-shot single poll (one HTTP call, write rows, exit)
    loop      long-running daemon, polls every --interval seconds
    discover  refresh the auto-discovered slug cache from Gamma /tags
    cleanup   retention + VACUUM (drops rows older than RETENTION_DAYS, reclaims
              space, and strips raw_response_json from kept success rows so the
              db cannot bloat past a few MB) — wired into scripts/imdr_daily.py
              and run daily.

Watchlist sources (unioned each poll):
  - ``C:\\IMDR_LOCAL\\polymarket\\watchlist.yml`` — manual, structured YAML
    (see ``scripts/prediction/polymarket/watchlist.py`` for schema).
  - ``C:\\IMDR_LOCAL\\polymarket\\auto_discovered.json`` — refreshed hourly by
    ``loop`` from Gamma /tags using the macro tag patterns. Skip with
    ``--no-discover`` on the loop command.

Run:
    python -m scripts.prediction.polymarket.streaming poll
    python -m scripts.prediction.polymarket.streaming loop --interval 900
    python -m scripts.prediction.polymarket.streaming discover
    python -m scripts.prediction.polymarket.streaming cleanup
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from imdr.connectors.http import HTTPClient

from scripts.explore.polymarket_macro_stream import (
    EXCLUDE_RE,
    MACRO_RE,
    _to_float,
)
from scripts.prediction.polymarket.watchlist import (
    WATCHLIST_FILE,
    active_slugs,
    asset_tag_map,
    load_watchlist,
    mark_pruned,
)

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

POLY_DIR = Path(r"C:\IMDR_LOCAL\polymarket")
DISCOVERY_FILE = POLY_DIR / "auto_discovered.json"
DB_FILE = POLY_DIR / "observations.db"
GAMMA_BASE = "https://gamma-api.polymarket.com"

DEFAULT_INTERVAL_SEC = 900
INTERVAL_MIN_SEC = 60
INTERVAL_MAX_SEC = 1800
RETENTION_DAYS = 7
HEARTBEAT_EVERY_N = 12

# Gamma /events caps URLs at ~8KB; chunk slug requests so the URL stays small.
# 50 slugs * ~60 bytes each (`&slug=…`) ≈ 3KB, comfortably under the limit.
SLUG_CHUNK_SIZE = 50

# Discovery: refresh the auto_discovered.json no more often than this
DISCOVERY_REFRESH_SEC = 3600
# Discovery: 24h volume floor for auto-included events.
# 2026-05-04 v2: returned to $0 — thinly-traded data-release markets (e.g.
# april-unemployment-rate at ~$3K 24h vol) carry the strongest information
# signal precisely because they're not consensus-driven. Noise gating now
# happens via CURATION_EXCLUDE topic patterns, not volume.
DISCOVERY_MIN_VOLUME = 0.0
# Discovery: cap on auto-discovered slugs (top-N by volume24h). Manual
# watchlist is always included regardless of this cap. Lowered from 150 → 30
# on 2026-05-04 — only the most-liquid macro markets surface; long-tail noise
# (Russia territorial captures, Abraham Accords speculation) drops out.
DISCOVERY_MAX_SLUGS = 30

# Curation filter applied on top of EXCLUDE_RE. Drops markets that are not
# information-flow pre-indicators of asset moves: long-horizon nominee races
# (2028+), state/provincial/local elections, asset-price binaries (BTC/ETH/oil
# hits), and Fed-decision markets which trail OIS / FedWatch.
CURATION_EXCLUDE_PATTERNS = [
    r"nominee.?2028", r"president.{0,5}2028", r"election.?winner.?2028",
    r"governor", r"legislative.?assembly", r"provincial",
    r"mayoral", r"province", r"state.?senate", r"state.?house",
    # State / district / referendum politics — too local to move macro.
    # Aggregate `balance-of-power-2026-midterms` and party-of-house/senate
    # markets are already in watchlist.yml; individual district + state-Senate
    # races and ballot props are noise.
    r"(?:democratic|republican).?primary",
    r"\bhouse.?primary\b", r"\bsenate.?primary\b",
    # State-name + (midterm|primary|senate|house|race|election|referendum|amendment)
    r"(?:california|texas|florida|new.?york|louisiana|mississippi|alabama|georgia|virginia|arizona|nevada|colorado|ohio|michigan|pennsylvania|wisconsin|minnesota|illinois|massachusetts|new.?jersey|tennessee|kentucky|north.?carolina|south.?carolina|indiana|missouri|oklahoma|kansas|utah|oregon|washington|new.?hampshire|wyoming|iowa|idaho|maine|nebraska|montana|rhode.?island|new.?mexico|delaware|south.?dakota|alaska|hawaii|arkansas|connecticut|north.?dakota|vermont|west.?virginia|maryland).?(?:midterm|primary|senate|house|race|election|referendum|amendment|abortion)",
    # State two-letter abbreviation prefixes (e.g. ca-23, hi-02-house, ms-house).
    # Anchored to slug start because abbreviations like "in" / "la" / "or" are
    # also common English words — "lee-...-in-2026" must not match.
    r"^(?:ca|tx|fl|ny|la|ms|al|ga|va|az|nv|co|oh|mi|pa|wi|mn|il|ma|nj|tn|ky|nc|sc|in|mo|ok|ks|ut|or|wa|nh|wy|ia|id|me|ne|mt|ri|nm|de|sd|ak|hi|ar|ct|nd|vt|wv|md)-(?:\d+|primary|midterm|senate|house)",
    # District-level "house-election-winner" and "house-winner" binaries
    r"-house-(?:election-)?winner\b",
    # State ballot props (abortion, constitutional amendments, etc.)
    r"abortion.?(?:protection|amendment|ban)", r"state.?constitution",
    r"sex.?change.?for.?minors",
    r"special.?election",
    r"what.?price.?will", r"hit.?in.?(?:january|february|march|april|may|june|july|august|september|october|november|december)",
    r"\bcl-hit\b", r"\bgc-hit\b", r"\bsi-hit\b",
    r"bitcoin.?vs", r"largest.?company",
    r"fed.?decision", r"fed.?rate.?cut", r"fed.?chair", r"warsh.?confirmed",
    r"who.?will.?be.?confirmed",
    # Direct asset-price binaries — these trail spot, not lead it. Drop wholesale.
    r"\b(?:wti|brent|crude|ng|gas|gasoline|xau|gold|xag|silver|btc|bitcoin|eth|ethereum)\b.*\bhit\b",
    r"\b(?:wti|brent|crude|ng|gas|gasoline|xau|gold|xag|silver|btc|bitcoin|eth|ethereum)\b.*(?:up.?or.?down|closes.?(?:above|below)|all.?time.?high|all.?time.?low)",
    r"crude.?oil.?(?:all.?time.?high|all.?time.?low|reserves)",
    r"hit.?week.?of", r"hit.?by.?end.?of",
    r"\busd.?hit\b",
    # Entertainment / personal-life / novelty — no plausible macro transmission.
    # Added 2026-05-01 after auto-discovery surfaced citizenship-revoked,
    # divorce, Kanye, "praise Allah", "51st state", and pardon markets.
    r"\b2028\b",                              # 2028 election speculation too far out
    r"citizenship.?revoked",                  # person-specific noise
    r"\b\d+(?:st|nd|rd|th)[\s-]?state\b",     # "51st state" joke markets
    r"\bdivorce\b",                           # personal-life
    r"\bkanye\b",                             # celebrity
    r"praise.{0,10}allah",                    # novelty/entertainment
    r"renames?.{0,40}\bto\b",                 # joke rename markets
    r"epstein.?(?:island|client)",            # celebrity-gossip
    r"\bpardon",                              # presidential pardons
    r"\barrested\b",                          # public-figure arrests
    # Added 2026-05-04 after polywatch fired noise alerts on these patterns:
    r"publicly.?insult",                      # "Trump publicly insults someone on..."
    r"\binsult\b",                            # broader insult markets
    r"\bcustody\b",                           # Yoon out of custody, etc
    r"abraham.?accords?",                     # speculative diplomatic markets
    r"normalize.?relations?",                 # speculative bilateral normalization
    r"national.?emergency",                   # low-probability speculation
    r"\bcapture.?all.?of\b",                  # Russia/Ukraine territorial micro-moves
    r"\bdrops?.?out\b",                       # Netanyahu/etc drops-out speculation
    # Random-word filters (2026-05-04 v2) — categories of consistently
    # non-macro noise that auto-discovery surfaces. Volume floor was removed,
    # so topic gating must do the noise filtering on its own.
    # — Mortality / personal life
    r"\b(?:dies?|death|dying|dead)\b",        # X dies by Y mortality binaries
    r"\bwedding\b|\bmarries\b|\bengaged\b",   # personal life events
    r"\bbreakup\b|\bdating\b",                # relationship gossip
    # — Gossip / commentary / celebrity
    r"\bbeef\b|\bfeud\b",                     # X-vs-Y gossip
    r"\bnostradamus\b|\bpsychic\b|predicts?\s+the",  # speculation-of-prediction
    r"\bnext.?(?:pope|emperor|monarch|royal)\b",    # religious/monarchy
    r"\bcoronation\b|\babdicat",              # royal events
    # — Awards / culture
    r"\bnobel\b",                             # Nobel Prize markets
    r"time.?person.?of.?the.?year",           # Time POTY
    r"\bbox.?office\b",                       # movie ticket sales
    r"\bbest\b.{0,30}(?:picture|movie|film|album|song|book|director|actor|actress)\b",
    r"\b(?:movie|film|tv|show|series)\s+(?:hit|gross|premier|debut)",
    # — Sports / entertainment broaders (supplements EXCLUDE_RE)
    r"\bcoach\b|\bdraft\s+pick\b|\brookie\b",
    r"\bgrand.?slam\b|\bfinals?\s+winner\b",
    # — Tech / consumer noise
    r"\b(?:tiktok|instagram|gmail|youtube|whatsapp|snapchat|reddit)\b",
    # — Personal legal / scandal
    r"\bindicted\b|\bconvicted\b|\bsentenced\b|\bplea\b",
    r"\bscandal\b",
    # — Speculative tail / catastrophe
    r"\b(?:wwiii?|world.?war.?iii?)\b",
    r"alien.?(?:contact|invasion|disclosure)",
    r"\b(?:apocalypse|rapture|extinction)\b",
    # — Verbal-act / social-media markets ("Will X tweet/say Y by Z")
    r"\b(?:tweets?|posts?)[\s-]+(?:about|on|by|before)",
    r"will.{0,15}(?:say|tweet|post)[\s-]+",
    # — Health / vaccine speculation (rare but appears in 'science' tag)
    r"\bcure\b.{0,20}(?:cancer|aids|alzheimer|disease)",
    r"\bvaccine\b.{0,20}(?:approved|hits|reaches)",
    # — Generic "next X" personality races (presidential-2028 already gated)
    r"\bnext.?(?:ceo|chairman|president of\s+(?!the\s+(?:united\s+states|us|fed|ecb)))",
]
CURATION_EXCLUDE_RE = re.compile("|".join(CURATION_EXCLUDE_PATTERNS), re.I)

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")

DDL = """
CREATE TABLE IF NOT EXISTS market_observation (
    snapshot_ts        TEXT     NOT NULL,
    condition_id       TEXT     NOT NULL,
    event_id           INTEGER,
    event_slug         TEXT,
    event_title        TEXT,
    question           TEXT,
    yes_price          REAL,
    no_price           REAL,
    best_bid           REAL,
    best_ask           REAL,
    spread             REAL,
    last_trade_price   REAL,
    volume_total       REAL,
    volume_24h         REAL,
    liquidity          REAL,
    updated_at_src     TEXT,
    PRIMARY KEY (snapshot_ts, condition_id)
);
CREATE INDEX IF NOT EXISTS idx_obs_event_ts ON market_observation (event_id, snapshot_ts);
CREATE INDEX IF NOT EXISTS idx_obs_ts       ON market_observation (snapshot_ts);
CREATE INDEX IF NOT EXISTS idx_obs_cond_ts  ON market_observation (condition_id, snapshot_ts);

CREATE TABLE IF NOT EXISTS poll_log (
    poll_ts            TEXT     PRIMARY KEY,
    n_slugs_requested  INTEGER,
    n_events_returned  INTEGER,
    n_markets_seen     INTEGER,
    n_rows_written     INTEGER,
    http_ok            INTEGER  NOT NULL,
    error              TEXT,
    raw_response_json  TEXT
);

CREATE TABLE IF NOT EXISTS watchlist (
    slug             TEXT     PRIMARY KEY,
    event_id         INTEGER,
    first_added_ts   TEXT     NOT NULL,
    last_seen_ts     TEXT,
    removed_ts       TEXT
);
"""


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def open_db() -> sqlite3.Connection:
    """Open the polymarket SQLite DB.

    WAL journal mode + 2s busy_timeout: streaming.py and polywatch.py both
    hold long-lived connections to this file. Without WAL, a writer in one
    process locks out the other and surfaces as ``OperationalError: database
    is locked``.
    """
    POLY_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_FILE), timeout=2)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(DDL)
    conn.commit()
    return conn


def _harvest_macro_tags(http: HTTPClient) -> list[str]:
    """Get macro tag slugs by unioning /tags and event tags scanned across the
    most-active /events response. Polymarket's /tags is a curated subset, so
    /events provides the long tail (iran, hormuz, geopolitics, etc.).
    """
    seen: set[str] = set()

    def _accept(slug: str, label: str) -> None:
        if not slug or slug in seen:
            return
        if EXCLUDE_RE.search(slug) or EXCLUDE_RE.search(label):
            return
        if MACRO_RE.search(slug) or MACRO_RE.search(label):
            seen.add(slug)

    try:
        tags = http.get_json("/tags", params={"limit": 1000})
        if isinstance(tags, dict) and "data" in tags:
            tags = tags["data"]
        if isinstance(tags, list):
            for t in tags:
                _accept(str(t.get("slug") or ""), str(t.get("label") or ""))
    except Exception as e:
        print(f"[discover] /tags fetch failed ({e!r}); continuing with /events",
              file=sys.stderr)

    # Harvest tags from active events (sorted by volume so the top markets
    # bring in their tags). Page through to broaden coverage.
    for offset in (0, 200, 400):
        try:
            events = http.get_json(
                "/events",
                params={
                    "closed": "false",
                    "limit": 200,
                    "offset": offset,
                    "order": "volume24hr",
                    "ascending": "false",
                },
            )
            if isinstance(events, dict) and "data" in events:
                events = events["data"]
        except Exception as e:
            print(f"[discover] /events offset={offset} failed ({e!r})",
                  file=sys.stderr)
            continue
        if not isinstance(events, list):
            continue
        for ev in events:
            for t in ev.get("tags") or []:
                _accept(str(t.get("slug") or ""), str(t.get("label") or ""))

    return sorted(seen)


def discover_macro_slugs(http: HTTPClient,
                         min_volume: float = DISCOVERY_MIN_VOLUME) -> dict:
    """Scan macro tags → fetch events → return slug list with metadata.

    Output schema (also written to ``DISCOVERY_FILE``)::

        {
          "refreshed_ts": "<iso>",
          "tags_matched": [<slug>, ...],
          "slugs": [<slug>, ...],
          "events": [{"slug","title","volume24h","tag"}, ...]
        }
    """
    refreshed_ts = datetime.now(timezone.utc).isoformat(timespec="microseconds")
    tags = _harvest_macro_tags(http)
    seen_slugs: dict[str, dict] = {}
    for tag in tags:
        try:
            events = http.get_json(
                "/events",
                params={"tag_slug": tag, "closed": "false", "limit": 200},
            )
        except Exception as e:
            print(f"[discover] tag={tag} fetch failed: {e!r}", file=sys.stderr)
            continue
        if isinstance(events, dict) and "data" in events:
            events = events["data"]
        for ev in events if isinstance(events, list) else []:
            slug = str(ev.get("slug") or "")
            if not slug or not SLUG_RE.match(slug):
                continue
            title = str(ev.get("title") or "")
            if EXCLUDE_RE.search(slug) or EXCLUDE_RE.search(title):
                continue
            if CURATION_EXCLUDE_RE.search(slug) or CURATION_EXCLUDE_RE.search(title):
                continue
            # Skip events past their deadline. Polymarket often leaves
            # `closed=false` set on the parent for hours/days after endDate;
            # combined with sub-markets whose orderbooks have already closed
            # (outcomePrices=None), the per-market `_is_resolved` check is too
            # lenient on its own. Event endDate < now is the unambiguous signal
            # that the event is over.
            now_iso = datetime.now(timezone.utc).isoformat()
            ev_end = ev.get("endDate")
            if ev_end and ev_end < now_iso:
                continue
            sub_markets = ev.get("markets") or []
            if isinstance(sub_markets, list) and sub_markets and \
                    all(_is_resolved(m, now_iso) for m in sub_markets):
                continue
            v24 = _to_float(ev.get("volume24hr")) or 0.0
            if v24 < min_volume:
                continue
            existing = seen_slugs.get(slug)
            if existing is None or v24 > existing["volume24h"]:
                seen_slugs[slug] = {
                    "slug": slug,
                    "title": title,
                    "volume24h": v24,
                    "tag": tag,
                }
        time.sleep(0.1)
    # Cap to top-N by volume24h. Manual watchlist is unioned in separately
    # in resolve_slugs(), so curated events are unaffected.
    ranked = sorted(seen_slugs.values(),
                    key=lambda r: r["volume24h"], reverse=True)
    capped = ranked[:DISCOVERY_MAX_SLUGS]
    payload = {
        "refreshed_ts": refreshed_ts,
        "min_volume": min_volume,
        "max_slugs": DISCOVERY_MAX_SLUGS,
        "tags_matched": tags,
        "slugs": sorted(r["slug"] for r in capped),
        "events": capped,
        "n_total_discovered": len(ranked),
    }
    DISCOVERY_FILE.parent.mkdir(parents=True, exist_ok=True)
    DISCOVERY_FILE.write_text(json.dumps(payload, indent=2))
    return payload


def load_discovered_slugs(max_age_sec: int = DISCOVERY_REFRESH_SEC * 24) -> list[str]:
    """Read discovered slugs from disk, ignoring the cache if too old."""
    if not DISCOVERY_FILE.exists():
        return []
    try:
        payload = json.loads(DISCOVERY_FILE.read_text())
    except (ValueError, json.JSONDecodeError):
        return []
    refreshed = payload.get("refreshed_ts")
    if refreshed:
        try:
            ts = datetime.fromisoformat(refreshed.replace("Z", "+00:00"))
            age = (datetime.now(timezone.utc) - ts).total_seconds()
            if age > max_age_sec:
                return []
        except ValueError:
            pass
    return [s for s in payload.get("slugs") or [] if SLUG_RE.match(s)]


def _market_yes_price(market: dict) -> float | None:
    """Parse the YES outcome price out of a Gamma market dict."""
    prices_raw = market.get("outcomePrices")
    if isinstance(prices_raw, str):
        try:
            arr = json.loads(prices_raw)
        except (ValueError, json.JSONDecodeError):
            return None
        if isinstance(arr, list) and arr:
            return _to_float(arr[0])
    return None


def _is_resolved(market: dict, now_iso: str) -> bool:
    """Treat a sub-market as resolved (and skip it) when:
      - Polymarket has set ``closed=True``, OR
      - its ``endDate`` is past AND the YES price is pinned at 0/1 (admin
        hasn't formally closed it yet but the outcome is settled).
    """
    if market.get("closed"):
        return True
    end = market.get("endDate")
    if not end or end >= now_iso:
        return False
    yes = _market_yes_price(market)
    return yes is not None and (yes <= 0.005 or yes >= 0.995)


def classify_slug(http: HTTPClient, slug: str, now_iso: str) -> tuple[str, str]:
    """Hit Gamma to determine the live status of a manual-watchlist slug.

    Returns (status, detail) where status is one of:
      LIVE     — at least one sub-market still trading
      DEAD     — event present but every sub-market is _is_resolved()
      MISSING  — Gamma returns no event for this slug (likely renamed/removed)
      ERROR    — API call raised; conservative — leave the slug alone

    Uses ``closed=false`` to be lenient (zombie sub-markets that Polymarket
    hasn't formally closed but are pinned past their endDate still come back
    via this filter and get caught by _is_resolved).
    """
    try:
        resp = http.get_json("/events", params={"slug": slug, "closed": "false"})
    except Exception as e:
        return "ERROR", f"{type(e).__name__}: {e}"
    if isinstance(resp, dict) and "data" in resp:
        resp = resp["data"]
    events = resp if isinstance(resp, list) else []
    if not events:
        return "MISSING", "event not found"
    # Take the first matching event (Gamma's slug is unique).
    ev = events[0]
    markets = ev.get("markets") or []
    if not isinstance(markets, list) or not markets:
        return "DEAD", "0 sub-markets"
    n_live = sum(1 for m in markets if not _is_resolved(m, now_iso))
    if n_live == 0:
        return "DEAD", f"{len(markets)} sub-markets, 0 live"
    return "LIVE", f"{len(markets)} sub-markets, {n_live} live"


def upsert_watchlist(conn: sqlite3.Connection, active_slugs: list[str], poll_ts: str) -> None:
    cur = conn.cursor()
    if active_slugs:
        placeholders = ",".join("?" for _ in active_slugs)
        cur.execute(
            f"UPDATE watchlist SET removed_ts = ? "
            f"WHERE removed_ts IS NULL AND slug NOT IN ({placeholders})",
            [poll_ts, *active_slugs],
        )
    else:
        cur.execute(
            "UPDATE watchlist SET removed_ts = ? WHERE removed_ts IS NULL",
            [poll_ts],
        )
    for slug in active_slugs:
        cur.execute(
            "INSERT INTO watchlist (slug, first_added_ts, last_seen_ts, removed_ts) "
            "VALUES (?, ?, NULL, NULL) "
            "ON CONFLICT(slug) DO UPDATE SET removed_ts = NULL",
            [slug, poll_ts],
        )
    conn.commit()


# ---------------------------------------------------------------------------
# Core poll
# ---------------------------------------------------------------------------

def resolve_slugs(*, include_discovered: bool = True) -> tuple[list[str], int, int]:
    """Union manual watchlist with auto-discovered slugs (manual wins on dedup).

    Returns (slugs, n_manual, n_discovered).
    """
    manual = active_slugs(load_watchlist(WATCHLIST_FILE))
    discovered: list[str] = []
    if include_discovered:
        discovered = load_discovered_slugs()
    seen = set(manual)
    out = list(manual)
    for s in discovered:
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out, len(manual), len(discovered)


def poll(conn: sqlite3.Connection, http: HTTPClient,
         *, include_discovered: bool = True) -> dict:
    """One full poll: read watchlist, hit Gamma, write rows. Returns summary."""
    poll_ts = datetime.now(timezone.utc).isoformat(timespec="microseconds")
    snapshot_ts = poll_ts

    slugs, n_manual, n_discovered = resolve_slugs(include_discovered=include_discovered)
    upsert_watchlist(conn, slugs, poll_ts)

    if not slugs:
        conn.execute(
            "INSERT INTO poll_log VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [poll_ts, 0, 0, 0, 0, 1, "watchlist empty", None],
        )
        conn.commit()
        return {"poll_ts": poll_ts, "slugs": 0, "events": 0,
                "markets_seen": 0, "rows": 0, "ok": True, "error": None,
                "msg": "watchlist empty"}

    chunk_errors: list[str] = []
    events: list[dict] = []
    for i in range(0, len(slugs), SLUG_CHUNK_SIZE):
        chunk = slugs[i:i + SLUG_CHUNK_SIZE]
        params = (
            [("slug", s) for s in chunk]
            + [("closed", "false"), ("limit", str(max(len(chunk) * 2, 100)))]
        )
        try:
            response = http.get_json("/events", params=params)
            if isinstance(response, dict) and "data" in response:
                response = response["data"]
            if isinstance(response, list):
                events.extend(response)
        except Exception as e:
            chunk_errors.append(f"chunk {i // SLUG_CHUNK_SIZE}: {e!r}")

    error: str | None = "; ".join(chunk_errors) if chunk_errors else None
    # Only persist the raw payload when something went wrong — otherwise the
    # column blows the DB out by megabytes per poll (~6MB × 96 polls/day).
    raw_response_text = json.dumps(events, default=str) if error and events else None

    n_markets_seen = 0
    n_resolved_skipped = 0
    dead_slugs: list[str] = []  # event slugs whose every sub-market is resolved
    rows: list[tuple] = []
    for ev in events:
        ev_id = ev.get("id")
        ev_slug = ev.get("slug")
        ev_title = ev.get("title")
        if ev_slug:
            conn.execute(
                "UPDATE watchlist SET event_id = ?, last_seen_ts = ? WHERE slug = ?",
                [ev_id, poll_ts, ev_slug],
            )
        markets = ev.get("markets") or []
        if not isinstance(markets, list):
            continue
        ev_live_count = 0
        for m in markets:
            n_markets_seen += 1
            if _is_resolved(m, snapshot_ts):
                n_resolved_skipped += 1
                continue
            cond_id = m.get("conditionId")
            if not cond_id:
                continue
            ev_live_count += 1
            yes_p = no_p = None
            prices_raw = m.get("outcomePrices")
            if isinstance(prices_raw, str):
                try:
                    arr = json.loads(prices_raw)
                    if isinstance(arr, list):
                        if len(arr) >= 1:
                            yes_p = _to_float(arr[0])
                        if len(arr) >= 2:
                            no_p = _to_float(arr[1])
                except (ValueError, json.JSONDecodeError):
                    pass
            best_bid = _to_float(m.get("bestBid"))
            best_ask = _to_float(m.get("bestAsk"))
            spread = (best_ask - best_bid) if (best_bid is not None and best_ask is not None) else None
            rows.append((
                snapshot_ts,
                cond_id,
                ev_id,
                ev_slug,
                ev_title,
                m.get("question"),
                yes_p,
                no_p,
                best_bid,
                best_ask,
                spread,
                _to_float(m.get("lastTradePrice")),
                _to_float(m.get("volumeNum") or m.get("volume")),
                _to_float(m.get("volume24hr")),
                _to_float(m.get("liquidityNum") or m.get("liquidity")),
                m.get("updatedAt"),
            ))
        if ev_slug and ev_live_count == 0:
            dead_slugs.append(ev_slug)

    n_rows_written = 0
    if rows:
        try:
            conn.executemany(
                """INSERT INTO market_observation (
                    snapshot_ts, condition_id, event_id, event_slug, event_title,
                    question, yes_price, no_price, best_bid, best_ask, spread,
                    last_trade_price, volume_total, volume_24h, liquidity, updated_at_src
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                rows,
            )
            n_rows_written = len(rows)
        except sqlite3.IntegrityError as e:
            error = (error + " " if error else "") + f"insert_collision={e!r}"

    conn.execute(
        "INSERT INTO poll_log VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [poll_ts, len(slugs), len(events), n_markets_seen, n_rows_written,
         1 if error is None else 0, error, raw_response_text],
    )
    conn.commit()
    return {
        "poll_ts": poll_ts,
        "slugs": len(slugs),
        "manual_slugs": n_manual,
        "discovered_slugs": n_discovered,
        "events": len(events),
        "markets_seen": n_markets_seen,
        "resolved_skipped": n_resolved_skipped,
        "dead_slugs": dead_slugs,
        "rows": n_rows_written,
        "ok": error is None,
        "error": error,
    }


# ---------------------------------------------------------------------------
# Daily maintenance
# ---------------------------------------------------------------------------

def purge_and_vacuum(conn: sqlite3.Connection) -> dict:
    cutoff = f"datetime('now', '-{RETENTION_DAYS} days')"
    size_before = DB_FILE.stat().st_size if DB_FILE.exists() else 0

    cur = conn.cursor()
    cur.execute(f"DELETE FROM market_observation WHERE snapshot_ts < {cutoff}")
    obs_deleted = cur.rowcount
    cur.execute(f"DELETE FROM poll_log WHERE poll_ts < {cutoff}")
    poll_deleted = cur.rowcount
    # Strip raw_response_json from kept success rows — the payload is only
    # diagnostic-useful for failed polls, and persisting it on every poll is
    # what bloated the DB to 18 GB. Idempotent and cheap on already-clean rows.
    cur.execute(
        "UPDATE poll_log SET raw_response_json = NULL "
        "WHERE http_ok = 1 AND raw_response_json IS NOT NULL"
    )
    raw_json_cleared = cur.rowcount
    cur.execute(
        f"UPDATE watchlist SET removed_ts = ? "
        f"WHERE removed_ts IS NULL AND last_seen_ts IS NOT NULL "
        f"AND last_seen_ts < {cutoff}",
        [datetime.now(timezone.utc).isoformat(timespec="microseconds")],
    )
    auto_removed = cur.rowcount
    conn.commit()

    conn.execute("VACUUM")

    size_after = DB_FILE.stat().st_size if DB_FILE.exists() else 0
    cur.execute("SELECT COUNT(*) FROM market_observation")
    obs_remaining = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM watchlist WHERE removed_ts IS NULL")
    active_slugs = cur.fetchone()[0]
    cur.execute("SELECT MIN(snapshot_ts), MAX(snapshot_ts) FROM market_observation")
    obs_min, obs_max = cur.fetchone()

    return {
        "retention_days": RETENTION_DAYS,
        "deleted_observations": obs_deleted,
        "deleted_poll_log": poll_deleted,
        "raw_json_cleared": raw_json_cleared,
        "watchlist_auto_removed": auto_removed,
        "size_before_bytes": size_before,
        "size_after_bytes": size_after,
        "remaining_observations": obs_remaining,
        "active_slugs": active_slugs,
        "oldest_observation": obs_min,
        "newest_observation": obs_max,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _print_poll(res: dict) -> None:
    if not res["ok"]:
        print(f"poll {res['poll_ts']} FAILED: {res.get('error')}")
        return
    if "msg" in res:
        print(f"poll {res['poll_ts']}  ({res['msg']})")
        return
    print(f"poll {res['poll_ts']}")
    print(f"  slugs={res['slugs']}  events={res['events']}  "
          f"markets_seen={res['markets_seen']}  rows={res['rows']}")


def _print_cleanup(res: dict) -> None:
    print(f"polymarket cleanup — retention={res['retention_days']}d")
    print(f"  observations deleted:        {res['deleted_observations']:,}")
    print(f"  poll_log entries deleted:    {res['deleted_poll_log']:,}")
    print(f"  raw_response_json cleared:   {res['raw_json_cleared']:,}")
    print(f"  watchlist slugs auto-removed: {res['watchlist_auto_removed']}")
    print(f"  active slugs (still tracked): {res['active_slugs']}")
    print(f"  observations remaining:      {res['remaining_observations']:,}")
    if res["oldest_observation"]:
        print(f"  oldest observation:          {res['oldest_observation']}")
        print(f"  newest observation:          {res['newest_observation']}")
    print(f"  db size: {res['size_before_bytes']/1024:.1f} KB → "
          f"{res['size_after_bytes']/1024:.1f} KB")


def cmd_poll(_args: argparse.Namespace) -> None:
    with HTTPClient(base_url=GAMMA_BASE, timeout=30) as http:
        conn = open_db()
        try:
            _print_poll(poll(conn, http))
        finally:
            conn.close()


def cmd_discover(args: argparse.Namespace) -> None:
    with HTTPClient(base_url=GAMMA_BASE, timeout=30) as http:
        payload = discover_macro_slugs(http, min_volume=args.min_volume)
    print(f"[discover] refreshed_ts={payload['refreshed_ts']}")
    print(f"  tags matched:   {len(payload['tags_matched'])}")
    print(f"  slugs found:    {len(payload['slugs'])}  (min_vol=${args.min_volume:,.0f})")
    print(f"  cache file:     {DISCOVERY_FILE}")
    if payload["events"]:
        print("  top 10 by volume24h:")
        for e in payload["events"][:10]:
            print(f"    ${e['volume24h']:>12,.0f}  [{e['tag']:<20s}]  {e['slug']}")


def _poll_with_lock_retry(conn: sqlite3.Connection, http: HTTPClient,
                          include_discovered: bool,
                          max_attempts: int = 5,
                          base_backoff_sec: float = 2.0) -> dict:
    """Run poll() with bounded retry on ``database is locked``.

    The cleanup VACUUM holds an exclusive lock for the duration of its run.
    On an 18GB DB that's tens of minutes — a single 2s busy_timeout is not
    enough. Exponential backoff (2s, 4s, 8s, 16s, 32s ≈ 62s total) lets the
    loop ride out a normal cleanup invocation without dying.
    """
    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return poll(conn, http, include_discovered=include_discovered)
        except sqlite3.OperationalError as e:
            if "locked" not in str(e).lower():
                raise
            last_exc = e
            if attempt == max_attempts:
                break
            wait = base_backoff_sec * (2 ** (attempt - 1))
            print(f"[warn] db locked (attempt {attempt}/{max_attempts}); "
                  f"retrying in {wait:.0f}s")
            time.sleep(wait)
    raise last_exc  # type: ignore[misc]


def cmd_loop(args: argparse.Namespace) -> None:
    interval = max(INTERVAL_MIN_SEC, min(INTERVAL_MAX_SEC, args.interval))
    use_discovery = not args.no_discover
    print(f"[loop] interval={interval}s  db={DB_FILE}")
    print(f"[loop] watchlist={WATCHLIST_FILE}")
    print(f"[loop] discovery={'on' if use_discovery else 'off'}  "
          f"refresh_every={DISCOVERY_REFRESH_SEC}s")
    print(f"[loop] Ctrl+C to stop.\n")
    n_polls = 0
    last_discovery = 0.0
    warned_dead: set[str] = set()
    with HTTPClient(base_url=GAMMA_BASE, timeout=30) as http:
        conn = open_db()
        try:
            while True:
                t0 = time.monotonic()
                # Auto-refresh discovery cache periodically (in-process)
                if use_discovery and (t0 - last_discovery) > DISCOVERY_REFRESH_SEC:
                    try:
                        d = discover_macro_slugs(http)
                        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
                        print(f"[{ts}] discovery refresh — "
                              f"tags={len(d['tags_matched'])} "
                              f"slugs={len(d['slugs'])}")
                        last_discovery = t0
                    except Exception as e:
                        print(f"[error] discovery refresh failed: {e!r}")
                try:
                    res = _poll_with_lock_retry(conn, http, use_discovery)
                    n_polls += 1
                    dur_ms = int((time.monotonic() - t0) * 1000)
                    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
                    line = (f"[{ts}] poll #{n_polls:>4} — "
                            f"slugs={res['slugs']:>3} "
                            f"(manual={res['manual_slugs']} "
                            f"auto={res['discovered_slugs']}) "
                            f"events={res['events']:>3} "
                            f"rows={res['rows']:>4} "
                            f"zombie_skip={res.get('resolved_skipped', 0)} "
                            f"dur={dur_ms:>4}ms")
                    if not res["ok"]:
                        line += f"  ERR={res['error']}"
                    print(line)
                    manual_slug_set = (set(active_slugs(load_watchlist(WATCHLIST_FILE)))
                                       if WATCHLIST_FILE.exists() else set())
                    new_dead = [s for s in res.get("dead_slugs", []) if s not in warned_dead]
                    for s in new_dead:
                        warned_dead.add(s)
                        # Manual watchlist is curated by hand — keep dead slugs
                        # silent so the user isn't nagged to remove them.
                        if s in manual_slug_set:
                            continue
                        print(f"  [warn] auto-discovered event has no live sub-markets — "
                              f"will drop on next discovery refresh: {s}")
                    if n_polls % HEARTBEAT_EVERY_N == 0:
                        cur = conn.cursor()
                        cur.execute("SELECT COUNT(*) FROM market_observation")
                        total = cur.fetchone()[0]
                        cur.execute("SELECT COUNT(*) FROM watchlist WHERE removed_ts IS NULL")
                        active = cur.fetchone()[0]
                        print(f"[heartbeat] total_observations={total:,}  "
                              f"active_slugs={active}")
                except Exception as e:
                    print(f"[error] poll iteration failed: {e!r}")
                sleep_for = interval - (time.monotonic() - t0)
                if sleep_for > 0:
                    time.sleep(sleep_for)
        except KeyboardInterrupt:
            print(f"\n[loop] stopped after {n_polls} polls.")
        finally:
            conn.close()


def cmd_cleanup(_args: argparse.Namespace) -> None:
    conn = open_db()
    try:
        _print_cleanup(purge_and_vacuum(conn))
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Prune (manual-watchlist audit + comment-out)
# ---------------------------------------------------------------------------

def cmd_prune(args: argparse.Namespace) -> None:
    """Audit the manual watchlist against live Polymarket state.

    Default = dry-run; ``--apply`` mutates ``watchlist.yml`` (with .bak),
    flipping ``pruned: true`` on dead/missing entries.
    Never touches ``auto_discovered.json``.
    """
    if not WATCHLIST_FILE.exists():
        print(f"[prune] no watchlist file at {WATCHLIST_FILE}")
        return

    entries = load_watchlist(WATCHLIST_FILE)
    slugs = active_slugs(entries)
    if not slugs:
        print("[prune] watchlist is empty — nothing to do.")
        return

    asset_tags = asset_tag_map(entries)

    today = datetime.now(timezone.utc).date()
    now_iso = datetime.now(timezone.utc).isoformat()

    print(f"# slug status report  (today={today.isoformat()}, manual_slugs={len(slugs)})")
    counts = {"LIVE": 0, "DEAD": 0, "MISSING": 0, "ERROR": 0}
    prune_map: dict[str, str] = {}

    with HTTPClient(base_url=GAMMA_BASE, timeout=30) as http:
        for slug in slugs:
            status, detail = classify_slug(http, slug, now_iso)
            counts[status] = counts.get(status, 0) + 1
            tag = asset_tags.get(slug, "uncurated")
            print(f"{status:<7} [{tag:<20s}]  {slug:<60s}  ({detail})")
            if status in ("DEAD", "MISSING"):
                prune_map[slug] = status
            elif status == "ERROR" and args.include_error:
                prune_map[slug] = status

    print()
    print(f"summary: {counts['LIVE']} LIVE, {counts['DEAD']} DEAD, "
          f"{counts['MISSING']} MISSING, {counts['ERROR']} ERROR")

    if not prune_map:
        print("plan:    nothing to prune.")
        return

    if not args.apply:
        print(f"plan:    would mark {len(prune_map)} entries pruned "
              f"(dry-run; pass --apply to write)")
        return

    bak = WATCHLIST_FILE.with_name(WATCHLIST_FILE.name + ".bak")
    n_pruned = mark_pruned(WATCHLIST_FILE, prune_map, today)
    print(f"backed up {WATCHLIST_FILE} -> {bak}")
    print(f"wrote {WATCHLIST_FILE} — flipped pruned=true on {n_pruned} entries")


def main() -> None:
    p = argparse.ArgumentParser(prog="polymarket_streaming")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("poll", help="One-shot single poll")
    pl = sub.add_parser("loop", help="Continuous polling daemon")
    pl.add_argument(
        "--interval", type=int, default=DEFAULT_INTERVAL_SEC,
        help=f"Seconds between polls (default {DEFAULT_INTERVAL_SEC}, "
             f"clamped to [{INTERVAL_MIN_SEC},{INTERVAL_MAX_SEC}])",
    )
    pl.add_argument(
        "--no-discover", action="store_true",
        help="Skip macro tag-driven auto-discovery; use only manual watchlist.yml",
    )
    pd = sub.add_parser("discover",
                        help="One-shot refresh of auto_discovered.json from Gamma /tags")
    pd.add_argument("--min-volume", type=float, default=DISCOVERY_MIN_VOLUME,
                    help=f"Min 24h volume to include (default ${DISCOVERY_MIN_VOLUME:,.0f})")
    sub.add_parser("cleanup", help=f"Weekly maintenance: purge >{RETENTION_DAYS}d, VACUUM, summary")
    pp = sub.add_parser("prune",
                        help="Audit manual watchlist; comment out DEAD/MISSING slugs (with .bak)")
    pp.add_argument("--apply", action="store_true",
                    help="Actually rewrite watchlist.yml (default is dry-run)")
    pp.add_argument("--include-error", action="store_true",
                    help="Also comment out slugs that errored (default keeps them)")
    args = p.parse_args()
    {
        "poll":     cmd_poll,
        "loop":     cmd_loop,
        "discover": cmd_discover,
        "cleanup":  cmd_cleanup,
        "prune":    cmd_prune,
    }[args.cmd](args)


if __name__ == "__main__":
    main()
