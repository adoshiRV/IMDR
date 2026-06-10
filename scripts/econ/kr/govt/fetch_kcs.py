"""Korea Customs Service (KCS) — News + FAQ/Notice boards.

Recipe: egov pattern at
  https://www.customs.go.kr/english/na/ntt/selectNttList.do?mi={mi}&bbsId={bbsId}

Rows are <tr> elements with data-table attributes:
  - data-table="subject" → <a data-id="{nttSn}" data-url="{hash}">title</a>
  - data-table="date"    → YYYY.MM.DD
Detail URL: /english/na/ntt/selectNttInfo.do?mi={mi}&bbsId={bbsId}&nttSn={id}&nttSnUrl={hash}

Multiple boards probed; News (mi=8016/bbsId=1744) was stale to 2024 at the
2026-06-10 audit, FAQ & Notice (mi=11767/bbsId=2740) more active. Both
fetched daily so cadence drift is visible.

10-day trade quick estimates — KCS's highest-value content for macro
trading — are NOT on these boards. They live in the Korean-side
press-release archive. To be added once the Korean-side URL is mapped.
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

KCS_BASE = "https://www.customs.go.kr"
KCS_LIST_URL = (
    "{base}/english/na/ntt/selectNttList.do?mi={mi}&bbsId={bbsId}"
)
# (stream label, mi, bbsId, doc_type)
KCS_BOARDS: list[tuple[str, str, str, str]] = [
    ("kcs_news",         "8016",  "1744", "release"),
    ("kcs_faq_notice",   "11767", "2740", "release"),
]


def _parse_date(s: str) -> date | None:
    s = (s or "").strip()
    if not s:
        return None
    for fmt in ("%Y.%m.%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _parse_row(tr, mi: str, bbs_id: str, stream: str, doc_type: str) -> FilingItem | None:
    subject_td = tr.find("td", attrs={"data-table": "subject"})
    date_td = tr.find("td", attrs={"data-table": "date"})
    if not subject_td or not date_td:
        return None
    a = subject_td.find("a", attrs={"data-id": True})
    if not a:
        return None
    ntt_sn = str(a.get("data-id") or "")
    ntt_sn_url = str(a.get("data-url") or "")
    title = re.sub(r"\s+", " ", a.get_text(" ")).strip()
    if not title or not ntt_sn:
        return None
    publish_date = _parse_date(date_td.get_text(strip=True))
    if publish_date is None:
        return None
    detail = (
        f"{KCS_BASE}/english/na/ntt/selectNttInfo.do?mi={mi}&bbsId={bbs_id}"
        f"&nttSn={ntt_sn}&nttSnUrl={ntt_sn_url}"
    )
    return FilingItem(
        vendor_code="kcs",
        title=title,
        publish_date=publish_date,
        source_url=detail,
        pdf_url=None,
        doc_type=doc_type,
        stream=stream,
        extras={"nttSn": ntt_sn, "nttSnUrl": ntt_sn_url, "mi": mi, "bbsId": bbs_id},
    )


def discover() -> FetchResult:
    sess = make_session()
    items: list[FilingItem] = []
    failed: list[str] = []
    for stream, mi, bbs_id, doc_type in KCS_BOARDS:
        url = KCS_LIST_URL.format(base=KCS_BASE, mi=mi, bbsId=bbs_id)
        try:
            r = patient_get(sess, url)
        except RuntimeError as exc:
            failed.append(f"{stream}: {str(exc)[:80]}")
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        for tr in soup.select("tbody tr"):
            it = _parse_row(tr, mi, bbs_id, stream, doc_type)
            if it is not None:
                items.append(it)
    if failed and not items:
        return FetchResult(vendor_code="kcs", ok=False, error="; ".join(failed))
    note = f"{len(KCS_BOARDS) - len(failed)}/{len(KCS_BOARDS)} boards"
    if failed:
        note += f"  (failed: {', '.join(f.split(':')[0] for f in failed)})"
    return FetchResult(vendor_code="kcs", ok=True, items=items, note=note)


if __name__ == "__main__":
    res = discover()
    print(f"kcs ok={res.ok} items={len(res.items)} note={res.note}")
    for it in res.items[:10]:
        print(f"  {it.publish_date}  [{it.stream:18}] {it.title[:100]}")
