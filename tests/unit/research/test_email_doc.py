"""Unit tests for the email->Document adapter edge cases.

The adapter suite covered the sanitizer happy-path + one synthesize call.
This locks down the bits the full `--load` path actually depends on:

* the trailing-boilerplate cutter (earliest-of-many marker, banner removal),
* `DESK_DISCLAIMER_RE` (drives source_type in the crawler),
* `best_body_text` (sanitized vs pre-extracted summary, MIN_BODY_CHARS),
* `build_email_document`'s three outcomes — `synthetic_body`, `skip`,
  `synthetic_body(pdf_missing)` — plus `_first_pdf_attachment` skipping
  inline images.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

_PR = Path(__file__).resolve().parents[3] / "playground" / "research"
if str(_PR) not in sys.path:
    sys.path.insert(0, str(_PR))

from ingest import email_doc as ed  # noqa: E402


# ─── trailing-boilerplate cutter ─────────────────────────────────────────
def test_strips_westpac_phishing_banner():
    # Westpac prepends an anti-phishing banner to every email; strip it so it
    # doesn't pollute embeddings or inflate link-only pointers (2026-06-22).
    html = ("<p>Westpac will never send you a link directly to our sign in page. "
            "Always type westpac.com.au into your browser. More Info - visit "
            "westpac.com.au/hoaxemails View online</p>"
            "<p>Overnight Market Wrap. AUD rose to 0.7012; AU 3yr swap opens 4.45%.</p>")
    out = ed.sanitize_email_html(html)
    assert "never send you a link" not in out and "hoaxemails" not in out
    assert "Overnight Market Wrap" in out


def test_cuts_at_earliest_of_multiple_markers():
    # Two legal-tail markers present; everything from the FIRST is dropped.
    html = (
        "<p>Real note body here.</p>"
        "<p>For Reg AC certification ...</p>"
        "<p>Things you should know ...</p>"
    )
    out = ed.sanitize_email_html(html)
    assert out == "Real note body here."


def test_cuts_confidentiality_and_unsubscribe_tails():
    html = "<p>SGS outperform.</p><p>This email message is confidential and ...</p>"
    assert "SGS outperform." in ed.sanitize_email_html(html)
    assert "confidential" not in ed.sanitize_email_html(html)
    html2 = "<p>Keep this.</p><p>You have received this email because you are subscribed.</p>"
    assert ed.sanitize_email_html(html2) == "Keep this."


# ─── vendor disclaimer footers (grounded in real bodies, 2026-06-22) ─────
def test_cuts_anz_research_footer():
    # ANZ Research's footer was NOT previously cut, leaking the legal block
    # into the body (defeating wrapper-skip on link-only pointers).
    html = ("<p>Fed outlook: the reaction function has hardened.</p>"
            "<p>Regards, ANZ Research</p>"
            "<p>By continuing to use our services you acknowledge and accept our Terms</p>"
            "<p>IMPORTANT NOTICE: This communication is issued by ANZ Bank New Zealand Limited. "
            "This communication is intended only for the addressee.</p>")
    out = ed.sanitize_email_html(html)
    assert "Fed outlook" in out
    assert "IMPORTANT NOTICE" not in out and "issued by ANZ" not in out


def test_cuts_bofa_sales_trading_disclaimer():
    html = ("<p>Short EURUSD on the Warsh read; USDJPY options desk sees regime change.</p>"
            "<p>This marketing material was prepared by marketing personnel of Bank of America Securities.</p>"
            "<p>This message may contain information that is privileged, confidential.</p>")
    out = ed.sanitize_email_html(html)
    assert "Warsh" in out
    assert "marketing material" not in out and "privileged" not in out


def test_anz_link_only_pointer_wrapper_skips():
    # "What's Priced In" is a link-only pointer: once the ANZ footer is cut,
    # the residual body is < MIN_BODY_CHARS, so build_email_document skips it
    # instead of ingesting the disclaimer as content.
    from types import SimpleNamespace
    ref = SimpleNamespace(
        body_html=("<p>Monetary Policy Expectations</p><p>Open this report</p>"
                   "<p>Regards, David Croy</p>"
                   "<p>By continuing to use our services you acknowledge and accept our Terms</p>"
                   "<p>IMPORTANT NOTICE: This communication is issued by ANZ Bank New Zealand Limited.</p>"),
        body_text_summary="", attachments=())
    doc, path, _ = ed.build_email_document(ref)
    assert path == "skip" and doc is None


# ─── desk "not research" disclaimer detector ─────────────────────────────
def test_desk_disclaimer_matches_variants():
    assert ed.DESK_DISCLAIMER_RE.search("This is a product of sales and trading")
    assert ed.DESK_DISCLAIMER_RE.search("not a product of research")
    assert ed.DESK_DISCLAIMER_RE.search("a sales note and not a product of research")
    assert ed.DESK_DISCLAIMER_RE.search("not to be considered independent research")


def test_desk_disclaimer_ignores_plain_note():
    assert ed.DESK_DISCLAIMER_RE.search("a normal macro research note") is None


# ─── best_body_text: sanitized vs summary fallback ───────────────────────
def test_best_body_prefers_substantive_sanitized():
    # Sanitized body >= MIN_BODY_CHARS wins outright, even if a summary exists.
    big = SimpleNamespace(body_html="<p>" + "word " * 100 + "</p>",
                          body_text_summary="short summary")
    out = ed.best_body_text(big)
    assert len(out) >= ed.MIN_BODY_CHARS
    assert "short summary" not in out


def test_best_body_falls_back_to_longer_summary():
    # Trimmed body_html + a fuller pre-extracted summary -> take the summary.
    short = SimpleNamespace(body_html="<p>tiny</p>", body_text_summary="x" * 250)
    out = ed.best_body_text(short)
    assert out == "x" * 250


# ─── build_email_document outcomes ───────────────────────────────────────
def test_build_body_only_synthetic():
    ref = SimpleNamespace(body_html="<p>" + "macro " * 60 + "</p>",
                          body_text_summary="", attachments=())
    doc, path, body = ed.build_email_document(ref)
    assert path == "synthetic_body"
    assert doc is not None and doc.parser_version == ed.EMAIL_PARSER_VERSION
    assert len(body) >= ed.MIN_BODY_CHARS


def test_build_skips_pure_wrapper():
    ref = SimpleNamespace(body_html="<p>click here</p>", body_text_summary="", attachments=())
    doc, path, _ = ed.build_email_document(ref)
    assert path == "skip"
    assert doc is None


def test_build_pdf_missing_degrades_to_body():
    # PDF advertised but bytes not staged -> degrade to a body-only synthetic
    # tagged so the caller can see the bytes were unavailable.
    ref = SimpleNamespace(
        body_html="<p>" + "macro " * 60 + "</p>", body_text_summary="",
        attachments=({"name": "x.pdf", "content_type": "application/pdf",
                      "is_inline": False, "file": "nope/x.pdf"},),
    )
    doc, path, _ = ed.build_email_document(ref, staging_dir=None)
    assert path == "synthetic_body(pdf_missing)"
    assert doc is not None


# ─── attachment picker ignores inline images ─────────────────────────────
def test_first_pdf_attachment_skips_inline():
    ref = SimpleNamespace(attachments=(
        {"name": "logo.png", "is_inline": True},
        {"name": "r.pdf", "content_type": "application/pdf", "is_inline": False},
    ))
    att = ed._first_pdf_attachment(ref)
    assert att is not None and att["name"] == "r.pdf"


def test_first_pdf_attachment_none_when_only_inline():
    ref = SimpleNamespace(attachments=(
        {"name": "chart.png", "content_type": "image/png", "is_inline": True},
    ))
    assert ed._first_pdf_attachment(ref) is None
