"""Per-agency body / PDF resolvers.

Each resolver takes a discovered FilingItem and returns one of:
  * ``("pdf", pdf_bytes)``  — for sources where we can pull the PDF
  * ``("body", body_text)`` — for HTML-only or PDF-blocked sources

Recipes proven 2026-06-10 — see
``docs/admin/econ/korea/govt_doc_sources.md`` §Per-agency resolution
recipes for the empirical basis.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Literal

from bs4 import BeautifulSoup  # type: ignore

sys.path.insert(0, str(Path(__file__).parent))
from _http import make_session, patient_get  # noqa: E402
from _models import FilingItem  # noqa: E402

ResolvedKind = Literal["pdf", "body"]
ResolveResult = tuple[ResolvedKind, bytes | str]


# ─── BoK ──────────────────────────────────────────────────────────────
def resolve_bok(item: FilingItem) -> ResolveResult:
    """view.do → grab the .pdf anchor (skip .hwp sibling) → download."""
    sess = make_session()
    r = patient_get(sess, item.source_url)
    soup = BeautifulSoup(r.text, "html.parser")
    pdf_href: str | None = None
    for a in soup.find_all("a", href=True):
        href = str(a.get("href") or "")
        if re.search(r"\.hwp", href, re.I):
            continue
        if re.search(r"\.pdf([\?&]|$)", href, re.I) or "CommonDownload" in href:
            pdf_href = href
            break
    if not pdf_href:
        # Fallback: use the detail page text as body
        text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))
        return ("body", text)
    pdf_url = pdf_href if pdf_href.startswith("http") else f"https://www.bok.or.kr{pdf_href}"
    pdf = patient_get(sess, pdf_url)
    return ("pdf", pdf.content)


# ─── FSS ──────────────────────────────────────────────────────────────
def resolve_fss(item: FilingItem) -> ResolveResult:
    """view.do → dl.file-list → first <a> → /eng/cmmn/file/fileDown.do?..."""
    sess = make_session()
    r = patient_get(sess, item.source_url)
    soup = BeautifulSoup(r.text, "html.parser")
    file_list = soup.find("dl", class_="file-list")
    if not file_list:
        body = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))
        return ("body", body)
    a = file_list.find("a", href=True)
    if not a:
        body = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))
        return ("body", body)
    href = str(a.get("href") or "")
    pdf_url = href if href.startswith("http") else f"https://www.fss.or.kr{href}"
    pdf = patient_get(sess, pdf_url)
    return ("pdf", pdf.content)


# ─── FSC ──────────────────────────────────────────────────────────────
def resolve_fsc(item: FilingItem) -> ResolveResult:
    """detail page has BOTH body and PDF. Prefer PDF.

    Article-ID is the last path segment of the source_url
    (/eng/pr010101/{article_id}). PDF URL is deterministic.
    """
    sess = make_session()
    r = patient_get(sess, item.source_url)
    soup = BeautifulSoup(r.text, "html.parser")
    # Article id from URL path
    m = re.search(r"/pr010101/(\d+)", item.source_url)
    article_id = m.group(1) if m else None
    if article_id:
        pdf_url = (
            f"https://www.fsc.go.kr/comm/getFile?srvcId=BBSTY1"
            f"&upperNo={article_id}&fileTy=ATTACH&fileNo=1"
        )
        try:
            pdf = patient_get(sess, pdf_url, attempts=6)
            if pdf.content.startswith(b"%PDF"):
                return ("pdf", pdf.content)
        except RuntimeError:
            pass
    # Fallback: body text
    wrap = soup.find("div", class_="board-view-wrap")
    body_node = wrap.find("div", class_="body") if wrap else None
    body_text = re.sub(r"\s+", " ", body_node.get_text(" ", strip=True)) if body_node else ""
    if not body_text:
        body_text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))
    return ("body", body_text)


# ─── KDI ──────────────────────────────────────────────────────────────
def resolve_kdi(item: FilingItem) -> ResolveResult:
    """detail page → parse onclick='/eng/file/download?atch_no=...' → GET."""
    sess = make_session()
    r = patient_get(sess, item.source_url)
    m = re.search(r"onclick=\"location\.href='(/eng/file/download[^']+)'\"", r.text)
    if not m:
        soup = BeautifulSoup(r.text, "html.parser")
        body = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))
        return ("body", body)
    pdf_url = f"https://www.kdi.re.kr{m.group(1)}"
    pdf = patient_get(sess, pdf_url)
    if not pdf.content.startswith(b"%PDF"):
        soup = BeautifulSoup(r.text, "html.parser")
        body = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))
        return ("body", body)
    return ("pdf", pdf.content)


# ─── MOEF ─────────────────────────────────────────────────────────────
def resolve_moef(item: FilingItem) -> ResolveResult:
    """detail page → body text. No PDF attachments on the boards we cover."""
    sess = make_session()
    r = patient_get(sess, item.source_url)
    soup = BeautifulSoup(r.text, "html.parser")
    body_node = (
        soup.find("div", class_="board-view-cont")
        or soup.find("div", class_="bbs-view-cont")
        or soup.find("div", class_="view_cont")
    )
    if body_node is None:
        body_node = max(soup.find_all("div"), key=lambda d: len(d.get_text(strip=True)), default=None)
    body_text = re.sub(r"\s+", " ", body_node.get_text(" ", strip=True)) if body_node else ""
    if not body_text:
        body_text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))
    return ("body", body_text)


# ─── MOTIR ────────────────────────────────────────────────────────────
def resolve_motir(item: FilingItem) -> ResolveResult:
    """Article.js → /eng/article/{cat}/{bbsSeqN}/view → body in div.detail-cont.

    PDF download via /attach/down/... is TLS-blocked from this network
    (per the 2026-06-10 probe) — body text path only.
    """
    extras = item.extras or {}
    article_id = extras.get("article_id")
    article_type = extras.get("article_type", "2")
    category_hash = extras.get("category_hash", "EATCLdfa319ada")
    if not article_id:
        return ("body", item.title)   # last-ditch fallback
    detail_url = (
        f"https://english.motir.go.kr/eng/article/{category_hash}/{article_id}/view"
        f"?pageIndex=1&bbsCdN={article_type}"
    )
    sess = make_session()
    r = patient_get(sess, detail_url, attempts=12, base_sleep=3.0)
    soup = BeautifulSoup(r.text, "html.parser")
    body_node = soup.find("div", class_="detail-cont")
    if body_node is None:
        body_node = soup.find("div", class_="board-detail")
    if body_node is None:
        body_node = max(soup.find_all("div"), key=lambda d: len(d.get_text(strip=True)), default=None)
    body_text = re.sub(r"\s+", " ", body_node.get_text(" ", strip=True)) if body_node else ""
    if not body_text:
        body_text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))
    return ("body", body_text)


# ─── KCS ──────────────────────────────────────────────────────────────
def resolve_kcs(item: FilingItem) -> ResolveResult:
    """Deferred: News board attachments are JPG images, not PDFs.

    Returns title-only body so the daily pull doesn't crash; ingest
    consumers should generally skip KCS until live boards are mapped
    (Korean-side press releases are the real target).
    """
    return ("body", item.title)


# ─── Dispatch ─────────────────────────────────────────────────────────
_RESOLVERS = {
    "bok": resolve_bok,
    "fss": resolve_fss,
    "fsc": resolve_fsc,
    "kdi": resolve_kdi,
    "moef": resolve_moef,
    "motir": resolve_motir,
    "kcs": resolve_kcs,
}


def resolve(item: FilingItem) -> ResolveResult:
    fn = _RESOLVERS.get(item.vendor_code)
    if fn is None:
        raise ValueError(f"no resolver for vendor_code={item.vendor_code!r}")
    return fn(item)


if __name__ == "__main__":
    # Smoke test — pick one item from the latest snapshot per vendor and resolve.
    import io as _io
    import json as _json
    sys.stdout = _io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    snap_dir = Path(__file__).parent / "data" / "snapshots"
    snaps = sorted(snap_dir.glob("*.json"))
    if not snaps:
        print("no snapshot — run ingest_filings.py first")
        sys.exit(1)
    payload = _json.loads(snaps[-1].read_text(encoding="utf-8"))
    for vendor, items in payload.get("vendors", {}).items():
        if not items:
            continue
        item = FilingItem.from_json(items[0])
        try:
            kind, body = resolve(item)
            size = len(body) if isinstance(body, (bytes, str)) else 0
            preview = body[:120] if isinstance(body, str) else body[:8].hex()
            print(f"  {vendor:6}  kind={kind}  size={size}  preview={preview!r}")
        except Exception as exc:  # noqa: BLE001
            print(f"  {vendor:6}  ERR  {type(exc).__name__}: {str(exc)[:160]}")
