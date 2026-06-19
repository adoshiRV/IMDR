"""Tests for filters/jpm.py::should_exclude — business-group drops and
macro-desk bypass.

The key invariants being pinned:

1. Macro-desk titles (Market Intelligence / MACRO THEMATICS / SSA CB) are
   NOT dropped even when published under an EXCLUDED_BUSINESS_GROUPS value.
2. Non-macro titles with those same business groups ARE dropped.
3. CJK and noise drops still apply even when the title matches the macro
   allowlist (business-group bypass does not suppress later checks).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_RESEARCH_ROOT = Path(__file__).resolve().parents[3] / "playground" / "research"
if str(_RESEARCH_ROOT) not in sys.path:
    sys.path.insert(0, str(_RESEARCH_ROOT))

from ingest.filters.jpm import should_exclude  # noqa: E402


# ---------------------------------------------------------------------------
# Macro-desk titles must NOT drop on business-group, for any excluded BG
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("title,business_group", [
    (
        "JPM | US MACRO THEMATICS - Quick Hits: Less Hot CPI",
        "Specialist Sales",
    ),
    (
        "JPM US Market Intelligence | Macro Week Ahead",
        "Data Assets & Alpha Group",
    ),
    (
        "JPM US Market Intelligence | Trading CPI",
        "Data Assets & Alpha Group",
    ),
    (
        "JPM International Market Intelligence | Morning Briefing",
        "Specialist Sales",
    ),
    (
        "JP Morgan SSA CB - Week in Review 1-5 Jun",
        "Specialist Sales",
    ),
    (
        "JPM | US MACRO THEMATICS - Morning Quick Hits: deal optimism",
        "Specialist Sales",
    ),
    # Non Research Other is also an excluded BG — macro bypass must work there too.
    (
        "JPM US Market Intelligence | Afternoon Briefing",
        "Non Research Other",
    ),
])
def test_macro_desk_bypasses_business_group_drop(title: str, business_group: str) -> None:
    """Macro-desk titles must be kept regardless of which excluded BG they sit in."""
    result = should_exclude(title=title, business_group=business_group)
    assert result is None, (
        f"Expected {title!r} (BG={business_group!r}) to be kept, "
        f"but should_exclude returned {result!r}"
    )


# ---------------------------------------------------------------------------
# Non-macro titles with excluded BGs must still drop on business-group
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("title,business_group", [
    (
        "JPM | APAC FINANCIALS - Japan Banks",
        "Specialist Sales",
    ),
    (
        "JPM NA Rates Sales Daily (06/11)",
        "Specialist Sales",
    ),
    (
        "Data Insights",
        "Data Assets & Alpha Group",
    ),
    (
        "Through The Retail Lens",
        "Specialist Sales",
    ),
    (
        "JPM PI - Weekly Wrap",
        "Non Research Other",
    ),
])
def test_non_macro_title_still_drops_on_business_group(title: str, business_group: str) -> None:
    """Non-macro titles with excluded BGs must return the business-group reason."""
    result = should_exclude(title=title, business_group=business_group)
    assert result == f"business-group:{business_group!r}", (
        f"Expected {title!r} (BG={business_group!r}) to drop with "
        f"'business-group:{business_group!r}', got {result!r}"
    )


# ---------------------------------------------------------------------------
# Business-group drop does not fire when BG is empty / not in the excluded set
# ---------------------------------------------------------------------------

def test_empty_business_group_passes_bg_check() -> None:
    """An empty business_group never triggers the BG drop."""
    result = should_exclude(title="Global Data Watch", business_group="")
    assert result is None


def test_non_excluded_business_group_passes() -> None:
    result = should_exclude(
        title="Global FX Strategy Weekly",
        business_group="Global FX Research",
    )
    assert result is None


# ---------------------------------------------------------------------------
# CJK drop still applies even when title matches the macro allowlist
# (business-group bypass must not suppress subsequent checks)
# ---------------------------------------------------------------------------

def test_cjk_in_macro_desk_title_still_drops() -> None:
    """A macro-desk title that also contains CJK must drop on cjk, not pass."""
    # Inject a CJK character into a macro-desk title.
    cjk_title = "JPM US Market Intelligence | 週間マクロ"
    result = should_exclude(title=cjk_title, business_group="Specialist Sales")
    assert result == "cjk:'japanese'", (
        f"Expected CJK drop, got {result!r}"
    )


# ---------------------------------------------------------------------------
# Regression: no business_group arg (default) — should not raise
# ---------------------------------------------------------------------------

def test_no_business_group_kwarg_does_not_raise() -> None:
    result = should_exclude(title="JPM US Market Intelligence | Trading CPI")
    assert result is None


# ---------------------------------------------------------------------------
# Extel-vote admin note — must drop regardless of BG (fires first)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("title", [
    "*Extel Vote Ends Tomorrow* JPM US Market Intelligence",
    "Extel Vote Ends Today — please vote",
    "EXTEL VOTE REMINDER",
    "*Extel Vote Open* JPM US Market Intelligence | Morning Briefing",
])
def test_extel_vote_drops(title: str) -> None:
    """Extel-vote admin notes must drop with reason 'admin:extel-vote'."""
    result = should_exclude(title=title, business_group="")
    assert result == "admin:extel-vote", (
        f"Expected 'admin:extel-vote' for {title!r}, got {result!r}"
    )


def test_extel_vote_drops_even_with_allowed_business_group() -> None:
    """Extel-vote drop is independent of business_group value."""
    result = should_exclude(
        title="*Extel Vote Ends Tomorrow* JPM US Market Intelligence",
        business_group="Global Research",
    )
    assert result == "admin:extel-vote"


def test_normal_mi_morning_briefing_not_dropped_as_extel() -> None:
    """Normal MI Morning Briefing titles must NOT be caught by the extel-vote check."""
    for title in [
        "JPM US Market Intelligence | Morning Briefing",
        "JPM International Market Intelligence | Afternoon Briefing",
        "JPM US Market Intelligence | Macro Week Ahead",
        "JPM US Market Intelligence | Trading CPI",
    ]:
        result = should_exclude(title=title, business_group="")
        assert result is None, (
            f"MI title {title!r} should pass, but got {result!r}"
        )
