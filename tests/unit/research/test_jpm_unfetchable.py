"""Tests for JPM crawler _unfetchable_reason — macro-desk isResearch=N exemption.

2026-06-14: JPM flags macro-desk commentary (Market Intelligence / MACRO
THEMATICS / SSA CB) as isResearch=N even though the content is pre-event
macro analysis.  _unfetchable_reason must NOT drop those rows.

Covers:
* 5 concrete keep examples supplied by the user.
* 3 equity/sector-desk drop examples.
* documentType=Video still drops regardless of title.
* isResearch=Y rows pass through unchanged (isResearch gate never fires).
* Edge cases: empty title, mixed case.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

_RESEARCH_ROOT = Path(__file__).resolve().parents[3] / "playground" / "research"
if str(_RESEARCH_ROOT) not in sys.path:
    sys.path.insert(0, str(_RESEARCH_ROOT))

from ingest.crawler_jpm import ReportRef, _unfetchable_reason  # noqa: E402


# ---------------------------------------------------------------------------
# Minimal fixture factory
# ---------------------------------------------------------------------------

def _ref(
    title: str,
    *,
    is_research: str = "N",
    document_type: str = "Document",
    business_group: str = "",
) -> ReportRef:
    """Build a minimal ReportRef for _unfetchable_reason testing."""
    return ReportRef(
        url="https://markets.jpmorgan.com/jpmm/research.article_page?action=open&doc=GPS-0000000-0",
        pdf_url="https://markets.jpmorgan.com/research/PubServlet?action=open&doc=GPS-0000000-0.pdf",
        uuid="GPS-0000000-0",
        title=title,
        publish_date=date(2026, 6, 14),
        is_research=is_research,
        document_type=document_type,
        business_group=business_group,
    )


# ---------------------------------------------------------------------------
# KEEP: macro-desk series that should NOT be dropped by isResearch=N
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("title", [
    "JPM US Market Intelligence | Macro Week Ahead",
    "JPM US Market Intelligence | Trading CPI",
    "JPM | US MACRO THEMATICS - Morning Quick Hits: deal optimism",
    "JPM | US MACRO THEMATICS - Quick Hits: Less Hot CPI / Continued...",
    "JP Morgan SSA CB - Week in Review 1-5 Jun",
])
def test_macro_desk_is_not_dropped(title: str) -> None:
    """User-supplied keep examples must pass _unfetchable_reason."""
    ref = _ref(title, is_research="N")
    assert _unfetchable_reason(ref) is None, (
        f"Expected {title!r} to be kept (macro desk), but got dropped"
    )


# ---------------------------------------------------------------------------
# KEEP: credit-desk series (2026-07-16, Fold 1c) — isResearch=N but wanted
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("title", [
    "J.P. Morgan Emerging Markets Credit Rundown",
    "JPM EMEA Macro Credit Weekly Commentary #26: (6th - 10th July)",
    "JPM NA Macro Credit Weekly Commentary #26: (6th - 10th July)",
    "JPM Macro Credit Perspectives Call - ST - July 9 2026",
    "JPM Performing Credit (IG/HY) - Recap Week of 7/6",
    "JPMorgan iTraxx Index Vol Commentary",
    "EMEA SOVEREIGN REPO - IF FUNDING SNEEZES, CARRY CATCHES A COLD",
])
def test_credit_desk_is_not_dropped(title: str) -> None:
    """Named JPM credit-desk series must pass _unfetchable_reason despite
    isResearch=N (Fold 1c MACRO_DESK_KEEP extension)."""
    ref = _ref(title, is_research="N")
    assert _unfetchable_reason(ref) is None, (
        f"Expected credit-desk {title!r} to be kept, but got dropped"
    )


@pytest.mark.parametrize("title", [
    "JPM International Market Intelligence | Morning Briefing",
    "JPM US Market Intelligence | Morning Briefing",
    "JPM US Market Intelligence | Afternoon Briefing",
])
def test_market_intelligence_variants_not_dropped(title: str) -> None:
    """All Market Intelligence sub-series (US, International, AM/PM) pass."""
    ref = _ref(title, is_research="N")
    assert _unfetchable_reason(ref) is None


def test_macro_thematics_case_insensitive() -> None:
    """The regex is case-insensitive: 'US Macro Thematics' variant passes."""
    ref = _ref("JPM | US Macro Thematics - Proceed with caution", is_research="N")
    assert _unfetchable_reason(ref) is None


def test_ssa_cb_case_insensitive() -> None:
    ref = _ref("JP Morgan SSA CB - Week in Review 8-12 Jun", is_research="N")
    assert _unfetchable_reason(ref) is None


# ---------------------------------------------------------------------------
# DROP: equity / sector-desk rows that must still be dropped
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("title", [
    # From user directive — confirmed drop examples
    "JPM | APAC FINANCIALS - Japan Banks (BoJ), China ODI ...",
    "JPM: Chips for Breakfast - WWDC Preview, ANET Suggestions, ...",
    "JPM | BEST OF BRITISH - Burnham Watch, Fiscal big picture, AI ...",
    # EOD desk commentary
    "NY Crude EOD",
    "BRL EOD Commentary - 12 Jun 2026",
    "Chile Rates EOD ***10y CLP vs 10y SOFR***",
    "MXN Rates EOD",
    "Colombia EoD Jun-12",
    "Argentina EOD",
    # Sector / equity desks
    "JPM | US Healthcare: IMNM, UPB, Biotech Catalyst Tracker",
    "JPM | US Fins Daily - My 2c...",
    "JPM | US Consumer Daily: KTB Initiate at OW",
    "JPM | EU Financials: Global IBs - Stay Positive",
    "JPM | EU Oil & Gas Early Riser: REP",
    "JPM | Industrial Strength Morning Messages: Trump pulls back",
    "JPM | Silver Sunrise Euro TMT Daily: Nokia, Adyen, SAP",
    "JPM TECH SKETCH: GOOGL Launches UBER One (Sorta)",
    "JPM | EMEA Spec Sits Daily: ITRK LN, CBK GY",
    "JPM | Industrial Spec Sales - Sunday Machinations",
    "JPM | UK FINANCIALS: Seeing Red",
    # Sales / admin
    "Read this, Listen to that",
    "Through The Retail Lens",
    "JPM NA Rates Sales Daily (06/11)",
    "JPM PI - Weekly Wrap",
    "Data Insights",
])
def test_non_macro_desk_still_dropped(title: str) -> None:
    """isResearch=N rows outside the macro-desk exemption must still drop."""
    ref = _ref(title, is_research="N")
    reason = _unfetchable_reason(ref)
    assert reason == "isResearch=N", (
        f"Expected {title!r} to drop with 'isResearch=N', got {reason!r}"
    )


# ---------------------------------------------------------------------------
# Video always drops, regardless of title
# ---------------------------------------------------------------------------

def test_video_drops_even_with_macro_title() -> None:
    """documentType=Video trumps any macro-desk title exemption."""
    ref = _ref(
        "JPM US Market Intelligence | Macro Week Ahead",
        is_research="N",
        document_type="Video",
    )
    assert _unfetchable_reason(ref) == "documentType=Video"


def test_video_drops_on_research_y_too() -> None:
    ref = _ref("Flows & Liquidity", is_research="Y", document_type="Video")
    assert _unfetchable_reason(ref) == "documentType=Video"


# ---------------------------------------------------------------------------
# isResearch=Y rows pass through regardless
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("title", [
    "Global Data Watch",
    "US Weekly Prospects",
    "Credit Market Outlook & Strategy",
])
def test_is_research_y_passes_through(title: str) -> None:
    ref = _ref(title, is_research="Y")
    assert _unfetchable_reason(ref) is None


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_empty_title_drops() -> None:
    """Empty title: isResearch=N should still drop (no macro pattern match)."""
    ref = _ref("", is_research="N")
    assert _unfetchable_reason(ref) == "isResearch=N"


def test_market_intelligence_mixed_case() -> None:
    ref = _ref("JPM US MARKET INTELLIGENCE | Morning Briefing", is_research="N")
    assert _unfetchable_reason(ref) is None


def test_title_only_containing_market_word_still_drops() -> None:
    """'market' alone does not trigger the exemption — needs 'market intelligence'."""
    ref = _ref("Global Market Outlook", is_research="N")
    assert _unfetchable_reason(ref) == "isResearch=N"
