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
