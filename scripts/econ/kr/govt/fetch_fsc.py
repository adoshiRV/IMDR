"""FSC (Korea Financial Services Commission) — press releases.

Recipe (proven 2026-06-10): server-rendered list at
https://www.fsc.go.kr/eng/pr010101

DOM shape:
  <ul class="board-list">
    <li>
      <span class="data">May 25, 2026</span>
      <div class="cont">
        <a href="/eng/pr010101/{id}?…">
          <dl>
            <dt>{title}</dt>
            <dd>{summary}</dd>
          </dl>
        </a>
      </div>
    </li>
  </ul>

TLS-flaky from this network — uses patient_get (10 attempts).
"""
from __future__ import annotations

import re
import sys
from datetime import date, datetime
from pathlib import Path

from bs4 import BeautifulSoup  # type: ignore

sys.path.insert(0, str(Path(__file__).parent))
from _http import make_session, patient_get  # noqa: E402
from _models import FetchResult, FilingItem  # noqa: E402

FSC_LIST_URL = "https://www.fsc.go.kr/eng/pr010101"
FSC_BASE = "https://www.fsc.go.kr"


def _parse_date(s: str) -> date | None:
    s = (s or "").strip()
    if not s:
        return None
    for fmt in ("%b %d, %Y", "%B %d, %Y", "%Y-%m-%d", "%Y.%m.%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _refine_doc_type(title: str) -> str:
    t = title.lower()
    if "household loans" in t or "capital" in t or "ratios" in t:
        return "report"
    if "chairman" in t and ("meets" in t or "visits" in t or "speech" in t):
        return "speech"
    if "review" in t and ("stability" in t or "risk" in t):
        return "review"
    return "release"


def _parse_li(li) -> FilingItem | None:
    date_span = li.find("span", class_="data")
    if not date_span:
        return None
    publish_date = _parse_date(date_span.get_text(strip=True))
    if publish_date is None:
        return None
    a = li.find("a", href=True)
    if not a:
        return None
    href = str(a.get("href") or "")
    dt = a.find("dt")
    if not dt:
        return None
    title = re.sub(r"\s+", " ", dt.get_text(" ")).strip()
    if not title:
        return None
    dd = a.find("dd")
    summary = re.sub(r"\s+", " ", dd.get_text(" ")).strip()[:400] if dd else ""

    m_id = re.search(r"/pr010101/(\d+)", href)
    article_id = m_id.group(1) if m_id else ""

    detail_url = FSC_BASE + href if href.startswith("/") else href
    return FilingItem(
        vendor_code="fsc",
        title=title,
        publish_date=publish_date,
        source_url=detail_url,
        pdf_url=None,
        doc_type=_refine_doc_type(title),
        stream="fsc_press_releases",
        extras={"article_id": article_id, "summary": summary},
    )


def discover(*, pages: int = 1) -> FetchResult:
    sess = make_session()
    items: list[FilingItem] = []
    for page in range(1, pages + 1):
        url = FSC_LIST_URL if page == 1 else f"{FSC_LIST_URL}?curPage={page}"
        try:
            r = patient_get(sess, url)
        except RuntimeError as exc:
            return FetchResult(vendor_code="fsc", ok=False, error=str(exc))
        soup = BeautifulSoup(r.text, "html.parser")
        ul = soup.find("ul", class_="board-list")
        if not ul:
            continue
        for li in ul.find_all("li", recursive=False):
            it = _parse_li(li)
            if it is not None:
                items.append(it)
    return FetchResult(vendor_code="fsc", ok=True, items=items, note=f"{pages} page(s)")


if __name__ == "__main__":
    res = discover()
    print(f"fsc ok={res.ok} items={len(res.items)} err={res.error}")
    for it in res.items[:10]:
        print(f"  {it.publish_date}  [{it.doc_type:8}] {it.title[:120]}")
