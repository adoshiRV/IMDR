"""FOMC monetary-policy STATEMENTS — discovery probe.

Source: federalreserve.gov/monetarypolicy/fomccalendars.htm

The FOMC calendar hub is a single server-rendered HTML page (~160 KB,
plain GET, no JS). Every post-meeting policy decision is published as a
press release at:

    /newsevents/pressreleases/monetary{YYYYMMDD}a.htm   ← the statement (HTML)
    /monetarypolicy/files/monetary{YYYYMMDD}a1.pdf      ← implementation note (PDF)

where {YYYYMMDD} is the second (decision) day of the meeting. The page
also carries `...a1.htm`, `...b.htm` (e.g. balance-sheet plans) variants;
this probe keeps the canonical `...a.htm` statement only and attaches the
matching `...a1.pdf` implementation note as pdf_url when present.

Crawler shape: **Shape D — HTML-listing on a govt portal** (single GET,
regex over hrefs, no pagination — the whole multi-year calendar is on one
page). The {YYYYMMDD} date is parsed straight out of the URL slug, so no
date-cell scraping is needed.

Reachability (probed 2026-06-22): 200 OK / ~164 KB over plain HTTPS.
No Akamai, no TLS reset. plain httpx, no Playwright.
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

# Statement press release: monetary{YYYYMMDD}a.htm (the "a" variant is the
# policy statement; a1=implementation note, b=balance-sheet plan, etc.)
_STMT_HREF_RE = re.compile(
    r"/newsevents/pressreleases/monetary(\d{8})a\.htm", re.I
)


def _date_from_slug(yyyymmdd: str) -> date | None:
    try:
        return date(int(yyyymmdd[:4]), int(yyyymmdd[4:6]), int(yyyymmdd[6:8]))
    except ValueError:
        return None


def _parse_calendar(html: str) -> list[FilingItem]:
    items: list[FilingItem] = []
    seen: set[str] = set()
    for m in _STMT_HREF_RE.finditer(html):
        yyyymmdd = m.group(1)
        d = _date_from_slug(yyyymmdd)
        if d is None:
            continue
        url = f"{FED_BASE}/newsevents/pressreleases/monetary{yyyymmdd}a.htm"
        if url in seen:
            continue
        seen.add(url)
        # Implementation-note PDF lives under /monetarypolicy/files/ with
        # the same slug + "1". Always emitted by the Fed alongside the
        # statement; attach as pdf_url (resolution proof, not downloaded).
        pdf_url = f"{FED_BASE}/monetarypolicy/files/monetary{yyyymmdd}a1.pdf"
        items.append(FilingItem(
            vendor_code="fed",
            title=f"FOMC statement - {d.isoformat()}",
            publish_date=d,
            source_url=url,
            pdf_url=pdf_url,
            doc_type="decision",
            stream="fomc_statements",
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
        save_raw("fomc_statements", "fomccalendars.htm", r.text)
    items = _parse_calendar(r.text)
    return FetchResult(
        vendor_code="fed",
        ok=True,
        items=items,
        note=f"{len(items)} statements parsed from FOMC calendar",
    )


def _print_summary(res: FetchResult) -> None:
    print(f"fomc_statements  ok={res.ok}  items={len(res.items)}  err={res.error}")
    print(f"  note: {res.note}")
    for it in res.items[:10]:
        print(f"  {it.publish_date}  [{it.doc_type:9}] {it.title}")
        print(f"             html: {it.source_url}")
        print(f"             pdf : {it.pdf_url}")


if __name__ == "__main__":
    _print_summary(discover())
