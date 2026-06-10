"""KDI (Korea Development Institute) — featured publications.

Recipe (proven 2026-06-10): server-rendered featured cards on
  https://www.kdi.re.kr/eng/research/{monTrends,economy,monEb}

Each card is an `<a href="/eng/research/{type}?pub_no={id}">` containing:
  <b class="iNN">{category}</b>
  <strong>{title}</strong>
  <p>{abstract}</p>
  <span>{Month DD, YYYY}</span>

The full back-issue archive is JS-rendered (SPA) — featured cards only
surface the most recent ~3 highlighted pubs per landing. That's sufficient
for daily monitoring; the orchestrator's seen.json dedup catches anything
already ingested, and back-fill of historical issues is a separate
one-time concern.

URL family for detail pages — keyed by pub_no:
  /eng/research/economy?pub_no=...      (Economic Outlook)
  /eng/research/focusView?pub_no=...    (KDI FOCUS)
  /eng/research/monTrends?pub_no=...    (Monthly Trends)
  /eng/research/monEbView?pub_no=...    (Economic Bulletin)
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

KDI_BASE = "https://www.kdi.re.kr"
KDI_LANDING_URLS = [
    f"{KDI_BASE}/eng/research/monTrends",   # Monthly Economic Trends
    f"{KDI_BASE}/eng/research/economy",     # Economic Outlook
    f"{KDI_BASE}/eng/research/monEb",       # Economic Bulletin
]


def _parse_date(s: str) -> date | None:
    s = (s or "").strip()
    if not s:
        return None
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%Y-%m-%d", "%Y.%m.%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _category_to_doctype(category: str) -> str:
    c = (category or "").lower()
    if "outlook" in c:
        return "outlook"
    if "focus" in c or "policy study" in c:
        return "report"
    if "trends" in c or "bulletin" in c:
        return "report"
    return "report"


def _stream_from_href(href: str) -> str:
    if "economy?" in href:
        return "kdi_economic_outlook"
    if "focusView" in href:
        return "kdi_focus"
    if "monTrends" in href:
        return "kdi_monthly_trends"
    if "monEb" in href:
        return "kdi_economic_bulletin"
    return "kdi_other"


def _parse_landing(html: str, seen_pub_nos: set[str]) -> list[FilingItem]:
    items: list[FilingItem] = []
    for m in re.finditer(r'<a\s+href="([^"]+pub_no=\d+)"[^>]*>(.{50,1500}?)</a>', html, re.S):
        href = m.group(1)
        inner = m.group(2)
        pub_no_m = re.search(r"pub_no=(\d+)", href)
        if not pub_no_m:
            continue
        pub_no = pub_no_m.group(1)
        if pub_no in seen_pub_nos:
            continue   # dedup across the 3 landings
        seen_pub_nos.add(pub_no)

        title_m = re.search(r"<strong>([^<]+)</strong>", inner)
        date_m = re.search(r"<span>([^<]+)</span>", inner)
        cat_m = re.search(r"<b[^>]*>([^<]+)</b>", inner)
        if not title_m or not date_m:
            continue
        title = re.sub(r"\s+", " ", title_m.group(1)).strip()
        publish_date = _parse_date(date_m.group(1))
        category = cat_m.group(1).strip() if cat_m else ""
        if not title or publish_date is None:
            continue

        detail_url = KDI_BASE + href if href.startswith("/") else href
        # abstract is the <p> inside, if present
        abs_m = re.search(r"<p[^>]*>([^<]+)</p>", inner)
        abstract = re.sub(r"\s+", " ", abs_m.group(1)).strip()[:400] if abs_m else ""

        items.append(FilingItem(
            vendor_code="kdi",
            title=title,
            publish_date=publish_date,
            source_url=detail_url,
            pdf_url=None,
            doc_type=_category_to_doctype(category),
            stream=_stream_from_href(href),
            extras={"pub_no": pub_no, "category": category, "abstract": abstract},
        ))
    return items


def discover() -> FetchResult:
    sess = make_session()
    items: list[FilingItem] = []
    seen_pub_nos: set[str] = set()
    failed: list[str] = []
    for url in KDI_LANDING_URLS:
        try:
            r = patient_get(sess, url)
        except RuntimeError as exc:
            failed.append(f"{url.rsplit('/', 1)[-1]}: {str(exc)[:80]}")
            continue
        items.extend(_parse_landing(r.text, seen_pub_nos))
    if failed and not items:
        return FetchResult(vendor_code="kdi", ok=False, error="; ".join(failed))
    note = f"{len(KDI_LANDING_URLS) - len(failed)}/{len(KDI_LANDING_URLS)} landings"
    if failed:
        note += f"  (failed: {', '.join(f.split(':')[0] for f in failed)})"
    return FetchResult(vendor_code="kdi", ok=True, items=items, note=note)


if __name__ == "__main__":
    res = discover()
    print(f"kdi ok={res.ok} items={len(res.items)} note={res.note}")
    for it in res.items[:10]:
        print(f"  {it.publish_date}  [{it.doc_type:8}] {it.stream:25} {it.title[:90]}")
