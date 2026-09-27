"""OJK -- Otoritas Jasa Keuangan, the financial-services regulator.

OJK matters to Track B because Indonesia splits its central-bank mandate:
BI owns monetary policy and macroprudential, OJK owns banking/capital-market
supervision and publishes the bank-level data and the sector reports behind
the credit cycle. Its monthly press stream also carries the Dewan Komisioner
(Board of Commissioners) monthly meeting result -- the regulator's nearest
analogue to an RDG.

Transport: server-rendered SharePoint on `ojk.go.id`, plain HTTPS, no gate.
Same CMS family as BI but a DIFFERENT row shape, which is why it does not
reuse `_bi_aspnet`:

    <li class="list-group-item">
      <div class="date"> 9 September 2026 </div>
      <a href="{detail}" class="group-item-title"><strong>{title}</strong></a>
      <div class="caption">{abstract}</div>

Note `ul.list-group` is ALSO the site's left-hand nav, so a naive
`list-group-item` sweep picks up ~370 menu entries per page. Rows are
identified by the presence of an `a.group-item-title`, which the nav items
do not have.

Pagination is the same `DataPager` dead end as BI (see `_bi_aspnet`), so
this is page-1-only: 10 rows, roughly the last week of OJK press.
"""
from __future__ import annotations

import datetime as dt
import html as _html
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _http import make_session, patient_get, throttle
from _models import FetchResult, FilingItem

VENDOR_CODE = "ojk"
OJK_ROOT = "https://ojk.go.id"

# (stream, listing_url, doc_type)
STREAMS: tuple[tuple[str, str, str], ...] = (
    (
        "press_release",
        f"{OJK_ROOT}/id/berita-dan-kegiatan/siaran-pers/Default.aspx",
        "release",
    ),
    (
        "press_release_en",
        f"{OJK_ROOT}/en/berita-dan-kegiatan/siaran-pers/Default.aspx",
        "release",
    ),
    (
        "annual_report",
        f"{OJK_ROOT}/id/data-dan-statistik/laporan-tahunan/Default.aspx",
        "report",
    ),
)

# NOT a stream: `/id/kanal/perbankan/data-dan-statistik/
# statistik-perbankan-indonesia/Default.aspx` (Statistik Perbankan Indonesia)
# renders a data-download page, not an article listing -- zero
# `a.group-item-title` nodes. It is a Track A candidate (bank-level
# statistics as series), not a Track B document stream, so it is recorded in
# `id_govt_doc_sources.md` under the Track A follow-ups instead of being
# carried here as a permanently empty fetch.

_MONTHS = {
    "januari": 1, "februari": 2, "maret": 3, "april": 4, "mei": 5, "juni": 6,
    "juli": 7, "agustus": 8, "september": 9, "oktober": 10, "november": 11,
    "desember": 12,
    "january": 1, "february": 2, "march": 3, "may": 5, "june": 6, "july": 7,
    "august": 8, "october": 10, "december": 12,
}

_ROW = re.compile(r'<li class="list-group-item">(.*?)</li>', re.S)
_TITLE = re.compile(
    r'<a\s+href="([^"]+)"[^>]*class="group-item-title"[^>]*>(.*?)</a>', re.S
)
_DATE_DIV = re.compile(r'<div class="date">(.*?)</div>', re.S)
_CAPTION = re.compile(r'<div class="caption">(.*?)</div>', re.S)
# OJK's two language mirrors disagree on date ORDER, not just month name:
# /id/ serves "9 September 2026" (D Month YYYY) and /en/ serves
# "August 31, 2026" (Month D, YYYY). Parsing only the first shape silently
# drops every English row -- which is exactly what happened before this was
# split in two.
_DATE_DMY = re.compile(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})")
_DATE_MDY = re.compile(r"([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})")

# The Dewan Komisioner monthly meeting result -- OJK's policy-decision text.
DK_TITLE = re.compile(
    r"rapat\s+dewan\s+komisioner|\bRDK\b|board\s+of\s+commissioners", re.I
)


def _text(raw: str) -> str:
    s = re.sub(r"<[^>]+>", " ", raw)
    s = _html.unescape(s).replace("\xa0", " ")
    return re.sub(r"\s+", " ", s).strip()


def _parse_date(raw: str) -> dt.date | None:
    """Accept both `9 September 2026` and `August 31, 2026`."""
    s = _text(raw)
    m = _DATE_DMY.search(s)
    if m:
        day, month_name, year = m.group(1), m.group(2), m.group(3)
    else:
        m = _DATE_MDY.search(s)
        if not m:
            return None
        month_name, day, year = m.group(1), m.group(2), m.group(3)
    month = _MONTHS.get(month_name.strip().lower())
    if not month:
        return None
    try:
        return dt.date(int(year), month, int(day))
    except ValueError:
        return None


def parse_rows(html: str) -> list[dict]:
    """Extract press rows, skipping the ~370 nav `list-group-item`s."""
    rows: list[dict] = []
    for blk in _ROW.findall(html):
        m = _TITLE.search(blk)
        if not m:
            continue  # nav item, not a filing
        d = _DATE_DIV.search(blk)
        pub = _parse_date(d.group(1)) if d else None
        title = _text(m.group(2))
        if not (title and pub):
            continue
        cap = _CAPTION.search(blk)
        href = m.group(1)
        rows.append(
            {
                "url": href if href.startswith("http") else OJK_ROOT + href,
                "title": title,
                "publish_date": pub,
                "abstract": _text(cap.group(1)) if cap else "",
            }
        )
    return rows


def discover(throttle_s: float = 1.0) -> FetchResult:
    items: list[FilingItem] = []
    failed: list[str] = []

    with make_session() as client:
        for stream, url, doc_type in STREAMS:
            try:
                html = patient_get(client, url).text
            # Broad by intent: per-stream isolation.
            except Exception as exc:
                failed.append(f"{stream}: {type(exc).__name__}")
                continue
            for row in parse_rows(html):
                dt_ = "decision" if DK_TITLE.search(row["title"]) else doc_type
                items.append(
                    FilingItem(
                        vendor_code=VENDOR_CODE,
                        title=row["title"],
                        publish_date=row["publish_date"],
                        source_url=row["url"],
                        doc_type=dt_,
                        stream=stream,
                        extras={"abstract": row["abstract"]} if row["abstract"] else {},
                    )
                )
            throttle(throttle_s)

    note = f"{len(STREAMS) - len(failed)}/{len(STREAMS)} streams"
    if failed:
        note += f"; failed: {', '.join(failed)}"
    return FetchResult(
        vendor_code=VENDOR_CODE,
        ok=len(failed) < len(STREAMS),
        items=items,
        error="; ".join(failed) or None,
        note=note,
    )


if __name__ == "__main__":
    res = discover()
    print(f"ojk ok={res.ok} items={len(res.items)} :: {res.note}")
    by: dict[str, int] = {}
    for it in res.items:
        by[it.stream] = by.get(it.stream, 0) + 1
    for s, n in sorted(by.items(), key=lambda kv: -kv[1]):
        print(f"  {n:3d}  {s}")
    for it in sorted(res.items, key=lambda i: i.publish_date, reverse=True)[:10]:
        print(f"   {it.publish_date}  [{it.doc_type:8s}] {it.title[:74]}")
