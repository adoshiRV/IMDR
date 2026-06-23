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

from datetime import date  # noqa: E402
from types import SimpleNamespace  # noqa: E402

from ingest.dedup_merge import (  # noqa: E402
    THRESHOLD,
    _pair_score,
    find_email_twin,
    find_portal_twin,
    jaccard,
    title_tokens,
)


def _score(email: str, portal: str) -> float:
    return jaccard(title_tokens(email), title_tokens(portal))


class _FakeEngine:
    """Minimal stand-in: `find_portal_twin` only does `engine.connect()` →
    `conn.execute(...).all()`. Returns (id, title) rows for the portal set."""
    def __init__(self, portal_titles):
        self._rows = [(i + 1, t) for i, t in enumerate(portal_titles)]

    def connect(self):
        rows = self._rows
        class _Conn:
            def __enter__(self_): return self_
            def __exit__(self_, *a): return False
            def execute(self_, *a, **k): return SimpleNamespace(all=lambda: rows)
        return _Conn()


def _twin(email_title, portal_titles):
    return find_portal_twin(_FakeEngine(portal_titles), vendor_code="goldman",
                            publish_date=date(2026, 6, 22), title=email_title)


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


# ─── find_portal_twin: masthead + short-core recall (2026-06-23 smoke) ─────
def test_masthead_prefixed_email_matches_portal_core():
    # GS prepends a series masthead to the verbatim portal title. The plain
    # Jaccard scores below threshold (masthead dilutes overlap), but the new
    # containment / masthead-strip paths catch it.
    cases = [
        ("Asia-Pacific Inflation Monitor: Oil Past the Peak", "Oil Past the Peak"),
        ("China Matters: All About Tech", "All About Tech"),
        ("Canada Economics Comment: May CPI Preview", "May CPI Preview"),
        ("CEEMEA Economics Analyst: Turkiye Growth Slowdown Needs to Be Sustained",
         "Turkiye Growth Slowdown Needs to Be Sustained"),
    ]
    for email, portal in cases:
        # plain Jaccard would miss it...
        assert _score(email, portal) < THRESHOLD, email
        # ...but find_portal_twin now catches it.
        twin = _twin(email, [portal])
        assert twin is not None and twin.portal_title == portal, email


def test_short_core_exact_substring_matches():
    # Below the 3-token floor, but the portal title appears verbatim → twin.
    assert _twin("Global Rates Trader: Dealing With Inflation",
                 ["Dealing With Inflation"]) is not None
    assert _twin("Macro Roadmap", ["Macro Roadmap"]) is not None


def test_twin_still_rejects_net_new_desk_note():
    # Net-new desk note must NOT match an unrelated portal note (no shared
    # core, no containment, no substring) — precision preserved.
    assert _twin("[/] DB JPY Market PM Summary",
                 ["Japan Economic Notes: Overview of next two weeks",
                  "Oil Past the Peak"]) is None


def test_twin_containment_needs_three_shared_tokens():
    # A 2-token portal title fully "inside" the email must NOT trigger
    # containment (guards the year/mojibake degenerate-match class).
    assert _twin("Global FX: Dollar View", ["Dollar View"]) is None


# ─── email↔email twin (collapse same note arriving by two paths) ───────────
class _FakeEmailEngine:
    """Returns (id, title, imi) email rows, honouring the `publish_date = :pd`
    filter so the same-day window guard is exercised."""
    def __init__(self, rows):  # rows: (id, title, imi, date)
        self._rows = rows

    def connect(self):
        rows = self._rows
        class _Conn:
            def __enter__(self_): return self_
            def __exit__(self_, *a): return False
            def execute(self_, _sql, params):
                same_day = [(i, t, m) for (i, t, m, d) in rows if d == params["pd"]]
                same_day.sort(key=lambda r: r[0])
                return SimpleNamespace(all=lambda: same_day)
        return _Conn()


def _etwin(title, rows, pd=date(2026, 6, 21), imi="self"):
    return find_email_twin(_FakeEmailEngine(rows), vendor_code="stanc",
                           publish_date=pd, title=title, internet_message_id=imi)


def test_pair_score_matches_dual_masthead_core():
    # The real SMS case: desk forward vs formal research, shared dash-masthead
    # core "SMS – Balancing act". Different mastheads → both carry a prefix.
    assert _pair_score(
        "SCB Global Macro Strategy - SMS – Balancing act (with weekly podcast)",
        "Sunday Macro Strategy – SMS – Balancing act") >= THRESHOLD


def test_email_twin_collapses_same_day_dual_send():
    # The formal-research email finds the earlier-loaded desk forward (same
    # day) and is skipped.
    rows = [(11547, "SCB Global Macro Strategy - SMS – Balancing act (with weekly podcast)",
             "<desk@x>", date(2026, 6, 21))]
    twin = _etwin("Sunday Macro Strategy – SMS – Balancing act", rows, imi="<research@x>")
    assert twin is not None and twin.report_id == 11547


def test_email_twin_preserves_daily_series_across_days():
    # SAME title, DIFFERENT day = a fresh daily edition → NOT a twin (the
    # publish_date=0 window is the guard). Monday's PM Summary must not collapse
    # Tuesday's.
    rows = [(100, "[/] DB JPY Market PM Summary", "<mon@x>", date(2026, 6, 22))]
    twin = _etwin("[/] DB JPY Market PM Summary", rows,
                  pd=date(2026, 6, 23), imi="<tue@x>")
    assert twin is None


def test_email_twin_keeps_distinct_same_day_notes():
    # Two genuinely different same-day SCB notes must NOT collapse.
    rows = [(200, "SCB (China Research) - PBoC to add overnight reverse repo",
             "<a@x>", date(2026, 6, 21))]
    twin = _etwin("SCB (China Research) - Net FX settlement edged down in May",
                  rows, imi="<b@x>")
    assert twin is None


def test_email_twin_preserves_numbered_series_editions():
    # Serial guard: "Asia G10 Spot Views #1490" and "#1489" are DIFFERENT
    # editions even same-day — title_tokens drops the issue number, so without
    # the guard they'd score 1.0 and wrongly collapse.
    assert _pair_score("Arvin The : Asia G10 Spot Views #1490",
                       "Arvin The : Asia G10 Spot Views #1489") == 0.0
    rows = [(11569, "Arvin The : Asia G10 Spot Views #1490", "<a@x>", date(2026, 6, 18))]
    assert _etwin("Arvin The : Asia G10 Spot Views #1489", rows,
                  pd=date(2026, 6, 18), imi="<b@x>") is None
    # ...but the SAME issue number (true resend) still collapses:
    assert _pair_score("Arvin The : Asia G10 Spot Views #1490",
                       "Arvin The : Asia G10 Spot Views #1490") >= THRESHOLD


def test_serial_guard_blocks_portal_twin_of_other_edition():
    # "Global oil market tracker: issue 6" must not twin portal "...: issue 5".
    assert find_portal_twin(
        _FakeEngine(["Global oil market tracker: issue 5"]),
        vendor_code="anz", publish_date=date(2026, 6, 22),
        title="Global oil market tracker: issue 6") is None


def test_email_twin_excludes_self_imi():
    rows = [(300, "Sunday Macro Strategy – SMS – Balancing act", "<self@x>",
             date(2026, 6, 21))]
    twin = _etwin("Sunday Macro Strategy – SMS – Balancing act", rows, imi="<self@x>")
    assert twin is None
