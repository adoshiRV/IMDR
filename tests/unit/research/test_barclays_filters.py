"""Tests for filters/barclays.py — chart-only/data-dump drop list + CJK filter.

Invariants pinned here:

1. "Valuation Overview" and "Valuation Summary" title variants drop
   (companion to "valuation sheet" which is already in _noise.py).
2. QPS presentation decks drop only when publication_type == "Presentation"
   — QPS research notes (same title prefix, different type) must NOT drop.
3. Existing event-admin prefix drops still work (regression guard).
4. Known KEEP titles (economics, rates, FX, credit strategy) still pass.
5. CJK-titled publications drop as "cjk:'japanese'" (GAP 3 backstop).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_RESEARCH_ROOT = Path(__file__).resolve().parents[3] / "playground" / "research"
if str(_RESEARCH_ROOT) not in sys.path:
    sys.path.insert(0, str(_RESEARCH_ROOT))

from ingest.filters.barclays import should_exclude  # noqa: E402


# ---------------------------------------------------------------------------
# Valuation variant substrings — must drop
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("title", [
    "European Media Valuation Overview",
    "US Consumer Staples Valuation Overview",
    "Asia Telecoms Valuation Summary",
    "EM Credit Valuation Summary: June 2026",
    "Valuation Summary: UK Banks",
])
def test_valuation_variant_substrings_drop(title: str) -> None:
    """Valuation Overview / Summary variants must drop as chart-only."""
    result = should_exclude(title=title)
    assert result is not None, (
        f"Expected {title!r} to be dropped, but should_exclude returned None"
    )


# ---------------------------------------------------------------------------
# QPS presentation decks — drop ONLY with publication_type == "Presentation"
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("title", [
    "QPS: Factor Timing Deck",
    "QPS | Cross-Asset Quant Deck",
    "QPS — Rates Presentation",
])
def test_qps_presentation_drops(title: str) -> None:
    """QPS decks with publication_type='Presentation' must drop."""
    result = should_exclude(title=title, publication_type="Presentation")
    assert result == "chart-only:qps-presentation", (
        f"Expected 'chart-only:qps-presentation' for {title!r} "
        f"(Presentation type), got {result!r}"
    )


@pytest.mark.parametrize("title", [
    "QPS: Factor Timing Deck",
    "QPS | Cross-Asset Quant Views",
    "QPS — Rates Outlook",
])
def test_qps_research_note_does_not_drop(title: str) -> None:
    """QPS titles WITHOUT publication_type='Presentation' must NOT drop on the
    QPS-presentation rule (they may drop on other rules, but not this one)."""
    result = should_exclude(title=title, publication_type="")
    # The QPS presentation rule must not fire when type != "Presentation"
    assert result != "chart-only:qps-presentation", (
        f"QPS research note {title!r} wrongly dropped as 'chart-only:qps-presentation'"
    )


# ---------------------------------------------------------------------------
# Existing event-admin drops still work (regression guard)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("title", [
    "Reminder: Analyst Access: Barclays Tuesday Credit Call",
    "***STARTS IN 1 HOUR 1PM ET***: Barclays Hosted Expert Call",
    "Webinar Invite: Analyst Access: EM Rates",
    "Corporate Access: Equitable (EQH): Management Meeting",
])
def test_existing_event_admin_drops_still_work(title: str) -> None:
    """Pre-existing event-admin drops must still fire."""
    result = should_exclude(title=title)
    assert result is not None, (
        f"Expected {title!r} to still drop, but should_exclude returned None"
    )


# ---------------------------------------------------------------------------
# Known KEEP titles — must NOT drop
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("title", [
    "Global Rates Outlook: ECB and Fed Divergence",
    "European Economics: Inflation Monitor",
    "FX Pulse: Dollar Strength",
    "Credit Strategy: IG vs HY Spreads",
    "Emerging Markets Macro Quarterly",
    "Commodities Weekly: Oil Supply Dynamics",
])
def test_known_keep_titles_pass(title: str) -> None:
    """Legitimate macro/rates/FX/credit titles must not be dropped."""
    result = should_exclude(title=title)
    assert result is None, (
        f"Expected {title!r} to be KEPT, but should_exclude returned {result!r}"
    )


# ---------------------------------------------------------------------------
# "valuation sheet" already caught by _noise.py (regression guard)
# ---------------------------------------------------------------------------

def test_valuation_sheet_already_drops_via_noise() -> None:
    """'valuation sheet' must drop (already covered by _noise.CHART_PACK_SUBSTRINGS)."""
    result = should_exclude(title="European Media Valuation Sheet")
    assert result is not None, (
        "Expected 'European Media Valuation Sheet' to drop via _noise, but got None"
    )


# ---------------------------------------------------------------------------
# GAP 3 — CJK backstop (must fire before all other rules)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("title", [
    # Hiragana
    "日本のインフレ動向：CPI上昇の背景",
    # Katakana + CJK
    "グローバル金利ウィークリー：ECB利上げ後の展開",
    # Full-width colon (CJK punctuation range)
    "金利市場：週次分析レポート",
    # Mixed CJK + Latin (still drops)
    "Japan Rates Weekly: 日本国債の動向",
])
def test_cjk_titles_drop(title: str) -> None:
    """CJK-character titles must drop as 'cjk:\"japanese\"'."""
    result = should_exclude(title=title)
    assert result == "cjk:'japanese'", (
        f"Expected cjk drop for {title!r}, got {result!r}"
    )


@pytest.mark.parametrize("title", [
    # ASCII-only titles that contain words that look similar but aren't CJK
    "Global Rates Weekly: ECB and Fed Divergence",
    "Japan Economics: BoJ policy outlook",
    "Asia FX Weekly: Yen and Yuan dynamics",
])
def test_ascii_titles_not_dropped_as_cjk(title: str) -> None:
    """Pure ASCII titles (even Japan-related) must NOT be dropped by the CJK rule."""
    result = should_exclude(title=title)
    assert result != "cjk:'japanese'", (
        f"ASCII title {title!r} wrongly dropped as CJK: {result!r}"
    )
