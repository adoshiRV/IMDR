"""CB event scrapers — one function per central bank.

Each function returns list[dict] with keys:
    country_code, event_date, event_name, ticker, category, relevance, source, is_estimated

Scrapers use requests + BeautifulSoup.  If a scrape fails, logs a warning
and returns an empty list so the refresh pipeline is never blocked.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

import requests
import structlog
from bs4 import BeautifulSoup

log = structlog.get_logger(__name__)

_TIMEOUT = 15  # seconds
_HEADERS = {"User-Agent": "IMDR-CalendarBot/1.0"}


def _make_event(
    country_code: str,
    event_date: date,
    event_name: str,
    *,
    ticker: str | None = None,
    category: str = "Central Banks",
    relevance: float = 90.0,
    source: str = "unknown",
    is_estimated: bool = False,
) -> dict:
    return {
        "country_code": country_code,
        "event_date": event_date,
        "event_name": event_name,
        "ticker": ticker,
        "category": category,
        "relevance": relevance,
        "source": source,
        "is_estimated": is_estimated,
    }


# ---------------------------------------------------------------------------
# PBOC LPR — algorithmic (20th of each month, shift to next Mon if weekend)
# ---------------------------------------------------------------------------

def generate_pboc_lpr(year: int) -> list[dict]:
    """Generate 12 monthly PBOC LPR fixing dates for *year*."""
    events = []
    for month in range(1, 13):
        d = date(year, month, 20)
        # Shift weekend to next Monday
        if d.weekday() == 5:  # Saturday
            d += timedelta(days=2)
        elif d.weekday() == 6:  # Sunday
            d += timedelta(days=1)
        events.append(_make_event(
            "CN", d, "PBOC 1Y/5Y Loan Prime Rate",
            relevance=95.0, source="pboc.gov.cn",
        ))
    return events


# ---------------------------------------------------------------------------
# MAS — estimated mid-month (Jan, Apr, Jul, Oct)
# ---------------------------------------------------------------------------

_MAS_MONTHS = [1, 4, 7, 10]
_MAS_DEFAULT_DAY = 14  # historical mid-month pattern


def generate_mas_estimates(year: int) -> list[dict]:
    """Generate 4 quarterly MAS Monetary Policy Statement estimates."""
    events = []
    for month in _MAS_MONTHS:
        d = date(year, month, _MAS_DEFAULT_DAY)
        if d.weekday() == 5:
            d += timedelta(days=2)
        elif d.weekday() == 6:
            d += timedelta(days=1)
        events.append(_make_event(
            "SG", d, "MAS Monetary Policy Statement",
            relevance=94.0, source="estimated", is_estimated=True,
        ))
    return events


# ---------------------------------------------------------------------------
# RBI MPC — scrape rbi.org.in
# ---------------------------------------------------------------------------

_RBI_URL = "https://www.rbi.org.in/scripts/annualpolicy.aspx"

# Fallback: known FY schedule pages
_RBI_SEARCH_URLS = [
    "https://hellobanker.in/rbi-releases-schedule-of-meeting-of-monetary-policy-committee-{fy}/",
    "https://www.5paisa.com/blog/rbi-mpc-meeting-{year}",
]

_RBI_DATE_PATTERN = re.compile(
    r"(\w+)\s+(\d{1,2})(?:\s*[-,&]\s*\d{1,2})*(?:\s*[-,&]\s*(\d{1,2}))?\s*,?\s*(\d{4})"
)

_MONTH_MAP = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}


def scrape_rbi_mpc(year: int) -> list[dict]:
    """Scrape RBI MPC meeting schedule. Returns last day of each meeting."""
    try:
        # Try the hellobanker page which has clean table format
        fy = f"{year}-{(year + 1) % 100:02d}"
        url = _RBI_SEARCH_URLS[0].format(fy=fy)
        resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
        if resp.status_code != 200:
            log.warning("rbi_scrape_http_error", url=url, status=resp.status_code)
            return _rbi_fallback(year)

        soup = BeautifulSoup(resp.text, "html.parser")
        text = soup.get_text()

        events = []
        # Look for patterns like "April 6, 7, and 8, 2026" or "June 3, 4, and 5, 2026"
        for match in re.finditer(
            r"(\w+)\s+(\d{1,2})\s*,\s*(\d{1,2})\s*(?:,?\s*and\s+)?(\d{1,2})\s*,?\s*(\d{4})",
            text,
        ):
            month_name, _, _, last_day, yr = match.groups()
            month_num = _MONTH_MAP.get(month_name.lower())
            if month_num and int(yr) == year:
                d = date(year, month_num, int(last_day))
                events.append(_make_event(
                    "IN", d, "RBI Repurchase Rate",
                    ticker="INRPYLDP Index",
                    relevance=94.7, source="rbi.org.in",
                ))

        if events:
            log.info("rbi_scraped", count=len(events), year=year)
            return events

        return _rbi_fallback(year)

    except Exception:
        log.warning("rbi_scrape_failed", year=year, exc_info=True)
        return _rbi_fallback(year)


def _rbi_fallback(year: int) -> list[dict]:
    """RBI meets bimonthly (Feb, Apr, Jun, Aug, Oct, Dec) — estimate first week."""
    log.info("rbi_using_fallback_estimates", year=year)
    events = []
    for month in [2, 4, 6, 8, 10, 12]:
        # First Wednesday of each even month is typical
        d = date(year, month, 1)
        # Find first Wednesday
        while d.weekday() != 2:
            d += timedelta(days=1)
        # MPC runs 3 days ending on this date + 2
        announcement = d + timedelta(days=2)  # Friday
        events.append(_make_event(
            "IN", announcement, "RBI Repurchase Rate",
            ticker="INRPYLDP Index",
            relevance=94.7, source="estimated", is_estimated=True,
        ))
    return events


# ---------------------------------------------------------------------------
# CBC Taiwan — scrape cbc.gov.tw
# ---------------------------------------------------------------------------

_CBC_LISTING_URL = "https://www.cbc.gov.tw/en/lp-448-2.html"
_CBC_SCHEDULE_URL_TEMPLATE = "https://www.cbc.gov.tw/en/cp-448-{page_id}-2.html"

# Known page IDs for provisional schedule pages (discovered via listing page)
_CBC_KNOWN_PAGES = {
    2026: "189515-f1342",
}


def scrape_cbc_schedule(year: int) -> list[dict]:
    """Scrape CBC (Taiwan) quarterly meeting dates from the schedule page."""
    try:
        # Try known page first, then search listing
        page_id = _CBC_KNOWN_PAGES.get(year)
        if page_id:
            url = _CBC_SCHEDULE_URL_TEMPLATE.format(page_id=page_id)
        else:
            url = _find_cbc_schedule_page(year)
            if not url:
                return _cbc_fallback(year)

        resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
        if resp.status_code != 200:
            log.warning("cbc_scrape_http_error", status=resp.status_code)
            return _cbc_fallback(year)

        soup = BeautifulSoup(resp.text, "html.parser")
        text = soup.get_text()

        # The schedule page has dates on standalone lines: "March 19", "June 18", etc.
        # Only match the 4 quarterly months (Mar, Jun, Sep, Dec).
        events = []
        _CBC_MONTHS = {"march": 3, "june": 6, "september": 9, "december": 12}
        cbc_pattern = re.compile(
            r"^(March|June|September|December)\s+(\d{1,2})$",
            re.IGNORECASE | re.MULTILINE,
        )

        for match in cbc_pattern.finditer(text):
            month_name, day = match.groups()
            month_num = _CBC_MONTHS.get(month_name.lower())
            if month_num:
                d = date(year, month_num, int(day))
                events.append(_make_event(
                    "TW", d, "CBC Quarterly Rate Decision",
                    relevance=93.0, source="cbc.gov.tw",
                ))

        # Deduplicate
        seen = set()
        unique = []
        for e in events:
            if e["event_date"] not in seen:
                seen.add(e["event_date"])
                unique.append(e)

        if unique:
            log.info("cbc_scraped", count=len(unique), year=year)
            return unique

        return _cbc_fallback(year)

    except Exception:
        log.warning("cbc_scrape_failed", year=year, exc_info=True)
        return _cbc_fallback(year)


def _find_cbc_schedule_page(year: int) -> str | None:
    """Search CBC press releases listing for the schedule page URL."""
    try:
        resp = requests.get(_CBC_LISTING_URL, headers=_HEADERS, timeout=_TIMEOUT)
        if resp.status_code != 200:
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
        for a in soup.find_all("a"):
            text = a.get_text(strip=True)
            if "provisional" in text.lower() and str(year) in text:
                href = a.get("href", "")
                if href.startswith("/"):
                    return f"https://www.cbc.gov.tw{href}"
                return href
    except Exception:
        pass
    return None


def _cbc_fallback(year: int) -> list[dict]:
    """CBC meets quarterly (Mar, Jun, Sep, Dec) — estimate 3rd Thursday."""
    log.info("cbc_using_fallback_estimates", year=year)
    events = []
    for month in [3, 6, 9, 12]:
        d = date(year, month, 1)
        # Find 3rd Thursday
        thursdays = 0
        while thursdays < 3:
            if d.weekday() == 3:
                thursdays += 1
                if thursdays == 3:
                    break
            d += timedelta(days=1)
        events.append(_make_event(
            "TW", d, "CBC Quarterly Rate Decision",
            relevance=93.0, source="estimated", is_estimated=True,
        ))
    return events


# ---------------------------------------------------------------------------
# BSP Philippines — scrape bsp.gov.ph
# ---------------------------------------------------------------------------

_BSP_URL = (
    "https://www.bsp.gov.ph/Pages/PriceStability/"
    "ScheduleOfMeetingsOfTheAdvisoryCommitteeAndMonetaryBoardOnMonetaryPolicy.aspx"
)


def scrape_bsp_schedule(year: int) -> list[dict]:
    """Scrape BSP (Philippines) monetary board meeting dates.

    The BSP page has dates embedded with zero-width spaces, e.g.:
        "Apr23 (Thu)(MB Meeting No. 2)"
        "Jun  18 (Thu)(MB Meeting No. 3)"
    We clean the text first, then parse "MB Meeting No." patterns.
    """
    try:
        resp = requests.get(_BSP_URL, headers=_HEADERS, timeout=_TIMEOUT)
        if resp.status_code != 200:
            log.warning("bsp_scrape_http_error", status=resp.status_code)
            return _bsp_fallback(year)

        soup = BeautifulSoup(resp.text, "html.parser")
        # Clean zero-width spaces and non-breaking spaces
        raw = soup.get_text()
        text = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", raw)
        text = text.replace("\xa0", " ")

        events = []
        _SHORT_MONTHS = {
            "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
            "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
        }

        # Scope to the target year section — look for "MPR I - {year}" marker
        year_marker = f"MPR I - {year}"
        alt_marker = f"MPR I -{year}"
        start_idx = text.find(year_marker)
        if start_idx == -1:
            start_idx = text.find(alt_marker)
        if start_idx == -1:
            # Try just finding the year near "MB Meeting"
            start_idx = 0

        # End at the next year's section or "(DD Month YYYY MB" pattern from prior year
        end_idx = len(text)
        prev_year_marker = f"MPR I - {year - 1}"
        if start_idx > 0:
            # Find next MPR marker after our section
            next_section = text.find(f"MPR I - {year + 1}", start_idx)
            if next_section == -1:
                next_section = text.find(f"({year - 1}", start_idx)
            if next_section > 0:
                end_idx = next_section

        section = text[max(0, start_idx - 200):end_idx]

        # Collect meeting numbers to detect the 6 meetings for this year
        meetings_found: dict[int, date] = {}
        for match in re.finditer(
            r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s*(\d{1,2})\s*\(\w+\)\s*\(MB Meeting No\.\s*(\d+)\)",
            section,
            re.IGNORECASE,
        ):
            month_abbr, day, meeting_num = match.groups()
            num = int(meeting_num)
            month_num = _SHORT_MONTHS.get(month_abbr.lower())
            if month_num and num not in meetings_found:
                # Only take the first occurrence of each meeting number
                meetings_found[num] = date(year, month_num, int(day))

        for num in sorted(meetings_found):
            events.append(_make_event(
                "PH", meetings_found[num], "BSP Overnight Reverse Repurchase Rate",
                relevance=92.0, source="bsp.gov.ph",
            ))

        # No fallback to other date formats — only trust "MB Meeting No." patterns
        # to avoid picking up MPR publication dates

        # Deduplicate
        seen = set()
        unique = []
        for e in events:
            if e["event_date"] not in seen:
                seen.add(e["event_date"])
                unique.append(e)

        if unique:
            log.info("bsp_scraped", count=len(unique), year=year)
            return unique

        return _bsp_fallback(year)

    except Exception:
        log.warning("bsp_scrape_failed", year=year, exc_info=True)
        return _bsp_fallback(year)


def _bsp_fallback(year: int) -> list[dict]:
    """BSP meets ~6x per year (Feb, Apr, Jun, Aug, Oct, Dec) — estimate 3rd Thursday."""
    log.info("bsp_using_fallback_estimates", year=year)
    events = []
    for month in [2, 4, 6, 8, 10, 12]:
        d = date(year, month, 1)
        thursdays = 0
        while thursdays < 3:
            if d.weekday() == 3:
                thursdays += 1
                if thursdays == 3:
                    break
            d += timedelta(days=1)
        events.append(_make_event(
            "PH", d, "BSP Overnight Reverse Repurchase Rate",
            relevance=92.0, source="estimated", is_estimated=True,
        ))
    return events


# ---------------------------------------------------------------------------
# Public API: scrape all
# ---------------------------------------------------------------------------

def scrape_all(year: int) -> list[dict]:
    """Run all scrapers/generators for the given year.

    Returns a unified list of CB event dicts.
    """
    all_events: list[dict] = []
    all_events.extend(generate_pboc_lpr(year))
    all_events.extend(generate_mas_estimates(year))
    all_events.extend(scrape_rbi_mpc(year))
    all_events.extend(scrape_cbc_schedule(year))
    all_events.extend(scrape_bsp_schedule(year))
    log.info("scrape_all_complete", year=year, total=len(all_events))
    return all_events
