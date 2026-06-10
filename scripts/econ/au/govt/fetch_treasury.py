"""Treasury (Department of the Treasury) — publications discovery.

Source: `https://treasury.gov.au/publication`

The Treasury publications listing is a Drupal-rendered page with 10
most-recent publications per page. Every entry is a `<div class="views-row">`
containing a title link to `/publication/p{NUMERIC_ID}` and a
`<time datetime="...">` with the ISO publish date.

Reachability (probed 2026-06-10): 200 OK over plain HTTPS. No Akamai, no
corp-firewall block. Uses `_http.py` not `_playwright.py`.

Discovery is broad — captures every publication type (Budget Papers,
MYEFO, PEFO, IGR, Treasury Round-Up, Senate responses, etc.). Downstream
filtering can prioritise by title keyword when the research-doc pipeline
absorbs filings; for now the manifest carries everything.
"""
from __future__ import annotations

import re
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _http import make_session, patient_get  # noqa: E402
from _models import FetchResult, FilingItem  # noqa: E402

TREASURY_BASE = "https://treasury.gov.au"
TREASURY_LIST_URL = "https://treasury.gov.au/publication"
TREASURY_LIST_PAGE_URL = "https://treasury.gov.au/publication?page={page}"

# Match numeric publication slugs: /publication/p2026-775765
_PUB_HREF_RE = re.compile(r"^/publication/p\d{4}-\d+$")


def _parse_listing_html(html: str) -> list[FilingItem]:
    from bs4 import BeautifulSoup  # type: ignore

    soup = BeautifulSoup(html, "html.parser")
    items: list[FilingItem] = []
    seen_urls: set[str] = set()

    for row in soup.find_all("div", class_=re.compile(r"\bviews-row\b")):
        title_block = row.find("div", class_=re.compile(r"field--name-node-title"))
        title_a = title_block.find("a", href=_PUB_HREF_RE) if title_block else None
        if not title_a:
            continue

        href = title_a.get("href") or ""
        url = TREASURY_BASE + href if href.startswith("/") else href
        if url in seen_urls:
            continue
        seen_urls.add(url)

        title = re.sub(r"\s+", " ", title_a.get_text(" ")).strip()
        if not title:
            continue

        time_el = row.find("time")
        publish_date = _parse_time_attr(time_el)
        if publish_date is None:
            continue

        items.append(FilingItem(
            vendor_code="treasury_au",
            title=title,
            publish_date=publish_date,
            source_url=url,
            pdf_url=None,
            doc_type=_classify_doc_type(title),
            stream="treasury_publications",
            extras={"pub_slug": href.rsplit("/", 1)[-1]},
        ))
    return items


def _parse_time_attr(time_el) -> date | None:
    if time_el is None:
        return None
    iso = time_el.get("datetime") or ""
    # ISO format: "2026-06-04T12:00:00Z"
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", iso)
    if not m:
        # Fall back to the visible text "04 June 2026"
        from _playwright import extract_date  # noqa: E402
        return extract_date(time_el.get_text(strip=True))
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def _classify_doc_type(title: str) -> str:
    """Coarse doc_type classifier from title keywords.

    Match the FilingItem taxonomy: release / minutes / report / outlook /
    speech / decision / review. Macro-fiscal items get `report`; the rest
    default to `release`.
    """
    low = title.lower()
    if "budget paper" in low or "budget statement" in low or "budget overview" in low:
        return "report"
    if "myefo" in low or "mid-year economic" in low:
        return "report"
    if "pefo" in low or "pre-election economic" in low:
        return "report"
    if "final budget outcome" in low:
        return "report"
    if "intergenerational report" in low:
        return "report"
    if "round-up" in low or "research paper" in low or "working paper" in low:
        return "report"
    return "release"


def discover(*, pages: int = 2) -> FetchResult:
    """Pull the first ``pages`` × 10 publications from Treasury.

    Default 2 pages = 20 publications covers ~1-2 weeks of activity. The
    orchestrator dedups against rolling seen.json so re-runs are idempotent.
    """
    items: list[FilingItem] = []
    with make_session() as sess:
        for page in range(pages):
            url = TREASURY_LIST_URL if page == 0 else TREASURY_LIST_PAGE_URL.format(page=page)
            try:
                r = patient_get(sess, url)
            except RuntimeError as exc:
                return FetchResult(vendor_code="treasury_au", ok=False, error=str(exc))
            page_items = _parse_listing_html(r.text)
            items.extend(page_items)
    # Dedup across pages by source_url
    seen_urls: set[str] = set()
    deduped: list[FilingItem] = []
    for it in items:
        if it.source_url in seen_urls:
            continue
        seen_urls.add(it.source_url)
        deduped.append(it)
    return FetchResult(
        vendor_code="treasury_au",
        ok=True,
        items=deduped,
        note=f"{pages} page(s) × 10 publications",
    )


if __name__ == "__main__":
    res = discover()
    print(f"treasury ok={res.ok} items={len(res.items)} err={res.error}")
    for it in res.items[:20]:
        print(f"  {it.publish_date}  [{it.doc_type:8}] {it.title[:90]}")
