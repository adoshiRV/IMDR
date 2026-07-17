"""Nomura classifier — FI structured-credit routing (credit-coverage fix).

Pins the 2026-07-17 fix: FI docs whose assetClasses[] is empty (Nomura's
CLO / Securitized Products / ABS desk omits it) route to CREDIT via a title
signal instead of defaulting to RATES. Genuine rates FI stays RATES.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

_RESEARCH_ROOT = Path(__file__).resolve().parents[3] / "playground" / "research"
if str(_RESEARCH_ROOT) not in sys.path:
    sys.path.insert(0, str(_RESEARCH_ROOT))

from ingest.classifiers.canonical import ASSET_CLASS_CREDIT, ASSET_CLASS_RATES  # noqa: E402
from ingest.classifiers.nomura import _split_fi, classify  # noqa: E402


def _ref(title: str, asset_class_id: str = "FI", asset_classes=()):
    return SimpleNamespace(
        title=title, asset_class_id=asset_class_id,
        asset_classes=tuple(asset_classes),
        publish_date=date(2026, 7, 17),
    )


@pytest.mark.parametrize("title", [
    "CLO Special Topics - Estimated H1 Returns, NAIC Update",
    "Securitized Products Weekly - Securitized Products Weekly",
    "Securitized Products Special Topics - Fiber ABS Sector Overview",
    "Agency MBS - Prepayment update",
    "Covered Bond Insight - Looking ahead",
    "US CLO - Supply Expectations and Loan Ratings",
])
def test_fi_structured_credit_routes_to_credit(title: str) -> None:
    """Empty-assetClasses FI structured-credit docs now classify CREDIT."""
    assert classify(_ref(title)).asset_class == ASSET_CLASS_CREDIT


@pytest.mark.parametrize("title", [
    "JGB 10y swaption vol update",
    "Rates Strategy - Bund ASW and 2s10s",
])
def test_fi_rates_stays_rates(title: str) -> None:
    """Genuine rates FI (empty assetClasses) still defaults to RATES."""
    assert classify(_ref(title)).asset_class == ASSET_CLASS_RATES


def test_split_fi_title_fallback() -> None:
    assert _split_fi([], "CLO Special Topics") == ASSET_CLASS_CREDIT
    assert _split_fi([], "Securitized Products Weekly") == ASSET_CLASS_CREDIT
    assert _split_fi([], "JGB swaption") == ASSET_CLASS_RATES
    # explicit assetClasses still win over title
    assert _split_fi(["Credit"], "irrelevant rates title") == ASSET_CLASS_CREDIT
    assert _split_fi(["Rates"], "CLO mention") == ASSET_CLASS_RATES
