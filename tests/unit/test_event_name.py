"""Unit tests for imdr.market_calendar.event_name.normalize_event_name.

Regression for the 2026-07 TE calendar-refresh abort: TE event id 420801
(2026-07-10, country_id 17) alternated between an accented rendered-text
fallback ("ecb vujčić speech") and its plain-ASCII data-event slug
("ecb vujcic speech"). Both must normalize to the exact same string so the
shared upsert path (te_scraper + bql_econdata) always MATCHes the existing
row on calendar.cb_events' accent/case-insensitive unique index instead of
attempting a colliding INSERT.
"""
from __future__ import annotations

from imdr.market_calendar.event_name import normalize_event_name


def test_accented_and_plain_spelling_normalize_identically():
    assert normalize_event_name("ecb vujčić speech") == normalize_event_name("ecb vujcic speech")
    assert normalize_event_name("ecb vujčić speech") == "ecb vujcic speech"


def test_case_variants_normalize_identically():
    assert normalize_event_name("ECB Interest Rate Decision") == "ecb interest rate decision"
    assert (
        normalize_event_name("Ecb Interest Rate Decision")
        == normalize_event_name("ecb interest rate decision")
    )


def test_leading_trailing_whitespace_stripped():
    assert normalize_event_name("  gdp mom prel  ") == "gdp mom prel"


def test_already_canonical_is_unchanged():
    assert normalize_event_name("inflation rate yoy") == "inflation rate yoy"


def test_distinct_events_stay_distinct():
    assert normalize_event_name("gdp mom prel") != normalize_event_name("gdp qoq prel")
