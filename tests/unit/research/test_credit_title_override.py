"""Shared credit-title override (2026-07-17 credit-coverage audit).

`canonical.looks_like_credit` + the UBS/HSBC classifier overrides that route
a desk-coded RATES (or unclassified) note to CREDIT when the title names a
credit product (covered bonds, CLO/ABS/securitized, HY/HG/IG, CDS/iTraxx).
Only upgrades RATES/"" → CREDIT; never touches EQUITY/FX/MACRO/COMMODITIES.
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

from ingest.classifiers.canonical import (  # noqa: E402
    ASSET_CLASS_CREDIT, ASSET_CLASS_RATES, looks_like_credit,
)
from ingest.classifiers.hsbc import classify as hsbc_classify  # noqa: E402
from ingest.classifiers.ubs import classify as ubs_classify  # noqa: E402


@pytest.mark.parametrize("title,expected", [
    ("Covered Bonds: higher FY26 supply but manageable", True),
    ("Global Covered Bond Insight", True),
    ("US CLO Weekly", True),
    ("Securitized Products Outlook", True),
    ("iTraxx Main roll analysis", True),
    ("High Yield strategy update", True),
    ("EMBI Monthly", True),
    ("JGB 10y swaption vol", False),
    ("Global Rates Comment: 2s10s steepener", False),
    ("EUR-USD FX trade idea", False),
    ("", False),
])
def test_looks_like_credit(title: str, expected: bool) -> None:
    assert looks_like_credit(title) is expected


# ── UBS: Rates-desk (B.RATES) covered-bond note → CREDIT ──────────────────
def _ubs(title: str, bac: str = "B.RATES"):
    return SimpleNamespace(business_area_code=bac, title=title,
                           publish_date=date(2026, 7, 17))


def test_ubs_covered_bond_overrides_to_credit() -> None:
    r = ubs_classify(_ubs("Global Rates Comment \"Covered Bonds: higher FY26 supply\""))
    assert r.asset_class == ASSET_CLASS_CREDIT


def test_ubs_plain_rates_stays_rates() -> None:
    r = ubs_classify(_ubs("Global Rates Strategy \"Close BoE Sep'26 receiver\""))
    assert r.asset_class == ASSET_CLASS_RATES


# ── HSBC: Rates-product covered-bond note → CREDIT ────────────────────────
def _hsbc(title: str, product: str = "Rates"):
    return SimpleNamespace(publication_type=product, title=title, analysts="",
                           publish_date=date(2026, 7, 17))


def test_hsbc_covered_bond_overrides_to_credit() -> None:
    r = hsbc_classify(_hsbc("Covered Bond Insight Looking ahead"))
    assert r.asset_class == ASSET_CLASS_CREDIT


def test_hsbc_plain_rates_stays_rates() -> None:
    r = hsbc_classify(_hsbc("Rates Insight: UST 10y outlook"))
    assert r.asset_class == ASSET_CLASS_RATES
