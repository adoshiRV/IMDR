"""Tests for is_single_name_equity — Barclays EQUITY and CREDIT branches.

Pins the 2026-06-15 fixes for three gaps:

GAP 1 — EQUITY default-drop:
  * Pure sector/single-company titles → DROP ("equity-vendor-default-drop:barclays")
  * "European Equity and Credit Strategy" → KEEP (sole cross-cutting survivor)
  * Cross-vendor conf-event titles → DROP ("equity-conf-event")

GAP 2 — CREDIT default-drop (keep-allowlist approach):
  * "US HY Research: Kohl's (KSS):" pattern → DROP
  * "US HG Research: Target (TGT):" pattern → DROP
  * Single-issuer earnings notes → DROP
  * "US Credit Alpha" / "EM Credit Strategy" / "Global CLOs" → KEEP
  * Securitisation data-runs (MBS PRICE REPORT) → KEEP
  * Macro/rates/FX reports unaffected (no CREDIT asset_class) → KEEP

GAP 3 — CJK filter: covered in test_barclays_filters.py (filter layer).

Reference corpus: 274 EQUITY + 187 CREDIT docs, vendor_id=2, >= 2026-05-20.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

_RESEARCH_ROOT = Path(__file__).resolve().parents[3] / "playground" / "research"
if str(_RESEARCH_ROOT) not in sys.path:
    sys.path.insert(0, str(_RESEARCH_ROOT))

from ingest.classifiers.canonical import (  # noqa: E402
    ASSET_CLASS_CREDIT,
    ASSET_CLASS_EQUITY,
    ASSET_CLASS_MACRO,
    ASSET_CLASS_RATES,
    ASSET_CLASS_FX,
)
from ingest.classifiers.models import ClassifyResult, Tag  # noqa: E402
from ingest.relevance import is_single_name_equity  # noqa: E402


def _result(asset_class: str) -> ClassifyResult:
    """Minimal ClassifyResult with given asset_class and no ticker tags."""
    return ClassifyResult(asset_class=asset_class, tags=[])


# ---------------------------------------------------------------------------
# GAP 1 — EQUITY: sector titles that must DROP
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("title", [
    # Pinned from spec + corpus
    "U.S. REITs: Weekly Observations",
    "European Construction & Building Materials: Capital Allocation",
    "U.S. Large-Cap Banks: Capital Outlook: A more pragmatic capital regime emerges",
    # Broader sector wraps (confirmed in 274-doc corpus)
    "U.S. Autos & Mobility: DriveBytes: May'26 US LV SAAR",
    "European Banks: Weekly Briefing; CoW: TRS mechanics",
    "China Technology: CBO - China Brief Overnight - June 5, 2026",
    "U.S. Large-Cap Banks: Weekly Bank Briefing",
    "European Aviation Daily: Icarus",
    "Global Metals & Mining Valuation Sheet",
    "Retail Detail (Inditex/B&M results, Pepco Dealz Poland sale)",
    "U.S. Software: rAImo's AI Newsletter",
    "Barclays T.R.U.C.K.S. — Tracking Real-time U.S. Cargo KPIs",
    "RevPAR Weekly: Strong week for Revpar",
    "Signal in the Noise Vol. 233: Why the US is ground zero for FWA",
    # "Capital" compound words that are sector-specific (not top-down)
    "European Construction & Building Materials: Capital Allocation: Buyback Tracker",
    "Integrated Energy: Buyback watch",
    # "strategy" word that appears in sector context (should NOT match allowlist
    # because the allowlist requires "equity ... strategy" or "cross-asset")
    "Global Biopharmaceuticals: ADA Conference Planner and Preview",
])
def test_barclays_equity_drops(title: str) -> None:
    """Barclays EQUITY sector titles must be dropped."""
    drop, reason = is_single_name_equity(
        vendor_code="barclays",
        result=_result(ASSET_CLASS_EQUITY),
        title=title,
    )
    assert drop, f"Expected DROP for {title!r} but got keep (reason={reason!r})"
    assert "equity" in reason.lower() or reason == "equity-conf-event", (
        f"Unexpected reason {reason!r} for {title!r}"
    )


# ---------------------------------------------------------------------------
# GAP 1 — EQUITY: cross-asset titles that must KEEP
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("title", [
    # Pinned from spec (the sole survivor in the 7-day window)
    "European Equity and Credit Strategy: What after the ECB hike",
    # Allowlist phrases
    "European Equity & Credit Strategy: Positioning Update",
    "Global Equity and Credit Research Strategy",
    "Cross-Asset Outlook: Risk-On or Risk-Off?",
    "Global Cross Asset Strategy: Monthly",
])
def test_barclays_equity_keeps(title: str) -> None:
    """Barclays cross-asset / equity-credit-strategy titles must be kept."""
    drop, reason = is_single_name_equity(
        vendor_code="barclays",
        result=_result(ASSET_CLASS_EQUITY),
        title=title,
    )
    assert not drop, f"Expected KEEP for {title!r} but got drop (reason={reason!r})"


# ---------------------------------------------------------------------------
# GAP 1 — EQUITY: conf-event titles drop via cross-vendor gate
# (fires before the Barclays branch)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("title", [
    "Randstad: Takeaways from Virtual Staffing Trip (RAND, MAN, RHI)",
    "Private Equity Funds: Takeaways from Bain's mid-year private equity market report",
    "CEE Banks Investor Field Trip: Growth intact, earnings durability debated",
    "U.S. Small & Mid Cap Biotechnology: Lung Cancer KOL Lunch: Takeaways",
    "European Software & Payments: Takeaways from Money20/20",
])
def test_barclays_equity_conf_event_drops(title: str) -> None:
    """Barclays EQUITY conference/event titles must drop via equity-conf-event."""
    drop, reason = is_single_name_equity(
        vendor_code="barclays",
        result=_result(ASSET_CLASS_EQUITY),
        title=title,
    )
    assert drop, f"Expected DROP for {title!r} but got keep (reason={reason!r})"
    assert reason == "equity-conf-event", (
        f"Expected 'equity-conf-event' for {title!r}, got {reason!r}"
    )


# ---------------------------------------------------------------------------
# GAP 2 — CREDIT: single-name issuer notes now KEEP (2026-07-16, Fold 1a —
# recall-first; issuer-level credit is wanted). Retitled from the old
# "must DROP" test. See docs/admin/development/credit_bofa.md.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("title", [
    # Pinned from spec
    "US HY Research: Kohl's (KSS): Regaining Solid Footing",
    "US HG Research: Target (TGT): 1Q26 Review",
    "European HY Research: PureGym (PURGYM): Some headline",
    # From corpus
    "European HY Research: ADRBID: Here we go again",
    "European HY Research: PINEFI: Timing is everything",
    "European HY Research: LOXAM / KILOTO: Opportunities outside of France",
    "European HY Research: SFRFP, ILDFP: A MoU is finally signed at Altice France",
    "Asia-Pac HY Research: SoftBank Group Corp: Immediate downgrade risk subsided",
    "European HG Research: Adecco (ADENVX): Margin disappointment",
    "European HG Research: UCGIM/CMZB: Positive skew for CMZB subs",
    "European HG Research: VGP-SAGAX initiation: Diverging growth models",
    "EEMEA Corporate Credit: Ulker (ULKER): Strong balance sheet",
    "EEMEA Corporate Credit: Navoi Mining (NAVOIM): A low cost giant",
    "US HG Research: HPE F2Q26 Results: Harder to ignore",
    "US HG Research: AVGO F2Q26 Results: Momentum meets math",
    "US HG Research: ORCL F4Q26 Results: The Customer Comes (and Pays) First",
    "US HG Research: HG Healthcare: CVS versus HCA - Where the Value is Now",
    "US HG Research: DELL/HPQ Results: One of these things is not like the other",
    # Named companies without sector framing
    "Tyson, JBS and Pilgrim's Pride: Headlines Weighing More than Fundamentals",
])
def test_barclays_credit_single_name_now_keeps(title: str) -> None:
    """Barclays CREDIT single-name issuer notes are now KEPT (Fold 1a,
    2026-07-16 keep-by-default — was DROP under the retired keep-allowlist)."""
    drop, reason = is_single_name_equity(
        vendor_code="barclays",
        result=_result(ASSET_CLASS_CREDIT),
        title=title,
    )
    assert not drop, f"Expected KEEP for {title!r} but got drop (reason={reason!r})"


# ---------------------------------------------------------------------------
# GAP 2 — CREDIT: strategy / multi-name series that must KEEP
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("title", [
    # Pinned from spec
    "US Credit Alpha: Sea of calm",
    "EM Credit Strategy: Emerging Markets Credit Monitor",
    "MBS PRICE REPORT-20260612",
    "Global CLOs: CLO Census",
    # From corpus
    "European Credit Alpha: Wait and watch",
    "Asia Credit Alpha: Sticky spreads",
    "US Investment Grade & High Yield: Capitulation and Complacency Signals",
    "MBS DAILY MARKET ANALYSIS- June  1, 2026",
    "Seasoned Pass-through OAS Report-20260601",
    "Roll Analysis Report-20260601",
    "Carry Analysis Report-20260601",
    "Price Change Attribution Report-20260601",
    "FRM Daily OAS Report-20260601",
    "Cross Sector Analysis Report-20260601",
    "Global Credit Derivatives Research: CDS index and TRS positioning",
    "CDS Relative Value: UK corporate CDS: a cross-asset lens",
    "Systematic Credit: Barclays Credit Factor Insights: Holding In",
    "Macro Credit Views: Positive convexity to Europe performance",
    "US Credit Research: AI Infrastructure Financing: Tracking Issuance Across Asset Classes",
    "European corporate credit fund flows: Outflows from IG, inflows in HY",
    "European Investment Grade: €-IG steady amid UK vol",
    "European High Yield: Dissecting the UK Premium",
    "European Hybrid Capital Monthly Update: May 2026",
    "Hybrid Capital: Cross Atlantic Weekly Hybrid Monitor",
    "The AAA Investor: What to expect from June covered bond supply?",
    "US Securitized Credit: Monthly Securitized Products Snapshot",
    "European Leveraged Loans: May 2026 Loans Monthly",
    "US Leveraged Finance: Seizing opportunities in CCCs",
    "Global CLOs: Technical Titan: Net Downgrades Are Getting Worse",
    "Asia Credit Research and Strategy: Ratings reboot",
    "Asia Credit Research & Strategy: Asia Credit Survey Results",
    "US HY Research: E&P: Assessing the High Yield E&P Maturity Wall",
    "US HY Research: Oil Services: Trends in Offshore Drilling",
    "US HY Research: Midstream: Assessing the HY Midstream Maturity Wall",
    "US HY Research: Technology Comp Sheets",
    "US HY Research: High Yield Telecom, Cable, Satellites: Comp Sheets",
    "US HY Research: HY Consumer Products: Comp Sheets",
    "US HY Research: Mortgage Finance Cheat Sheet: 1Q26 Credit Metrics",
    "US HY Research: HY Media & Entertainment: No longer trading at",
    "HY-Lights: Sectors re-sliced",
    "Creditcast: The democratisation of credit",
    "Crosscast: Fertilizer supply shock: LatAm implications",
    "HG Pharmaceuticals: Partner Up - PFE and BMY Are Showing Other Ways to Grow",
    "HG Chemicals: Charts worth a look",
    "IG Technology: What would US stakes in OpenAI and Anthropic mean",
    "High Grade Utilities: 2026 Issuance Tracker",
    "HG Research: Consumer Products, Food & Beverage: M&A Updates",
    "European Banks supply (May 2026): AT1 supply surges",
    "LatAm Corporate Credit Strategy: May Performance Overview",
    "European HG Research: CASTSS: Back to basics",
    "Colombian Local and Credit Views: The price is (to the) right",
    "Emerging Asia Sovereign Credit: Sri Lanka: Rate hikes begin",
    "EGYPT sovereign credit: Weathering the storm",
    "Zambia sovereign credit: Tender realities",
    "European Credit — Appendices: Fundamentals in focus",
    "European Overview: Wait and watch",
    "BDCs vs. REITs: Lessons Learned from Past Redemption Waves",
    "Five in Five: REITWeek Takeaways 2026",
    "Airlines: Show Me the Yield",
    "Italian banks: M&A heats up",
    "Insurance case studies: (Re)location, location, location",
    "AI in Fixed Income Survey: The buy-side view on AI",
])
def test_barclays_credit_keeps(title: str) -> None:
    """Barclays CREDIT strategy / multi-name series must be kept."""
    drop, reason = is_single_name_equity(
        vendor_code="barclays",
        result=_result(ASSET_CLASS_CREDIT),
        title=title,
    )
    assert not drop, f"Expected KEEP for {title!r} but got drop (reason={reason!r})"


# ---------------------------------------------------------------------------
# CREDIT: pure non-research admin/logistics still DROPS (Fold 1a)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("title", [
    "US HY Research: HY Healthcare Earnings Calendar 2Q26",
    "Aviation Debt: REGISTRATION OPEN - 16th Annual Aviation Forum",
    "REITs: Join Our Expert Call - Multifamily Outlook",
    "European Credit: Save the Date - 2026 Credit Conference",
])
def test_barclays_credit_admin_drops(title: str) -> None:
    """Calendars / event-registration pings still drop as credit-admin-drop."""
    drop, reason = is_single_name_equity(
        vendor_code="barclays",
        result=_result(ASSET_CLASS_CREDIT),
        title=title,
    )
    assert drop and reason == "credit-admin-drop", (
        f"Expected credit-admin-drop for {title!r}, got drop={drop} reason={reason!r}"
    )


# ---------------------------------------------------------------------------
# Macro / Rates / FX unaffected — must all KEEP
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("title, asset_class", [
    ("Global Economics Weekly", ASSET_CLASS_MACRO),
    ("Global Rates Weekly", ASSET_CLASS_RATES),
    ("FX & EM Weekly Thoughts", ASSET_CLASS_FX),
    ("Federal Reserve Commentary: June FOMC preview", ASSET_CLASS_MACRO),
    ("Emerging Markets Macro Quarterly", ASSET_CLASS_MACRO),
    ("Commodities Weekly: Oil Supply Dynamics", ASSET_CLASS_MACRO),
])
def test_macro_rates_fx_unaffected(title: str, asset_class: str) -> None:
    """Macro/rates/FX reports are unaffected by the Barclays EQUITY/CREDIT branches."""
    drop, reason = is_single_name_equity(
        vendor_code="barclays",
        result=_result(asset_class),
        title=title,
    )
    assert not drop, (
        f"Expected KEEP for {title!r} (asset_class={asset_class!r}) "
        f"but got drop (reason={reason!r})"
    )
