"""Tests for ``imdr.market_calendar.cb_events`` query helpers.

The 3 simple filter helpers (``upcoming_cb_events``, ``recent_cb_events``,
``rate_decisions``) used to filter on ``CBEvent.country_code``. Phase H sub-
step 5.3 (2026-05-13) migrated them to ``country_id`` via a
``_resolve_country_id`` lookup against ``dbo.dim_country``. These tests lock
in the resolve-then-filter behaviour, including the unknown-country
short-circuit.

``events_for_currency`` is more interesting — it composes 3 raw SQL queries
and an ORM query. It already used ``country_id`` (rewritten in Phase D Step 4
to fix a latent bug). These tests mock ``session.execute`` / ``session.query``
to lock in:

  1. unknown currency → ``[]`` (no events, no FX, no curves queried)
  2. known currency, no events → ``[]`` (FX/curves queries skipped)
  3. known currency with events → returns dicts with FX pairs + curves
"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import pytest

from imdr.market_calendar import cb_events as cb_mod
from imdr.models.calendar import CBEvent


@pytest.fixture
def jpy_event():
    """A canned CBEvent for tests (country_id=26 for JP)."""
    e = CBEvent()
    e.id = 1
    e.event_date = date(2026, 6, 16)
    e.country_id = 26
    e.event_name = "BOJ Target Rate"
    e.category = "Central Banks"
    e.is_estimated = False
    return e


def _stub_session(
    *,
    currency_row: tuple | None,
    events: list,
    fx_rows: list[tuple] = (),
    curve_rows: list[tuple] = (),
) -> MagicMock:
    """Build a mock session for events_for_currency.

    Call order inside events_for_currency:
      1. execute("SELECT id, country_id FROM dim_currency …") → first() returns currency_row
      2. session.query(CBEvent).filter(...).order_by(...).all() → events
      3. execute("SELECT base_ccy, quote_ccy FROM dim_currency_pair …") → fetchall() → fx_rows
      4. execute("SELECT ccy, curve, curve_type FROM dim_curve …") → fetchall() → curve_rows
    """
    currency_result = MagicMock()
    currency_result.first.return_value = currency_row
    fx_result = MagicMock()
    fx_result.fetchall.return_value = list(fx_rows)
    curve_result = MagicMock()
    curve_result.fetchall.return_value = list(curve_rows)

    # session.execute returns results in the call order above (excluding currency_row=None short-circuit).
    if currency_row is None:
        execute_results = [currency_result]
    else:
        execute_results = [currency_result, fx_result, curve_result]

    # ORM query chain: session.query(CBEvent).filter(...).filter(...).filter(...).order_by(...).all()
    query_chain = MagicMock()
    query_chain.filter.return_value = query_chain
    query_chain.order_by.return_value = query_chain
    query_chain.all.return_value = events

    session = MagicMock()
    session.execute.side_effect = execute_results
    session.query.return_value = query_chain
    return session


class TestEventsForCurrency:
    def test_unknown_currency_short_circuits(self):
        """If dim_currency has no row for the ccy, return [] without touching anything else."""
        s = _stub_session(currency_row=None, events=[])
        result = cb_mod.events_for_currency(s, "XYZ", days_ahead=30)
        assert result == []
        # Only the currency lookup was executed.
        assert s.execute.call_count == 1
        assert s.query.call_count == 0

    def test_known_currency_no_events(self, jpy_event):
        """If the country has no upcoming events, FX/curve queries are skipped."""
        s = _stub_session(
            currency_row=(18, 26),  # JPY id=18, country_id=26
            events=[],
        )
        result = cb_mod.events_for_currency(s, "JPY", days_ahead=30)
        assert result == []
        # Only the currency lookup; FX/curve queries never run because events is empty.
        assert s.execute.call_count == 1

    def test_known_currency_with_events_returns_dicts(self, jpy_event):
        s = _stub_session(
            currency_row=(18, 26),
            events=[jpy_event],
            fx_rows=[("USD", "JPY"), ("EUR", "JPY")],
            curve_rows=[
                ("JPY", "TONAR", "rfr"),
                ("JPY", "JPY_LIBOR", "ibor"),
            ],
        )
        result = cb_mod.events_for_currency(s, "JPY", days_ahead=30)
        assert len(result) == 1
        row = result[0]
        assert row["event"] is jpy_event
        assert row["affected_fx_pairs"] == ["USD/JPY", "EUR/JPY"]
        assert row["affected_curves"] == [
            "JPY TONAR (rfr)",
            "JPY JPY_LIBOR (ibor)",
        ]

    def test_lowercase_ccy_is_uppercased(self, jpy_event):
        """The currency lookup should normalize case."""
        s = _stub_session(currency_row=(18, 26), events=[jpy_event])
        cb_mod.events_for_currency(s, "jpy", days_ahead=30)
        first_call_kwargs = s.execute.call_args_list[0]
        params = first_call_kwargs.args[1]
        assert params == {"ccy": "JPY"}

    def test_confirmed_only_propagates(self, jpy_event):
        """When confirmed_only=True, the ORM filter chain gets an extra is_estimated check."""
        s = _stub_session(currency_row=(18, 26), events=[jpy_event])
        cb_mod.events_for_currency(s, "JPY", days_ahead=30, confirmed_only=True)
        s.query.assert_called_once_with(CBEvent)
        # filter() chained ≥4 times: date >=, date <=, country_id ==, is_estimated
        assert s.query.return_value.filter.call_count >= 4


# ── Filter helpers: country_code → country_id migration (Phase H 5.3) ────


def _stub_for_filter_helper(
    events: list,
    country_id: int | None = 1,
) -> MagicMock:
    """Mock a session for the 3 filter helpers.

    The helper's first call is ``_resolve_country_id`` which does
    ``session.execute(SELECT id FROM dim_country WHERE country_code=...)``
    and reads ``.first()``. If ``country_id`` is None, the resolver returns
    None and the filter helper short-circuits.
    """
    resolve_result = MagicMock()
    resolve_result.first.return_value = (country_id,) if country_id is not None else None
    query_chain = MagicMock()
    query_chain.filter.return_value = query_chain
    query_chain.order_by.return_value = query_chain
    query_chain.all.return_value = events
    session = MagicMock()
    session.execute.return_value = resolve_result
    session.query.return_value = query_chain
    return session


class TestFilterHelpersResolveCountryId:
    """The 3 filter helpers must resolve country_code → country_id and filter on the FK."""

    def test_upcoming_resolves_country_code(self):
        s = _stub_for_filter_helper(events=[], country_id=1)
        cb_mod.upcoming_cb_events(s, country_code="us")
        # Resolver call: SELECT id FROM dim_country WHERE country_code = :cc (uppercased)
        resolve_call = s.execute.call_args
        params = resolve_call.args[1]
        assert params == {"cc": "US"}
        # ORM filter chain: date >=, date <=, country_id ==
        assert s.query.return_value.filter.call_count == 3

    def test_recent_resolves_country_code(self):
        s = _stub_for_filter_helper(events=[], country_id=26)
        cb_mod.recent_cb_events(s, country_code="jp")
        params = s.execute.call_args.args[1]
        assert params == {"cc": "JP"}
        assert s.query.return_value.filter.call_count == 3

    def test_rate_decisions_resolves_country_code(self):
        s = _stub_for_filter_helper(events=[], country_id=2)
        cb_mod.rate_decisions(s, country_code="eu")
        params = s.execute.call_args.args[1]
        assert params == {"cc": "EU"}
        # Baseline filters (date >=, date <=, ticker not null, relevance > 50) + country_id == 5
        assert s.query.return_value.filter.call_count >= 5

    def test_unknown_country_returns_empty_list(self):
        """If dim_country doesn't have the code, short-circuit with []."""
        s = _stub_for_filter_helper(events=[], country_id=None)
        result = cb_mod.upcoming_cb_events(s, country_code="ZZZ")
        assert result == []
        # The ORM query was never started because we short-circuit at resolve.
        assert s.query.call_count == 0

    def test_country_code_none_skips_filter_and_resolver(self):
        """country_code=None must not call the resolver or add a country filter."""
        s = _stub_for_filter_helper(events=[])
        cb_mod.upcoming_cb_events(s, country_code=None)
        # No execute call (resolver skipped).
        assert s.execute.call_count == 0
        # Only the 2 date filters apply.
        assert s.query.return_value.filter.call_count == 2
