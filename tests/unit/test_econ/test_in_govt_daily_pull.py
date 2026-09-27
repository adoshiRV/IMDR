"""Tests for scripts/econ/in/govt/daily_pull.py — RBI title/date scraping
+ sidecar persistence.

Network- and DB-free. Covers:
- _parse_rbi_listing_html extracts (url, slug, title, publish_date) from
  the real `<a href=...><img alt='PDF - <title>' ...></a>` anchor pattern,
  attributing each row to its nearest preceding date-header.
- Footer/nav PDFs outside rbidocs.rbi.org.in are filtered out.
- Duplicate hrefs are deduped.
- Rows with no matching `alt='PDF - ...'` still yield (url, slug, None, date).
- _rbi_parse_date_header parses "Mon DD, YYYY" and rejects garbage.
- _write_sidecar + the ingest side's _load_sidecar round-trip correctly.
"""

from __future__ import annotations

import importlib
import json

# `scripts.econ.in.govt` can't be imported via a normal `from X.in.Y import`
# statement — `in` is a Python keyword. The production code itself is only
# ever invoked via `python -m scripts.econ.in.govt.daily_pull` (a dotted
# string, not a parsed import statement); tests need the same importlib
# workaround.
daily_pull = importlib.import_module("scripts.econ.in.govt.daily_pull")
_parse_rbi_listing_html = daily_pull._parse_rbi_listing_html
_rbi_parse_date_header = daily_pull._rbi_parse_date_header
_write_sidecar = daily_pull._write_sidecar

_SAMPLE_LISTING_HTML = """
<table class="tablebg" width="100%">
<tr><td class="tableheader" colspan="4" align="left"><b>Jul 14, 2026<b></td></tr>
<tr>
  <td><a class='link2' href=BS_PressReleaseDisplay.aspx?prid=63143>Temporary Closure of RBI Monetary Museum, Mumbai w.e.f. July 22, 2026</a></td>
  <td nowrap colspan=3>
    <a id='APDF_PR665' target='_blank' href='https://rbidocs.rbi.org.in/rdocs/PressRelease/PDFs/PR665BBB.PDF'>
      <img alt='PDF - Temporary Closure of RBI Monetary Museum, Mumbai w.e.f. July 22, 2026' src='../Images/pdf.gif'>
    </a>
  </td>
</tr>
<tr><td class="tableheader" colspan="4" align="left"><b>Jul 13, 2026<b></td></tr>
<tr>
  <td><a class='link2' href=BS_PressReleaseDisplay.aspx?prid=63139>SGB redemption price</a></td>
  <td nowrap colspan=3>
    <a id='APDF_PR6611' target='_blank' href='https://rbidocs.rbi.org.in/rdocs/PressRelease/PDFs/PR6611.PDF'>
      <img alt='PDF - Premature redemption under Sovereign Gold Bond (SGB) Scheme' src='../Images/pdf.gif'>
    </a>
  </td>
</tr>
<tr>
  <td colspan="4">
    <a href="https://www.rbi.org.in/otherpage.aspx">Unrelated nav link, no .pdf</a>
  </td>
</tr>
</table>
"""


def test_parse_rbi_listing_html_extracts_real_title_and_date():
    out = _parse_rbi_listing_html(_SAMPLE_LISTING_HTML)
    by_slug = {slug: (url, title, date) for url, slug, title, date in out}

    assert "PR665BBB.PDF" in by_slug
    url, title, date = by_slug["PR665BBB.PDF"]
    assert url == "https://rbidocs.rbi.org.in/rdocs/PressRelease/PDFs/PR665BBB.PDF"
    assert title == "Temporary Closure of RBI Monetary Museum, Mumbai w.e.f. July 22, 2026"
    assert date == "2026-07-14"

    assert "PR6611.PDF" in by_slug
    _, title2, date2 = by_slug["PR6611.PDF"]
    assert title2 == "Premature redemption under Sovereign Gold Bond (SGB) Scheme"
    assert date2 == "2026-07-13"


def test_parse_rbi_listing_html_only_two_pdfs():
    """Only the two rbidocs.rbi.org.in PDF anchors survive — the
    non-.pdf nav link isn't matched by the PDF-anchor regex at all."""
    out = _parse_rbi_listing_html(_SAMPLE_LISTING_HTML)
    slugs = {slug for _, slug, _, _ in out}
    assert slugs == {"PR665BBB.PDF", "PR6611.PDF"}


def test_parse_rbi_listing_html_filters_non_rbidocs_domain():
    """A .pdf anchor hosted outside rbidocs.rbi.org.in (footer/generic
    site PDF, not a press release) is dropped by the domain filter."""
    html = """
    <tr><td class="tableheader"><b>Jul 10, 2026<b></td></tr>
    <a href="https://www.rbi.org.in/otherpath/generic.pdf">
      <img alt='PDF - Generic Site PDF'>
    </a>
    """
    out = _parse_rbi_listing_html(html)
    assert out == []


def test_parse_rbi_listing_html_dedupes_same_href():
    doubled = _SAMPLE_LISTING_HTML + _SAMPLE_LISTING_HTML
    out = _parse_rbi_listing_html(doubled)
    urls = [url for url, _, _, _ in out]
    assert len(urls) == len(set(urls)) == 2


def test_parse_rbi_listing_html_missing_alt_title_yields_none():
    html_no_alt = """
    <tr><td class="tableheader"><b>Jul 10, 2026<b></td></tr>
    <a href="https://rbidocs.rbi.org.in/rdocs/PressRelease/PDFs/PR700.PDF">no alt attr here</a>
    """
    out = _parse_rbi_listing_html(html_no_alt)
    assert len(out) == 1
    url, slug, title, date = out[0]
    assert slug == "PR700.PDF"
    assert title is None
    assert date == "2026-07-10"


def test_rbi_parse_date_header_valid():
    assert _rbi_parse_date_header("Jul 14, 2026") == "2026-07-14"
    assert _rbi_parse_date_header("  Jan 01, 2022  ") == "2022-01-01"


def test_rbi_parse_date_header_rejects_garbage():
    assert _rbi_parse_date_header("not a date") is None
    assert _rbi_parse_date_header("") is None


def test_write_sidecar_round_trip(tmp_path):
    pdf_path = tmp_path / "PR665BBB.PDF"
    pdf_path.write_bytes(b"%PDF-1.4 fake")
    _write_sidecar(
        pdf_path,
        url="https://rbidocs.rbi.org.in/rdocs/PressRelease/PDFs/PR665BBB.PDF",
        title="Temporary Closure of RBI Monetary Museum",
        publish_date="2026-07-14",
    )
    sidecar = tmp_path / "PR665BBB.PDF.meta.json"
    assert sidecar.exists()
    meta = json.loads(sidecar.read_text(encoding="utf-8"))
    assert meta == {
        "title": "Temporary Closure of RBI Monetary Museum",
        "source_url": "https://rbidocs.rbi.org.in/rdocs/PressRelease/PDFs/PR665BBB.PDF",
        "publish_date": "2026-07-14",
    }
