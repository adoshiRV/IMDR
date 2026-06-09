"""Query helpers for calendar.cb_events — upcoming and recent CB events.

Phase H sub-step 5.3 (2026-05-13): the legacy ``cb_events.country_code``
varchar(5) column is being dropped (migration 051). All filter helpers now
resolve ``country_code`` → ``country_id`` via ``dbo.dim_country`` and filter
on the FK column. An unknown country_code returns ``[]`` rather than
matching zero rows silently.

:func:`events_for_currency` was rewritten on the country-anchor chain in
Step 4 (Phase D) and already used ``country_id``; no change here.
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

from imdr.models.calendar import CBEvent


def _resolve_country_id(session: Session, country_code: str) -> int | None:
    """Return ``dbo.dim_country.id`` for the given country_code, or None if unknown.

    Case-insensitive on input — the canonical column is uppercase
    (``US``, ``UK``, ``EU``, …).
    """
    row = session.execute(
        text("SELECT id FROM [dbo].[dim_country] WHERE country_code = :cc"),
        {"cc": country_code.upper()},
    ).first()
    return int(row[0]) if row else None


def upcoming_cb_events(
    session: Session,
    country_code: str | None = None,
    days_ahead: int = 30,
    confirmed_only: bool = False,
) -> list[CBEvent]:
    """Query DB for upcoming CB events, optionally filtered by country code.

    ``country_code`` is the canonical business key (``US``, ``UK``, ``EU``,
    etc.). It's resolved to ``dim_country.id`` and the filter runs on
    ``cb_events.country_id``. An unknown country code returns ``[]``.
    """
    today = date.today()
    end = today + timedelta(days=days_ahead)

    if country_code:
        country_id = _resolve_country_id(session, country_code)
        if country_id is None:
            return []
    else:
        country_id = None

    query = (
        session.query(CBEvent)
        .filter(CBEvent.event_date >= today)
        .filter(CBEvent.event_date <= end)
    )
    if country_id is not None:
        query = query.filter(CBEvent.country_id == country_id)
    if confirmed_only:
        query = query.filter(CBEvent.is_estimated == False)  # noqa: E712

    return query.order_by(CBEvent.event_date, CBEvent.event_datetime).all()


def recent_cb_events(
    session: Session,
    country_code: str | None = None,
    days_back: int = 30,
) -> list[CBEvent]:
    """Query DB for recent CB events, optionally filtered by country code."""
    today = date.today()
    start = today - timedelta(days=days_back)

    if country_code:
        country_id = _resolve_country_id(session, country_code)
        if country_id is None:
            return []
    else:
        country_id = None

    query = (
        session.query(CBEvent)
        .filter(CBEvent.event_date >= start)
        .filter(CBEvent.event_date < today)
    )
    if country_id is not None:
        query = query.filter(CBEvent.country_id == country_id)

    return query.order_by(CBEvent.event_date.desc(), CBEvent.event_datetime.desc()).all()


def rate_decisions(
    session: Session,
    country_code: str | None = None,
    days_back: int = 90,
    days_ahead: int = 90,
    confirmed_only: bool = False,
) -> list[CBEvent]:
    """Query for rate decision events specifically (high-relevance ticker-based events)."""
    today = date.today()
    start = today - timedelta(days=days_back)
    end = today + timedelta(days=days_ahead)

    if country_code:
        country_id = _resolve_country_id(session, country_code)
        if country_id is None:
            return []
    else:
        country_id = None

    query = (
        session.query(CBEvent)
        .filter(CBEvent.event_date >= start)
        .filter(CBEvent.event_date <= end)
        .filter(CBEvent.ticker.isnot(None))
        .filter(CBEvent.relevance > 50.0)
    )
    if country_id is not None:
        query = query.filter(CBEvent.country_id == country_id)
    if confirmed_only:
        query = query.filter(CBEvent.is_estimated == False)  # noqa: E712

    return query.order_by(CBEvent.event_date).all()


def events_for_currency(
    session: Session,
    ccy: str,
    days_ahead: int = 30,
    confirmed_only: bool = False,
) -> list[dict]:
    """Find CB events for a currency, including affected FX pairs and rates curves.

    Resolves the currency to its owning country via ``dim_currency.country_id``
    (a country may own several currencies — e.g. ``CN`` owns ``CNY``, ``CNH``,
    ``CNO``; this query uses the country derived from the currency the caller
    passed in). Then:

    * filters ``cb_events`` rows whose ``country_id`` matches that country;
    * finds FX pairs where either leg's currency is the input ccy
      (``base_currency_id`` or ``quote_currency_id`` matches);
    * finds rates curves anchored to that country
      (``dim_curve.country_id``).

    Returns list of dicts::

        {
            "event": CBEvent,
            "affected_fx_pairs": list[str],   # e.g. ["USD/JPY"]
            "affected_curves": list[str],     # e.g. ["JPY TONAR (rfr)"]
        }

    Empty list if the currency is unknown or no events match.
    """
    today = date.today()
    end = today + timedelta(days=days_ahead)

    # 1. Resolve currency → (currency_id, country_id) via dim_currency.
    row = session.execute(
        text("""
            SELECT id, country_id
            FROM [dbo].[dim_currency]
            WHERE code = :ccy
        """),
        {"ccy": ccy.upper()},
    ).first()
    if row is None:
        return []
    currency_id, country_id = row

    # 2. CB events for the country.
    query = (
        session.query(CBEvent)
        .filter(CBEvent.event_date >= today)
        .filter(CBEvent.event_date <= end)
        .filter(CBEvent.country_id == country_id)
    )
    if confirmed_only:
        query = query.filter(CBEvent.is_estimated == False)  # noqa: E712

    events = query.order_by(CBEvent.event_date).all()
    if not events:
        return []

    # 3. FX pairs with this currency on either leg.
    fx_rows = session.execute(
        text("""
            SELECT base_ccy, quote_ccy
            FROM [fx].[dim_currency_pair]
            WHERE base_currency_id = :cid OR quote_currency_id = :cid
            ORDER BY base_ccy, quote_ccy
        """),
        {"cid": currency_id},
    ).fetchall()
    fx_pairs = [f"{r[0]}/{r[1]}" for r in fx_rows]

    # 4. Rates curves anchored to this country (country owns multiple currencies;
    #    the original semantics filtered to the country, not the specific ccy).
    curve_rows = session.execute(
        text("""
            SELECT ccy, curve, curve_type
            FROM [rates].[dim_curve]
            WHERE country_id = :cid
            ORDER BY ccy, curve
        """),
        {"cid": country_id},
    ).fetchall()
    curves = [f"{r[0]} {r[1]} ({r[2]})" for r in curve_rows]

    return [
        {
            "event": e,
            "affected_fx_pairs": fx_pairs,
            "affected_curves": curves,
        }
        for e in events
    ]
