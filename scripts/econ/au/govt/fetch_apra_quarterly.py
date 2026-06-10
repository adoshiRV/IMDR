"""APRA — quarterly performance statistics discovery.

Sources:
  - ADI Performance:
        https://www.apra.gov.au/quarterly-authorised-deposit-taking-institution-statistics
  - GI Performance:
        https://www.apra.gov.au/quarterly-general-insurance-performance-statistics

APRA publishes quarterly bank-sector (ADI) and insurance-sector (GI)
performance statistics. The ADI Performance page also hosts the property
exposures XLSX (no separate page for that — verified 2026-06-10).

Each stats page carries a `<time datetime="...">` element marking the
release date of the latest quarterly update, plus the actual XLSX
download links. We emit ONE FilingItem per stats page per release; the
XLSX URL goes in `extras` since the FilingItem schema only carries a
single optional `pdf_url`.

Reachability (probed 2026-06-10): 200 OK over plain HTTPS. PDF + XLSX
downloads at `apra.gov.au/sites/default/files/*` confirmed working —
NOT subject to the corp firewall block that affects AOFM.
"""
from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _http import make_session, patient_get  # noqa: E402
from _models import FetchResult, FilingItem  # noqa: E402


APRA_BASE = "https://www.apra.gov.au"

_STREAMS = [
    {
        "stream": "apra_adi_performance",
        "url": "https://www.apra.gov.au/quarterly-authorised-deposit-taking-institution-statistics",
        "title": "Quarterly Authorised Deposit-taking Institution Performance Statistics",
        "xlsx_label_hint": "performance",   # filter XLSX anchor text
    },
    {
        "stream": "apra_gi_performance",
        "url": "https://www.apra.gov.au/quarterly-general-insurance-performance-statistics",
        "title": "Quarterly General Insurance Performance Statistics",
        "xlsx_label_hint": "performance statistics database",
    },
]


def _parse_page(html: str, page_url: str, label_hint: str) -> tuple[date | None, str | None]:
    """Return (page release date, primary XLSX url) for one APRA stats page."""
    from bs4 import BeautifulSoup  # type: ignore

    soup = BeautifulSoup(html, "html.parser")

    # Page release date — first <time datetime="..."> we find
    page_date: date | None = None
    time_el = soup.find("time")
    if time_el is not None:
        iso = time_el.get("datetime") or ""
        m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", iso)
        if m:
            try:
                page_date = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            except ValueError:
                pass

    # Primary XLSX — the first XLSX whose anchor text matches the hint AND
    # does NOT contain "historical" / "specifications" / "glossary".
    primary_xlsx: str | None = None
    for a in soup.find_all("a", href=re.compile(r"\.xlsx", re.I)):
        href = a.get("href", "")
        text = a.get_text(" ", strip=True).lower()
        if label_hint not in text:
            continue
        if any(skip in text for skip in ("historical", "specifications", "glossary")):
            continue
        primary_xlsx = href if href.startswith("http") else APRA_BASE + href
        break
    return page_date, primary_xlsx


def discover() -> FetchResult:
    items: list[FilingItem] = []
    errors: list[str] = []
    notes: list[str] = []
    with make_session() as sess:
        for s in _STREAMS:
            try:
                r = patient_get(sess, s["url"])
            except RuntimeError as exc:
                errors.append(f"{s['stream']}: {exc}")
                continue
            page_date, xlsx_url = _parse_page(r.text, s["url"], s["xlsx_label_hint"])
            if page_date is None:
                errors.append(f"{s['stream']}: no <time> publish date on page")
                continue

            items.append(FilingItem(
                vendor_code="apra",
                title=f"{s['title']} — released {page_date.isoformat()}",
                publish_date=page_date,
                source_url=s["url"],
                pdf_url=None,
                doc_type="report",
                stream=s["stream"],
                extras={"xlsx_url": xlsx_url, "page_release_date": page_date.isoformat()},
            ))
            notes.append(f"{s['stream']}: {page_date}")

    if not items and errors:
        return FetchResult(vendor_code="apra", ok=False, error="; ".join(errors))
    return FetchResult(
        vendor_code="apra",
        ok=True,
        items=items,
        note=", ".join(notes) + (f"  errors=[{'; '.join(errors)}]" if errors else ""),
    )


if __name__ == "__main__":
    res = discover()
    print(f"apra ok={res.ok} items={len(res.items)} err={res.error}")
    for it in res.items:
        print(f"  {it.publish_date}  [{it.doc_type:8}] {it.title[:90]}")
        print(f"    xlsx: {it.extras.get('xlsx_url')}")
