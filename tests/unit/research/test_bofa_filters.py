"""Tests for BofA discovery filters.

Pins:
1. credit_hub_drop_reason — KEEP-by-default as of 2026-07-17 (Fold 2a
   recall-first): single-name issuers + sector credit are now KEPT (were
   DROP); macro/strategy/sovereign still KEEP; pure data-packs gated
   elsewhere (should_exclude / _noise), not here.
2. should_exclude — date-only thin titles, conference announcements,
   shared noise families (event-admin "in 1hr", chart-pack substrings).
3. _noise.EVENT_ADMIN_PREFIXES — "in 1hr" / "in 1 hr" abbreviations
   that were missing and let BofA event pings through.

All example titles are taken directly from the 2026-06-08→15 smoke manifest
or from the deliverable spec. Drop-reason strings are pinned exactly.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_RESEARCH_ROOT = Path(__file__).resolve().parents[3] / "playground" / "research"
if str(_RESEARCH_ROOT) not in sys.path:
    sys.path.insert(0, str(_RESEARCH_ROOT))

from ingest.filters.bofa import credit_hub_drop_reason, should_exclude  # noqa: E402
from ingest.filters._noise import classify_noise  # noqa: E402


# ---------------------------------------------------------------------------
# credit_hub_drop_reason — KEEP-by-default (2026-07-17, Fold 2a recall-first).
# Single-name issuers AND sector credit are now WANTED, so this function no
# longer drops them (was the old "credit-hub-nonmacro" default-drop). Pure
# number-dump data-packs, if undesired, are gated elsewhere — should_exclude
# (date-only title) / the _noise filter — NOT here.
# See docs/admin/development/credit_bofa.md Fold 2a.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("hub,series,title", [
    ("credit_high_grade",           "Campbell's",         "In a pretzel; FY27 deleveraging path"),
    ("credit_high_yield",           "VF Corporation",     "4Q was in-line ex-tariff benefits"),
    ("credit_strategy_americas",    "Victoria's Secret",  "Trading levels indicate the Secret is out"),
    ("credit_high_grade",           "Nuts & Bolts",       "FedEx Freight Spin Complete"),
    ("credit_high_yield",           "Samsung C&T",        "Model"),
])
def test_credit_hub_keeps_single_name_issuer(hub: str, series: str, title: str) -> None:
    """Single-name issuer credit is now KEPT (recall-first)."""
    assert credit_hub_drop_reason(hub=hub, series=series, title=title) is None


@pytest.mark.parametrize("hub,series,title", [
    ("credit_strategy_americas",    "High Yield Energy",                 "Energy Weekly"),
    ("credit_strategy_americas",    "Weekly Relative Value Update",      "Food and Beverage – 6/12/26"),
    ("credit_strategy_americas",    "Weekly Relative Value Update",      "Consumer Products – 6/12/26"),
    ("credit_strategy_americas",    "Retail, Apparel and Consumer Products", "May data shows no signs of consumer spending"),
    ("credit_strategy_americas",    "Retailing",                         "The Monthly Checkout"),
    ("credit_em_corporate",         "LatAm Petrochemicals",              "Monthly Petrochemical Monitor: PE and PVC"),
    ("credit_high_grade",           "Investment Grade Utilities",        "Utilities and Power Weekly"),
    ("credit_high_yield",           "HY Homebuilders, Building Materials", "Weekly Update"),
    ("credit_high_grade",           "BofA IG Healthcare Weekly",         "Vital Signs"),
    ("credit_strategy_americas",    "High Grade Energy Weekly",          "Week ending June 12, 2026"),
])
def test_credit_hub_keeps_sector(hub: str, series: str, title: str) -> None:
    """Sector-credit wraps are now KEPT (recall-first)."""
    assert credit_hub_drop_reason(hub=hub, series=series, title=title) is None


@pytest.mark.parametrize("hub,series,title", [
    ("credit_securitized",  "Hybrid Arm Package",           "12 June 2026"),
    ("credit_securitized",  "PassThrough Package",          "12 June 2026"),
    ("credit_securitized",  "Freddie Mac S-curve Prepayment", "08 June 2026"),
    ("credit_securitized",  "Agency MBS Alert",             "Servicer Tracker - 2026 June"),
])
def test_credit_hub_no_longer_gates_data_packs(hub: str, series: str, title: str) -> None:
    """credit_hub_drop_reason no longer drops securitized data-packs; pure
    number-dump suppression (if any) is handled by should_exclude
    (date-only title) / _noise, not this function. (Recall-first: accepted
    residual MBS data-pack noise — see credit_bofa.md.)"""
    assert credit_hub_drop_reason(hub=hub, series=series, title=title) is None


# ---------------------------------------------------------------------------
# credit_hub_drop_reason — KEEP cases
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("hub,series,title", [
    # Credit-strategy / cross-credit flagship
    ("credit_global",               "IG Credit Strategist",              "Positioning for Iran resolution"),
    ("credit_global",               "Situation Room",                    "Slower into bonds"),
    ("credit_global",               "US Fixed Income Strategy",          "The US Fixed Income Weekly"),
    ("credit_high_yield",           "High Yield & Loan Strategy",        "Higher rates, more AI-capex, lower fragility"),
    ("credit_em_corporate",         "European Credit",                   "3Q26 Best ideas"),
    # Securitized strategy
    ("credit_securitized",          "Agency MBS Weekly",                 "A sentiment shift and a deep dive"),
    ("credit_securitized",          "Securitization Weekly Overview",    "A series of close calls: tight spreads"),
    # Sovereign / EM macro
    ("credit_em_fi",                "Brazil Watch",                      "May IPCA: broad inflation, plus hotspots"),
    ("credit_em_fi",                "India Watch",                       "May CPI review: Inflation inched up"),
    ("credit_em_fi",                "India Watch",                       "Monsoon Tracker: Slow progress"),
    ("credit_em_fi",                "Asia Economic Weekly",              "Japan: Oil shock: Pipeline pressures"),
    ("credit_em_fi",                "Emerging Insight",                  "China – Will ample monetary liquidity continue"),
    ("credit_em_fi",                "GEMs Conference Call",              "Serbia politics: what's at stake"),
    ("credit_em_fi",                "GEMs Conference Call",              "Armenia: what is next to watch?"),
    ("credit_em_fi",                "EEMEA Conference Call",             "IMF LIC-DSF 2026 Review: what changes"),
    ("credit_em_fi",                "What's priced in",                  "BCB likely to cut this week"),
    # European morning credit — qualifies via series ("morning credit" contains "credit" but
    # actually matches _SOVEREIGN_EM_KEEP_RE on "morning credit")
    ("credit_em_corporate",         "European Morning Credit",           "Today in European Credit"),
])
def test_credit_hub_keeps_macro_strategy(hub: str, series: str, title: str) -> None:
    reason = credit_hub_drop_reason(hub=hub, series=series, title=title)
    assert reason is None, (
        f"Expected KEEP for hub={hub!r}, series={series!r}, title={title!r}, "
        f"but got drop reason {reason!r}"
    )


# Non-credit hubs are untouched by credit_hub_drop_reason
@pytest.mark.parametrize("hub,series,title", [
    ("economics_overview",  "Global Economic Weekly",   "The Fed is passively easing policy"),
    ("rates_regional",      "Global Rates Weekly",      "Warsh debut, war détente"),
    ("futures",             "Global Futures Fair Values", "11-Jun-26 Close"),
    ("commodities",         "Commodity Strategist",     "7th Virtual Commodity Conference 2026"),
])
def test_non_credit_hub_not_affected(hub: str, series: str, title: str) -> None:
    reason = credit_hub_drop_reason(hub=hub, series=series, title=title)
    assert reason is None, (
        f"Non-credit hub {hub!r} should not trigger credit_hub_drop_reason, "
        f"got {reason!r}"
    )


# ---------------------------------------------------------------------------
# should_exclude — conference announcement substrings
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("title,expected_substr", [
    (
        "7th Virtual Commodity Conference 2026",
        "title-substring:'virtual commodity conference'",
    ),
    (
        "2026 Energy and Power Credit Conference – BofA Securities",
        "title-substring:' credit conference'",
    ),
])
def test_should_exclude_conference_announcements(title: str, expected_substr: str) -> None:
    reason = should_exclude(title=title)
    assert reason == expected_substr, (
        f"Expected {expected_substr!r} for {title!r}, got {reason!r}"
    )


# ---------------------------------------------------------------------------
# should_exclude — date-only / thin titles
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("title", [
    "12 June 2026",
    "08 June 2026",
    "11-Jun-26 Close",
    "Week ending June 12, 2026",
    "Week ending January 5, 2026",
])
def test_should_exclude_date_only_title(title: str) -> None:
    reason = should_exclude(title=title)
    assert reason is not None, f"Expected DROP for date-only title {title!r}"
    assert "date-only-title" in reason, (
        f"Expected 'date-only-title' in reason for {title!r}, got {reason!r}"
    )


# Real analytical titles with a date must NOT match the date-only regex.
@pytest.mark.parametrize("title", [
    "May IPCA: broad inflation, plus hotspots",
    "May CPI review: Inflation inched up but remains benign",
    "A series of close calls: tight spreads",
    "Positioning for Iran resolution",
    "Warsh debut, war détente",
    "Weekly Update on Macro Outlook",  # "weekly update" but not a bare date
])
def test_should_exclude_not_triggered_on_real_titles(title: str) -> None:
    # These may still be caught by other rules (e.g. noise), but must
    # NOT be caught specifically by the date-only-title regex.
    # We import the raw regex to test that check in isolation.
    from ingest.filters.bofa import _DATE_ONLY_TITLE_RE  # noqa: PLC0415
    from ingest.filters import normalize_title  # noqa: PLC0415
    norm = normalize_title(title)
    assert not _DATE_ONLY_TITLE_RE.match(norm), (
        f"Date-only regex should NOT match analytical title {title!r}"
    )


# ---------------------------------------------------------------------------
# should_exclude — event-admin "in 1hr" / "in 1 hr" (D3 — _noise.py fix)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("title,expected_reason", [
    (
        "In 1hr: European Credit Research – 3Q26 Best Ideas",
        "noise:event-admin:'in 1hr'",
    ),
    (
        "In 1 hr: BofA World Cup Series: The future of AI",
        "noise:event-admin:'in 1 hr'",
    ),
    (
        "In 30 mins: Global Macro call",
        "noise:event-admin:'in 30 mins'",
    ),
    (
        "In 1 Hour: Expert Access: Macro panel",
        "noise:event-admin:'in 1 hour'",
    ),
])
def test_noise_event_admin_in_n_hr_variants(title: str, expected_reason: str) -> None:
    reason = classify_noise(title)
    assert reason == expected_reason, (
        f"Expected {expected_reason!r} for {title!r}, got {reason!r}"
    )


# The existing "In 1 HR: BofA World Cup Series" from the manifest hits
# should_exclude end-to-end.
def test_should_exclude_in_1_hr_bofa_title() -> None:
    title = "In 1 HR: BofA World Cup Series: The future of AI in finance"
    reason = should_exclude(title=title)
    assert reason is not None, f"Expected DROP for {title!r}"
    assert "event-admin" in reason, (
        f"Expected event-admin drop for {title!r}, got {reason!r}"
    )


# ---------------------------------------------------------------------------
# Regression — titles that must NOT be dropped by any bofa filter
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("title", [
    "Positioning for Iran resolution",
    "Slower into bonds",
    "The US Fixed Income Weekly",
    "Higher rates, more AI-capex, lower fragility",
    "3Q26 Best ideas",
    "A sentiment shift and a deep dive into the market",
    "May IPCA: broad inflation, plus hotspots",
    "May CPI review: Inflation inched up but remains benign",
    "Monsoon Tracker: Slow progress",
    "Japan: Oil shock: Pipeline pressures set the tone",
    "China – Will ample monetary liquidity continue to be a tailwind?",
    "Serbia politics: what's at stake and what's next",
    "Armenia: what is next to watch?",
    "IMF LIC-DSF 2026 Review: what changes and what doesn't",
    "BCB likely to cut this week, BCCH on hold",
])
def test_should_exclude_not_triggered_on_keep_list(title: str) -> None:
    reason = should_exclude(title=title)
    assert reason is None, (
        f"should_exclude should return None for kept title {title!r}, "
        f"got {reason!r}"
    )
