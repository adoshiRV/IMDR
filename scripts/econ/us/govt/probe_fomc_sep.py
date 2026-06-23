"""FOMC Summary of Economic Projections (SEP) — discovery probe.

Source: federalreserve.gov/monetarypolicy/fomccalendars.htm

The SEP (the "dot plot" + central-tendency macro forecasts) is published
at the four projection meetings per year (Mar / Jun / Sep / Dec) at:

    /monetarypolicy/fomcprojtabl{YYYYMMDD}.htm        ← projections table (HTML)
    /monetarypolicy/files/fomcprojtabl{YYYYMMDD}.pdf  ← projections table (PDF)

where {YYYYMMDD} is the projection meeting's decision day. This is the
``fomcprojtabl{YYYYMMDD}.pdf`` pattern called out in the US index.md.
Only ~4 of the 8 annual meetings carry an SEP, so the SEP count is roughly
half the statement count.

Crawler shape: **Shape D — HTML-listing on a govt portal** (single GET,
regex over hrefs, date from URL slug, no pagination).

Reachability (probed 2026-06-22): 200 OK over plain HTTPS. plain httpx.
"""
from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _http import make_session, patient_get, save_raw  # noqa: E402
from _models import FetchResult, FilingItem  # noqa: E402

FED_BASE = "https://www.federalreserve.gov"
CALENDAR_URL = f"{FED_BASE}/monetarypolicy/fomccalendars.htm"

# PDF: /monetarypolicy/files/fomcprojtabl{YYYYMMDD}.pdf
# HTML: /monetarypolicy/fomcprojtabl{YYYYMMDD}.htm
_SEP_HREF_RE = re.compile(r"fomcprojtabl(\d{8})\.(?:pdf|htm)", re.I)


def _date_from_slug(yyyymmdd: str) -> date | None:
    try:
        return date(int(yyyymmdd[:4]), int(yyyymmdd[4:6]), int(yyyymmdd[6:8]))
    except ValueError:
        return None


def _parse_calendar(html: str) -> list[FilingItem]:
    items: list[FilingItem] = []
    seen: set[str] = set()
    for m in _SEP_HREF_RE.finditer(html):
        yyyymmdd = m.group(1)
        d = _date_from_slug(yyyymmdd)
        if d is None:
            continue
        if yyyymmdd in seen:   # dedup pdf + htm hits for the same meeting
            continue
        seen.add(yyyymmdd)
        html_url = f"{FED_BASE}/monetarypolicy/fomcprojtabl{yyyymmdd}.htm"
        pdf_url = f"{FED_BASE}/monetarypolicy/files/fomcprojtabl{yyyymmdd}.pdf"
        items.append(FilingItem(
            vendor_code="fed",
            title=f"Summary of Economic Projections - {d.isoformat()}",
            publish_date=d,
            source_url=html_url,
            pdf_url=pdf_url,
            doc_type="projection",
            stream="fomc_sep",
            extras={"meeting_date": d.isoformat()},
        ))
    items.sort(key=lambda it: it.publish_date, reverse=True)
    return items


def discover(*, save_raw_html: bool = True) -> FetchResult:
    with make_session() as sess:
        try:
            r = patient_get(sess, CALENDAR_URL)
        except RuntimeError as exc:
            return FetchResult(vendor_code="fed", ok=False, error=str(exc))
    if save_raw_html:
        save_raw("fomc_sep", "fomccalendars.htm", r.text)
    items = _parse_calendar(r.text)
    return FetchResult(
        vendor_code="fed",
        ok=True,
        items=items,
        note=f"{len(items)} SEP releases (fomcprojtabl pattern) parsed from FOMC calendar",
    )


def _print_summary(res: FetchResult) -> None:
    print(f"fomc_sep  ok={res.ok}  items={len(res.items)}  err={res.error}")
    print(f"  note: {res.note}")
    for it in res.items[:10]:
        print(f"  {it.publish_date}  [{it.doc_type:10}] {it.title}")
        print(f"             pdf : {it.pdf_url}")


if __name__ == "__main__":
    _print_summary(discover())
