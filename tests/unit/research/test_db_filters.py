"""Tests for filters/db.py::should_exclude — product-type and chart-pack rules.

Invariants pinned here:

1. "Fixed Income Chart Of The Day" with product_type="Charts" DROPS on
   product-type:'Charts'. (The brief 2026-06-14 keep-override was REVERTED
   2026-06-15: its extractable text is ~all watermark + disclaimer
   boilerplate — the analysis lives in chart images PyMuPDF can't OCR.)
2. "Fixed Income Chart Of The Day" with NO product_type still drops via
   the shared noise classifier (chart-pack 'chart of the day').
3. A generic Charts deck drops on product-type:'Charts'.
4. "Catalyst Call" always drops.
5. "DBDaily" is still KEPT (genuine cross-asset macro daily — text-rich).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_RESEARCH_ROOT = Path(__file__).resolve().parents[3] / "playground" / "research"
if str(_RESEARCH_ROOT) not in sys.path:
    sys.path.insert(0, str(_RESEARCH_ROOT))

from ingest.filters.db import should_exclude  # noqa: E402


# ---------------------------------------------------------------------------
# FI-Chart-of-Day: NO special treatment — drops like any chart deck.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("title", [
    "Fixed Income Chart Of The Day: EUR STIR: Looking ahead to June",
    "Fixed Income Chart Of The Day: USD CPI: a cross-asset view",
    "Fixed Income Chart Of The Day: Looking ahead to the ECB meeting",
])
def test_fi_chart_of_day_charts_product_type_drops(title: str) -> None:
    """FI-Chart-of-Day tagged product_type='Charts' drops (override reverted)."""
    result = should_exclude(title=title, product_type="Charts")
    assert result == "product-type:'Charts'", (
        f"Expected {title!r} (product_type='Charts') to drop on product-type, "
        f"got {result!r}"
    )


@pytest.mark.parametrize("title", [
    "Fixed Income Chart Of The Day: USD CPI: a cross-asset view",
    "Fixed Income Chart Of The Day: Liquidity transmission by FHLBs",
])
def test_fi_chart_of_day_no_product_type_drops_as_chart_pack(title: str) -> None:
    """With no product_type, FI-Chart-of-Day drops via shared chart-pack noise."""
    result = should_exclude(title=title)
    assert result == "noise:chart-pack:'chart of the day'", (
        f"Expected {title!r} to drop as chart-pack noise, got {result!r}"
    )


# ---------------------------------------------------------------------------
# Generic Charts deck: drops on product-type.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("title", [
    "European Equity Strategy Charts",
    "EM Credit Charts Weekly",
    "Asia Macro Charts Pack",
    "Charts: Global Rates Dashboard",
])
def test_generic_charts_product_type_still_drops(title: str) -> None:
    """A Charts deck drops on product-type:'Charts'."""
    result = should_exclude(title=title, product_type="Charts")
    assert result == "product-type:'Charts'", (
        f"Expected {title!r} to drop as product-type:'Charts', got {result!r}"
    )


# ---------------------------------------------------------------------------
# Catalyst Call: always drops.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("title", [
    "Catalyst Call: Deutsche Telekom — upgrade to Buy",
    "Catalyst Call: Volkswagen — initiate coverage",
])
def test_catalyst_call_always_drops(title: str) -> None:
    """Catalyst Call product_type drops regardless of title content."""
    result = should_exclude(title=title, product_type="Catalyst Call")
    assert result == "product-type:'Catalyst Call'", (
        f"Expected {title!r} to drop as product-type:'Catalyst Call', got {result!r}"
    )


# ---------------------------------------------------------------------------
# DBDaily: KEPT (genuine text-rich macro daily — not reverted).
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("title", [
    "DBDaily: US core CPI missed; US to launch new Iran strike",
    "DBDaily: Jolts jump; Euro core CPI beats",
])
def test_dbdaily_still_kept(title: str) -> None:
    """DBDaily remains a macro-keep (text-rich cross-asset daily)."""
    assert should_exclude(title=title) is None, (
        f"Expected {title!r} to be KEPT (DBDaily macro-keep)"
    )
