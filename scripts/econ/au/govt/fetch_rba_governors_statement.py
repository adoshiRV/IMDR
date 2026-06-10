"""RBA — Governor's Statement (Monetary Policy Decision) discovery.

Source: `https://www.rba.gov.au/monetary-policy/int-rate-decisions/{YYYY}/`

The RBA Board issues a Governor's Statement after each cash-rate meeting
(~8 per year, T+0). The decision-year listing page is the navigation
entry point but the actual detail pages live under the media-releases
namespace:
    /media-releases/{YYYY}/mr-{YY}-{NN}.html

Both index and detail pages are Akamai-gated (HTTP 403 to plain
`httpx`/`requests`; probed 2026-06-10 — error references
`errors.edgesuite.net`). Same gating layer as the RBA statistical
tables — re-uses the persistent-profile Playwright pattern from
`playground/econ/rba/fetch_d2_e_tables.py`.

Discovery only — no PDF/HTML fetch. The orchestrator writes FilingItems
to `data/snapshots/{date}.json`; the research-doc pipeline will fetch
the body when it absorbs filings.
"""
from __future__ import annotations

import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _models import FetchResult, FilingItem  # noqa: E402
from _playwright import extract_date, fetch_rba_html  # noqa: E402

HERE = Path(__file__).resolve().parent
PROFILE = HERE / "profile_rba_gov"

RBA_BASE = "https://www.rba.gov.au"
RBA_DECISIONS_URL = "https://www.rba.gov.au/monetary-policy/int-rate-decisions/{year}/"
_ANCHOR_SELECTOR = "a[href*='/media-releases/']"

# Per-decision URL pattern: /media-releases/2026/mr-26-12.html
_DECISION_HREF_RE = re.compile(
    r"/media-releases/(\d{4})/(mr-\d{2}-\d{2}\.html)",
    re.IGNORECASE,
)


def _parse_listing_html(html: str, year: int) -> list[FilingItem]:
    """Extract decisions from one year's listing page.

    The RBA listing renders each decision as a table row with an `<a>`
    to the detail page; the link text or surrounding cell carries the
    meeting date (e.g. "13 May 2026"). We parse via BeautifulSoup so
    layout tweaks don't break us.
    """
    from bs4 import BeautifulSoup  # type: ignore

    soup = BeautifulSoup(html, "html.parser")
    items: list[FilingItem] = []
    seen_urls: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        m = _DECISION_HREF_RE.search(href)
        if not m:
            continue
        url = href if href.startswith("http") else RBA_BASE + href
        if url in seen_urls:
            continue
        seen_urls.add(url)

        link_text = re.sub(r"\s+", " ", a.get_text(" ")).strip()
        # Date may live in the link text or in a sibling cell. Try the link
        # text first; fall back to the enclosing <tr>.
        publish_date = extract_date(link_text)
        if publish_date is None:
            tr = a.find_parent("tr")
            if tr is not None:
                publish_date = extract_date(tr.get_text(" "))
        if publish_date is None:
            continue

        title = link_text or f"Monetary Policy Decision — {publish_date.isoformat()}"
        # If the link text is just a date, expand the title for readability.
        if re.fullmatch(r"\d{1,2}\s+\w+\s+\d{4}", title or ""):
            title = f"Monetary Policy Decision — {title}"

        items.append(FilingItem(
            vendor_code="rba",
            title=title,
            publish_date=publish_date,
            source_url=url,
            pdf_url=None,
            doc_type="decision",
            stream="rba_governors_statement",
            extras={"year": year, "filename": m.group(2)},
        ))
    return items


def discover(*, years: list[int] | None = None) -> FetchResult:
    """Pull the listing for the requested years (default: current year).

    Returns FetchResult with one FilingItem per decision found. The
    orchestrator dedups against rolling seen.json so re-runs are idempotent.
    """
    if years is None:
        years = [datetime.now().year]

    items: list[FilingItem] = []
    notes: list[str] = []
    for year in years:
        try:
            html = fetch_rba_html(
                RBA_DECISIONS_URL.format(year=year),
                PROFILE,
                anchor_selector=_ANCHOR_SELECTOR,
            )
        except Exception as exc:  # noqa: BLE001
            return FetchResult(
                vendor_code="rba",
                ok=False,
                error=f"playwright fetch {year}: {type(exc).__name__}: {exc}",
            )
        year_items = _parse_listing_html(html, year)
        items.extend(year_items)
        notes.append(f"{year}: {len(year_items)}")
    return FetchResult(
        vendor_code="rba",
        ok=True,
        items=items,
        note="years " + ", ".join(notes),
    )


if __name__ == "__main__":
    res = discover()
    print(f"rba_governors_statement ok={res.ok} items={len(res.items)} err={res.error}")
    for it in res.items[:20]:
        print(f"  {it.publish_date}  [{it.doc_type:8}] {it.title[:90]}")
