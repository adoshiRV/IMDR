"""FOMC MINUTES — discovery probe.

Source: federalreserve.gov/monetarypolicy/fomccalendars.htm

Minutes of each FOMC meeting are released on a ~3-week lag and published at:

    /monetarypolicy/fomcminutes{YYYYMMDD}.htm        ← minutes (HTML)
    /monetarypolicy/files/fomcminutes{YYYYMMDD}.pdf  ← minutes (PDF)

where {YYYYMMDD} is the meeting's decision day (same slug as the
statement). Both HTML and PDF are listed on the calendar hub; this probe
keeps the HTML detail page as source_url and the PDF as pdf_url.

The 3-week lag means the most-recent meeting will appear on the calendar
(statement present) but its minutes link may not yet exist — that's
expected cadence drift, not a bug.

Crawler shape: **Shape D — HTML-listing on a govt portal** (single GET,
regex over hrefs, date parsed from URL slug, no pagination).

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

# HTML detail page: /monetarypolicy/fomcminutes{YYYYMMDD}.htm
_MIN_HREF_RE = re.compile(r"/monetarypolicy/fomcminutes(\d{8})\.htm", re.I)


def _date_from_slug(yyyymmdd: str) -> date | None:
    try:
        return date(int(yyyymmdd[:4]), int(yyyymmdd[4:6]), int(yyyymmdd[6:8]))
    except ValueError:
        return None


def _parse_calendar(html: str) -> list[FilingItem]:
    items: list[FilingItem] = []
    seen: set[str] = set()
    for m in _MIN_HREF_RE.finditer(html):
        yyyymmdd = m.group(1)
        d = _date_from_slug(yyyymmdd)
        if d is None:
            continue
        url = f"{FED_BASE}/monetarypolicy/fomcminutes{yyyymmdd}.htm"
        if url in seen:
            continue
        seen.add(url)
        pdf_url = f"{FED_BASE}/monetarypolicy/files/fomcminutes{yyyymmdd}.pdf"
        items.append(FilingItem(
            vendor_code="fed",
            title=f"FOMC minutes - meeting of {d.isoformat()}",
            publish_date=d,   # = meeting date; actual release is ~3 wks later
            source_url=url,
            pdf_url=pdf_url,
            doc_type="minutes",
            stream="fomc_minutes",
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
        save_raw("fomc_minutes", "fomccalendars.htm", r.text)
    items = _parse_calendar(r.text)
    return FetchResult(
        vendor_code="fed",
        ok=True,
        items=items,
        note=f"{len(items)} minutes parsed from FOMC calendar (publish_date = meeting date, release ~3wk later)",
    )


def _print_summary(res: FetchResult) -> None:
    print(f"fomc_minutes  ok={res.ok}  items={len(res.items)}  err={res.error}")
    print(f"  note: {res.note}")
    for it in res.items[:10]:
        print(f"  {it.publish_date}  [{it.doc_type:9}] {it.title}")
        print(f"             html: {it.source_url}")
        print(f"             pdf : {it.pdf_url}")


if __name__ == "__main__":
    _print_summary(discover())
