"""Per-stream resolvers for Indonesia govt-filings ingest.

Each resolver takes a discovered `FilingItem` and returns either
``("pdf", pdf_bytes)`` or ``("text", body_text)``. `ingest_filing` accepts
both: the text path goes through `synthesize_document_from_text`.

## Why Indonesia allows the text path (Australia does not)

`scripts/econ/au/govt/resolvers.py` is PDF-only by a deliberate 2026-06-11
decision — every AU stream is Playwright-rendered to PDF so it lands in
SharePoint. Indonesia follows **Korea's** mixed contract instead, for three
reasons specific to these sources:

1. **BI is HTML-first and its body text is good.** Measured over 11
   consecutive releases (seq 180-190, 3-17 Sep 2026): 821-5,006 characters
   of clean policy prose, and the 2026-08-19 BI-Rate statement is 14,413.
   That is the document, not a summary of it.
2. **BI is not gated**, so the AU justification does not transfer. AU needed
   Playwright anyway to get past RBA's Akamai check, which made
   render-to-PDF nearly free. Here it would mean adding a browser dependency
   to a plain-httpx pipeline purely to re-encode text we already hold.
3. **Where a real publisher PDF exists we take it.** BPS hands back a signed
   PDF URL per press release and DJPPR a `/media/{GUID}` link, so those
   streams are `("pdf", ...)` — the authoritative artefact, with charts and
   tables that body text would lose.

Net: PDF when the publisher has one, text when the page IS the document.
Never a browser.

## Transports

  - `_fetch_pdf_direct`  — plain httpx GET (BPS signed URLs, DJPPR /media/)
  - `_resolve_bi_body`   — BI detail page -> `#layout-page-content` text,
                           preferring `#layout-lampiran` PDFs when attached
  - `_resolve_ojk_body`  — OJK detail page -> article text, preferring a
                           direct `.pdf` href when present

## The BI 404 trap

A missing BI `.aspx` answers **HTTP 200** with full site chrome (~133 KB).
`_bi_detail()` raises on an absent `#layout-title` so the caller records a
resolve failure instead of ingesting a page of navigation as policy text.
"""
from __future__ import annotations

import datetime as dt
import html as _html
import re
import sys
from pathlib import Path
from typing import Literal

sys.path.insert(0, str(Path(__file__).parent))
from _http import make_session, patient_get
from _models import FilingItem

ResolvedKind = Literal["pdf", "text"]
ResolveResult = tuple[ResolvedKind, bytes | str]

BI_ROOT = "https://www.bi.go.id"
OJK_ROOT = "https://ojk.go.id"

# Below this many characters the "body" is boilerplate, not a document.
# BI's thinnest real release in the 11-release sample was 821 chars; OJK
# captions run shorter, so the floor is set under both and the caller turns
# a raise into a per-item resolve failure.
_MIN_BODY_CHARS = 200

_BI_TITLE = re.compile(r'id="layout-title"[^>]*>(.*?)</div>', re.S)
_BI_CONTENT = re.compile(
    r'id="layout-page-content"[^>]*>(.*?)'
    r'(?=<div[^>]*id="layout-(?:lampiran|kontak|last-update))',
    re.S,
)
_BI_ATTACH = re.compile(
    r'id="layout-lampiran"[^>]*>(.*?)(?=<div[^>]*id="layout-(?:kontak|last-update))',
    re.S,
)
_OJK_CONTENT = re.compile(
    r'<div[^>]*class="[^"]*(?:ms-rtestate-field|article-content|isi-berita)[^"]*"[^>]*>(.*?)</div>',
    re.S,
)
_HREF = re.compile(r'href="([^"]+)"')
_PDF_HREF = re.compile(r'href="([^"]+\.pdf[^"]*)"', re.I)


def _text(raw: str) -> str:
    """Strip markup, entities and SharePoint zero-width junk."""
    s = re.sub(r"<(?:script|style)[^>]*>.*?</(?:script|style)>", " ", raw, flags=re.S)
    s = re.sub(r"<[^>]+>", " ", s)
    s = _html.unescape(s).replace("\xa0", " ").replace("​", "").replace("‍", "")
    return re.sub(r"\s+", " ", s).strip()


def _fetch_pdf_direct(url: str) -> bytes:
    """Plain httpx GET for a publisher PDF."""
    with make_session(timeout=120.0) as client:
        r = patient_get(client, url, min_bytes=1024)
    body = r.content
    if not body.startswith(b"%PDF"):
        raise RuntimeError(
            f"not a PDF (first bytes {body[:8]!r}) for {url} — "
            f"BPS signed URLs expire, so re-discover before retrying"
        )
    return body


def _bi_detail(url: str) -> str:
    """Fetch a BI detail page, rejecting the HTTP-200 disguised 404."""
    with make_session() as client:
        html = patient_get(client, url).text
    if not _BI_TITLE.search(html):
        raise RuntimeError(f"BI page missing (200-with-chrome 404): {url}")
    return html


def _resolve_bi_body(item: FilingItem) -> ResolveResult:
    """Prefer an attached PDF; otherwise the page body text."""
    html = _bi_detail(item.source_url)

    attach = _BI_ATTACH.search(html)
    if attach:
        for href in _HREF.findall(attach.group(1)):
            if ".pdf" in href.lower():
                pdf_url = href if href.startswith("http") else BI_ROOT + href
                try:
                    return "pdf", _fetch_pdf_direct(pdf_url)
                except Exception:
                    # An unreachable attachment must not lose the release —
                    # fall through to the body text, which is the document
                    # for most BI streams anyway.
                    break

    body = _BI_CONTENT.search(html)
    text = _text(body.group(1)) if body else ""
    if len(text) < _MIN_BODY_CHARS:
        raise RuntimeError(
            f"BI body too thin ({len(text)} chars < {_MIN_BODY_CHARS}): "
            f"{item.source_url}"
        )
    return "text", text


def _resolve_ojk_body(item: FilingItem) -> ResolveResult:
    """OJK detail page: direct PDF href if there is one, else article text."""
    with make_session() as client:
        html = patient_get(client, item.source_url).text

    m = _PDF_HREF.search(html)
    if m:
        href = m.group(1)
        pdf_url = href if href.startswith("http") else OJK_ROOT + href
        try:
            return "pdf", _fetch_pdf_direct(pdf_url)
        except Exception:
            pass

    chunks = [_text(c) for c in _OJK_CONTENT.findall(html)]
    text = max(chunks, key=len) if chunks else ""
    if len(text) < _MIN_BODY_CHARS:
        # Fall back to the listing abstract, which the fetcher already
        # captured — better a short real document than a dropped one.
        text = item.extras.get("abstract", "")
    if len(text) < _MIN_BODY_CHARS:
        raise RuntimeError(
            f"OJK body too thin ({len(text)} chars): {item.source_url}"
        )
    return "text", text


def _resolve_pdf_url(item: FilingItem) -> ResolveResult:
    """For streams whose listing row already carries the document URL."""
    if not item.pdf_url:
        raise RuntimeError(f"no pdf_url on {item.stream} item: {item.source_url}")
    return "pdf", _fetch_pdf_direct(item.pdf_url)


def _resolve_djppr_detail(item: FilingItem) -> ResolveResult:
    """DJPPR press release: the CMS detail payload carries the full text.

    The listing repeater gives only a title + date, which is why this looked
    at first like an SPA with nothing to ingest. It is not: fetching the
    detail slug through the same `?url=` API returns a `@Konten` field with
    the entire release (34,422 characters on the ORI030 result of
    2026-08-03), and usually a `@link-file` pointing at the PDF.

    Field names are read case-insensitively — this CMS emits `@Konten`
    and `@link-file` here but `@judul`/`@tanggal` on the listing, and it
    does not agree with itself on case across pages.

    **Not every press row links to a detail page.** A minority point straight
    at a media file (`.../web/api/v1/media/{GUID}`), so deriving a slug from
    the last path segment yields the GUID and the page API answers "404".
    Observed on the full 2026-09-21 ingest: `Pembukaan Masa Penawaran Green
    Sukuk Ritel` linked to `E6B48E4B-9108-4872-896D-0AC966451083`. Those rows
    already carry the file in `pdf_url`, so take it directly.
    """
    import json

    # Direct-to-media row: there is no detail page to fetch.
    if item.pdf_url and "/media/" in item.pdf_url:
        return "pdf", _fetch_pdf_direct(item.pdf_url)

    slug = item.source_url.rsplit("/", 1)[-1]
    with make_session() as client:
        payload = patient_get(
            client, "https://api-djppr.kemenkeu.go.id/web/api/v1/page?url=" + slug
        ).json()
    data = payload.get("Data") or {}
    if data.get("Title") == "404" or not data.get("PageContentLive"):
        raise RuntimeError(f"DJPPR detail slug not found: {slug}")

    leaves: dict[str, str] = {}

    def walk(node) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                if isinstance(v, str) and len(v) > len(leaves.get(k.lower(), "")):
                    leaves[k.lower()] = v
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(json.loads(data["PageContentLive"]))

    pdf = leaves.get("@link-file") or leaves.get("@linkfile")
    if pdf and pdf.startswith("http"):
        try:
            return "pdf", _fetch_pdf_direct(pdf)
        except Exception:
            pass  # fall through to the text, which is the full release

    text = _text(leaves.get("@konten", ""))
    if len(text) < _MIN_BODY_CHARS:
        raise RuntimeError(
            f"DJPPR body too thin ({len(text)} chars): {item.source_url}"
        )
    return "text", text


# ---------------------------------------------------------------------
# Dispatch — by `stream`, so BI's 10 streams pick the right transport
# ---------------------------------------------------------------------

_RESOLVERS = {
    # BI — every stream is an .aspx detail page
    "news_release":           _resolve_bi_body,
    "news_release_en":        _resolve_bi_body,
    "policy_review_tkm":      _resolve_bi_body,
    "policy_report_lkm":      _resolve_bi_body,
    "financial_stability":    _resolve_bi_body,
    "inflation_analysis":     _resolve_bi_body,
    "money_supply_report":    _resolve_bi_body,
    "bop_report":             _resolve_bi_body,
    "annual_economic_report": _resolve_bi_body,
    "governor_speeches":      _resolve_bi_body,
    # BPS — the API row carries a signed PDF URL
    "press_release_brs":      _resolve_pdf_url,
    "publication":            _resolve_pdf_url,
    "news":                   _resolve_pdf_url,
    # DJPPR — press releases resolve through the CMS detail payload
    # (@Konten / @link-file); calendars + term sheets are /media/ documents
    # whose URL is already on the listing row.
    "press_release":          _resolve_djppr_detail,
    "auction_calendar":       _resolve_pdf_url,
    "retail_sbn":             _resolve_pdf_url,
    # OJK
    "press_release_en":       _resolve_ojk_body,
    "annual_report":          _resolve_ojk_body,
}

# `press_release` is a stream name BOTH DJPPR and OJK use, so dispatching on
# stream alone is ambiguous for it. `resolve()` disambiguates on
# vendor_code before falling back to the table.
_BY_VENDOR_STREAM = {
    ("djppr", "press_release"): _resolve_djppr_detail,
    ("ojk", "press_release"):   _resolve_ojk_body,
}

_DISCOVERY_ONLY: set[str] = set()


def is_ingestable(item: FilingItem) -> bool:
    """False for rows we discover but deliberately do not ingest.

    Order matters: the undated guard must run BEFORE the resolver lookup,
    or DJPPR's undated rows would slip through on a vendor+stream match.
    """
    if f"{item.vendor_code}|{item.stream}" in _DISCOVERY_ONLY:
        return False
    if item.extras.get("undated") == "1":
        # Undated reference artefacts (issuance calendars, retail-SBN term
        # sheets) carry no meaningful publish_date — the fetcher stamps them
        # with today so they are not lost, which would misdate a
        # date-ordered corpus.
        return False
    if (item.vendor_code, item.stream) in _BY_VENDOR_STREAM:
        return True
    return item.stream in _RESOLVERS


def resolve(item: FilingItem) -> ResolveResult:
    fn = _BY_VENDOR_STREAM.get((item.vendor_code, item.stream))
    if fn is None:
        fn = _RESOLVERS.get(item.stream)
    if fn is None:
        raise ValueError(
            f"no resolver for stream={item.stream!r} "
            f"(vendor_code={item.vendor_code!r})"
        )
    return fn(item)


# ---------------------------------------------------------------------
# BI archive backfill — sequential news-release ID enumeration
# ---------------------------------------------------------------------
#
# BI's listings are page-1-only (pagination is a dead end from plain httpx
# — see `_bi_aspnet`), so this is the ONLY way to reach the archive.
#
# News-release detail URLs are `sp_{28}{seq}{yy}.aspx`, where 28 is the
# Communication Department's code, `seq` the release number within the year
# and `yy` the 2-digit year — release "No.28/184/DKom" of 2026 is
# `sp_2818426.aspx`. The sequence is dense: verified 2026 seq 180-190 all
# resolve, 191+ are the disguised 404.

BI_SP_URL = BI_ROOT + "/id/publikasi/ruang-media/news-release/Pages/sp_28{seq}{yy}.aspx"

_BI_DATE = re.compile(r'id="layout-date"[^>]*>(.*?)</div>', re.S)
_BI_TITLE_SUFFIX = re.compile(
    r"\s*(?:Siaran Pers|News Release|Press Release|Laporan|Pidato)\s*$", re.I
)


def is_missing(html: str) -> bool:
    """True when a BI `.aspx` is really a 404 wearing an HTTP 200.

    Structural on purpose: the 404 body is ~133,451 bytes today, but a
    byte-count check would break on the next template tweak.
    """
    return not _BI_TITLE.search(html)


def _bi_date(raw: str) -> dt.date | None:
    """`"9/17/2026 7:00 PM"` -> `date(2026, 9, 17)`.

    BI's detail pages serve **M/D/YYYY**, unlike its listings which serve
    `D Month YYYY`. Reading this as D/M/YYYY silently mis-dates every
    release published before the 13th of a month.
    """
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", _text(raw))
    if not m:
        return None
    try:
        return dt.date(int(m.group(3)), int(m.group(1)), int(m.group(2)))
    except ValueError:
        return None


def bi_news_release_url(seq: int, year: int) -> str:
    return BI_SP_URL.format(seq=seq, yy=year % 100)


def resolve_bi_detail(url: str) -> dict:
    """Full BI detail parse — title, date, body, attachments, department.

    Used by the backfill enumerator and available for ad-hoc inspection.
    Returns `{"ok": False, ...}` for the disguised 404 rather than raising,
    so a caller walking a sequence can just skip.
    """
    with make_session() as client:
        html = patient_get(client, url).text
    if is_missing(html):
        return {"ok": False, "url": url, "reason": "missing (200-with-chrome 404)"}

    title = _BI_TITLE_SUFFIX.sub("", _text(_BI_TITLE.search(html).group(1)))
    d = _BI_DATE.search(html)
    body = _BI_CONTENT.search(html)
    att = _BI_ATTACH.search(html)
    pdfs = []
    if att:
        for href in _HREF.findall(att.group(1)):
            if ".pdf" in href.lower():
                pdfs.append(href if href.startswith("http") else BI_ROOT + href)
    dept = re.search(r'id="layout-sumber-data"[^>]*>(.*?)</div></div>', html, re.S)
    return {
        "ok": True,
        "url": url,
        "title": title,
        "publish_date": _bi_date(d.group(1)) if d else None,
        "body_text": _text(body.group(1)) if body else "",
        "pdf_urls": pdfs,
        "source_dept": _text(dept.group(1)) if dept else "",
    }


def probe_bi_sequence(year: int, start: int, stop: int) -> list[dict]:
    """Resolve `sp_28{start..stop}{yy}`, skipping the disguised 404s.

    Backfill / discovery helper — NOT called by the daily ingest. Walk
    small ranges: each hit is a ~160 KB page.
    """
    out = []
    for seq in range(start, stop + 1):
        got = resolve_bi_detail(bi_news_release_url(seq, year))
        if got["ok"]:
            got["seq"] = seq
            out.append(got)
    return out
