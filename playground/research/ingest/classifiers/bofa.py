"""BofA Securities Mercury classifier.

The crawler does most of the heavy lifting (hub-level + series-regex
+ MBS-data-table + credit-hub-allowlist drops). By the time the
classifier runs, surviving ReportRefs carry:

* ``hub`` — which Mercury hub URL surfaced the tile. This is the
  primary asset-class signal (Tier-1) — see ``_HUB_ASSET_CLASS``
  in :mod:`crawler_bofa` and the analogous map below.
* ``series`` — the flagship series name (Global Rates Weekly,
  Inflation Strategist, Emerging Insight, etc.). Sometimes more
  specific than the hub (e.g. an "Inflation Strategist" tile in the
  rates_inflation hub is RATES not generic MACRO).
* ``analyst_primary`` + ``analysts`` — for analyst-tag emission.
* ``subject`` — currently mirrors ``series`` (a single-name subject
  that survived the crawler is rare but possible; we tag it
  anyway).

Classification strategy:

1. **Tier-0** — ``hub`` → canonical asset_class. Decisive on most
   tiles (e.g. economics_overview → MACRO, fx_global → FX,
   credit_high_grade → CREDIT).
2. **Tier-1 override** — specific series names that are more
   specific than the hub (e.g. anything matching ``Technical
   Strategy`` / ``Technical Advantage`` from a rates / FX hub
   gets STRATEGY, not RATES or FX).
3. **EM-macro reclassification** — tiles from ``credit_em_*`` hubs
   or with macro-sovereign series (Watch / Economic Weekly /
   Emerging Insight / GEMs / EEMEA) that also hit macro keywords
   in the title are promoted to MACRO. Credit-strategy series
   (Strategist / Situation Room) stay CREDIT.
4. **Country / region** — BofA tiles don't carry structured country
   IDs; we surface country via word-boundary keyword matching on
   series + title. Specific anchors (BCB→BR, IPCA→BR, etc.) are
   checked before the generic short-code ambiguous keywords.

Pure function. No DB / network. Called twice per report (once for
relevance filter, once for write).
"""
from __future__ import annotations

import re

from .canonical import (
    ASSET_CLASS_COMMODITIES,
    ASSET_CLASS_CREDIT,
    ASSET_CLASS_EQUITY,
    ASSET_CLASS_FX,
    ASSET_CLASS_MACRO,
    ASSET_CLASS_RATES,
    ASSET_CLASS_STRATEGY,
    REGION_AMERICAS,
    REGION_APAC,
    REGION_EMEA,
    REGION_GLOBAL,
    REGION_LATAM,
    TAG_AUTHOR,
    TAG_COUNTRY,
    TAG_DISCIPLINE,
    TAG_REGION,
    TAG_THEME,
    TAG_VENDOR_PUBTYPE,
    VENDOR_DISPLAY,
)


# ─── Hub → canonical asset_class ────────────────────────────────────────
_HUB_TO_ASSET_CLASS: dict[str, str] = {
    "economics_overview":           ASSET_CLASS_MACRO,
    "economics_country":            ASSET_CLASS_MACRO,
    "investment_themes":            ASSET_CLASS_STRATEGY,
    "rates_regional":               ASSET_CLASS_RATES,
    "rates_inflation":              ASSET_CLASS_RATES,
    "fx_g10":                       ASSET_CLASS_FX,
    "fx_global":                    ASSET_CLASS_FX,
    "commodities":                  ASSET_CLASS_COMMODITIES,
    "futures":                      ASSET_CLASS_COMMODITIES,
    "credit_global":                ASSET_CLASS_CREDIT,
    "credit_strategy_americas":     ASSET_CLASS_CREDIT,
    "credit_high_grade":            ASSET_CLASS_CREDIT,
    "credit_high_yield":            ASSET_CLASS_CREDIT,
    "credit_securitized":           ASSET_CLASS_CREDIT,
    "credit_em_fi":                 ASSET_CLASS_CREDIT,
    "credit_em_corporate":          ASSET_CLASS_CREDIT,
    "credit_municipal":             ASSET_CLASS_CREDIT,
    "equity_regional":              ASSET_CLASS_EQUITY,
    "equity_etf":                   ASSET_CLASS_STRATEGY,
    "equity_em_equity":             ASSET_CLASS_EQUITY,
    "technical_analysis":           ASSET_CLASS_STRATEGY,
}


# ─── Hub → region bucket (when obvious; None when mixed) ────────────────
_HUB_TO_REGION: dict[str, str] = {
    "economics_country":            REGION_GLOBAL,   # has country tabs, default global
    "credit_em_fi":                 REGION_GLOBAL,   # EM is multi-region
    "credit_em_corporate":          REGION_GLOBAL,
    "equity_em_equity":             REGION_GLOBAL,
    "credit_municipal":             REGION_AMERICAS,  # US munis
    "credit_strategy_americas":     REGION_AMERICAS,
    "credit_securitized":           REGION_AMERICAS,  # US MBS
    "credit_high_grade":            REGION_AMERICAS,  # US HG
    "credit_high_yield":            REGION_AMERICAS,  # US HY
    # Most other hubs are global / multi-region — leave empty so
    # downstream classifiers can fall back to title heuristics.
}


# ─── Series-name override (Tier-1) ───────────────────────────────────────
# A handful of series names are more specific than the hub. Most live
# in cross-cutting hubs (rates_regional, fx_global, technical_analysis)
# where the series carries the real signal.
_TECHNICAL_SERIES_RE = re.compile(
    r"\b(Technical|Quant|FX Quant|Seasonality|Sentiment Survey)\b",
    re.IGNORECASE,
)
_STRATEGY_SERIES_RE = re.compile(
    r"\b(Strategy|Strategist|Thematic|Cross[-\s]Asset|Year Ahead|RIC)\b",
    re.IGNORECASE,
)


def _override_from_series(series: str, base: str) -> str:
    """Promote certain series names to STRATEGY when they're clearly
    cross-asset / thematic / technical even if the hub maps to a
    narrower class."""
    if base in (ASSET_CLASS_MACRO, ASSET_CLASS_RATES, ASSET_CLASS_FX,
                ASSET_CLASS_COMMODITIES):
        if _TECHNICAL_SERIES_RE.search(series) or _STRATEGY_SERIES_RE.search(series):
            return ASSET_CLASS_STRATEGY
    return base


# ─── EM-macro reclassification (Tier-2) ─────────────────────────────────
# Reports from credit_em_* hubs or with macro-sovereign series that hit
# macro keywords in title/series are reclassified as MACRO.
# Credit-STRATEGY series (Strategist / Situation Room) are exempt.

_EM_CREDIT_HUBS: frozenset[str] = frozenset({"credit_em_fi", "credit_em_corporate"})

# Series names that signal a macro/sovereign report even when in a credit hub.
_EM_MACRO_SERIES_RE = re.compile(
    r"\b(watch|economic\s+weekly|economic\s+viewpoint|economic\s+monitor|"
    r"emerging\s+insight|gems|eemea|asia\s+economic|what['’]s\s+priced\s+in)\b",
    re.IGNORECASE,
)

# Series names that are credit-strategy — NOT reclassified even in credit_em hubs.
_CREDIT_STRATEGY_SERIES_RE = re.compile(
    r"\b(strategist|situation\s+room|fixed\s+income\s+strategy|"
    r"high\s+yield\s+(?:&|and)\s+loan)\b",
    re.IGNORECASE,
)

# Macro keywords in title that clinch the reclassification.
_MACRO_KEYWORDS_RE = re.compile(
    r"\b(cpi|ipca|inflation|monetary|central\s+bank|"
    r"rate\s+cut|rate\s+hike|rate\s+decision|"
    r"election|politics|sovereign|fiscal|gdp|imf|"
    r"monsoon|liquidity|fx\s+reserves|"
    r"bcb|copom|bccch|banxico|rbi|boj|pboc|bok|fomc|ecb|boe)\b",
    re.IGNORECASE,
)


def _em_macro_reclassify(*, hub: str, series: str, title: str, base: str) -> str:
    """Reclassify CREDIT → MACRO for EM/sovereign macro reports.

    Only fires when ``base`` is CREDIT (i.e. the hub mapped to CREDIT).
    Credit-strategy series (Strategist / Situation Room) are exempt.

    Two promotion paths:
    A. Series is a recognised macro/sovereign series (Watch, Economic Weekly,
       Emerging Insight, GEMs, EEMEA, Asia Economic, What's priced in) →
       promote to MACRO unconditionally (the series name is the signal).
    B. Hub is credit_em_* AND the title contains a macro keyword (CPI, election,
       monetary, etc.) → promote to MACRO. This catches cases where the series
       isn't on the named list but the content is clearly macro.
    """
    if base != ASSET_CLASS_CREDIT:
        return base

    # Credit-strategy series are authoritative CREDIT — don't reclassify.
    if _CREDIT_STRATEGY_SERIES_RE.search(series or ""):
        return base

    # Path A: series name is a recognised macro/sovereign series.
    if _EM_MACRO_SERIES_RE.search(series or ""):
        return ASSET_CLASS_MACRO

    # Path B: EM credit hub + macro keyword in title/series.
    if hub in _EM_CREDIT_HUBS:
        blob = (series or "") + " " + (title or "")
        if _MACRO_KEYWORDS_RE.search(blob):
            return ASSET_CLASS_MACRO

    return base


# ─── Country anchor heuristics from series / title ──────────────────────
# BofA tiles don't expose structured country IDs. We use word-boundary
# matching for short/ambiguous codes to prevent substring false-positives
# (e.g. "us" matching inside "plus", "versus", "consensus", "focus").
#
# Order matters: specific anchors and multi-word names BEFORE ambiguous
# short codes. Within short codes, longer/rarer ones before shorter ones.

# Central-bank / series anchors — checked first (most specific).
# Each entry: (regex_pattern, country_code)
_CB_ANCHOR_RULES: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(pat, re.IGNORECASE), code)
    for pat, code in (
        # Series anchors — these fire on the series name alone.
        (r"\bBrazil\s+Watch\b",      "BR"),
        (r"\bIndia\s+Watch\b",       "IN"),
        (r"\bChina\s+Viewpoint\b",   "CN"),
        (r"\bJapan\s+Rates\b",       "JP"),
        (r"\bJapan\s+Watch\b",       "JP"),
        # Central-bank tickers (unambiguous short codes).
        (r"\bIPCA\b",                "BR"),   # Brazilian inflation index
        (r"\bBCB\b",                 "BR"),   # Banco Central do Brasil
        (r"\bCopom\b",               "BR"),   # BCB policy committee
        (r"\bBCCh\b",                "CL"),   # Banco Central de Chile
        (r"\bBanxico\b",             "MX"),   # Banco de México
        (r"\bRBI\b",                 "IN"),   # Reserve Bank of India
        (r"\bBoJ\b",                 "JP"),   # Bank of Japan
        (r"\bPBoC\b",                "CN"),   # People's Bank of China
        (r"\bBoK\b",                 "KR"),   # Bank of Korea
        (r"\bFOMC\b",                "US"),   # Federal Open Market Committee
        (r"\bFed\b",                 "US"),   # US Federal Reserve
        (r"\bECB\b",                 "EU"),   # European Central Bank
        (r"\bBoE\b",                 "UK"),   # Bank of England
        # Dotted short codes — \b doesn't work after a period (non-word char),
        # so use lookahead for whitespace or end-of-string instead.
        (r"\bu\.s\.(?:\s|$)",        "US"),   # "u.s. Treasury" / "u.s."
        (r"\bu\.k\.(?:\s|$)",        "UK"),   # "u.k. gilts" / "u.k."
    )
)

# Multi-word country names — safe, no ambiguity risk.
_MULTIWORD_COUNTRY_RULES: tuple[tuple[str, str], ...] = (
    ("united states",     "US"),
    ("united kingdom",    "UK"),
    ("euro area",         "EU"),
    ("eurozone",          "EU"),
    ("hong kong",         "HK"),
    ("new zealand",       "NZ"),
    ("south africa",      "ZA"),
    ("saudi arabia",      "SA"),
    ("north america",     "US"),  # approximate
)

# Short/ambiguous country keywords — matched with word boundaries (\b) to
# avoid false positives inside longer words (e.g. "us" in "plus").
_SHORT_COUNTRY_RULES: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(r"\b" + re.escape(kw) + r"\b", re.IGNORECASE), code)
    for kw, code in (
        # Longer/rarer short names first.
        ("türkiye",      "TR"),
        ("turkey",       "TR"),
        ("argentina",    "AR"),
        ("argentine",    "AR"),
        ("colombia",     "CO"),
        ("australia",    "AU"),
        ("singapore",    "SG"),
        ("malaysia",     "MY"),
        ("thailand",     "TH"),
        ("vietnam",      "VN"),
        ("indonesia",    "ID"),
        ("philippines",  "PH"),
        ("nigeria",      "NG"),
        ("germany",      "DE"),
        ("switzerland",  "CH"),
        ("taiwan",       "TW"),
        ("russia",       "RU"),
        ("france",       "FR"),
        ("brazil",       "BR"),
        ("mexico",       "MX"),
        ("egypt",        "EG"),
        ("canada",       "CA"),
        ("india",        "IN"),
        ("china",        "CN"),
        ("korea",        "KR"),
        ("japan",        "JP"),
        ("spain",        "ES"),
        ("italy",        "IT"),
        ("peru",         "PE"),
        ("chile",        "CL"),
        ("armenia",      "AM"),
        ("serbia",       "RS"),
        # Short ambiguous codes — word-boundary protected.
        ("us",           "US"),   # word-boundary stops "plus" / "versus"
        ("uk",           "UK"),
        ("eu",           "EU"),
    )
)


def _country_from_text(series: str, title: str) -> str | None:
    """Best-effort country extraction from series / title keywords.

    Checking order (most to least specific):
    1. Central-bank / series anchors (IPCA, BCB, FOMC, BoJ, etc.)
    2. Multi-word country names (no ambiguity risk, simple substring)
    3. Short country names with word-boundary regex (prevents "us" inside
       "plus", "versus", "consensus", etc.)
    """
    blob = (series + " " + title).lower()
    blob_original = series + " " + title  # preserve case for regex rules

    # 1. CB / series anchors (applied to original-case blob, regex has IGNORECASE).
    for pat, code in _CB_ANCHOR_RULES:
        if pat.search(blob_original):
            return code

    # 2. Multi-word country names (safe substring on lower-cased blob).
    for kw, code in _MULTIWORD_COUNTRY_RULES:
        if kw in blob:
            return code

    # 3. Short names with word-boundary regex.
    for pat, code in _SHORT_COUNTRY_RULES:
        if pat.search(blob_original):
            return code

    return None


def classify(ref) -> "object":
    from .models import ClassifyResult, Tag  # noqa: PLC0415

    title = (ref.title or "").strip()
    series = (getattr(ref, "series", "") or "").strip()
    hub = (getattr(ref, "hub", "") or "").strip()
    analyst_primary = (getattr(ref, "analyst_primary", "") or "").strip()
    analysts = tuple(getattr(ref, "analysts", ()) or ())

    # Tier-0: hub → asset_class
    asset_class = _HUB_TO_ASSET_CLASS.get(hub, "")
    # Tier-1: series override (technical / cross-asset strategy)
    if asset_class:
        asset_class = _override_from_series(series, asset_class)

    # Tier-2: EM-macro reclassification (CREDIT → MACRO for sovereign/macro
    # reports in credit_em hubs or with macro-sovereign series).
    if asset_class:
        asset_class = _em_macro_reclassify(
            hub=hub, series=series, title=title, base=asset_class,
        )

    # Region — start from hub, refine via country lookup.
    region_bucket = _HUB_TO_REGION.get(hub, "")
    country_code = _country_from_text(series, title)

    out_tags: list[Tag] = []

    # vendor_pubtype: emit the series name (it's BofA's editorial-level
    # publication unit, e.g. "Global Rates Weekly", "Inflation Strategist").
    # NB: dim_tag enforces global uniqueness on tag value alone (see
    # feedback-westpac-three-hubs memory) — we do NOT also emit the same
    # value as TAG_THEME, because that yields the same tag_id and
    # violates uq_research_map_report_tag on (report_id, tag_id).
    if series:
        out_tags.append(Tag(TAG_VENDOR_PUBTYPE, series[:50]))

    # discipline: canonical asset class
    if asset_class:
        out_tags.append(Tag(TAG_DISCIPLINE, asset_class.lower()))

    # region / country
    if region_bucket:
        out_tags.append(Tag(TAG_REGION, region_bucket))
    if country_code:
        out_tags.append(Tag(TAG_COUNTRY, country_code))

    # authors — primary first, cap at 4 to keep map_report_tag tidy.
    seen_a: set[str] = set()
    for nm in (analyst_primary, *analysts):
        nm = (nm or "").strip()
        if not nm or nm.lower() in seen_a:
            continue
        seen_a.add(nm.lower())
        out_tags.append(Tag(TAG_AUTHOR, nm[:50]))
        if len(seen_a) >= 4:
            break

    # Context blob for RAG.
    lines = [
        f"Vendor: {VENDOR_DISPLAY.get('bofa', 'BofA Securities Research')}",
        f"Title: {title}",
        f"Published: {ref.publish_date.isoformat()}",
    ]
    if series:
        lines.append(f"Series: {series}")
    if hub:
        lines.append(f"Hub: {hub}")
    if asset_class:
        lines.append(f"Asset class: {asset_class}")
    if country_code:
        lines.append(f"Country: {country_code}")
    if region_bucket:
        lines.append(f"Region: {region_bucket}")
    if analyst_primary:
        lines.append(f"Primary analyst: {analyst_primary}")
    if analysts and len(analysts) > 1:
        lines.append(f"All analysts: {', '.join(analysts[:6])}")
    context = "\n".join(lines)

    return ClassifyResult(
        asset_class=asset_class,
        country_code=country_code,
        tags=out_tags,
        context=context,
    )
