"""FSS (Korea Financial Supervisory Service) — press releases.

Recipe (proven 2026-06-09): server-rendered egov BBS at
https://www.fss.or.kr/eng/bbs/B0000211/list.do?menuNo=400010

Table rows: industry, type, title (anchor with nttId), date (YYYY-MM-DD),
file indicator. Detail URL pattern: /eng/bbs/B0000211/view.do?nttId=N&menuNo=400010
PDF download (from detail page): /eng/cmmn/file/fileDown.do?menuNo=…&atchFileId=…&fileSn=N
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

FSS_LIST_URL = "https://www.fss.or.kr/eng/bbs/B0000211/list.do?menuNo=400010&pageIndex={page}"
FSS_BASE = "https://www.fss.or.kr"


def _parse_date(s: str) -> date | None:
    s = (s or "").strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%Y.%m.%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _refine_doc_type(title: str) -> str:
    t = title.lower()
    if "press briefing" in t or "fss chairman" in t:
        return "release"
    if "household loans" in t or "capital ratios" in t or "earnings" in t:
        return "report"
    if "review" in t and ("stability" in t or "risk" in t):
        return "review"
    return "release"


def _parse_row(tr) -> FilingItem | None:
    tds = tr.find_all("td")
    if len(tds) < 4:
        return None
    title_td = tr.find("td", class_="title")
    if not title_td:
        return None
    a = title_td.find("a", href=True)
    if not a:
        return None
    href = str(a.get("href") or "")
    title = re.sub(r"\s+", " ", a.get_text(" ")).strip()
    m_ntt = re.search(r"nttId=(\d+)", href)
    if not m_ntt or not title:
        return None
    # Date is the td with no class and a YYYY-MM-DD pattern
    publish_date = None
    industry_label = ""
    type_label = ""
    cate_spans = tr.find_all("span", class_="cate")
    if len(cate_spans) >= 1:
        industry_label = re.sub(r"\s+", " ", cate_spans[0].get_text(" ")).strip()
    if len(cate_spans) >= 2:
        type_label = re.sub(r"\s+", " ", cate_spans[1].get_text(" ")).strip()
    for td in tds:
        txt = re.sub(r"\s+", " ", td.get_text(" ")).strip()
        d = _parse_date(txt)
        if d is not None:
            publish_date = d
            break
    if publish_date is None:
        return None
    return FilingItem(
        vendor_code="fss",
        title=title,
        publish_date=publish_date,
        source_url=FSS_BASE + href if href.startswith("/") else href,
        pdf_url=None,
        doc_type=_refine_doc_type(title),
        stream="fss_press_releases",
        extras={
            "nttId": m_ntt.group(1),
            "industry": industry_label,
            "type": type_label,
        },
    )


def discover(*, pages: int = 2) -> FetchResult:
    sess = make_session()
    items: list[FilingItem] = []
    for page in range(1, pages + 1):
        try:
            r = patient_get(sess, FSS_LIST_URL.format(page=page))
        except RuntimeError as exc:
            return FetchResult(vendor_code="fss", ok=False, error=str(exc))
        soup = BeautifulSoup(r.text, "html.parser")
        for tr in soup.select("tbody tr"):
            it = _parse_row(tr)
            if it is not None:
                items.append(it)
    return FetchResult(vendor_code="fss", ok=True, items=items, note=f"{pages} page(s)")


if __name__ == "__main__":
    res = discover()
    print(f"fss ok={res.ok} items={len(res.items)} err={res.error}")
    for it in res.items[:10]:
        print(f"  {it.publish_date}  [{it.doc_type:8}] {it.extras.get('industry','?')[:20]:20}  {it.title[:100]}")
