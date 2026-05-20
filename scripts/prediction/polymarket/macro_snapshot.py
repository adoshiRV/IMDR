"""Macro snapshot — combined Polymarket consensus report.

Reads ``C:\\IMDR_LOCAL\\polymarket\\observations.db`` and renders a single
HTML file showing the desk's curated macro / event-driven cross-section at the
latest snapshot timestamp: geopolitics, US data + Fed, G10 central banks, and
an Asia overlay (BoJ / BoK / RBA / RBNZ / China-Korea-Japan data).

Output: ``C:\\IMDR_LOCAL\\polymarket\\snapshots\\macro_snapshot_<YYYYMMDD>_<HHMM>.html``

Run:
    python -m scripts.prediction.polymarket.macro_snapshot

The curated event set lives in ``watchlist.yml`` (shared with the streaming
poller and polywatch). Entries with ``section`` + ``label`` + ``asset`` set
render here; bare polling-only entries don't. Edit the YAML to add/remove
rows; everything else (consensus %, tail buckets, Δ24h, volume, link) is
computed from the latest snapshot in the SQLite DB.

See docs/prediction/macro_snapshot.md for the spec.
"""
from __future__ import annotations

import argparse
import calendar
import html
import re
import sqlite3
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from scripts.prediction.polymarket.watchlist import (
    WatchlistEntry,
    load_watchlist,
    snapshot_entries,
)

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


POLY_DIR = Path(r"C:\IMDR_LOCAL\polymarket")
DB_FILE = POLY_DIR / "observations.db"
OUT_DIR = POLY_DIR / "snapshots"

POLYMARKET_EVENT_URL = "https://polymarket.com/event/{slug}"


# ``event_date`` on a watchlist entry is the underlying release/decision date.
# Used to decide whether the row is upcoming (normal section), recently
# resolved (quarantined for RECENT_RESOLVED_DAYS), or stale (dropped).
# Lookup priority: event_id first; then slug (exact match, or prefix when it
# ends with '*' — useful for events Polymarket hasn't posted yet).

RECENT_RESOLVED_DAYS = 5
RECENTLY_RESOLVED_SECTION = "Recently Resolved"

# Horizon-mismatch threshold: if the chosen sub-market's date is more than this
# many days from the watchlist event_date, surface a warning subnote.
HORIZON_MATCH_TOLERANCE_DAYS = 14


# ---------------------------------------------------------------------------
# Question-date parser — extracts a horizon date from a sub-market question.
# ---------------------------------------------------------------------------
# Used to disambiguate horizon-laddered events. Example: an "Iran peace deal
# by..." event groups May-15 / May-31 / Jun-30 / Dec-31 sub-markets. By
# default we'd pick the highest-yes_price (always Dec-31) as modal — wrong
# when the watchlist row is labeled "Jun 30". Instead, score sub-markets by
# how close their parsed date is to the watchlist event_date.
#
# Returns None when no recognizable date phrase is found — callers fall back
# to the legacy highest-yes_price behavior in that case.

_MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10,
    "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}
_MONTH_RE = (r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
             r"jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|"
             r"nov(?:ember)?|dec(?:ember)?")

# "by Month Day(, Year)?" / "Month Day(, Year)?" / "on Month Day(, Year)?"
_DATE_RE = re.compile(
    rf"\b(?:by|on|before)?\s*({_MONTH_RE})\.?\s+(\d{{1,2}})(?:,?\s+(\d{{4}}))?\b",
    re.I,
)
# "end of {month}" or "end-{month}"
_END_OF_MONTH_RE = re.compile(rf"end[\s-]of[\s-]({_MONTH_RE})", re.I)
# "by end of YYYY" / "before YYYY" / "by YYYY"
_END_OF_YEAR_RE = re.compile(r"\b(?:by\s+end\s+of|before|by)\s+(\d{4})\b", re.I)
# "in YYYY" — matched last so explicit dates win.
_IN_YEAR_RE = re.compile(r"\bin\s+(\d{4})\b", re.I)
# "in QN YYYY" / "QN YYYY" — quarter-end.
_QUARTER_RE = re.compile(r"\bQ([1-4])\s+(\d{4})\b", re.I)
# Central-bank meeting reference: "after the {Month} {Year}? meeting/decision".
_MEETING_RE = re.compile(
    rf"\b(?:after\s+the\s+)?({_MONTH_RE})(?:\s+(\d{{4}}))?\s+(?:meeting|decision|fomc|interest\s+rate\s+(?:announcement|decision))",
    re.I,
)


def _last_day_of_month(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def extract_question_date(question: str, default_year: int) -> date | None:
    """Best-effort parse of a horizon date from a sub-market question.

    ``default_year`` is used when the phrasing omits a year ("by June 30");
    pass the watchlist event_date's year so phrasing implicitly means the
    same year as the row.
    """
    if not question:
        return None

    # Quarter ("Q2 2026") — common in GDP markets.
    m = _QUARTER_RE.search(question)
    if m:
        q = int(m.group(1))
        year = int(m.group(2))
        end_month = q * 3
        return _safe_date(year, end_month, _last_day_of_month(year, end_month))

    # End-of-{month}.
    m = _END_OF_MONTH_RE.search(question)
    if m:
        month = _MONTHS[m.group(1).lower()]
        # Year not given by this phrasing; assume default_year.
        return _safe_date(default_year, month, _last_day_of_month(default_year, month))

    # "by end of YYYY" / "before YYYY" / "by YYYY" — year-boundary.
    m = _END_OF_YEAR_RE.search(question)
    if m:
        year = int(m.group(1))
        # "before 2027" semantically means "by end of 2026".
        if "before" in (m.group(0) or "").lower():
            year -= 1
        return _safe_date(year, 12, 31)

    # Explicit Month Day (with or without year). Prefer the FIRST occurrence
    # so prefixes like "by June 30" win over trailing "in 2026" framing.
    m = _DATE_RE.search(question)
    if m:
        month = _MONTHS[m.group(1).lower()]
        day = int(m.group(2))
        year = int(m.group(3)) if m.group(3) else default_year
        return _safe_date(year, month, day)

    # Central-bank meeting reference — anchor to mid-month (15th).
    m = _MEETING_RE.search(question)
    if m:
        month = _MONTHS[m.group(1).lower()]
        year = int(m.group(2)) if m.group(2) else default_year
        return _safe_date(year, month, 15)

    # "in YYYY" (no month) → year-end.
    m = _IN_YEAR_RE.search(question)
    if m:
        return _safe_date(int(m.group(1)), 12, 31)

    return None


def _pick_modal(sub_rows: list, target_date: date | None) -> tuple[int, date | None]:
    """Choose which sub-market is the headline.

    Returns (index_into_sub_rows, parsed_date_for_chosen_row).

    Strategy:
      1. If target_date is None → highest yes_price wins (legacy behavior).
      2. Else parse a date from each sub-market's question. If at least one
         parses, pick the row whose parsed date is closest to target_date,
         breaking ties by highest yes_price.
      3. If no rows parse a date, fall back to highest yes_price.

    Caller is expected to pass ``sub_rows`` already sorted by yes_price desc
    so ties resolve naturally to the higher-probability row.
    """
    if not sub_rows:
        return -1, None
    if target_date is None:
        return 0, None

    default_year = target_date.year
    parsed: list[tuple[int, date | None]] = [
        (i, extract_question_date(r["question"] or "", default_year))
        for i, r in enumerate(sub_rows)
    ]
    dated = [(i, d) for i, d in parsed if d is not None]
    if not dated:
        return 0, None

    best_i, best_d = min(
        dated,
        key=lambda pair: (abs((pair[1] - target_date).days),
                          -float(sub_rows[pair[0]]["yes_price"] or 0)),
    )
    return best_i, best_d


# ---------------------------------------------------------------------------
# Data extraction
# ---------------------------------------------------------------------------

def _resolve_event_id(conn: sqlite3.Connection, ev: WatchlistEntry,
                      latest_ts: str) -> int | None:
    if ev.event_id is not None:
        return ev.event_id
    if not ev.slug:
        return None
    if ev.slug.endswith("*"):
        # Prefix match — useful for events Polymarket hasn't posted yet
        # (e.g. "how-many-jobs-added-in-may-*" auto-binds when May NFP goes live).
        pattern = ev.slug[:-1] + "%"
        row = conn.execute(
            "SELECT event_id FROM market_observation WHERE event_slug LIKE ? AND snapshot_ts=? LIMIT 1",
            [pattern, latest_ts],
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT event_id FROM market_observation WHERE event_slug=? AND snapshot_ts=? LIMIT 1",
            [ev.slug, latest_ts],
        ).fetchone()
    return row[0] if row else None


def _classify_event(event_date: date | None, today: date) -> tuple[str | None, bool]:
    """Decide what section bucket a watchlist row belongs in.

    Returns (section_override, include). section_override=None keeps the row's
    original section; include=False drops the row entirely (past quarantine).
    """
    if event_date is None:
        return None, True  # open-ended — always show
    if event_date >= today:
        return None, True  # upcoming — normal section
    if (today - event_date).days <= RECENT_RESOLVED_DAYS:
        return RECENTLY_RESOLVED_SECTION, True  # quarantined for context
    return None, False  # stale — drop


def _prior_yes(conn: sqlite3.Connection, condition_id: str, not_after_ts: str) -> float | None:
    pr = conn.execute(
        """SELECT yes_price FROM market_observation
           WHERE condition_id=? AND snapshot_ts<=?
           ORDER BY snapshot_ts DESC LIMIT 1""",
        [condition_id, not_after_ts],
    ).fetchone()
    return pr["yes_price"] if pr is not None else None


def _vol_baseline_7d(conn: sqlite3.Connection, condition_id: str,
                     not_after_ts: str) -> float | None:
    """Median 24h volume over trailing 7d on the modal condition.

    Mirrors polywatch.vol_baseline_24h — median, not mean, so a single burst
    day doesn't inflate the baseline.
    """
    not_after_dt = datetime.fromisoformat(not_after_ts.replace("Z", "+00:00"))
    start = (not_after_dt - timedelta(days=7)).isoformat(timespec="microseconds")
    rows = conn.execute(
        """SELECT volume_24h FROM market_observation
           WHERE condition_id=? AND snapshot_ts BETWEEN ? AND ?
             AND volume_24h IS NOT NULL""",
        [condition_id, start, not_after_ts],
    ).fetchall()
    vals = sorted(float(r[0]) for r in rows if r[0] is not None and float(r[0]) > 0)
    if not vals:
        return None
    n = len(vals)
    return vals[n // 2] if n % 2 == 1 else 0.5 * (vals[n // 2 - 1] + vals[n // 2])


def _event_data(conn: sqlite3.Connection, event_id: int, latest_ts: str,
                six_hours_ago_ts: str, day_ago_ts: str, week_ago_ts: str,
                target_date: date | None) -> dict | None:
    """Pull modal + tail + Δ6h/Δ24h/Δ7d + decisiveness gap + vol-burst ratio.

    ``target_date`` is the watchlist row's event_date. When provided, the
    "modal" sub-market is the one whose question-date is closest to it (so a
    "Jun 30" row no longer reports the Dec 31 sub-market's price). Falls back
    to highest-yes_price when no sub-market's question parses to a date.
    """
    sub = conn.execute(
        """SELECT condition_id, question, yes_price, volume_24h, spread
           FROM market_observation WHERE event_id=? AND snapshot_ts=?
           ORDER BY yes_price DESC""",
        [event_id, latest_ts],
    ).fetchall()
    if not sub:
        return None
    sub = [s for s in sub if s["yes_price"] is not None]
    if not sub:
        return None

    modal_idx, modal_qdate = _pick_modal(sub, target_date)
    modal = sub[modal_idx]

    # Horizon mismatch warning surfaces in the rendered row when the chosen
    # sub-market's date isn't close to the row's event_date — gives the
    # reader explicit signal that no exact-match sub-market existed.
    horizon_mismatch_days: int | None = None
    if target_date is not None and modal_qdate is not None:
        diff = abs((modal_qdate - target_date).days)
        if diff > HORIZON_MATCH_TOLERANCE_DAYS:
            horizon_mismatch_days = diff

    # Per-sub-market metrics: tail buckets render as sub-rows so the reader
    # sees every meaningful outcome with its own % and Δs.
    def _row_metrics(s) -> dict:
        cid = s["condition_id"]
        yes = float(s["yes_price"]) if s["yes_price"] is not None else None
        p6 = _prior_yes(conn, cid, six_hours_ago_ts)
        p24 = _prior_yes(conn, cid, day_ago_ts)
        p7 = _prior_yes(conn, cid, week_ago_ts)
        return {
            "q": s["question"],
            "yes": yes,
            "prior_6h": p6, "prior_24h": p24,
            "delta_6h": (yes - p6) if (yes is not None and p6 is not None) else None,
            "delta_24h": (yes - p24) if (yes is not None and p24 is not None) else None,
            "delta_7d": (yes - p7) if (yes is not None and p7 is not None) else None,
            "vol_24h": float(s["volume_24h"] or 0),
        }

    others = [s for i, s in enumerate(sub) if i != modal_idx]
    # Show up to 5 tail rows (>=2% yes) to avoid swamping events with
    # long-tail sub-markets like 12-bucket NFP or 18-party Russian elections.
    tail = [_row_metrics(s) for s in others[:5] if (s["yes_price"] or 0) >= 0.02]

    # Decisiveness gap: how far the modal leads the next-strongest sub-market.
    gap: float | None = None
    if others and others[0]["yes_price"] is not None:
        gap = float(modal["yes_price"]) - float(others[0]["yes_price"])

    cid = modal["condition_id"]
    prior_6h = _prior_yes(conn, cid, six_hours_ago_ts)
    prior_24h = _prior_yes(conn, cid, day_ago_ts)
    prior_7d = _prior_yes(conn, cid, week_ago_ts)
    delta_6h = (modal["yes_price"] - prior_6h) if prior_6h is not None else None
    delta_24h = (modal["yes_price"] - prior_24h) if prior_24h is not None else None
    delta_7d = (modal["yes_price"] - prior_7d) if prior_7d is not None else None

    vol_24h = float(modal["volume_24h"]) if modal["volume_24h"] is not None else 0.0
    vol_base_7d = _vol_baseline_7d(conn, cid, latest_ts)
    vol_ratio = (vol_24h / vol_base_7d) if (vol_base_7d and vol_base_7d > 0) else None

    total_vol = sum(float(s["volume_24h"] or 0) for s in sub)

    meta = conn.execute(
        """SELECT event_slug, event_title FROM market_observation
           WHERE event_id=? AND snapshot_ts=? LIMIT 1""",
        [event_id, latest_ts],
    ).fetchone()

    return {
        "modal_q": modal["question"],
        "modal_qdate": modal_qdate.isoformat() if modal_qdate else None,
        "horizon_mismatch_days": horizon_mismatch_days,
        "yes": float(modal["yes_price"]),
        "tail": tail,
        "gap": gap,
        "prior_6h": prior_6h,
        "prior_24h": prior_24h,
        "delta_6h": delta_6h,
        "delta_24h": delta_24h,
        "delta_7d": delta_7d,
        "vol_24h": total_vol,
        "vol_ratio": vol_ratio,
        "event_slug": meta["event_slug"] if meta else "",
        "event_title": meta["event_title"] if meta else "",
    }


# ---------------------------------------------------------------------------
# HTML rendering
# ---------------------------------------------------------------------------

CSS = """
body { font: 13px/1.45 -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
       color:#222; max-width:1280px; margin:24px auto; padding:0 16px; }
h1 { font-size:20px; margin:0 0 4px; }
h2 { font-size:14px; margin:18px 0 6px; padding:4px 8px; background:#f3f4f6;
     border-left:3px solid #555; color:#222; }
.meta { color:#666; font-size:12px; margin-bottom:14px; }
table { border-collapse:collapse; width:100%; font-size:12.5px; }
th, td { border-bottom:1px solid #eee; padding:6px 8px; text-align:left;
         vertical-align:top; }
th { background:#fafafa; font-weight:600; color:#444; position:sticky;
     top:0; z-index:1; }
td.num { text-align:right; font-variant-numeric:tabular-nums; }
.consensus { font-weight:700; color:#1f4ed8; }
.delta-up { color:#0a7c2c; font-weight:600; }
.delta-down { color:#b1331a; font-weight:600; }
.delta-flat { color:#777; }
.tail { color:#666; font-size:11.5px; }
.subnote { color:#888; font-size:11px; display:block; }
.outcome-q { color:#222; font-size:12px; margin-top:2px; }
.outcome-name { color:#222; font-weight:600; }
.outcome-pct { color:#1f4ed8; font-weight:700; }
tr.headline > td { border-top:2px solid #ddd; }
tr.headline:first-child > td { border-top:none; }
tr.subrow > td { border-top:none; padding-top:3px; padding-bottom:3px;
                 background:#fafafa; color:#555; font-size:12px; }
tr.subrow .outcome-name.subrow-name { font-weight:500; color:#444; }
tr.subrow td.num { color:#555; }
.horizon-ok { color:#0a7c2c; font-size:10.5px; }
.horizon-warn { background:#fff1d6; color:#a65a00; padding:1px 5px;
                border-radius:3px; font-size:10.5px; font-weight:600;
                display:inline-block; margin-top:2px; }
.event-date { color:#1f4ed8; font-weight:600; font-size:11px; }
.gap-tight { color:#b1331a; font-weight:600; }   /* coin-flip / two-way */
.gap-loose { color:#0a7c2c; font-weight:600; }   /* entrenched */
.burst-hot { background:#fff1d6; color:#a65a00; padding:0 4px;
             border-radius:3px; font-size:10.5px; font-weight:600; }
.burst-cold { background:#eee; color:#888; padding:0 4px;
              border-radius:3px; font-size:10.5px; }
.read { color:#222; }
.asset { background:#eef2ff; color:#1f4ed8; padding:1px 6px;
         border-radius:3px; font-size:11px; font-weight:600; white-space:nowrap; }
a { color:#1f4ed8; text-decoration:none; }
a:hover { text-decoration:underline; }
.section-banner { font-weight:700; color:#444; }
.foot { color:#888; font-size:11.5px; margin-top:18px; border-top:1px solid #eee;
        padding-top:8px; }
.na { color:#aaa; }
"""


def _fmt_pct(x: float | None) -> str:
    if x is None:
        return '<span class="na">n/a</span>'
    return f"{x * 100:.1f}%"


def _fmt_delta(d: float | None, prior: float | None = None) -> str:
    """Format Δ in pp; append relative %-change as a subnote when prior is in
    the tail (<20% or >80%) — that's the only regime where pp underplays the move.
    """
    if d is None:
        return '<span class="na">n/a</span>'
    pp = d * 100
    cls = "delta-up" if pp > 0.05 else "delta-down" if pp < -0.05 else "delta-flat"
    sign = "+" if pp >= 0 else ""
    main = f'<span class="{cls}">{sign}{pp:.1f}pp</span>'
    if prior is not None and abs(d) >= 0.005 and prior > 0 and (prior < 0.20 or prior > 0.80):
        rel = (d / prior) * 100
        rel_sign = "+" if rel >= 0 else ""
        main += f'<span class="subnote">{rel_sign}{rel:.0f}% rel</span>'
    return main


def _fmt_gap(gap: float | None) -> str:
    if gap is None:
        return ""
    pp = gap * 100
    if pp < 0:
        # Horizon-aware modal selection picked a sub-market that isn't the
        # highest-Yes alternative. The "gap" is now distance BELOW the leader
        # — relevant info, but not a coin-flip signal. Show explicitly.
        return (f'<span class="subnote">'
                f'<span class="gap-tight">{pp:+.1f}pp vs leading horizon</span>'
                f'</span>')
    if pp <= 5:
        cls = "gap-tight"
        label = f"gap +{pp:.1f}pp · two-way"
    elif pp >= 30:
        cls = "gap-loose"
        label = f"gap +{pp:.1f}pp"
    else:
        cls = ""
        label = f"gap +{pp:.1f}pp"
    klass = f' class="{cls}"' if cls else ""
    return f'<span class="subnote"><span{klass}>{label}</span></span>'


def _fmt_burst(ratio: float | None) -> str:
    if ratio is None:
        return ""
    if ratio >= 1.5:
        return f'<span class="burst-hot">{ratio:.1f}× burst</span>'
    if ratio <= 0.5:
        return f'<span class="burst-cold">{ratio:.1f}× quiet</span>'
    return ""


def _fmt_vol(v: float | None) -> str:
    if v is None or v <= 0:
        return '<span class="na">—</span>'
    if v >= 1_000_000:
        return f"${v / 1_000_000:.2f}M"
    if v >= 1_000:
        return f"${v / 1_000:.0f}K"
    return f"${v:.0f}"


def _fmt_tail(tail: list[dict]) -> str:
    if not tail:
        return ""
    parts = []
    for t in tail:
        q = html.escape(_strip_tail_q(t["q"]))
        parts.append(f"{q}: {t['yes'] * 100:.1f}%")
    return '<div class="tail">' + " · ".join(parts) + "</div>"


def _strip_tail_q(q: str) -> str:
    """Compress a verbose sub-market question down to its distinguishing piece.

    Bucket markets (NFP, unemployment, CB hike/hold/cut) are unfortunately
    phrased verbosely on Polymarket — "Will the US add between 50k and 100k
    jobs in April?" — so we strip leading boilerplate and an inner phrase or
    two to surface the bucket label itself ("50k-100k jobs in April").
    """
    s = q.strip().rstrip("?")
    # Specific entity prefixes first — order matters; longest match wins.
    for prefix in (
        # Strip "add" but NOT "lose" — keep "lose" in the shortened form so
        # "0-50k jobs lost" doesn't collide with "0-50k jobs added".
        "Will the US add ",
        "Will the US ",
        "Will the Fed announce ",
        "Will the Fed increase ",
        "Will the Fed decrease ",
        "Will the Fed ",
        "Will the European Central Bank ",
        "Will the Bank of Canada ",
        "Will the Bank of Mexico ",
        "Will the Bank of Korea ",
        "Will the Bank of Japan ",
        "Will the Reserve Bank of Australia ",
        "Will the Reserve Bank of New Zealand ",
        "Will the ",
        "Will ",
        "No change in ",
        "Bank of England ",
        "Bank of Japan ",
        "Reserve Bank of Australia ",
        "Reserve Bank of New Zealand ",
        "Bank of Korea ",
        "Bank of Mexico ",
        "Bank of Canada ",
        "Bank of Israel ",
    ):
        if s.lower().startswith(prefix.lower()):
            s = s[len(prefix):]
            break
    # The "between X and Y" phrasing reads more naturally as a range.
    s = re.sub(r"\bbetween\s+([\w.]+)\s+and\s+([\w.]+)\b", r"\1–\2", s, flags=re.I)
    # Trim trailing meeting/decision boilerplate when the meeting month is
    # already implied by the row's target date.
    s = re.sub(r"\s+after\s+the\s+\w+\s+(?:\d{4}\s+)?(?:meeting|decision)$", "", s, flags=re.I)
    return s[:80]


SECTION_ORDER = (
    "Geopolitics / Oil",
    "US Data & Fed",
    "Europe / G10 CB",
    "Asia Overlay",
    "Tariffs / Trade",
    RECENTLY_RESOLVED_SECTION,
)

# Editorial banner shown above the Recently Resolved section. The point of
# the quarantine is to give the desk a few days' visibility into how the
# print actually moved the modal bucket — not to forecast.
SECTION_BANNERS = {
    RECENTLY_RESOLVED_SECTION:
        f"Underlying release/decision happened in the last {RECENT_RESOLVED_DAYS} "
        "days; rows here are backward-looking — Δ6h captures the resolution-day "
        "reaction. They drop off automatically once past the quarantine window.",
}


def render_html(rows: list[dict], snapshot_ts: str, generated_ts: str,
                missing: list[str], dropped_stale: list[str] | None = None) -> str:
    parts: list[str] = []
    parts.append("<!DOCTYPE html>")
    parts.append("<html><head><meta charset='utf-8'>")
    parts.append("<title>Macro Snapshot — Polymarket</title>")
    parts.append(f"<style>{CSS}</style></head><body>")
    parts.append("<h1>Polymarket Macro Snapshot</h1>")
    parts.append(
        f"<div class='meta'>"
        f"snapshot: <b>{html.escape(snapshot_ts)}</b> · "
        f"generated: {html.escape(generated_ts)} · "
        f"db: <code>C:\\IMDR_LOCAL\\polymarket\\observations.db</code>"
        f"</div>"
    )

    by_section: dict[str, list[dict]] = {}
    for r in rows:
        by_section.setdefault(r["section"], []).append(r)

    n = 0
    for section in SECTION_ORDER:
        section_rows = by_section.get(section, [])
        if not section_rows:
            continue
        parts.append(f"<h2>{html.escape(section)}</h2>")
        banner = SECTION_BANNERS.get(section)
        if banner:
            parts.append(f"<div class='meta'>{html.escape(banner)}</div>")
        parts.append("<table>")
        parts.append(
            "<thead><tr>"
            "<th>#</th><th>Asset</th><th>Event</th>"
            "<th>Outcome</th><th class='num'>Outcome %</th>"
            "<th class='num'>Δ6h</th><th class='num'>Δ24h</th><th class='num'>Δ7d</th>"
            "<th class='num'>Vol 24h</th>"
            "</tr></thead><tbody>"
        )
        for r in section_rows:
            n += 1
            link = (POLYMARKET_EVENT_URL.format(slug=r["event_slug"])
                    if r.get("event_slug") else None)
            label_html = html.escape(r["label"])
            if link:
                label_html = f'<a href="{html.escape(link)}" target="_blank">{label_html}</a>'

            # Event-date pill: "resolved YYYY-MM-DD" in the quarantine section,
            # otherwise the target horizon up front so the reader sees it.
            if r.get("event_date"):
                if section == RECENTLY_RESOLVED_SECTION:
                    date_pill = f"<div class='subnote'>resolved {html.escape(r['event_date'])}</div>"
                else:
                    date_pill = (f"<div class='subnote'>target "
                                 f"<span class='event-date'>{html.escape(r['event_date'])}</span></div>")
            else:
                date_pill = ""

            # Horizon-match annotation (warning or green confirmation).
            mismatch = r.get("horizon_mismatch_days")
            qdate = r.get("modal_qdate")
            horizon_note = ""
            if mismatch is not None:
                horizon_note = (
                    f"<div><span class='horizon-warn'>"
                    f"⚠ outcome shown is {html.escape(qdate or '?')} — "
                    f"{int(mismatch)}d off the target</span></div>"
                )
            elif qdate and r.get("event_date") and qdate != r.get("event_date"):
                horizon_note = (
                    f"<div><span class='horizon-ok'>matched on "
                    f"{html.escape(qdate)}</span></div>"
                )

            # ----- Headline row (matched / modal sub-market) -----
            short_q = _strip_tail_q(r.get("modal_q") or "")
            burst = _fmt_burst(r.get("vol_ratio"))
            burst_html = f"<span class='subnote'>{burst}</span>" if burst else ""

            parts.append("<tr class='headline'>")
            parts.append(f"<td class='num'>{n}</td>")
            parts.append(f"<td><span class='asset'>{html.escape(r['asset'])}</span></td>")
            parts.append(
                f"<td>{label_html}{date_pill}{horizon_note}</td>"
            )
            parts.append(f"<td class='outcome-name'>{html.escape(short_q)}</td>")
            parts.append(
                f"<td class='num'><span class='outcome-pct'>{_fmt_pct(r.get('yes'))}</span>"
                f"{_fmt_gap(r.get('gap'))}</td>"
            )
            parts.append(
                f"<td class='num'>{_fmt_delta(r.get('delta_6h'), r.get('prior_6h'))}</td>"
            )
            parts.append(
                f"<td class='num'>{_fmt_delta(r.get('delta_24h'), r.get('prior_24h'))}</td>"
            )
            parts.append(f"<td class='num'>{_fmt_delta(r.get('delta_7d'))}</td>")
            parts.append(
                f"<td class='num'>{_fmt_vol(r.get('vol_24h'))}{burst_html}</td>"
            )
            parts.append("</tr>")

            # ----- Tail rows: every other meaningful sub-market, with own
            # %, deltas, vol — so the reader sees the full distribution.
            for t in r.get("tail", []):
                t_short = _strip_tail_q(t.get("q") or "")
                parts.append("<tr class='subrow'>")
                parts.append("<td></td><td></td><td></td>")  # number, asset, event blanks
                parts.append(f"<td class='outcome-name subrow-name'>{html.escape(t_short)}</td>")
                parts.append(
                    f"<td class='num'>{_fmt_pct(t.get('yes'))}</td>"
                )
                parts.append(
                    f"<td class='num'>{_fmt_delta(t.get('delta_6h'), t.get('prior_6h'))}</td>"
                )
                parts.append(
                    f"<td class='num'>{_fmt_delta(t.get('delta_24h'), t.get('prior_24h'))}</td>"
                )
                parts.append(f"<td class='num'>{_fmt_delta(t.get('delta_7d'))}</td>")
                parts.append(f"<td class='num'>{_fmt_vol(t.get('vol_24h'))}</td>")
                parts.append("</tr>")
        parts.append("</tbody></table>")

    parts.append("<div class='foot'>")
    parts.append(
        "<b>Headline row</b> = the sub-market whose horizon best matches the "
        "row's <b>target</b> date (closest parsed date in the question text). "
        "For bucket-style events without horizons (e.g. NFP, CB hike/hold/cut), "
        "this falls back to the highest-Yes sub-market — the consensus outcome. "
        "<b>Sub-rows</b> show the rest of the distribution with each "
        "alternative outcome's own % and Δ moves. "
        "Δ24h is each sub-market's yes_price change vs ~24h prior; "
        "<span class='na'>n/a</span> means no prior snapshot. "
        "<span class='horizon-warn'>⚠</span> warns when no sub-market exists "
        f"within {HORIZON_MATCH_TOLERANCE_DAYS}d of the target — the headline "
        "row is showing a different horizon than the label implies."
    )
    if missing:
        parts.append(
            "<br>Events not found at this snapshot: "
            + ", ".join(html.escape(m) for m in missing)
            + "."
        )
    if dropped_stale:
        parts.append(
            f"<br>Dropped (resolved &gt;{RECENT_RESOLVED_DAYS}d ago): "
            + ", ".join(html.escape(m) for m in dropped_stale)
            + "."
        )
    parts.append(
        "<br>Spec: <code>docs/prediction/macro_snapshot.md</code> · "
        "Generator: <code>scripts/prediction/polymarket/macro_snapshot.py</code>"
    )
    parts.append("</div></body></html>")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SnapshotData:
    """Plain-data result of `collect_snapshot_rows` — reusable across renderers.

    Same payload feeds the HTML writer here and the Adaptive Card formatter at
    `src/imdr/notifications/formatters/macro_snapshot_card.py`.
    """
    rows: list[dict]
    snapshot_ts: str
    generated_ts: str
    missing: list[str]
    dropped_stale: list[str]


def collect_snapshot_rows(db_path: Path = DB_FILE) -> SnapshotData:
    """Build the structured snapshot data without rendering anything."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        latest = conn.execute(
            "SELECT MAX(snapshot_ts) FROM market_observation"
        ).fetchone()[0]
        if not latest:
            raise SystemExit("No snapshots in market_observation.")
        latest_dt = datetime.fromisoformat(latest.replace("Z", "+00:00"))
        six_hours_ago = (latest_dt - timedelta(hours=6)).isoformat(timespec="microseconds")
        day_ago = (latest_dt - timedelta(hours=24)).isoformat(timespec="microseconds")
        week_ago = (latest_dt - timedelta(days=7)).isoformat(timespec="microseconds")

        today_utc = latest_dt.astimezone(timezone.utc).date()

        events = snapshot_entries(load_watchlist())
        events = sorted(events, key=lambda e: e.event_date or date.max)

        rows: list[dict] = []
        missing: list[str] = []
        dropped_stale: list[str] = []
        for ev in events:
            section_override, include = _classify_event(ev.event_date, today_utc)
            if not include:
                dropped_stale.append(ev.label)
                continue
            eid = _resolve_event_id(conn, ev, latest)
            data = (_event_data(conn, eid, latest, six_hours_ago, day_ago, week_ago,
                                target_date=ev.event_date)
                    if eid else None)
            if data is None:
                missing.append(ev.label)
                continue
            rows.append({
                "section": section_override or ev.section,
                "label": ev.label,
                "asset": ev.asset,
                "market_read": ev.market_read,
                "event_date": ev.event_date.isoformat() if ev.event_date else None,
                **data,
            })

        generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        return SnapshotData(rows=rows, snapshot_ts=latest, generated_ts=generated,
                            missing=missing, dropped_stale=dropped_stale)
    finally:
        conn.close()


def build_snapshot(db_path: Path = DB_FILE, out_dir: Path = OUT_DIR) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    data = collect_snapshot_rows(db_path)
    html_doc = render_html(data.rows, data.snapshot_ts, data.generated_ts,
                           data.missing, data.dropped_stale)

    latest_dt = datetime.fromisoformat(data.snapshot_ts.replace("Z", "+00:00"))
    stamp = latest_dt.strftime("%Y%m%d_%H%M")
    out_path = out_dir / f"macro_snapshot_{stamp}.html"
    out_path.write_text(html_doc, encoding="utf-8")
    print(f"[macro_snapshot] wrote {out_path}")
    if data.missing:
        print(f"[macro_snapshot] missing ({len(data.missing)}): {', '.join(data.missing)}")
    if data.dropped_stale:
        print(f"[macro_snapshot] dropped stale ({len(data.dropped_stale)}): {', '.join(data.dropped_stale)}")
    return out_path


def main() -> None:
    ap = argparse.ArgumentParser(prog="macro_snapshot")
    ap.add_argument("--db", default=str(DB_FILE), help="Polymarket SQLite DB path")
    ap.add_argument("--out-dir", default=str(OUT_DIR), help="Output directory for HTML files")
    args = ap.parse_args()
    build_snapshot(Path(args.db), Path(args.out_dir))


if __name__ == "__main__":
    main()
