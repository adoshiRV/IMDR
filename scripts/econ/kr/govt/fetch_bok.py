"""Bank of Korea — News & Publications discovery (egov POST recipe).

Recipe (proven 2026-06-10 — see memory project_bok_listcont_post_recipe):
  POST https://www.bok.or.kr/eng/singl/newsDataEng/listCont.do
  Form: pageIndex, targetDepth='', menuNo, syncMenuChekKey=1,
        searchCnd=1, searchKwd='', date/sdate/edate='',
        sort=1, pageUnit=10
  Headers: Referer + X-Requested-With: XMLHttpRequest

Returns 10 items/page as <li class="bbsRowCls">…</li> rows with
<span class="t1"> category, <span class="date">YYYY.MM.DD, and a
<a class="title" href="…?nttId=N&menuNo=…">title</a>.

We hit menuNo=400007 (top "News & Publications") which fans across
every BoK stream and tag each item with its category from t1.
"""
from __future__ import annotations

import re
import sys
from datetime import date, datetime
from pathlib import Path

from bs4 import BeautifulSoup  # type: ignore

sys.path.insert(0, str(Path(__file__).parent))
from _http import make_session, patient_post  # noqa: E402
from _models import FetchResult, FilingItem  # noqa: E402

BOK_LIST_URL = "https://www.bok.or.kr/eng/singl/newsDataEng/listCont.do"
BOK_BASE = "https://www.bok.or.kr"

# menuNo selects which BoK landing the listCont.do endpoint emits items
# for. Probed 2026-06-11 (playground/econ/kr_govt_docs/probe_backfill_depth.py):
#   400007 (top news) caps server-side at ~250 items / ~7 months
#   400215 (MPR), 400219 (FSR), 400221 (Annual), 400067 (Working Papers),
#   400409 (Issue Notes), 400403 (Open Market Operations), 400423 (Press
#   Releases) each return the SAME 5000-item firehose going back to
#   2011-09-08 — menuNo on these isn't actually filtering server-side.
# We use 400423 (Press Releases) for the full firehose; falling back to
# any other working menuNo would return identical content.
BOK_MENU_NO = "400423"
BOK_REFERER = f"https://www.bok.or.kr/eng/singl/newsDataEng/list.do?menuNo={BOK_MENU_NO}"

# Map BoK's <span class="t1"> category label → our doc_type taxonomy.
# Unknown categories fall back to 'release'.
_T1_TO_DOCTYPE = {
    "press releases": "release",
    "bok issue note": "report",
    "open market operations": "release",
    "monetary policy report": "report",
    "financial stability report": "report",
    "annual report": "report",
    "speech": "speech",
    "working paper": "report",
    "discussion paper": "report",
    "minutes of the monetary policy board meeting": "minutes",
    "economic outlook": "outlook",
    "korea economic outlook": "outlook",
    "recent economic developments": "report",
    "notice": "release",
}


def _parse_bok_date(s: str) -> date | None:
    s = (s or "").strip()
    if not s:
        return None
    for fmt in ("%Y.%m.%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _stream_from_menu_no(menu_no: str) -> str:
    # Best-effort menuNo → stream label. Full catalogue lives in
    # docs/admin/econ/korea/govt_doc_sources.md §Cluster B.
    return {
        "400069": "bok_news",
        "400215": "bok_monetary_policy_report",
        "400219": "bok_financial_stability_report",
        "400067": "bok_working_papers",
        "400221": "bok_annual_report",
        "400403": "bok_open_market_operations",
        "400409": "bok_issue_notes",
        "400411": "bok_cbdc",
        "400423": "bok_press_releases",
    }.get(menu_no, f"bok_menu_{menu_no}")


def _refine_doc_type(title: str, t1: str) -> str | None:
    """Override the t1-category-based doc_type when the title is more specific.

    BoK's Press Releases board (menuNo=400423) is heterogenous — Monetary
    Policy Decisions, GDP releases, BoP, FX reserves, etc. all live under
    the same 't1' label. Use title cues to upgrade specific items.
    """
    t = title.lower()
    if "monetary policy decision" in t:
        return "decision"
    if "opening remarks" in t and "press conference" in t:
        return "decision"
    if "minutes of the monetary policy" in t:
        return "minutes"
    if "economic outlook" in t and "report" not in t:
        return "outlook"
    if "financial stability report" in t:
        return "report"
    if "speech by" in t or "remarks by" in t:
        return "speech"
    return None


def _parse_row(li_html: str) -> FilingItem | None:
    soup = BeautifulSoup(li_html, "html.parser")
    title_a = soup.find("a", class_="title")
    if not title_a:
        return None
    title = re.sub(r"\s+", " ", title_a.get_text(" ")).strip()
    href = str(title_a.get("href") or "")
    if not title or not href:
        return None
    m_ntt = re.search(r"nttId=(\d+)", href)
    if not m_ntt:
        return None
    m_menu = re.search(r"menuNo=(\d+)", href)
    menu_no = m_menu.group(1) if m_menu else ""

    date_span = soup.find("span", class_="date")
    publish_date = _parse_bok_date(date_span.get_text() if date_span else "")
    if publish_date is None:
        return None

    t1_span = soup.find("span", class_="t1")
    category = (t1_span.get_text(strip=True) if t1_span else "").lower()
    doc_type = _refine_doc_type(title, category) or _T1_TO_DOCTYPE.get(category, "release")

    detail_url = BOK_BASE + href if href.startswith("/") else href
    return FilingItem(
        vendor_code="bok",
        title=title,
        publish_date=publish_date,
        source_url=detail_url,
        pdf_url=None,   # resolved later at ingest time via view.do scrape
        doc_type=doc_type,
        stream=_stream_from_menu_no(menu_no),
        extras={
            "nttId": m_ntt.group(1),
            "menuNo": menu_no,
            "t1_category": category,
        },
    )


def discover(*, pages: int = 2) -> FetchResult:
    """Pull the latest ``pages`` × 10 items from BoK News & Publications.

    Default pages=2 (20 items) is enough headroom for the daily run —
    BoK rarely publishes more than 5 items per business day across all
    streams combined.
    """
    sess = make_session()
    items: list[FilingItem] = []
    for page in range(1, pages + 1):
        form = {
            "pageIndex": str(page),
            "targetDepth": "",
            "menuNo": BOK_MENU_NO,
            "syncMenuChekKey": "1",
            "searchCnd": "1",
            "searchKwd": "",
            "date": "",
            "sdate": "",
            "edate": "",
            "sort": "1",
            "pageUnit": "10",
        }
        try:
            r = patient_post(
                sess,
                BOK_LIST_URL,
                data=form,
                headers={"Referer": BOK_REFERER, "X-Requested-With": "XMLHttpRequest"},
            )
        except RuntimeError as exc:
            return FetchResult(vendor_code="bok", ok=False, error=str(exc))

        for m in re.finditer(r"<li class=\"bbsRowCls\">.*?</li>", r.text, re.S):
            it = _parse_row(m.group(0))
            if it is not None:
                items.append(it)
    return FetchResult(vendor_code="bok", ok=True, items=items, note=f"{pages} page(s) × 10/page")


if __name__ == "__main__":
    res = discover()
    print(f"bok ok={res.ok} items={len(res.items)} err={res.error}")
    for it in res.items[:15]:
        print(f"  {it.publish_date}  [{it.doc_type:8}] {it.stream:30}  {it.title[:100]}")
