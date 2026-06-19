"""Unit tests for the email→portal fuzzy dedup-merge matcher.

The DB pairs are the real ones from the 2026-06-19 backfill smoke
(Walter Wong re-forwarding portal notes with a `[/] DB {Masthead} -`
prefix). The matcher must catch those as twins (score ≥ THRESHOLD) while
sparing genuinely net-new desk notes.
"""
from __future__ import annotations

import sys
from pathlib import Path

_RESEARCH_ROOT = Path(__file__).resolve().parents[3] / "playground" / "research"
if str(_RESEARCH_ROOT) not in sys.path:
    sys.path.insert(0, str(_RESEARCH_ROOT))

from ingest.dedup_merge import (  # noqa: E402
    THRESHOLD,
    jaccard,
    title_tokens,
)


def _score(email: str, portal: str) -> float:
    return jaccard(title_tokens(email), title_tokens(portal))


# ─── tokenization ─────────────────────────────────────────────────────────
def test_title_tokens_strips_vendor_forward_and_punctuation():
    toks = title_tokens("RE: [/] DB Fed Notes - June FOMC recap: Rock Chalk, Warsh-hawk")
    assert "db" not in toks and "re" not in toks      # vendor + forward markers dropped
    assert {"fed", "notes", "june", "fomc", "recap", "rock", "chalk", "warsh", "hawk"} <= toks
    assert all(len(t) > 1 for t in toks)              # single chars dropped


def test_title_tokens_drops_pure_digits():
    # Years / day-numbers carry no headline signal and must not drive matches.
    toks = title_tokens("Citi Weekly ASW Run (Nominals + Linkers) - 9 Jun 2026")
    assert "2026" not in toks and "9" not in toks   # pure-digit tokens dropped
    assert "weekly" not in toks                       # generic cadence word dropped
    assert {"asw", "run", "nominals", "linkers", "jun"} <= toks


def test_year_only_or_mojibake_portal_does_not_match():
    # Regression: a CJK/mojibake portal title "2026年6月8日…" tokenizes to
    # only digits; with digit-drop it yields no significant tokens, so a
    # shared year can't produce a spurious 1.0 (the bug that wrongly
    # deleted a Citi ASW Run row in the first backfill cleanup).
    assert _score("Citi Weekly ASW Run (Nominals + Linkers) - 9 Jun 2026",
                  "2026年6月8日") < THRESHOLD


def test_jaccard_edges():
    assert jaccard(frozenset(), frozenset({"a", "b"})) == 0.0
    assert jaccard(frozenset({"a", "b"}), frozenset({"a", "b"})) == 1.0
    # subset → ⅓ (Jaccard, not overlap coefficient — this is what keeps a
    # small email set from over-scoring against a larger portal set)
    assert jaccard(frozenset({"a"}), frozenset({"a", "b", "c"})) == 1 / 3


# ─── real twins MUST match (≥ THRESHOLD) ──────────────────────────────────
def test_portal_twins_score_above_threshold():
    pairs = [
        ("[/] DB Fed Notes - June FOMC recap: Rock Chalk, Warsh-hawk",
         "Fed Notes: June FOMC recap: Rock Chalk, Warsh-hawk"),
        ("[/] DB Fed Notes - Who's who in the June 2026 dot plot",
         "Fed Notes: Who's who in the June 2026 dot plot"),
        ("[/] DB FX Blog - Beneficiaries of the peace",
         "FX Blog: Beneficiaries of the peace"),
        ("[/] DB Asia Macro Strategy Notes - CCS monitor: Receive CNH 5Y5Y",
         "Asia Macro Strategy Notes: CCS monitor: Receive CNH 5Y5Y; pay ..."),
        ("[/] DB Japan Monetary Policy Watch - MPM review: an initial dovish read",
         "Japan Monetary Policy Watch : MPM review: an initial dovish read"),
    ]
    for email, portal in pairs:
        assert _score(email, portal) >= THRESHOLD, (email, _score(email, portal))


def test_known_under_dedup_differing_masthead():
    # Documented recall trade-off: the desk re-titles the SAME note under a
    # different masthead ("DB Strategy:" vs portal "FX Blog:"). Jaccard sees
    # the masthead difference and scores below threshold, so this twin is
    # MISSED (leaves a dup row) — the accepted price of precision-first
    # matching on a destructive merge. (Core-extraction would catch it.)
    assert _score("[/] DB Strategy: Thoughts on the dollar and the Fed",
                  "FX Blog: Thoughts on the dollar and the Fed") < THRESHOLD


# ─── net-new desk notes MUST NOT match ────────────────────────────────────
def test_net_new_desk_notes_below_threshold():
    cases = [
        # JPY PM Summary (maki desk daily) vs nearest portal Japan note
        ("[/] DB JPY Market PM Summary",
         "Japan Economic Notes: Overview of next two weeks"),
        # DB Asia Week Ahead vs the portal's Australia/NZ week-ahead
        ("[/] DB Asia Week Ahead : 8 - 12 June",
         "Australia / New Zealand Week Ahead: 22-28 June"),
        # Citi desk note vs an unrelated portal note
        ("Citi Macro - Trading Thoughts on ASEAN Rates",
         "Fed Notes: June FOMC recap: Rock Chalk, Warsh-hawk"),
    ]
    for email, portal in cases:
        assert _score(email, portal) < THRESHOLD, (email, _score(email, portal))
