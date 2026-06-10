"""RBA — Board Minutes discovery.

Source: `https://www.rba.gov.au/monetary-policy/rba-board-minutes/{YYYY}/`

The RBA publishes Board Minutes T+14 after each cash-rate meeting (~8/yr).
The minutes give the detailed account of the deliberation — voting, scenarios,
staff briefings, forward-guidance hints — which the T+0 Governor's Statement
condenses to a few paragraphs. For a rates desk, minutes are higher-signal
than the decision itself.

URL pattern (probed 2026-06-10):
    /monetary-policy/rba-board-minutes/{YYYY}/{YYYY-MM-DD}.html

The date IS the filename — no need to parse cell text. Future-dated
placeholder entries are HTML-commented out on the listing page, so
BeautifulSoup's default comment-stripping behaviour drops them naturally.

Akamai-gated, same as Governor's Statement. Re-uses the persistent-profile
Playwright pattern (fresh `profile_rba_minutes/` per run).
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
PROFILE = HERE / "profile_rba_minutes"

RBA_BASE = "https://www.rba.gov.au"
RBA_MINUTES_URL = "https://www.rba.gov.au/monetary-policy/rba-board-minutes/{year}/"
_ANCHOR_SELECTOR = "a[href*='/monetary-policy/rba-board-minutes/']"

# Per-minutes URL: /monetary-policy/rba-board-minutes/2026/2026-05-05.html
_MINUTES_HREF_RE = re.compile(
    r"/monetary-policy/rba-board-minutes/(\d{4})/(\d{4}-\d{2}-\d{2})\.html",
    re.IGNORECASE,
)


def _parse_listing_html(html: str, year: int) -> list[FilingItem]:
    from bs4 import BeautifulSoup  # type: ignore

    soup = BeautifulSoup(html, "html.parser")
    items: list[FilingItem] = []
    seen_urls: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        m = _MINUTES_HREF_RE.search(href)
        if not m:
            continue
        # Skip the index page itself.
        if href.endswith("/index.html"):
            continue
        url = href if href.startswith("http") else RBA_BASE + href
        if url in seen_urls:
            continue
        seen_urls.add(url)

        try:
            publish_date = date.fromisoformat(m.group(2))
        except ValueError:
            continue

        link_text = re.sub(r"\s+", " ", a.get_text(" ")).strip()
        title = f"Minutes of the Monetary Policy Board Meeting — {link_text or publish_date.isoformat()}"

        items.append(FilingItem(
            vendor_code="rba",
            title=title,
            publish_date=publish_date,
            source_url=url,
            pdf_url=None,
            doc_type="minutes",
            stream="rba_board_minutes",
            extras={"year": year, "filename": m.group(2) + ".html"},
        ))
    return items


def discover(*, years: list[int] | None = None) -> FetchResult:
    if years is None:
        years = [datetime.now().year]

    items: list[FilingItem] = []
    notes: list[str] = []
    for year in years:
        try:
            html = fetch_rba_html(
                RBA_MINUTES_URL.format(year=year),
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
    print(f"rba_board_minutes ok={res.ok} items={len(res.items)} err={res.error}")
    for it in res.items[:20]:
        print(f"  {it.publish_date}  [{it.doc_type:8}] {it.title[:90]}")
