"""RBA — Financial Stability Review (FSR) discovery.

Source: `https://www.rba.gov.au/publications/fsr/`

Semi-annual FSR (Apr + Oct). Covers housing market, household leverage,
business sector resilience, banks' capital, and macro-financial risks.
Complements the RBA D2 credit + E1/E2 balance-sheet data we already load
for cells 4.1 and 4.2.

URL pattern (mirrors SMP layout — same site, same Akamai gate):
    /publications/fsr/{YYYY}/{apr|oct}/

One FilingItem per FSR release. publish_date = first of the month
(per-release detail page carries exact date; deferred to ingest time).
"""
from __future__ import annotations

import re
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _models import FetchResult, FilingItem  # noqa: E402
from _playwright import fetch_rba_html  # noqa: E402

HERE = Path(__file__).resolve().parent
PROFILE = HERE / "profile_rba_fsr"

RBA_BASE = "https://www.rba.gov.au"
RBA_FSR_URL = "https://www.rba.gov.au/publications/fsr/"
_ANCHOR_SELECTOR = "a[href*='/publications/fsr/']"

_FSR_HREF_RE = re.compile(
    r"/publications/fsr/(\d{4})/(apr|oct)/?",
    re.IGNORECASE,
)

_MONTH_TO_NUM = {"apr": 4, "oct": 10}
_MONTH_FULL = {"apr": "April", "oct": "October"}


def _parse_listing_html(html: str) -> list[FilingItem]:
    from bs4 import BeautifulSoup  # type: ignore

    soup = BeautifulSoup(html, "html.parser")
    items: list[FilingItem] = []
    seen_urls: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        m = _FSR_HREF_RE.search(href)
        if not m:
            continue
        year = int(m.group(1))
        mon_slug = m.group(2).lower()
        url = RBA_BASE + f"/publications/fsr/{year}/{mon_slug}/"
        if url in seen_urls:
            continue
        seen_urls.add(url)

        publish_date = date(year, _MONTH_TO_NUM[mon_slug], 1)
        title = f"Financial Stability Review — {_MONTH_FULL[mon_slug]} {year}"

        items.append(FilingItem(
            vendor_code="rba",
            title=title,
            publish_date=publish_date,
            source_url=url,
            pdf_url=None,
            doc_type="report",
            stream="rba_fsr",
            extras={"year": year, "month_slug": mon_slug},
        ))
    return items


def discover(*, since_year: int | None = None) -> FetchResult:
    try:
        html = fetch_rba_html(RBA_FSR_URL, PROFILE, anchor_selector=_ANCHOR_SELECTOR)
    except Exception as exc:  # noqa: BLE001
        return FetchResult(
            vendor_code="rba",
            ok=False,
            error=f"playwright fetch fsr top-level: {type(exc).__name__}: {exc}",
        )

    items = _parse_listing_html(html)
    if since_year is not None:
        items = [it for it in items if it.publish_date.year >= since_year]
    items.sort(key=lambda it: it.publish_date, reverse=True)
    return FetchResult(
        vendor_code="rba",
        ok=True,
        items=items,
        note=f"{len(items)} FSR releases" + (f" (since {since_year})" if since_year else ""),
    )


if __name__ == "__main__":
    res = discover(since_year=datetime.now().year - 2)
    print(f"rba_fsr ok={res.ok} items={len(res.items)} err={res.error}")
    for it in res.items[:20]:
        print(f"  {it.publish_date}  [{it.doc_type:8}] {it.title[:90]}")
