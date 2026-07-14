"""Senior Loan Officer Opinion Survey (SLOOS) — discovery probe.

Source: federalreserve.gov/data/sloos.htm

The SLOOS is the quarterly (Jan/Apr/Jul/Oct) bank-lending-standards survey —
a leading credit-cycle read. The landing page lists every release back to
~1996 as a link to a per-release HTML summary, each with companion PDFs:

    /data/sloos/sloos-{YYYYMM}.htm            ← national summary (HTML)
    /data/documents/sloos-{YYYYMM}.pdf        ← summary report (PDF)
    /data/documents/sloos-{YYYYMM}-table1.pdf , -table2.pdf , -charts.pdf

The release slug `{YYYYMM}` is the survey reference month (01/04/07/10), the
publish_date used here (the report itself prints the exact release date a
few weeks later in body text; that precise date is left to body-resolution
at ingest time). `source_url` is the HTML summary; `pdf_url` is the summary
PDF; the table/chart PDFs are carried in `extras`.

Crawler shape: **Shape B — index HTML listing, slug-keyed** (single GET,
regex over hrefs, date from the `{YYYYMM}` URL slug). plain httpx, no
Playwright.

Reachability (probed 2026-06-22): listing 200 OK / ~105 KB; summary PDF 200
application/pdf / ~1.4-1.6 MB. No JS, no gate. (A `/feeds/sloos.html` link
exists but the HTML listing already carries the full slug-keyed archive, so
no feed is needed.)
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
SLOOS_URL = f"{FED_BASE}/data/sloos.htm"

# Per-release HTML summary: /data/sloos/sloos-{YYYYMM}.htm
_SLOOS_HREF_RE = re.compile(r"/data/sloos/sloos-(\d{6})\.htm", re.I)


def _date_from_yyyymm(yyyymm: str) -> date | None:
    try:
        return date(int(yyyymm[:4]), int(yyyymm[4:6]), 1)
    except ValueError:
        return None


def _parse_listing(html: str, *, limit: int) -> list[FilingItem]:
    items: list[FilingItem] = []
    seen: set[str] = set()
    for m in _SLOOS_HREF_RE.finditer(html):
        yyyymm = m.group(1)
        d = _date_from_yyyymm(yyyymm)
        if d is None or yyyymm in seen:
            continue
        seen.add(yyyymm)
        html_url = f"{FED_BASE}/data/sloos/sloos-{yyyymm}.htm"
        pdf_url = f"{FED_BASE}/data/documents/sloos-{yyyymm}.pdf"
        items.append(FilingItem(
            vendor_code="fed",
            title=f"Senior Loan Officer Opinion Survey - {yyyymm[:4]}-{yyyymm[4:6]}",
            publish_date=d,
            source_url=html_url,
            pdf_url=pdf_url,
            doc_type="survey",
            stream="sloos",
            extras={
                "reference_month": f"{yyyymm[:4]}-{yyyymm[4:6]}",
                "table_pdfs": [
                    f"{FED_BASE}/data/documents/sloos-{yyyymm}-table1.pdf",
                    f"{FED_BASE}/data/documents/sloos-{yyyymm}-table2.pdf",
                ],
                "charts_pdf": f"{FED_BASE}/data/documents/sloos-{yyyymm}-charts.pdf",
            },
        ))
    items.sort(key=lambda it: it.publish_date, reverse=True)
    return items[:limit]


def discover(*, limit: int = 16, save_raw_html: bool = True) -> FetchResult:
    """Pull the most-recent ``limit`` SLOOS releases (default 16 ≈ 4 years)."""
    with make_session() as sess:
        try:
            r = patient_get(sess, SLOOS_URL)
        except RuntimeError as exc:
            return FetchResult(vendor_code="fed", ok=False, error=str(exc))
    if save_raw_html:
        save_raw("sloos", "sloos.htm", r.text)
    items = _parse_listing(r.text, limit=limit)
    return FetchResult(
        vendor_code="fed",
        ok=True,
        items=items,
        note=f"top {len(items)} SLOOS releases parsed from /data/sloos.htm",
    )


def _print_summary(res: FetchResult) -> None:
    print(f"sloos  ok={res.ok}  items={len(res.items)}  err={res.error}")
    print(f"  note: {res.note}")
    for it in res.items[:10]:
        print(f"  {it.publish_date}  [{it.doc_type:7}] {it.title}")
        print(f"             html: {it.source_url}")
        print(f"             pdf : {it.pdf_url}")


if __name__ == "__main__":
    _print_summary(discover())
