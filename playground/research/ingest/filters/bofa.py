"""Discovery filter for BofA Securities Mercury.

The substantive drops live in
:func:`crawler_bofa._drop_reason` (hub-level blanket + series-regex
single-name + MBS data-table). This module provides:

1. :func:`should_exclude` — title-level backstop (noise families + thin
   titles + conference announcement drops). Called by the crawler after
   ``_drop_reason`` passes.

2. :func:`credit_hub_drop_reason` — credit-hub allowlist gate. Credit hubs
   default-DROP unless the series/title matches macro/sovereign/strategy
   KEEP signals. Mirrors the ``_EQUITY_HUBS`` blanket-drop precedent for
   equity hubs. Called by the crawler for tiles in the eight credit hubs.

See ``docs/admin/research/scrapers/bofa.md`` for full context.
"""
from __future__ import annotations

import re

from . import match_title_prefix, match_title_regex, match_title_substring
from ._noise import classify_noise


# ---------------------------------------------------------------------------
# Credit hubs — the eight hubs that default-DROP unless kept by allow-list
# ---------------------------------------------------------------------------

_CREDIT_HUBS: frozenset[str] = frozenset({
    "credit_global",
    "credit_strategy_americas",
    "credit_high_grade",
    "credit_high_yield",
    "credit_securitized",
    "credit_em_fi",
    "credit_em_corporate",
    "credit_municipal",
})

# Series or title fragments that identify CREDIT-STRATEGY output we keep
# (flagship cross-credit / cross-asset strategy series). Checked against
# series first, then title.
_CREDIT_STRATEGY_KEEP_RE = re.compile(
    r"\b(strategist|strategy|situation\s+room|fixed\s+income|"
    r"best\s+ideas?|cross[-\s]asset|credit\s+derivatives|"
    r"market\s+review|securitized\s+products?\s+strategy|"
    r"securitization\s+weekly|agency\s+mbs\s+weekly|"
    r"high\s+yield\s+(?:&|and)\s+loan)\b",
    re.IGNORECASE,
)

# Series or title fragments that identify SOVEREIGN / EM-MACRO output we keep.
# Checked against series first, then title.
_SOVEREIGN_EM_KEEP_RE = re.compile(
    r"\b(watch|economic\s+weekly|economic\s+viewpoint|economic\s+monitor|"
    r"emerging\s+insight|gems|eemea|em\s+|macro|morning\s+credit|"
    r"european\s+morning\s+credit|asia\s+economic)\b",
    re.IGNORECASE,
)

# Title keywords that clinch a macro/sovereign classification for credit-hub
# tiles. Checked (case-insensitive) against the normalised title blob when
# the series alone doesn't match the keep lists above.
_MACRO_TITLE_KEYWORDS: tuple[str, ...] = (
    "cpi", "ipca", "inflation", "monetary", "central bank",
    "rate cut", "rate hike", "rate decision",
    "election", "politics", "sovereign", "fiscal",
    "gdp", "imf", "monsoon", "liquidity", "fx reserves",
    "bcb", "copom", "bccch", "banxico", "rbi", "boj", "pboc",
    "bok", "fomc", "ecb", "boe",
)


def credit_hub_drop_reason(*, hub: str, series: str, title: str) -> str | None:
    """Return a drop reason for a credit-hub tile that doesn't match the
    macro/sovereign/strategy KEEP signals, or ``None`` to keep.

    Only called when ``hub`` is in ``_CREDIT_HUBS``. Mirrors the equity-hub
    blanket-drop: credit hubs default-drop unless the series or title signals
    macro-relevant content.
    """
    if hub not in _CREDIT_HUBS:
        return None

    series_lc = (series or "").lower()
    title_lc = (title or "").lower()
    blob = series_lc + " " + title_lc

    # KEEP: credit-strategy / flagship series (Strategist, Situation Room, etc.)
    if _CREDIT_STRATEGY_KEEP_RE.search(series or "") or _CREDIT_STRATEGY_KEEP_RE.search(title or ""):
        return None

    # KEEP: sovereign/EM-macro series or title fragments
    if _SOVEREIGN_EM_KEEP_RE.search(series or "") or _SOVEREIGN_EM_KEEP_RE.search(title or ""):
        return None

    # KEEP: macro keywords in title (CPI, IPCA, election, etc.)
    for kw in _MACRO_TITLE_KEYWORDS:
        if kw in blob:
            return None

    # Everything else in a credit hub: DROP.
    tag = (series or title or "unknown")[:30]
    return f"credit-hub-nonmacro:{tag}"


# ---------------------------------------------------------------------------
# BofA-specific title drops (backstop for titles that slip past the
# credit-hub gate or arrive from non-credit hubs)
# ---------------------------------------------------------------------------

EXCLUDED_TITLE_PREFIXES: tuple[str, ...] = (
    # Empty — BofA-specific prefix drops added here if observed in production.
)

EXCLUDED_TITLE_SUBSTRINGS: tuple[str, ...] = (
    # Conference announcement pings (not research content).
    "virtual commodity conference",   # BofA: "7th Virtual Commodity Conference 2026"
    " credit conference",             # BofA: "2026 Energy and Power Credit Conference..."
)

# Date-only / boilerplate titles: thin MBS data-pack date stamps and futures
# close snapshots that slipped past the series-level MBS-datatable check.
# Pattern matches:
#   "12 June 2026"  /  "08 June 2026"         — MBS package date stamps
#   "11-Jun-26 Close"                          — futures daily close
#   "Week ending June 12, 2026"                — HG energy data table
# Month name pattern covers both abbreviated (Jun) and full (June) forms.
# Anchored tight so real analytical titles with a date in them don't match.
# Month name pattern covering both abbreviated (Jun) and full (June) forms.
_MONTH_PAT = (
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may"
    r"|june?|july?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
)
_DATE_ONLY_TITLE_RE = re.compile(
    r"^(?:"
    + r"\d{1,2}\s+" + _MONTH_PAT + r"\s+\d{4}"                    # "12 June 2026"
    + r"|\d{1,2}-" + _MONTH_PAT + r"-\d{2,4}\s+close"             # "11-Jun-26 Close"
    + r"|week\s+ending\s+" + _MONTH_PAT + r"[\s\d,]+"             # "Week ending June 12, 2026"
    + r")\s*$",
    re.IGNORECASE,
)

_DATE_ONLY_TITLE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("date-only-title", _DATE_ONLY_TITLE_RE),
)


def should_exclude(*, title: str) -> str | None:
    """Return a drop reason if the title matches BofA-specific noise, else None.

    Called by the crawler after ``_drop_reason`` (hub-blanket + series +
    MBS data-table) passes. Checks, in order:
    1. BofA-specific title-prefix/substring patterns.
    2. Date-only / thin-title regex.
    3. Shared noise families (chart-pack / morning-note / event-admin).
    """
    if not title:
        return None

    reason = match_title_prefix(title, EXCLUDED_TITLE_PREFIXES)
    if reason is not None:
        return reason

    reason = match_title_substring(title, EXCLUDED_TITLE_SUBSTRINGS)
    if reason is not None:
        return reason

    reason = match_title_regex(title, _DATE_ONLY_TITLE_PATTERNS)
    if reason is not None:
        return reason

    return classify_noise(title)
