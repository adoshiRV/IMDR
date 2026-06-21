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
