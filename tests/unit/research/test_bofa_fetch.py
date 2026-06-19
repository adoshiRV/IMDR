"""Tests for fetch_bofa.py — viewer-path pure-function helpers.

Pins:
1. _extract_reminted_pdf_url — extracts the re-minted research1.ml.com/C?...
   URL from the live fixture HTML (with &amp; decoded), returns None for HTML
   with no such URL.
2. _looks_like_viewer — True for the viewer fixture bytes, False for raw
   %PDF- bytes and for the ASP.NET expired interstitial HTML.

All tests are pure-function: no network, no browser, no Playwright.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_RESEARCH_ROOT = Path(__file__).resolve().parents[3] / "playground" / "research"
if str(_RESEARCH_ROOT) not in sys.path:
    sys.path.insert(0, str(_RESEARCH_ROOT))

from ingest.fetch_bofa import (  # noqa: E402
    _extract_reminted_pdf_url,
    _looks_like_viewer,
)

_FIXTURE_HTML = Path(__file__).resolve().parent / "fixtures" / "bofa_viewer_sample.html"


# ---------------------------------------------------------------------------
# _extract_reminted_pdf_url
# ---------------------------------------------------------------------------

def test_extract_reminted_url_from_fixture() -> None:
    """The live fixture contains the re-minted URL with &amp;-encoded params.

    Expected (after &amp; → & decoding):
        https://research1.ml.com/C?q=9lsMgztjz9teIhJ66J!jZA
            &e=adoshi%40rvcapital.com&h=u4G1yg
    """
    html = _FIXTURE_HTML.read_text(encoding="utf-8", errors="replace")
    url = _extract_reminted_pdf_url(html)

    assert url is not None, "Expected a re-minted URL in the fixture HTML"
    assert url.startswith("https://research1.ml.com/C?"), (
        f"URL should start with research1.ml.com/C?, got: {url[:80]!r}"
    )
    # Verify the q= token is present (non-empty after q=)
    assert "q=9lsMgztjz9teIhJ66J" in url, (
        f"Expected q-token in URL, got: {url!r}"
    )
    # Verify entitlement was rebound to our address, not the original recipient
    assert "e=adoshi%40rvcapital.com" in url, (
        f"Expected e=adoshi%40rvcapital.com in URL, got: {url!r}"
    )
    assert "h=u4G1yg" in url, (
        f"Expected h= parameter in URL, got: {url!r}"
    )
    # &amp; must be decoded to bare &
    assert "&amp;" not in url, (
        f"&amp; should have been decoded to & in: {url!r}"
    )


def test_extract_reminted_url_returns_none_for_plain_html() -> None:
    html = "<html><body><p>No research URL here.</p></body></html>"
    assert _extract_reminted_pdf_url(html) is None


def test_extract_reminted_url_ignores_empty_q_token() -> None:
    # The JS variable `var researchURL = 'https://research1.ml.com/C?q=';`
    # appears early in the fixture — q= has nothing after it before the quote.
    html = "<script>var researchURL = 'https://research1.ml.com/C?q=';</script>"
    assert _extract_reminted_pdf_url(html) is None


def test_extract_reminted_url_handles_unencoded_ampersand() -> None:
    # URL constructed with bare & (not &amp;) should also be matched.
    html = (
        "<a href='https://research1.ml.com/C?q=ABC123"
        "&e=user%40example.com&h=XYZ'>"
    )
    url = _extract_reminted_pdf_url(html)
    assert url is not None
    assert "q=ABC123" in url
    assert "e=user%40example.com" in url
    assert "&amp;" not in url


# ---------------------------------------------------------------------------
# _looks_like_viewer
# ---------------------------------------------------------------------------

_INTERSTITIAL_HTML = (
    b"<html><head><title>Research Content</title></head><body>"
    b"<p>Expired</p>"
    b'<form id="GetDoc"><input name="Proceed" type="submit" value="Proceed"/>'
    b"</form></body></html>"
)

_PLAIN_PDF = b"%PDF-1.6 fake pdf bytes" + b"x" * 200


def test_looks_like_viewer_true_for_fixture() -> None:
    body = _FIXTURE_HTML.read_bytes()
    # The fixture is >10KB, contains b"Liferay" and b"research1.ml.com"
    assert _looks_like_viewer(body, "https://rsch.baml.com/report") is True


def test_looks_like_viewer_false_for_pdf() -> None:
    assert _looks_like_viewer(_PLAIN_PDF, "https://research1.ml.com/C?q=x") is False


def test_looks_like_viewer_false_for_interstitial() -> None:
    assert _looks_like_viewer(_INTERSTITIAL_HTML, "https://research1.ml.com/C?q=x") is False


def test_looks_like_viewer_false_for_small_html() -> None:
    # Body must be >= 10KB to be treated as the viewer.
    small = b"<html><body>Liferay research1.ml.com</body></html>"
    assert _looks_like_viewer(small, "https://rsch.baml.com/r?q=x") is False


def test_looks_like_viewer_true_for_rsch_baml_host_with_large_html() -> None:
    # Host alone (rsch.baml.com) + large body is sufficient even without
    # Liferay/research1 markers — the host is the /r? forwarding endpoint.
    body = b"<html><body>" + b"x" * 11_000 + b"</body></html>"
    assert _looks_like_viewer(body, "https://rsch.baml.com/r?q=abc") is True


def test_looks_like_viewer_false_for_other_host_without_markers() -> None:
    body = b"<html><body>" + b"x" * 11_000 + b"</body></html>"
    assert _looks_like_viewer(body, "https://research1.ml.com/C?q=x") is False
