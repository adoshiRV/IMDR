"""Tests for is_single_name_equity — JPM EQUITY branch.

Pins the 2026-06-15 tightening:
  - FTM wraps drop (``ftm`` token removed from _JPM_EQUITY_KEEP)
  - ``forecast`` token removed (equity-sector forecasts no longer kept)
  - ``derivatives`` token removed (equity-derivatives strategy no longer kept)
  - _JPM_INDUSTRY_DROP gains 5 new entries: china/japan quant strategy,
    equity/tactical derivatives strategy, technology outlook
  - Known macro-adjacent titles still pass (strategy, cross-asset, positioning,
    monthly/weekly/daily wrap, model portfolio, earnings season, etc.)

For relevance-branch tests, the MI/THEMATICS titles are kept via
MACRO_DESK_KEEP *before* asset_class is consulted, so we don't need
to reach this module for them — they are covered in test_jpm_filters.py.
Here we focus on EQUITY-classified docs, constructing ClassifyResult with
asset_class=EQUITY and n_tickers=0 (multi-name or no ticker = realistic
for the sector/strategy wraps we're testing).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_RESEARCH_ROOT = Path(__file__).resolve().parents[3] / "playground" / "research"
if str(_RESEARCH_ROOT) not in sys.path:
    sys.path.insert(0, str(_RESEARCH_ROOT))

from ingest.classifiers.canonical import ASSET_CLASS_EQUITY  # noqa: E402
from ingest.classifiers.models import ClassifyResult  # noqa: E402
from ingest.relevance import is_single_name_equity  # noqa: E402


def _equity_result(n_tickers: int = 0) -> ClassifyResult:
    """Minimal ClassifyResult for a JPM EQUITY doc with no single-name signal."""
    from ingest.classifiers.models import Tag
    tags = [Tag(category="ticker", value=f"T{i}") for i in range(n_tickers)]
    return ClassifyResult(asset_class=ASSET_CLASS_EQUITY, tags=tags)


# ---------------------------------------------------------------------------
# DROP NOW — titles that should no longer survive the JPM EQUITY branch
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("title", [
    # FTM wraps (``ftm`` token removed)
    "J.P. Morgan U.S. FTM 10 Jun 26",
    "JPM | FTM | Today's Research | CEEMEA",
    "J.P. Morgan Europe FTM",
    "JPM | FTM | Asia Pacific Morning",
    # _JPM_INDUSTRY_DROP new entries
    "China Quant Strategy",
    "Japan Quant Strategy",
    "European Equity Derivatives Strategy",
    "US Tactical Derivatives Strategy",
    "Asia Pacific Equity Derivatives Strategy",
    # ``derivatives`` token removed — "Derivatives Exchanges" data tables
    "Derivatives Exchanges",
    # ``forecast`` token removed — equity-sector forecasts
    "S&P Global Mobility Forecast Update",
    # _JPM_INDUSTRY_DROP: technology outlook
    "Asia Technology Outlook",
    "Japan Technology Outlook — 2026",
])
def test_jpm_equity_drops(title: str) -> None:
    """These titles must be dropped by the JPM EQUITY branch."""
    drop, reason = is_single_name_equity(
        vendor_code="jpm",
        result=_equity_result(n_tickers=0),
        title=title,
    )
    assert drop, f"Expected DROP for {title!r} but got keep (reason={reason!r})"


# ---------------------------------------------------------------------------
# STILL KEEP — macro-adjacent EQUITY titles that must survive
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("title", [
    # Strategy / cross-asset / allocation
    "Brazil Equity Strategy",
    "Cross Asset Systematic Highlights",
    "Consensus Asset Allocation",
    "The J.P. Morgan View",
    # Positioning / flow
    "Investor Positioning",
    # Regional wraps (monthly/weekly/daily)
    "Asia Pacific Monthly Wrap",
    "Global Markets Weekly Wrap",
    "EMEA Daily Wrap",
    # Portfolio / model portfolio
    "Global Model Portfolio",
    "JPM Portfolio Strategy Update",
    # Earnings-season multi-name
    "Earnings Season Preview",
    "Global Earnings Season Dashboard",
    # Thematic / outlook (non-tech-sector)
    "Global Macro Themes",
    "Emerging Markets Outlook",
    "2026 Global Equity Outlook",
    # Dashboard
    "Global Equity Dashboard",
])
def test_jpm_equity_keeps(title: str) -> None:
    """These titles must be kept by the JPM EQUITY branch (n_tickers=0)."""
    drop, reason = is_single_name_equity(
        vendor_code="jpm",
        result=_equity_result(n_tickers=0),
        title=title,
    )
    assert not drop, (
        f"Expected KEEP for {title!r} but got drop (reason={reason!r})"
    )


# ---------------------------------------------------------------------------
# Single-name always drops regardless of title
# ---------------------------------------------------------------------------

def test_jpm_equity_single_ticker_always_drops() -> None:
    """n_tickers==1 must drop even on a strategy-titled report."""
    drop, reason = is_single_name_equity(
        vendor_code="jpm",
        result=_equity_result(n_tickers=1),
        title="Brazil Equity Strategy",
    )
    assert drop
    assert reason == "equity-vendor-default-drop:1-ticker"


# ---------------------------------------------------------------------------
# _JPM_INDUSTRY_DROP fires BEFORE _JPM_EQUITY_KEEP (precedence check)
# ---------------------------------------------------------------------------

def test_industry_drop_precedes_keep_allowlist() -> None:
    """'China Quant Strategy' contains 'strategy' (keep token) but the industry
    drop must take precedence and drop it."""
    drop, reason = is_single_name_equity(
        vendor_code="jpm",
        result=_equity_result(n_tickers=0),
        title="China Quant Strategy",
    )
    assert drop, "China Quant Strategy should drop via _JPM_INDUSTRY_DROP"
    assert reason == "equity-vendor-default-drop:industry"


def test_tech_outlook_drop_precedes_keep_allowlist() -> None:
    """'Asia Technology Outlook' contains 'outlook' (keep token) but the industry
    drop must take precedence."""
    drop, reason = is_single_name_equity(
        vendor_code="jpm",
        result=_equity_result(n_tickers=0),
        title="Asia Technology Outlook",
    )
    assert drop, "Asia Technology Outlook should drop via _JPM_INDUSTRY_DROP"
    assert reason == "equity-vendor-default-drop:industry"


def test_eq_derivatives_strategy_drop_precedes_keep_allowlist() -> None:
    """'European Equity Derivatives Strategy' contains 'strategy' but industry
    drop must take precedence."""
    drop, reason = is_single_name_equity(
        vendor_code="jpm",
        result=_equity_result(n_tickers=0),
        title="European Equity Derivatives Strategy",
    )
    assert drop
    assert reason == "equity-vendor-default-drop:industry"


# ---------------------------------------------------------------------------
# Verify MI/THEMATICS titles are not reached via the EQUITY branch
# (they short-circuit in relevance.py at the MACRO_DESK_KEEP check)
# — belt-and-suspenders: if they somehow arrive here with EQUITY class
# they would be kept because MACRO_DESK_KEEP fires before _JPM_INDUSTRY_DROP
# in is_single_name_equity for JPM.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("title", [
    "JPM | US MACRO THEMATICS - Quick Hits: Less Hot CPI",
    "JPM US Market Intelligence | Macro Week Ahead",
    "JPM US Market Intelligence | Trading CPI",
    "JPM US Market Intelligence | Morning Briefing",
    "JPM International Market Intelligence | Afternoon Briefing",
])
def test_macro_desk_titles_kept_even_when_equity_classified(title: str) -> None:
    """MACRO_DESK_KEEP bypass fires before _JPM_INDUSTRY_DROP, so MI/THEMATICS
    titles always keep even if the asset_class is EQUITY."""
    drop, reason = is_single_name_equity(
        vendor_code="jpm",
        result=_equity_result(n_tickers=0),
        title=title,
    )
    assert not drop, (
        f"MI/THEMATICS title {title!r} must keep even under EQUITY classification, "
        f"got drop reason={reason!r}"
    )
