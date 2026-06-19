"""Tests for filters/nomura.py — chart-only/data-dump drop list.

Invariants pinned here:

1. Each series added in the 2026-06-15 content audit drops when passed as
   the ``title`` argument to should_exclude.
2. Existing noise-report-title drops still work (regression guard).
3. Known KEEP titles (macro, rates, FX strategy) still pass.
4. Drop fires case-insensitively.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_RESEARCH_ROOT = Path(__file__).resolve().parents[3] / "playground" / "research"
if str(_RESEARCH_ROOT) not in sys.path:
    sys.path.insert(0, str(_RESEARCH_ROOT))

from ingest.filters.nomura import should_exclude  # noqa: E402


# ---------------------------------------------------------------------------
# Chart-only / data-dump series — must drop via title
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("title", [
    # FX fixing model — pure model output
    "USD/CNY Fix Model",
    "USD/CNY Fix Model: June 2026",
    # Month-end FX model
    "G10 FX Month-end Model",
    "G10 FX Month-End Model — May 2026",
    # Portfolio updates — trade-table + disclaimer
    "FX and Rates Portfolio Update",
    "FX and Rates Portfolio Update: June 13",
    "Credit Portfolio Update",
    "Credit Portfolio Update — Week 24",
    "Macro Portfolio Update",
    "Macro Portfolio Update: June 2026",
])
def test_chart_only_series_drops_via_title(title: str) -> None:
    """Chart-only / data-dump series must return a drop reason when passed as title."""
    result = should_exclude(title=title)
    assert result is not None, (
        f"Expected {title!r} to be dropped, but should_exclude returned None"
    )


# ---------------------------------------------------------------------------
# Existing noise-report-title logic still fires (regression guard)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("report_title_en", [
    "MBS Data Reports — June 2026",
    "Japan Small Cap Weekly",
    "Agency MBS Lockup Reports",
])
def test_existing_noise_report_title_still_drops(report_title_en: str) -> None:
    result = should_exclude(report_title_en=report_title_en)
    assert result is not None, (
        f"Expected noise-report-title drop for {report_title_en!r}, got None"
    )
    assert result.startswith("noise-report-title:"), (
        f"Expected 'noise-report-title:' prefix, got {result!r}"
    )


# ---------------------------------------------------------------------------
# Known KEEP titles — must NOT drop
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("title", [
    "Japan Rates Outlook: Yieldcurve Control Exit",
    "Global FX: Dollar Asymmetry Post-FOMC",
    "Asia EM Fixed Income Strategy",
    "Nomura Cross-Asset Monthly",
    "US Economics: Fed Preview",
    "Global Macro Views",
    "EM Rates Monitor",
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
    assert should_exclude(title="usd/cny fix model") is not None
    assert should_exclude(title="G10 FX MONTH-END MODEL") is not None
    assert should_exclude(title="credit portfolio update") is not None
