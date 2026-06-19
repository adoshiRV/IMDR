"""Tests for filters/ms.py — chart-only/data-dump drop list.

Invariants pinned here:

1. Each series added in the 2026-06-15 content audit returns a drop reason.
2. Known KEEP titles (FX strategy, rates, macro) still pass.
3. Drop fires case-insensitively.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_RESEARCH_ROOT = Path(__file__).resolve().parents[3] / "playground" / "research"
if str(_RESEARCH_ROOT) not in sys.path:
    sys.path.insert(0, str(_RESEARCH_ROOT))

from ingest.filters.ms import should_exclude  # noqa: E402


# ---------------------------------------------------------------------------
# Chart-only / data-dump series — must drop
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("title", [
    # Geopolitical data tracker — daily chart table
    "Strait of Hormuz - Daily Tracker",
    "Strait of Hormuz - Daily Tracker: June 2026",
    # Calendar / data-watch table
    "Key Data Watch Calendar",
    "Key Data Watch Calendar: Week of 9 June",
    # Australia quant factor-screen
    "Factor Effectiveness",
    "Factor Effectiveness: Australia Quant Screen",
    # Forecast aggregation table
    "Key Forecasts",
    "Key Forecasts: EM Rates",
    # Chart-of-the-day (single chart + caption)
    "Chart of the Day",
    "Chart of the Day: US 10y Treasury",
])
def test_chart_only_series_drops(title: str) -> None:
    """Chart-only / data-dump series must return a drop reason."""
    result = should_exclude(title=title)
    assert result is not None, (
        f"Expected {title!r} to be dropped, but should_exclude returned None"
    )


# ---------------------------------------------------------------------------
# Known KEEP titles — must NOT drop
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("title", [
    "Global FX Strategy: Dollar Weakness",
    "GEF Weekly: US Rates Outlook",
    "EM Fixed Income Strategy",
    "Asia Macro: China Reopening",
    "US Economics: CPI Preview",
    "Cross-Asset Navigator",
    "The FX Pulse",
    "Rates Strategist",
    "Macro Strategy: Positioning for the Turn",
])
def test_known_keep_titles_pass(title: str) -> None:
    """Legitimate macro/rates/FX titles must not be dropped."""
    result = should_exclude(title=title)
    assert result is None, (
        f"Expected {title!r} to be KEPT, but should_exclude returned {result!r}"
    )


# ---------------------------------------------------------------------------
# Case-insensitivity check
# ---------------------------------------------------------------------------

def test_drop_is_case_insensitive() -> None:
    """Drop rule fires regardless of title casing."""
    assert should_exclude(title="strait of hormuz - daily tracker") is not None
    assert should_exclude(title="KEY DATA WATCH CALENDAR") is not None
    assert should_exclude(title="Factor Effectiveness") is not None
