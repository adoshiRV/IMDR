"""Tests for classifiers/db.py — macro-desk reclassification.

Pins the 2026-06-18 fix: DB files its economics / central-bank / EM-macro
desks under the EQUITY (`EQ`/`REC`/`TP`) topic template, so they were
classified EQUITY and then blanket-dropped by relevance.py's DB-EQUITY
default-drop — silently losing the entire "Fed Notes" Fed-watching series
(FOMC previews/recaps), "China Macro", "Asia Macro Insight", "Japan
Monetary Policy Watch", "RBA Blog", etc.

`classify()` must now force MACRO for those, and that MACRO result must
survive `relevance.is_single_name_equity` (end-to-end keep).

All example titles/series are taken verbatim from logs/research_ingest_*
[DROP] lines for vendor `db`.

Run::

    python -m pytest tests/unit/research/test_db_classifier.py -v
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import pytest

_RESEARCH_ROOT = Path(__file__).resolve().parents[3] / "playground" / "research"
if str(_RESEARCH_ROOT) not in sys.path:
    sys.path.insert(0, str(_RESEARCH_ROOT))

from ingest.classifiers.db import classify, _is_macro_series, _desk_override  # noqa: E402
from ingest.classifiers.canonical import (  # noqa: E402
    ASSET_CLASS_COMMODITIES,
    ASSET_CLASS_CREDIT,
    ASSET_CLASS_EQUITY,
    ASSET_CLASS_FX,
    ASSET_CLASS_MACRO,
    ASSET_CLASS_RATES,
)
from ingest.relevance import is_single_name_equity  # noqa: E402


# ---------------------------------------------------------------------------
# Minimal stubs mirroring the crawler_db dataclasses (avoids importing the
# crawler, which requires playwright).
# ---------------------------------------------------------------------------

@dataclass
class _Topic:
    name: str = ""
    template: str = ""
    id: str = ""


@dataclass
class _Company:
    name: str = ""
    symbol: str = ""
    is_primary: bool = False


@dataclass
class _Ref:
    title: str
    periodical_name: str = ""
    product_type: str = "Report"
    region: str = "Global"
    synopsis: str = ""
    page_count: int = 4
    topics: tuple = ()
    analysts: tuple = ()
    companies: tuple = ()
    publish_date: date = date(2026, 6, 17)
    uuid: str = "test-rid-604"


# Topic with the EQUITY template — the exact mis-filing that caused the
# losses (DB tags economics desks with the equity reporting template).
# `_EQ` carries a macro topic NAME ("US Economics") as real Fed Notes do;
# `_EQ_SECTOR` is a plain equity-sector topic (no macro/FX/commodity
# vocab) for the regressions that must STAY equity.
_EQ = (_Topic(name="US Economics", template="EQ"),)
_EQ_SECTOR = (_Topic(name="", template="EQ"),)


# ---------------------------------------------------------------------------
# _is_macro_series — the desk-identity signal
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("periodical", [
    "Fed Notes",
    "China Macro",
    "Latam Macro Notes",
    "Asia Macro Insight",
    "India Economics Weekly",
    "Japan Monetary Policy Watch",
    "RBA Blog",
    "US Economic Perspectives",
])
def test_is_macro_series_true_on_macro_desks(periodical):
    assert _is_macro_series(periodical, (), "") is True


@pytest.mark.parametrize("periodical", [
    "European Chemicals",
    "Global Autos Daily",
    "Gaming",
    "U.S. Lodging Industry",
    "Online Brokers",
    "Covered Bonds and SSA Update",
])
def test_is_macro_series_false_on_equity_and_credit_desks(periodical):
    assert _is_macro_series(periodical, (), "") is False


def test_is_macro_series_excludes_bare_outlook():
    # "outlook" is deliberately NOT a macro token — overlaps equity wraps.
    assert _is_macro_series("Auto Sector Outlook", (), "") is False


def test_is_macro_series_matches_via_title_when_periodical_empty():
    assert _is_macro_series("", (), "Fed Notes: June FOMC recap") is True


# ---------------------------------------------------------------------------
# classify() — EQUITY-template macro desks become MACRO
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("title,periodical", [
    ("Fed Notes: June FOMC recap: Rock Chalk, Warsh-hawk", "Fed Notes"),
    ("Fed Notes: June FOMC preview: Warsh-ing their hands", "Fed Notes"),
    ("Asia Macro Insight: Further rate hikes ahead", "Asia Macro Insight"),
    ("China Macro: May activity: deepening K-shaped divide", "China Macro"),
    ("MPM review: an initial dovish read", "Japan Monetary Policy Watch"),
    ("Cash rate on hold as expected", "RBA Blog"),
    ("Peru – Another strong growth print", "Latam Macro Notes"),
])
def test_macro_desk_filed_under_eq_template_becomes_macro(title, periodical):
    ref = _Ref(title=title, periodical_name=periodical, topics=_EQ)
    assert classify(ref).asset_class == ASSET_CLASS_MACRO


# ---------------------------------------------------------------------------
# classify() — FX & commodity desks mis-filed under EQ
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("title,periodical", [
    ("Antipodean central bank risks and a Middle-East premium", "FX Blog"),
    ("Chinese capital returns to Australia", "FX Blog"),
    ("FX Valuation Snapshot (May 2026)", "FX Valuation Snapshot"),
])
def test_fx_desk_filed_under_eq_becomes_fx(title, periodical):
    # FX wins over macro even when the title is central-bank flavoured —
    # the periodical is the desk of record.
    ref = _Ref(title=title, periodical_name=periodical, topics=_EQ)
    assert classify(ref).asset_class == ASSET_CLASS_FX


def test_commodity_desk_hsueh_on_oil_becomes_commodities():
    ref = _Ref(title="New data points", periodical_name="Hsueh On Oil", topics=_EQ)
    assert classify(ref).asset_class == ASSET_CLASS_COMMODITIES


@pytest.mark.parametrize("title,periodical", [
    # Equity-SECTOR commodity coverage — must STAY equity (correctly dropped).
    ("Chile production falls sharply in April", "Global Copper"),
    ("Vale site trip. Copper: US tariffs", "EMEA Metals & Mining"),
    ("Sector update", "India Oil and Gas"),
    ("2Q26 results", "Grupo Mexico & Southern Copper"),
    ("ENN Q4 beat", "ENN Energy & ENN Natural Gas"),
    ("Time to revisit?", "China City-gas Utilities"),
])
def test_equity_sector_commodity_coverage_stays_equity(title, periodical):
    ref = _Ref(title=title, periodical_name=periodical, topics=_EQ_SECTOR)
    assert classify(ref).asset_class == ASSET_CLASS_EQUITY


def test_cryptocurrency_markets_not_misrouted_to_fx():
    # "\bcurrenc" must not match inside "cryptocurrency" (no word boundary).
    ref = _Ref(title="Weekly", periodical_name="Cryptocurrency Markets",
               topics=_EQ_SECTOR)
    assert classify(ref).asset_class == ASSET_CLASS_EQUITY


def test_desk_override_returns_empty_when_no_desk_signal():
    assert _desk_override("European Chemicals", (), "Petrochemical prices") == ""


def test_genuine_equity_single_name_stays_equity():
    """Regression: a real equity coverage note must NOT be reclassified."""
    ref = _Ref(
        title="Jupiter: Changing gear? A detailed review",
        periodical_name="European Asset Managers",
        topics=(_Topic(name="European Asset Managers", template="EQ"),),
        companies=(_Company(name="Jupiter", symbol="JUP.L", is_primary=True),),
    )
    assert classify(ref).asset_class == ASSET_CLASS_EQUITY


def test_credit_note_not_touched_by_macro_override():
    """FI-template credit note stays CREDIT (override only fires on
    EQUITY/empty, so CREDIT is never clobbered)."""
    ref = _Ref(
        title="European HY one-stop: Weekly Earnings and Event Calendar",
        periodical_name="European HY one-stop",
        topics=(_Topic(name="European High Yield Credit", template="FI"),),
    )
    assert classify(ref).asset_class == ASSET_CLASS_CREDIT


def test_rates_note_not_touched_by_macro_override():
    """FI-template rates note stays RATES."""
    ref = _Ref(
        title="Covered Bonds and SSA Update: EUR benchmark CB supply",
        periodical_name="Covered Bonds and SSA Update",
        topics=(_Topic(name="European Covered Bonds", template="FI"),),
    )
    assert classify(ref).asset_class == ASSET_CLASS_RATES


# ---------------------------------------------------------------------------
# End-to-end: classifier MACRO result survives the relevance filter
# ---------------------------------------------------------------------------

def test_fed_notes_recap_survives_relevance_end_to_end():
    ref = _Ref(
        title="Fed Notes: June FOMC recap: Rock Chalk, Warsh-hawk",
        periodical_name="Fed Notes",
        topics=_EQ,
    )
    result = classify(ref)
    assert result.asset_class == ASSET_CLASS_MACRO
    drop, reason = is_single_name_equity(
        vendor_code="db", result=result, title=ref.title,
    )
    assert drop is False, f"Fed Notes recap must be KEPT, got drop reason {reason!r}"


def test_pre_fix_behaviour_would_have_dropped():
    """Documents the bug: the SAME ref classified as EQUITY (the pre-fix
    behaviour) IS dropped by relevance — proving the classifier fix is what
    rescues it."""
    from ingest.classifiers.models import ClassifyResult
    as_equity = ClassifyResult(
        asset_class=ASSET_CLASS_EQUITY, country_code="US", tags=[], context="",
    )
    drop, reason = is_single_name_equity(
        vendor_code="db", result=as_equity,
        title="Fed Notes: June FOMC recap: Rock Chalk, Warsh-hawk",
    )
    assert drop is True
    assert reason == "equity-vendor-default-drop"
