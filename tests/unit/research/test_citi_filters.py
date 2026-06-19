"""Tests for filters/citi.py — chart-only/data-dump drop list.

Invariants pinned here:

1. Each series added in the 2026-06-15 content audit returns a drop reason.
2. Existing prefix drops (futures positioning, citi weather, etc.) still work.
3. Known KEEP titles (macro strategy, rates, FX) still pass.
4. Drop fires case-insensitively.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_RESEARCH_ROOT = Path(__file__).resolve().parents[3] / "playground" / "research"
if str(_RESEARCH_ROOT) not in sys.path:
    sys.path.insert(0, str(_RESEARCH_ROOT))

from ingest.filters.citi import should_exclude  # noqa: E402


# ---------------------------------------------------------------------------
# Chart-only / data-dump series — must drop (2026-06-15 additions)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("title", [
    # Bond-index data snapshot, 2-chunk near-empty
    "iBoxx Snapshot",
    "iBoxx Snapshot: EUR IG",
    "iBoxx Snapshot: USD HY — June 2026",
])
def test_new_chart_only_series_drops(title: str) -> None:
    """New chart-only / data-dump series must return a drop reason."""
    result = should_exclude(title=title)
    assert result is not None, (
        f"Expected {title!r} to be dropped, but should_exclude returned None"
    )


# ---------------------------------------------------------------------------
# Existing prefix drops still work (regression guard)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("title", [
    "Futures Positioning Update — CFTC",
    "Citi Weather Metrics: US Cooling Degree Days",
    "Global Earnings Revision — Q2 2026",
    "Global Market Intelligence Dashboard",
    "WARN Act Notices: Week of 9 June",
    "Interactive Daily Style Performance",
])
def test_existing_prefix_drops_still_work(title: str) -> None:
    """Pre-existing excluded prefixes must still drop."""
    result = should_exclude(title=title)
    assert result is not None, (
        f"Expected {title!r} to still drop, but should_exclude returned None"
    )


# ---------------------------------------------------------------------------
# Known KEEP titles — must NOT drop
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("title", [
    "Global Rates Weekly",
    "FX Strategy: G10 Outlook",
    "Asia EM Macro: Indonesia Rates",
    "Credit Outlook: IG Spreads",
    "US Economics: CPI Preview",
    "Cross-Asset Allocation Update",
    "Citi Macro Strategy Monthly",
])
def test_known_keep_titles_pass(title: str) -> None:
    """Legitimate macro/rates/FX titles must not be dropped."""
    result = should_exclude(title=title)
    assert result is None, (
        f"Expected {title!r} to be KEPT, but should_exclude returned {result!r}"
    )


# ---------------------------------------------------------------------------
# CJK / Japanese-script drops
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("title,expected_reason", [
    ("2026年6月11日", "cjk:'japanese'"),
    ("米CPI：コアCPIは基調インフレの落ち着きを示唆", "cjk:'japanese'"),
    ("グローバル・マクロ・ストラテジー", "cjk:'japanese'"),
])
def test_cjk_titles_drop_with_japanese_reason(title: str, expected_reason: str) -> None:
    """CJK-character titles must drop with the exact reason string."""
    result = should_exclude(title=title)
    assert result == expected_reason, (
        f"Expected {expected_reason!r} for {title!r}, got {result!r}"
    )


def test_english_title_not_dropped_as_cjk() -> None:
    """A normal English macro title must NOT be dropped by the CJK rule."""
    assert should_exclude(title="Global Rates Weekly") is None


# ---------------------------------------------------------------------------
# Case-insensitivity check
# ---------------------------------------------------------------------------

def test_drop_is_case_insensitive() -> None:
    """Drop rule fires regardless of title casing."""
    assert should_exclude(title="iboxx snapshot") is not None
    assert should_exclude(title="IBOXX SNAPSHOT: USD HY") is not None
