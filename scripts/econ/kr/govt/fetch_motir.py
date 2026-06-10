"""MOTIR (Korea Ministry of Trade, Industry and Resources) — press releases.

Recipe (proven 2026-06-10): server-rendered list at
  https://english.motir.go.kr/eng/article/EATCLdfa319ada

DOM shape per item (one <li> per article):
  <li>
    <a href="javascript:article.view('{articleId}', '{type}');">
      <div class="item">
        <strong class="title">{title}</strong>
        <p class="info">
          <span class="cont">{summary}</span>
          <span class="date"><i>date</i>YYYY-MM-DD</span>
        </p>
      </div>
    </a>
  </li>

NOTE: MOTIR (Ministry of Trade, Industry and Resources) is the renamed
MOTIE (...and Energy). Hostname is motir.go.kr (with 'r'), not motie.
See memory: project_motie_renamed_to_motir.md.

The 'EATCLdfa319ada' category hash is opaque — it identifies the
"Press Releases" category. Other category hashes (announcement, FTA, etc.)
exist but were not enumerated in the 2026-06-10 probe.
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

MOTIR_PRESS_CATEGORY = "EATCLdfa319ada"
MOTIR_LIST_URL = (
    f"https://english.motir.go.kr/eng/article/{MOTIR_PRESS_CATEGORY}?pageIndex={{page}}&bbsCdN=2"
)
MOTIR_BASE = "https://english.motir.go.kr"


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


def _parse_li(li) -> FilingItem | None:
    a = li.find("a", href=True)
    if not a:
        return None
    href = str(a.get("href") or "")
    m = re.search(r"article\.view\('(\d+)',\s*'(\d+)'\)", href)
    if not m:
        return None
    article_id = m.group(1)
    article_type = m.group(2)

    title_tag = li.find("strong", class_="title")
    if not title_tag:
        return None
    title = re.sub(r"\s+", " ", title_tag.get_text(" ")).strip()
    if not title:
        return None

    date_span = li.find("span", class_="date")
    publish_date = None
    if date_span:
        # remove the <i>date</i> prefix label
        for i_tag in date_span.find_all("i"):
            i_tag.decompose()
        publish_date = _parse_date(date_span.get_text(strip=True))
    if publish_date is None:
        return None

    summary_span = li.find("span", class_="cont")
    summary = re.sub(r"\s+", " ", summary_span.get_text(" "))[:400].strip() if summary_span else ""

    # Best-guess detail URL — actual form needs runtime verification at
    # ingest time. The /eng/article/{category}/{id} pattern matches the
    # form action and the click-handler routing.
    detail_url = f"{MOTIR_BASE}/eng/article/{MOTIR_PRESS_CATEGORY}/{article_id}"

    return FilingItem(
        vendor_code="motir",
        title=title,
        publish_date=publish_date,
        source_url=detail_url,
        pdf_url=None,
        doc_type="release",
        stream="motir_press_releases",
        extras={
            "article_id": article_id,
            "article_type": article_type,
            "category_hash": MOTIR_PRESS_CATEGORY,
            "summary": summary,
        },
    )


def discover(*, pages: int = 1) -> FetchResult:
    sess = make_session()
    items: list[FilingItem] = []
    for page in range(1, pages + 1):
        try:
            r = patient_get(sess, MOTIR_LIST_URL.format(page=page))
        except RuntimeError as exc:
            return FetchResult(vendor_code="motir", ok=False, error=str(exc))
        soup = BeautifulSoup(r.text, "html.parser")
        for li in soup.select("div.board-list li, .board-list li"):
            it = _parse_li(li)
            if it is not None:
                items.append(it)
    return FetchResult(vendor_code="motir", ok=True, items=items, note=f"{pages} page(s)")


if __name__ == "__main__":
    res = discover()
    print(f"motir ok={res.ok} items={len(res.items)} err={res.error}")
    for it in res.items[:10]:
        print(f"  {it.publish_date}  [{it.doc_type:8}] {it.title[:110]}")
