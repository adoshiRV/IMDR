"""Tests for the Citi Velocity Research title-keyword refinement.

Pins:
1.  Titles that were previously mislabelled STRATEGY/MACRO must now
    resolve to RATES, FX, or CREDIT.
2.  Central-bank / macro-release titles must stay MACRO (macro guard wins).
3.  Confident results (EQUITY, COMMODITIES) are never overridden.

The helper under test is ``_title_refine_asset_class`` which is the
pure-function that ``classify()`` calls as a late Tier-1 pass.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_RESEARCH_ROOT = Path(__file__).resolve().parents[3] / "playground" / "research"
if str(_RESEARCH_ROOT) not in sys.path:
    sys.path.insert(0, str(_RESEARCH_ROOT))

from ingest.classifiers.citi import _title_refine_asset_class  # noqa: E402
from ingest.classifiers.canonical import (  # noqa: E402
    ASSET_CLASS_COMMODITIES,
    ASSET_CLASS_CREDIT,
    ASSET_CLASS_EQUITY,
    ASSET_CLASS_FX,
    ASSET_CLASS_MACRO,
    ASSET_CLASS_RATES,
    ASSET_CLASS_STRATEGY,
)


# ---------------------------------------------------------------------------
# RATES — must be promoted from STRATEGY or MACRO
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("title,starting_class", [
    # Evidence titles from the task spec
    ("EMU spreads de-couple & SSA RV trade",     ASSET_CLASS_STRATEGY),
    ("Summer seasonality vs supply",             ASSET_CLASS_STRATEGY),
    ("30y — robust due to domestic demand",      ASSET_CLASS_STRATEGY),
    ("Range-bound SOFR/IORB",                   ASSET_CLASS_STRATEGY),
    ("Add Dec26/27 FOMC OIS steepener",          ASSET_CLASS_STRATEGY),
    ("10yr Auction – Strong Demand",             ASSET_CLASS_STRATEGY),
    # Rates keywords when the structured signal left us at MACRO
    ("Weekly Auction Preview – Gilts",          ASSET_CLASS_MACRO),
    ("Bund Relative Value: flattener ideas",    ASSET_CLASS_STRATEGY),
    ("BTP-OAT spread dynamics",                 ASSET_CLASS_STRATEGY),
    ("UST 5s30s steepener entry",               ASSET_CLASS_STRATEGY),
    ("Front-end SOFR: how far can it rally?",   ASSET_CLASS_STRATEGY),
    ("JGB duration and asset-swap overview",    ASSET_CLASS_STRATEGY),
    ("TIPS breakeven monitor",                  ASSET_CLASS_STRATEGY),
    ("Index Roll Down and Relative Value",      ASSET_CLASS_STRATEGY),
])
def test_rates_promoted(title: str, starting_class: str) -> None:
    result = _title_refine_asset_class(title, starting_class)
    assert result == ASSET_CLASS_RATES, (
        f"Expected RATES for {title!r} (start={starting_class}), got {result!r}"
    )


# ---------------------------------------------------------------------------
# FX — must be promoted from STRATEGY or MACRO
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("title,starting_class", [
    # Evidence titles from the task spec
    ("An analysis of the USD/JPY price formation mechanism", ASSET_CLASS_STRATEGY),
    ("Short NZDUSD as a risk-off hedge",                    ASSET_CLASS_STRATEGY),
    ("Trade idea: unwinding basket long KRW, SGD, TWD",     ASSET_CLASS_STRATEGY),
    # Additional FX signals
    ("EUR/USD: ranging ahead of payrolls",                  ASSET_CLASS_STRATEGY),
    ("GBP/USD: post-election positioning",                  ASSET_CLASS_STRATEGY),
    ("CNY depreciation and carry trade unwind",             ASSET_CLASS_STRATEGY),
    ("FX volatility: positioning for the FOMC",             ASSET_CLASS_STRATEGY),
    ("De-dollarisation: structural or cyclical?",           ASSET_CLASS_STRATEGY),
])
def test_fx_promoted(title: str, starting_class: str) -> None:
    result = _title_refine_asset_class(title, starting_class)
    assert result == ASSET_CLASS_FX, (
        f"Expected FX for {title!r} (start={starting_class}), got {result!r}"
    )


# ---------------------------------------------------------------------------
# CREDIT — must be promoted from STRATEGY or MACRO
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("title,starting_class", [
    # Evidence titles from the task spec
    ("Agency CMBS Holding Steady",               ASSET_CLASS_STRATEGY),
    ("Stressing ABS, Calling on Non-QM",         ASSET_CLASS_STRATEGY),
    ("Prepayment drivers in UK RMBS",            ASSET_CLASS_STRATEGY),
    ("Credit Snapshot - High Yield",             ASSET_CLASS_STRATEGY),
    # Additional credit signals
    ("CDX IG: tightening into year-end",         ASSET_CLASS_STRATEGY),
    ("iTraxx Crossover — spread widening risk",  ASSET_CLASS_STRATEGY),
    ("Investment Grade credit outlook",          ASSET_CLASS_STRATEGY),
    ("CLO market update",                        ASSET_CLASS_STRATEGY),
    ("Leveraged loan technicals",                ASSET_CLASS_STRATEGY),
])
def test_credit_promoted(title: str, starting_class: str) -> None:
    result = _title_refine_asset_class(title, starting_class)
    assert result == ASSET_CLASS_CREDIT, (
        f"Expected CREDIT for {title!r} (start={starting_class}), got {result!r}"
    )


# ---------------------------------------------------------------------------
# MACRO guard — must stay MACRO regardless of any rates/FX/credit words
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("title,starting_class", [
    # Evidence titles from the task spec (must NOT become RATES/FX/CREDIT)
    ("FOMC Preview – Hawkish SEP, dovish Warsh",     ASSET_CLASS_MACRO),
    ("Norges Bank Preview",                          ASSET_CLASS_MACRO),
    ("Pickup in Core CPI Momentum",                  ASSET_CLASS_MACRO),
    # Central-bank title that also contains "rates" — guard wins
    ("ECB: once hikes are underway",                 ASSET_CLASS_MACRO),
    ("ECB: once hikes are underway",                 ASSET_CLASS_STRATEGY),
    # Macro data prints
    ("US Payrolls: a closer look at revisions",      ASSET_CLASS_MACRO),
    ("China GDP: stronger than expected",            ASSET_CLASS_MACRO),
    ("UK Inflation Watch",                           ASSET_CLASS_MACRO),
    ("Fed minutes: a hawkish surprise",              ASSET_CLASS_MACRO),
    # Preview / watch keywords
    ("BoJ Policy Watch – June meeting",              ASSET_CLASS_STRATEGY),
    ("RBA Preview: hold with a twist",               ASSET_CLASS_STRATEGY),
    ("FOMC Preview: 25bp cut odds",                  ASSET_CLASS_STRATEGY),
    # NB: the FOMC OIS steepener title is RATES (OIS/steepener before
    # "FOMC" only appears there as a meeting date anchor, not a macro call)
    # so "FOMC" alone doesn't guard; "FOMC Preview" does via "preview" pattern.
])
def test_macro_guard_keeps_macro(title: str, starting_class: str) -> None:
    result = _title_refine_asset_class(title, starting_class)
    assert result == ASSET_CLASS_MACRO, (
        f"Expected MACRO for {title!r} (start={starting_class}), got {result!r}"
    )


# ---------------------------------------------------------------------------
# Confident classes are never overridden
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("title,starting_class,expected", [
    ("RMBS holdings in equity portfolios", ASSET_CLASS_EQUITY,      ASSET_CLASS_EQUITY),
    ("CDX implied vol vs commodities",     ASSET_CLASS_COMMODITIES, ASSET_CLASS_COMMODITIES),
    ("FX rates dashboard",                 ASSET_CLASS_FX,          ASSET_CLASS_FX),
    ("JGB auction results",               ASSET_CLASS_RATES,        ASSET_CLASS_RATES),
    ("CDX IG spread monitor",             ASSET_CLASS_CREDIT,       ASSET_CLASS_CREDIT),
])
def test_confident_classes_not_overridden(
    title: str, starting_class: str, expected: str
) -> None:
    result = _title_refine_asset_class(title, starting_class)
    assert result == expected, (
        f"Expected {expected!r} (unchanged) for {title!r} "
        f"(start={starting_class}), got {result!r}"
    )


# ---------------------------------------------------------------------------
# STRATEGY stays STRATEGY when no keyword fires
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("title", [
    "Equity Allocation: overweight EM",
    "Annual Outlook 2026: navigating uncertainty",
    "Model Portfolio rebalancing",
    "Thematic deep dive: energy transition",
    "Cross-asset flows update",
])
def test_strategy_stays_strategy(title: str) -> None:
    result = _title_refine_asset_class(title, ASSET_CLASS_STRATEGY)
    assert result == ASSET_CLASS_STRATEGY, (
        f"Expected STRATEGY for {title!r}, got {result!r}"
    )
