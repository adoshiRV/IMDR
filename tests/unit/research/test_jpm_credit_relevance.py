"""Tests for is_single_name_equity — JPM CREDIT branch (Fold 1a keep-by-default).

As of 2026-07-16 JPM CREDIT is **keep-by-default**: single-name issuer notes
AND sector/thematic credit wraps are KEPT (recall-first; issuer/sector credit
is wanted — the PM corpus Z:\\Business\\Research\\Credit is issuer/sector
organised). Only pure non-research admin/logistics drops (credit-admin-drop).
This replaces the retired keep-allowlist + n_tickers==1 + industry drops.
See docs/admin/development/credit_bofa.md Fold 1a.

Run::

    python -m pytest tests/unit/research/test_jpm_credit_relevance.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_RESEARCH_ROOT = Path(__file__).resolve().parents[3] / "playground" / "research"
if str(_RESEARCH_ROOT) not in sys.path:
    sys.path.insert(0, str(_RESEARCH_ROOT))

from ingest.classifiers.canonical import ASSET_CLASS_CREDIT  # noqa: E402
from ingest.classifiers.models import ClassifyResult, Tag  # noqa: E402
from ingest.relevance import is_single_name_equity  # noqa: E402


def _credit(n_tickers: int = 0) -> ClassifyResult:
    tags = [Tag(category="ticker", value=f"T{i}") for i in range(n_tickers)]
    return ClassifyResult(asset_class=ASSET_CLASS_CREDIT, tags=tags)


# ---------------------------------------------------------------------------
# Single-name issuer credit — was dropped (:1-ticker / default), now KEEP
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("title", [
    "Bank of America",
    "Goldman Sachs",
    "Wells Fargo",
    "Citigroup Inc.",
    "Morgan Stanley",
    "PNC Financial",
    "Zhongsheng Group Holdings",
    "Amprion",
    "Ashton Woods",
    "Ford Motor 2030",
])
def test_jpm_credit_single_name_keeps(title: str) -> None:
    """Single-issuer JPM credit notes are now KEPT even with n_tickers==1."""
    drop, reason = is_single_name_equity(
        vendor_code="jpm", result=_credit(n_tickers=1), title=title,
    )
    assert not drop, f"Expected KEEP for {title!r}, got drop reason={reason!r}"


# ---------------------------------------------------------------------------
# Sector / thematic / series credit — was :industry / default drop, now KEEP
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("title", [
    "Transportation Credit: Reshuffling Rail / Parcel Recs",
    "Technology & Telecom Weekly",
    "Train of Thought: European Transportation Credit Update",
    "APAC Credit Roundup",
    "Asia Credit Analytics",
    "Indonesian Credit",
    "Curveball: HG Credit Curve Opportunities",
    "JPM Daily Credit Strategy Update",
    "Credit Market Outlook & Strategy",
])
def test_jpm_credit_sector_and_series_keeps(title: str) -> None:
    """Sector-credit + strategy series are now KEPT (recall-first)."""
    drop, reason = is_single_name_equity(
        vendor_code="jpm", result=_credit(n_tickers=0), title=title,
    )
    assert not drop, f"Expected KEEP for {title!r}, got drop reason={reason!r}"


# ---------------------------------------------------------------------------
# Pure admin/logistics still DROPS
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("title", [
    "Transportation Earnings Calendar 2Q26",
    "Services Q226 Earnings Calendar",
    "Retail and Consumer Earnings Calendar",
])
def test_jpm_credit_admin_drops(title: str) -> None:
    drop, reason = is_single_name_equity(
        vendor_code="jpm", result=_credit(n_tickers=0), title=title,
    )
    assert drop and reason == "credit-admin-drop", (
        f"Expected credit-admin-drop for {title!r}, got drop={drop} reason={reason!r}"
    )
