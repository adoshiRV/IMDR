"""Tests for classifiers/bofa.py — EM-macro reclassification + country fix.

Pins:
1. _em_macro_reclassify — CREDIT → MACRO for EM/sovereign macro reports;
   credit-strategy series stay CREDIT.
2. _country_from_text — word-boundary matching prevents false US hits
   from "plus"/"versus"/"consensus"; CB anchors (IPCA→BR, BCB→BR,
   BoJ→JP, etc.) fire before generic short codes.
3. classify() end-to-end — asset_class and country_code on real manifest
   titles.

All example titles/series are taken from the 2026-06-08→15 smoke manifest
or the deliverable spec.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional, Tuple

import pytest

_RESEARCH_ROOT = Path(__file__).resolve().parents[3] / "playground" / "research"
if str(_RESEARCH_ROOT) not in sys.path:
    sys.path.insert(0, str(_RESEARCH_ROOT))

from ingest.classifiers.bofa import (  # noqa: E402
    _country_from_text,
    _em_macro_reclassify,
    classify,
)
from ingest.classifiers.canonical import (  # noqa: E402
    ASSET_CLASS_CREDIT,
    ASSET_CLASS_MACRO,
    ASSET_CLASS_RATES,
    ASSET_CLASS_FX,
    ASSET_CLASS_STRATEGY,
    ASSET_CLASS_COMMODITIES,
)


# ---------------------------------------------------------------------------
# Minimal stub for the ReportRef dataclass (avoids importing the full
# crawler which requires playwright).
# ---------------------------------------------------------------------------

@dataclass
class _Ref:
    title: str
    series: str = ""
    hub: str = ""
    analyst_primary: str = ""
    analysts: tuple = ()
    publish_date: date = date(2026, 6, 12)


# ---------------------------------------------------------------------------
# _em_macro_reclassify — CREDIT → MACRO
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("hub,series,title", [
    # From the manifest — all in credit_em_fi or carrying an EM-macro series
    ("credit_em_fi",    "Brazil Watch",       "May IPCA: broad inflation, plus hotspots"),
    ("credit_em_fi",    "India Watch",        "May CPI review: Inflation inched up"),
    ("credit_em_fi",    "India Watch",        "Monsoon Tracker: Slow progress"),
    ("credit_em_fi",    "Asia Economic Weekly", "Japan: Oil shock: Pipeline pressures"),
    ("credit_em_fi",    "Emerging Insight",   "China – Will ample monetary liquidity continue"),
    ("credit_em_fi",    "GEMs Conference Call", "Serbia politics: what's at stake"),
    ("credit_em_fi",    "GEMs Conference Call", "Armenia: what is next to watch?"),
    ("credit_em_fi",    "EEMEA Conference Call", "IMF LIC-DSF 2026 Review: what changes"),
    ("credit_em_fi",    "What's priced in",   "BCB likely to cut this week"),
    # Non-EM hub but EM-macro series
    ("credit_global",   "Emerging Insight",   "Peru elections – Uncertainty lingers"),
])
def test_em_macro_reclassify_credit_to_macro(hub: str, series: str, title: str) -> None:
    result = _em_macro_reclassify(hub=hub, series=series, title=title, base=ASSET_CLASS_CREDIT)
    assert result == ASSET_CLASS_MACRO, (
        f"Expected MACRO for hub={hub!r}, series={series!r}, title={title!r}, "
        f"got {result!r}"
    )


# Credit-strategy series must stay CREDIT even in EM hubs
@pytest.mark.parametrize("hub,series,title", [
    ("credit_global",   "IG Credit Strategist",         "Positioning for Iran resolution"),
    ("credit_global",   "Situation Room",               "Slower into bonds"),
    ("credit_global",   "US Fixed Income Strategy",     "The US Fixed Income Weekly"),
    ("credit_high_yield", "High Yield & Loan Strategy", "Higher rates, more AI-capex"),
])
def test_em_macro_reclassify_strategy_stays_credit(hub: str, series: str, title: str) -> None:
    result = _em_macro_reclassify(hub=hub, series=series, title=title, base=ASSET_CLASS_CREDIT)
    assert result == ASSET_CLASS_CREDIT, (
        f"Expected CREDIT for {series!r}, got {result!r}"
    )


# Non-CREDIT base classes must never be touched by _em_macro_reclassify
@pytest.mark.parametrize("base", [
    ASSET_CLASS_MACRO, ASSET_CLASS_RATES, ASSET_CLASS_FX,
    ASSET_CLASS_STRATEGY, ASSET_CLASS_COMMODITIES,
])
def test_em_macro_reclassify_non_credit_base_unchanged(base: str) -> None:
    result = _em_macro_reclassify(
        hub="credit_em_fi", series="Emerging Insight",
        title="China – monetary liquidity", base=base,
    )
    assert result == base, (
        f"Expected unchanged {base!r}, got {result!r}"
    )


# ---------------------------------------------------------------------------
# _country_from_text — CB anchor / word-boundary rules
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("series,title,expected_code", [
    # IPCA → BR (Brazilian inflation index; prevents "plus hotspots" from matching US)
    ("Brazil Watch",    "May IPCA: broad inflation, plus hotspots",     "BR"),
    # BCB → BR
    ("What's priced in", "BCB likely to cut this week",                 "BR"),
    # India Watch series anchor
    ("India Watch",     "May CPI review",                               "IN"),
    # Monsoon is a macro keyword but BoK→KR check: "Monsoon Tracker" should → IN via series anchor
    ("India Watch",     "Monsoon Tracker: Slow progress",               "IN"),
    # Japan via title keyword (word-boundary)
    ("Asia Economic Weekly", "Japan: Oil shock: Pipeline pressures",    "JP"),
    # China via title keyword
    ("Emerging Insight", "China – Will ample monetary liquidity",       "CN"),
    # Serbia → RS
    ("GEMs Conference Call", "Serbia politics: what's at stake",        "RS"),
    # Armenia → AM
    ("GEMs Conference Call", "Armenia: what is next to watch?",         "AM"),
    # IMF title — EEMEA series, no specific country in title → None expected
    # (we don't assert a code here, just that "us" doesn't fire)
])
def test_country_from_text_cb_anchors(series: str, title: str, expected_code: str) -> None:
    code = _country_from_text(series, title)
    assert code == expected_code, (
        f"Expected country={expected_code!r} for series={series!r}, title={title!r}, "
        f"got {code!r}"
    )


# BUG FIX: "us" must NOT match inside "plus", "versus", "consensus", "focus".
@pytest.mark.parametrize("series,title", [
    ("Brazil Watch",   "May IPCA: broad inflation, plus hotspots"),
    ("Global Macro",   "Consensus outlook versus actual"),
    ("EM Strategy",    "Focus on EM fundamentals"),
    ("Credit Weekly",  "Versus peers: spread dynamics"),
])
def test_country_us_not_matched_inside_other_words(series: str, title: str) -> None:
    code = _country_from_text(series, title)
    # Either None or some other country — but NOT US from a word inside another word.
    # For "Brazil Watch" + "IPCA" the expected result is BR, not US.
    assert code != "US" or "united states" in (series + " " + title).lower() or "u.s." in (series + " " + title).lower(), (
        f"'us' matched inside another word for series={series!r}, title={title!r}, "
        f"got code={code!r}"
    )


def test_country_us_explicit_matches() -> None:
    """Explicit 'US' / 'u.s.' should still resolve to US."""
    assert _country_from_text("US Fixed Income Strategy", "") == "US"
    assert _country_from_text("", "US Payrolls: a closer look") == "US"
    assert _country_from_text("", "The u.s. Treasury curve") == "US"


def test_country_from_text_no_match_returns_none() -> None:
    """A title with no country signal must return None (not US or anything else)."""
    code = _country_from_text("High Yield & Loan Strategy", "Higher rates, more AI-capex")
    assert code is None, f"Expected None, got {code!r}"


# ---------------------------------------------------------------------------
# classify() — end-to-end asset_class + country_code on manifest titles
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("hub,series,title,expected_ac,expected_cc", [
    # EM macro → reclassified to MACRO
    ("credit_em_fi",    "Brazil Watch",       "May IPCA: broad inflation, plus hotspots",  ASSET_CLASS_MACRO, "BR"),
    ("credit_em_fi",    "India Watch",        "May CPI review: Inflation inched up",        ASSET_CLASS_MACRO, "IN"),
    ("credit_em_fi",    "India Watch",        "Monsoon Tracker: Slow progress",             ASSET_CLASS_MACRO, "IN"),
    ("credit_em_fi",    "Emerging Insight",   "China – Will ample monetary liquidity",      ASSET_CLASS_MACRO, "CN"),
    ("credit_em_fi",    "GEMs Conference Call", "Serbia politics: what's at stake",         ASSET_CLASS_MACRO, "RS"),
    ("credit_em_fi",    "EEMEA Conference Call", "IMF LIC-DSF 2026 Review",                ASSET_CLASS_MACRO, None),
    ("credit_em_fi",    "What's priced in",   "BCB likely to cut this week",               ASSET_CLASS_MACRO, "BR"),
    # Credit-strategy stays CREDIT
    ("credit_global",   "IG Credit Strategist", "Positioning for Iran resolution",         ASSET_CLASS_CREDIT, None),
    ("credit_global",   "Situation Room",       "Slower into bonds",                        ASSET_CLASS_CREDIT, None),
    # Economics hubs stay MACRO
    ("economics_overview", "Global Economic Weekly", "The Fed is passively easing policy", ASSET_CLASS_MACRO, None),
    # Rates hub
    ("rates_regional",  "Global Rates Weekly", "Warsh debut, war détente",                 ASSET_CLASS_RATES, None),
    # FX hub
    ("fx_g10",          "Global FX weekly",    "Friction with Conviction",                 ASSET_CLASS_FX, None),
])
def test_classify_asset_class_and_country(
    hub: str, series: str, title: str,
    expected_ac: str, expected_cc: "str | None",
) -> None:
    ref = _Ref(title=title, series=series, hub=hub)
    result = classify(ref)
    assert result.asset_class == expected_ac, (
        f"Expected asset_class={expected_ac!r} for hub={hub!r}, "
        f"series={series!r}, title={title!r}, got {result.asset_class!r}"
    )
    if expected_cc is not None:
        assert result.country_code == expected_cc, (
            f"Expected country_code={expected_cc!r} for title={title!r}, "
            f"got {result.country_code!r}"
        )


def test_classify_brazil_watch_not_us() -> None:
    """Regression: Brazil Watch / IPCA must be BR, never US ('plus' false-match)."""
    ref = _Ref(
        title="May IPCA: broad inflation, plus hotspots",
        series="Brazil Watch",
        hub="credit_em_fi",
    )
    result = classify(ref)
    assert result.country_code == "BR", (
        f"Expected BR, got {result.country_code!r}"
    )
    assert result.country_code != "US"
