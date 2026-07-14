"""ANZ-Indeed Australian Job Ads — the successor to ANZ's long-running
"Job Advertisements" series, co-produced with Indeed's Hiring Lab.

Investigated 2026-07-14 in this order:
  1. Indeed Hiring Lab open data (github.com/hiring-lab/job_postings_tracker,
     AU/aggregate_job_postings_AU.csv + AU/job_postings_by_sector_AU.csv) --
     Indeed's own *raw* postings-volume index, daily, 2020-02 -> present,
     CC-BY licensed, no auth. Real and freely downloadable, but this is
     Indeed's global "Job Postings Index" product, NOT the branded
     ANZ-Indeed series itself (different base, different methodology,
     national+sector only for AU, no state cut).
  2. ANZ Research release -- the branded monthly series turned out to be
     the cleaner and more authoritative pull. anz.com/anz.com.au guessed
     URLs 404 (not a network block: the same client got 200s from
     anz.com.au/bluenotes/, github.com and duckduckgo.com in the same
     session), but the newsroom archive page
     ``https://www.anz.com.au/newsroom/media/release-dates/`` is reachable
     with a plain GET and embeds a "Download data" link to a structured
     XLSX -- the SEEK idiom (see seek_jobads.py): a stable landing page,
     scraped every run, pointing at a content-dated download URL that
     changes with each monthly release (path segment is the release
     month, filename carries the prior month's short code, e.g.
     ``.../2026/july/ANZ-Indeed Australian Job Ads data_Jun26.xlsx``).

Chose (2): it is ANZ's own official series (full history back to the
newspaper-ad era, spliced through internet ads to today's Indeed-sourced
methodology), monthly, base 2019=100, Original + Seasonally Adjusted +
Trend cuts -- confirmed via the downloaded workbook 1975-01 -> 2026-06
(619 monthly obs), single sheet ``ANZ-Indeed Australian Job Ads``
(the ``% mm`` / ``% yy`` sheets are derived growth-rate transforms of the
same three series, not additional dimensions -- not ingested). National
only: no state or industry/occupation breakdown is published in this
workbook (the monthly release PDF's prose mentions state colour --
e.g. "Job Ads in New South Wales rose the most" -- but does not tabulate
it). Not built: Indeed Hiring Lab's own AU CSVs (source 1 above) -- a
distinct, differently-based dataset; a future fetcher could add it
separately (e.g. under an ``indeed`` vendor) rather than conflating it
with this series.
"""
from __future__ import annotations

import datetime
import io
import re

import httpx

from imdr.domains.econ.schema import IndicatorRow, ObservationRow

UTC = datetime.timezone.utc
VENDOR_NAME = "ANZ"

RELEASE_DATES_URL = "https://www.anz.com.au/newsroom/media/release-dates/"
_BASE_URL = "https://www.anz.com.au"
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"

DATA_SHEET_NAME = "ANZ-Indeed Australian Job Ads"

_DOWNLOAD_LINK_RE = re.compile(
    r'<a href="([^"]+/jobads/[^"]+\.xlsx)">Download data</a>'
)


def _make_client() -> httpx.Client:
    return httpx.Client(timeout=30.0, follow_redirects=True, headers={"User-Agent": _UA})


def fetch_release_dates_html(client: httpx.Client) -> str:
    r = client.get(RELEASE_DATES_URL)
    r.raise_for_status()
    return r.text


def discover_download_url(html: str) -> str:
    """Return the absolute URL of the "Download data" XLSX link on the archive page."""
    m = _DOWNLOAD_LINK_RE.search(html)
    if not m:
        raise RuntimeError(
            "Could not find the 'Download data' link on the ANZ-Indeed Job Ads "
            "release-dates archive page -- page layout may have changed"
        )
    href = m.group(1)
    if href.startswith("http"):
        return href
    return _BASE_URL + href


def fetch_workbook_bytes(client: httpx.Client, url: str) -> bytes:
    r = client.get(url)
    r.raise_for_status()
    return r.content


def parse_data_sheet(wb) -> list[dict]:
    """Extract raw rows from the "ANZ-Indeed Australian Job Ads" sheet."""
    ws = wb[DATA_SHEET_NAME]
    rows = list(ws.iter_rows(values_only=True))
    out: list[dict] = []
    for r in rows:
        d = r[0]
        if not isinstance(d, (datetime.date, datetime.datetime)):
            continue
        out.append({
            "date": d.date() if hasattr(d, "date") else d,
            "original": r[1],
            "sa": r[2],
            "trend": r[3],
        })
    return out


_VARIANTS = (
    ("INDEX", "sa", "Seasonally Adjusted", True),
    ("INDEX_TREND", "trend", "Trend", False),
    ("INDEX_ORIG", "original", "Original", False),
)


def rows_to_records(
    raw_rows: list[dict],
    *,
    since: datetime.date | None = None,
    until: datetime.date | None = None,
    now: datetime.datetime | None = None,
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    now = now or datetime.datetime.now(UTC)
    indicators: dict[str, IndicatorRow] = {}
    observations: list[ObservationRow] = []
    for row in raw_rows:
        d = row["date"]
        if since and d < since:
            continue
        if until and d > until:
            continue
        for variant, field, variant_label, is_sa in _VARIANTS:
            v = row.get(field)
            if v is None:
                continue
            imdr_code = f"ANZ.JOBADS.{variant}.NATIONAL.AU"
            if imdr_code not in indicators:
                indicators[imdr_code] = IndicatorRow(
                    imdr_code=imdr_code,
                    vendor_name=VENDOR_NAME,
                    source_code=f"ANZ.JOBADS.{variant}.NATIONAL",
                    display_name=(
                        f"ANZ-Indeed Australian Job Ads — National "
                        f"({variant_label}, 2019=100)"
                    ),
                    unit="index",
                    frequency="MONTHLY",
                    country_iso="AU",
                    category="labour",
                    is_seasonally_adjusted=is_sa,
                )
            observations.append(ObservationRow(
                imdr_code=imdr_code, obs_date=d, vintage=0,
                release_date=now, value=float(v), ingested_at=now,
            ))
    return list(indicators.values()), observations


def build_rows(
    since: str | None = None,
    until: str | None = None,
) -> tuple[list[IndicatorRow], list[ObservationRow]]:
    import openpyxl

    lo = datetime.date.fromisoformat(since) if since else None
    hi = datetime.date.fromisoformat(until) if until else None

    with _make_client() as client:
        html = fetch_release_dates_html(client)
        download_url = discover_download_url(html)
        print(f"  data download: {download_url}")
        wb_bytes = fetch_workbook_bytes(client, download_url)

    wb = openpyxl.load_workbook(io.BytesIO(wb_bytes), data_only=True)
    raw_rows = parse_data_sheet(wb)
    indicators, observations = rows_to_records(raw_rows, since=lo, until=hi)

    print(f"  JOBADS  n_raw_rows={len(raw_rows)} n_indicators={len(indicators)} n_obs={len(observations)}")

    return indicators, observations
