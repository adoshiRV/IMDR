"""TradingEconomics economic-calendar scraper.

Polite, single-request fetch of https://tradingeconomics.com/calendar and
idempotent upsert into `calendar.cb_events`.

Why this exists
---------------
The default `/calendar` page returns a 7-day forward window (today + 6 days)
across ~24 countries — Actual / Previous / Consensus / Forecast plus a 1-3
importance rating per event. Running the scrape daily catches actuals as
they release: a row inserted with Actual=NULL on T-1 gets UPDATEd with the
released value on day T.

Design
------
- ONE polite GET per run (no loops, no retries, no headless browser).
- robots.txt is honoured (TE allows /calendar for a stock UA).
- gzip/deflate only (stdlib `requests` can't decode brotli).
- Idempotent UPSERT on (vendor_id, event_date, country_id) plus whichever
  of the two filtered unique indexes applies: by `ticker` when TE gives a
  real data-symbol, else by `event_name` (TE's `data-event` slug). Generic
  'CALENDAR' placeholders are NULLed and always keyed by event_name.
- TE 1-3 importance is normalised to BBG's 0-100 scale so the `relevance`
  column stays homogeneous (1->33.33, 2->66.67, 3->100.0).

Country mapping
---------------
Most TE ISO-like codes map directly to dim_country.country_code. Two
overrides:
  TE 'EA' (Euro Area)      -> dim_country.country_code 'EU'  (Eurozone TARGET2)
  TE 'GB' (United Kingdom) -> dim_country.country_code 'UK'
Codes with no dim_country row (e.g. 'OP' = OPEC) are skipped with a warning.
"""
from __future__ import annotations

import random
import re
import time
import urllib.robotparser
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Iterable

import requests
import structlog
from bs4 import BeautifulSoup
from sqlalchemy import text
from sqlalchemy.orm import Session

log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

BASE = "https://tradingeconomics.com"
PATH = "/calendar"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    # NB: omit 'br' — stdlib requests can't decode brotli without the brotli pkg
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}

VENDOR_CODE = "tradingeconomics"

# TE ISO -> dim_country.country_code overrides. Everything else is identity.
_COUNTRY_OVERRIDES = {
    "EA": "EU",   # Euro Area  -> Eurozone (TARGET2)
    "GB": "UK",   # GB         -> UK
    # Supranational / non-country macro signals all land in the
    # 'Worldwide' pseudo-country. Per-issuer provenance survives on
    # cb_events.source ('tradingeconomics:<te_id>') and on te_url.
    "WL": "WW",   # FAO Food Index, NY Fed Global Supply Chain Pressure
    "OP": "WW",   # OPEC Monthly Report, OPEC ministerial meetings
}

# TE 1-3 importance normalised to BBG's 0-100 relevance scale.
_IMPORTANCE_TO_RELEVANCE = {1: 33.33, 2: 66.67, 3: 100.0}


# ---------------------------------------------------------------------------
# Parsed-event record
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TECalendarEvent:
    """One parsed row from TE's /calendar page."""

    event_date: date
    event_datetime: datetime | None
    country_iso_te: str
    country_name: str
    event_slug: str          # 'ecb interest rate decision' (data-event)
    event_text: str          # rendered text (includes the reference period inline)
    category: str | None
    symbol: str | None       # data-symbol — TE's event-type ticker
    te_id: str | None        # data-id — per-instance stable id (not used as PK)
    te_url: str | None
    importance: int | None   # 1, 2, 3 (None if not encoded)
    time_text: str           # e.g. '01:00 AM' (TE local; informational)
    actual: str | None
    previous: str | None     # may carry trailing '*' marker = revised
    consensus: str | None
    forecast: str | None


# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------

def _check_robots() -> bool:
    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(f"{BASE}/robots.txt")
    try:
        rp.read()
    except Exception as e:  # noqa: BLE001
        log.warning("te.robots_read_failed", error=str(e))
        return False
    return rp.can_fetch(UA, f"{BASE}{PATH}")


def fetch_calendar_html(
    *,
    d1: date | None = None,
    d2: date | None = None,
    polite_pause: tuple[float, float] = (5.0, 8.0),
) -> str:
    """Single polite GET to /calendar. Returns the decoded HTML.

    Date range: if `d1` and `d2` are both provided, set TE's
    `cal-custom-range` cookie to `"YYYY-MM-DD|YYYY-MM-DD"` so the server
    returns events in that exact window. Default (None/None) gives TE's
    7-day forward page.

    Politeness: 5-8s pre-flight jitter by default — bumped from 3-5s
    because the custom-range response is ~3.5MB (vs ~1.5MB default).

    Honors robots.txt; raises RuntimeError if disallowed or if a Cloudflare
    challenge fires.
    """
    if not _check_robots():
        raise RuntimeError("robots.txt disallows /calendar for our UA")

    pause = random.uniform(*polite_pause)
    log.info("te.preflight_sleep", seconds=round(pause, 2))
    time.sleep(pause)

    cookies: dict[str, str] = {}
    if d1 is not None and d2 is not None:
        if d2 < d1:
            raise ValueError(f"d2 ({d2}) must be >= d1 ({d1})")
        cookies["cal-custom-range"] = f"{d1.isoformat()}|{d2.isoformat()}"

    url = f"{BASE}{PATH}"
    log.info("te.fetch", url=url, cookies=cookies or None)
    r = requests.get(url, headers=HEADERS, cookies=cookies, timeout=60, allow_redirects=True)
    log.info("te.fetch_done", status=r.status_code, bytes=len(r.content))

    if r.status_code != 200:
        raise RuntimeError(f"TE returned status {r.status_code}")

    body_head = r.text[:2000].lower()
    if "just a moment" in body_head or "cf-chl" in body_head or "challenge-platform" in body_head:
        raise RuntimeError("Cloudflare challenge fired — need a headed browser")

    return r.text


# ---------------------------------------------------------------------------
# Parse
# ---------------------------------------------------------------------------

_DATE_TD_CLASS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _parse_importance(span_classes: Iterable[str]) -> int | None:
    for c in span_classes:
        if c.startswith("calendar-date-"):
            try:
                return int(c.rsplit("-", 1)[1])
            except ValueError:
                pass
    return None


def _parse_time(time_text: str, event_date: date) -> datetime | None:
    """Combine the row's '01:00 AM' text with the event date.

    The page renders in GMT by default (server-side scrape with no locale).
    We store as UTC; consumers can shift by event_date_offset if needed.
    """
    if not time_text:
        return None
    try:
        t = datetime.strptime(time_text.strip(), "%I:%M %p").time()
    except ValueError:
        return None
    return datetime.combine(event_date, t, tzinfo=timezone.utc)


def parse_calendar_html(html: str) -> list[TECalendarEvent]:
    """Parse the raw HTML into a list of TECalendarEvent records."""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", id="calendar")
    if table is None:
        log.warning("te.parse_no_calendar_table")
        return []

    events: list[TECalendarEvent] = []
    for tr in table.find_all("tr", recursive=False):
        if not tr.get("data-id"):
            continue
        tds = tr.find_all("td", recursive=False)
        if len(tds) < 3:
            continue

        # event_date: the first <td> has a class like "2026-06-11"
        ev_date: date | None = None
        for c in tds[0].get("class") or []:
            if _DATE_TD_CLASS_RE.match(c):
                ev_date = date.fromisoformat(c)
                break
        if ev_date is None:
            # cannot place this row in time — skip
            continue

        # importance + time text (col 0)
        span = tds[0].find("span")
        importance = _parse_importance(span.get("class") or []) if span else None
        time_text = tds[0].get_text(" ", strip=True)
        ev_dt = _parse_time(time_text, ev_date)

        # country ISO (col 1, nested table)
        country_iso = ""
        nested = tds[1].find("table")
        if nested:
            iso_cell = nested.find("td", class_="calendar-iso")
            if iso_cell:
                country_iso = iso_cell.get_text(strip=True)

        # event text (col 2)
        event_text = tds[2].get_text(" ", strip=True)

        def _cell(i: int) -> str:
            return tds[i].get_text(" ", strip=True) if len(tds) > i else ""

        # TE's /calendar row layout:
        #   td[0] = date + importance dot + time
        #   td[1] = country flag + ISO (nested table)
        #   td[2] = event name + reference period ("MAY", "Q1 2026") inline
        #   td[3] = Actual
        #   td[4] = Previous (may carry trailing '*' for revised)
        #   td[5] = Consensus
        #   td[6] = Forecast (TE's own model forecast)
        #   td[7] = importance bars + alert-bell icons (no text)
        # Prior to 2026-06-12 this parser indexed td[3] as a separate
        # "reference" column and pushed Actual/Previous/Consensus/Forecast
        # one cell to the right — yielding cb_events rows whose `actual`
        # column actually held TE's *Previous* value. See migration 089.
        events.append(TECalendarEvent(
            event_date=ev_date,
            event_datetime=ev_dt,
            country_iso_te=country_iso,
            country_name=(tr.get("data-country") or "").strip(),
            event_slug=(tr.get("data-event") or "").strip(),
            event_text=event_text,
            category=(tr.get("data-category") or "").strip() or None,
            symbol=(tr.get("data-symbol") or "").strip() or None,
            te_id=(tr.get("data-id") or "").strip() or None,
            te_url=(tr.get("data-url") or "").strip() or None,
            importance=importance,
            time_text=time_text,
            actual=_cell(3) or None,
            previous=_cell(4) or None,
            consensus=_cell(5) or None,
            forecast=_cell(6) or None,
        ))

    return events


# ---------------------------------------------------------------------------
# Country resolution
# ---------------------------------------------------------------------------

def build_country_lookup(session: Session) -> dict[str, int]:
    """{country_code -> id} for every active country in dim_country."""
    rows = session.execute(text(
        "SELECT country_code, id FROM dbo.dim_country WHERE is_active = 1"
    )).all()
    return {r[0]: r[1] for r in rows}


def build_country_name_lookup(session: Session) -> dict[int, str]:
    """{id -> display_name} for every active country in dim_country."""
    rows = session.execute(text(
        "SELECT id, display_name FROM dbo.dim_country WHERE is_active = 1"
    )).all()
    return {int(r[0]): r[1] for r in rows}


def resolve_country_id(
    te_iso: str,
    lookup: dict[str, int],
) -> int | None:
    """Map a TE ISO-ish code to dim_country.id, or None if unknown."""
    if not te_iso:
        return None
    mapped = _COUNTRY_OVERRIDES.get(te_iso, te_iso)
    return lookup.get(mapped)


# ---------------------------------------------------------------------------
# Upsert
# ---------------------------------------------------------------------------

def _resolve_vendor_id(session: Session) -> int:
    row = session.execute(text(
        "SELECT id FROM dbo.dim_vendor WHERE vendor_code = :v"
    ), {"v": VENDOR_CODE}).first()
    if row is None:
        raise RuntimeError(
            f"dim_vendor row for {VENDOR_CODE!r} not found — apply migration 094"
        )
    return int(row[0])


@dataclass(frozen=True)
class ActualChange:
    """One row whose `actual` value transitioned in this run.

    Carries everything the email formatter needs to render a TE-style row,
    without a re-query. `old_actual` will be None on first appearance of
    the actual (NULL -> value); both old and new are non-empty strings on
    a revision.
    """

    event_id: int
    event_date: date
    event_datetime: datetime | None
    country_id: int
    country_iso_te: str
    country_name: str
    event_name: str
    ticker: str | None
    old_actual: str | None
    new_actual: str
    previous: str | None
    consensus: str | None
    forecast: str | None
    revised: str | None
    relevance: float | None
    te_url: str | None


@dataclass
class UpsertResult:
    parsed: int
    skipped_unknown_country: int
    inserted: int
    updated_actual: int
    updated_other: int
    unchanged: int
    actual_changes: list[ActualChange] = field(default_factory=list)


# Split previous "-35% *" into (clean_value, revised_marker)
_REVISED_SUFFIX_RE = re.compile(r"\s*\*+\s*$")


def _split_previous(prev_raw: str | None) -> tuple[str | None, str | None]:
    if prev_raw is None:
        return None, None
    revised = "*" if _REVISED_SUFFIX_RE.search(prev_raw) else None
    clean = _REVISED_SUFFIX_RE.sub("", prev_raw).strip() or None
    return clean, revised


# Truncate to schema width (varchar(20)) — TE occasionally emits noisy
# multi-value strings like '$-310.0B' which fit, but auction "4.538%" is fine.
def _trunc(s: str | None, n: int = 20) -> str | None:
    if s is None:
        return None
    return s[:n]


_UPSERT_SQL = text("""
MERGE [calendar].[cb_events] AS tgt
USING (
    SELECT
        :vendor_id           AS vendor_id,
        :event_date          AS event_date,
        :event_datetime      AS event_datetime,
        :country_id          AS country_id,
        :event_name          AS event_name,
        :category            AS category,
        :ticker              AS ticker,
        :survey              AS survey,
        :actual              AS actual,
        :prior_value         AS prior_value,
        :revised             AS revised,
        :forecast            AS forecast,
        :relevance           AS relevance,
        :source              AS source
) AS src
-- Match through whichever filtered unique index is active for this src
-- row, so an index-conflicting target is always MATCHED (UPDATE) rather
-- than re-INSERTed:
--   ticker IS NOT NULL -> UX_cb_events_vendor_date_country_ticker
--   ticker IS NULL     -> UX_cb_events_vendor_date_country_event
-- Matching on event_name alone (pre-2026-06-15) broke when TE renamed an
-- event instance between runs while keeping its data-symbol: the new name
-- missed the existing row and the INSERT collided on the ticker index.
ON  tgt.vendor_id  = src.vendor_id
AND tgt.event_date = src.event_date
AND tgt.country_id = src.country_id
AND (
        (src.ticker IS NOT NULL AND tgt.ticker = src.ticker)
     OR (src.ticker IS NULL AND tgt.ticker IS NULL AND tgt.event_name = src.event_name)
    )
WHEN MATCHED THEN
    UPDATE SET
        -- refresh the name too: a ticker-matched row may have been renamed
        -- by TE (no-op on the event_name-matched branch).
        event_name     = src.event_name,
        event_datetime = src.event_datetime,
        category       = src.category,
        ticker         = src.ticker,
        survey         = src.survey,
        actual         = src.actual,
        prior_value    = src.prior_value,
        revised        = src.revised,
        forecast       = src.forecast,
        relevance      = src.relevance,
        source         = src.source,
        updated_at     = SYSDATETIMEOFFSET()
WHEN NOT MATCHED THEN
    INSERT (
        vendor_id, event_date, event_datetime, country_id, category,
        event_name, ticker, survey, actual, prior_value, revised,
        forecast, relevance, source, is_estimated, created_at, updated_at
    )
    VALUES (
        src.vendor_id, src.event_date, src.event_datetime, src.country_id,
        ISNULL(src.category, 'Unknown'),
        src.event_name, src.ticker, src.survey, src.actual,
        src.prior_value, src.revised, src.forecast, src.relevance,
        src.source, 0, SYSDATETIMEOFFSET(), SYSDATETIMEOFFSET()
    )
OUTPUT $action AS act,
       inserted.id AS event_id,
       deleted.actual AS old_actual,
       inserted.actual AS new_actual;
""")


def _is_placeholder_symbol(symbol: str | None) -> bool:
    """True if TE's data-symbol is a generic non-ticker placeholder.

    TE attaches a 'CALENDAR' placeholder to rows that have no real
    instrument ticker — bare 'CALENDAR', per-country '{ISO} CALENDAR'
    ('ESP CALENDAR', 'USD CALENDAR', ...) and the run-together
    'OPECALENDAR'. A single placeholder is shared across many distinct
    same-country events (e.g. multiple sovereign bond auctions on one
    day), so it is NOT a usable uniqueness key. These rows must always
    route through the event_name uniqueness index, never the ticker one.

    Unlike `_build_collision_set` (which only catches placeholders reused
    within a single scrape batch on the same date), this catches the
    placeholder regardless of how many copies appear in any one run —
    closing the cross-date / cross-run gap that let 'ESP CALENDAR' hit the
    ticker unique index on 2026-06-15 (TE renamed te_id 419028 from
    'bonos y obligaciones auction' to '14-year obligacion auction').
    """
    return bool(symbol) and "CALENDAR" in symbol.upper()


def _build_collision_set(
    events: list[TECalendarEvent],
    country_lookup: dict[str, int],
) -> set[tuple[str, int, str]]:
    """Identify (event_date, country_id, symbol) triples that appear >1x.

    A backstop for non-placeholder symbols (the 'CALENDAR' family is
    handled unconditionally by `_is_placeholder_symbol`): if TE ever
    re-uses a real data-symbol across distinct same-day same-country
    events, NULL the ticker on those rows too so they participate in the
    event_name uniqueness path instead of the ticker uniqueness path.
    """
    seen: dict[tuple[str, int, str], int] = {}
    for e in events:
        if not e.symbol:
            continue
        country_id = resolve_country_id(e.country_iso_te, country_lookup)
        if country_id is None:
            continue
        key = (e.event_date.isoformat(), country_id, e.symbol)
        seen[key] = seen.get(key, 0) + 1
    return {k for k, n in seen.items() if n > 1}


def upsert_events(
    session: Session,
    events: list[TECalendarEvent],
    *,
    dry_run: bool = False,
    now_utc: datetime | None = None,
) -> UpsertResult:
    """Idempotent upsert of TE events into calendar.cb_events.

    Forward-event guard: TE's /calendar page displays the *last released
    level* in the Actual column for events that haven't released yet —
    a placeholder, not a real outcome. We NULL `actual` and `revised`
    when the release has not yet happened.

    "Has not yet happened" is decided per row:
      - if the row has a parsed event_datetime  -> compare to now (UTC)
      - if it doesn't                            -> fall back to date,
                                                    null when event_date >= today
                                                    (no-time events could fire
                                                    any time during the day)

    Effect: an event scheduled today at 12:15 UTC and scraped at 16:00 UTC
    keeps its actual. A 23:00 UTC event scraped at 16:00 has actual nulled.
    """
    vendor_id = _resolve_vendor_id(session)
    country_lookup = build_country_lookup(session)
    country_name_lookup = build_country_name_lookup(session)
    colliding_symbols = _build_collision_set(events, country_lookup)
    now = now_utc or datetime.now(timezone.utc)
    today_utc = now.date()

    res = UpsertResult(
        parsed=len(events),
        skipped_unknown_country=0,
        inserted=0,
        updated_actual=0,
        updated_other=0,
        unchanged=0,
    )

    for e in events:
        country_id = resolve_country_id(e.country_iso_te, country_lookup)
        if country_id is None:
            log.warning("te.skip_unknown_country", iso=e.country_iso_te, event_text=e.event_text)
            res.skipped_unknown_country += 1
            continue

        prior_clean, revised_marker = _split_previous(e.previous)
        relevance = _IMPORTANCE_TO_RELEVANCE.get(e.importance) if e.importance else None

        # Forward-event guard. See upsert_events() docstring for rationale.
        if e.event_datetime is not None:
            event_is_forward = e.event_datetime > now
        else:
            event_is_forward = e.event_date >= today_utc
        if event_is_forward:
            actual_to_store: str | None = None
            revised_to_store: str | None = None
        else:
            actual_to_store = e.actual
            revised_to_store = revised_marker

        # event_name: prefer stable TE slug, fall back to rendered text
        event_name = (e.event_slug or e.event_text or "").strip()[:500]
        if not event_name:
            continue

        # ticker: drop TE's data-symbol when it can't serve as a uniqueness
        # key — either a generic 'CALENDAR' placeholder (always) or a real
        # symbol TE happens to re-use across distinct same-day same-country
        # events. Those rows route through the event_name uniqueness index
        # instead of the ticker one.
        ticker_to_store: str | None = e.symbol
        if e.symbol and (
            _is_placeholder_symbol(e.symbol)
            or (e.event_date.isoformat(), country_id, e.symbol) in colliding_symbols
        ):
            ticker_to_store = None

        # source: 'tradingeconomics:393889' — preserve TE per-instance id
        source = f"tradingeconomics:{e.te_id}" if e.te_id else "tradingeconomics"

        # Legacy ODBC driver ("SQL Server") can't bind date/datetime — strings only.
        event_date_str = e.event_date.isoformat()
        event_dt_str = e.event_datetime.isoformat() if e.event_datetime else None

        params = {
            "vendor_id": vendor_id,
            "event_date": event_date_str,
            "event_datetime": event_dt_str,
            "country_id": country_id,
            "event_name": event_name,
            "category": (e.category or "")[:50] or None,
            "ticker": _trunc(ticker_to_store, 50),
            "survey": _trunc(e.consensus),
            "actual": _trunc(actual_to_store),
            "prior_value": _trunc(prior_clean),
            "revised": _trunc(revised_to_store),
            "forecast": _trunc(e.forecast),
            "relevance": relevance,
            "source": _trunc(source, 200),
        }

        if dry_run:
            # classify against the existing row, no write — mirror the MERGE
            # match: by ticker when present, else by event_name (ticker NULL).
            if params["ticker"] is not None:
                existing = session.execute(text(
                    "SELECT actual FROM calendar.cb_events "
                    "WHERE vendor_id=:v AND event_date=:d AND country_id=:c AND ticker=:t"
                ), {"v": vendor_id, "d": event_date_str, "c": country_id, "t": params["ticker"]}).first()
            else:
                existing = session.execute(text(
                    "SELECT actual FROM calendar.cb_events "
                    "WHERE vendor_id=:v AND event_date=:d AND country_id=:c "
                    "AND event_name=:n AND ticker IS NULL"
                ), {"v": vendor_id, "d": event_date_str, "c": country_id, "n": event_name}).first()
            if existing is None:
                res.inserted += 1
            elif (existing[0] or "") != (params["actual"] or ""):
                res.updated_actual += 1
            else:
                res.unchanged += 1
            continue

        out = session.execute(_UPSERT_SQL, params).first()
        if out is None:
            res.unchanged += 1
        else:
            act, event_id, old_actual, new_actual = out
            if act == "INSERT":
                res.inserted += 1
            elif act == "UPDATE":
                if (old_actual or "") != (new_actual or ""):
                    res.updated_actual += 1
                else:
                    res.updated_other += 1
            # Capture a per-row change record when `actual` transitions to a
            # real value (NULL -> "X" or "X" -> revised "Y"). Filtering on
            # new_actual being non-empty also excludes the forward-guard
            # writes (event slid into future -> we NULLed it).
            if (old_actual or "") != (new_actual or "") and new_actual:
                res.actual_changes.append(ActualChange(
                    event_id=int(event_id),
                    event_date=e.event_date,
                    event_datetime=e.event_datetime,
                    country_id=country_id,
                    country_iso_te=e.country_iso_te,
                    country_name=country_name_lookup.get(country_id, e.country_iso_te),
                    event_name=event_name,
                    ticker=ticker_to_store,
                    old_actual=old_actual,
                    new_actual=new_actual,
                    previous=prior_clean,
                    consensus=e.consensus,
                    forecast=e.forecast,
                    revised=revised_to_store,
                    relevance=relevance,
                    te_url=e.te_url,
                ))

    if not dry_run:
        session.commit()

    return res


# ---------------------------------------------------------------------------
# Top-level orchestration
# ---------------------------------------------------------------------------

DEFAULT_LOOKBACK_DAYS = 7
DEFAULT_LOOKAHEAD_DAYS = 21


def default_window(today: date | None = None) -> tuple[date, date]:
    """Rolling 4-week window: T-7 to T+21."""
    t = today or date.today()
    return t - timedelta(days=DEFAULT_LOOKBACK_DAYS), t + timedelta(days=DEFAULT_LOOKAHEAD_DAYS)


def refresh(
    session: Session,
    *,
    d1: date | None = None,
    d2: date | None = None,
    dry_run: bool = False,
    html_override: str | None = None,
) -> UpsertResult:
    """One full refresh cycle: fetch -> parse -> upsert.

    Defaults to the rolling 4-week window (1 week lookback + 3 weeks
    forward). `html_override` lets callers replay a saved snapshot.
    """
    if html_override is not None:
        html = html_override
    else:
        if d1 is None or d2 is None:
            d1, d2 = default_window()
        log.info("te.window", d1=d1.isoformat(), d2=d2.isoformat())
        html = fetch_calendar_html(d1=d1, d2=d2)
    events = parse_calendar_html(html)
    log.info("te.parsed", n=len(events))
    return upsert_events(session, events, dry_run=dry_run)
