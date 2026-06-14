"""Macro release alert email formatter.

Renders the HTML email sent by the 15-minute TradingEconomics calendar
alerter (`scripts/calendar/te_release_alert.py`) when one or more
medium/high-importance economic events flip their `actual` from
NULL -> value, or get revised.

Visual layout mirrors a TE /calendar row: time UTC | flag | event |
Actual (big, colour-coded vs consensus) | Previous | Consensus | Forecast.

Subject prefix is `[Macro]` — explicitly NOT `[IMDR]` so user-side spam
filters keyed off `[IMDR]` don't catch macro release notifications.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from jinja2 import Environment, FileSystemLoader

from imdr.market_calendar.te_scraper import ActualChange

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"

MAX_ROWS_IN_EMAIL = 12

# All times in the email render in Singapore time. TE parses event datetimes
# as UTC; we convert at render time so the desk reading the inbox doesn't
# have to do the +8 math.
_SGT = timezone(timedelta(hours=8))


# ---------------------------------------------------------------------------
# Numeric extraction for beat/miss colouring
# ---------------------------------------------------------------------------

_NUM_RE = re.compile(r"-?\d+(?:[.,]\d+)?")


def _to_number(s: str | None) -> float | None:
    """Best-effort: pull the first numeric token out of a TE cell.

    Handles '4.538%', '$-310.0B', 'A$1.8B', '-35%', '131', 'ZAR50.2B'.
    Strips trailing revised markers (* / ®). Returns None when nothing
    numeric is present (e.g. cells like 'None' or speech rows with no
    consensus).
    """
    if s is None:
        return None
    m = _NUM_RE.search(s.replace(",", ""))
    if not m:
        return None
    try:
        return float(m.group(0))
    except ValueError:
        return None


def _beat_miss(actual: str | None, consensus: str | None) -> str:
    """Return 'beat', 'miss', or 'neutral' for actual vs consensus.

    'beat' = actual numerically greater than consensus, 'miss' = lower,
    'neutral' = no consensus or equal. Note: a higher CPI print is still
    classed 'beat' here — the colour just communicates direction vs
    expectation, the email doesn't try to interpret macro polarity.
    """
    a = _to_number(actual)
    c = _to_number(consensus)
    if a is None or c is None:
        return "neutral"
    if a > c:
        return "beat"
    if a < c:
        return "miss"
    return "neutral"


# ---------------------------------------------------------------------------
# Importance -> visual badge
# ---------------------------------------------------------------------------

def _importance_dots(relevance: float | None) -> tuple[str, str]:
    """Return (dots, colour) badge for the importance column.

    Mapped to RV palette (rv_tokens.css):
      relevance >= 90  -> 3 dots, --neg (#B23A2B)
      relevance >= 60  -> 2 dots, --warn (#B8862F)
      otherwise        -> 1 dot,  --text-faint (#A7A8A8)
    """
    if relevance is None:
        return "●", "#A7A8A8"
    if relevance >= 90:
        return "●●●", "#B23A2B"
    if relevance >= 60:
        return "●●", "#B8862F"
    return "●", "#A7A8A8"


# ---------------------------------------------------------------------------
# Event name prettifier
# ---------------------------------------------------------------------------

def _prettify_event(name: str) -> str:
    """Title-case TE's lowercase slugs for the email.

    'ecb interest rate decision' -> 'ECB Interest Rate Decision'.
    'gdp mom prel' -> 'GDP MoM Prel'.
    """
    UPPER = {"ecb", "fomc", "fed", "boj", "rba", "rbi", "rbnz", "boc",
             "bcb", "snb", "bsp", "cbc", "pboc", "boe", "bok",
             "ppi", "cpi", "gdp", "pmi", "ism", "ny", "nfp", "adp",
             "jgb", "ust", "ags", "us", "uk", "eu", "ea", "opec"}
    # Cadence abbreviations — readers want "MoM" not "Mom".
    MIXED = {"mom": "MoM", "yoy": "YoY", "qoq": "QoQ", "wow": "WoW"}
    out = []
    for tok in name.split():
        low = tok.lower()
        if low in UPPER:
            out.append(low.upper())
        elif low in MIXED:
            out.append(MIXED[low])
        else:
            out.append(tok.capitalize() if tok and tok[0].islower() else tok)
    return " ".join(out)


# ---------------------------------------------------------------------------
# Per-row context builder
# ---------------------------------------------------------------------------

def _change_to_ctx(c: ActualChange) -> dict[str, Any]:
    dots, dot_colour = _importance_dots(c.relevance)
    direction = _beat_miss(c.new_actual, c.consensus)
    # Palette aligned with docs/admin/research/brief_assets/rv_tokens.css
    actual_colour = {
        "beat": "#004527",     # rv-green   (--pos)
        "miss": "#B23A2B",     # rv-neg
        "neutral": "#3D3E3E",  # rv-fg
    }[direction]

    # Render the event time in Singapore time for the desk.
    if c.event_datetime:
        time_sgt = c.event_datetime.astimezone(_SGT).strftime("%H:%M")
    else:
        time_sgt = "--:--"

    iso = (c.country_iso_te or "").upper()

    is_revised = bool(c.old_actual) and c.old_actual != c.new_actual

    return {
        "event_id": c.event_id,
        "time_sgt": time_sgt,
        "iso": iso,
        "country_name": c.country_name or iso,
        "event_name": _prettify_event(c.event_name),
        "actual": c.new_actual,
        "old_actual": c.old_actual,
        "previous": c.previous or "—",
        "consensus": c.consensus or "—",
        "forecast": c.forecast or "—",
        "dots": dots,
        "dot_colour": dot_colour,
        "actual_colour": actual_colour,
        "direction": direction,
        "is_revised": is_revised,
        "te_url": (f"https://tradingeconomics.com{c.te_url}"
                   if c.te_url and c.te_url.startswith("/")
                   else (c.te_url or "")),
    }


def _sort_key(c: ActualChange) -> tuple[float, str, str]:
    """Highest-importance first; ties broken by time then country."""
    rel = -(c.relevance or 0)
    t = c.event_datetime.isoformat() if c.event_datetime else ""
    return rel, t, c.country_iso_te or ""


def _dedupe_by_event_id(changes: list[ActualChange]) -> list[ActualChange]:
    """Collapse multiple changes that target the same DB row.

    TE occasionally renders two calendar rows with the same `data-event`
    slug on the same day in the same country (different reporting periods
    sharing one event_name). Both UPSERTs land on the same DB row, so
    both emit an ActualChange. We keep only the LAST change for each
    event_id — the final state in the DB this tick.
    """
    latest: dict[int, ActualChange] = {}
    for c in changes:
        latest[c.event_id] = c
    return list(latest.values())


# ---------------------------------------------------------------------------
# Formatter
# ---------------------------------------------------------------------------

class TEReleaseAlertFormatter:
    """Builds subject + HTML body for the 15-minute macro release digest."""

    def __init__(self) -> None:
        self._env = Environment(
            loader=FileSystemLoader(str(_TEMPLATE_DIR)),
            autoescape=True,
        )
        self._template = self._env.get_template("te_release_alert.html")

    def format_subject(
        self,
        changes: Iterable[ActualChange] | None = None,
        **kwargs: Any,
    ) -> str:
        changes = sorted(_dedupe_by_event_id(list(changes or [])), key=_sort_key)
        now_hhmm = datetime.now(_SGT).strftime("%H:%M")
        if not changes:
            # Caller should not send when there are no changes, but be safe.
            return f"[Macro] No releases | {now_hhmm} SGT"
        if len(changes) == 1:
            c = changes[0]
            country = c.country_name or (c.country_iso_te or "").upper()
            event = _prettify_event(c.event_name)
            actual = c.new_actual
            tail = f" (vs {c.consensus} cons)" if c.consensus else ""
            return f"[Macro] {country} {event} {actual}{tail} | {now_hhmm} SGT"
        # multi-event digest
        top = changes[0]
        country = top.country_name or (top.country_iso_te or "").upper()
        event = _prettify_event(top.event_name)
        return (
            f"[Macro] {len(changes)} releases @ {now_hhmm} SGT | "
            f"top: {country} {event} {top.new_actual}"
        )

    def format_body(
        self,
        changes: Iterable[ActualChange] | None = None,
        **kwargs: Any,
    ) -> str:
        changes = sorted(_dedupe_by_event_id(list(changes or [])), key=_sort_key)
        n_total = len(changes)
        truncated = max(0, n_total - MAX_ROWS_IN_EMAIL)
        rows = [_change_to_ctx(c) for c in changes[:MAX_ROWS_IN_EMAIL]]
        now_sgt = datetime.now(_SGT)
        ctx = {
            "rows": rows,
            "n_total": n_total,
            "n_truncated": truncated,
            "run_time_sgt": now_sgt.strftime("%Y-%m-%d %H:%M:%S SGT"),
        }
        return self._template.render(**ctx)
