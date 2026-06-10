"""RBA — Statement on Monetary Policy (SMP) discovery.

Source: `https://www.rba.gov.au/publications/smp/`

The SMP is the RBA's quarterly forecast publication (Feb / May / Aug / Nov).
Every revision to GDP / CPI / unemployment forecasts lives here, plus
scenarios, sectoral analysis, international developments. For any rates
view, this is the forecast anchor.

URL pattern (probed 2026-06-10):
    /publications/smp/{YYYY}/{mmm}/    where mmm = feb | may | aug | nov

One FilingItem per SMP release. `publish_date` is approximated as the
first of the month — the per-SMP detail page carries the exact date but
we leave that for the eventual ingest step.

Akamai-gated. Re-uses the Playwright pattern with a fresh
`profile_rba_smp/` per run.
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
PROFILE = HERE / "profile_rba_smp"

RBA_BASE = "https://www.rba.gov.au"
RBA_SMP_URL = "https://www.rba.gov.au/publications/smp/"
_ANCHOR_SELECTOR = "a[href*='/publications/smp/']"

# Per-SMP URL: /publications/smp/2026/may/
_SMP_HREF_RE = re.compile(
    r"/publications/smp/(\d{4})/(feb|may|aug|nov)/?",
    re.IGNORECASE,
)

_MONTH_TO_NUM = {"feb": 2, "may": 5, "aug": 8, "nov": 11}
_MONTH_FULL = {"feb": "February", "may": "May", "aug": "August", "nov": "November"}


def _parse_listing_html(html: str) -> list[FilingItem]:
    from bs4 import BeautifulSoup  # type: ignore

    soup = BeautifulSoup(html, "html.parser")
    items: list[FilingItem] = []
    seen_urls: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        m = _SMP_HREF_RE.search(href)
        if not m:
            continue
        year = int(m.group(1))
        mon_slug = m.group(2).lower()

        # Normalise URL to include trailing slash
        url = RBA_BASE + f"/publications/smp/{year}/{mon_slug}/"
        if url in seen_urls:
            continue
        seen_urls.add(url)

        publish_date = date(year, _MONTH_TO_NUM[mon_slug], 1)
        title = f"Statement on Monetary Policy — {_MONTH_FULL[mon_slug]} {year}"

        items.append(FilingItem(
            vendor_code="rba",
            title=title,
            publish_date=publish_date,
            source_url=url,
            pdf_url=None,
            doc_type="report",
            stream="rba_smp",
            extras={"year": year, "month_slug": mon_slug},
        ))
    return items


def discover(*, since_year: int | None = None) -> FetchResult:
    """Discover all SMP releases visible on the top-level listing.

    Default: returns every SMP since 1997 (the RBA archive goes back that
    far). Use `since_year` to clip to the recent history — desk-relevant
    setups usually only care about the latest 1-2 years.
    """
    try:
        html = fetch_rba_html(RBA_SMP_URL, PROFILE, anchor_selector=_ANCHOR_SELECTOR)
    except Exception as exc:  # noqa: BLE001
        return FetchResult(
            vendor_code="rba",
            ok=False,
            error=f"playwright fetch smp top-level: {type(exc).__name__}: {exc}",
        )

    items = _parse_listing_html(html)
    if since_year is not None:
        items = [it for it in items if it.publish_date.year >= since_year]
    items.sort(key=lambda it: it.publish_date, reverse=True)
    return FetchResult(
        vendor_code="rba",
        ok=True,
        items=items,
        note=f"{len(items)} SMP releases" + (f" (since {since_year})" if since_year else ""),
    )


if __name__ == "__main__":
    # When invoked directly we restrict to the last 3 years for readability.
    res = discover(since_year=datetime.now().year - 2)
    print(f"rba_smp ok={res.ok} items={len(res.items)} err={res.error}")
    for it in res.items[:20]:
        print(f"  {it.publish_date}  [{it.doc_type:8}] {it.title[:90]}")
