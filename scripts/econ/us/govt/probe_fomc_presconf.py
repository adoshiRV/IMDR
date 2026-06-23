"""FOMC press-conference materials — discovery probe.

Source: federalreserve.gov/monetarypolicy/fomccalendars.htm

Since 2019 the Chair holds a press conference after every FOMC meeting.
The press-conference materials hang off the same FOMC calendar hub as the
statement / minutes / SEP (streams 1.1-1.3). Per meeting:

    /monetarypolicy/fomcpresconf{YYYYMMDD}.htm   ← landing page (HTML)
    /mediacenter/files/FOMCpresconf{YYYYMMDD}.pdf ← Chair Q&A TRANSCRIPT (PDF)

NOTE the transcript PDF lives under **/mediacenter/files/** with a
capitalised `FOMCpresconf` stem — NOT `/monetarypolicy/files/`. Verified
2026-06-22: `/monetarypolicy/files/FOMCpresconf{YYYYMMDD}.pdf` → 404,
`/mediacenter/files/FOMCpresconf{YYYYMMDD}.pdf` → 200 application/pdf.
(The US doc-inventory row 1.4 has the correct path; the build prompt's
`/monetarypolicy/files/...` was wrong.)

The lowercase `fomcpresconf{YYYYMMDD}.htm` link appears ~89× on the calendar
hub; the date is parsed straight from the `{YYYYMMDD}` URL slug. One row per
meeting that has a presser.

Crawler shape: **Shape B — calendar/index HTML hub, slug-keyed** (single
GET, regex over hrefs, date from URL slug, no pagination). Same transport as
probe_fomc_statements / probe_fomc_sep.

Reachability (probed 2026-06-22): calendar hub 200 OK / ~164 KB; transcript
PDF 200 OK / ~210-240 KB over plain HTTPS. plain httpx, no Playwright.
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

# Landing page: /monetarypolicy/fomcpresconf{YYYYMMDD}.htm (lowercase stem)
_PRESCONF_HREF_RE = re.compile(r"/monetarypolicy/fomcpresconf(\d{8})\.htm", re.I)


def _date_from_slug(yyyymmdd: str) -> date | None:
    try:
        return date(int(yyyymmdd[:4]), int(yyyymmdd[4:6]), int(yyyymmdd[6:8]))
    except ValueError:
        return None


def _parse_calendar(html: str) -> list[FilingItem]:
    items: list[FilingItem] = []
    seen: set[str] = set()
    for m in _PRESCONF_HREF_RE.finditer(html):
        yyyymmdd = m.group(1)
        d = _date_from_slug(yyyymmdd)
        if d is None or yyyymmdd in seen:
            continue
        seen.add(yyyymmdd)
        html_url = f"{FED_BASE}/monetarypolicy/fomcpresconf{yyyymmdd}.htm"
        # Transcript PDF: capitalised stem under /mediacenter/files/.
        pdf_url = f"{FED_BASE}/mediacenter/files/FOMCpresconf{yyyymmdd}.pdf"
        items.append(FilingItem(
            vendor_code="fed",
            title=f"FOMC press conference transcript - {d.isoformat()}",
            publish_date=d,
            source_url=html_url,
            pdf_url=pdf_url,
            doc_type="transcript",
            stream="fomc_presconf",
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
        save_raw("fomc_presconf", "fomccalendars.htm", r.text)
    items = _parse_calendar(r.text)
    return FetchResult(
        vendor_code="fed",
        ok=True,
        items=items,
        note=f"{len(items)} press-conference transcripts (fomcpresconf pattern) parsed from FOMC calendar",
    )


def _print_summary(res: FetchResult) -> None:
    print(f"fomc_presconf  ok={res.ok}  items={len(res.items)}  err={res.error}")
    print(f"  note: {res.note}")
    for it in res.items[:10]:
        print(f"  {it.publish_date}  [{it.doc_type:10}] {it.title}")
        print(f"             html: {it.source_url}")
        print(f"             pdf : {it.pdf_url}")


if __name__ == "__main__":
    _print_summary(discover())
