"""Beige Book (Summary of Commentary on Current Economic Conditions) — probe.

Source: federalreserve.gov/monetarypolicy/beige-book-default.htm
Archive: federalreserve.gov/monetarypolicy/beige-book-archive.htm
         → per-year index /monetarypolicy/beigebook{YYYY}.htm

Published 8×/yr (~2 weeks before each FOMC meeting), the Beige Book is the
12-district anecdotal-conditions read that feeds the meeting. Per release:

    /monetarypolicy/beigebook{YYYYMM}[-summary].htm   ← national summary (HTML)
    /monetarypolicy/files/BeigeBook_{YYYYMMDD}.pdf     ← full report (PDF)

IMPORTANT slug quirk (verified 2026-06-22): the HTML detail slug uses a
sequential meeting-cycle `{YYYYMM}` that does NOT map to the PDF's release
month, and the `-summary` suffix is present on some editions and absent on
others. So the listing's HTML and PDF hrefs are both extracted directly and
paired in document order — never reconstructed. The **PDF filename carries
the authoritative release date** `{YYYYMMDD}` and is the publish_date.

The default page lists only the current year (~8 releases). To reach the
requested ~16 (≈2 years), this probe also pulls the prior calendar year's
archive index `/monetarypolicy/beigebook{YYYY-1}.htm`. Same href shapes on
every page.

Crawler shape: **Shape B — index HTML listing, slug-keyed** (1-2 GETs,
regex over hrefs, date from the PDF filename). plain httpx, no Playwright.

Reachability (probed 2026-06-22): default 200 OK / ~88 KB; year index
200 OK / ~50 KB; PDF 200 application/pdf. No JS, no gate.
"""
from __future__ import annotations

import bisect
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _http import make_session, patient_get, save_raw  # noqa: E402
from _models import FetchResult, FilingItem  # noqa: E402

FED_BASE = "https://www.federalreserve.gov"
DEFAULT_URL = f"{FED_BASE}/monetarypolicy/beige-book-default.htm"

# Full report PDF carries the release date: BeigeBook_{YYYYMMDD}.pdf
_BB_PDF_RE = re.compile(r'(?:href="|https?://[^"]*?)?(/monetarypolicy/files/BeigeBook_(\d{8})\.pdf)', re.I)
# National-summary HTML: beigebook{YYYYMM}[-summary].htm
_BB_HTML_RE = re.compile(r'(/monetarypolicy/beigebook(\d{6})(?:-summary)?\.htm)', re.I)


def _date_from_slug(yyyymmdd: str) -> date | None:
    try:
        return date(int(yyyymmdd[:4]), int(yyyymmdd[4:6]), int(yyyymmdd[6:8]))
    except ValueError:
        return None


def _parse_page(html: str) -> list[tuple[date, str, str]]:
    """Return (release_date, pdf_url, html_url) triples from one listing page.

    The listing renders the year's releases as interleaved HTML→PDF pairs in
    document order (each release's national-summary `.htm` link immediately
    precedes its `BeigeBook_{YYYYMMDD}.pdf`), then — lower on the page — a
    flat all-years archive list of bare `.htm` links with NO adjacent PDF.

    Because the HTML slug's cycle-month `{YYYYMM}` does NOT map to the PDF's
    release month and the `-summary` suffix varies, pairing is done by **byte
    adjacency**: each PDF takes the nearest preceding HTML link in document
    order. The archive-block HTML links (no following PDF) are never the
    nearest-preceding of any PDF, so they're naturally ignored. The PDF's
    `{YYYYMMDD}` is the authoritative release date.
    """
    # Collect (offset, html_url) for every summary link.
    html_at: list[tuple[int, str]] = [
        (m.start(), FED_BASE + m.group(1)) for m in _BB_HTML_RE.finditer(html)
    ]
    html_at.sort()
    html_offsets = [o for o, _ in html_at]

    out: list[tuple[date, str, str]] = []
    seen_pdf: set[str] = set()
    import bisect
    for m in _BB_PDF_RE.finditer(html):
        href, yyyymmdd = m.group(1), m.group(2)
        d = _date_from_slug(yyyymmdd)
        if d is None or yyyymmdd in seen_pdf:
            continue
        seen_pdf.add(yyyymmdd)
        pdf_url = FED_BASE + href
        # Nearest HTML link strictly before this PDF's offset.
        idx = bisect.bisect_left(html_offsets, m.start()) - 1
        html_url = html_at[idx][1] if idx >= 0 else pdf_url
        out.append((d, pdf_url, html_url))
    return out


def discover(*, limit: int = 16, save_raw_html: bool = True) -> FetchResult:
    pages: list[str] = []
    this_year = date.today().year
    # Default page = current year (~8). Each prior-year index adds ~8 more.
    # Walk back enough years to cover `limit`, hard-capped at 3 prior years.
    urls = [(DEFAULT_URL, "beige-book-default.htm")]
    n_prior_years = max(1, min(3, -(-limit // 8)))   # ceil(limit/8), 1..3
    for yr in range(this_year - 1, this_year - 1 - n_prior_years, -1):
        urls.append((f"{FED_BASE}/monetarypolicy/beigebook{yr}.htm", f"beigebook{yr}.htm"))

    triples: list[tuple[date, str, str]] = []
    with make_session() as sess:
        for url, fname in urls:
            try:
                r = patient_get(sess, url)
            except RuntimeError:
                continue                        # year index may not exist; skip
            if save_raw_html:
                save_raw("beige_book", fname, r.text)
            pages.append(fname)
            triples.extend(_parse_page(r.text))

    # Dedup by PDF url, newest first, cap at limit.
    by_pdf: dict[str, tuple[date, str, str]] = {}
    for d, pdf_url, html_url in triples:
        by_pdf.setdefault(pdf_url, (d, pdf_url, html_url))
    rows = sorted(by_pdf.values(), key=lambda t: t[0], reverse=True)[:limit]

    items = [
        FilingItem(
            vendor_code="fed",
            title=f"Beige Book - {d.isoformat()}",
            publish_date=d,
            source_url=html_url,
            pdf_url=pdf_url,
            doc_type="report",
            stream="beige_book",
            extras={"release_date": d.isoformat()},
        )
        for d, pdf_url, html_url in rows
    ]
    return FetchResult(
        vendor_code="fed",
        ok=True,
        items=items,
        note=f"{len(items)} Beige Book releases from {len(pages)} listing page(s) {pages}",
    )


def _print_summary(res: FetchResult) -> None:
    print(f"beige_book  ok={res.ok}  items={len(res.items)}  err={res.error}")
    print(f"  note: {res.note}")
    for it in res.items[:10]:
        print(f"  {it.publish_date}  [{it.doc_type:7}] {it.title}")
        print(f"             html: {it.source_url}")
        print(f"             pdf : {it.pdf_url}")


if __name__ == "__main__":
    _print_summary(discover())
