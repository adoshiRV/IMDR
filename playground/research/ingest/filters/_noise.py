"""Shared discovery-noise classifier — vendor-agnostic title rules.

Each vendor's ``should_exclude`` calls :func:`classify_noise` as a final
catch-all after its own vendor-native signals (companies[], productFocus,
business-group, etc.). This module owns three families of noise that
recur across vendors and aren't tied to any single vendor's structured
metadata:

* **Event admin** — meeting invites, webinar reminders, "starts in 1
  hour" pings, rescheduled notices. Pure calendar entries, never
  analytical content. Mirrors prefixes already in
  ``filters/barclays.py::EXCLUDED_TITLE_PREFIXES`` — promoted here so
  every vendor benefits without per-module duplication.

* **Morning notes** — daily sales-recap titles that ship every business
  day, carry minimal analytical content, and pollute embeddings.
  Examples: ANZ "Australian Morning Focus" / "Daily Rates RV Pack", DB
  "Early Morning Reid" / "DBDaily", Westpac "Morning Report", HSBC
  "Americas FX Morning Bullets <date>", Citi date-of-week index pages.

* **Chart packs / pure-data sheets** — programmatic relative-value /
  pricing-analytics SKUs with no narrative. Heavily concentrated at
  JPM (~270 daily SKUs) but every vendor has some.

Reasons returned use a ``"noise:<family>:<pattern>"`` shape so logs
make the rule traceable:

    "noise:event-admin:'reminder:'"
    "noise:morning-note:'dbdaily:'"
    "noise:chart-pack:'rich/cheap'"

If a new pattern surfaces in production [DROP] logs, add it to the
relevant tuple below with a one-line comment naming the vendor + a
sample title. Tests in ``test_noise_filter.py`` pin one real-world
example per pattern.
"""
from __future__ import annotations

import re

from . import (
    match_title_prefix,
    match_title_regex,
    match_title_substring,
    normalize_title,
)


# ---------------------------------------------------------------------
# Family 1 — Event admin (meeting invites, reminders, time-imminent
# pings). Prefix-anchored against the normalised title.
# ---------------------------------------------------------------------
EVENT_ADMIN_PREFIXES: tuple[str, ...] = (
    # Invites / registrations
    "invite:",                # generic vendor pattern
    "webinar invite",         # Barclays: "Webinar Invite: Analyst Access: ..."
    "webcast:",               # legacy
    "conference call:",       # legacy
    "save the date",          # Barclays: "SAVE THE DATE: EU MedTech ..."
    "client web conference",  # SocGen: "Client Web Conference Invitation – Fed Digest"
    "join us",                # generic event nag
    "rsvp",                   # generic event nag

    # Reminders for upcoming events
    "reminder:",              # Barclays: "Reminder: Analyst Access: ..."
    "reminder -",             # Barclays: "Reminder - In One Hour: ..."
    "reminder tomorrow",      # Barclays: "Reminder Tomorrow: Analyst Access ..."
    "final reminder",         # Barclays: "Final Reminder: Corporate Access ..."

    # Time-imminent pings (event happening now-ish)
    "starting soon",          # Barclays: "Starting soon: ... Thursday Macro ..."
    "starting in",            # Barclays: "Starting in One Hour: Expert Access ..."
    "starts in",              # Barclays: "***STARTS IN 1 HOUR 1PM ET***: ..."
    "in one hour",            # Barclays: "In One Hour: Expert Access ..."
    "in 1 hour",              # numeric variant
    "in 1hr",                 # BofA: "In 1hr: European Credit Research"
    "in 1 hr",                # BofA: abbreviated form
    "in an hour",             # Barclays: "** Reminder: IN AN HOUR ** ..."
    "in 2 hours",             # numeric variant
    "in 2hr",                 # abbreviated variant
    "in 2 hr",                # abbreviated variant
    "in 30 mins",             # BofA: abbreviated plural (must precede "in 30 min")
    "in 30 min",              # numeric variant
    "webinar today",          # Barclays: "Webinar today at 10am EDT: ..."
    "webinar tomorrow",       # Barclays: "Webinar TOMORROW: ..."

    # Re-broadcast / republished / rescheduled
    "rescheduled to",         # Barclays: "Rescheduled to 1PM ET Tomorrow ..."
    "replay:",                # Barclays: "Replay: Expert Access ..."

    # Event-brand prefixes — recurring hosted-call series, not research.
    # Already in barclays/goldman/anz/nomura/bnp lists; promoted here so
    # JPM / Citi / DB / SocGen / HSBC / MS / Westpac / UBS / Stanc / BofA
    # all pick them up for free.
    "analyst access:",        # Barclays: "Analyst Access: Barclays Tuesday Credit Call"
    "expert access:",         # Barclays: "Expert Access: ..."
    "corporate access:",      # Barclays: "Corporate Access: Equitable (EQH): ..."
)


# ---------------------------------------------------------------------
# Family 2 — Morning notes (daily sales-recap titles). Mix of
# prefix-anchored exact titles and a Citi weekday-date regex.
# ---------------------------------------------------------------------
MORNING_NOTE_PREFIXES: tuple[str, ...] = (
    # ANZ — two daily recap series + one chart deck.
    # NB: "Daily Rates RV Pack" and "AUD Rates Weekly Snapshot" used to be
    # here too, but ANZ wants those KEPT (rates-event coverage) — they live
    # in filters/anz.py::_ANZ_RATES_KEEP now (a vendor-scoped keep-override).
    # Don't re-add them here or they'd be dropped before the override runs.
    "australian morning focus",
    "nz morning focus",
    "charts that matter",
    # Barclays — daily Best-of recap (exact title)
    "before the bell:",       # "Before the Bell: Your Daily Best of Barclays Research"
    # DB — two daily series
    "dbdaily:",
    "early morning reid:",
    # Goldman — daily updates
    "us morning update",
    "asian equity market daily update",
    # HSBC — daily FX morning bullets
    "americas fx morning bullets",
    # JPM — daily research index pages, format "JPM | FTM | Today's Research | <region>"
    "jpm | ftm | today",
    # Nomura — sales-trader daily Japan recap
    "matsuzawa morning report",
    # Westpac — bare "Morning Report" (only Westpac uses this as the full title)
    "morning report",
)


# Citi day-of-week index pages — title format is literally
# "Tuesday, 09 June 2026" / "Wednesday, 10 June 2026". Anchor on the
# weekday + comma + digit so we don't false-match real headlines that
# happen to start with a weekday name.
_WEEKDAY_DATE_RE = re.compile(
    r"^(monday|tuesday|wednesday|thursday|friday|saturday|sunday),\s+\d"
)
MORNING_NOTE_REGEXES: "tuple[tuple[str, re.Pattern[str]], ...]" = (
    ("weekday-date-index", _WEEKDAY_DATE_RE),
)


# ---------------------------------------------------------------------
# Family 3 — Chart packs / pure-data sheets (substring match on the
# normalised title). Heavy on JPM; lighter coverage at other vendors.
# ---------------------------------------------------------------------
CHART_PACK_SUBSTRINGS: tuple[str, ...] = (
    # JPM daily relative-value / pricing tables (40+ SKUs, ~370 docs / 2w)
    "rich/cheap",             # JPM: "Global EM Local Bond Rich/Cheap Report"
    "daily analytics",        # JPM: "CDX.NA.HY Daily Analytics"
    "analytics package",      # JPM: "US Cash Interest Rate Analytics Package - USD"
    "analytics report",       # JPM: "EM and Asian CDS Index Daily Analytics Report"
    "analytics chartpack",    # JPM: "FX Derivatives Analytics Chartpack"
    "pricing package",        # JPM: "MBS Pricing and Analytics Package - USD"
    "pricing and analytics",  # JPM: same
    "vol package",            # JPM: "Euro Vol Package" / "Global Interest Rate Vol Package"
    "msrb trade",             # JPM: "MSRB Trade Report Package"
    "cds basis report",       # JPM: "European High Yield Bond - CDS Basis Report"
    "asset swap report",      # JPM: "Global EM Local Bond Asset Swap Report"
    "carry and roll",         # JPM: "Global EM Local Rates Carry and Roll Analytics Report"
    "fx carry report",        # JPM: "FX Carry Report"
    "reference sheet",        # JPM: "U.S. Treasury Futures Basis Reference Sheet"
    "snapshot report",        # JPM: "JULI Snapshot Report"
    "fair value monitor",     # JPM: "J.P. Morgan EM Local Currency Bonds Fair Value Monitor"
    "fair value regressions", # JPM: "Daily FX Fair Value Regressions Report"
    "relative value screen",  # JPM: "Credit Relative Value Screen"
    "relative value report",  # JPM: "TIPS Relative Value Report"
    "spread vs ratings",      # JPM: "EM Spread vs Ratings Report"
    "position indicator",     # JPM: "European Bond Futures Position Indicator Report"
    "correlations report",    # JPM: "FX Cross-Market Correlations Report"
    "index movers",           # JPM: "Index Movers Daily"
    "global index mail",      # JPM: "Global Index Mail"
    "liquidity monitor",      # JPM: "Short-Term Liquidity Monitor"
    "liquidity report",       # JPM: "Eurex Market Liquidity Report"
    # (JPM FTM "Today's Research" pages — handled by the morning-note
    # prefix `"jpm | ftm | today"` instead, so they don't double-fire.)
    "pari credit",            # JPM: "Muni Corporate pari credit relative value report"
    "butterfly report",       # JPM: "Euro Swap Butterfly Report"
    "easi vs fx",             # JPM: "EM Easi vs Fx Report"
    "front-end spread",       # JPM: "Front-end Spread Analytics Report"
    "cross currency report",  # JPM: "EM Sovereign Cross Currency Report"
    "bond-cds basis",         # JPM: "EM US Dollar Sovereign Bond-CDS Basis Report"
    "talking points",         # JPM: "High Yield Talking Points"
    "qed): global",           # JPM: "Quant Econ Dashboard (QED): Global GDP Nowcaster"

    # Generic chart-pack words (any vendor)
    "chart pack",
    "chart book",
    "chartpack",
    "chartbook",
    "chart deck",
    "chart decks",
    "chart of the day",       # DB: "Fixed Income Chart Of The Day: ..."
    "multi-factor analysis",  # Barclays: "CBOT Ultrabond Futures Multi-factor Analysis"
    "valuation sheet",        # Barclays: "European Media Valuation Sheet"

    # Citi
    "tactical style rotation",  # Citi: "Citi Quant: Daily Tactical Style Rotation Forecasts"

    # Goldman
    "ratings and target price changes",  # Goldman: "Ratings and Target Price Changes - June 08, 2026"
)


# Order matters: chart-pack > morning-note > event-admin. Chart-pack is
# the most stable signal (substring); morning-note is the next most
# stable (anchored prefix); event-admin is intentionally last because
# its prefixes are the noisiest (most prone to evolving wording).
def classify_noise(title: str) -> str | None:
    """Return a ``"noise:<family>:'<pattern>'"`` reason if ``title``
    matches any of the three shared noise families, else ``None``.

    Vendors call this as the final step in their ``should_exclude``
    chain — after any vendor-native structured signals. The reason
    string is what shows up as the ``[SKIP]`` tag in the crawler log,
    so an operator can trace which rule fired and decide whether to
    narrow it.
    """
    if not title:
        return None

    reason = match_title_substring(title, CHART_PACK_SUBSTRINGS)
    if reason is not None:
        return _retag(reason, "chart-pack")

    reason = match_title_prefix(title, MORNING_NOTE_PREFIXES)
    if reason is not None:
        return _retag(reason, "morning-note")

    reason = match_title_regex(title, MORNING_NOTE_REGEXES)
    if reason is not None:
        return _retag(reason, "morning-note")

    reason = match_title_prefix(title, EVENT_ADMIN_PREFIXES)
    if reason is not None:
        return _retag(reason, "event-admin")

    return None


def _retag(reason: str, family: str) -> str:
    """Rewrite the helper's ``title-prefix:'x'`` / ``title-substring:'x'``
    / ``title-regex:'x'`` reason to ``noise:<family>:'x'`` so families
    are first-class in the log tag.
    """
    # reason has shape ``"<kind>:'<value>'"`` — split once on ":" and
    # keep everything after the kind tag.
    _, _, value = reason.partition(":")
    return f"noise:{family}:{value}"


__all__ = (
    "EVENT_ADMIN_PREFIXES",
    "MORNING_NOTE_PREFIXES",
    "MORNING_NOTE_REGEXES",
    "CHART_PACK_SUBSTRINGS",
    "classify_noise",
)
