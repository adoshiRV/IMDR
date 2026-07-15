"""Bloomberg BQL economic-calendar loader.

Reads a SQLite database (``BQL.EconData.DB``) produced by an upstream Bloomberg
**BQL** Excel pull and idempotently upserts it into ``calendar.cb_events`` — the
sibling of :mod:`imdr.market_calendar.te_scraper` (TradingEconomics). Together
BQL and TE are the two canonical event sources behind the calendar.

Source shape
------------
One table, ``bql_events``, with two datasets:

* ``economic_calendar``   — upcoming events (survey + prior, mostly no actual)
* ``historical_econ_data`` — past events (actual filled in)

The upstream pull runs ~daily and *appends*, so the same logical event appears
multiple times as its value is revised (e.g. JOLTS Job Openings 2025-12-09:
``7658.0`` then a revised ``7670.0``). :func:`read_bql_events` therefore
collapses to ONE row per ``(event_date, country, event_name)`` — keeping the
freshest snapshot (a non-empty ``actual`` wins; ties broken by latest
``ingested_at``).

Lane
----
BQL is Bloomberg, so it writes into the **BBG vendor lane** (``vendor_id=4``) —
the daily-refresh authority for that lane. Within its window it supersedes the
older Excel/legacy Bloomberg rows in place (the unique index
``UX_cb_events_vendor_date_country_event`` keys on
``(vendor_id, event_date, country_id, event_name)``, so there is one canonical
row per event). TE keeps its own vendor lane (``vendor_id=73``), untouched.

Design (mirrors te_scraper)
---------------------------
- Idempotent MERGE keyed on ``(vendor_id, event_date, country_id, event_name)``
  with ``ticker`` always NULL (BQL carries no instrument tickers).
- ``event_name`` is normalized (casefold + accent-stripped, see
  ``imdr.market_calendar.event_name``) at read/dedup time, so an accent/case
  variant of an already-stored event always MATCHes on MERGE instead of
  colliding with the DB's accent/case-insensitive unique index on INSERT.
- Each row's upsert runs in its own SAVEPOINT — one bad row logs and is
  skipped (``UpsertResult.errored``) instead of aborting the whole run.
- Forward-event guard: NULL ``actual``/``revised`` for events that have not yet
  released (an upcoming row should never carry an outcome).
- BQL ``relevancy`` ordinal → BBG's 0-100 ``relevance`` scale, with a
  ``tier_rank`` fallback for central-bank/speaker rows whose ``relevancy``
  field bleeds into country names.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import structlog
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from imdr.market_calendar.event_name import normalize_event_name

log = structlog.get_logger(__name__)

# Default location of the upstream BQL SQLite DB (STIRT dashboard share).
DEFAULT_DB = Path(r"Z:/Business/Research/Dashboard/STIRT/db/BQL.EconData.DB")

VENDOR_CODE = "BBG"
BQL_SOURCE = "bloomberg_bql"

# Daily incremental window. The full history is backfilled once (`--all`);
# day-to-day the only rows that change are actuals/revisions filling in around
# recent releases, so a rolling window keeps each run fast. Mirrors te_scraper.
DEFAULT_LOOKBACK_DAYS = 7
DEFAULT_LOOKAHEAD_DAYS = 21

# BQL country code → dim_country.country_code. Everything else is identity
# (US, JP, AU, CA, KR, NZ, SG, IN, PH, TW, TH, ID, MY already match).
_COUNTRY_OVERRIDES = {
    "GB": "UK",   # United Kingdom
    "EZ": "EU",   # Eurozone aggregate
}

# BQL `relevancy` ordinal → BBG 0-100 relevance scale (rate_decisions() filters
# relevance > 50). For central-bank/speaker rows `relevancy` bleeds into country
# names, so fall back to `tier_rank` (policy events outrank everything).
_RELEVANCY_SCORE = {
    "very high": 100.0,
    "high": 80.0,
    "medium": 60.0,
    "low": 40.0,
    "very low": 20.0,
}
_TIER_RANK_SCORE = {1: 90.0, 2: 60.0, 3: 30.0}


# ---------------------------------------------------------------------------
# Parsed-event record
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BqlEvent:
    """One normalized, deduped event ready to upsert."""

    event_date: date
    event_datetime: datetime | None
    country_code: str
    event_name: str
    category: str | None
    survey: str | None
    actual: str | None
    prior_value: str | None
    revised: str | None
    relevance: float | None
    frequency: str | None


# ---------------------------------------------------------------------------
# Read + normalize
# ---------------------------------------------------------------------------

def _clean(val: str | None, width: int = 20) -> str | None:
    """``""``/``--``/``nan`` → None; truncate to a column width."""
    if val is None:
        return None
    s = str(val).strip()
    if s in ("", "--", "nan", "NaT"):
        return None
    return s[:width]


def _map_country_code(code: str | None) -> str:
    if not code:
        return "XX"
    code = str(code).strip().upper()
    return _COUNTRY_OVERRIDES.get(code, code)


def _relevance(relevancy: str | None, tier: str | None, tier_rank) -> float | None:
    if relevancy:
        score = _RELEVANCY_SCORE.get(str(relevancy).strip().lower())
        if score is not None:
            return score
    if tier and str(tier).strip().lower() == "policy":
        return 100.0
    try:
        return _TIER_RANK_SCORE.get(int(tier_rank))
    except (TypeError, ValueError):
        return None


def _parse_datetime(date_str: str | None, time_str: str | None) -> datetime | None:
    """Combine BQL `date` + `time` into a UTC-stamped datetime.

    BQL times are Bloomberg-rendered local time; we stamp UTC to match the
    te_scraper convention so the `event_datetime` column stays homogeneous.
    The value drives only the forward-event guard, where sub-day timezone
    skew is immaterial.
    """
    if not date_str:
        return None
    d = _parse_date(date_str)
    if d is None:
        return None
    t_raw = (time_str or "").strip()
    if not t_raw:
        return None
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            t = datetime.strptime(t_raw, fmt).time()
        except ValueError:
            continue
        return datetime(d.year, d.month, d.day, t.hour, t.minute, t.second,
                        tzinfo=timezone.utc)
    return None


def _parse_date(date_str: str | None) -> date | None:
    if not date_str:
        return None
    try:
        return date.fromisoformat(str(date_str).strip()[:10])
    except ValueError:
        return None


def _snapshot_rank(row: dict) -> tuple[int, str]:
    """Freshness key for choosing among duplicate snapshots of one event.

    A non-empty ``actual`` wins (a released value beats a pending one); ties
    break on the latest ``ingested_at`` (most recent daily pull = most revised).
    """
    has_actual = 1 if _clean(row.get("actual")) else 0
    return (has_actual, str(row.get("ingested_at") or ""))


def default_window(today: date | None = None) -> tuple[date, date]:
    """Rolling daily window: T-7 to T+21 (mirrors te_scraper.default_window)."""
    t = today or date.today()
    return t - timedelta(days=DEFAULT_LOOKBACK_DAYS), t + timedelta(days=DEFAULT_LOOKAHEAD_DAYS)


def read_bql_events(
    db_path: Path,
    *,
    d1: date | None = None,
    d2: date | None = None,
) -> list[BqlEvent]:
    """Read ``bql_events`` read-only and return one deduped BqlEvent per
    ``(event_date, country_code, event_name)`` (freshest snapshot).

    When ``d1``/``d2`` are given, only events with ``event_date`` in
    ``[d1, d2]`` are read. All snapshots of one event share its ``event_date``,
    so the window never splits an event's snapshot set — the freshest-snapshot
    dedup stays correct. Both None → read everything (full backfill).
    """
    uri = f"file:{db_path.as_posix()}?mode=ro&immutable=1"
    con = sqlite3.connect(uri, uri=True)
    con.row_factory = sqlite3.Row
    sql = (
        "SELECT date, time, country_code, name, display_name, "
        "category, category_label, tier, tier_rank, relevancy, "
        "survey, actual, prior, revision, release_freq, ingested_at "
        "FROM bql_events"
    )
    params: list[str] = []
    if d1 is not None and d2 is not None:
        sql += " WHERE date >= ? AND date <= ?"
        params = [d1.isoformat(), d2.isoformat()]
    try:
        rows = con.execute(sql, params).fetchall()
    finally:
        con.close()
    log.info("bql.read_rows", rows=len(rows), d1=d1.isoformat() if d1 else None,
             d2=d2.isoformat() if d2 else None)

    # Collapse daily-pull snapshots to one row per logical event.
    best: dict[tuple[str, str, str], dict] = {}
    for r in rows:
        rd = dict(r)
        event_date = _parse_date(rd.get("date"))
        name_raw = (_clean(rd.get("name"), 500) or _clean(rd.get("display_name"), 500))
        # Normalized (casefold + accent-stripped, see imdr.market_calendar.
        # event_name) so two spellings of the same event collapse to one
        # dedup key here AND one stored value downstream — mirrors te_scraper,
        # closing the same accent/case collision against the shared unique
        # index on calendar.cb_events.
        name = normalize_event_name(name_raw) if name_raw else None
        cc = _map_country_code(rd.get("country_code"))
        if event_date is None or not name:
            continue
        key = (event_date.isoformat(), cc, name)
        rd["_name"] = name
        rd["_cc"] = cc
        rd["_event_date"] = event_date
        if key not in best or _snapshot_rank(rd) >= _snapshot_rank(best[key]):
            best[key] = rd

    events: list[BqlEvent] = []
    for rd in best.values():
        cat = _clean(rd.get("category_label"), 50) or _clean(rd.get("category"), 50)
        events.append(BqlEvent(
            event_date=rd["_event_date"],
            event_datetime=_parse_datetime(rd.get("date"), rd.get("time")),
            country_code=rd["_cc"],
            event_name=rd["_name"],
            category=cat,
            survey=_clean(rd.get("survey")),
            actual=_clean(rd.get("actual")),
            prior_value=_clean(rd.get("prior")),
            revised=_clean(rd.get("revision")),
            relevance=_relevance(rd.get("relevancy"), rd.get("tier"), rd.get("tier_rank")),
            frequency=_clean(rd.get("release_freq"), 5),
        ))
    log.info("bql.deduped_events", events=len(events))
    return events


# ---------------------------------------------------------------------------
# Country / vendor resolution
# ---------------------------------------------------------------------------

def build_country_lookup(session: Session) -> dict[str, int]:
    rows = session.execute(text(
        "SELECT country_code, id FROM dbo.dim_country WHERE is_active = 1"
    )).all()
    return {r[0]: r[1] for r in rows}


def _resolve_vendor_id(session: Session) -> int:
    row = session.execute(text(
        "SELECT id FROM dbo.dim_vendor WHERE vendor_code = :v"
    ), {"v": VENDOR_CODE}).first()
    if row is None:
        raise RuntimeError(f"dim_vendor row for {VENDOR_CODE!r} not found")
    return int(row[0])


# ---------------------------------------------------------------------------
# Upsert
# ---------------------------------------------------------------------------

@dataclass
class UpsertResult:
    parsed: int
    skipped_unknown_country: int
    inserted: int
    updated_actual: int
    updated_other: int
    unchanged: int
    errored: int = 0


# BQL has no tickers, so every row routes through the event_name unique index
# (UX_cb_events_vendor_date_country_event, ticker IS NULL).
_UPSERT_SQL = text("""
MERGE [calendar].[cb_events] AS tgt
USING (
    SELECT
        :vendor_id      AS vendor_id,
        :event_date     AS event_date,
        :event_datetime AS event_datetime,
        :country_id     AS country_id,
        :event_name     AS event_name,
        :category       AS category,
        :survey         AS survey,
        :actual         AS actual,
        :prior_value    AS prior_value,
        :revised        AS revised,
        :relevance      AS relevance,
        :frequency      AS frequency,
        :source         AS source
) AS src
ON  tgt.vendor_id  = src.vendor_id
AND tgt.event_date = src.event_date
AND tgt.country_id = src.country_id
AND tgt.ticker IS NULL
AND tgt.event_name = src.event_name
WHEN MATCHED THEN
    UPDATE SET
        event_datetime = src.event_datetime,
        category       = src.category,
        survey         = src.survey,
        actual         = src.actual,
        prior_value    = src.prior_value,
        revised        = src.revised,
        relevance      = src.relevance,
        frequency      = src.frequency,
        source         = src.source,
        updated_at     = SYSDATETIMEOFFSET()
WHEN NOT MATCHED THEN
    INSERT (
        vendor_id, event_date, event_datetime, country_id, category,
        event_name, ticker, survey, actual, prior_value, revised,
        relevance, frequency, source, is_estimated, created_at, updated_at
    )
    VALUES (
        src.vendor_id, src.event_date, src.event_datetime, src.country_id,
        ISNULL(src.category, 'Unknown'),
        src.event_name, NULL, src.survey, src.actual, src.prior_value,
        src.revised, src.relevance, src.frequency, src.source, 0,
        SYSDATETIMEOFFSET(), SYSDATETIMEOFFSET()
    )
OUTPUT $action AS act,
       deleted.actual AS old_actual,
       inserted.actual AS new_actual;
""")


def upsert_events(
    session: Session,
    events: list[BqlEvent],
    *,
    dry_run: bool = False,
    now_utc: datetime | None = None,
) -> UpsertResult:
    """Idempotent upsert of BQL events into the BBG lane of calendar.cb_events.

    Forward-event guard: an event that has not yet released should not carry an
    ``actual``. We NULL ``actual``/``revised`` when the event is still in the
    future — by ``event_datetime`` when present, else by ``event_date >= today``.
    """
    vendor_id = _resolve_vendor_id(session)
    country_lookup = build_country_lookup(session)
    now = now_utc or datetime.now(timezone.utc)
    today_utc = now.date()

    res = UpsertResult(
        parsed=len(events), skipped_unknown_country=0,
        inserted=0, updated_actual=0, updated_other=0, unchanged=0,
    )

    for e in events:
        country_id = country_lookup.get(_COUNTRY_OVERRIDES.get(e.country_code, e.country_code))
        if country_id is None:
            log.warning("bql.skip_unknown_country", cc=e.country_code, event_name=e.event_name)
            res.skipped_unknown_country += 1
            continue

        if e.event_datetime is not None:
            is_forward = e.event_datetime > now
        else:
            is_forward = e.event_date >= today_utc
        actual_to_store = None if is_forward else e.actual
        revised_to_store = None if is_forward else e.revised

        params = {
            "vendor_id": vendor_id,
            "event_date": e.event_date.isoformat(),
            "event_datetime": e.event_datetime.isoformat() if e.event_datetime else None,
            "country_id": country_id,
            "event_name": e.event_name,
            "category": e.category,
            "survey": e.survey,
            "actual": actual_to_store,
            "prior_value": e.prior_value,
            "revised": revised_to_store,
            "relevance": e.relevance,
            "frequency": e.frequency,
            "source": BQL_SOURCE,
        }

        if dry_run:
            existing = session.execute(text(
                "SELECT actual FROM calendar.cb_events "
                "WHERE vendor_id=:v AND event_date=:d AND country_id=:c "
                "AND event_name=:n AND ticker IS NULL"
            ), {"v": vendor_id, "d": params["event_date"], "c": country_id,
                "n": e.event_name}).first()
            if existing is None:
                res.inserted += 1
            elif (existing[0] or "") != (actual_to_store or ""):
                res.updated_actual += 1
            else:
                res.unchanged += 1
            continue

        # Isolate this row in a SAVEPOINT: one bad row must not roll back —
        # or abort the process on — every other row already upserted in
        # this run. Mirrors te_scraper.upsert_events.
        try:
            with session.begin_nested():
                out = session.execute(_UPSERT_SQL, params).first()
        except SQLAlchemyError as exc:
            log.error(
                "bql.upsert_row_failed",
                event_name=e.event_name,
                event_date=params["event_date"],
                country_id=country_id,
                error=str(exc),
            )
            res.errored += 1
            continue

        if out is None:
            res.unchanged += 1
            continue
        act, old_actual, new_actual = out
        if act == "INSERT":
            res.inserted += 1
        elif (old_actual or "") != (new_actual or ""):
            res.updated_actual += 1
        else:
            res.updated_other += 1

    if not dry_run:
        session.commit()
    return res


# ---------------------------------------------------------------------------
# Top-level orchestration
# ---------------------------------------------------------------------------

def refresh(
    session: Session,
    *,
    db_path: Path | None = None,
    d1: date | None = None,
    d2: date | None = None,
    dry_run: bool = False,
) -> UpsertResult:
    """One refresh cycle: read SQLite (windowed unless d1/d2 are None) -> dedup
    -> upsert. Pass ``d1``/``d2`` for an explicit window; both None reads the
    whole file (full backfill)."""
    db_path = db_path or DEFAULT_DB
    events = read_bql_events(db_path, d1=d1, d2=d2)
    return upsert_events(session, events, dry_run=dry_run)
