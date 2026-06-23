"""Financial Stability Report (FSR) — discovery probe.

Source: federalreserve.gov/publications/financial-stability-report.htm

The FSR is the Fed Board's semi-annual (≈May + Nov) asset-valuation /
leverage / funding-risk read. The listing page is a single server-rendered
HTML page with every report back to 2018. Per report:

    /publications/files/financial-stability-report-{YYYYMMDD}.pdf  ← report (PDF)
    /publications/{month}-{year}-financial-stability-report-purpose-and-framework.htm
                                                                   ← landing (HTML)

The PDF filename carries the exact release date `{YYYYMMDD}` (the
authoritative publish_date). The HTML landing slug is free-form prose
(`2026-may-...`, `november-2025-...`, `April-2025-...`) with inconsistent
casing/order, so the listing's HTML hrefs are extracted directly and paired
to the nearest PDF in document order rather than reconstructed.

Crawler shape: **Shape B — index HTML listing, slug-keyed** (single GET,
regex over hrefs, date from the PDF filename). plain httpx, no Playwright.

Reachability (probed 2026-06-22): 200 OK / ~86 KB; PDF 200 application/pdf.
No JS, no gate.
"""
from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _http import make_session, patient_get, save_raw  # noqa: E402
from _models import FetchResult, FilingItem  # noqa: E402

FED_BASE = "https://www.federalreserve.gov"
FSR_URL = f"{FED_BASE}/publications/financial-stability-report.htm"

# Report PDF carries the release date.
_FSR_PDF_RE = re.compile(
    r'/publications/files/financial-stability-report-(\d{8})\.pdf', re.I
)
# Landing page: prose slug ending in -purpose-and-framework.htm
_FSR_HTML_RE = re.compile(
    r'href="(/publications/[a-z0-9\-]*financial-stability[a-z0-9\-]*purpose-and-framework\.htm)"',
    re.I,
)


def _date_from_slug(yyyymmdd: str) -> date | None:
    try:
        return date(int(yyyymmdd[:4]), int(yyyymmdd[4:6]), int(yyyymmdd[6:8]))
    except ValueError:
        return None


def _parse_listing(html: str) -> list[FilingItem]:
    pdfs: list[tuple[date, str]] = []
    seen: set[str] = set()
    for m in _FSR_PDF_RE.finditer(html):
        yyyymmdd = m.group(1)
        d = _date_from_slug(yyyymmdd)
        if d is None or yyyymmdd in seen:
            continue
        seen.add(yyyymmdd)
        pdfs.append((d, f"{FED_BASE}/publications/files/financial-stability-report-{yyyymmdd}.pdf"))

    # Landing hrefs in document order (newest first on the page).
    html_links: list[str] = []
    seen_h: set[str] = set()
    for m in _FSR_HTML_RE.finditer(html):
        href = m.group(1)
        if href in seen_h:
            continue
        seen_h.add(href)
        html_links.append(FED_BASE + href)

    # Page lists newest-first for both; pair by position.
    pdfs_sorted = sorted(pdfs, key=lambda t: t[0], reverse=True)
    items: list[FilingItem] = []
    for i, (d, pdf_url) in enumerate(pdfs_sorted):
        landing = html_links[i] if i < len(html_links) else pdf_url
        items.append(FilingItem(
            vendor_code="fed",
            title=f"Financial Stability Report - {d.isoformat()}",
            publish_date=d,
            source_url=landing,
            pdf_url=pdf_url,
            doc_type="report",
            stream="financial_stability_report",
            extras={"release_date": d.isoformat()},
        ))
    return items


def discover(*, save_raw_html: bool = True) -> FetchResult:
    with make_session() as sess:
        try:
            r = patient_get(sess, FSR_URL)
        except RuntimeError as exc:
            return FetchResult(vendor_code="fed", ok=False, error=str(exc))
    if save_raw_html:
        save_raw("financial_stability_report", "financial-stability-report.htm", r.text)
    items = _parse_listing(r.text)
    return FetchResult(
        vendor_code="fed",
        ok=True,
        items=items,
        note=f"{len(items)} Financial Stability Reports parsed from FSR listing",
    )


def _print_summary(res: FetchResult) -> None:
    print(f"financial_stability_report  ok={res.ok}  items={len(res.items)}  err={res.error}")
    print(f"  note: {res.note}")
    for it in res.items[:10]:
        print(f"  {it.publish_date}  [{it.doc_type:7}] {it.title}")
        print(f"             html: {it.source_url}")
        print(f"             pdf : {it.pdf_url}")


if __name__ == "__main__":
    _print_summary(discover())
