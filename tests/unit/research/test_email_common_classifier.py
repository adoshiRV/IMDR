"""Unit tests for the keyword classifier used on email-sourced research.

`classifiers/email_common.classify_email` is the fallback every CBA/CACIB
ref and every body-only ref with an empty portal asset_class runs through,
yet the adapter suite only exercised it once. This locks down the
asset-class scoring (including the deliberate commodities-specificity
guard from the ANZ India-BoP smoke), the word-boundary country/region
scan, the instrument theme tags, and the never-guess-a-country contract.

The matcher is strict word-boundary with NO stemming ("yields" does not
match the "yield" stem), so the fixtures use exact tokens on purpose.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace

_PR = Path(__file__).resolve().parents[3] / "playground" / "research"
if str(_PR) not in sys.path:
    sys.path.insert(0, str(_PR))

from ingest.classifiers import email_common  # noqa: E402


def _ref(*, title="", body="", summary="", sender="", vendor="", source_type="research"):
    return SimpleNamespace(
        title=title, body_html=body, body_text_summary=summary,
        sender_name=sender, vendor_code=vendor, source_type=source_type,
        publish_date=date(2026, 6, 11),
    )


def _classify(ref, vendor_code=None):
    return email_common.classify_email(ref, vendor_code=vendor_code)


def _tags(result):
    return {(t.category, t.value) for t in result.tags}


# ─── asset-class scoring, one per class ──────────────────────────────────
def test_asset_class_rates():
    r = _classify(_ref(title="JGB curve and swap; ASW, duration, repo",
                       body="<p>The bond curve.</p>"))
    assert r.asset_class == "RATES"


def test_asset_class_fx():
    r = _classify(_ref(title="USDJPY and the rupiah",
                       body="<p>FX intervention; reserves; depreciation of the currency.</p>"))
    assert r.asset_class == "FX"


def test_asset_class_credit():
    r = _classify(_ref(title="High yield and IG spreads",
                       body="<p>cds, itraxx, default rate, maturity wall, investment grade.</p>"))
    assert r.asset_class == "CREDIT"


def test_asset_class_equity():
    r = _classify(_ref(title="Equity earnings and valuation",
                       body="<p>share price, p/e, stock.</p>"))
    assert r.asset_class == "EQUITY"


def test_asset_class_strategy():
    r = _classify(_ref(title="Cross-asset positioning",
                       body="<p>asset allocation, portfolio strategy.</p>"))
    assert r.asset_class == "STRATEGY"


def test_asset_class_commodities():
    r = _classify(_ref(title="Crude oil and brent",
                       body="<p>copper, iron ore, gold, natural gas, base metals.</p>"))
    assert r.asset_class == "COMMODITIES"


# ─── commodities-specificity guard (ANZ India-BoP smoke 2026-06-15) ──────
def test_bare_oil_does_not_beat_macro():
    # A stray "oil markets" mention in a macro note must NOT flip the class
    # to COMMODITIES — the stems are "crude oil"/"oil price", never bare oil.
    r = _classify(_ref(
        title="Inflation and GDP",
        body="<p>oil markets aside, cpi and unemployment and monetary policy "
             "and central bank growth.</p>",
    ))
    assert r.asset_class == "MACRO"


# ─── no-stemming word-boundary contract ──────────────────────────────────
def test_plural_does_not_match_singular_stem():
    # "yields" must NOT match the "yield" RATES stem; with no other RATES
    # tokens the only scoring hit is MACRO's "growth".
    r = _classify(_ref(title="Outlook", body="<p>yields keep growth steady.</p>"))
    assert r.asset_class == "MACRO"


# ─── country / region scan ───────────────────────────────────────────────
def test_country_and_region_apac():
    r = _classify(_ref(title="Indonesia rates", body="<p>indonesia srbi and yield.</p>"))
    assert r.country_code == "ID"
    assert ("country", "ID") in _tags(r)
    assert ("region", "apac") in _tags(r)


def test_country_and_region_emea():
    r = _classify(_ref(title="Germany bund", body="<p>france gilt bund yield.</p>"))
    assert r.country_code == "DE"
    assert ("region", "emea") in _tags(r)


def test_no_country_is_left_unset():
    # Never guesses a country it cannot see — and no country => no region tag.
    r = _classify(_ref(title="Generic rates note", body="<p>yield and curve and swap.</p>"))
    assert r.country_code is None
    assert not any(cat == "country" for cat, _ in _tags(r))
    assert not any(cat == "region" for cat, _ in _tags(r))


# ─── instrument theme tags + author tag ──────────────────────────────────
def test_instrument_theme_tags_emitted():
    r = _classify(_ref(title="Indonesia SRBI and IndoGB",
                       body="<p>srbi 7.68; indogb fair value; korea ktb.</p>"))
    themes = {v for c, v in _tags(r) if c == "theme"}
    assert {"SRBI", "INDOGB", "KTB"} <= themes


def test_sender_becomes_author_tag():
    r = _classify(_ref(title="Some macro note",
                       body="<p>inflation gdp cpi growth.</p>", sender="Zeke Koh"))
    assert ("author", "Zeke Koh") in _tags(r)


# ─── context block carries the desk-commentary provenance line ───────────
def test_desk_commentary_noted_in_context():
    r = _classify(_ref(title="t", body="<p>inflation</p>", source_type="desk_commentary"))
    assert "desk/sales commentary" in r.context


def test_vendor_code_argument_overrides_ref():
    # vendor_code kwarg wins over the ref's own vendor_code in the context.
    r = _classify(_ref(title="t", body="<p>inflation</p>", vendor="db"), vendor_code="citi")
    assert "Vendor:" in r.context


# ── country scan: subject-weighted, thresholded, tie-safe ──────────────────
# Before 2026-09-28 the scanner took an argmax of raw name counts over the
# whole blob, with no threshold and ties broken by declaration order. On a
# 414-message sample that put 15% of tags on a SINGLE passing mention and a
# further 17% on a silent tie. Observed misfires: "Australian Morning Focus"
# -> CN (china=1, india=1), "NZ Morning Focus" -> AU (3-way tie at 1),
# "DB JPY Market PM Summary" -> DE (germany=2; "japan" never appeared).

from ingest.classifiers.email_common import _scan_country  # noqa: E402


def test_subject_outweighs_a_passing_body_mention():
    """The subject states what a note is about; one body mention does not."""
    assert _scan_country("Australian Morning Focus", "china grew. india too.") == "AU"


def test_currency_and_abbreviation_in_the_subject_identify_the_country():
    """'JPY'/'NZ' in a subject are decisive even if the name never appears."""
    assert _scan_country("DB JPY Market PM Summary", "bunds in germany, germany") == "JP"
    assert _scan_country("NZ Morning Focus", "australia japan china") == "NZ"
    assert _scan_country("NZ Insight: Weekly Fuel Market Watch", "singapore gasoline") == "NZ"


def test_aliases_are_not_scanned_in_the_body():
    """Body-scanning aliases would tag the whole corpus US.

    'usd', 'fed' and 'treasury' appear in virtually every FX and rates note,
    so they are subject-only signals. A body full of them must not win.
    """
    got = _scan_country("Indonesia rates update", "usd usd usd fed fed treasury ust")
    assert got == "ID"


def test_a_single_body_mention_is_not_enough():
    """Below the score threshold we return None — NULL beats wrong."""
    assert _scan_country("Weekly Wrap", "one passing mention of singapore") is None


def test_a_tie_returns_none_rather_than_list_order():
    """A multi-country wrap belongs to no single country.

    'australia' precedes 'japan' and 'china' in _COUNTRY_SCAN, so the old
    argmax silently returned AU for this input.
    """
    assert _scan_country("Morning Wrap", "australia japan china") is None


def test_unambiguous_body_evidence_still_wins_without_a_subject_hit():
    """A note genuinely about one country is still tagged from the body."""
    body = "indonesia " * 5 + "china"
    assert _scan_country("Daily Alert", body) == "ID"


def test_korea_aliases_collapse_to_one_code():
    """'korea' and 'south korea' both normalise to KR and must not self-tie."""
    assert _scan_country("South Korea rates", "korea korea south korea") == "KR"


# ── regulatory distribution block must not vote on country ─────────────────

from ingest.classifiers.email_common import trim_disclaimer  # noqa: E402

_WESTPAC_TAIL = (
    "singapore: this material has been prepared and issued for distribution in "
    "singapore to institutional investors, accredited investors and expert "
    "investors (as defined in the applicable singapore laws and regulations). "
    "recipients of this material in singapore should contact westpac singapore "
    "branch in respect of any matters arising from this material."
)


def test_disclaimer_block_is_trimmed_before_scanning():
    """A Westpac daily carries 4+ 'singapore' hits purely from its legal block."""
    body = ("the rba held rates today and the australian dollar rallied. "
            "australia's labour market stayed tight. " * 6) + _WESTPAC_TAIL
    assert "singapore" in body
    assert "singapore" not in trim_disclaimer(body)


def test_boilerplate_does_not_win_the_country_tag():
    """Subject matter beats the jurisdiction list."""
    body = ("the rba held rates today and the australian dollar rallied. "
            "australia's labour market stayed tight. " * 6) + _WESTPAC_TAIL
    assert _scan_country("Morning Report", body) == "AU"


def test_a_cue_near_the_top_is_not_treated_as_a_footer():
    """Trimming on an early cue would throw the whole note away."""
    body = "important disclosures follow. " + ("indonesia rupiah bonds rallied. " * 40)
    assert trim_disclaimer(body) == body
    assert _scan_country("Indonesia daily", body) == "ID"


def test_trim_is_a_noop_when_there_is_no_disclaimer():
    body = "plain note about japan and jgbs with no legal tail"
    assert trim_disclaimer(body) == body


# ── body-safe instrument markers + subject tie-break ───────────────────────


def test_instrument_markers_count_in_the_body():
    """A desk note can name its market without spelling out the country.

    "Citi Macro - SRBI...the new golden child in Asia?" says 'Indonesia' once
    in the body but is unmistakably Indonesian: BI, IDR, SRBI, IndoGB. Under a
    names-only body scan that single mention fell below the threshold and the
    note lost its country entirely.
    """
    body = ("BI surprise 25bps hike to 5.5% to stem IDR depreciation. "
            "SRBI 1Y 7.68%, 9M 7.46%. Indonesia IndoGB 5y fair value 7.3-7.7%.")
    assert _scan_country("Citi Macro - SRBI...the new golden child in Asia?", body) == "ID"


def test_ubiquitous_tokens_are_still_subject_only():
    """'usd'/'fed'/'treasury' must never win from the body.

    They appear in nearly every FX and rates note; body-scanning them would
    tag the whole corpus US.
    """
    body = "usd usd usd fed fed fed treasury ust ust " + ("jgb boj " * 4)
    assert _scan_country("Japan rates", body) == "JP"


def test_subject_breaks_a_tie_when_it_names_exactly_one_side():
    """The subject is the author's own statement of topic."""
    # germany scores on two names + 'bunds'; japan scores on the subject alias.
    assert _scan_country("DB JPY Market PM Summary", "bunds in germany, germany") == "JP"


def test_subject_tie_break_does_not_rescue_a_genuinely_split_note():
    """If the subject names both sides, it is still a multi-country note."""
    assert _scan_country("Australia and Japan wrap", "australia japan") is None
