"""NY Fed dealer surveys (SPD / SMP / SME) — discovery probe.

Source: newyorkfed.org/markets/market-intelligence/survey-of-market-expectations

The NY Fed's pre-FOMC surveys capture the Street's expectations for the
policy path, balance sheet, and economic projections, released ~1 week
after each FOMC meeting. Two long-running series:

  * **SPD** — Survey of Primary Dealers
  * **SMP** — Survey of Market Participants

Both were consolidated/renamed; the current public name is the **Survey of
Market Expectations (SME)** and all editions — old and new — are listed on a
single hub page.

Listing transport
-----------------
newyorkfed.org is a Sitecore/medialibrary stack. The *old* landing
``/markets/primarydealer_survey_questions.html`` still 200s but is now a thin
redirect-style page (no PDFs in its HTML). The **live hub** is

    /markets/market-intelligence/survey-of-market-expectations

which is plain-GET friendly (probed 2026-06-22: HTTP 200 / ~210 KB, no JS
render needed — the result PDFs are present in the raw HTML, NOT lazy-loaded).
``_http.py:make_session()`` reused verbatim; no Playwright, no anti-detection.

Every edition's PDFs sit under a stable medialibrary path:

    /medialibrary/media/markets/survey/{YYYY}/{mon}-{...}results.pdf   ← RESULTS (high-signal)
    /medialibrary/media/markets/survey/{YYYY}/{mon}-{...}survey-*.pdf  ← the questionnaire

The filename naming evolved across the series' history (``sme-results`` →
``spd-results`` / ``smp-results`` → ``survey-pd`` / ``survey-mp`` and older
``mp_*_result`` forms), but the **``result``** token reliably marks a results
PDF and the ``{YYYY}/`` folder + ``{mon}-`` filename prefix give the date.
This probe keeps the RESULTS PDFs (the questionnaire is captured in extras).

Crawler shape: **Shape A/D hybrid — single-GET HTML hub, regex over hrefs**
(one GET, no pagination, date parsed from the medialibrary URL — analogous to
the Fed calendar-hub slug parsing, just on a different host).
"""
from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _http import make_session, patient_get, save_raw  # noqa: E402
from _models import FetchResult, FilingItem  # noqa: E402

NYFED_BASE = "https://www.newyorkfed.org"
HUB_URL = f"{NYFED_BASE}/markets/market-intelligence/survey-of-market-expectations"

# /medialibrary/media/markets/survey/{YYYY}/{filename}.pdf
_SURVEY_PDF_RE = re.compile(
    r'href="(/medialibrary/media/markets/survey/(\d{4})/([^"]+\.pdf))"', re.I
)

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    "january": 1, "february": 2, "march": 3, "april": 4, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10,
    "november": 11, "december": 12,
}
_MONTH_PREFIX_RE = re.compile(r"^([a-z]+?)[-_]", re.I)

# A results PDF vs the questionnaire. "result" covers result/results/_result.
_IS_RESULTS_RE = re.compile(r"result", re.I)

# Which series a filename belongs to (for extras / dedup of the two series in
# one meeting month). pd/spd = primary dealers, mp/smp = market participants,
# sme = consolidated survey of market expectations.
def _series(fn: str) -> str:
    f = fn.lower()
    if "sme" in f:
        return "SME"
    if "spd" in f or "survey-pd" in f or "primary-dealers" in f or "-pd-" in f or f.startswith("pd-"):
        return "SPD"
    if "smp" in f or "survey-mp" in f or "market-participants" in f or "-mp-" in f or "mp_" in f or f.startswith("mp-"):
        return "SMP"
    return "survey"


def _date_from_filename(year: int, fn: str) -> date | None:
    m = _MONTH_PREFIX_RE.match(fn)
    if not m:
        return None
    mon = _MONTHS.get(m.group(1).lower())
    if mon is None:
        return None
    # Survey-edition day is not in the URL; anchor to the 1st of the month.
    return date(year, mon, 1)


def _parse_hub(html: str) -> list[FilingItem]:
    items: list[FilingItem] = []
    seen: set[str] = set()
    for m in _SURVEY_PDF_RE.finditer(html):
        rel, year_s, fn = m.group(1), m.group(2), m.group(3)
        if not _IS_RESULTS_RE.search(fn):
            continue  # keep only RESULTS PDFs; questionnaires recorded below
        url = NYFED_BASE + rel
        if url in seen:
            continue
        seen.add(url)
        year = int(year_s)
        pub = _date_from_filename(year, fn.rsplit("/", 1)[-1])
        if pub is None:
            continue
        series = _series(fn)
        items.append(FilingItem(
            vendor_code="nyfed",
            title=f"NY Fed {series} Results - {pub.isoformat()}",
            publish_date=pub,
            source_url=HUB_URL,
            pdf_url=url,
            doc_type="survey",
            stream="nyfed_dealer_survey",
            extras={"series": series, "year": year, "filename": fn.rsplit("/", 1)[-1]},
        ))
    items.sort(key=lambda it: it.publish_date, reverse=True)
    return items


def discover(*, meetings: int = 8, save_raw_html: bool = True) -> FetchResult:
    """Discover the most recent dealer-survey RESULTS PDFs.

    ``meetings`` caps to the latest N results PDFs (the SME consolidation
    means recent months have one results PDF; older months have a separate
    SPD + SMP results PDF, so the cap is on PDF count, not distinct dates).
    """
    with make_session() as sess:
        try:
            r = patient_get(sess, HUB_URL)
        except RuntimeError as exc:
            return FetchResult(vendor_code="nyfed", ok=False, error=str(exc))
    if save_raw_html:
        save_raw("nyfed_dealer_survey", "survey-of-market-expectations.html", r.text)
    items = _parse_hub(r.text)[:meetings]
    return FetchResult(
        vendor_code="nyfed",
        ok=True,
        items=items,
        note=(
            f"{len(items)} dealer-survey results PDFs (SPD/SMP/SME) "
            f"parsed from the SME hub"
        ),
    )


def _print_summary(res: FetchResult) -> None:
    print(f"nyfed_dealer_survey  ok={res.ok}  items={len(res.items)}  err={res.error}")
    print(f"  note: {res.note}")
    for it in res.items[:12]:
        print(f"  {it.publish_date}  [{it.extras.get('series',''):6}] {it.title}")
        print(f"             pdf : {it.pdf_url}")


if __name__ == "__main__":
    _print_summary(discover())
