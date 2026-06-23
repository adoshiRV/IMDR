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


# ─── portal-pointer detection (teaser cover-note + report link) ──────────
def _deal_pointer_html():
    # Mirrors DB "[/] … What a 'deal' …": a short teaser + a report link +
    # the DB confidentiality footer (which must be cut, else it inflates).
    return (
        "<p>From: Sameer Goel</p>"
        "<p>It looks like a deal is finally on the table in the Middle East. "
        "While the specifics still need work, the reaction in commodity markets "
        "this morning suggests confidence that getting oil back on water is "
        "where the gap between the two sides is narrowest. In our latest Asia "
        "Macro Strategy Notes report, 1) we discuss what a deal potentially "
        "means for Asia macro; 2) we rank currencies in Asia in order of their "
        "relative potential benefit from a deal; and 3) we highlight 3 trades — "
        "2 FX and 1 rates — we like.</p>"
        "<p><a href='http://research.db.com/research/TinyUrl/XLXMW'>link</a></p>"
        "<p>This email may contain confidential and/or privileged information. "
        + ("blah " * 200) + "</p>"
    )


def test_cuts_db_confidentiality_footer():
    out = ed.sanitize_email_html(_deal_pointer_html())
    assert "rank" in out  # substantive teaser kept
    assert "may contain confidential" not in out  # DB footer cut
    assert len(out) < ed.POINTER_MAX_CHARS  # boilerplate no longer inflates it


def test_is_portal_pointer_short_body_with_report_link():
    ref = SimpleNamespace(body_html=_deal_pointer_html(), body_text_summary="", attachments=())
    body = ed.best_body_text(ref)
    assert ed.is_portal_pointer(ref, body) is True
    doc, path, _ = ed.build_email_document(ref)
    assert path == "skip(portal_pointer)" and doc is None


def test_portal_pointer_ignores_long_body_with_link():
    # A full desk note that merely cites a report link must NOT be flagged.
    ref = SimpleNamespace(
        body_html="<p>" + ("real analysis " * 80) +
                  "see http://research.db.com/research/TinyUrl/ABCDE</p>",
        body_text_summary="", attachments=())
    body = ed.best_body_text(ref)
    assert len(body) >= ed.POINTER_MAX_CHARS
    assert ed.is_portal_pointer(ref, body) is False


def test_portal_pointer_ignores_short_body_without_report_link():
    # Short genuine desk one-liner with no report-download link → kept.
    ref = SimpleNamespace(
        body_html="<p>BI surprised with a 25bp hike; we stay received front-end IDR.</p>",
        body_text_summary="", attachments=())
    body = ed.best_body_text(ref)
    assert ed.is_portal_pointer(ref, body) is False


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


def test_first_pdf_attachment_picks_inline_pdf_with_saved_file():
    # Route C: DB attaches the real report PDF with a content-id (is_inline=True),
    # but the producer SAVED its bytes (`file` set) — it IS the report, not an
    # inline image, so it must be picked despite the inline flag.
    ref = SimpleNamespace(attachments=(
        {"name": "logo.png", "content_type": "image/png", "is_inline": True},
        {"name": "r.pdf", "content_type": "application/pdf", "is_inline": True,
         "file": "attachments/abc12345.pdf"},
    ))
    att = ed._first_pdf_attachment(ref)
    assert att is not None and att["name"] == "r.pdf"


def test_build_email_document_resolves_pdf_relative_to_vendor_dir(tmp_path):
    # `file` is vendor-relative ("attachments/x.pdf"); resolution must use the
    # JSON's own dir (via ref._staging_file), NOT staging_root/file.
    import importlib
    parse = importlib.import_module("ingest.parse")
    vendor_dir = tmp_path / "db"
    (vendor_dir / "attachments").mkdir(parents=True)
    pdf_file = vendor_dir / "attachments" / "abc12345.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 fake")
    captured = {}
    orig = parse.parse_pdf
    parse.parse_pdf = lambda data: captured.setdefault("data", data) or ed.synthesize_document("x" * 300)
    try:
        ref = SimpleNamespace(
            body_html="<p>" + ("macro " * 60) + "</p>", body_text_summary="",
            attachments=({"name": "r.pdf", "content_type": "application/pdf",
                          "is_inline": True, "file": "attachments/abc12345.pdf"},),
            _staging_file=str(vendor_dir / "db_note.json"),
        )
        doc, path, _ = ed.build_email_document(ref, staging_dir=tmp_path)
        assert path == "pdf"
        assert captured["data"] == b"%PDF-1.4 fake"  # read the vendor-dir file
    finally:
        parse.parse_pdf = orig
