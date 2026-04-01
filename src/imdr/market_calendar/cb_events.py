"""Query helpers for calendar.cb_events — upcoming and recent CB events."""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

from imdr.models.calendar import CBEvent


def upcoming_cb_events(
    session: Session,
    market_code: str | None = None,
    days_ahead: int = 30,
    confirmed_only: bool = False,
) -> list[CBEvent]:
    """Query DB for upcoming CB events, optionally filtered by market code."""
    today = date.today()
    end = today + timedelta(days=days_ahead)

    query = (
        session.query(CBEvent)
        .filter(CBEvent.event_date >= today)
        .filter(CBEvent.event_date <= end)
    )
    if market_code:
        query = query.filter(CBEvent.country_code == market_code)
    if confirmed_only:
        query = query.filter(CBEvent.is_estimated == False)  # noqa: E712

    return query.order_by(CBEvent.event_date, CBEvent.event_datetime).all()


def recent_cb_events(
    session: Session,
    market_code: str | None = None,
    days_back: int = 30,
) -> list[CBEvent]:
    """Query DB for recent CB events, optionally filtered by market code."""
    today = date.today()
    start = today - timedelta(days=days_back)

    query = (
        session.query(CBEvent)
        .filter(CBEvent.event_date >= start)
        .filter(CBEvent.event_date < today)
    )
    if market_code:
        query = query.filter(CBEvent.country_code == market_code)

    return query.order_by(CBEvent.event_date.desc(), CBEvent.event_datetime.desc()).all()


def rate_decisions(
    session: Session,
    market_code: str | None = None,
    days_back: int = 90,
    days_ahead: int = 90,
    confirmed_only: bool = False,
) -> list[CBEvent]:
    """Query for rate decision events specifically (high-relevance ticker-based events)."""
    today = date.today()
    start = today - timedelta(days=days_back)
    end = today + timedelta(days=days_ahead)

    query = (
        session.query(CBEvent)
        .filter(CBEvent.event_date >= start)
        .filter(CBEvent.event_date <= end)
        .filter(CBEvent.ticker.isnot(None))
        .filter(CBEvent.relevance > 50.0)
    )
    if market_code:
        query = query.filter(CBEvent.country_code == market_code)
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

    Joins through dim_market_currency to find the market, then returns
    CB events plus lists of affected instruments.

    Returns list of dicts:
        {
            "event": CBEvent,
            "affected_fx_pairs": list[str],  # e.g. ["USD/JPY"]
            "affected_curves": list[str],    # e.g. ["JPY TONAR (OIS)"]
        }
    """
    today = date.today()
    end = today + timedelta(days=days_ahead)

    # Find market codes for this currency
    rows = session.execute(
        text("""
            SELECT market_code FROM [calendar].[dim_market_currency]
            WHERE ccy = :ccy
        """),
        {"ccy": ccy},
    ).fetchall()
    market_codes = [r[0] for r in rows]

    if not market_codes:
        return []

    # Get CB events for these markets
    query = (
        session.query(CBEvent)
        .filter(CBEvent.event_date >= today)
        .filter(CBEvent.event_date <= end)
        .filter(CBEvent.country_code.in_(market_codes))
    )
    if confirmed_only:
        query = query.filter(CBEvent.is_estimated == False)  # noqa: E712

    events = query.order_by(CBEvent.event_date).all()

    if not events:
        return []

    # Find affected FX pairs
    fx_rows = session.execute(
        text("""
            SELECT base_ccy, quote_ccy, market_code
            FROM [fx].[dim_currency_pair]
            WHERE market_code IN :mcs
        """).bindparams(mcs=tuple(market_codes)),
    ).fetchall() if market_codes else []
    fx_pairs = [f"{r[0]}/{r[1]}" for r in fx_rows]

    # Find affected rates curves
    curve_rows = session.execute(
        text("""
            SELECT ccy, curve, curve_type
            FROM [rates].[dim_curve]
            WHERE market_code IN :mcs
        """).bindparams(mcs=tuple(market_codes)),
    ).fetchall() if market_codes else []
    curves = [f"{r[0]} {r[1]} ({r[2]})" for r in curve_rows]

    return [
        {
            "event": e,
            "affected_fx_pairs": fx_pairs,
            "affected_curves": curves,
        }
        for e in events
    ]
