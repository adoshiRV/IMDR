"""Weekly rundown of upcoming RBA calendar items from calendar.cb_events.

Reads AU central-bank events via ``imdr.market_calendar.cb_events.upcoming_cb_events``,
collapses cross-vendor near-duplicates (Bloomberg "RBA Cash Rate Target" vs TE
"rba interest rate decision"; "RBA Minutes of X Policy Meeting" vs
"rba meeting minutes"; the two speech spellings per official), and prints the
survivors grouped by calendar week (Mon-Sun), date-sorted within each week.

Times are shown in Sydney local (AEST/AEDT). Rows with no confirmed time or
that are still projected (``is_estimated=1``) are flagged ``(soft)`` — see
docs/admin/calendar/cb_events_refresh.md.

Usage:
    python -m scripts.calendar.rba_upcoming_weekly
    python -m scripts.calendar.rba_upcoming_weekly --weeks 12
    python -m scripts.calendar.rba_upcoming_weekly --confirmed-only
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from imdr.config.settings import get_settings
from imdr.connectors.mssql import MSSQLConnector
from imdr.market_calendar.cb_events import upcoming_cb_events

SYDNEY = ZoneInfo("Australia/Sydney")

# RBA officials whose surnames appear in speech/testimony event names. Used to
# collapse the two spellings (e.g. "rba kent speech" / "rba's kent-fireside
# chat") into one appearance per person per day.
_RBA_OFFICIALS = (
    "bullock", "kent", "hauser", "jones", "jacobs", "hunter", "plumb",
    "mcphee", "harper", "connolly", "brischetto", "kohler", "smith",
    "hewson", "debelle", "lowe", "ellis", "kearns", "heath", "cagliarini",
)


_DT_RE = re.compile(
    r"(?P<d>\d{4}-\d{2}-\d{2})[ T](?P<t>\d{2}:\d{2}:\d{2})"
    r"(?:\.(?P<frac>\d+))?\s*(?P<tz>[+-]\d{2}:?\d{2}|Z)?"
)


def _to_date(v: object) -> date | None:
    """Coerce a DB value (date, datetime, or ISO string) to a date."""
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    return date.fromisoformat(str(v)[:10])


def _to_dt(v: object) -> datetime | None:
    """Coerce a DB datetimeoffset value to a tz-aware datetime.

    The legacy ODBC "SQL Server" driver returns datetimeoffset as a string like
    ``2026-08-11 04:30:00.0000000 +00:00`` (7 fractional digits), which
    ``datetime.fromisoformat`` rejects — so parse tolerantly. Naive results are
    assumed UTC (cb_events stores UTC offsets).
    """
    if v is None or isinstance(v, datetime):
        return v
    m = _DT_RE.match(str(v).strip())
    if not m:
        return None
    iso = f"{m['d']}T{m['t']}"
    if m["frac"]:
        iso += f".{m['frac'][:6]}"
    tz = m["tz"]
    if tz == "Z":
        iso += "+00:00"
    elif tz:
        iso += tz if ":" in tz else f"{tz[:3]}:{tz[3:]}"
    parsed = datetime.fromisoformat(iso)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


@dataclass(frozen=True)
class RBAItem:
    """One collapsed RBA calendar item."""

    event_date: date
    event_datetime: datetime | None
    kind: str          # canonical grouping key, e.g. "Rate Decision"
    label: str         # display label
    is_soft: bool      # projected date or no confirmed time


def classify_event(event_name: str) -> tuple[str, str] | None:
    """Map a raw cb_events name to (kind, detail) for de-duplication.

    ``detail`` distinguishes rows that share a kind but are genuinely separate
    (a speaker, or a CPI measure/frequency). Returns None for names that are
    not RBA calendar items.
    """
    n = " ".join(event_name.lower().split())
    if "rba" not in n and "reserve bank of australia" not in n:
        return None

    # Rate decision (Bloomberg "cash rate target" == TE "interest rate decision")
    if "cash rate target" in n or "interest rate decision" in n or "cash rate" in n:
        return ("Rate Decision", "")
    if "press conference" in n:
        return ("Press Conference", "")
    if "statement on monetary policy" in n:
        return ("Statement on Monetary Policy", "")
    if "minutes" in n:
        return ("Minutes", "")
    if "chart pack" in n:
        return ("Chart Pack", "")
    if "financial stability review" in n:
        return ("Financial Stability Review", "")
    if "bulletin" in n:
        return ("Bulletin", "")
    if "payments system board" in n:
        return ("Payments System Board Meeting", "")
    if "annual report" in n:
        return ("Annual Report", "")
    # RBA-branded CPI measures (ABS release, tagged RBA) — keep measure+freq apart
    if "trimmed mean cpi" in n or "weighted median cpi" in n:
        measure = "Trimmed mean CPI" if "trimmed mean" in n else "Weighted median CPI"
        freq = "YoY" if "yoy" in n else "QoQ" if "qoq" in n else "MoM" if "mom" in n else ""
        return ("Core CPI", f"{measure} {freq}".strip())
    # Speeches / testimony / panels / fireside chats — one per speaker per day
    if any(w in n for w in ("speech", "speaks", "fireside", "testimony",
                            "panel", "remarks", "lecture", "conference")):
        speaker = next((o for o in _RBA_OFFICIALS if o in n), None)
        detail = speaker.title() if speaker else "official"
        return ("Speech", detail)
    return None


_LABELS = {
    "Rate Decision": "RBA Cash Rate decision",
    "Press Conference": "RBA press conference",
    "Statement on Monetary Policy": "RBA Statement on Monetary Policy",
    "Minutes": "RBA Board meeting minutes",
    "Chart Pack": "RBA Chart Pack",
    "Financial Stability Review": "RBA Financial Stability Review",
    "Bulletin": "RBA Bulletin",
    "Payments System Board Meeting": "RBA Payments System Board meeting",
    "Annual Report": "RBA Annual Report",
}


def _label_for(kind: str, detail: str) -> str:
    if kind == "Speech":
        return f"RBA speech — {detail}" if detail != "official" else "RBA speech"
    if kind == "Core CPI":
        return f"{detail} (RBA measure)"
    return _LABELS.get(kind, kind)


def collapse(rows: list[tuple[date, datetime | None, str, bool]]) -> list[RBAItem]:
    """Collapse cross-vendor duplicate rows to one item per (date, kind, detail).

    ``rows`` is (event_date, event_datetime, event_name, is_estimated).
    Winner within a group prefers a confirmed (non-estimated) row that carries a
    time. ``is_soft`` is True when the surviving row is projected or has no time.
    """
    groups: dict[tuple[date, str, str], RBAItem] = {}
    for ev_date, ev_dt, ev_name, est in rows:
        classified = classify_event(ev_name)
        if classified is None:
            continue
        kind, detail = classified
        key = (ev_date, kind, detail)
        soft = bool(est) or ev_dt is None
        candidate = RBAItem(
            event_date=ev_date,
            event_datetime=ev_dt,
            kind=kind,
            label=_label_for(kind, detail),
            is_soft=soft,
        )
        cur = groups.get(key)
        if cur is None:
            groups[key] = candidate
            continue
        # Prefer the harder, time-bearing row.
        cur_score = (0 if cur.is_soft else 1, 1 if cur.event_datetime else 0)
        new_score = (0 if candidate.is_soft else 1, 1 if candidate.event_datetime else 0)
        if new_score > cur_score:
            groups[key] = candidate

    return sorted(
        groups.values(),
        key=lambda i: (
            i.event_date,
            i.event_datetime.timestamp() if i.event_datetime else float("inf"),
            i.label,
        ),
    )


def _week_start(d: date) -> date:
    """Monday of the week containing d."""
    return d - timedelta(days=d.weekday())


def _fmt_time(item: RBAItem) -> str:
    if item.event_datetime is None:
        return "time TBc"
    local = item.event_datetime.astimezone(SYDNEY)
    tzname = local.tzname() or "AEST/AEDT"
    return f"{local:%H:%M} {tzname}"


def render(items: list[RBAItem], weeks: int) -> str:
    lines: list[str] = []
    title = f"Upcoming RBA calendar — next {weeks} weeks (from {date.today():%a %d %b %Y})"
    lines.append(title)
    lines.append("=" * len(title))
    if not items:
        lines.append("  (no RBA events found in window)")
        return "\n".join(lines)

    cur_week: date | None = None
    for it in items:
        wk = _week_start(it.event_date)
        if wk != cur_week:
            cur_week = wk
            lines.append("")
            lines.append(f"Week of {wk:%a %d %b %Y}")
            lines.append("-" * 40)
        soft = "  (soft)" if it.is_soft else ""
        lines.append(
            f"  {it.event_date:%a %d %b}  {_fmt_time(it):<14}  {it.label}{soft}"
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Weekly upcoming RBA calendar view")
    parser.add_argument("--weeks", type=int, default=8, help="horizon in weeks (default 8)")
    parser.add_argument("--confirmed-only", action="store_true",
                        help="exclude projected (is_estimated) rows")
    args = parser.parse_args()

    settings = get_settings()
    connector = MSSQLConnector(settings)
    try:
        with Session(connector.engine) as session:
            events = upcoming_cb_events(
                session,
                country_code="AU",
                days_ahead=args.weeks * 7,
                confirmed_only=args.confirmed_only,
            )
            rows = [
                (_to_date(e.event_date), _to_dt(e.event_datetime),
                 e.event_name, bool(e.is_estimated))
                for e in events
            ]
    finally:
        connector.dispose()

    items = collapse(rows)
    print(render(items, args.weeks))
    return 0


if __name__ == "__main__":
    sys.exit(main())
