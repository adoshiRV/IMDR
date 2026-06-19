"""MOSPI press-release listing API client.

Single endpoint shared by every MOSPI domain — CPI, IIP, NAS GDP, PLFS:

  POST https://www.mospi.gov.in/api/latest-release/get-web-latest-release-list

Body fields used: search_term (free text), sort_field=published_year,
sort_order=DESC, lang=en, data_source=web. Each result item carries a
`file_one` (PDF) and optional `file_two` (XLSX) attachment.

For each topic the latest release contains the FULL time-series back to
the base year, so prod fetchers only need to pull the most-recent item
and parse it — there is no per-release backfill loop.
"""
from __future__ import annotations

import datetime
import re
from typing import Iterable

import httpx


BASE = "https://www.mospi.gov.in"
LISTING = f"{BASE}/api/latest-release/get-web-latest-release-list"

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 Chrome/120 Safari/537.36"),
    "Content-Type": "application/json",
    "Referer": "https://mospi.gov.in/",
    "Origin": "https://mospi.gov.in",
}


def list_releases(client: httpx.Client, search_term: str, page_size: int = 10) -> list[dict]:
    body = {
        "page_no": 1, "page_size": page_size,
        "search_term": search_term,
        "sort_field": "published_year", "sort_order": "DESC",
        "from_date": "", "to_date": "",
        "lang": "en", "data_source": "web",
    }
    r = client.post(LISTING, headers=HEADERS, json=body)
    r.raise_for_status()
    return r.json().get("data", []) or []


def fetch_attachment(client: httpx.Client, path: str) -> bytes:
    url = f"{BASE}/{path.lstrip('/')}"
    r = client.get(url, headers={"User-Agent": HEADERS["User-Agent"],
                                  "Referer": HEADERS["Referer"]})
    r.raise_for_status()
    return r.content


_MONTH_RE = re.compile(r"month of (\w+),?\s*(\d{4})", re.I)


def parse_month_year(title: str) -> datetime.date | None:
    """Extract the obs_date end-month from a MOSPI release title.

    Title pattern: ``Quick Estimates of IIP (Base: 2011-12) for the
    month of March 2026``. Returns the first-of-month date for the
    matched ``<Month> <Year>`` token, or ``None`` if absent.
    """
    m = _MONTH_RE.search(title or "")
    if not m:
        return None
    try:
        return datetime.datetime.strptime(
            f"{m.group(1)} {m.group(2)}", "%B %Y"
        ).date()
    except ValueError:
        return None


def latest_xlsx(
    client: httpx.Client, search_term: str,
    *, suffixes: Iterable[str] = (".xlsx", ".xls"),
    use_file_two: bool = True,
) -> tuple[str, datetime.date, bytes]:
    """Return (title, end_month, bytes) for the most-recent release.

    ``use_file_two=True`` prefers the secondary attachment (typically the
    XLSX press-release statement). Set False to pull ``file_one`` (the
    PDF).  Raises ``RuntimeError`` if no item matched.
    """
    for item in list_releases(client, search_term):
        attach = item.get("file_two" if use_file_two else "file_one") or {}
        path = (attach.get("path") or "").lower()
        if not any(path.endswith(s) for s in suffixes):
            continue
        end = parse_month_year(item.get("title", ""))
        if end is None:
            continue
        blob = fetch_attachment(client, attach["path"])
        return item["title"], end, blob
    raise RuntimeError(f"no MOSPI release with matching attachment for {search_term!r}")
