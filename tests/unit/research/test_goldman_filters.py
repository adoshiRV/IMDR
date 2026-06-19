"""Tests for filters/goldman.py — chart-only/data-dump drop list.

Invariants pinned here:

1. Each series added in the 2026-06-15 content audit returns a drop reason.
2. Known KEEP titles (macro weekly, FX strategy, rates outlook) still pass.
3. The drop fires case-insensitively (normalize_title lowercases).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_RESEARCH_ROOT = Path(__file__).resolve().parents[3] / "playground" / "research"
if str(_RESEARCH_ROOT) not in sys.path:
    sys.path.insert(0, str(_RESEARCH_ROOT))

from ingest.filters.goldman import should_exclude  # noqa: E402


# ---------------------------------------------------------------------------
# Chart-only / data-dump series — must drop
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("title", [
    # Commodities chart packs
    "Commodity Futures Volatility Report",
    "Commodity Futures Volatility Report — June 2026",
    "Commodity Futures Curve Report",
    "Commodity Futures Curve Report: Energy",
    "Commodity Pre Post Roll Report",
    "Commodity Pre Post Roll Report — Weekly",
    # GS Rates MarketStrats family
    "GS Rates MarketStrats | Global Bond Report",
    "GS Rates MarketStrats | Global Bond Futures Carry Report",
    "GS Rates MarketStrats | Global Rates Movers",
    "GS Rates MarketStrats | Global Rates Best Trades",
    "GS Rates MarketStrats | Global Rates Seasonality",
    # Tail StratBook
    "GS MarketStrats | The Tail StratBook",
    "GS MarketStrats | The Tail StratBook — May 2026",
    # FX data dumps
    "Views From the Treasury Desk",
    "Views From the Treasury Desk: Week of 9 Jun",
    "FX Forward Point Roll",
    "FX Forward Point Roll — June 2026",
    "FX Carry Vol Monitor",
    "FX Carry Vol Monitor: EM Edition",
    # Credit MarketStrats
    "GS Credit MarketStrats | CDS Indices Positioning Update",
    "GS Credit MarketStrats | Single Name CDS Weekly Volume",
    # Credit Volatility
    "GS Credit Reports - Credit Volatility Report",
    # CLO Secondary
    "GS CLO Secondary | USD CLO EQTY RUN",
    "GS CLO Secondary | MEZZ RUN",
    # What is Priced In
    "GS What is Priced In",
    "GS What is Priced In: Fed — June 2026",
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
    "US Economics Weekly Update",
    "Global FX Strategy: Dollar Asymmetry",
    "The Weekly FX Wrap Up",
    "European Rates Outlook: ECB Meeting Preview",
    "Global Credit Strategy: Spreads at Inflection",
    "Asia EM Macro: Indonesia Rates View",
    "Goldman Sachs Global ECS Research — US CPI Preview",
    "The Dollar into US CPI",
    "Fixed Income Weekly",
    "Emerging Markets Quarterly",
])
def test_known_keep_titles_pass(title: str) -> None:
    """Legitimate macro/rates/FX strategy titles must not be dropped."""
    result = should_exclude(title=title)
    assert result is None, (
        f"Expected {title!r} to be KEPT, but should_exclude returned {result!r}"
    )


# ---------------------------------------------------------------------------
# Case-insensitivity check
# ---------------------------------------------------------------------------

def test_drop_is_case_insensitive() -> None:
    """Drop rule fires regardless of title casing."""
    assert should_exclude(title="commodity futures volatility report") is not None
    assert should_exclude(title="COMMODITY FUTURES VOLATILITY REPORT") is not None
    assert should_exclude(title="GS CLO SECONDARY | USD CLO EQTY RUN") is not None
