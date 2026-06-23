"""Monetary Policy Report (MPR) — discovery probe.

Source: federalreserve.gov/monetarypolicy/publications/mpr_default.htm

The MPR is the semi-annual (Feb + Jul) macro narrative the Fed submits to
Congress alongside the Chair's Humphrey-Hawkins testimony. The default page
is a single server-rendered HTML listing of all reports back to ~1996. Per
report:

    /publications/files/{YYYYMMDD}_mprfullreport.pdf   ← full report (PDF)
        (older / some reports live under /monetarypolicy/files/ instead)
    /monetarypolicy/{YYYY}-{MM}-mpr-statement.htm       ← landing page (HTML)
        (older reports use -summary.htm instead of -statement.htm)

The full-report PDF filename carries the exact release date `{YYYYMMDD}`,
which is the authoritative publish_date. The HTML landing slug uses
`{YYYY}-{MM}` (report month) with a varying `-statement` / `-summary`
suffix, so the listing's hrefs are extracted directly rather than
reconstructed. Each PDF is paired to its nearest preceding landing-page
href in document order.

Crawler shape: **Shape B — index HTML listing, slug-keyed** (single GET,
regex over hrefs; date parsed from the PDF filename, not a date cell).

Reachability (probed 2026-06-22): 200 OK / ~98 KB over plain HTTPS. The PDF
under `/publications/files/` and `/monetarypolicy/files/` both 200 with
application/pdf. plain httpx, no Playwright.
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
MPR_URL = f"{FED_BASE}/monetarypolicy/publications/mpr_default.htm"

# Full-report PDF: {YYYYMMDD}_mprfullreport.pdf (under /publications/files/
# OR /monetarypolicy/files/). Capture the full href + the date.
_MPR_PDF_RE = re.compile(
    r'href="(/[a-z/]*files/(\d{8})_mprfullreport\.pdf)"', re.I
)
# Landing page: /monetarypolicy/{YYYY}-{MM}-mpr-(statement|summary).htm
_MPR_HTML_RE = re.compile(
    r'href="(/monetarypolicy/(\d{4})-(\d{2})-mpr-(?:statement|summary)\.htm)"', re.I
)


def _date_from_slug(yyyymmdd: str) -> date | None:
    try:
        return date(int(yyyymmdd[:4]), int(yyyymmdd[4:6]), int(yyyymmdd[6:8]))
    except ValueError:
        return None


def _parse_listing(html: str) -> list[FilingItem]:
    # Map (year, month) -> landing-page URL for pairing with the PDF.
    html_by_ym: dict[tuple[str, str], str] = {}
    for m in _MPR_HTML_RE.finditer(html):
        href, yyyy, mm = m.group(1), m.group(2), m.group(3)
        html_by_ym.setdefault((yyyy, mm), FED_BASE + href)

    items: list[FilingItem] = []
    seen: set[str] = set()
    for m in _MPR_PDF_RE.finditer(html):
        href, yyyymmdd = m.group(1), m.group(2)
        d = _date_from_slug(yyyymmdd)
        if d is None or yyyymmdd in seen:
            continue
        seen.add(yyyymmdd)
        pdf_url = FED_BASE + href
        landing = html_by_ym.get((yyyymmdd[:4], yyyymmdd[4:6]))
        items.append(FilingItem(
            vendor_code="fed",
            title=f"Monetary Policy Report - {d.isoformat()}",
            publish_date=d,
            source_url=landing or pdf_url,   # prefer HTML landing; fall back to PDF
            pdf_url=pdf_url,
            doc_type="report",
            stream="monetary_policy_report",
            extras={"release_date": d.isoformat()},
        ))
    items.sort(key=lambda it: it.publish_date, reverse=True)
    return items


def discover(*, save_raw_html: bool = True) -> FetchResult:
    with make_session() as sess:
        try:
            r = patient_get(sess, MPR_URL)
        except RuntimeError as exc:
            return FetchResult(vendor_code="fed", ok=False, error=str(exc))
    if save_raw_html:
        save_raw("monetary_policy_report", "mpr_default.htm", r.text)
    items = _parse_listing(r.text)
    return FetchResult(
        vendor_code="fed",
        ok=True,
        items=items,
        note=f"{len(items)} MPR reports (mprfullreport pattern) parsed from MPR listing",
    )


def _print_summary(res: FetchResult) -> None:
    print(f"monetary_policy_report  ok={res.ok}  items={len(res.items)}  err={res.error}")
    print(f"  note: {res.note}")
    for it in res.items[:10]:
        print(f"  {it.publish_date}  [{it.doc_type:7}] {it.title}")
        print(f"             html: {it.source_url}")
        print(f"             pdf : {it.pdf_url}")


if __name__ == "__main__":
    _print_summary(discover())
